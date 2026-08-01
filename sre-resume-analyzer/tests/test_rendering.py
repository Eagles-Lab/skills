import json
from pathlib import Path

import pytest

from sre_resume_analyzer.models import Resume
from sre_resume_analyzer.rendering import (
    RenderedReports,
    RenderingError,
    ReportRenderer,
    _evidence_text,
    _grade_for_dimension,
    _to_mapping,
    stable_render_fingerprint,
)

FIXTURES = Path(__file__).parent / "fixtures"


def _inputs():
    resume = Resume.model_validate(
        json.loads((FIXTURES / "runtime_complete.json").read_text(encoding="utf-8"))
    )
    score = json.loads((FIXTURES / "runtime_score.json").read_text(encoding="utf-8"))
    analysis = {
        "strengths": [{"label": "监控相关经验", "summary": "证据充分"}],
        "weaknesses": [{"label": "告警设计能力", "summary": "补充生产证据"}],
    }
    return resume, score, analysis


def test_render_is_deterministic_and_generates_ten_questions():
    renderer = ReportRenderer()
    resume, score, analysis = _inputs()
    kwargs = {
        "resume_id": "candidate_complete",
        "generated_at": "2026-08-02T00:00:00Z",
        "analyzer_version": "3.0.0-rc.1",
        "input_sha256": "a" * 64,
    }
    first = renderer.render(resume, score, analysis, **kwargs)
    second = renderer.render(resume, score, analysis, **kwargs)

    assert first == second
    assert first.interview_questions.count("### ") == 10
    assert "不能单独用于招聘决策" in first.suggestions
    assert "Top" not in first.suggestions


def test_contact_is_opt_in():
    renderer = ReportRenderer()
    resume, score, analysis = _inputs()
    base = {
        "resume_id": "candidate_complete",
        "generated_at": "2026-08-02T00:00:00Z",
        "analyzer_version": "3.0.0-rc.1",
        "input_sha256": "a" * 64,
    }
    private = renderer.render(resume, score, analysis, **base)
    explicit = renderer.render(resume, score, analysis, include_contact=True, **base)

    assert "candidate@example.invalid" not in private.suggestions
    assert "candidate@example.invalid" not in private.interview_questions
    assert "candidate@example.invalid" in explicit.suggestions


def test_strict_undefined_fails_closed(tmp_path):
    (tmp_path / "suggestions_template.md").write_text("{{ missing }}", encoding="utf-8")
    (tmp_path / "interview_questions_template.md").write_text("ok", encoding="utf-8")
    renderer = ReportRenderer(tmp_path)
    resume, score, analysis = _inputs()

    with pytest.raises(RenderingError, match="missing"):
        renderer.render(
            resume,
            score,
            analysis,
            resume_id="candidate_complete",
            generated_at="2026-08-02T00:00:00Z",
            analyzer_version="3.0.0-rc.1",
            input_sha256="a" * 64,
        )


def test_render_helpers_cover_all_grade_and_evidence_fallbacks():
    assert [_grade_for_dimension(value) for value in (9, 7, 5, 3, 1)] == [
        "A",
        "B",
        "C",
        "D",
        "F",
    ]
    assert _evidence_text({}) == "已识别到结构化证据"
    with pytest.raises(TypeError, match="expected a model"):
        _to_mapping(None)

    reports = RenderedReports("suggestions", "questions")
    assert stable_render_fingerprint(reports) == stable_render_fingerprint(reports)
    assert len(stable_render_fingerprint(reports)) == 64


def test_suggestion_variants_cover_sequence_invalid_ai_and_incomplete_project():
    renderer = ReportRenderer()
    resume, score, analysis = _inputs()
    resume_data = resume.model_dump(mode="json")
    resume_data["projects"] = [
        {
            "name": "Incomplete",
            "role": "",
            "duration": "now",
            "description": "work",
            "tech_stack": [],
            "achievements": [],
        }
    ]
    score["ai_bonus"]["applications"] = ["llm", "aiops"]
    context = renderer._suggestions_context(
        resume_data,
        score,
        analysis,
        resume_id="id",
        generated_at="now",
        analyzer_version="v3",
        include_contact=False,
    )
    assert context["ai_applications"] == ["aiops", "llm"]
    assert len(context["project_suggestions"]) == 2

    score["ai_bonus"]["applications"] = "invalid"
    context = renderer._suggestions_context(
        resume_data,
        score,
        analysis,
        resume_id="id",
        generated_at="now",
        analyzer_version="v3",
        include_contact=False,
    )
    assert context["ai_applications"] == []


def test_duplicate_question_candidates_are_deduplicated(monkeypatch):
    renderer = ReportRenderer()
    resume, score, _ = _inputs()
    monkeypatch.setattr(
        "sre_resume_analyzer.rendering.GENERAL_QUESTIONS", ["duplicate", "duplicate"]
    )
    monkeypatch.setattr(
        "sre_resume_analyzer.rendering.QUESTION_BANK",
        {name: ["duplicate"] for name in score["dimension_scores"]},
    )
    questions = renderer._build_questions(resume.model_dump(mode="json"), score, seed="stable")
    assert len({question["question"] for question in questions}) == len(questions)
