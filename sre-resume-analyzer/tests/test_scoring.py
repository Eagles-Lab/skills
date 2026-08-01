import json
from copy import deepcopy

import pytest
import yaml
from pydantic import ValidationError

from sre_resume_analyzer.matching import EvidenceMatcher
from sre_resume_analyzer.models import Resume
from sre_resume_analyzer.scoring import (
    DEFAULT_SCORING_CONFIG,
    SCORING_CONFIG_VERSION,
    ScoreCalculator,
    ScoringConfig,
)


def make_resume(projects=None, internships=None, skills=None):
    return Resume.model_validate(
        {
            "resume_id": "scoring-fixture",
            "basic_info": {
                "name": "Candidate",
                "school": "Example University",
                "major": "Computer Science",
                "degree": "Bachelor",
                "graduation_year": 2026,
            },
            "internships": internships or [],
            "projects": projects or [],
            "skills": skills
            or {
                "programming_languages": [],
                "monitoring_tools": [],
                "container_tech": [],
                "cloud_platforms": [],
                "cicd_tools": [],
            },
        }
    )


def project(name, description, tech_stack=None, achievements=None):
    return {
        "name": name,
        "role": "engineer",
        "duration": "2025-01 to 2025-06",
        "description": description,
        "tech_stack": tech_stack or [],
        "achievements": achievements or [],
    }


def empty_skills():
    return {
        "programming_languages": [],
        "monitoring_tools": [],
        "container_tech": [],
        "cloud_platforms": [],
        "cicd_tools": [],
    }


def test_minimal_resume_has_true_one_point_floor():
    result = ScoreCalculator().calculate(make_resume())

    assert result.base_score == 1.0
    assert result.total_score == 1.0
    assert result.grade.grade == "F"
    assert result.scoring_config_version == SCORING_CONFIG_VERSION
    assert result.dimension_scores["resume_quality"].breakdown["completeness"] == 0.0


def test_single_high_strength_source_is_capped_at_six():
    resume = make_resume(
        projects=[
            project(
                "monitoring",
                "主导设计并部署生产环境 Prometheus 监控平台",
                ["Prometheus"],
            )
        ]
    )

    result = ScoreCalculator().calculate(resume)

    assert result.dimension_scores["monitoring"].score == 6.0


def test_two_independent_strong_sources_gain_one_point():
    resume = make_resume(
        projects=[
            project("one", "负责设计并部署生产环境 Prometheus 监控平台", ["Prometheus"]),
            project("two", "实现 Prometheus exporter 并配置 Grafana 面板", ["Grafana"]),
        ]
    )

    result = ScoreCalculator().calculate(resume)

    assert result.dimension_scores["monitoring"].score == 10.0


def test_keyword_spam_and_repetition_cannot_reach_b_grade():
    skills = {
        "programming_languages": ["Python", "Go", "Bash"],
        "monitoring_tools": ["Prometheus", "Grafana", "Zabbix", "Prometheus"],
        "container_tech": ["Docker", "Kubernetes", "Helm"],
        "cloud_platforms": ["AWS", "GCP"],
        "cicd_tools": ["Jenkins", "GitHub Actions", "Terraform"],
    }

    result = ScoreCalculator().calculate(make_resume(skills=skills))

    assert result.grade.grade == "F"
    assert result.total_score < 4.0
    assert result.dimension_scores["monitoring"].score == 2.0


def test_negated_examples_cannot_exceed_four_in_related_dimensions():
    resume = make_resume(
        projects=[
            project(
                "negated",
                "No experience with Prometheus or Grafana. "
                "未使用 Kubernetes, 也没有 Terraform 经验。",
            )
        ]
    )

    result = ScoreCalculator().calculate(resume)

    assert result.dimension_scores["monitoring"].score <= 4.0
    assert result.dimension_scores["containerization"].score <= 4.0
    assert result.dimension_scores["automation"].score <= 4.0


def test_semantically_equivalent_chinese_and_english_examples_are_within_half_point():
    chinese = make_resume(
        projects=[project("monitoring", "实现并部署生产环境 Prometheus 监控平台")]
    )
    english = make_resume(
        projects=[
            project("monitoring", "Implemented and deployed a production Prometheus platform")
        ]
    )

    chinese_score = ScoreCalculator().calculate(chinese)
    english_score = ScoreCalculator().calculate(english)

    assert abs(chinese_score.total_score - english_score.total_score) <= 0.5
    assert (
        chinese_score.dimension_scores["monitoring"].score
        == english_score.dimension_scores["monitoring"].score
    )


