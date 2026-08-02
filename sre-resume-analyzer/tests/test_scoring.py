from __future__ import annotations

# ruff: noqa: RUF001
import copy
import json

import pytest
from pydantic import ValidationError

from sre_resume_analyzer.models import Resume
from sre_resume_analyzer.scoring import (
    DEFAULT_SCORING_CONFIG,
    DIMENSION_WEIGHTS,
    SCORING_CONFIG_VERSION,
    ScoreCalculator,
    ScoringConfig,
)

DIMENSION_TERM = {
    "systems_network_foundation": "Linux",
    "programming_automation": "Python",
    "troubleshooting": "故障排查",
    "cloud_distributed_infrastructure": "Kubernetes",
    "reliability_engineering": "Prometheus",
}

DIMENSION_COVERAGE_TERMS = {
    "systems_network_foundation": ("Linux", "TCP", "MySQL"),
    "programming_automation": ("Python", "Bash", "pytest"),
    "troubleshooting": ("日志分析", "tcpdump", "根因分析"),
    "cloud_distributed_infrastructure": ("Kubernetes", "AWS", "Kafka"),
    "reliability_engineering": ("Prometheus", "告警规则", "SLO"),
}


def project(description: str) -> dict[str, object]:
    return {"description": description}


def score(value: dict[str, object]):
    return ScoreCalculator().calculate(Resume.model_validate(value))


def test_weights_profile_and_empty_floor_contract():
    result = score({})
    assert sum(DIMENSION_WEIGHTS.values()) == pytest.approx(1.0)
    assert result.scoring_profile == "cn-campus-sre"
    assert result.scoring_config_version == SCORING_CONFIG_VERSION
    assert result.total_score == 1.0
    assert result.grade.grade == "F"
    assert result.resume_quality.weight == 0.0
    assert set(result.dimension_scores) == set(DIMENSION_WEIGHTS)


@pytest.mark.parametrize("dimension,term", DIMENSION_TERM.items())
@pytest.mark.parametrize(
    "descriptions,expected",
    [
        ([], 1.0),
        (["SKILL_ONLY"], 2.0),
        (["使用 {term} 完成课程实验"], 4.0),
        (["实现并部署 {term} 工具"], 6.0),
        (["负责设计并部署 {term}，完成故障排查和测试验证"], 8.0),
    ],
)
def test_general_dimension_evidence_boundaries(dimension, term, descriptions, expected):
    if descriptions == ["SKILL_ONLY"]:
        value = {"skills": {"programming_languages": [term]}}
    else:
        value = {
            "projects": [project(description.format(term=term)) for description in descriptions]
        }
    assert score(value).dimension_scores[dimension].score == expected


@pytest.mark.parametrize("dimension,terms", DIMENSION_COVERAGE_TERMS.items())
def test_general_high_scores_require_multiple_applied_evidence_groups(dimension, terms):
    first, second, third = terms
    narrow = score(
        {"projects": [project(f"在生产环境部署 {first} 并服务真实用户")]}
    ).dimension_scores[dimension]
    broad_result = score(
        {"projects": [project(f"在生产环境部署 {first} 和 {second} 并服务真实用户")]}
    ).dimension_scores[dimension]
    multi_source = score(
        {
            "projects": [
                project(f"负责设计并部署 {first} 和 {second}，完成故障排查和测试验证"),
                project(f"实现并部署 {third} 独立工具"),
            ]
        }
    ).dimension_scores[dimension]

    assert narrow.depth_score == 9.0
    assert narrow.coverage_cap == 8.0
    assert narrow.score == 8.0
    assert len(narrow.applied_evidence_groups) == 1
    assert broad_result.depth_score == broad_result.coverage_cap == broad_result.score == 9.0
    assert len(broad_result.applied_evidence_groups) == 2
    assert multi_source.depth_score == multi_source.coverage_cap == multi_source.score == 10.0
    assert len(multi_source.applied_evidence_groups) >= 3


@pytest.mark.parametrize(
    "value,expected",
    [
        ({"skills": {"ai_tools": ["Cursor", "ChatGPT"]}}, 2.0),
        ({"projects": [project("使用 ChatGPT 编码并由人工验证结果")]}, 4.0),
        ({"projects": [project("实现并部署可运行的 RAG 自动诊断工作流")]}, 6.0),
        (
            {"projects": [project("实现 RAG 自动诊断工作流，建立评测集并加入权限与人工确认")]},
            8.0,
        ),
        ({"projects": [project("在生产环境部署 RAG Agent 自动诊断并服务真实用户")]}, 9.0),
        (
            {
                "projects": [
                    project("实现 RAG 自动诊断，建立评测集并加入权限控制"),
                    project("独立实现并部署 Agent 告警摘要工作流"),
                ]
            },
            10.0,
        ),
    ],
)
def test_ai_dimension_boundaries(value, expected):
    assert score(value).dimension_scores["ai_engineering_aiops"].score == expected


