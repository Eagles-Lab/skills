import json
from datetime import datetime, timezone
from pathlib import Path

import pytest

from sre_resume_analyzer.analyzer import ResumeAnalyzer, _model_mapping, _utc_now, load_resume
from sre_resume_analyzer.errors import AnalyzerError, InputValidationError, OutputConflictError
from sre_resume_analyzer.output import OUTPUT_FILENAMES
from sre_resume_analyzer.rendering import RenderingError

FIXTURES = Path(__file__).parent / "fixtures"
FIXED_TIME = datetime(2026, 8, 2, tzinfo=timezone.utc)


class FakeCalculator:
    def calculate(self, resume):
        return json.loads((FIXTURES / "runtime_score.json").read_text(encoding="utf-8"))


def test_v2_input_is_rejected_without_output(tmp_path):
    with pytest.raises(InputValidationError, match="canonical resume schema v3"):
        ResumeAnalyzer(tmp_path / "out", calculator=FakeCalculator()).analyze(
            FIXTURES / "runtime_v2_rejected.json"
        )
    assert not (tmp_path / "out").exists()


def test_analysis_creates_exact_bundle_with_metadata(tmp_path):
    analyzer = ResumeAnalyzer(
        tmp_path,
        calculator=FakeCalculator(),
        clock=lambda: FIXED_TIME,
    )
    paths = analyzer.analyze(FIXTURES / "runtime_complete.json")
    bundle = tmp_path / "candidate_complete"
    score = json.loads((bundle / "score.json").read_text(encoding="utf-8"))
    analysis = json.loads((bundle / "analysis.json").read_text(encoding="utf-8"))

    assert sorted(path.name for path in bundle.iterdir()) == sorted(OUTPUT_FILENAMES)
    assert set(paths) == {"extracted", "score", "analysis", "suggestions", "interview_questions"}
    assert score["schema_version"] == "3.0"
    assert score["analyzer_version"] == "3.0.0-rc.1"
    assert score["generated_at"] == "2026-08-02T00:00:00Z"
    assert len(score["input_sha256"]) == 64
    assert score["scoring_config_version"]
    assert analysis["ai_analysis"]["applications"] == score["ai_bonus"]["applications"]


def test_missing_id_is_stable_and_contact_is_private_by_default(tmp_path):
    first = ResumeAnalyzer(
        tmp_path / "one", calculator=FakeCalculator(), clock=lambda: FIXED_TIME
    ).analyze(FIXTURES / "runtime_minimal.json")
    second = ResumeAnalyzer(
        tmp_path / "two", calculator=FakeCalculator(), clock=lambda: FIXED_TIME
    ).analyze(FIXTURES / "runtime_minimal.json")

    first_dir = Path(first["score"]).parent
    second_dir = Path(second["score"]).parent
    assert first_dir.name == second_dir.name
    for filename in OUTPUT_FILENAMES:
        assert (first_dir / filename).read_bytes() == (second_dir / filename).read_bytes()


def test_contact_requires_explicit_flag(tmp_path):
    default = ResumeAnalyzer(
        tmp_path / "default", calculator=FakeCalculator(), clock=lambda: FIXED_TIME
    ).analyze(FIXTURES / "runtime_complete.json")
    explicit = ResumeAnalyzer(
        tmp_path / "explicit", calculator=FakeCalculator(), clock=lambda: FIXED_TIME
    ).analyze(FIXTURES / "runtime_complete.json", include_contact=True)

    assert "candidate@example.invalid" not in Path(default["suggestions"]).read_text()
    assert "candidate@example.invalid" in Path(explicit["suggestions"]).read_text()


def test_schema_error_does_not_echo_sensitive_value(tmp_path):
    bad = tmp_path / "bad.json"
    bad.write_text(
        json.dumps({"basic_info": {"name": "DO_NOT_LOG_ME"}}),
        encoding="utf-8",
    )
    with pytest.raises(InputValidationError) as captured:
        load_resume(bad)
    assert "DO_NOT_LOG_ME" not in str(captured.value)


def test_input_file_errors_and_mapping_boundaries(tmp_path):
    with pytest.raises(InputValidationError, match="does not exist"):
        load_resume(tmp_path / "missing.json")

    invalid = tmp_path / "invalid.json"
    invalid.write_text("not-json", encoding="utf-8")
    with pytest.raises(InputValidationError, match="JSONDecodeError"):
        load_resume(invalid)

    oversized = tmp_path / "oversized.json"
    oversized.write_bytes(b"x" * (5 * 1024 * 1024 + 1))
    with pytest.raises(InputValidationError, match="5 MiB"):
        load_resume(oversized)

    link = tmp_path / "linked.json"
    link.symlink_to(FIXTURES / "runtime_minimal.json")
    with pytest.raises(InputValidationError, match="symlink"):
        load_resume(link)

    model = load_resume(FIXTURES / "runtime_minimal.json")
    assert _model_mapping(model)["basic_info"]["name"] == "最小样例"
    with pytest.raises(TypeError, match="expected score"):
        _model_mapping(1)
    assert _utc_now().tzinfo is not None


def test_analyzer_translates_renderer_and_unexpected_errors(tmp_path):
    class BadRenderer:
        def render(self, *args, **kwargs):
            raise RenderingError("missing template value")

    with pytest.raises(AnalyzerError, match="missing template value"):
        ResumeAnalyzer(
            tmp_path / "render", calculator=FakeCalculator(), renderer=BadRenderer()
        ).analyze(FIXTURES / "runtime_minimal.json")

    class BadCalculator:
        def __init__(self, error):
            self.error = error

        def calculate(self, resume):
            raise self.error

    expected = AnalyzerError("expected")
    with pytest.raises(AnalyzerError, match="expected"):
        ResumeAnalyzer(tmp_path / "expected", calculator=BadCalculator(expected)).analyze(
            FIXTURES / "runtime_minimal.json"
        )
    with pytest.raises(AnalyzerError, match="RuntimeError"):
        ResumeAnalyzer(
            tmp_path / "unexpected", calculator=BadCalculator(RuntimeError("secret"))
        ).analyze(FIXTURES / "runtime_minimal.json")


def test_low_score_produces_weakness_and_output_conflict_is_preserved(tmp_path):
    class LowCalculator(FakeCalculator):
        def calculate(self, resume):
            score = super().calculate(resume)
            score["dimension_scores"]["monitoring"]["score"] = 1.0
            return score

    analyzer = ResumeAnalyzer(tmp_path, calculator=LowCalculator(), clock=lambda: FIXED_TIME)
    outputs = analyzer.analyze(FIXTURES / "runtime_minimal.json")
    analysis = json.loads(Path(outputs["analysis"]).read_text())
    assert analysis["weaknesses"][0]["dimension"] == "monitoring"
    with pytest.raises(OutputConflictError):
        analyzer.analyze(FIXTURES / "runtime_minimal.json")
