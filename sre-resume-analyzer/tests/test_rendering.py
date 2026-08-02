from __future__ import annotations

# ruff: noqa: RUF001
from pathlib import Path

import pytest

from sre_resume_analyzer.models import Resume
from sre_resume_analyzer.rendering import RenderingError, ReportRenderer, stable_render_fingerprint
from sre_resume_analyzer.scoring import ScoreCalculator


def render(resume: Resume, *, seed: str = "seed", include_contact: bool = False):
    score = ScoreCalculator().calculate(resume).model_dump(mode="json")
    analysis = {
        "strengths": [],
        "weaknesses": [],
        "security_warnings": [],
        "data_quality_warnings": [
            {
                "code": "missing_school",
                "path": "basic_info.school",
                "message": "未提供或未可靠识别，请后续补充。",
            }
        ],
    }
    return ReportRenderer().render(
        resume,
        score,
        analysis,
        resume_id="internal",
        output_name="候选人-abcdef12",
        generated_at="2026-08-02T00:00:00Z",
        analyzer_version="3.0.0-rc.2",
        input_sha256="a" * 64,
        seed=seed,
        include_contact=include_contact,
    )


def test_report_has_new_dimensions_quality_explanations_and_no_legacy_contract():
    reports = render(Resume.model_validate({}))
    text = reports.suggestions
    for label in (
        "计算机系统与网络基础",
        "编程与自动化工程",
        "故障分析与问题解决",
        "云基础设施与分布式系统",
        "可靠性工程实践",
        "AI 辅助工程与 AIOps 实践",
    ):
        assert label in text
    assert "简历整体质量诊断（不计入技术总分）" in text
    assert "尚未体现" in text
    assert "暂无满足规则的正向证据" not in text
    assert "AI 应用加分" not in text
    assert "基础分" not in text
    assert "/11.5" not in text
    assert "简历 ID" not in text


def test_missing_facts_use_explicit_reminder_not_fabricated_values():
    text = render(Resume.model_validate({})).suggestions
    assert "未提供或未可靠识别，请后续补充。" in text
    assert "示例大学" not in text


def test_question_generation_is_seeded_stable_and_exactly_ten():
    resume = Resume.model_validate(
        {
            "basic_info": {"name": "候选人"},
            "projects": [{"name": "平台", "description": "实现 Kubernetes 平台"}],
        }
    )
    first = render(resume, seed="same")
    second = render(resume, seed="same")
    different = render(resume, seed="different")
    assert first.interview_questions == second.interview_questions
    assert first.interview_questions != different.interview_questions
    assert sum(line.startswith("### ") for line in first.interview_questions.splitlines()) == 10
    assert "AI 辅助工程与 AIOps 实践" in first.interview_questions
    assert stable_render_fingerprint(first) == stable_render_fingerprint(second)


def test_contact_is_opt_in_and_html_is_escaped():
    resume = Resume.model_validate(
        {
            "basic_info": {
                "name": "<b>候选人</b>",
                "contact": {"email": "x@example.com", "phone": "13800000000"},
            }
        }
    )
    hidden = render(resume)
    shown = render(resume, include_contact=True)
    assert "x@example.com" not in hidden.suggestions
    assert "x@example.com" in shown.suggestions
    assert "&lt;b&gt;候选人&lt;/b&gt;" in shown.suggestions


def test_strict_undefined_template_failure_is_wrapped(tmp_path: Path):
    (tmp_path / "suggestions_template.md").write_text("{{ missing }}")
    (tmp_path / "interview_questions_template.md").write_text("ok")
    renderer = ReportRenderer(tmp_path)
    resume = Resume.model_validate({})
    score = ScoreCalculator().calculate(resume)
    with pytest.raises(RenderingError):
        renderer.render(
            resume,
            score,
            {
                "strengths": [],
                "weaknesses": [],
                "security_warnings": [],
                "data_quality_warnings": [],
            },
            resume_id="internal",
            output_name="未知姓名-abcdef12",
            generated_at="2026-08-02T00:00:00Z",
            analyzer_version="3.0.0-rc.2",
            input_sha256="a" * 64,
        )