def test_ai_does_not_borrow_quantification_or_guardrails_across_projects():
    result = score(
        {
            "projects": [
                project("实现 RAG 自动诊断工作流"),
                project("普通 Python 服务建立评测和权限控制，效率提升 50%"),
            ]
        }
    )
    assert result.dimension_scores["ai_engineering_aiops"].score == 6.0


def test_keyword_stuffing_and_negation_do_not_reach_b():
    result = score(
        {
            "skills": {
                "programming_languages": ["Linux", "Python", "故障排查"],
                "container_tech": ["Kubernetes"],
                "monitoring_tools": ["Prometheus"],
                "ai_tools": ["Cursor"],
            },
            "projects": [{"description": "未使用 Docker，不熟悉 Prometheus"}],
        }
    )
    assert result.total_score == 2.0
    assert result.grade.grade == "F"


def test_total_rounds_once_and_stays_in_ten_point_range():
    result = score({"projects": [project("实现并部署 Python Kubernetes Prometheus 工具")]})
    raw = sum(item.weighted_score for item in result.dimension_scores.values())
    assert result.total_score == round(raw, 1)
    assert 1.0 <= result.total_score <= 10.0


def test_resume_quality_is_independent_and_has_explanations():
    low = score({}).resume_quality
    high = score(
        {
            "basic_info": {"name": "测试", "school": "大学", "major": "计算机", "degree": "本科"},
            "projects": [
                {
                    "name": "平台",
                    "duration": "2025",
                    "description": "负责设计并实现 Python 平台，测试后性能提升 50%",
                    "tech_stack": ["Python"],
                    "achievements": ["覆盖 10 个服务，故障减少 30%"],
                }
            ],
            "skills": {"programming_languages": ["Python"]},
        }
    ).resume_quality
    assert low.score == 1.0
    assert high.score > low.score
    assert set(high.breakdown) == set(high.findings)
    assert all("暂无满足规则" not in text for text in high.findings.values())


def test_grade_boundaries():
    calculator = ScoreCalculator()
    for value, grade in [
        (9.5, "A+"),
        (9.4, "A"),
        (8.5, "A"),
        (7.0, "B"),
        (5.5, "C"),
        (4.0, "D"),
        (3.9, "F"),
    ]:
        assert calculator.grade_for_score(value).grade == grade


@pytest.mark.parametrize(
    "mutate",
    [
        lambda value: value["dimension_weights"].pop("systems_network_foundation"),
        lambda value: value["dimension_weights"].update({"systems_network_foundation": 0.3}),
        lambda value: value["matching"]["dimension_keywords"].pop("troubleshooting"),
        lambda value: value["evidence_groups"].pop("troubleshooting"),
        lambda value: value["grade_thresholds"]["A+"]["range"].__setitem__(1, 11.5),
    ],
)
def test_scoring_contract_is_not_silently_customizable(mutate):
    value = copy.deepcopy(DEFAULT_SCORING_CONFIG)
    mutate(value)
    with pytest.raises(ValidationError):
        ScoringConfig.model_validate(value)


def test_scoring_config_loaders_and_validation_edges(tmp_path):
    value = copy.deepcopy(DEFAULT_SCORING_CONFIG)
    instance = ScoringConfig.model_validate(value)
    assert ScoringConfig.from_source(instance) is instance
    assert ScoringConfig.from_source(value) == instance
    json_path = tmp_path / "config.json"
    json_path.write_text(json.dumps(value))
    yaml_path = tmp_path / "config.yaml"
    yaml_path.write_text("version: only-version")
    assert ScoringConfig.from_source(json_path) == instance
    with pytest.raises(ValidationError):
        ScoringConfig.from_source(yaml_path)
    bad_json = tmp_path / "bad.json"
    bad_json.write_text("{")
    with pytest.raises(ValueError, match="could not be read"):
        ScoringConfig.from_source(bad_json)
    list_json = tmp_path / "list.json"
    list_json.write_text("[]")
    with pytest.raises(ValueError, match="root must be an object"):
        ScoringConfig.from_source(list_json)
    with pytest.raises(ValueError, match="could not be read"):
        ScoringConfig.from_source(tmp_path / "missing.json")


