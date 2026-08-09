"""End-to-end deterministic analysis orchestration."""
# ruff: noqa: RUF001

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Callable, Dict, Mapping, Optional

from pydantic import ValidationError

from .dedup_core import SourceIdentityKind, aggregate_source_sha256
from .errors import AnalyzerError, InputValidationError, OutputSafetyError
from .models import SCHEMA_VERSION, DataQualityWarning, Resume
from .output import (
    derive_output_name,
    derive_resume_id,
    sha256_file,
    validate_resume_id,
    write_run_output,
)
from .rendering import DIMENSION_LABELS, RenderingError, ReportRenderer
from .scoring import SCORING_CONFIG_VERSION, ScoreCalculator
from .security import SECURITY_WARNING, contains_instruction_like_content
from .source_audit import audit_source_mapping
from .version import ANALYZER_VERSION, STATUS

Clock = Callable[[], datetime]
MISSING_DATA_MESSAGE = "未提供或未可靠识别，请后续补充。"
_SHA256 = re.compile(r"^[a-f0-9]{64}$")


def _utc_now() -> datetime:
    return datetime.now(UTC)


def _validation_summary(error: ValidationError) -> str:
    issues = []
    for item in error.errors(include_input=False, include_url=False):
        location = ".".join(str(part) for part in item.get("loc", ())) or "root"
        issues.append(f"{location}: {item.get('type', 'invalid')}")
    return "; ".join(issues[:12])


