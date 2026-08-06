#!/usr/bin/env python3
# ruff: noqa: RUF001, RUF100 -- Chinese punctuation is part of the Markdown contract.
"""Validate local-model guidance drafts and atomically publish an enriched run.

This script is deliberately offline and uses only the Python standard library.
The running Codex or Claude instance creates drafts; this script never calls a
model API and never changes deterministic JSON or scores.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import shutil
import stat
import sys
import tempfile
import uuid
from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Any

SCHEMA_VERSION = "1.0"
MAX_MARKDOWN_BYTES = 1_048_576
MAX_JSON_BYTES = 8_388_608
REQUIRED_ANALYSIS_FILES = {
    "analysis.json",
    "extracted.json",
    "score.json",
    "suggestions.md",
}
SHA256_RE = re.compile(r"^[0-9a-fA-F]{64}$")
SAFE_NAME_RE = re.compile(r"^[^/\\\x00-\x1f\x7f]+$")
MARKER_RE = re.compile(r"\[(E|S|R)([1-9][0-9]*)\]")
DEFINITION_RE = re.compile(r"^- \[([ESR][1-9][0-9]*)\] (\S+)$")
QUESTION_RE = re.compile(r"(?m)^#{2,3}\s+(10|[1-9])[.、)]\s+.+$")
EMAIL_RE = re.compile(r"(?i)(?<![\w.+-])[\w.+-]+@[\w-]+(?:\.[\w-]+)+")
PHONE_RE = re.compile(r"(?<!\d)(?:\+?86[- ]?)?1[3-9]\d{9}(?!\d)")
INSTRUCTION_RE = re.compile(
    r"(?i)(?:ignore\s+(?:all\s+)?previous|system\s+prompt|developer\s+message|"
    r"reveal\s+(?:the\s+)?prompt|execute\s+(?:this\s+)?command|tool\s+call|"
    r"忽略(?:以上|之前|前面).{0,12}(?:指令|要求)|系统提示(?:词|内容)?|"
    r"开发者消息|执行(?:以下|这个|上述).{0,8}(?:命令|代码)|调用.{0,8}工具|"
    r"泄露.{0,8}(?:提示词|密钥|环境变量))"
)
SCORE_RESTATEMENT_RE = re.compile(
    r"(?i)(?:技术证据覆盖总分|整体证据覆盖等级|总分|维度(?:得分|评分)|证据分|"
    r"质量(?:诊断)?分|诊断分)\s*(?:为|是|达到|[:：])?\s*"
    r"(?:[0-9]+(?:\.[0-9]+)?(?:\s*/\s*10)?|[A-F](?:\+)?)"
)
REQUIRED_SUGGESTION_SECTIONS = ("逐段经历点评", "改写示例", "成长建议")
LLM_ENHANCEMENT_HEADING = "# 本地 LLM 个性化增强"
QUESTION_LABELS = ("主问题：", "针对性追问：", "核验要点：")
FAILURE_CODES = {
    "contact_detected",
    "incomplete_draft",
    "instruction_like_content",
    "invalid_citation",
    "invalid_question_count",
    "invalid_structure",
    "invalid_utf8",
    "missing_draft",
    "oversized_draft",
    "score_restatement_detected",
}


class FinalizationError(RuntimeError):
    """A global validation or atomic-publication error."""


class CandidateDraftError(RuntimeError):
    """A sanitized, candidate-local validation error."""

    def __init__(self, code: str) -> None:
        if code not in FAILURE_CODES:
            raise ValueError("unknown candidate draft failure code")
        super().__init__(code)
        self.code = code


@dataclass(frozen=True)
class RawEvidence:
    digest: str
    line_count: int


@dataclass(frozen=True)
class CandidateInput:
    output_name: str
    directory: Path
    extracted: Any
    score: Any
    source_hashes: tuple[str, ...]


@dataclass(frozen=True)
class ValidatedDraft:
    suggestions: str
    questions: str
    citation_counts: Mapping[str, int]


def _sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def _read_bytes(path: Path, limit: int) -> bytes:
    if path.is_symlink() or not path.is_file():
        raise FinalizationError("required input is not a regular file")
    if path.stat().st_size > limit:
        raise FinalizationError("required input exceeds its size limit")
    return path.read_bytes()


def _read_json(path: Path) -> tuple[Any, bytes]:
    raw = _read_bytes(path, MAX_JSON_BYTES)
    try:
        return json.loads(raw.decode("utf-8")), raw
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise FinalizationError("required JSON is not valid UTF-8 JSON") from exc


def _read_draft(path: Path) -> str:
    if path.is_symlink() or not path.is_file():
        raise CandidateDraftError("incomplete_draft")
    if path.stat().st_size > MAX_MARKDOWN_BYTES:
        raise CandidateDraftError("oversized_draft")
    try:
        return path.read_bytes().decode("utf-8")
    except UnicodeDecodeError as exc:
        raise CandidateDraftError("invalid_utf8") from exc


def _validate_name(name: str) -> None:
    if (
        not name
        or name in {".", ".."}
        or Path(name).name != name
        or not SAFE_NAME_RE.fullmatch(name)
    ):
        raise FinalizationError("unsafe candidate output name")


def _assert_private_tree(root: Path) -> Path:
    if root.is_symlink() or not root.is_dir():
        raise FinalizationError("input root must be a regular directory")
    resolved = root.resolve(strict=True)
    for path in (root, *root.rglob("*")):
        if path.is_symlink():
            raise FinalizationError("symbolic links are not allowed")
        mode = stat.S_IMODE(path.stat().st_mode)
        expected = 0o700 if path.is_dir() else 0o600
        if mode != expected:
            raise FinalizationError(f"private input permissions required ({expected:04o})")
        if not path.is_dir() and not path.is_file():
            raise FinalizationError("special filesystem entries are not allowed")
    return resolved


def _source_hashes(score: Any) -> tuple[str, ...]:
    if not isinstance(score, Mapping):
        raise FinalizationError("score JSON must be an object")
    values: set[str] = set()
    raw_hashes = score.get("source_hashes", [])
    if isinstance(raw_hashes, list):
        for value in raw_hashes:
            if isinstance(value, str) and SHA256_RE.fullmatch(value):
                values.add(value.lower())
    input_digest = score.get("input_sha256")
    if not values and isinstance(input_digest, str) and SHA256_RE.fullmatch(input_digest):
        values.add(input_digest.lower())
    audit = score.get("source_mapping_audit")
    audits: list[Any] = [audit] if isinstance(audit, Mapping) else []
    multiple = score.get("source_mapping_audits")
    if isinstance(multiple, list):
        audits.extend(multiple)
    for item in audits:
        if isinstance(item, Mapping):
            digest = item.get("raw_source_sha256")
            if isinstance(digest, str) and SHA256_RE.fullmatch(digest):
                values.add(digest.lower())
    if not values:
        raise FinalizationError("score JSON has no valid source hash")
    return tuple(sorted(values))


def _load_candidates(run_root: Path) -> tuple[list[CandidateInput], bytes | None]:
    _assert_private_tree(run_root)
    allowed_root_entries = {"resume_analysis", "interview_questions", "batch_summary.json"}
    if {path.name for path in run_root.iterdir()} - allowed_root_entries:
        raise FinalizationError("deterministic run contains an unexpected entry")
    analysis_root = run_root / "resume_analysis"
    question_root = run_root / "interview_questions"
    if not analysis_root.is_dir() or not question_root.is_dir():
        raise FinalizationError("deterministic run layout is incomplete")
    candidates: list[CandidateInput] = []
    question_entries = list(question_root.iterdir())
    if any(
        path.is_symlink() or not path.is_file() or path.suffix != ".md" for path in question_entries
    ):
        raise FinalizationError("deterministic interview directory contains an unsafe entry")
    question_names = {path.stem for path in question_entries}
    for directory in sorted(analysis_root.iterdir(), key=lambda item: item.name):
        if directory.is_symlink() or not directory.is_dir():
            raise FinalizationError("analysis root contains an unsafe entry")
        _validate_name(directory.name)
        actual = {path.name for path in directory.iterdir()}
        if actual != REQUIRED_ANALYSIS_FILES:
            raise FinalizationError("deterministic candidate file set is invalid")
        if directory.name not in question_names:
            raise FinalizationError("deterministic interview file is missing")
        extracted, _ = _read_json(directory / "extracted.json")
        score, _ = _read_json(directory / "score.json")
        analysis, _ = _read_json(directory / "analysis.json")
        if not isinstance(score, Mapping) or score.get("output_name") != directory.name:
            raise FinalizationError("score output name does not match its directory")
        if not isinstance(analysis, Mapping) or analysis.get("output_name") != directory.name:
            raise FinalizationError("analysis output name does not match its directory")
        candidates.append(
            CandidateInput(
                output_name=directory.name,
                directory=directory,
                extracted=extracted,
                score=score,
                source_hashes=_source_hashes(score),
            )
        )
        candidate = candidates[-1]
        deterministic_reports = (
            directory / "suggestions.md",
            question_root / f"{directory.name}.md",
        )
        for report in deterministic_reports:
            raw_report = _read_bytes(report, MAX_MARKDOWN_BYTES)
            try:
                report_text = raw_report.decode("utf-8")
            except UnicodeDecodeError as exc:
                raise FinalizationError("deterministic Markdown is not valid UTF-8") from exc
            if _contains_contact(report_text, candidate):
                raise FinalizationError("deterministic Markdown contains contact data")
            if INSTRUCTION_RE.search(report_text):
                raise FinalizationError("deterministic Markdown contains instruction-like content")
    expected = {item.output_name for item in candidates}
    if not candidates or question_names != expected:
        raise FinalizationError("deterministic candidate set is inconsistent")
    summary = run_root / "batch_summary.json"
    summary_bytes = _read_bytes(summary, MAX_JSON_BYTES) if summary.exists() else None
    if summary_bytes is not None:
        try:
            json.loads(summary_bytes.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise FinalizationError("batch summary is not valid UTF-8 JSON") from exc
    return candidates, summary_bytes


def _load_raw_index(root: Path | None) -> Mapping[str, RawEvidence]:
    if root is None:
        return {}
    _assert_private_tree(root)
    result: dict[str, RawEvidence] = {}
    for path in sorted(root.rglob("raw_extraction.json")):
        value, _ = _read_json(path)
        if not isinstance(value, Mapping):
            raise FinalizationError("raw extraction must be a JSON object")
        digest = value.get("source_sha256")
        full_text = value.get("full_text")
        if (
            value.get("content_trust") != "untrusted"
            or not isinstance(digest, str)
            or not SHA256_RE.fullmatch(digest)
            or not isinstance(full_text, str)
            or not full_text.strip()
        ):
            raise FinalizationError("raw extraction contract is invalid")
        digest = digest.lower()
        evidence = RawEvidence(digest=digest, line_count=max(1, len(full_text.splitlines())))
        existing = result.get(digest)
        if existing is not None and existing != evidence:
            raise FinalizationError("conflicting raw extraction hashes")
        result[digest] = evidence
    if not result:
        raise FinalizationError("raw extraction directory contains no evidence")
    return result


def _resolve_pointer(document: Any, pointer: str) -> Any:
    if pointer == "":
        return document
    if not pointer.startswith("/"):
        raise KeyError(pointer)
    current = document
    for encoded in pointer[1:].split("/"):
        token = encoded.replace("~1", "/").replace("~0", "~")
        if isinstance(current, list):
            if not token.isdigit() or (len(token) > 1 and token.startswith("0")):
                raise KeyError(pointer)
            current = current[int(token)]
        elif isinstance(current, Mapping) and token in current:
            current = current[token]
        else:
            raise KeyError(pointer)
    return current


def _split_evidence_index(text: str) -> tuple[str, str]:
    matches = list(re.finditer(r"(?m)^#{2,3}\s+证据索引\s*$", text))
    if len(matches) != 1:
        raise CandidateDraftError("invalid_structure")
    match = matches[0]
    return text[: match.start()].rstrip(), text[match.end() :].strip()


def _parse_definitions(index: str) -> Mapping[str, str]:
    definitions: dict[str, str] = {}
    for line in index.splitlines():
        if not line.strip():
            continue
        match = DEFINITION_RE.fullmatch(line.strip())
        if match is None or match.group(1) in definitions:
            raise CandidateDraftError("invalid_citation")
        definitions[match.group(1)] = match.group(2)
    if not definitions:
        raise CandidateDraftError("invalid_citation")
    return definitions


def _weak_dimensions(score: Any) -> set[str]:
    if not isinstance(score, Mapping):
        return set()
    dimensions = score.get("dimension_scores")
    if not isinstance(dimensions, Mapping):
        return set()
    ranked: list[tuple[float, str]] = []
    weak: set[str] = set()
    for name, item in dimensions.items():
        if not isinstance(name, str) or not isinstance(item, Mapping):
            continue
        value = item.get("score")
        if isinstance(value, int | float):
            ranked.append((float(value), name))
        missing = item.get("missing_evidence_groups")
        if isinstance(missing, list) and missing:
            weak.add(name)
    weak.update(name for _, name in sorted(ranked)[:2])
    return weak


def _validate_target(
    marker: str,
    target: str,
    candidate: CandidateInput,
    raw_index: Mapping[str, RawEvidence],
) -> None:
    kind = marker[0]
    if kind == "E":
        prefix = "extracted.json#"
        document = candidate.extracted
    elif kind == "S":
        prefix = "score.json#"
        document = candidate.score
    else:
        match = re.fullmatch(r"raw:([0-9a-fA-F]{64})#L([1-9][0-9]*)-L([1-9][0-9]*)", target)
        if match is None:
            raise CandidateDraftError("invalid_citation")
        digest = match.group(1).lower()
        start, end = int(match.group(2)), int(match.group(3))
        evidence = raw_index.get(digest)
        if (
            evidence is None
            or digest not in candidate.source_hashes
            or start > end
            or end > evidence.line_count
        ):
            raise CandidateDraftError("invalid_citation")
        return
    if not target.startswith(prefix):
        raise CandidateDraftError("invalid_citation")
    try:
        _resolve_pointer(document, target[len(prefix) :])
    except (IndexError, KeyError) as exc:
        raise CandidateDraftError("invalid_citation") from exc


def _validate_citations(
    text: str,
    candidate: CandidateInput,
    raw_index: Mapping[str, RawEvidence],
) -> tuple[str, Mapping[str, str], Mapping[str, int]]:
    body, index = _split_evidence_index(text)
    definitions = _parse_definitions(index)
    used = [f"{kind}{number}" for kind, number in MARKER_RE.findall(body)]
    if not used or set(used) != set(definitions):
        raise CandidateDraftError("invalid_citation")
    for marker, target in definitions.items():
        if marker[0] == "E" and not target.startswith("extracted.json#"):
            raise CandidateDraftError("invalid_citation")
        if marker[0] == "S" and not target.startswith("score.json#"):
            raise CandidateDraftError("invalid_citation")
        _validate_target(marker, target, candidate, raw_index)
    counts = {
        "extracted": sum(marker.startswith("E") for marker in used),
        "score": sum(marker.startswith("S") for marker in used),
        "raw": sum(marker.startswith("R") for marker in used),
    }
    return body, definitions, counts


def _contact_tokens(candidate: CandidateInput) -> set[str]:
    if not isinstance(candidate.extracted, Mapping):
        return set()
    basic_info = candidate.extracted.get("basic_info")
    contact = basic_info.get("contact") if isinstance(basic_info, Mapping) else None
    if not isinstance(contact, Mapping):
        return set()
    return {
        value.strip().casefold()
        for value in contact.values()
        if isinstance(value, str) and len(value.strip()) >= 4
    }


def _contains_contact(text: str, candidate: CandidateInput) -> bool:
    if EMAIL_RE.search(text) or PHONE_RE.search(text):
        return True
    folded = text.casefold()
    return any(token in folded for token in _contact_tokens(candidate))


def _reject_unsafe_draft(text: str, candidate: CandidateInput) -> None:
    if _contains_contact(text, candidate):
        raise CandidateDraftError("contact_detected")
    if INSTRUCTION_RE.search(text):
        raise CandidateDraftError("instruction_like_content")


def _validate_suggestions(
    text: str,
    candidate: CandidateInput,
    raw_index: Mapping[str, RawEvidence],
) -> Mapping[str, int]:
    _reject_unsafe_draft(text, candidate)
    body, _, counts = _validate_citations(text, candidate, raw_index)
    headings = re.findall(r"(?m)^(#{1,6})\s+(.+?)\s*$", body)
    expected_headings = [("##", heading) for heading in REQUIRED_SUGGESTION_SECTIONS]
    if headings != expected_headings:
        raise CandidateDraftError("invalid_structure")
    if SCORE_RESTATEMENT_RE.search(body):
        raise CandidateDraftError("score_restatement_detected")
    bullet_count = 0
    for line in body.splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        if not stripped.startswith(("- ", "* ")):
            raise CandidateDraftError("invalid_structure")
        bullet_count += 1
        if MARKER_RE.search(line) is None:
            raise CandidateDraftError("invalid_citation")
    if bullet_count < 4:
        raise CandidateDraftError("invalid_structure")
    return counts


def _question_blocks(body: str) -> list[str]:
    matches = list(QUESTION_RE.finditer(body))
    if [int(match.group(1)) for match in matches] != list(range(1, 11)):
        raise CandidateDraftError("invalid_question_count")
    return [
        body[match.start() : matches[index + 1].start() if index + 1 < len(matches) else len(body)]
        for index, match in enumerate(matches)
    ]


def _score_marker_is_weak(marker: str, target: str, weak: set[str]) -> bool:
    if not marker.startswith("S") or not target.startswith("score.json#/dimension_scores/"):
        return False
    remainder = target.removeprefix("score.json#/dimension_scores/")
    dimension = remainder.split("/", 1)[0].replace("~1", "/").replace("~0", "~")
    return dimension in weak or "/missing_evidence_groups" in target


def _validate_questions(
    text: str,
    candidate: CandidateInput,
    raw_index: Mapping[str, RawEvidence],
) -> Mapping[str, int]:
    _reject_unsafe_draft(text, candidate)
    body, definitions, counts = _validate_citations(text, candidate, raw_index)
    blocks = _question_blocks(body)
    grounded_count = 0
    weak_count = 0
    weak = _weak_dimensions(candidate.score)
    for block in blocks:
        for line in block.splitlines():
            stripped = line.strip()
            if not stripped or stripped.startswith("#"):
                continue
            if not stripped.startswith(("- ", "* ")):
                raise CandidateDraftError("invalid_structure")
            if MARKER_RE.search(line) is None:
                raise CandidateDraftError("invalid_citation")
        for label in QUESTION_LABELS:
            matching_lines = [line for line in block.splitlines() if label in line]
            if len(matching_lines) != 1 or MARKER_RE.search(matching_lines[0]) is None:
                raise CandidateDraftError("invalid_structure")
        markers = {f"{kind}{number}" for kind, number in MARKER_RE.findall(block)}
        targets = {marker: definitions[marker] for marker in markers}
        if any(
            marker.startswith("R")
            or (
                marker.startswith("E")
                and any(
                    segment in target
                    for segment in ("#/projects/", "#/internships/", "#/security_activities/")
                )
            )
            for marker, target in targets.items()
        ):
            grounded_count += 1
        if any(_score_marker_is_weak(marker, target, weak) for marker, target in targets.items()):
            weak_count += 1
    if grounded_count < 6 or weak_count < 2:
        raise CandidateDraftError("invalid_structure")
    return counts


def _validate_draft(
    draft_directory: Path,
    candidate: CandidateInput,
    raw_index: Mapping[str, RawEvidence],
) -> ValidatedDraft:
    suggestions = _read_draft(draft_directory / "suggestions.md")
    questions = _read_draft(draft_directory / "interview_questions.md")
    suggestion_counts = _validate_suggestions(suggestions, candidate, raw_index)
    question_counts = _validate_questions(questions, candidate, raw_index)
    counts = {
        key: int(suggestion_counts[key]) + int(question_counts[key])
        for key in ("extracted", "score", "raw")
    }
    return ValidatedDraft(suggestions.rstrip() + "\n", questions.rstrip() + "\n", counts)


def _validate_draft_root(root: Path | None, candidate_names: set[str]) -> Path | None:
    if root is None or not root.exists():
        return None
    resolved = _assert_private_tree(root)
    entries = {path.name for path in root.iterdir()}
    if not entries.issubset(candidate_names):
        raise FinalizationError("draft directory contains an unexpected candidate")
    for path in root.iterdir():
        if not path.is_dir():
            raise FinalizationError("draft root may contain only candidate directories")
        _validate_name(path.name)
        allowed = {"suggestions.md", "interview_questions.md"}
        if {item.name for item in path.iterdir()} - allowed:
            raise FinalizationError("draft candidate contains an unexpected file")
    return resolved


def _write_bytes(path: Path, value: bytes) -> None:
    path.write_bytes(value)
    path.chmod(0o600)


def _write_text(path: Path, value: str) -> None:
    _write_bytes(path, value.encode("utf-8"))


def _mkdir(path: Path) -> None:
    path.mkdir(mode=0o700, parents=False, exist_ok=False)


def _generator_label(generator: str) -> str:
    return "Codex" if generator == "codex" else "Claude"


def _suggestions_mode_header(generator: str, fallback_reason: str | None) -> str:
    if fallback_reason is None:
        return (
            f"> 生成模式：本地 {_generator_label(generator)} 个性化增强；"
            "确定性报告与评分未修改。\n\n"
        )
    return (
        f"> 生成模式：确定性模板回退（原因：`{fallback_reason}`）；未生成本地模型个性化增强。\n\n"
    )


def _questions_mode_header(generator: str, fallback_reason: str | None) -> str:
    if fallback_reason is None:
        return (
            f"> 生成模式：本地 {_generator_label(generator)} 个性化面试题；确定性评分未修改。\n\n"
        )
    return (
        f"> 生成模式：确定性模板回退（原因：`{fallback_reason}`）；未生成本地模型个性化面试题。\n\n"
    )


def _merge_suggestions(deterministic: bytes, guidance: str, generator: str) -> bytes:
    separator = (
        b""
        if deterministic.endswith(b"\n\n")
        else b"\n"
        if deterministic.endswith(b"\n")
        else b"\n\n"
    )
    return (
        _suggestions_mode_header(generator, None).encode()
        + deterministic
        + separator
        + LLM_ENHANCEMENT_HEADING.encode()
        + b"\n\n"
        + guidance.encode()
    )


def _single_summary() -> bytes:
    value = {
        "schema_version": "guidance-1.0",
        "status": "single_candidate",
        "note": (
            "Generated by the guidance finalizer because the deterministic single run "
            "had no batch summary."
        ),
    }
    return (json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n").encode()


def _copy_candidate(
    staging: Path,
    deterministic_run: Path,
    candidate: CandidateInput,
    draft: ValidatedDraft | None,
    generator: str,
    fallback_reason: str | None,
) -> Mapping[str, Any]:
    analyses = staging / "resume_analysis"
    deterministic_questions = staging / "deterministic_interview_questions"
    questions = staging / "interview_questions"
    destination = analyses / candidate.output_name
    _mkdir(destination)
    for filename in ("extracted.json", "score.json", "analysis.json"):
        _write_bytes(destination / filename, (candidate.directory / filename).read_bytes())
    deterministic_suggestions = (candidate.directory / "suggestions.md").read_bytes()
    deterministic_question_path = (
        deterministic_run / "interview_questions" / f"{candidate.output_name}.md"
    )
    deterministic_interview = deterministic_question_path.read_bytes()
    _write_bytes(destination / "deterministic_suggestions.md", deterministic_suggestions)
    _write_bytes(deterministic_questions / f"{candidate.output_name}.md", deterministic_interview)
    if draft is None:
        final_suggestions = (
            _suggestions_mode_header(generator, fallback_reason).encode()
            + deterministic_suggestions
        )
        final_questions = (
            _questions_mode_header(generator, fallback_reason).encode() + deterministic_interview
        )
        counts = {"extracted": 0, "score": 0, "raw": 0}
        mode = "deterministic_fallback"
    else:
        final_suggestions = _merge_suggestions(
            deterministic_suggestions,
            draft.suggestions,
            generator,
        )
        final_questions = (_questions_mode_header(generator, None) + draft.questions).encode()
        counts = dict(draft.citation_counts)
        mode = "llm"
    _write_bytes(destination / "suggestions.md", final_suggestions)
    _write_bytes(questions / f"{candidate.output_name}.md", final_questions)
    return {
        "output_name": candidate.output_name,
        "mode": mode,
        "fallback_reason": fallback_reason,
        "source_hashes": list(candidate.source_hashes),
        "citation_counts": counts,
        "artifacts": {
            "analysis_sha256": _sha256_bytes((candidate.directory / "analysis.json").read_bytes()),
            "deterministic_interview_questions_sha256": _sha256_bytes(deterministic_interview),
            "deterministic_suggestions_sha256": _sha256_bytes(deterministic_suggestions),
            "extracted_sha256": _sha256_bytes(
                (candidate.directory / "extracted.json").read_bytes()
            ),
            "interview_questions_sha256": _sha256_bytes(final_questions),
            "score_sha256": _sha256_bytes((candidate.directory / "score.json").read_bytes()),
            "suggestions_sha256": _sha256_bytes(final_suggestions),
        },
    }


def _build_staging(
    staging: Path,
    deterministic_run: Path,
    candidates: Iterable[CandidateInput],
    draft_root: Path | None,
    raw_index: Mapping[str, RawEvidence],
    generator: str,
    summary_bytes: bytes | None,
) -> Mapping[str, Any]:
    for dirname in (
        "resume_analysis",
        "deterministic_interview_questions",
        "interview_questions",
    ):
        _mkdir(staging / dirname)
    records: list[Mapping[str, Any]] = []
    llm_count = 0
    fallback_count = 0
    for candidate in candidates:
        draft: ValidatedDraft | None = None
        reason: str | None = None
        directory = draft_root / candidate.output_name if draft_root is not None else None
        if directory is None or not directory.exists():
            reason = "missing_draft"
        else:
            try:
                draft = _validate_draft(directory, candidate, raw_index)
            except CandidateDraftError as exc:
                reason = exc.code
        if draft is None:
            fallback_count += 1
        else:
            llm_count += 1
        records.append(
            _copy_candidate(
                staging,
                deterministic_run,
                candidate,
                draft,
                generator,
                reason,
            )
        )
    total = llm_count + fallback_count
    status = (
        "complete" if fallback_count == 0 else "fallback" if llm_count == 0 else "partial_fallback"
    )
    manifest = {
        "schema_version": SCHEMA_VERSION,
        "status": status,
        "generator_requested": generator,
        "counts": {"total": total, "llm": llm_count, "fallback": fallback_count},
        "candidates": records,
    }
    _write_text(
        staging / "guidance_manifest.json",
        json.dumps(manifest, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
    )
    _write_bytes(staging / "batch_summary.json", summary_bytes or _single_summary())
    return manifest


def _validate_output_path(output: Path, deterministic_run: Path, overwrite: bool) -> Path:
    parent = output.parent
    if not parent.exists() or parent.is_symlink() or not parent.is_dir():
        raise FinalizationError("output parent must be an existing regular directory")
    _validate_name(output.name)
    deterministic_resolved = deterministic_run.resolve(strict=True)
    prospective = parent.resolve(strict=True) / output.name
    if _paths_overlap(prospective, deterministic_resolved):
        raise FinalizationError("output must be disjoint from the deterministic run")
    if output.is_symlink():
        raise FinalizationError("output may not be a symbolic link")
    if output.exists() and not overwrite:
        raise FinalizationError("output already exists; use --overwrite explicitly")
    if output.exists() and not output.is_dir():
        raise FinalizationError("existing output is not a directory")
    return prospective


def _paths_overlap(left: Path, right: Path) -> bool:
    return left == right or left in right.parents or right in left.parents


def finalize(
    *,
    deterministic_run: Path,
    draft_dir: Path | None,
    output_dir: Path,
    generator: str,
    raw_extraction_dir: Path | None,
    overwrite: bool,
) -> Mapping[str, Any]:
    if generator not in {"codex", "claude"}:
        raise FinalizationError("unsupported guidance generator")
    deterministic_run = _assert_private_tree(deterministic_run)
    output_dir = _validate_output_path(output_dir, deterministic_run, overwrite)
    candidates, summary_bytes = _load_candidates(deterministic_run)
    names = {candidate.output_name for candidate in candidates}
    draft_root = _validate_draft_root(draft_dir, names)
    raw_index = _load_raw_index(raw_extraction_dir)
    if draft_root is not None and _paths_overlap(output_dir, draft_root):
        raise FinalizationError("output must be disjoint from the draft directory")
    if raw_extraction_dir is not None:
        raw_root = raw_extraction_dir.resolve(strict=True)
        if _paths_overlap(output_dir, raw_root):
            raise FinalizationError("output must be disjoint from the raw extraction directory")
    parent = output_dir.parent
    previous_umask = os.umask(0o077)
    staging: Path | None = None
    backup: Path | None = None
    try:
        staging = Path(tempfile.mkdtemp(prefix=f".{output_dir.name}.staging-", dir=parent))
        staging.chmod(0o700)
        manifest = _build_staging(
            staging,
            deterministic_run,
            candidates,
            draft_root,
            raw_index,
            generator,
            summary_bytes,
        )
        if os.environ.get("LOCAL_GUIDANCE_TEST_FAIL_AT") == "before_publish":
            raise OSError("injected failure before publish")
        if output_dir.exists():
            backup = parent / f".{output_dir.name}.backup-{uuid.uuid4().hex}"
            os.replace(output_dir, backup)
        try:
            if os.environ.get("LOCAL_GUIDANCE_TEST_FAIL_AT") == "after_backup":
                raise OSError("injected failure after backup")
            os.replace(staging, output_dir)
        except Exception:
            if backup is not None and backup.exists() and not output_dir.exists():
                os.replace(backup, output_dir)
            raise
        if backup is not None:
            try:
                shutil.rmtree(backup)
            except Exception:
                os.replace(output_dir, staging)
                os.replace(backup, output_dir)
                raise
        return manifest
    except Exception as exc:
        if isinstance(exc, FinalizationError):
            raise
        raise FinalizationError("atomic guidance publication failed") from exc
    finally:
        os.umask(previous_umask)
        if staging is not None and staging.exists():
            shutil.rmtree(staging)


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Validate local Codex/Claude guidance and atomically publish an enriched run."
    )
    parser.add_argument("--deterministic-run", type=Path, required=True)
    parser.add_argument("--draft-dir", type=Path)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--generator", choices=("codex", "claude"), required=True)
    parser.add_argument("--raw-extraction-dir", type=Path)
    parser.add_argument("--overwrite", action="store_true")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    try:
        manifest = finalize(
            deterministic_run=args.deterministic_run,
            draft_dir=args.draft_dir,
            output_dir=args.output_dir,
            generator=args.generator,
            raw_extraction_dir=args.raw_extraction_dir,
            overwrite=args.overwrite,
        )
    except FinalizationError as exc:
        print(f"guidance finalization failed: {exc}", file=sys.stderr)
        return 5
    print(
        json.dumps(
            {
                "status": manifest["status"],
                "counts": manifest["counts"],
                "output_dir": str(args.output_dir),
            },
            ensure_ascii=False,
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
