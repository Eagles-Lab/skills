"""Shared deterministic primitives for auditing canonical facts against raw text."""

from __future__ import annotations

import hashlib
import json
import re
import unicodedata
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping, Sequence

SOURCE_MAPPING_AUDIT_VERSION = "2.0.0"
MAX_RAW_EXTRACTION_BYTES = 25 * 1024 * 1024

_SHA256_PATTERN = re.compile(r"^[a-fA-F0-9]{64}$")
_ASCII_TOKEN_PATTERN = re.compile(r"^[A-Za-z0-9_.+#/@:%‰\- \t]+$")
_ASCII_LEFT_TOKEN_BOUNDARY = r"A-Za-z0-9_.+#/@%‰~\-"
_ASCII_RIGHT_TOKEN_BOUNDARY = r"A-Za-z0-9_+#/@%‰~\-"
_EMPTY_SECTION_CONTENT_PATTERN = re.compile(
    r"^(?:无|暂无|没有|未有|待补充|未填写|none|n/?a|not\s+provided)?$",
    re.IGNORECASE,
)
_CLAUSE_SPLIT_PATTERN = re.compile(
    r"[,\uff0c;\uff1b\u3002\uff01\uff1f!?]+|(?<![A-Za-z0-9])\.|\.(?![A-Za-z0-9])"
)
_CLAUSE_BOUNDARY = "\x00"
_ASCII_WORD_BOUNDARY = "\x01"
_NEGATION_CONTEXT_CHARS = 96
_ALIAS_GROUPS: tuple[tuple[str, tuple[str, ...]], ...] = (
    ("kubernetes", ("kubernetes", "k8s")),
    ("go", ("go", "golang")),
    ("javascript", ("javascript", "js")),
    ("typescript", ("typescript", "ts")),
    ("postgresql", ("postgresql", "postgres")),
    ("shell", ("shell", "bash")),
)
_ALIASES: Mapping[str, tuple[str, ...]] = {
    alias: aliases for _, aliases in _ALIAS_GROUPS for alias in aliases
}


@dataclass(frozen=True)
class RawExtraction:
    """Validated privacy-sensitive extraction data used only during the audit."""

    full_text: str
    source_sha256: str


@dataclass(frozen=True)
class FactClaim:
    """One explicitly registered canonical leaf and its grounding rule."""

    pointer: str
    value: str | int
    match_kind: str = "direct"
    candidates: tuple[str, ...] = ()
    scope_text: str | None = None
    scope_values: tuple[str, ...] = ()
    raw_scope_text: str | None = None


@dataclass(frozen=True, order=True)
class AuditViolation:
    """A stable machine-readable failure without sensitive values or excerpts."""

    code: str
    pointer: str


@dataclass(frozen=True)
class SourceMappingAuditResult:
    """Privacy-safe metadata proving the canonical mapping passed audit v2."""

    raw_source_sha256: str
    canonical_facts_sha256: str
    checked_fact_count: int
    warning_codes: tuple[str, ...]

    def public_metadata(self) -> dict[str, Any]:
        return {
            "audit_version": SOURCE_MAPPING_AUDIT_VERSION,
            "passed": True,
            "raw_source_sha256": self.raw_source_sha256,
            "canonical_facts_sha256": self.canonical_facts_sha256,
            "checked_fact_count": self.checked_fact_count,
            "warning_codes": list(self.warning_codes),
        }


@dataclass(frozen=True)
class RecordCollectionScopeResult:
    """Unique raw scopes for canonical records plus privacy-safe coverage failures."""

    scopes: tuple[str, ...]
    violations: tuple[AuditViolation, ...]


@dataclass(frozen=True)
class _EvidenceText:
    normalized: str
    compact: str


def _raise(error_type: type[Exception], code: str, pointer: str = "/") -> None:
    raise error_type(f"{code}@{pointer}")


def load_raw_extraction(path: Path, error_type: type[Exception]) -> RawExtraction:
    """Load one untrusted extraction without following symlinks or leaking content."""

    source = Path(path)
    if source.is_symlink():
        _raise(error_type, "raw_extraction_unsafe_symlink")
    if not source.exists():
        _raise(error_type, "raw_extraction_missing")
    if not source.is_file():
        _raise(error_type, "raw_extraction_not_regular")
    try:
        size = source.stat().st_size
    except OSError:
        _raise(error_type, "raw_extraction_unreadable")
    if size > MAX_RAW_EXTRACTION_BYTES:
        _raise(error_type, "raw_extraction_too_large")
    try:
        payload = source.read_bytes().decode("utf-8")
    except (OSError, UnicodeError):
        _raise(error_type, "raw_extraction_unreadable")
    try:
        value = json.loads(payload)
    except json.JSONDecodeError:
        _raise(error_type, "raw_extraction_invalid_json")
    if not isinstance(value, Mapping):
        _raise(error_type, "raw_extraction_root_not_object")
    if value.get("content_trust") != "untrusted":
        _raise(error_type, "raw_extraction_trust_invalid", "/content_trust")
    full_text = value.get("full_text")
    if not isinstance(full_text, str) or not full_text.strip():
        _raise(error_type, "raw_extraction_full_text_invalid", "/full_text")
    digest = value.get("source_sha256")
    if not isinstance(digest, str) or not _SHA256_PATTERN.fullmatch(digest):
        _raise(error_type, "raw_extraction_sha256_invalid", "/source_sha256")
    return RawExtraction(full_text=full_text, source_sha256=digest.lower())


