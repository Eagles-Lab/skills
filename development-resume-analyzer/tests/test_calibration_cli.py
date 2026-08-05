from __future__ import annotations

import csv
import json
from pathlib import Path

import pytest

from development_resume_analyzer.calibration import REQUIRED_COLUMNS, evaluate, render_markdown
from development_resume_analyzer.cli import batch_main, calibrate_main, extract_main
from development_resume_analyzer.errors import InputValidationError
from development_resume_analyzer.models import Resume
from development_resume_analyzer.scoring import DIMENSIONS, ScoreCalculator

FIXTURES = Path(__file__).parent / "fixtures"


def _calibration_data(tmp_path: Path) -> tuple[Path, Path]:
    resumes = tmp_path / "resumes"
    resumes.mkdir()
    empty = Resume(resume_id="empty")
    complete_data = json.loads((FIXTURES / "complete.json").read_text())
    complete_data["resume_id"] = "complete"
    complete = Resume.model_validate(complete_data)
    for name, resume in (("empty", empty), ("complete", complete)):
        (resumes / f"{name}.json").write_text(resume.model_dump_json())
    reviews = tmp_path / "reviews.csv"
    fields = sorted(REQUIRED_COLUMNS)
    with reviews.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        for resume in (empty, complete):
            score = ScoreCalculator().calculate(resume)
            for reviewer in ("r1", "r2"):
                row = {
                    "resume_id": resume.resume_id,
                    "reviewer_id": reviewer,
                    "resume_quality": score.resume_quality.score,
                    "overall_grade": score.grade.grade,
                    "notes": "independent review",
                }
                row.update({key: score.dimension_scores[key].score for key in DIMENSIONS})
                writer.writerow(row)
    return resumes, reviews


def test_calibration_report_passes_exact_independent_reviews(tmp_path: Path) -> None:
    resumes, reviews = _calibration_data(tmp_path)
    report = evaluate(resumes, reviews)
    assert report["passed"] is True
    assert report["thresholds_passed"] is True
    assert report["calibration_status"] == "not_calibrated"
    assert "reviewer_weighted_kappa" not in report["metrics"]
    assert "reviewer_weighted_kappa" not in report["thresholds"]
    assert report["metrics"]["tool_human_spearman"] == 1.0
    markdown = render_markdown(report)
    assert "separately reviewed calibration release" in markdown


def test_calibration_cli_writes_private_bundle(tmp_path: Path) -> None:
    resumes, reviews = _calibration_data(tmp_path)
    output = tmp_path / "report"
    assert (
        calibrate_main(
            [
                "--resumes",
                str(resumes),
                "--reviews",
                str(reviews),
                "--output-dir",
                str(output),
            ]
        )
        == 0
    )
    assert (output / "calibration_report.json").exists()
    assert (
        calibrate_main(
            ["--resumes", str(resumes), "--reviews", str(reviews), "--output-dir", str(output)]
        )
        == 5
    )


def test_calibration_rejects_bad_csv_and_missing_reviewers(tmp_path: Path) -> None:
    resumes = tmp_path / "resumes"
    resumes.mkdir()
    (resumes / "one.json").write_text(Resume(resume_id="one").model_dump_json())
    bad = tmp_path / "bad.csv"
    bad.write_text("resume_id,reviewer_id\none,r1\n")
    with pytest.raises(InputValidationError):
        evaluate(resumes, bad)


def test_extract_cli_pdf_and_output_errors(tmp_path: Path) -> None:
    not_pdf = tmp_path / "resume.txt"
    not_pdf.write_text("not a pdf")
    assert extract_main([str(not_pdf), "--output", str(tmp_path / "raw_extraction.json")]) == 4
    fake_pdf = tmp_path / "broken.pdf"
    fake_pdf.write_bytes(b"not a pdf")
    assert extract_main([str(fake_pdf), "--output", str(tmp_path / "extracted.json")]) == 5


def test_batch_cli_rejects_missing_input(tmp_path: Path) -> None:
    assert (
        batch_main(
            [
                "--input-dir",
                str(tmp_path / "missing"),
                "--output-dir",
                str(tmp_path / "out"),
            ]
        )
        == 2
    )
