"""Human-review calibration metrics for the deterministic scoring engine."""

from __future__ import annotations

import csv
import json
import math
import statistics
from collections import defaultdict
from pathlib import Path
from typing import Any, Dict, List, Mapping, Optional, Sequence, Tuple, Union

from pydantic import BaseModel, ConfigDict, Field

from .models import ScoreResult
from .scoring import DIMENSION_WEIGHTS, ScoreCalculator, ScoringConfig

CALIBRATION_FIELDS: Tuple[str, ...] = (
    "resume_id",
    "reviewer_id",
    "systems_network_foundation",
    "programming_automation",
    "troubleshooting",
    "cloud_distributed_infrastructure",
    "reliability_engineering",
    "ai_engineering_aiops",
    "resume_quality",
    "overall_grade",
    "notes",
)
CALIBRATION_DIMENSIONS: Tuple[str, ...] = (
    "systems_network_foundation",
    "programming_automation",
    "troubleshooting",
    "cloud_distributed_infrastructure",
    "reliability_engineering",
    "ai_engineering_aiops",
)
CALIBRATION_REVIEW_DIMENSIONS: Tuple[str, ...] = (*CALIBRATION_DIMENSIONS, "resume_quality")
GRADES: Tuple[str, ...] = ("A+", "A", "B", "C", "D", "F")


class CalibrationError(ValueError):
    """Raised for malformed or incomplete private calibration data."""


class CalibrationReview(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True, str_strip_whitespace=True)

    resume_id: str = Field(min_length=1)
    reviewer_id: str = Field(min_length=1)
    systems_network_foundation: float = Field(ge=1.0, le=10.0)
    programming_automation: float = Field(ge=1.0, le=10.0)
    troubleshooting: float = Field(ge=1.0, le=10.0)
    cloud_distributed_infrastructure: float = Field(ge=1.0, le=10.0)
    reliability_engineering: float = Field(ge=1.0, le=10.0)
    ai_engineering_aiops: float = Field(ge=1.0, le=10.0)
    resume_quality: float = Field(ge=1.0, le=10.0)
    overall_grade: str = Field(pattern=r"^(?:A\+|A|B|C|D|F)$")
    notes: str


class CalibrationThresholds(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True, frozen=True)

    minimum_sample_count: int = Field(default=40, ge=1)
    maximum_sample_count: int = Field(default=60, ge=1)
    minimum_weighted_kappa: float = 0.70
    minimum_spearman: float = 0.75
    maximum_median_absolute_error: float = 1.0
    minimum_grade_agreement: float = 0.80

    def model_post_init(self, __context: Any) -> None:
        if self.maximum_sample_count < self.minimum_sample_count:
            raise ValueError("maximum_sample_count must be at least minimum_sample_count")


class CalibrationReport(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)

    sample_count: int = Field(ge=0)
    reviewer_count: int = Field(ge=0)
    reviewer_weighted_kappa: Dict[str, float]
    mean_reviewer_kappa: float
    tool_human_spearman: float
    median_absolute_error: float
    grade_agreement: float
    confusion_matrix: Dict[str, Dict[str, int]]
    per_dimension_mae: Dict[str, float]
    group_median_absolute_error: Dict[str, float]
    thresholds: CalibrationThresholds
    passed: bool
    failures: List[str]
    config_diff: Dict[str, Any] = Field(default_factory=dict)