def normalize_text(value: str) -> str:
    """Normalize width, case, dash variants, and formatting-only characters."""

    normalized = unicodedata.normalize("NFKC", value).casefold()
    normalized = re.sub(r"[\u2010\u2011\u2012\u2013\u2014\u2212]", "-", normalized)
    return "".join(character for character in normalized if unicodedata.category(character) != "Cf")


def ascii_term_pattern(term: str) -> re.Pattern[str]:
    """Compile an ASCII-boundary-safe term matcher."""

    normalized = normalize_text(term).strip()
    escaped = re.escape(normalized).replace(r"\ ", r"\s+")
    return re.compile(r"(?<![A-Za-z0-9_])" + escaped + r"(?![A-Za-z0-9_])", re.I)


def _ascii_fact_pattern(term: str) -> re.Pattern[str]:
    """Compile an exact ASCII token matcher while allowing formatting spaces."""

    normalized = normalize_text(term).strip()
    pieces: list[str] = []
    for character in normalized:
        if character.isspace():
            pieces.append(r"\s+")
        elif character in "._+#/@:%‰~-":
            pieces.append(r"\s*" + re.escape(character) + r"\s*")
        else:
            pieces.append(re.escape(character))
    compact_term = "".join(normalized.split())
    left_boundary = _ASCII_LEFT_TOKEN_BOUNDARY + (
        ":" if compact_term and compact_term[0].isdigit() else ""
    )
    right_boundary = _ASCII_RIGHT_TOKEN_BOUNDARY + (
        ":" if compact_term and compact_term[-1].isdigit() else ""
    )
    return re.compile(
        rf"(?<![{left_boundary}]){''.join(pieces)}"
        rf"(?![{right_boundary}])(?!\.(?=[A-Za-z0-9]))",
        re.I,
    )


def _canonicalize_aliases(value: str) -> str:
    normalized = normalize_text(value)
    for canonical, aliases in _ALIAS_GROUPS:
        for alias in sorted(aliases, key=lambda item: (-len(item), item)):
            normalized = ascii_term_pattern(alias).sub(canonical, normalized)
    return normalized


def _compact(value: str) -> str:
    normalized = _canonicalize_aliases(value)
    following_nonspace = [""] * len(normalized)
    following = ""
    for index in range(len(normalized) - 1, -1, -1):
        following_nonspace[index] = following
        if not normalized[index].isspace():
            following = normalized[index]
    result: list[str] = []
    previous = ""
    line_has_content = False
    for index, character in enumerate(normalized):
        previous_immediate = normalized[index - 1] if index else ""
        following_immediate = normalized[index + 1] if index + 1 < len(normalized) else ""
        previous_is_ascii_token = bool(previous) and (
            (previous.isascii() and previous.isalnum()) or previous in "%‰+#"
        )
        if (
            character.isspace()
            and previous_is_ascii_token
            and following_nonspace[index].isascii()
            and following_nonspace[index].isalnum()
        ):
            if not result or result[-1] != _ASCII_WORD_BOUNDARY:
                result.append(_ASCII_WORD_BOUNDARY)
        elif character.isalnum():
            result.append(character)
        else:
            markdown_heading_marker = character == "#" and not line_has_content
            numeric_infix = (
                character in ".,:/+-" and previous.isdigit() and following_nonspace[index].isdigit()
            )
            numeric_suffix = character in "%‰" and previous.isdigit()
            numeric_postfix = character == "+" and (previous.isdigit() or previous in "%‰")
            numeric_range = (
                character in "-~" and previous in "%‰" and following_nonspace[index].isdigit()
            )
            numeric_comparator = character in "~<>=≤≥≦≧≈≃" and (
                previous.isdigit() or following_nonspace[index].isdigit()
            )
            ascii_infix_punctuation = character in "._/@:-" and (
                bool(previous_immediate)
                and previous_immediate.isascii()
                and previous_immediate.isalnum()
                and bool(following_immediate)
                and following_immediate.isascii()
                and following_immediate.isalnum()
            )
            ascii_suffix_punctuation = character in "+#" and (
                bool(previous_immediate)
                and previous_immediate.isascii()
                and (previous_immediate.isalnum() or previous_immediate in "+#")
            )
            ascii_separator_boundary = (
                previous_is_ascii_token
                and following_nonspace[index].isascii()
                and following_nonspace[index].isalnum()
                and not numeric_infix
                and not numeric_suffix
                and not numeric_postfix
                and not numeric_range
                and not numeric_comparator
                and not ascii_infix_punctuation
                and not ascii_suffix_punctuation
            )
            if markdown_heading_marker:
                if not result or result[-1] != _CLAUSE_BOUNDARY:
                    result.append(_CLAUSE_BOUNDARY)
            elif (
                numeric_infix
                or numeric_suffix
                or numeric_postfix
                or numeric_range
                or numeric_comparator
                or ascii_infix_punctuation
                or ascii_suffix_punctuation
            ):
                result.append(character)
            elif ascii_separator_boundary and (not result or result[-1] != _ASCII_WORD_BOUNDARY):
                result.append(_ASCII_WORD_BOUNDARY)
        if not character.isspace():
            previous = character
        if character in "\r\n":
            line_has_content = False
        elif not character.isspace():
            line_has_content = True
    return "".join(result)


