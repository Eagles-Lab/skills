"""Private two-reviewer calibration reporting for future scoring validation."""

from __future__ import annotations

import csv
import statistics
from collections import defaultdict
from pathlib import Path
from typing import Any

from .analyzer import load_resume
from .errors import InputValidationError
from .scoring import DIMENSION_WEIGHTS, DIMENSIONS, ScoreCalculator

REQUIRED_COLUMNS = {
    "resume_id",
    "reviewer_id",
    *DIMENSIONS,
    "resume_quality",
    "overall_grade",
    "notes",
}
GRADE_ORDER = {"F": 0, "D": 1, "C": 2, "B": 3, "A": 4, "A+": 5}


def evaluate(resumes_dir: Path, reviews_csv: Path) -> dict[str, Any]:
    rows = _read_reviews(reviews_csv)
    grouped: dict[str, list[dict[str, str]]] = defaultdict(list)
    for row in rows:
        grouped[row["resume_id"]].append(row)
    scores: dict[str, Any] = {}
    for path in sorted(Path(resumes_dir).glob("*.json")):
        resume = load_resume(path)
        if not resume.resume_id:
            raise InputValidationError("calibration canonical resumes require explicit resume_id")
        review_rows = grouped.get(resume.resume_id, [])
        if len(review_rows) != 2 or len({row["reviewer_id"] for row in review_rows}) != 2:
            raise InputValidationError(
                f"resume_id {resume.resume_id} requires two independent reviewers"
            )
        scores[resume.resume_id] = ScoreCalculator().calculate(resume)
    if set(scores) != set(grouped):
        raise InputValidationError("reviews and canonical resume_id sets must match exactly")
    tool_human: list[tuple[float, float]] = []
    grade_matches = 0
    dimension_errors: dict[str, list[float]] = {key: [] for key in DIMENSIONS}
    for resume_id, review_rows in sorted(grouped.items()):
        totals = []
        for row in review_rows:
            total = sum(float(row[key]) * DIMENSION_WEIGHTS[key] for key in DIMENSIONS)
            totals.append(total)
        human = statistics.mean(totals)
        tool = scores[resume_id].total_score
        tool_human.append((tool, human))
        if scores[resume_id].grade.grade in {row["overall_grade"] for row in review_rows}:
            grade_matches += 1
        for key in DIMENSIONS:
            dimension_errors[key].append(
                abs(
                    scores[resume_id].dimension_scores[key].score
                    - statistics.mean(float(row[key]) for row in review_rows)
                )
            )
    spearman = _spearman(tool_human)
    absolute_errors = [abs(tool - human) for tool, human in tool_human]
    grade_agreement = grade_matches / len(grouped) if grouped else 0.0
    thresholds = {
        "tool_human_spearman": 0.75,
        "median_absolute_error_max": 1.0,
        "grade_agreement": 0.80,
    }
    median_absolute_error = round(statistics.median(absolute_errors), 4)
    metrics = {
        "tool_human_spearman": round(spearman, 4),
        "median_absolute_error": median_absolute_error,
        "grade_agreement": round(grade_agreement, 4),
        "dimension_mean_absolute_error": {
            key: round(statistics.mean(values), 4) for key, values in dimension_errors.items()
        },
    }
    passed = spearman >= 0.75 and median_absolute_error <= 1.0 and grade_agreement >= 0.80
    return {
        "schema_version": "1.0",
        "calibration_status": "not_calibrated",
        "sample_count": len(grouped),
        "metrics": metrics,
        "thresholds": thresholds,
        "thresholds_passed": passed,
        "passed": passed,
    }


def render_markdown(report: dict[str, Any]) -> str:
    metrics = report["metrics"]
    return "\n".join(
        [
            "# Development Resume Analyzer calibration report",
            "",
            f"- status: `{report['calibration_status']}`",
            f"- samples: {report['sample_count']}",
            f"- tool-human Spearman: {metrics['tool_human_spearman']}",
            f"- median absolute error: {metrics['median_absolute_error']}",
            f"- grade agreement: {metrics['grade_agreement']}",
            "",
            "Passing this private report does not change released score files until a separately reviewed calibration release.",
        ]
    )


def _read_reviews(path: Path) -> list[dict[str, str]]:
    try:
        with Path(path).open(encoding="utf-8-sig", newline="") as handle:
            reader = csv.DictReader(handle)
            if not reader.fieldnames or not REQUIRED_COLUMNS.issubset(reader.fieldnames):
                raise InputValidationError("calibration CSV is missing required columns")
            rows = [dict(row) for row in reader]
    except OSError as exc:
        raise InputValidationError(
            f"calibration CSV could not be read: {type(exc).__name__}"
        ) from exc
    for row in rows:
        for key in DIMENSIONS:
            value = float(row[key])
            if not 1.0 <= value <= 10.0:
                raise InputValidationError(f"calibration score {key} must be in 1..10")
        if row["overall_grade"] not in GRADE_ORDER:
            raise InputValidationError("calibration grade is invalid")
    return rows


def _rank(values: list[float]) -> list[float]:
    order = sorted(range(len(values)), key=lambda index: values[index])
    ranks = [0.0] * len(values)
    index = 0
    while index < len(order):
        end = index + 1
        while end < len(order) and values[order[end]] == values[order[index]]:
            end += 1
        rank = (index + end - 1) / 2 + 1
        for position in order[index:end]:
            ranks[position] = rank
        index = end
    return ranks


def _spearman(pairs: list[tuple[float, float]]) -> float:
    if len(pairs) < 2:
        return 0.0
    left, right = zip(*pairs, strict=True)
    a, b = _rank(list(left)), _rank(list(right))
    mean_a, mean_b = statistics.mean(a), statistics.mean(b)
    numerator = sum((x - mean_a) * (y - mean_b) for x, y in zip(a, b, strict=True))
    denominator = (sum((x - mean_a) ** 2 for x in a) * sum((y - mean_b) ** 2 for y in b)) ** 0.5
    return numerator / denominator if denominator else 0.0
