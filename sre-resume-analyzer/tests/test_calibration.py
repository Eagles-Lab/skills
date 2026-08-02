from __future__ import annotations

import copy
import csv
from pathlib import Path

import pytest

from sre_resume_analyzer.calibration import (
    CALIBRATION_DIMENSIONS,
    CALIBRATION_FIELDS,
    CalibrationError,
    CalibrationEvaluator,
    CalibrationReview,
    CalibrationThresholds,
    grade_confusion,
    median_absolute_error,
    read_calibration_csv,
    render_calibration_markdown,
    scoring_config_diff,
    spearman_correlation,
    weighted_kappa,
)
from sre_resume_analyzer.scoring import DEFAULT_SCORING_CONFIG, ScoreCalculator, ScoringConfig


def review(resume_id: str, reviewer_id: str, value: float) -> CalibrationReview:
    grade = ScoreCalculator().grade_for_score(value).grade
    return CalibrationReview(
        resume_id=resume_id,
        reviewer_id=reviewer_id,
        systems_network_foundation=value,
        programming_automation=value,
        troubleshooting=value,
        cloud_distributed_infrastructure=value,
        reliability_engineering=value,
        ai_engineering_aiops=value,
        resume_quality=value,
        overall_grade=grade,
        notes="",
    )


def tool_score(value: float) -> dict[str, object]:
    grade = ScoreCalculator().grade_for_score(value).grade
    return {
        "total_score": value,
        "grade": {"grade": grade},
        "dimension_scores": {name: {"score": value} for name in CALIBRATION_DIMENSIONS},
        "resume_quality": {"score": value},
    }


def test_csv_contract_uses_six_dimensions_and_no_ai_bonus(tmp_path: Path):
    path = tmp_path / "reviews.csv"
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=CALIBRATION_FIELDS)
        writer.writeheader()
        writer.writerow(review("r1", "a", 6.0).model_dump())
    values = read_calibration_csv(path)
    assert values[0].ai_engineering_aiops == 6.0
    assert "ai_bonus" not in CALIBRATION_FIELDS


def test_csv_wrong_columns_and_bad_numeric_fail(tmp_path: Path):
    wrong = tmp_path / "wrong.csv"
    wrong.write_text("resume_id,reviewer_id\nr,a\n")
    with pytest.raises(CalibrationError, match="columns"):
        read_calibration_csv(wrong)
    bad = tmp_path / "bad.csv"
    with bad.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=CALIBRATION_FIELDS)
        writer.writeheader()
        row = review("r", "a", 6.0).model_dump()
        row["troubleshooting"] = "bad"
        writer.writerow(row)
    with pytest.raises(CalibrationError, match="numeric"):
        read_calibration_csv(bad)


def test_calibration_passes_for_aligned_reviewers_and_tool():
    reviews = [
        review(resume_id, reviewer, value)
        for resume_id, value in (("r1", 4.0), ("r2", 8.0), ("r3", 6.0))
        for reviewer in ("a", "b")
    ]
    thresholds = CalibrationThresholds(minimum_sample_count=3, maximum_sample_count=3)
    report = CalibrationEvaluator(thresholds).evaluate(
        reviews,
        {"r1": tool_score(4.0), "r2": tool_score(8.0), "r3": tool_score(6.0)},
        metadata={"r1": {"language": "zh"}, "r2": {"language": "en"}},
    )
    assert report.passed
    assert report.tool_human_spearman == 1.0
    assert report.median_absolute_error == 0.0
    assert report.grade_agreement == 1.0
    assert set(report.per_dimension_mae) == {*CALIBRATION_DIMENSIONS, "resume_quality"}
    assert "Status: **PASS**" in render_calibration_markdown(report)


def test_default_threshold_keeps_small_or_bad_calibration_experimental():
    reviews = [review("r1", "a", 4.0), review("r1", "b", 8.0)]
    report = CalibrationEvaluator().evaluate(reviews, {"r1": tool_score(1.0)})
    assert not report.passed
    assert "calibration sample count below threshold" in report.failures


def test_incomplete_review_pairs_and_missing_scores_fail():
    with pytest.raises(CalibrationError, match="exactly two"):
        CalibrationEvaluator().evaluate([review("r1", "a", 4.0)], {"r1": tool_score(4.0)})
    with pytest.raises(CalibrationError, match="missing tool score"):
        CalibrationEvaluator().evaluate([review("r1", "a", 4.0), review("r1", "b", 4.0)], {})


def test_metric_helpers_cover_ties_errors_and_confusion():
    assert weighted_kappa([1, 2, 3], [1, 2, 3]) == pytest.approx(1.0)
    assert weighted_kappa([2, 2], [2, 2]) == 1.0
    assert spearman_correlation([1, 2, 2], [2, 3, 3]) == pytest.approx(1.0)
    assert median_absolute_error([1, 3], [2, 4]) == 1.0
    matrix = grade_confusion(["A", "B"], ["A", "C"])
    assert matrix["A"]["A"] == 1
    assert matrix["B"]["C"] == 1
    with pytest.raises(CalibrationError):
        weighted_kappa([], [])
    with pytest.raises(CalibrationError):
        grade_confusion(["X"], ["A"])


def test_scoring_config_diff_is_stable():
    baseline = ScoringConfig.model_validate(copy.deepcopy(DEFAULT_SCORING_CONFIG))
    changed = copy.deepcopy(DEFAULT_SCORING_CONFIG)
    changed["version"] = "candidate"
    candidate = ScoringConfig.model_validate(changed)
    assert scoring_config_diff(baseline, candidate) == {
        "version": {"before": "cn-campus-sre-1.0.0", "after": "candidate"}
    }