def _evidence_text(value: str) -> _EvidenceText:
    return _EvidenceText(normalized=normalize_text(value), compact=_compact(value))


def fact_is_grounded(value: str | int, raw_text: str, *, aliases: bool = True) -> bool:
    """Return whether a canonical fact is a continuous normalized raw-text claim."""

    claim = normalize_text(str(value)).strip()
    if not claim:
        return False
    evidence = _evidence_text(raw_text)
    if _ASCII_TOKEN_PATTERN.fullmatch(claim):
        candidates: Sequence[str] = (claim,)
        if aliases:
            candidates = _ALIASES.get(claim.casefold(), candidates)
        return any(
            _ascii_fact_pattern(candidate).search(evidence.normalized) for candidate in candidates
        )
    compact = _compact(claim) if aliases else "".join(ch for ch in claim if ch.isalnum())
    source_compact = (
        evidence.compact if aliases else "".join(ch for ch in evidence.normalized if ch.isalnum())
    )
    return bool(compact) and any(
        _compact_match_is_bounded(compact, source_compact, match.start(), match.end())
        for match in re.finditer(re.escape(compact), source_compact)
    )


def _compact_match_is_bounded(claim: str, source: str, start: int, end: int) -> bool:
    """Prevent compact matching from extracting a fact from a longer ASCII token."""

    token_characters = frozenset("abcdefghijklmnopqrstuvwxyz0123456789_.+#/@:%‰~-")
    if claim[0] in token_characters and start > 0 and source[start - 1] in token_characters:
        return False
    return not (
        claim[-1] in token_characters and end < len(source) and source[end] in token_characters
    )


def direct_fact_is_grounded(value: str | int, raw_text: str) -> bool:
    """Ground a direct fact and reject common cases where mapping dropped negation."""

    if not fact_is_grounded(value, raw_text):
        return False
    claim = normalize_text(str(value)).strip()
    numeric_claim = any(character.isdigit() for character in claim)
    normalized_raw = normalize_text(raw_text)
    if _ASCII_TOKEN_PATTERN.fullmatch(claim):
        return any(
            _occurrence_is_positive(
                normalized_raw,
                match.start(),
                match.end(),
                numeric_claim=numeric_claim,
            )
            for item in _ALIASES.get(claim, (claim,))
            for match in _ascii_fact_pattern(item).finditer(normalized_raw)
        )

    clauses = _CLAUSE_SPLIT_PATTERN.split(normalized_raw)
    compact_claim = _compact(claim)
    compact_source = _CLAUSE_BOUNDARY.join(_compact(clause) for clause in clauses)
    if not compact_claim:
        return False
    bridge = re.escape(_CLAUSE_BOUNDARY) + "*"
    pattern = re.compile(bridge.join(re.escape(character) for character in compact_claim))
    for match in pattern.finditer(compact_source):
        if not _compact_match_is_bounded(
            compact_claim,
            compact_source,
            match.start(),
            match.end(),
        ):
            continue
        local_start = max(0, match.start() - _NEGATION_CONTEXT_CHARS)
        boundary = compact_source.rfind(
            _CLAUSE_BOUNDARY,
            local_start,
            match.start(),
        )
        prefix_start = boundary + 1 if boundary >= 0 else local_start
        suffix_end = compact_source.find(
            _CLAUSE_BOUNDARY,
            match.end(),
            match.end() + _NEGATION_CONTEXT_CHARS + 1,
        )
        if suffix_end < 0:
            suffix_end = len(compact_source)
        suffix_end = min(suffix_end, match.end() + _NEGATION_CONTEXT_CHARS)
        if _compact_context_is_positive(
            compact_source[prefix_start : match.start()],
            compact_source[match.end() : suffix_end],
            numeric_claim=numeric_claim,
        ):
            return True
    return False


def _occurrence_is_positive(
    source: str,
    start: int,
    end: int,
    *,
    numeric_claim: bool = False,
) -> bool:
    prefix_source = source[max(0, start - _NEGATION_CONTEXT_CHARS) : start]
    separators = tuple(_CLAUSE_SPLIT_PATTERN.finditer(prefix_source))
    if separators:
        prefix_source = prefix_source[separators[-1].end() :]
    suffix_source = source[end : end + _NEGATION_CONTEXT_CHARS]
    separator = _CLAUSE_SPLIT_PATTERN.search(suffix_source)
    if separator is not None:
        suffix_source = suffix_source[: separator.start()]
    prefix = _compact(prefix_source)
    suffix = _compact(suffix_source)
    return _compact_context_is_positive(prefix, suffix, numeric_claim=numeric_claim)