def load_resume(path: Path) -> Resume:
    """Load and strictly validate one canonical v3 JSON document."""

    source = Path(path)
    if not source.exists() or not source.is_file():
        raise InputValidationError(f"canonical resume file does not exist: {source}")
    if source.is_symlink():
        raise InputValidationError("canonical resume input must be a regular file, not a symlink")
    if source.stat().st_size > 5 * 1024 * 1024:
        raise InputValidationError("canonical resume JSON exceeds the 5 MiB limit")
    try:
        value = json.loads(source.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise InputValidationError(
            f"canonical resume JSON could not be read: {type(exc).__name__}"
        ) from exc
    if not isinstance(value, Mapping):
        raise InputValidationError("canonical resume schema v3 root must be an object")
    try:
        return Resume.model_validate(value)
    except ValidationError as exc:
        raise InputValidationError(
            f"input does not match canonical resume schema v3: {_validation_summary(exc)}"
        ) from exc


def _model_mapping(value: Any) -> Dict[str, Any]:
    if hasattr(value, "model_dump"):
        return dict(value.model_dump(mode="json"))
    if isinstance(value, Mapping):
        return dict(value)
    raise TypeError(f"expected score model or mapping, got {type(value).__name__}")


@dataclass(frozen=True)
class AnalysisArtifacts:
    resume_id: str
    output_name: str
    input_sha256: str
    extracted: Mapping[str, Any]
    score: Mapping[str, Any]
    analysis: Mapping[str, Any]
    suggestions: str
    interview_questions: str

    def output_payload(self) -> Dict[str, Any]:
        return {
            "output_name": self.output_name,
            "extracted": self.extracted,
            "score": self.score,
            "analysis": self.analysis,
            "suggestions": self.suggestions,
            "interview_questions": self.interview_questions,
        }


class ResumeAnalyzer:
    """Validate, score, render, and atomically persist one resume run."""

    def __init__(
        self,
        output_dir: Path,
        *,
        calculator: Optional[ScoreCalculator] = None,
        renderer: Optional[ReportRenderer] = None,
        clock: Clock = _utc_now,
    ) -> None:
        self.output_dir = Path(output_dir)
        self.calculator = calculator or ScoreCalculator()
        self.renderer = renderer or ReportRenderer()
        self.clock = clock

    def inspect_input(self, extracted_path: Path) -> tuple[Resume, str, str, str]:
        """Return the model, digest, internal identifier, and visible output name."""

        source = Path(extracted_path)
        resume = load_resume(source)
        input_sha256 = aggregate_source_sha256((sha256_file(source),))
        resume_id = (
            validate_resume_id(resume.resume_id)
            if resume.resume_id is not None
            else derive_resume_id(resume.basic_info.name, input_sha256)
        )
        output_name = derive_output_name(resume.basic_info.name, input_sha256)
        return resume, input_sha256, resume_id, output_name

    def build_artifacts(
        self,
        extracted_path: Path,
        *,
        raw_extraction_path: Optional[Path] = None,
        include_contact: bool = False,
        seed: Optional[str] = None,
    ) -> AnalysisArtifacts:
        source = Path(extracted_path)
        resume = load_resume(source)
        canonical_sha256 = sha256_file(source)
        source_audit = None
        source_identity_kind: SourceIdentityKind = "canonical_json_sha256"
        source_sha256 = canonical_sha256
        if raw_extraction_path is not None:
            source_audit = audit_source_mapping(raw_extraction_path, resume)
            source_identity_kind = "raw_document_sha256"
            source_sha256 = source_audit.raw_source_sha256
        audits = (source_audit.public_metadata(),) if source_audit is not None else ()
        return self.build_candidate_artifacts(
            resume,
            (source_sha256,),
            primary_canonical_sha256=canonical_sha256,
            source_identity_kind=source_identity_kind,
            source_mapping_audits=audits,
            include_contact=include_contact,
            seed=seed,
        )

    def build_candidate_artifacts(
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
        seed: Optional[str] = None,
    ) -> AnalysisArtifacts:
        if not source_hashes or any(not _SHA256.fullmatch(value) for value in source_hashes):
            raise InputValidationError("source hashes must contain SHA-256 digests")
        source_hashes = tuple(sorted(set(source_hashes)))
        input_sha256 = aggregate_source_sha256(source_hashes)
        primary_sha256 = primary_sha256 or source_hashes[0]
        primary_canonical_sha256 = primary_canonical_sha256 or primary_sha256
        source_record_count = source_record_count or len(source_hashes)
        resume_id = (
            validate_resume_id(resume.resume_id)
            if resume.resume_id is not None
            else derive_resume_id(resume.basic_info.name, input_sha256)
        )
        output_name = output_name or derive_output_name(resume.basic_info.name, input_sha256)
        generated_at = self.clock().astimezone(UTC).replace(microsecond=0).isoformat()
        generated_at = generated_at.replace("+00:00", "Z")
        data_warnings = collect_data_quality_warnings(resume)
        security_warnings = (
            [SECURITY_WARNING]
            if contains_instruction_like_content(resume.model_dump(mode="python"))
            else []
        )
        if (
            any(
                SECURITY_WARNING in audit.get("warning_codes", ())
                for audit in source_mapping_audits
            )
            and SECURITY_WARNING not in security_warnings
        ):
            security_warnings.append(SECURITY_WARNING)

        try:
            score_data = _model_mapping(self.calculator.calculate(resume))
            score_data.update(
                {
                    "schema_version": SCHEMA_VERSION,
                    "analyzer_version": ANALYZER_VERSION,
                    "analyzer_status": STATUS,
                    "resume_id": resume_id,
                    "output_name": output_name,
                    "input_sha256": input_sha256,
                    "source_hashes": list(source_hashes),
                    "generated_at": generated_at,
                    "security_warnings": security_warnings,
                    "data_quality_warnings": [
                        item.model_dump(mode="json") for item in data_warnings
                    ],
                    "scoring_config_version": score_data.get(
                        "scoring_config_version", SCORING_CONFIG_VERSION
                    ),
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
                }
            )
            analysis = self._build_analysis(
                score_data,
                resume_id,
                output_name,
                generated_at,
                input_sha256,
                security_warnings,
                data_warnings,
            )
            analysis["source_mapping_audits"] = score_data["source_mapping_audits"]
            rendered = self.renderer.render(
                resume,
                score_data,
                analysis,
                resume_id=resume_id,
                output_name=output_name,
                generated_at=generated_at,
                analyzer_version=ANALYZER_VERSION,
                input_sha256=input_sha256,
                seed=seed,
                include_contact=include_contact,
            )
            extracted = resume.model_dump(mode="json")
            extracted["resume_id"] = resume_id
            return AnalysisArtifacts(
                resume_id=resume_id,
                output_name=output_name,
                input_sha256=input_sha256,
                extracted=extracted,
                score=score_data,
                analysis=analysis,
                suggestions=rendered.suggestions,
                interview_questions=rendered.interview_questions,
            )
        except (InputValidationError, OutputSafetyError):
            raise
        except RenderingError as exc:
            raise AnalyzerError(str(exc)) from exc
        except AnalyzerError:
            raise
        except Exception as exc:
            raise AnalyzerError(f"analysis failed: {type(exc).__name__}") from exc

    def analyze(
        self,
        extracted_path: Path,
        *,
        raw_extraction_path: Optional[Path] = None,
        include_contact: bool = False,
        overwrite: bool = False,
        seed: Optional[str] = None,
    ) -> Dict[str, str]:
        artifacts = self.build_artifacts(
            extracted_path,
            raw_extraction_path=raw_extraction_path,
            include_contact=include_contact,
            seed=seed,
        )
        outputs = write_run_output(
            self.output_dir,
            [artifacts.output_payload()],
            overwrite=overwrite,
        )
        return outputs[artifacts.output_name]

    def _build_analysis(
        self,
        score: Mapping[str, Any],
        resume_id: str,
        output_name: str,
        generated_at: str,
        input_sha256: str,
        security_warnings: list[str],
        data_warnings: list[DataQualityWarning],
    ) -> Dict[str, Any]:
        strengths = []
        weaknesses = []
        dimensions = score.get("dimension_scores", {})
        for name in DIMENSION_LABELS:
            info = dimensions.get(name, {})
            numeric_score = float(info.get("score", 1.0))
            evidence_count = len(info.get("evidence", []))
            item = {
                "dimension": name,
                "label": DIMENSION_LABELS[name],
                "score": numeric_score,
                "evidence_count": evidence_count,
            }
            if numeric_score >= 8.0:
                item["summary"] = f"有 {evidence_count} 条规则证据支持较强覆盖。"
                strengths.append(item)
            elif numeric_score < 6.0:
                item["summary"] = "证据覆盖有限，建议补充个人行动、验证过程和同源结果。"
                weaknesses.append(item)

        grade = score.get("grade", {})
        ai_dimension = dimensions.get("ai_engineering_aiops", {})
        return {
            "schema_version": SCHEMA_VERSION,
            "analyzer_version": ANALYZER_VERSION,
            "analyzer_status": STATUS,
            "resume_id": resume_id,
            "output_name": output_name,
            "input_sha256": input_sha256,
            "generated_at": generated_at,
            "security_warnings": security_warnings,
            "data_quality_warnings": [item.model_dump(mode="json") for item in data_warnings],
            "strengths": strengths,
            "weaknesses": weaknesses,
            "ai_analysis": {
                "score": ai_dimension.get("score", 1.0),
                "evidence": ai_dimension.get("evidence", []),
            },
            "resume_quality": score.get("resume_quality", {}),
            "overall_assessment": (
                f"简历证据覆盖等级为 {grade.get('grade', 'F')}。"
                "该结果仅用于定位简历证据缺口，不能单独用于招聘决策。"
            ),
        }


def collect_data_quality_warnings(resume: Resume) -> list[DataQualityWarning]:
    """Create stable, structured reminders without inventing missing facts."""

    warnings: list[DataQualityWarning] = []

    def missing(code: str, path: str) -> None:
        warnings.append(DataQualityWarning(code=code, path=path, message=MISSING_DATA_MESSAGE))

    basic = resume.basic_info
    for field in ("name", "school", "major", "degree", "graduation_year"):
        if getattr(basic, field) is None:
            missing(f"missing_basic_info_{field}", f"basic_info.{field}")
    contact = basic.contact
    for field in ("phone", "email"):
        if contact is None or getattr(contact, field) is None:
            missing(f"missing_contact_{field}", f"basic_info.contact.{field}")

    if not resume.internships:
        missing("missing_internships", "internships")
    for index, internship in enumerate(resume.internships):
        for field in ("company", "role", "duration", "description"):
            if getattr(internship, field) is None:
                missing(f"missing_internship_{field}", f"internships.{index}.{field}")
        for field in ("tech_stack", "achievements"):
            if not getattr(internship, field):
                missing(f"missing_internship_{field}", f"internships.{index}.{field}")

    if not resume.projects:
        missing("missing_projects", "projects")
    for index, project in enumerate(resume.projects):
        for field in ("name", "role", "duration", "description"):
            if getattr(project, field) is None:
                missing(f"missing_project_{field}", f"projects.{index}.{field}")
        for field in ("tech_stack", "achievements"):
            if not getattr(project, field):
                missing(f"missing_project_{field}", f"projects.{index}.{field}")

    for field, items in resume.skills.model_dump(mode="python").items():
        if not items:
            missing(f"missing_skills_{field}", f"skills.{field}")
    return warnings
