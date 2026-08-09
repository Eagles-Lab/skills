"""Validate, score, render, and atomically publish security resume analysis."""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Callable, Mapping

from pydantic import ValidationError

from .dedup_core import SourceIdentityKind, aggregate_source_sha256
from .errors import AnalyzerError, InputValidationError, OutputSafetyError
from .matching import unsafe_offensive_statements
from .models import DataQualityWarning, Resume
from .output import (
    derive_output_name,
    derive_resume_id,
    sha256_file,
    validate_resume_id,
    write_run_output,
)
from .rendering import RenderingError, ReportRenderer
from .scoring import ScoreCalculator
from .security import SECURITY_WARNING, contains_instruction_like_content
from .source_audit import audit_source_mapping
from .version import ANALYZER_STATUS, ANALYZER_VERSION, CALIBRATION_STATUS

Clock = Callable[[], datetime]
MISSING_MESSAGE = "未提供或未可靠识别，请后续补充。"
_SHA256 = re.compile(r"^[a-f0-9]{64}$")


def _utc_now() -> datetime:
    return datetime.now(UTC)


def load_resume(path: Path) -> Resume:
    source = Path(path)
    if not source.exists() or not source.is_file() or source.is_symlink():
        raise InputValidationError("canonical security resume must be a regular JSON file")
    if source.stat().st_size > 5 * 1024 * 1024:
        raise InputValidationError("canonical security resume exceeds the 5 MiB limit")
    try:
        value = json.loads(source.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise InputValidationError(
            f"canonical security resume could not be read: {type(exc).__name__}"
        ) from exc
    if not isinstance(value, Mapping):
        raise InputValidationError("canonical security resume schema v1 root must be an object")
    try:
        return Resume.model_validate(value)
    except ValidationError as exc:
        issues = []
        for item in exc.errors(include_input=False, include_url=False)[:12]:
            location = ".".join(map(str, item.get("loc", ()))) or "root"
            issues.append(f"{location}: {item.get('type', 'invalid')}")
        raise InputValidationError(
            "input does not match canonical security resume schema v1: " + "; ".join(issues)
        ) from exc


@dataclass(frozen=True)
class AnalysisArtifacts:
    resume_id: str
    output_name: str
    source_hashes: tuple[str, ...]
    extracted: Mapping[str, Any]
    score: Mapping[str, Any]
    analysis: Mapping[str, Any]
    suggestions: str
    interview_questions: str

    def output_payload(self) -> dict[str, Any]:
        return {
            "output_name": self.output_name,
            "extracted": self.extracted,
            "score": self.score,
            "analysis": self.analysis,
            "suggestions": self.suggestions,
            "interview_questions": self.interview_questions,
        }


class SecurityResumeAnalyzer:
    def __init__(
        self,
        output_dir: Path,
        *,
        clock: Clock = _utc_now,
        renderer: ReportRenderer | None = None,
    ) -> None:
        self.output_dir = Path(output_dir)
        self.calculator = ScoreCalculator()
        self.clock = clock
        self.renderer = renderer or ReportRenderer()

    def build_artifacts(
        self,
        resume: Resume,
        source_hashes: tuple[str, ...],
        *,
        output_name: str | None = None,
        primary_sha256: str | None = None,
        primary_canonical_sha256: str | None = None,
        source_record_count: int | None = None,
        source_identity_kind: SourceIdentityKind = "canonical_json_sha256",
        conflicts: tuple[dict[str, str], ...] = (),
        source_mapping_audits: tuple[Mapping[str, Any], ...] = (),
        include_contact: bool = False,
        seed: str | None = None,
    ) -> AnalysisArtifacts:
        if not source_hashes or any(not _SHA256.fullmatch(value) for value in source_hashes):
            raise InputValidationError("source hashes must contain SHA-256 digests")
        source_hashes = tuple(sorted(set(source_hashes)))
        combined_sha256 = aggregate_source_sha256(source_hashes)
        primary_sha256 = primary_sha256 or source_hashes[0]
        primary_canonical_sha256 = primary_canonical_sha256 or primary_sha256
        source_record_count = source_record_count or len(source_hashes)
        resume_id = (
            validate_resume_id(resume.resume_id)
            if resume.resume_id
            else derive_resume_id(resume.basic_info.name, combined_sha256)
        )
        output_name = output_name or derive_output_name(resume.basic_info.name, combined_sha256)
        generated_at = (
            self.clock().astimezone(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")
        )
        warnings = collect_data_quality_warnings(resume)
        security_warnings = unsafe_offensive_statements(resume)
        if contains_instruction_like_content(resume.model_dump(mode="python")):
            security_warnings.append(SECURITY_WARNING)
        if (
            any(
                SECURITY_WARNING in audit.get("warning_codes", ())
                for audit in source_mapping_audits
            )
            and SECURITY_WARNING not in security_warnings
        ):
            security_warnings.append(SECURITY_WARNING)
        try:
            score = self.calculator.calculate(resume).model_dump(mode="json")
            score.update(
                {
                    "analyzer_version": ANALYZER_VERSION,
                    "analyzer_status": ANALYZER_STATUS,
                    "calibration_status": CALIBRATION_STATUS,
                    "resume_id": resume_id,
                    "output_name": output_name,
                    "input_sha256": combined_sha256,
                    "source_hashes": list(source_hashes),
                    "generated_at": generated_at,
                    "deduplication": {
                        "source_count": source_record_count,
                        "source_record_count": source_record_count,
                        "unique_source_count": len(source_hashes),
                        "deduplicated_source_count": source_record_count - 1,
                        "primary_sha256": primary_sha256,
                        "primary_canonical_sha256": primary_canonical_sha256,
                        "source_identity_kind": source_identity_kind,
                        "conflicts": list(conflicts),
                    },
                    "source_mapping_audits": [dict(item) for item in source_mapping_audits],
                    "data_quality_warnings": [item.model_dump(mode="json") for item in warnings],
                    "security_warnings": sorted(set(security_warnings)),
                }
            )
            analysis = {
                "schema_version": "1.0",
                "analyzer_version": ANALYZER_VERSION,
                "analyzer_status": ANALYZER_STATUS,
                "calibration_status": CALIBRATION_STATUS,
                "scoring_profile": score["scoring_profile"],
                "resume_id": resume_id,
                "output_name": output_name,
                "input_sha256": combined_sha256,
                "generated_at": generated_at,
                "data_quality_warnings": score["data_quality_warnings"],
                "security_warnings": score["security_warnings"],
                "resume_quality": score["resume_quality"],
                "source_mapping_audits": score["source_mapping_audits"],
                "overall_assessment": "该结果仅衡量未校准的简历证据覆盖度，不得用于排名或招聘决策。",
            }
            rendered = self.renderer.render(
                resume,
                score,
                analyzer_version=ANALYZER_VERSION,
                seed=seed or combined_sha256,
                include_contact=include_contact,
                security_warnings=score["security_warnings"],
            )
            extracted = resume.model_dump(mode="json")
            extracted["resume_id"] = resume_id
            return AnalysisArtifacts(
                resume_id,
                output_name,
                source_hashes,
                extracted,
                score,
                analysis,
                rendered.suggestions,
                rendered.interview_questions,
            )
        except (InputValidationError, OutputSafetyError):
            raise
        except RenderingError as exc:
            raise AnalyzerError(str(exc)) from exc
        except Exception as exc:
            raise AnalyzerError(f"security resume analysis failed: {type(exc).__name__}") from exc

    def analyze(
        self,
        extracted_path: Path,
        *,
        include_contact: bool = False,
        overwrite: bool = False,
        seed: str | None = None,
        raw_extraction_path: Path | None = None,
    ) -> dict[str, str]:
        resume = load_resume(extracted_path)
        canonical_digest = sha256_file(extracted_path)
        audits: tuple[Mapping[str, Any], ...]
        source_identity_kind: SourceIdentityKind
        if raw_extraction_path is not None:
            audit = audit_source_mapping(raw_extraction_path, resume)
            digest = audit.raw_source_sha256
            audits = (audit.public_metadata(),)
            source_identity_kind = "raw_document_sha256"
        else:
            digest = canonical_digest
            audits = ()
            source_identity_kind = "canonical_json_sha256"
        artifacts = self.build_artifacts(
            resume,
            (digest,),
            include_contact=include_contact,
            seed=seed,
            primary_canonical_sha256=canonical_digest,
            source_identity_kind=source_identity_kind,
            source_mapping_audits=audits,
        )
        return write_run_output(self.output_dir, [artifacts.output_payload()], overwrite=overwrite)[
            artifacts.output_name
        ]


def collect_data_quality_warnings(resume: Resume) -> list[DataQualityWarning]:
    warnings: list[DataQualityWarning] = []

    def add(code: str, path: str) -> None:
        warnings.append(DataQualityWarning(code=code, path=path, message=MISSING_MESSAGE))

    for field in ("name", "school", "major", "degree", "graduation_year"):
        if getattr(resume.basic_info, field) is None:
            add(f"missing_basic_info_{field}", f"basic_info.{field}")
    if not resume.internships:
        add("missing_internships", "internships")
    if not resume.projects:
        add("missing_projects", "projects")
    if not resume.security_activities:
        add("missing_security_activities", "security_activities")
    for field, values in resume.skills.model_dump(mode="python").items():
        if not values:
            add(f"missing_skills_{field}", f"skills.{field}")
    return warnings