def _compact_context_is_positive(
    prefix: str,
    suffix: str,
    *,
    numeric_claim: bool = False,
) -> bool:
    prefix = prefix.replace(_ASCII_WORD_BOUNDARY, "")
    suffix = suffix.replace(_ASCII_WORD_BOUNDARY, "")
    if numeric_claim:
        approximate_prefix = re.search(
            r"(?:约为|大约为|估计为|约|大约|不到|超过|近|至少|至多|最多|最少|"
            r"不少于|不低于|不超过|不高于|估算)$|(?:[~<>≤≥≦≧≈≃]=?|=)$|"
            r"(?:about|approximately|around|nearly|over|under|atleast|atmost|"
            r"minimum|maximum|estimated)$",
            prefix,
            re.I,
        )
        approximate_suffix = re.match(
            r"(?:左右|上下|以上|以下|以内|估算|大约|约|多|余|起|最少|最多|"
            r"或更多|或更少|及以上|及以下|至|到|[-~+])|"
            r"(?:approximately|about|around|ormore|orless|minimum|maximum|estimated)",
            suffix,
            re.I,
        )
        if approximate_prefix is not None or approximate_suffix is not None:
            return False
    if re.search(
        r"(?:不但|不仅|不得不|无不)[\u4e00-\u9fff]{0,8}$|notonly[a-z0-9]{0,24}$",
        prefix,
    ):
        return True
    if re.search(r"(?:无|尚无|缺乏|零)$", prefix) and re.match(r"(?:经验|基础|实践|能力)", suffix):
        return False
    negative_prefix = re.search(
        r"(?:不$|不是|不(?:懂|熟悉|负责|使用|具备|参与|会|能|可|曾|了解|掌握|建议|允许|支持)|"
        r"未|没(?:有)?|并非|非本人|无法|无经验|从未|尚未|不曾)[\u4e00-\u9fff]{0,8}$|"
        r"(?:not|never|without|no|didnot|doesnot|donot|willnot|wasnot|isnot|cannot|"
        r"cant|didnt|doesnt|dont|wont|shouldnt|wouldnt|couldnt|hasnt|havent|hadnt|"
        r"wasnt|isnt)"
        r"[a-z0-9]{0,24}$",
        prefix,
        re.I,
    )
    negative_suffix = re.match(
        r"(?:(?:经验)?(?:无|暂无|没有)|不会|不熟悉|不掌握|不了解|不懂|不具备|"
        r"未使用|未曾使用|未掌握|未了解|未参与|未参加|未接触|未学习|未学|"
        r"尚未(?:学习|使用|掌握|了解|接触)|从未(?:学习|使用|掌握|了解|接触)|"
        r"(?:目前|当前|暂时|暂|实际|其实|完全|确实|并|从来|尚)?"
        r"(?:尚未|还未|并未|从未|未曾|不曾|未|没有|没|并不|不)"
        r"(?:实际|真正)?(?:被)?(?:使用|用过|用于|应用|掌握|熟悉|了解|懂|接触|学习|实践|参与|具备|会|能)|"
        r"(?:目前|当前|暂时|暂|实际|其实|完全|确实)?(?:无法|未能)"
        r"(?:实际)?(?:使用|用于|应用|掌握|熟悉|了解|接触|学习|实践|参与)|"
        r"(?:目前|当前|暂时|暂|实际|其实|完全)?(?:无|没有)(?:相关)?(?:经验|经历|能力|基础)|"
        r"(?:经验|经历|能力)(?:目前|当前|实际|其实)?(?:并无|没有|为无)|"
        r"缺乏(?:经验|基础|实践|能力)?|零经验|无关|不足|否)|"
        r"(?:(?:experience[:=\-]?)?(?:no|none|zero|n/?a|false|denied|not|never|"
        r"absent|lacking)|notused|notfamiliar|notapplicable|notlearned|neverused|"
        r"(?:is|are|was|were|has|have|had)(?:currently|actually|really|completely|definitely)?"
        r"(?:never|not(?!only))(?:currently|actually|really|completely|definitely)?(?:been)?"
        r"(?:used|applied|learned|known|familiar|mastered)|"
        r"(?:is|are|was|were)(?:currently|actually|really|completely|definitely)?"
        r"(?:unfamiliar|unknown|unmastered)|"
        r"(?:currently|actually|really|completely|definitely)?(?:has|have|had)"
        r"(?:currently|actually|really|completely|definitely)?(?:no|zero)"
        r"(?:relevant)?(?:experience|knowledge|skill)|"
        r"(?:wasnt|werent|isnt|arent|hasnt|havent|hadnt)(?:been)?"
        r"(?:used|applied|learned|known|familiar|mastered))",
        suffix.lstrip(":-="),
        re.I,
    )
    return negative_prefix is None and negative_suffix is None


