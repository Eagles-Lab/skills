import shutil
from pathlib import Path

import pytest

from sre_resume_analyzer import calibration, cli, scoring
from sre_resume_analyzer.errors import (
    AnalyzerError,
    InputValidationError,
    OutputSafetyError,
    PDFExtractionError,
)

FIXTURES = Path(__file__).parent / "fixtures"


def test_analyze_cli_success(monkeypatch, capsys, tmp_path):
    class FakeAnalyzer:
        def __init__(self, output_dir):
            assert output_dir == tmp_path / "out"

        def analyze(self, *args, **kwargs):
            return {"score": str(tmp_path / "out" / "id" / "score.json")}

    monkeypatch.setattr(cli, "ResumeAnalyzer", FakeAnalyzer)
    code = cli.analyze_main(
        ["--extracted", str(tmp_path / "resume.json"), "--output-dir", str(tmp_path / "out")]
    )

    assert code == 0
    assert '"status": "success"' in capsys.readouterr().out


def test_analyze_cli_exit_categories(monkeypatch, tmp_path):
    class FakeAnalyzer:
        def __init__(self, output_dir):
            pass

        def analyze(self, *args, **kwargs):
            raise InputValidationError("invalid schema")

    monkeypatch.setattr(cli, "ResumeAnalyzer", FakeAnalyzer)
    args = ["--extracted", "bad.json", "--output-dir", str(tmp_path / "out")]
    assert cli.analyze_main(args) == 2

    FakeAnalyzer.analyze = lambda self, *args, **kwargs: (_ for _ in ()).throw(
        OutputSafetyError("unsafe")
    )
    assert cli.analyze_main(args) == 5


def test_extract_cli_never_prints_raw_text(monkeypatch, capsys, tmp_path):
    def fake_extract(pdf, output, **kwargs):
        output.write_text("TOP_SECRET_RAW_TEXT", encoding="utf-8")
        return output

    monkeypatch.setattr(cli, "write_raw_extraction", fake_extract)
    output = tmp_path / "raw_extraction.json"
    code = cli.extract_main([str(tmp_path / "resume.pdf"), "--output", str(output)])
    captured = capsys.readouterr()

    assert code == 0
    assert "TOP_SECRET_RAW_TEXT" not in captured.out
    assert "TOP_SECRET_RAW_TEXT" not in captured.err


def test_batch_cli_returns_partial_failure(monkeypatch, tmp_path):
    class FakeBatch:
        def __init__(self, *args, **kwargs):
            pass

        def process_directory(self, *args, **kwargs):
            return {"total": 2, "successful": 1, "failed": 1}

    monkeypatch.setattr(cli, "BatchProcessor", FakeBatch)
    assert (
        cli.batch_main(["--input-dir", str(tmp_path), "--output-dir", str(tmp_path / "out")]) == 3
    )


def test_calibration_cli_scores_canonical_resumes_in_one_step(monkeypatch, tmp_path):
    resumes = tmp_path / "resumes"
    resumes.mkdir()
    shutil.copy(FIXTURES / "runtime_complete.json", resumes / "one.json")
    reviews = tmp_path / "reviews.csv"
    reviews.write_text("private reviews are mocked", encoding="utf-8")

    class FakeCalculator:
        def __init__(self, config=None):
            self.config = config

        def calculate(self, resume):
            return {"total_score": 8.0}

    class FakeReport:
        passed = True

        def model_dump(self, mode):
            return {"passed": True, "sample_count": 1}

    monkeypatch.setattr(scoring, "ScoreCalculator", FakeCalculator)
    monkeypatch.setattr(
        calibration, "evaluate_calibration_csv", lambda *args, **kwargs: FakeReport()
    )
    monkeypatch.setattr(calibration, "render_calibration_markdown", lambda report: "PASS")
    output = tmp_path / "calibration"

    code = cli.calibrate_main(
        [
            "--resumes",
            str(resumes),
            "--reviews",
            str(reviews),
            "--output-dir",
            str(output),
        ]
    )

    assert code == 0
    assert (output / "calibration_report.json").exists()
    assert (output / "calibration_report.md").exists()


