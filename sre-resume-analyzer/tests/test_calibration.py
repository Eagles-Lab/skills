from pathlib import Path

import pytest

from sre_resume_analyzer.calibration import (
    CalibrationError,
    CalibrationEvaluator,
    CalibrationThresholds,
    _tool_dimension_score,
    _tool_grade,
    _tool_total,
    evaluate_calibration_csv,
    grade_confusion,
    median_absolute_error,
    read_calibration_csv,
    render_calibration_markdown,
    scoring_config_diff,
    spearman_correlation,
    weighted_kappa,
)
from sre_resume_analyzer.models import Resume
from sre_resume_analyzer.scoring import ScoreCalculator, ScoringConfig

FIXTURES = Path(__file__).parent / "fixtures"
DIMENSIONS = (
    "monitoring",
    "alerting",
    "automation",
    "containerization",
    "incident_handling",
    "resume_quality",
)


def tool_score(value, grade):
    return {
        "total_score": value,
        "grade": {"grade": grade},
        "dimension_scores": {dimension: {"score": min(value, 10.0)} for dimension in DIMENSIONS},
    }


def calibrated_scores():
    return {
        "cal-1": tool_score(2.0, "F"),
        "cal-2": tool_score(4.0, "D"),
        "cal-3": tool_score(6.0, "C"),
        "cal-4": tool_score(8.5, "A"),
    }


def test_csv_reader_uses_fixed_contract():
    reviews = read_calibration_csv(FIXTURES / "calibration_reviews.csv")

    assert len(reviews) == 8
    assert {item.reviewer_id for item in reviews} == {"sre-a", "sre-b"}


def test_core_metrics_handle_ties_without_scipy():
    assert weighted_kappa([1, 2, 3, 4], [1, 2, 3, 4]) == pytest.approx(1.0)
    assert weighted_kappa([2, 2], [2, 2]) == pytest.approx(1.0)
    assert spearman_correlation([1, 2, 2, 4], [1, 3, 3, 8]) == pytest.approx(1.0)
    assert spearman_correlation([1, 1], [1, 1]) == pytest.approx(1.0)
    assert spearman_correlation([1, 1], [2, 2]) == pytest.approx(0.0)
    assert median_absolute_error([1, 2, 3], [1, 4, 2]) == pytest.approx(1.0)
    assert grade_confusion(["A", "B"], ["A", "C"])["B"]["C"] == 1


def test_calibration_evaluator_reports_pass_groups_and_config_diff():
    reviews = read_calibration_csv(FIXTURES / "calibration_reviews.csv")
    metadata = {
        "cal-1": {"language": "zh", "resume_type": "student"},
        "cal-2": {"language": "zh", "resume_type": "student"},
        "cal-3": {"language": "en", "resume_type": "experienced"},
        "cal-4": {"language": "en", "resume_type": "experienced"},
    }

    report = CalibrationEvaluator(CalibrationThresholds(minimum_sample_count=4)).evaluate(
        reviews,
        calibrated_scores(),
        metadata=metadata,
        config_diff={"version": {"before": "2", "after": "3"}},
    )

    assert report.passed is True
    assert report.mean_reviewer_kappa == 1.0
    assert report.tool_human_spearman == 1.0
    assert report.median_absolute_error == 0.0
    assert report.grade_agreement == 1.0
    assert set(report.group_median_absolute_error) == {
        "language=en",
        "language=zh",
        "resume_type=experienced",
        "resume_type=student",
    }
    assert report.config_diff["version"]["after"] == "3"
    markdown = render_calibration_markdown(report)
    assert "Status: **PASS**" in markdown
    assert "## Scoring configuration diff" in markdown


def test_calibration_evaluator_fails_bad_tool_ordering():
    reviews = read_calibration_csv(FIXTURES / "calibration_reviews.csv")
    reversed_scores = {
        "cal-1": tool_score(8.5, "A"),
        "cal-2": tool_score(6.0, "C"),
        "cal-3": tool_score(4.0, "D"),
        "cal-4": tool_score(2.0, "F"),
    }

    report = CalibrationEvaluator().evaluate(reviews, reversed_scores)

    assert report.passed is False
    assert report.tool_human_spearman == -1.0
    assert report.failures
    markdown = render_calibration_markdown(report)
    assert "Status: **FAIL**" in markdown
    assert "## Failed thresholds" in markdown


def test_calibration_requires_exactly_two_complete_reviewers():
    reviews = read_calibration_csv(FIXTURES / "calibration_reviews.csv")[:-1]

    with pytest.raises(CalibrationError, match="one review from each reviewer"):
        CalibrationEvaluator().evaluate(reviews, calibrated_scores())


