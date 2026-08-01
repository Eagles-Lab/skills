"""End-to-end deterministic analysis orchestration."""
# ruff: noqa: RUF001

from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Callable, Dict, Mapping, Optional

from pydantic import ValidationError

from .errors import AnalyzerError, InputValidationError, OutputSafetyError
from .models import SCHEMA_VERSION, Resume
from .output import derive_resume_id, sha256_file, validate_resume_id, write_output_bundle
from .rendering import DIMENSION_LABELS, RenderingError, ReportRenderer
from .scoring import SCORING_CONFIG_VERSION, ScoreCalculator
from .security import SECURITY_WARNING, contains_instruction_like_content
from .version import ANALYZER_VERSION, STATUS

Clock = Callable[[], datetime]


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


class ResumeAnalyzer:
    """Validate, score, render, and atomically persist one resume."""

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

    def inspect_input(self, extracted_path: Path) -> tuple[Resume, str, str]:
        """Return the validated model, digest, and safe output identifier."""

        source = Path(extracted_path)
        resume = load_resume(source)
        input_sha256 = sha256_file(source)
        if resume.resume_id is not None:
            resume_id = validate_resume_id(resume.resume_id)
        else:
            resume_id = derive_resume_id(resume.basic_info.name, input_sha256)
        return resume, input_sha256, resume_id

    def analyze(
        self,
        extracted_path: Path,
        *,
        include_contact: bool = False,
        overwrite: bool = False,
        seed: Optional[str] = None,
    ) -> Dict[str, str]:
        resume, input_sha256, resume_id = self.inspect_input(extracted_path)
        generated_at = self.clock().astimezone(UTC).replace(microsecond=0).isoformat()
        generated_at = generated_at.replace("+00:00", "Z")
        warnings = (
            [SECURITY_WARNING]
            if contains_instruction_like_content(resume.model_dump(mode="python"))
            else []
        )

        try:
            score_result = self.calculator.calculate(resume)
            score_data = _model_mapping(score_result)
            score_data.update(
                {
                    "schema_version": SCHEMA_VERSION,
                    "analyzer_version": ANALYZER_VERSION,
                    "analyzer_status": STATUS,
                    "resume_id": resume_id,
                    "input_sha256": input_sha256,
                    "generated_at": generated_at,
                    "warnings": warnings,
                    "scoring_config_version": score_data.get(
                        "scoring_config_version", SCORING_CONFIG_VERSION
                    ),
                }
            )
            analysis = self._build_analysis(
                score_data,
                resume_id,
                generated_at,
                input_sha256,
                warnings,
            )
            rendered = self.renderer.render(
                resume,
                score_data,
                analysis,
                resume_id=resume_id,
                generated_at=generated_at,
                analyzer_version=ANALYZER_VERSION,
                input_sha256=input_sha256,
                seed=seed,
                include_contact=include_contact,
            )
            extracted = resume.model_dump(mode="json")
            extracted["resume_id"] = resume_id
            return write_output_bundle(
                self.output_dir,
                resume_id,
                extracted=extracted,
                score=score_data,
                analysis=analysis,
                suggestions=rendered.suggestions,
                interview_questions=rendered.interview_questions,
                overwrite=overwrite,
            )
        except (InputValidationError, OutputSafetyError):
            raise
        except RenderingError as exc:
            raise AnalyzerError(str(exc)) from exc
        except AnalyzerError:
            raise
        except Exception as exc:
            raise AnalyzerError(f"analysis failed: {type(exc).__name__}") from exc

    def _build_analysis(
        self,
        score: Mapping[str, Any],
        resume_id: str,
        generated_at: str,
        input_sha256: str,
        warnings: list[str],
    ) -> Dict[str, Any]:
        strengths = []
        weaknesses = []
        dimensions = score.get("dimension_scores", {})
        for name in DIMENSION_LABELS:
            info = dimensions.get(name, {})
            numeric_score = float(info.get("score", 1.0))
            evidence_count = len(info.get("evidence", []))
            if numeric_score >= 8.0:
                strengths.append(
                    {
                        "dimension": name,
                        "label": DIMENSION_LABELS[name],
                        "score": numeric_score,
                        "summary": f"有 {evidence_count} 条满足规则的证据。",
                    }
                )
            elif numeric_score < 7.0:
                weaknesses.append(
                    {
                        "dimension": name,
                        "label": DIMENSION_LABELS[name],
                        "score": numeric_score,
                        "summary": "证据覆盖不足，建议补充个人行动、规模和验证结果。",
                    }
                )

        grade = score.get("grade", {})
        return {
            "schema_version": SCHEMA_VERSION,
            "analyzer_version": ANALYZER_VERSION,
            "analyzer_status": STATUS,
            "resume_id": resume_id,
            "input_sha256": input_sha256,
            "generated_at": generated_at,
            "warnings": warnings,
            "strengths": strengths,
            "weaknesses": weaknesses,
            "ai_analysis": {
                "score": score.get("ai_bonus", {}).get("score", 0.0),
                "applications": score.get("ai_bonus", {}).get("applications", {}),
            },
            "overall_assessment": (
                f"简历证据覆盖等级为 {grade.get('grade', 'F')}。"
                "该结果仅用于定位简历证据缺口，不能单独用于招聘决策。"
            ),
        }