def graduation_year_is_grounded(value: int, raw_text: str) -> bool:
    """Ground graduation semantics, not an unrelated occurrence of the same year."""

    normalized = normalize_text(raw_text)
    year = str(value)
    cohort = f"{value % 100:02d}"
    year_token = rf"(?<!\d){re.escape(year)}(?!\d)"
    cohort_token = rf"(?<!\d)(?:{re.escape(year)}|{re.escape(cohort)})(?!\d)"
    explicit_patterns = (
        rf"{cohort_token}\s*(?:年\s*)?届",
        rf"(?:预计|预期|计划)?\s*(?:于\s*)?{year_token}\s*(?:年\s*)?(?:毕业|结业)",
        rf"(?:预计|预期|计划)?\s*(?:毕业|结业)(?:时间|年份|日期)?\s*[:\uff1a]?\s*{year_token}",
    )
    if any(re.search(pattern, normalized) for pattern in explicit_patterns):
        return True

    range_pattern = re.compile(
        rf"(?<!\d)(?:19|20)\d{{2}}(?:\s*[./]\s*\d{{1,2}})?"
        rf"\s*(?:-|~|至|到)\s*{year_token}(?:\s*[./]\s*\d{{1,2}})?"
    )
    lines = [line.strip() for line in normalized.splitlines() if line.strip()]
    education_cue = re.compile(r"教育|学历|大学|学院|本科|硕士|博士|专业|就读")
    for index, line in enumerate(lines):
        if not range_pattern.search(line):
            continue
        context = " ".join(lines[max(0, index - 1) : index + 1])
        if education_cue.search(context):
            return True
    return False


def controlled_signal_is_grounded(claim: FactClaim, raw_text: str) -> bool:
    """Require an enum signal in both the raw text and its canonical record scope."""

    scope_values = claim.scope_values or ((claim.scope_text,) if claim.scope_text else ())
    if not scope_values or not claim.candidates or not claim.raw_scope_text:
        return False
    return any(
        _positive_controlled_signal(candidate, scope_value)
        and fact_is_grounded(scope_value, claim.raw_scope_text)
        and _positive_controlled_signal(candidate, claim.raw_scope_text)
        for candidate in claim.candidates
        for scope_value in scope_values
    )


def _positive_controlled_signal(candidate: str, value: str) -> bool:
    """Reject locally negated enum signals while allowing a grounded positive one."""

    if not direct_fact_is_grounded(candidate, value):
        return False
    normalized_candidate = normalize_text(candidate).strip()
    normalized_value = normalize_text(value)
    escaped = re.escape(normalized_candidate).replace(r"\ ", r"\s+")
    negated = re.compile(
        rf"(?:不是|不是在|并非|非|不属于|不在|不算|未参与(?:过)?|未参加(?:过)?|没有参与|无)\s*{escaped}|"
        rf"不(?!仅|但|断)\s*{escaped}|"
        rf"{escaped}\s*(?:(?:范围)?(?:外|之外|以外)|未参加|未参与|无关|[:\uff1a]?\s*否)|"
        rf"\b(?:not|no|without|outside)\s+(?:(?:a|an|the|in|part\s+of)\s+)*{escaped}\b|"
        rf"\bnon[-\s]*{escaped}\b|"
        rf"\b{escaped}\b\s+(?:is\s+)?(?:not|outside|out\s+of\s+scope)\b",
        re.I,
    )
    return negated.search(normalized_value) is None


def anchored_record_scope(raw_text: str, anchors: Sequence[str]) -> str:
    """Return only raw lines that contain an explicit canonical record anchor.

    Unstructured extraction has no reliable record boundaries. Including nearby
    lines can therefore borrow a category or authorization signal from another
    record. The strict anchor-line rule is intentionally conservative.
    """

    if not anchors:
        return ""

    def anchor_is_grounded(anchor: str, line: str) -> bool:
        normalized = normalize_text(anchor).strip()
        escaped = re.escape(normalized).replace(r"\ ", r"\s+")
        return bool(re.search(r"(?<!\w)" + escaped + r"(?!\w)", normalize_text(line)))

    matches = [
        line
        for line in raw_text.splitlines()
        if all(anchor_is_grounded(anchor, line) for anchor in anchors)
    ]
    return matches[0] if len(matches) == 1 else ""