def test_resume_quality_is_independently_scored():
    minimal = ScoreCalculator().calculate(make_resume())
    rich = ScoreCalculator().calculate(
        make_resume(
            projects=[
                project(
                    "platform",
                    "负责设计并实现可观测平台\uff0c统一服务指标采集和故障排查流程",
                    ["Prometheus", "Grafana"],
                    ["将告警确认时间降低30%", "覆盖20个服务并完成上线验证"],
                )
            ],
            skills={**empty_skills(), "monitoring_tools": ["Prometheus", "Grafana"]},
        )
    )

    assert minimal.dimension_scores["resume_quality"].score == 1.0
    assert rich.dimension_scores["resume_quality"].score > 1.0
    assert rich.dimension_scores["resume_quality"].breakdown["quantified_results"] == 2.0


def test_ai_mentions_do_not_score_and_quantification_does_not_cross_projects():
    mention = make_resume(skills={**empty_skills(), "programming_languages": ["Cursor"]})
    cross_project = make_resume(
        projects=[
            project("ai", "构建 RAG 检索服务", ["RAG"]),
            project("cache", "优化缓存策略并将延迟降低30%", ["Redis"]),
        ]
    )

    mention_result = ScoreCalculator().calculate(mention)
    cross_result = ScoreCalculator().calculate(cross_project)

    assert mention_result.ai_bonus.score == 0.0
    assert cross_result.ai_bonus.score == 0.5
    assert cross_result.ai_bonus.applications["llm"][0].quantified is False


def test_three_ai_categories_with_local_outcome_receive_max_bonus():
    resume = make_resume(
        projects=[
            project(
                "aiops",
                "构建 RAG 服务、AI Agent 工作流和 anomaly detection\uff0c将诊断延迟降低30%",
                ["RAG", "AI Agent", "anomaly detection"],
            )
        ]
    )

    result = ScoreCalculator().calculate(resume)

    assert result.ai_bonus.score == 1.5
    assert result.ai_bonus.category_count == 3
    assert set(result.ai_bonus.applications) == {"ai_agents", "llm", "ml_ops"}


def test_ai_quantified_outcome_may_be_a_separate_achievement_in_the_same_project():
    resume = make_resume(
        projects=[
            project(
                "aiops",
                "构建 RAG 服务、AI Agent 工作流和 anomaly detection",
                ["RAG", "AI Agent", "anomaly detection"],
                ["优化诊断流程并将平均定位时间降低30%"],
            )
        ]
    )

    result = ScoreCalculator().calculate(resume)

    assert result.ai_bonus.score == 1.5
    assert all(
        item.quantified
        for category_items in result.ai_bonus.applications.values()
        for item in category_items
    )


def test_score_is_deterministic_and_only_final_values_are_rounded():
    resume = make_resume(projects=[project("one", "使用 Prometheus 配置监控", ["Prometheus"])])
    calculator = ScoreCalculator()

    first = calculator.calculate(resume)
    second = calculator.calculate(resume)

    assert first == second
    assert first.base_score == round(
        sum(value.weighted_score for value in first.dimension_scores.values()), 1
    )


def test_custom_config_mapping_is_validated_and_versioned():
    config = deepcopy(DEFAULT_SCORING_CONFIG)
    config["version"] = "fixture-1"

    result = ScoreCalculator(config).calculate(make_resume())

    assert result.scoring_config_version == "fixture-1"


def test_config_accepts_existing_model_json_and_yaml_paths(tmp_path):
    config_model = ScoringConfig.from_source()
    json_path = tmp_path / "scoring.json"
    yaml_path = tmp_path / "scoring.yaml"
    json_path.write_text(json.dumps(DEFAULT_SCORING_CONFIG), encoding="utf-8")
    yaml_path.write_text(yaml.safe_dump(DEFAULT_SCORING_CONFIG), encoding="utf-8")

    assert ScoringConfig.from_source(config_model) is config_model
    assert ScoringConfig.from_source(json_path).version == SCORING_CONFIG_VERSION
    assert ScoringConfig.from_source(str(yaml_path)).version == SCORING_CONFIG_VERSION


def test_config_path_rejects_non_object_root(tmp_path):
    path = tmp_path / "scoring.yaml"
    path.write_text("- not\n- an\n- object\n", encoding="utf-8")

    with pytest.raises(ValueError, match="root must be an object"):
        ScoringConfig.from_source(path)