@pytest.mark.parametrize(
    ("error", "code"),
    [(AnalyzerError("analysis"), 1), (KeyboardInterrupt(), 130), (RuntimeError("x"), 1)],
)
def test_analyze_cli_remaining_error_boundaries(monkeypatch, error, code):
    class FakeAnalyzer:
        def __init__(self, output_dir):
            pass

        def analyze(self, *args, **kwargs):
            raise error

    monkeypatch.setattr(cli, "ResumeAnalyzer", FakeAnalyzer)
    assert cli.analyze_main(["--extracted", "resume.json", "--output-dir", "processing"]) == code


@pytest.mark.parametrize(
    ("error", "code"),
    [
        (OutputSafetyError("output"), 5),
        (PDFExtractionError("pdf"), 4),
        (KeyboardInterrupt(), 130),
        (RuntimeError("x"), 1),
    ],
)
def test_extract_cli_error_boundaries(monkeypatch, error, code):
    def fail(*args, **kwargs):
        raise error

    monkeypatch.setattr(cli, "write_raw_extraction", fail)
    assert cli.extract_main(["resume.pdf", "--output", "raw_extraction.json"]) == code


@pytest.mark.parametrize(
    ("error", "code"),
    [
        (InputValidationError("input"), 2),
        (OutputSafetyError("output"), 5),
        (KeyboardInterrupt(), 130),
        (RuntimeError("x"), 1),
    ],
)
def test_batch_cli_error_boundaries(monkeypatch, tmp_path, error, code):
    class FakeBatch:
        def __init__(self, *args, **kwargs):
            pass

        def process_directory(self, *args, **kwargs):
            raise error

    monkeypatch.setattr(cli, "BatchProcessor", FakeBatch)
    assert (
        cli.batch_main(["--input-dir", str(tmp_path), "--output-dir", str(tmp_path / "out")])
        == code
    )


def test_batch_cli_full_success(monkeypatch, tmp_path):
    class FakeBatch:
        def __init__(self, *args, **kwargs):
            pass

        def process_directory(self, *args, **kwargs):
            return {"total": 1, "successful": 1, "failed": 0}

    monkeypatch.setattr(cli, "BatchProcessor", FakeBatch)
    assert (
        cli.batch_main(["--input-dir", str(tmp_path), "--output-dir", str(tmp_path / "out")]) == 0
    )


def test_cli_positive_integer_and_calibration_input_boundaries(tmp_path):
    assert cli._positive_integer("2") == 2
    with pytest.raises(Exception, match="at least 1"):
        cli._positive_integer("0")
    assert (
        cli.calibrate_main(
            [
                "--resumes",
                str(tmp_path / "missing"),
                "--reviews",
                str(tmp_path / "reviews.csv"),
                "--output-dir",
                str(tmp_path / "out"),
            ]
        )
        == 2
    )

    resumes = tmp_path / "resumes"
    resumes.mkdir()
    shutil.copy(FIXTURES / "runtime_minimal.json", resumes / "one.json")
    assert (
        cli.calibrate_main(
            [
                "--resumes",
                str(resumes),
                "--reviews",
                str(tmp_path / "reviews.csv"),
                "--output-dir",
                str(tmp_path / "out"),
                "--candidate-config",
                str(tmp_path / "missing-config.yaml"),
            ]
        )
        == 2
    )

    empty = tmp_path / "empty"
    empty.mkdir()
    assert (
        cli.calibrate_main(
            [
                "--resumes",
                str(empty),
                "--reviews",
                str(tmp_path / "reviews.csv"),
                "--output-dir",
                str(tmp_path / "out"),
            ]
        )
        == 2
    )