_RECORD_YEAR_PATTERN = re.compile(r"(?<!\d)(?:19|20)\d{2}(?!\d)", re.I)
_RECORD_DURATION_PATTERN = re.compile(
    r"(?<!\d)(?:19|20)\d{2}(?:\s*[./-]\s*\d{1,2})?\s*"
    r"(?:-|~|\u2013|\u2014|\u81f3|\u5230)\s*"
    r"(?:(?:19|20)\d{2}(?:\s*[./-]\s*\d{1,2})?|\u81f3\u4eca|\u73b0\u5728|"
    r"present|current)",
    re.I,
)
_RECORD_LEADING_BULLET = re.compile(r"^\s*(?:[-*+\u2022\u25cf\u25aa\u25e6]|\d+[.)\u3001])\s+")
_RECORD_CONTINUATION_PREFIX = re.compile(
    r"^\s*(?:(?:\u8d1f\u8d23|\u4f7f\u7528|\u5b9e\u73b0|\u5b8c\u6210|\u4f18\u5316|\u63d0\u5347|\u964d\u4f4e|\u5f00\u53d1|\u8bbe\u8ba1|\u7ef4\u62a4|\u53c2\u4e0e|\u6784\u5efa|\u90e8\u7f72|\u901a\u8fc7)|"
    r"(?:responsible|built|developed|implemented|designed|used|created|improved|"
    r"reduced|deployed|maintained|integrated|migrated|tested|analyzed|led|owned)\b)",
    re.I,
)
_RECORD_IDENTITY_PAIR = re.compile(
    r"(?:\u516c\u53f8|\u96c6\u56e2|\u5927\u5b66|\u5b66\u9662|\u5b66\u6821|\u5b9e\u9a8c\u5ba4|\u56e2\u961f|\u90e8\u95e8)"
    r".{0,96}(?:\u5e73\u53f0|\u7cfb\u7edf|\u9879\u76ee|\u670d\u52a1|\u4e2d\u5fc3|\u5de5\u5177)|"
    r"\b(?:company|corp(?:oration)?|inc|ltd|laboratory|lab|university|college)\b"
    r".{0,96}\b(?:project|platform|system|service|tool)\b",
    re.I,
)


def _heading_line_matches(line: str, pattern: re.Pattern[str]) -> bool:
    """Match a heading as a whole line, allowing Markdown markers and a trailing colon."""

    candidate = unicodedata.normalize("NFKC", line).strip()
    candidate = re.sub(r"^#{1,6}\s*", "", candidate)
    candidate = re.sub(r"\s*[:\uff1a]\s*$", "", candidate)
    return bool(candidate and pattern.fullmatch(candidate))


def _anchor_is_on_line(anchor: str, line: str) -> bool:
    normalized = normalize_text(anchor).strip()
    if not normalized:
        return False
    escaped = re.escape(normalized).replace(r"\ ", r"\s+")
    return bool(re.search(r"(?<!\w)" + escaped + r"(?!\w)", normalize_text(line)))


def _scope_has_all_anchors(scope: str, anchors: Sequence[str]) -> bool:
    lines = scope.splitlines()
    return bool(anchors) and all(
        any(_anchor_is_on_line(anchor, line) for line in lines) for anchor in anchors
    )


def _record_line_content(line: str) -> str:
    return _RECORD_LEADING_BULLET.sub("", line.strip())


def _is_record_continuation(line: str) -> bool:
    return _RECORD_CONTINUATION_PREFIX.match(_record_line_content(line)) is not None


def _looks_like_record_header(line: str, *, preceded_by_blank: bool) -> bool:
    """Recognize only explicit, low-noise record headers for omission coverage."""

    stripped = line.strip()
    if not stripped:
        return False
    is_bullet = _RECORD_LEADING_BULLET.match(stripped) is not None
    content = _record_line_content(stripped)
    has_duration = _RECORD_DURATION_PATTERN.search(content) is not None
    has_year = _RECORD_YEAR_PATTERN.search(content) is not None
    has_separator = bool(re.search(r"[|\uff5c\t]", content))
    has_identity_pair = _RECORD_IDENTITY_PAIR.search(content) is not None
    is_continuation = _is_record_continuation(content)
    without_dates = _RECORD_DURATION_PATTERN.sub("", content)
    without_dates = _RECORD_YEAR_PATTERN.sub("", without_dates)
    has_identity_text = bool(re.search(r"[A-Za-z\u4e00-\u9fff]", without_dates))
    weak_header = has_duration or (has_separator and not is_bullet) or (has_year and not is_bullet)
    return (
        has_identity_text
        and not is_continuation
        and (has_identity_pair or (preceded_by_blank and weak_header))
    )