def test_all_config_contract_error_branches():
    mutations = []
    value = copy.deepcopy(DEFAULT_SCORING_CONFIG)
    value["dimension_weights"]["systems_network_foundation"] -= 0.01
    mutations.append(value)
    value = copy.deepcopy(DEFAULT_SCORING_CONFIG)
    value["dimension_weights"]["systems_network_foundation"] += 0.01
    value["dimension_weights"]["programming_automation"] -= 0.01
    mutations.append(value)
    value = copy.deepcopy(DEFAULT_SCORING_CONFIG)
    value["evidence_scores"].pop("mention")
    mutations.append(value)
    value = copy.deepcopy(DEFAULT_SCORING_CONFIG)
    value["grade_thresholds"].pop("A")
    mutations.append(value)
    value = copy.deepcopy(DEFAULT_SCORING_CONFIG)
    value["grade_thresholds"]["B"]["range"] = [6.9, 8.4]
    mutations.append(value)
    value = copy.deepcopy(DEFAULT_SCORING_CONFIG)
    value["grade_thresholds"]["A"]["range"] = [9.4, 8.5]
    mutations.append(value)
    value = copy.deepcopy(DEFAULT_SCORING_CONFIG)
    value["evidence_groups"]["systems_network_foundation"]["operating_systems_resources"] = []
    mutations.append(value)
    value = copy.deepcopy(DEFAULT_SCORING_CONFIG)
    value["evidence_groups"]["systems_network_foundation"]["networking_protocols"].append("linux")
    mutations.append(value)
    value = copy.deepcopy(DEFAULT_SCORING_CONFIG)
    value["evidence_groups"]["systems_network_foundation"]["operating_systems_resources"].remove(
        "linux"
    )
    mutations.append(value)
    for invalid in mutations:
        with pytest.raises(ValidationError):
            ScoringConfig.model_validate(invalid)


def test_calculate_scores_alias_and_uncovered_quality_branches():
    calculator = ScoreCalculator()
    mapping_result = calculator.calculate_scores(
        {
            "basic_info": {"name": "候选人"},
            "projects": [
                {
                    "description": "只是一段普通描述",
                    "duration": "2026",
                    "achievements": ["使用 Python 完成实验"],
                }
            ],
        }
    )
    assert calculator.calculate_scores(Resume.model_validate({})).total_score == 1.0
    assert mapping_result.resume_quality.breakdown["completeness"] == 1.0
    assert mapping_result.resume_quality.breakdown["action_result"] == 1.0
    assert mapping_result.resume_quality.breakdown["quantified_results"] == 0.0
    assert mapping_result.resume_quality.breakdown["timeline_technical_consistency"] == 2.0
    assert calculator.grade_for_score(0.0).grade == "F"


def test_ai_plain_unverified_use_is_capped_at_mention():
    result = score({"projects": [project("使用 ChatGPT 编写代码")]})
    assert result.dimension_scores["ai_engineering_aiops"].score == 2.0


def test_complete_project_signals_can_span_description_and_achievements():
    result = score(
        {
            "projects": [
                {
                    "description": "负责设计并部署 Kubernetes 平台。",
                    "achievements": ["完成故障排查。", "使用测试验证恢复结果。"],
                }
            ]
        }
    )
    assert result.dimension_scores["cloud_distributed_infrastructure"].score == 8.0


def test_chinese_forward_case_scores_same_source_ai_and_troubleshooting_results():
    result = score(
        {
            "internships": [
                {
                    "description": "使用 Prometheus 观察服务延迟。",
                    "achievements": [
                        "比较指标、日志和 tcpdump 后定位到连接池上限，"
                        "复测后 p95 从 420 ms 降至 170 ms。"
                    ],
                }
            ],
            "projects": [
                {
                    "name": "告警归并与诊断建议 Agent",
                    "description": (
                        "使用 LangGraph 实现可运行的告警分析工作流。所有建议必须人工确认，"
                        "工具仅具只读权限，检索失败时回退到固定清单。"
                    ),
                    "achievements": ["构造 60 条故障样本，与规则基线比较，正确比例为 85%。"],
                }
            ],
        }
    )

    assert result.dimension_scores["troubleshooting"].score == 9.0
    assert result.dimension_scores["ai_engineering_aiops"].score == 9.0