def read_calibration_csv(path: Union[str, Path]) -> List[CalibrationReview]:
    """Read the fixed private-review CSV contract with explicit numeric parsing."""

    reviews: List[CalibrationReview] = []
    with Path(path).open("r", encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        actual_fields = tuple(reader.fieldnames or ())
        if set(actual_fields) != set(CALIBRATION_FIELDS):
            missing = sorted(set(CALIBRATION_FIELDS) - set(actual_fields))
            unexpected = sorted(set(actual_fields) - set(CALIBRATION_FIELDS))
            raise CalibrationError(
                f"invalid calibration CSV columns; missing={missing}, unexpected={unexpected}"
            )
        for line_number, row in enumerate(reader, start=2):
            try:
                reviews.append(
                    CalibrationReview(
                        resume_id=row["resume_id"],
                        reviewer_id=row["reviewer_id"],
                        systems_network_foundation=_parse_float(
                            row["systems_network_foundation"], "systems_network_foundation"
                        ),
                        programming_automation=_parse_float(
                            row["programming_automation"], "programming_automation"
                        ),
                        troubleshooting=_parse_float(row["troubleshooting"], "troubleshooting"),
                        cloud_distributed_infrastructure=_parse_float(
                            row["cloud_distributed_infrastructure"],
                            "cloud_distributed_infrastructure",
                        ),
                        reliability_engineering=_parse_float(
                            row["reliability_engineering"], "reliability_engineering"
                        ),
                        ai_engineering_aiops=_parse_float(
                            row["ai_engineering_aiops"], "ai_engineering_aiops"
                        ),
                        resume_quality=_parse_float(row["resume_quality"], "resume_quality"),
                        overall_grade=row["overall_grade"],
                        notes=row["notes"],
                    )
                )
            except (KeyError, TypeError, ValueError) as exc:
                raise CalibrationError(f"invalid calibration CSV row {line_number}: {exc}") from exc
    if not reviews:
        raise CalibrationError("calibration CSV contains no reviews")
    return reviews


def weighted_kappa(first: Sequence[float], second: Sequence[float]) -> float:
    """Quadratic weighted Cohen's kappa without a scipy dependency."""

    if len(first) != len(second) or not first:
        raise CalibrationError("weighted_kappa requires two non-empty, equal-length sequences")
    values = sorted(set(float(item) for item in first) | set(float(item) for item in second))
    if len(values) == 1:
        return 1.0
    span = values[-1] - values[0]
    observed = sum(
        ((float(a) - float(b)) / span) ** 2 for a, b in zip(first, second, strict=True)
    ) / len(first)
    first_counts = {
        value: sum(float(item) == value for item in first) / len(first) for value in values
    }
    second_counts = {
        value: sum(float(item) == value for item in second) / len(second) for value in values
    }
    expected = sum(
        first_counts[a] * second_counts[b] * ((a - b) / span) ** 2 for a in values for b in values
    )
    # With at least two observed rating values, marginal expected disagreement
    # is strictly positive; the single-value case returned above.
    return max(-1.0, min(1.0, 1.0 - observed / expected))


def spearman_correlation(first: Sequence[float], second: Sequence[float]) -> float:
    """Spearman rank correlation with average ranks for ties."""

    if len(first) != len(second) or not first:
        raise CalibrationError(
            "spearman_correlation requires two non-empty, equal-length sequences"
        )
    first_ranks = _average_ranks(first)
    second_ranks = _average_ranks(second)
    first_mean = statistics.fmean(first_ranks)
    second_mean = statistics.fmean(second_ranks)
    numerator = sum(
        (a - first_mean) * (b - second_mean) for a, b in zip(first_ranks, second_ranks, strict=True)
    )
    first_norm = math.sqrt(sum((item - first_mean) ** 2 for item in first_ranks))
    second_norm = math.sqrt(sum((item - second_mean) ** 2 for item in second_ranks))
    if first_norm == 0.0 or second_norm == 0.0:
        return 1.0 if list(first) == list(second) else 0.0
    return max(-1.0, min(1.0, numerator / (first_norm * second_norm)))


def median_absolute_error(expected: Sequence[float], actual: Sequence[float]) -> float:
    if len(expected) != len(actual) or not expected:
        raise CalibrationError(
            "median_absolute_error requires two non-empty, equal-length sequences"
        )
    return float(
        statistics.median(abs(float(a) - float(b)) for a, b in zip(expected, actual, strict=True))
    )


def grade_confusion(expected: Sequence[str], actual: Sequence[str]) -> Dict[str, Dict[str, int]]:
    if len(expected) != len(actual):
        raise CalibrationError("grade_confusion requires equal-length sequences")
    matrix = {grade: {candidate: 0 for candidate in GRADES} for grade in GRADES}
    for expected_grade, actual_grade in zip(expected, actual, strict=True):
        if expected_grade not in matrix or actual_grade not in matrix[expected_grade]:
            raise CalibrationError("unknown grade in confusion matrix")
        matrix[expected_grade][actual_grade] += 1
    return matrix


class CalibrationEvaluator:
    def __init__(self, thresholds: Optional[CalibrationThresholds] = None) -> None:
        self.thresholds = thresholds or CalibrationThresholds()
        self._grade_calculator = ScoreCalculator()

    def evaluate(
        self,
        reviews: Sequence[CalibrationReview],
        tool_scores: Mapping[str, Union[ScoreResult, Mapping[str, Any]]],
        metadata: Optional[Mapping[str, Mapping[str, str]]] = None,
        config_diff: Optional[Mapping[str, Any]] = None,
    ) -> CalibrationReport:
        grouped: Dict[str, List[CalibrationReview]] = defaultdict(list)
        for review in reviews:
            grouped[review.resume_id].append(review)
        if not grouped:
            raise CalibrationError("no calibration reviews supplied")

        ordered_ids = sorted(grouped)
        reviewer_ids = sorted({review.reviewer_id for review in reviews})
        if len(reviewer_ids) != 2:
            raise CalibrationError("calibration requires exactly two distinct reviewers")
        for resume_id in ordered_ids:
            sample_reviews = grouped[resume_id]
            complete_pair = len(sample_reviews) == 2 and {
                item.reviewer_id for item in sample_reviews
            } == set(reviewer_ids)
            if not complete_pair:
                raise CalibrationError(
                    f"resume {resume_id} must have one review from each reviewer"
                )
            if resume_id not in tool_scores:
                raise CalibrationError(f"missing tool score for resume {resume_id}")

        reviewer_kappa: Dict[str, float] = {}
        for dimension in CALIBRATION_REVIEW_DIMENSIONS:
            first = [
                _review_for(grouped[item], reviewer_ids[0]).model_dump()[dimension]
                for item in ordered_ids
            ]
            second = [
                _review_for(grouped[item], reviewer_ids[1]).model_dump()[dimension]
                for item in ordered_ids
            ]
            reviewer_kappa[dimension] = weighted_kappa(first, second)
        grade_scale = {grade: float(len(GRADES) - index) for index, grade in enumerate(GRADES)}
        reviewer_kappa["overall_grade"] = weighted_kappa(
            [
                grade_scale[_review_for(grouped[item], reviewer_ids[0]).overall_grade]
                for item in ordered_ids
            ],
            [
                grade_scale[_review_for(grouped[item], reviewer_ids[1]).overall_grade]
                for item in ordered_ids
            ],
        )

        human_totals: List[float] = []
        tool_totals: List[float] = []
        human_grades: List[str] = []
        tool_grades: List[str] = []
        dimension_errors: Dict[str, List[float]] = {
            dimension: [] for dimension in CALIBRATION_REVIEW_DIMENSIONS
        }
        sample_errors: Dict[str, float] = {}

        for resume_id in ordered_ids:
            pair = grouped[resume_id]
            human_dimensions = {
                dimension: statistics.fmean(float(getattr(review, dimension)) for review in pair)
                for dimension in CALIBRATION_DIMENSIONS
            }
            human_total = sum(
                human_dimensions[key] * DIMENSION_WEIGHTS[key] for key in CALIBRATION_DIMENSIONS
            )
            tool_score = tool_scores[resume_id]
            tool_total = _tool_total(tool_score)
            human_grade = self._grade_calculator.grade_for_score(round(human_total, 1)).grade
            tool_grade = _tool_grade(tool_score)

            human_totals.append(human_total)
            tool_totals.append(tool_total)
            human_grades.append(human_grade)
            tool_grades.append(tool_grade)
            sample_errors[resume_id] = abs(human_total - tool_total)
            for dimension in CALIBRATION_DIMENSIONS:
                dimension_errors[dimension].append(
                    abs(human_dimensions[dimension] - _tool_dimension_score(tool_score, dimension))
                )
            human_quality = statistics.fmean(review.resume_quality for review in pair)
            dimension_errors["resume_quality"].append(
                abs(human_quality - _tool_dimension_score(tool_score, "resume_quality"))
            )

        mean_kappa = statistics.fmean(reviewer_kappa.values())
        spearman = spearman_correlation(human_totals, tool_totals)
        median_error = median_absolute_error(human_totals, tool_totals)
        agreement = sum(
            expected == actual for expected, actual in zip(human_grades, tool_grades, strict=True)
        ) / len(human_grades)
        group_errors = _group_errors(sample_errors, metadata or {})

        failures: List[str] = []
        if len(ordered_ids) < self.thresholds.minimum_sample_count:
            failures.append("calibration sample count below threshold")
        if len(ordered_ids) > self.thresholds.maximum_sample_count:
            failures.append("calibration sample count above threshold")
        if mean_kappa < self.thresholds.minimum_weighted_kappa:
            failures.append("reviewer weighted kappa below threshold")
        if spearman < self.thresholds.minimum_spearman:
            failures.append("tool-human Spearman correlation below threshold")
        if median_error > self.thresholds.maximum_median_absolute_error:
            failures.append("median absolute error above threshold")
        if agreement < self.thresholds.minimum_grade_agreement:
            failures.append("grade agreement below threshold")

        return CalibrationReport(
            sample_count=len(ordered_ids),
            reviewer_count=len(reviewer_ids),
            reviewer_weighted_kappa={key: round(value, 4) for key, value in reviewer_kappa.items()},
            mean_reviewer_kappa=round(mean_kappa, 4),
            tool_human_spearman=round(spearman, 4),
            median_absolute_error=round(median_error, 4),
            grade_agreement=round(agreement, 4),
            confusion_matrix=grade_confusion(human_grades, tool_grades),
            per_dimension_mae={
                key: round(statistics.fmean(values), 4) for key, values in dimension_errors.items()
            },
            group_median_absolute_error=group_errors,
            thresholds=self.thresholds,
            passed=not failures,
            failures=failures,
            config_diff=dict(config_diff or {}),
        )


def evaluate_calibration_csv(
    reviews_path: Union[str, Path],
    tool_scores: Mapping[str, Union[ScoreResult, Mapping[str, Any]]],
    metadata: Optional[Mapping[str, Mapping[str, str]]] = None,
    config_diff: Optional[Mapping[str, Any]] = None,
    thresholds: Optional[CalibrationThresholds] = None,
) -> CalibrationReport:
    return CalibrationEvaluator(thresholds).evaluate(
        read_calibration_csv(reviews_path),
        tool_scores,
        metadata=metadata,
        config_diff=config_diff,
    )


def render_calibration_markdown(report: CalibrationReport) -> str:
    """Render a stable, privacy-minimized calibration summary."""

    status = "PASS" if report.passed else "FAIL"
    lines = [
        "# SRE Resume Analyzer Calibration Report",
        "",
        f"- Status: **{status}**",
        f"- Samples: {report.sample_count}",
        f"- Reviewers: {report.reviewer_count}",
        f"- Mean reviewer weighted kappa: {report.mean_reviewer_kappa:.4f}",
        f"- Tool-human Spearman: {report.tool_human_spearman:.4f}",
        f"- Median absolute error: {report.median_absolute_error:.4f}",
        f"- Grade agreement: {report.grade_agreement:.2%}",
        "",
        "## Per-dimension error",
        "",
    ]
    for dimension in CALIBRATION_REVIEW_DIMENSIONS:
        lines.append(f"- {dimension}: {report.per_dimension_mae[dimension]:.4f}")
    if report.group_median_absolute_error:
        lines.extend(["", "## Group error", ""])
        for group in sorted(report.group_median_absolute_error):
            lines.append(f"- {group}: {report.group_median_absolute_error[group]:.4f}")
    if report.config_diff:
        lines.extend(["", "## Scoring configuration diff", ""])
        for path in sorted(report.config_diff):
            change = report.config_diff[path]
            lines.append(f"- `{path}`: {json.dumps(change, ensure_ascii=False, sort_keys=True)}")
    if report.failures:
        lines.extend(["", "## Failed thresholds", ""])
        lines.extend("- " + failure for failure in report.failures)
    return "\n".join(lines) + "\n"


def scoring_config_diff(
    baseline: ScoringConfig,
    candidate: ScoringConfig,
) -> Dict[str, Any]:
    """Return a stable, flattened diff between two validated scoring configurations."""

    changes: Dict[str, Any] = {}

    def compare(path: str, before: Any, after: Any) -> None:
        if isinstance(before, Mapping) and isinstance(after, Mapping):
            for key in sorted(set(before) | set(after)):
                child = f"{path}.{key}" if path else str(key)
                compare(child, before.get(key), after.get(key))
            return
        if before != after:
            changes[path] = {"before": before, "after": after}

    compare(
        "",
        baseline.model_dump(mode="json"),
        candidate.model_dump(mode="json"),
    )
    return changes


def _parse_float(value: str, field: str) -> float:
    try:
        return float(value)
    except (TypeError, ValueError) as exc:
        raise CalibrationError(f"{field} must be numeric") from exc


def _average_ranks(values: Sequence[float]) -> List[float]:
    ordered = sorted(enumerate(values), key=lambda pair: (float(pair[1]), pair[0]))
    ranks = [0.0] * len(values)
    index = 0
    while index < len(ordered):
        end = index + 1
        while end < len(ordered) and float(ordered[end][1]) == float(ordered[index][1]):
            end += 1
        average_rank = (index + 1 + end) / 2.0
        for position in range(index, end):
            ranks[ordered[position][0]] = average_rank
        index = end
    return ranks


def _review_for(reviews: Sequence[CalibrationReview], reviewer_id: str) -> CalibrationReview:
    return next(review for review in reviews if review.reviewer_id == reviewer_id)


def _tool_total(score: Union[ScoreResult, Mapping[str, Any]]) -> float:
    value = score.total_score if isinstance(score, ScoreResult) else score["total_score"]
    return float(value)


def _tool_grade(score: Union[ScoreResult, Mapping[str, Any]]) -> str:
    if isinstance(score, ScoreResult):
        return score.grade.grade
    grade = score["grade"]
    return str(grade["grade"] if isinstance(grade, Mapping) else grade)


def _tool_dimension_score(score: Union[ScoreResult, Mapping[str, Any]], dimension: str) -> float:
    if dimension == "resume_quality":
        if isinstance(score, ScoreResult):
            return float(score.resume_quality.score)
        quality = score["resume_quality"]
        if isinstance(quality, Mapping):
            return float(quality["score"])
        if hasattr(quality, "score"):
            return float(quality.score)
        raise CalibrationError("tool resume_quality has no score")
    if isinstance(score, ScoreResult):
        for name, dimension_score in score.dimension_scores.items():
            if name == dimension:
                return float(dimension_score.score)
        raise CalibrationError(f"tool score is missing dimension {dimension}")
    dimensions = score["dimension_scores"]
    if not isinstance(dimensions, Mapping):
        raise CalibrationError("tool dimension_scores must be an object")
    value = dimensions[dimension]
    if isinstance(value, Mapping):
        return float(value["score"])
    if hasattr(value, "score"):
        return float(value.score)
    raise CalibrationError(f"tool dimension {dimension} has no score")


def _group_errors(
    sample_errors: Mapping[str, float],
    metadata: Mapping[str, Mapping[str, str]],
) -> Dict[str, float]:
    grouped: Dict[str, List[float]] = defaultdict(list)
    for resume_id, error in sample_errors.items():
        for key, value in sorted(metadata.get(resume_id, {}).items()):
            grouped[f"{key}={value}"].append(error)
    return {
        key: round(float(statistics.median(values)), 4) for key, values in sorted(grouped.items())
    }