def record_collection_scopes(
    raw_text: str,
    anchor_groups: Sequence[Sequence[str]],
    *,
    collection_pointer: str,
    heading_pattern: re.Pattern[str],
    all_headings_pattern: re.Pattern[str],
) -> RecordCollectionScopeResult:
    """Resolve every canonical record to one raw multi-line scope.

    A scope begins at an explicit canonical organization/name anchor or at a
    low-noise raw record header and ends at the next peer header or section
    heading. All anchors for a canonical record must occur in exactly one such
    scope. When an explicit raw header is left unclaimed, omission is a hard
    violation. Ambiguous input fails closed without exposing source text.
    """

    line_values = raw_text.splitlines(keepends=True)
    if not line_values:
        return RecordCollectionScopeResult(
            scopes=tuple("" for _ in anchor_groups),
            violations=tuple(
                AuditViolation("canonical_record_scope_not_found", f"{collection_pointer}/{index}")
                for index in range(len(anchor_groups))
            ),
        )

    offsets: list[int] = []
    offset = 0
    for line in line_values:
        offsets.append(offset)
        offset += len(line)

    target_headings = [
        index
        for index, line in enumerate(line_values)
        if _heading_line_matches(line, heading_pattern)
    ]
    regions: list[tuple[int, int]] = []
    if target_headings:
        for heading_index in target_headings:
            end_index = len(line_values)
            for index in range(heading_index + 1, len(line_values)):
                if _heading_line_matches(line_values[index], all_headings_pattern):
                    end_index = index
                    break
            if heading_index + 1 < end_index:
                regions.append((heading_index + 1, end_index))
    else:
        regions.append((0, len(line_values)))

    normalized_groups = tuple(
        tuple(anchor for anchor in anchors if normalize_text(anchor).strip())
        for anchors in anchor_groups
    )
    candidate_starts: dict[int, bool] = {}
    for region_start, region_end in regions:
        for index in range(region_start, region_end):
            preceded_by_blank = index == region_start or not line_values[index - 1].strip()
            if _looks_like_record_header(line_values[index], preceded_by_blank=preceded_by_blank):
                candidate_starts[index] = True
        for anchors in normalized_groups:
            if not anchors:
                continue
            primary_occurrences = [
                index
                for index in range(region_start, region_end)
                if _anchor_is_on_line(anchors[0], line_values[index])
            ]
            strong_occurrences = [
                index
                for index in primary_occurrences
                if all(_anchor_is_on_line(anchor, line_values[index]) for anchor in anchors)
                and not _is_record_continuation(line_values[index])
            ]
            record_starts = (strong_occurrences or primary_occurrences)[:1]
            for index in record_starts:
                candidate_starts.setdefault(index, False)

    spans: list[tuple[str, bool]] = []
    for region_start, region_end in regions:
        starts = sorted(index for index in candidate_starts if region_start <= index < region_end)
        for position, start_index in enumerate(starts):
            end_index = starts[position + 1] if position + 1 < len(starts) else region_end
            start_offset = offsets[start_index]
            end_offset = offsets[end_index] if end_index < len(offsets) else len(raw_text)
            scope = raw_text[start_offset:end_offset].strip()
            if scope:
                spans.append((scope, candidate_starts[start_index]))

    violations: set[AuditViolation] = set()
    scope_indexes: list[int | None] = []
    for index, anchors in enumerate(normalized_groups):
        pointer = f"{collection_pointer}/{index}"
        if not anchors:
            violations.add(AuditViolation("canonical_record_anchor_missing", pointer))
            scope_indexes.append(None)
            continue
        matches = [
            scope_index
            for scope_index, (scope, _) in enumerate(spans)
            if _scope_has_all_anchors(scope, anchors)
        ]
        if len(matches) == 1:
            scope_indexes.append(matches[0])
        else:
            code = (
                "canonical_record_scope_not_found"
                if not matches
                else "canonical_record_scope_ambiguous"
            )
            violations.add(AuditViolation(code, pointer))
            scope_indexes.append(None)

    claimed: dict[int, list[int]] = {}
    for record_index, scope_index in enumerate(scope_indexes):
        if scope_index is not None:
            claimed.setdefault(scope_index, []).append(record_index)
    for record_indexes in claimed.values():
        if len(record_indexes) <= 1:
            continue
        for record_index in record_indexes:
            violations.add(
                AuditViolation(
                    "canonical_record_scope_ambiguous",
                    f"{collection_pointer}/{record_index}",
                )
            )
            scope_indexes[record_index] = None

    if target_headings and any(
        is_explicit_header and scope_index not in claimed
        for scope_index, (_, is_explicit_header) in enumerate(spans)
    ):
        violations.add(AuditViolation("raw_record_not_mapped", collection_pointer))

    return RecordCollectionScopeResult(
        scopes=tuple(spans[index][0] if index is not None else "" for index in scope_indexes),
        violations=tuple(sorted(violations)),
    )


def section_state(
    raw_text: str,
    heading_pattern: re.Pattern[str],
    all_headings_pattern: re.Pattern[str],
) -> str:
    """Return absent, empty, or populated for a coarse source section."""

    normalized = unicodedata.normalize("NFKC", raw_text)
    matches = tuple(heading_pattern.finditer(normalized))
    if not matches:
        return "absent"
    for match in matches:
        next_heading = all_headings_pattern.search(normalized, match.end())
        end = next_heading.start() if next_heading else len(normalized)
        content = normalized[match.end() : end]
        compact = re.sub(r"[\s\W_]+", "", content, flags=re.UNICODE)
        if not _EMPTY_SECTION_CONTENT_PATTERN.fullmatch(compact):
            return "populated"
    return "empty"