def test_config_path_read_errors_are_sanitized(tmp_path):
    with pytest.raises(ValueError, match="FileNotFoundError"):
        ScoringConfig.from_source(tmp_path / "missing.yaml")

    invalid = tmp_path / "invalid.json"
    invalid.write_text("not-json", encoding="utf-8")
    with pytest.raises(ValueError, match="JSONDecodeError"):
        ScoringConfig.from_source(invalid)


@pytest.mark.parametrize(
    "mutator",
    [
        lambda config: config["dimension_weights"].pop("monitoring"),
        lambda config: config["dimension_weights"].update({"monitoring": 0.3}),
        lambda config: config["dimension_weights"].update({"monitoring": 0.0, "alerting": 0.35}),
        lambda config: config["dimension_weights"].update({"monitoring": 0.15, "alerting": 0.20}),
        lambda config: config["evidence_scores"].pop("mention"),
        lambda config: config["grade_thresholds"].pop("A+"),
        lambda config: config["grade_thresholds"]["A"].update({"range": [8.4, 9.4]}),
        lambda config: config["matching"]["dimension_keywords"].pop("monitoring"),
    ],
)
def test_config_rejects_incomplete_or_invalid_scoring_contract(mutator):
    config = deepcopy(DEFAULT_SCORING_CONFIG)
    mutator(config)

    with pytest.raises(ValidationError):
        ScoringConfig.from_source(config)


def test_config_rejects_reversed_grade_range():
    config = deepcopy(DEFAULT_SCORING_CONFIG)
    config["grade_thresholds"]["A+"]["range"] = [11.5, 9.5]

    with pytest.raises(ValidationError, match="minimum must not exceed"):
        ScoringConfig.from_source(config)


def test_calculator_accepts_injected_matcher_and_resume_model_alias():
    resume = make_resume()
    calculator = ScoreCalculator(matcher=EvidenceMatcher())

    assert calculator.calculate_scores(resume) == calculator.calculate(resume)


def test_custom_evidence_scores_cap_high_score_without_required_evidence_level():
    config = deepcopy(DEFAULT_SCORING_CONFIG)
    config["evidence_scores"]["implementation"] = 8.0
    resume = make_resume(
        projects=[
            project("one", "实现并部署 Prometheus 监控", ["Prometheus"]),
            project("two", "构建并配置 Grafana 面板", ["Grafana"]),
        ]
    )

    result = ScoreCalculator(config).calculate(resume)

    assert result.dimension_scores["monitoring"].score == 8.0


def test_resume_quality_intermediate_branches_are_explicit():
    resume = make_resume(projects=[project("short", "使用内部工具")])

    quality = ScoreCalculator().calculate(resume).dimension_scores["resume_quality"]

    assert quality.breakdown == {
        "completeness": 1.0,
        "action_result": 1.0,
        "quantified_results": 0.0,
        "clarity": 1.0,
        "timeline_technical_consistency": 1.0,
    }


def test_two_ai_application_categories_receive_one_point():
    resume = make_resume(projects=[project("ai", "构建 RAG 服务并实现 AI Agent 工作流")])

    bonus = ScoreCalculator().calculate(resume).ai_bonus

    assert bonus.score == 1.0
    assert bonus.category_count == 2


def test_ai_project_mention_without_action_is_not_an_application():
    resume = make_resume(projects=[project("ai", "RAG and AI Agent")])

    assert ScoreCalculator().calculate(resume).ai_bonus.score == 0.0


@pytest.mark.parametrize(
    "description",
    [
        "构建 RAG 服务;使用 RAG 并将延迟降低30%",
        "使用 RAG 并将延迟降低30%;构建 RAG 服务",
    ],
)
def test_ai_evidence_keeps_strongest_record_deterministically(description):
    resume = make_resume(projects=[project("ai", description)])

    application = ScoreCalculator().calculate(resume).ai_bonus.applications["llm"][0]

    assert application.quantified is True


def test_grade_falls_back_closed_for_non_comparable_value():
    grade = ScoreCalculator().grade_for_score(float("nan"))

    assert grade.grade == "F"


def test_v2_mapping_is_rejected_by_calculate_scores():
    value = make_resume().model_dump(mode="python")
    value["skills"] = ["Prometheus"]

    with pytest.raises(ValidationError):
        ScoreCalculator().calculate_scores(value)


@pytest.mark.parametrize(
    ("score", "grade"),
    [(9.5, "A+"), (9.4, "A"), (8.5, "A"), (7.0, "B"), (5.5, "C"), (4.0, "D"), (3.9, "F")],
)
def test_grade_thresholds_are_stable(score, grade):
    assert ScoreCalculator().grade_for_score(score).grade == grade