def test_csv_reader_rejects_bad_columns_empty_data_and_bad_numeric(tmp_path):
    bad_columns = tmp_path / "bad-columns.csv"
    bad_columns.write_text("resume_id,extra\ncal-1,x\n", encoding="utf-8")
    empty = tmp_path / "empty.csv"
    empty.write_text(
        ",".join(
            [
                "resume_id",
                "reviewer_id",
                "monitoring",
                "alerting",
                "automation",
                "containerization",
                "incident_handling",
                "resume_quality",
                "ai_bonus",
                "overall_grade",
                "notes",
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    bad_numeric = tmp_path / "bad-numeric.csv"
    bad_numeric.write_text(
        empty.read_text(encoding="utf-8") + "cal-1,sre-a,nope,2,2,2,2,2,0,F,fixture\n",
        encoding="utf-8",
    )

    with pytest.raises(CalibrationError, match="columns"):
        read_calibration_csv(bad_columns)
    with pytest.raises(CalibrationError, match="no reviews"):
        read_calibration_csv(empty)
    with pytest.raises(CalibrationError, match="row 2"):
        read_calibration_csv(bad_numeric)


@pytest.mark.parametrize(
    ("function", "first", "second"),
    [
        (weighted_kappa, [], []),
        (weighted_kappa, [1], [1, 2]),
        (spearman_correlation, [], []),
        (spearman_correlation, [1], [1, 2]),
        (median_absolute_error, [], []),
        (median_absolute_error, [1], [1, 2]),
    ],
)
def test_metrics_reject_empty_or_mismatched_inputs(function, first, second):
    with pytest.raises(CalibrationError):
        function(first, second)


def test_grade_confusion_rejects_bad_shapes_and_unknown_grades():
    with pytest.raises(CalibrationError, match="equal-length"):
        grade_confusion(["A"], [])
    with pytest.raises(CalibrationError, match="unknown grade"):
        grade_confusion(["X"], ["A"])


def test_evaluator_rejects_empty_single_reviewer_and_missing_tool_score():
    reviews = read_calibration_csv(FIXTURES / "calibration_reviews.csv")

    with pytest.raises(CalibrationError, match="no calibration reviews"):
        CalibrationEvaluator().evaluate([], {})
    with pytest.raises(CalibrationError, match="exactly two"):
        CalibrationEvaluator().evaluate(
            [review for review in reviews if review.reviewer_id == "sre-a"],
            calibrated_scores(),
        )
    with pytest.raises(CalibrationError, match="missing tool score"):
        CalibrationEvaluator().evaluate(reviews, {"cal-1": calibrated_scores()["cal-1"]})


def test_reviewer_disagreement_fails_kappa_threshold():
    reviews = read_calibration_csv(FIXTURES / "calibration_reviews.csv")
    changed = []
    reverse_grade = {"F": "A", "D": "C", "C": "D", "A": "F"}
    for review in reviews:
        if review.reviewer_id == "sre-a":
            changed.append(review)
            continue
        updates = {dimension: 10.0 - getattr(review, dimension) for dimension in DIMENSIONS}
        updates["overall_grade"] = reverse_grade[review.overall_grade]
        changed.append(review.model_copy(update=updates))

    report = CalibrationEvaluator().evaluate(changed, calibrated_scores())

    assert report.mean_reviewer_kappa < report.thresholds.minimum_weighted_kappa
    assert "reviewer weighted kappa below threshold" in report.failures


def test_csv_evaluation_wrapper_accepts_custom_thresholds():
    report = evaluate_calibration_csv(
        FIXTURES / "calibration_reviews.csv",
        calibrated_scores(),
        thresholds=CalibrationThresholds(
            minimum_sample_count=4,
            minimum_weighted_kappa=0.5,
            minimum_spearman=0.5,
            maximum_median_absolute_error=2.0,
            minimum_grade_agreement=0.5,
        ),
    )

    assert report.passed is True


def test_default_calibration_gate_requires_40_to_60_samples():
    report = CalibrationEvaluator().evaluate(
        read_calibration_csv(FIXTURES / "calibration_reviews.csv"),
        calibrated_scores(),
    )

    assert report.passed is False
    assert "calibration sample count below threshold" in report.failures


def test_scoring_config_diff_is_stable_and_reports_nested_changes():
    baseline = ScoringConfig.from_source()
    changed = baseline.model_dump(mode="python")
    changed["version"] = "candidate"
    changed["evidence_scores"]["usage"] = 5.0
    candidate = ScoringConfig.from_source(changed)

    assert scoring_config_diff(baseline, candidate) == {
        "evidence_scores.usage": {"before": 4.0, "after": 5.0},
        "version": {"before": "3.0.0", "after": "candidate"},
    }


def test_score_result_and_defensive_tool_score_shapes():
    resume = Resume.model_validate_json(
        (FIXTURES / "runtime_minimal.json").read_text(encoding="utf-8")
    )
    result = ScoreCalculator().calculate(resume)

    assert _tool_total(result) == result.total_score
    assert _tool_grade(result) == result.grade.grade
    assert _tool_grade({"grade": "F"}) == "F"
    assert _tool_dimension_score(result, "monitoring") == 1.0

    missing_dimension = result.model_copy(update={"dimension_scores": {}})
    with pytest.raises(CalibrationError, match="missing dimension"):
        _tool_dimension_score(missing_dimension, "monitoring")
    with pytest.raises(CalibrationError, match="must be an object"):
        _tool_dimension_score({"dimension_scores": []}, "monitoring")

    class ScoreLike:
        score = 3.0

    assert (
        _tool_dimension_score({"dimension_scores": {"monitoring": ScoreLike()}}, "monitoring")
        == 3.0
    )
    with pytest.raises(CalibrationError, match="has no score"):
        _tool_dimension_score({"dimension_scores": {"monitoring": object()}}, "monitoring")