def canonical_facts_sha256(canonical: Mapping[str, Any]) -> str:
    """Hash stable canonical JSON while excluding generated/internal resume_id."""

    facts = dict(canonical)
    facts.pop("resume_id", None)
    payload = json.dumps(
        facts,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def _escape_pointer_token(value: object) -> str:
    return str(value).replace("~", "~0").replace("/", "~1")


def populated_leaf_pointers(canonical: Mapping[str, Any]) -> set[str]:
    """Enumerate every populated factual leaf that adapters must register."""

    pointers: set[str] = set()

    def visit(value: Any, tokens: tuple[object, ...]) -> None:
        if isinstance(value, Mapping):
            for key in sorted(value):
                visit(value[key], (*tokens, key))
            return
        if isinstance(value, list):
            for index, item in enumerate(value):
                visit(item, (*tokens, index))
            return
        if value is None or value == "":
            return
        if tokens == ("resume_id",):
            return
        if (
            tokens
            and tokens[-1] in {"category", "environment"}
            and value
            in {
                "other",
                "unknown",
            }
        ):
            return
        pointers.add("/" + "/".join(_escape_pointer_token(token) for token in tokens))

    visit(canonical, ())
    return pointers


def duplicate_canonical_violations(canonical: Mapping[str, Any]) -> tuple[AuditViolation, ...]:
    """Reject exact duplicate records and repeated list facts that reuse one raw occurrence."""

    violations: set[AuditViolation] = set()

    def stable_key(value: Any) -> str:
        return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))

    def list_item_key(value: Any) -> str:
        if isinstance(value, str):
            return stable_key(["normalized_string", _compact(value)])
        return stable_key(value)

    def check_list(values: Any, pointer: str, code: str) -> None:
        if not isinstance(values, list):
            return
        seen: set[str] = set()
        for index, value in enumerate(values):
            key = list_item_key(value)
            if key in seen:
                violations.add(AuditViolation(code, f"{pointer}/{index}"))
            else:
                seen.add(key)

    seen_records: set[str] = set()
    for collection_name in ("internships", "projects", "security_activities"):
        records = canonical.get(collection_name)
        if not isinstance(records, list):
            continue
        for index, record in enumerate(records):
            if not isinstance(record, Mapping):
                continue
            organization = record.get("organization") or record.get("company")
            name = record.get("name")
            duration = record.get("duration")
            if collection_name == "internships" and organization and duration:
                record_key = stable_key(
                    [
                        "strong_identity",
                        normalize_text(str(organization)).strip(),
                        normalize_text(str(name)).strip() if name else None,
                        normalize_text(str(duration)).strip(),
                    ]
                )
            elif (
                collection_name in {"projects", "security_activities"}
                and name
                and (organization or duration)
            ):
                record_key = stable_key(
                    [
                        "strong_identity",
                        normalize_text(str(organization)).strip() if organization else None,
                        normalize_text(str(name)).strip(),
                        normalize_text(str(duration)).strip() if duration else None,
                    ]
                )
            else:
                record_key = stable_key(["exact_record", record])
            if record_key in seen_records:
                violations.add(
                    AuditViolation("canonical_duplicate_record", f"/{collection_name}/{index}")
                )
            else:
                seen_records.add(record_key)
            for field in ("tech_stack", "achievements"):
                check_list(
                    record.get(field),
                    f"/{collection_name}/{index}/{field}",
                    "canonical_duplicate_list_item",
                )

    skills = canonical.get("skills")
    if isinstance(skills, Mapping):
        for group, values in skills.items():
            check_list(
                values,
                f"/skills/{_escape_pointer_token(group)}",
                "canonical_duplicate_list_item",
            )
    return tuple(sorted(violations))


def audit_canonical_mapping(
    raw: RawExtraction,
    canonical: Mapping[str, Any],
    claims: Sequence[FactClaim],
    *,
    error_type: type[Exception],
    violations: Sequence[AuditViolation] = (),
    warning_codes: Sequence[str] = (),
) -> SourceMappingAuditResult:
    """Audit registered facts, fail closed on unregistered leaves, and return safe metadata."""

    failures = {*violations, *duplicate_canonical_violations(canonical)}
    expected = populated_leaf_pointers(canonical)
    registered: set[str] = set()
    for claim in claims:
        if claim.pointer in registered:
            failures.add(AuditViolation("audit_contract_duplicate_field", claim.pointer))
            continue
        registered.add(claim.pointer)
        grounded = False
        if claim.match_kind == "direct":
            evidence_scope = (
                claim.raw_scope_text if claim.raw_scope_text is not None else raw.full_text
            )
            grounded = direct_fact_is_grounded(claim.value, evidence_scope)
        elif claim.match_kind == "graduation_year" and isinstance(claim.value, int):
            grounded = graduation_year_is_grounded(claim.value, raw.full_text)
        elif claim.match_kind == "controlled":
            grounded = controlled_signal_is_grounded(claim, raw.full_text)
        elif claim.match_kind == "registered":
            grounded = True
        else:
            failures.add(AuditViolation("audit_contract_unknown_match_kind", claim.pointer))
            continue
        if not grounded:
            failures.add(AuditViolation("canonical_fact_not_grounded", claim.pointer))
    for pointer in sorted(expected - registered):
        failures.add(AuditViolation("audit_contract_uncovered_field", pointer))
    for pointer in sorted(registered - expected):
        failures.add(AuditViolation("audit_contract_unexpected_field", pointer))
    if failures:
        detail = ",".join(f"{item.code}@{item.pointer}" for item in sorted(failures))
        raise error_type(detail)
    return SourceMappingAuditResult(
        raw_source_sha256=raw.source_sha256,
        canonical_facts_sha256=canonical_facts_sha256(canonical),
        checked_fact_count=len(claims),
        warning_codes=tuple(sorted(set(warning_codes))),
    )
