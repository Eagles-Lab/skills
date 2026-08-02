"""Deterministic scoring for the Chinese campus SRE profile."""
# ruff: noqa: RUF001

from __future__ import annotations

import copy
import json
import re
from pathlib import Path
from typing import Any, Dict, List, Mapping, Optional, Sequence, Tuple, Union

import yaml
from pydantic import BaseModel, ConfigDict, Field, model_validator

from .matching import (
    DEFAULT_MATCHING_CONFIG,
    EvidenceMatcher,
    classify_evidence,
    is_quantified,
    iter_resume_records,
    iter_sentences,
    normalize_text,
)
from .models import (
    DimensionName,
    DimensionScore,
    Evidence,
    EvidenceLevel,
    GradeInfo,
    Resume,
    ResumeQualityDiagnostic,
    ScoreResult,
)
from .security import is_instruction_like

SCORING_CONFIG_VERSION = "cn-campus-sre-1.1.0"

DIMENSION_WEIGHTS: Dict[str, float] = {
    "systems_network_foundation": 0.22,
    "programming_automation": 0.18,
    "troubleshooting": 0.18,
    "cloud_distributed_infrastructure": 0.14,
    "reliability_engineering": 0.18,
    "ai_engineering_aiops": 0.10,
}

# Concepts are matched in matching.py, then collapsed into capability groups so
# breadth is measured without rewarding lists of synonymous tools.
DIMENSION_EVIDENCE_GROUPS: Dict[str, Dict[str, Tuple[str, ...]]] = {
    "systems_network_foundation": {
        "operating_systems_resources": ("linux", "system resources"),
        "networking_protocols": ("networking",),
        "storage_io": ("storage",),
        "databases": ("database",),
        "concurrency_algorithms": ("concurrency", "data structures"),
    },
    "programming_automation": {
        "programming_languages": ("python", "go", "java", "c/c++"),
        "scripting_automation": ("shell", "automation"),
        "testing_engineering": ("testing", "engineering"),
        "cicd_version_control": ("ci/cd", "version control"),
        "infrastructure_as_code": ("iac",),
    },
    "troubleshooting": {
        "logs_observability": ("log analysis",),
        "resource_diagnosis": ("resource analysis",),
        "network_diagnosis": ("packet analysis",),
        "performance_analysis": ("profiling",),
        "experiment_validation": ("hypothesis validation",),
        "root_cause_recovery": (
            "troubleshooting",
            "debugging",
            "root cause analysis",
            "incident response",
            "postmortem",
        ),
    },
    "cloud_distributed_infrastructure": {
        "containers_orchestration": ("docker", "kubernetes", "container", "orchestration"),
        "cloud_platforms": ("cloud",),
        "distributed_architecture": (
            "distributed systems",
            "microservices",
            "service discovery",
        ),
        "middleware_messaging": ("message queue", "middleware"),
        "data_storage_services": ("database service", "storage service"),
    },
    "reliability_engineering": {
        "monitoring_observability": (
            "prometheus",
            "grafana",
            "zabbix",
            "datadog",
            "opentelemetry",
            "distributed tracing",
            "observability",
            "metrics",
            "logging",
        ),
        "alerting": ("alertmanager", "alert rules", "alert deduplication"),
        "service_levels": ("sli/slo",),
        "capacity_performance": ("capacity",),
        "availability_recovery": (
            "disaster recovery",
            "failover",
            "high availability",
        ),
        "operations_change": ("on-call", "runbook", "release rollback"),
        "resilience_validation": ("chaos engineering",),
    },
    "ai_engineering_aiops": {
        "assisted_engineering": ("ai coding",),
        "llm_rag": ("llm", "rag"),
        "agent_workflows": ("agent", "ai workflow"),
        "evaluation": ("evaluation",),
        "aiops_diagnosis": ("anomaly detection", "aiops", "automated diagnosis"),
    },
}

EVIDENCE_SCORES: Dict[str, float] = {
    "mention": 2.0,
    "usage": 4.0,
    "implementation": 6.0,
    "ownership": 8.0,
    "production": 9.0,
    "outcome": 9.0,
}

GRADE_RANGES: Dict[str, Tuple[float, float]] = {
    "A+": (9.5, 10.0),
    "A": (8.5, 9.4),
    "B": (7.0, 8.4),
    "C": (5.5, 6.9),
    "D": (4.0, 5.4),
    "F": (1.0, 3.9),
}

GRADE_THRESHOLDS: Dict[str, Dict[str, object]] = {
    "A+": {"range": [9.5, 10.0], "label": "卓越", "description": "简历证据覆盖度卓越"},
    "A": {"range": [8.5, 9.4], "label": "优秀", "description": "简历证据覆盖度优秀"},
    "B": {"range": [7.0, 8.4], "label": "良好", "description": "简历证据覆盖度良好"},
    "C": {"range": [5.5, 6.9], "label": "中等", "description": "简历证据覆盖度中等"},
    "D": {"range": [4.0, 5.4], "label": "需改进", "description": "简历证据覆盖度有限"},
    "F": {"range": [1.0, 3.9], "label": "证据不足", "description": "简历中的相关证据不足"},
}

DEFAULT_SCORING_CONFIG: Dict[str, object] = {
    "version": SCORING_CONFIG_VERSION,
    "dimension_weights": copy.deepcopy(DIMENSION_WEIGHTS),
    "evidence_scores": copy.deepcopy(EVIDENCE_SCORES),
    "grade_thresholds": copy.deepcopy(GRADE_THRESHOLDS),
    "matching": copy.deepcopy(DEFAULT_MATCHING_CONFIG),
    "evidence_groups": {
        dimension: {group: list(concepts) for group, concepts in groups.items()}
        for dimension, groups in DIMENSION_EVIDENCE_GROUPS.items()
    },
}

TECHNICAL_DIMENSIONS: Tuple[DimensionName, ...] = (
    "systems_network_foundation",
    "programming_automation",
    "troubleshooting",
    "cloud_distributed_infrastructure",
    "reliability_engineering",
    "ai_engineering_aiops",
)

_OWNERSHIP_DESIGN = re.compile(
    r"负责|主导|设计|架构|独立完成|\b(?:own(?:ed)?|lead|led|design(?:ed)?|architect(?:ed)?)\b",
    re.IGNORECASE,
)
_TROUBLESHOOTING = re.compile(
    r"排障|故障排查|问题定位|根因|调试|\b(?:debug|troubleshoot|root cause|rca)\b",
    re.IGNORECASE,
)
_VALIDATION = re.compile(
    r"验证|测试|压测|评测|监控结果|回归|\b(?:validat|verif|test|benchmark|evaluat)",
    re.IGNORECASE,
)
_REAL_WORLD = re.compile(
    r"生产|线上|真实用户|用户使用|实习|值班|规模|"
    r"\b(?:production|prod|real users?|on-call|at scale)\b",
    re.IGNORECASE,
)
_AI_HUMAN_VALIDATION = re.compile(
    r"人工确认|人工审核|人工验证|代码审查|结果验证|"
    r"\b(?:human[- ]in[- ]the[- ]loop|human review|code review|verified)\b",
    re.IGNORECASE,
)
_AI_WORKFLOW = re.compile(
    r"rag|智能体|agent|告警摘要|异常检测|自动诊断|工作流|pipeline|检索增强",
    re.IGNORECASE,
)
_AI_EVALUATION = re.compile(
    r"评测|评估集|测试集|样本|用例|基线|准确率|正确率|召回率|"
    r"\b(?:eval|evaluation|benchmark|baseline|test cases?)\b",
    re.IGNORECASE,
)
_AI_GUARDRAIL = re.compile(
    r"权限|安全|人工确认|人工审核|降级|回滚|兜底|脱敏|"
    r"\b(?:permission|security|human approval|fallback|rollback|guardrail)\b",
    re.IGNORECASE,
)


class GradeThreshold(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)

    range: List[float] = Field(min_length=2, max_length=2)
    label: str = Field(min_length=1)
    description: str = Field(min_length=1)

    @model_validator(mode="after")
    def validate_range(self) -> GradeThreshold:
        if self.range[0] > self.range[1]:
            raise ValueError("grade range minimum must not exceed maximum")
        return self


class MatchingSettings(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)

    version: str = Field(min_length=1)
    dimension_keywords: Dict[str, Dict[str, List[str]]]


class ScoringConfig(BaseModel):
    """Validated and immutable campus scoring configuration."""

    model_config = ConfigDict(extra="forbid", strict=True, frozen=True)

    version: str = Field(min_length=1)
    dimension_weights: Dict[str, float]
    evidence_scores: Dict[str, float]
    grade_thresholds: Dict[str, GradeThreshold]
    matching: MatchingSettings
    evidence_groups: Dict[str, Dict[str, List[str]]]

    @model_validator(mode="after")
    def validate_contract(self) -> ScoringConfig:
        if set(self.dimension_weights) != set(TECHNICAL_DIMENSIONS):
            raise ValueError("dimension_weights must define the six campus SRE dimensions")
        if abs(sum(self.dimension_weights.values()) - 1.0) > 1e-9:
            raise ValueError("dimension weights must sum to 1.0")
        if any(
            abs(self.dimension_weights[key] - expected) > 1e-9
            for key, expected in DIMENSION_WEIGHTS.items()
        ):
            raise ValueError("cn-campus-sre dimension weights are fixed")
        if set(self.evidence_scores) != {level.value for level in EvidenceLevel}:
            raise ValueError("evidence_scores must define every evidence level")
        if set(self.grade_thresholds) != set(GRADE_RANGES):
            raise ValueError("grade_thresholds must define A+, A, B, C, D, and F")
        if any(
            tuple(self.grade_thresholds[grade].range) != GRADE_RANGES[grade]
            for grade in GRADE_RANGES
        ):
            raise ValueError("cn-campus-sre grade boundaries are fixed")
        if set(self.matching.dimension_keywords) != set(TECHNICAL_DIMENSIONS):
            raise ValueError("matching must define the six campus SRE dimensions")
        if set(self.evidence_groups) != set(TECHNICAL_DIMENSIONS):
            raise ValueError("evidence_groups must define the six campus SRE dimensions")
        for dimension in TECHNICAL_DIMENSIONS:
            configured_concepts = set(self.matching.dimension_keywords[dimension])
            groups = self.evidence_groups[dimension]
            if not groups or any(not concepts for concepts in groups.values()):
                raise ValueError(f"evidence_groups for {dimension} must be non-empty")
            assigned = [concept for concepts in groups.values() for concept in concepts]
            if len(assigned) != len(set(assigned)) or set(assigned) != configured_concepts:
                raise ValueError(
                    f"evidence_groups for {dimension} must assign every concept exactly once"
                )
        return self

    @classmethod
    def from_source(
        cls,
        source: Optional[Union[ScoringConfig, Mapping[str, Any], str, Path]] = None,
    ) -> ScoringConfig:
        if source is None:
            return cls.model_validate(copy.deepcopy(DEFAULT_SCORING_CONFIG))
        if isinstance(source, cls):
            return source
        if isinstance(source, (str, Path)):
            path = Path(source)
            try:
                with path.open("r", encoding="utf-8") as handle:
                    data = (
                        json.load(handle)
                        if path.suffix.lower() == ".json"
                        else yaml.safe_load(handle)
                    )
            except (OSError, json.JSONDecodeError, yaml.YAMLError) as exc:
                raise ValueError(
                    f"scoring configuration could not be read: {type(exc).__name__}"
                ) from exc
            if not isinstance(data, Mapping):
                raise ValueError("scoring configuration root must be an object")
            return cls.model_validate(dict(data))
        return cls.model_validate(dict(source))


class ScoreCalculator:
    """Calculate repeatable evidence coverage scores from a validated resume."""

    def __init__(
        self,
        config: Optional[Union[ScoringConfig, Mapping[str, Any], str, Path]] = None,
        matcher: Optional[EvidenceMatcher] = None,
    ) -> None:
        self.config = ScoringConfig.from_source(config)
        self.matcher = matcher or EvidenceMatcher(self.config.matching.dimension_keywords)

    def calculate(self, resume: Resume) -> ScoreResult:
        dimensions: Dict[DimensionName, DimensionScore] = {}
        for dimension in TECHNICAL_DIMENSIONS:
            evidence = self.matcher.find_evidence(resume, dimension)
            dimensions[dimension] = self._score_dimension(dimension, evidence, resume)

        raw_total = sum(item.weighted_score for item in dimensions.values())
        total_score = round(min(10.0, max(1.0, raw_total)), 1)
        return ScoreResult(
            scoring_config_version=self.config.version,
            total_score=total_score,
            dimension_scores=dimensions,
            resume_quality=self._score_resume_quality(resume),
            grade=self.grade_for_score(total_score),
        )

    def calculate_scores(self, extracted_data: Union[Resume, Mapping[str, Any]]) -> ScoreResult:
        resume = (
            extracted_data
            if isinstance(extracted_data, Resume)
            else Resume.model_validate(dict(extracted_data))
        )
        return self.calculate(resume)

    def _score_dimension(
        self,
        dimension: DimensionName,
        evidence: Sequence[Evidence],
        resume: Resume,
    ) -> DimensionScore:
        depth_score = (
            self._score_ai_dimension(evidence, resume)
            if dimension == "ai_engineering_aiops"
            else self._score_general_dimension(evidence, resume)
        )
        group_scores, covered_groups, applied_groups, missing_groups = (
            self._evidence_group_coverage(dimension, evidence)
        )
        coverage_cap = _coverage_cap(len(applied_groups))
        score = min(depth_score, coverage_cap)
        strongest = max(
            (item.level for item in evidence),
            key=lambda level: self.config.evidence_scores[level.value],
            default=None,
        )
        weight = self.config.dimension_weights[dimension]
        return DimensionScore(
            score=score,
            depth_score=depth_score,
            coverage_cap=coverage_cap,
            weight=weight,
            weighted_score=score * weight,
            evidence=list(evidence),
            keyword_count=len({item.keyword for item in evidence}),
            evidence_group_scores=group_scores,
            covered_evidence_groups=covered_groups,
            applied_evidence_groups=applied_groups,
            missing_evidence_groups=missing_groups,
            evidence_coverage=len(applied_groups) / len(group_scores),
            strongest_evidence_level=strongest,
        )

    def _evidence_group_coverage(
        self,
        dimension: DimensionName,
        evidence: Sequence[Evidence],
    ) -> Tuple[Dict[str, float], List[str], List[str], List[str]]:
        group_scores: Dict[str, float] = {}
        covered: List[str] = []
        applied: List[str] = []
        missing: List[str] = []
        for group, concepts in self.config.evidence_groups[dimension].items():
            items = [item for item in evidence if item.keyword in concepts]
            if not items:
                group_scores[group] = 0.0
                missing.append(group)
                continue
            covered.append(group)
            group_scores[group] = max(
                self.config.evidence_scores[item.level.value] for item in items
            )
            if any(
                item.source_kind != "skills" and item.level != EvidenceLevel.mention
                for item in items
            ):
                applied.append(group)
        return group_scores, covered, applied, missing

    def _score_general_dimension(self, evidence: Sequence[Evidence], resume: Resume) -> float:
        if not evidence:
            return 1.0
        grouped = _group_source_contexts(evidence)
        source_texts = _source_texts(resume)
        strong_sources = {
            source_id
            for source_id, items in grouped.items()
            if max(self.config.evidence_scores[item.level.value] for item in items) >= 6.0
        }
        complete_sources = {
            source_id
            for source_id, items in grouped.items()
            if _is_complete_student_project(items, source_texts.get(source_id, ""))
        }
        real_sources = {
            source_id
            for source_id, items in grouped.items()
            if _has_real_world_result(items, source_texts.get(source_id, ""))
        }
        if len(strong_sources) >= 2 and (complete_sources or real_sources):
            return 10.0
        if real_sources:
            return 9.0
        if complete_sources:
            return 8.0
        return min(
            6.0,
            max(self.config.evidence_scores[item.level.value] for item in evidence),
        )

    def _score_ai_dimension(self, evidence: Sequence[Evidence], resume: Resume) -> float:
        if not evidence:
            return 1.0
        grouped = _group_source_contexts(evidence)
        source_texts = _source_texts(resume)
        strong_sources = set()
        source_scores: List[float] = []
        for source_id, items in grouped.items():
            text = source_texts.get(source_id, " ".join(item.context for item in items))
            if source_id.startswith("skills:"):
                source_score = 2.0
            elif _AI_WORKFLOW.search(text) and (
                _OWNERSHIP_DESIGN.search(text)
                or re.search(r"实现|开发|构建|部署|编写|集成", text, re.IGNORECASE)
                or any(
                    item.level
                    in {
                        EvidenceLevel.implementation,
                        EvidenceLevel.ownership,
                        EvidenceLevel.production,
                        EvidenceLevel.outcome,
                    }
                    for item in items
                )
            ):
                source_score = 6.0
            elif _AI_HUMAN_VALIDATION.search(text) and any(
                item.level != EvidenceLevel.mention for item in items
            ):
                source_score = 4.0
            else:
                source_score = 2.0
            if _AI_EVALUATION.search(text) and _AI_GUARDRAIL.search(text) and source_score >= 6.0:
                source_score = 8.0
            if (
                _has_real_world_result(items, text)
                or (_AI_EVALUATION.search(text) and is_quantified(text))
            ) and source_score >= 6.0:
                source_score = 9.0
            if source_score >= 6.0:
                strong_sources.add(source_id)
            source_scores.append(source_score)
        if len(strong_sources) >= 2 and max(source_scores) >= 8.0:
            return 10.0
        return max(source_scores)

    def _score_resume_quality(self, resume: Resume) -> ResumeQualityDiagnostic:
        records = list(resume.internships) + list(resume.projects)
        skill_count = sum(len(items) for items in resume.skills.model_dump(mode="python").values())
        basic_values = resume.basic_info.model_dump(mode="python", exclude={"contact"}).values()
        present_basic = sum(value is not None for value in basic_values)
        completeness = (
            2.0
            if present_basic >= 4 and records and skill_count
            else (1.0 if present_basic or records or skill_count else 0.0)
        )

        contexts = [
            sentence
            for record in iter_resume_records(resume)
            if record.source_kind != "skills" and not record.mention_only
            for sentence, _ in iter_sentences(record.text)
            if not is_instruction_like(sentence)
        ]
        action_count = sum(classify_evidence(text) != EvidenceLevel.mention for text in contexts)
        action_result = (
            2.0
            if contexts and action_count >= 2 and action_count / len(contexts) >= 0.6
            else (1.0 if action_count else 0.0)
        )
        quantified_count = sum(is_quantified(text) for text in contexts)
        quantified_result = 2.0 if quantified_count >= 2 else (1.0 if quantified_count else 0.0)

        normalized_contexts = [normalize_text(text) for text in contexts if text.strip()]
        clear_count = sum(20 <= len(text) <= 500 for text in normalized_contexts)
        unique_ratio = (
            len(set(normalized_contexts)) / len(normalized_contexts) if normalized_contexts else 0.0
        )
        clarity = (
            2.0
            if normalized_contexts
            and clear_count / len(normalized_contexts) >= 0.6
            and unique_ratio >= 0.75
            else (1.0 if normalized_contexts else 0.0)
        )

        if records:
            durations = sum(record.duration is not None for record in records)
            described = sum(bool(record.description or record.achievements) for record in records)
            consistency = (
                2.0
                if durations == len(records) and described == len(records)
                else (1.0 if durations or described else 0.0)
            )
        else:
            consistency = 0.0

        breakdown = {
            "completeness": completeness,
            "action_result": action_result,
            "quantified_results": quantified_result,
            "clarity": clarity,
            "timeline_technical_consistency": consistency,
        }
        findings = {
            "completeness": _quality_finding(
                completeness, "核心信息与经历覆盖", "补充基本信息、项目或实习及技能"
            ),
            "action_result": _quality_finding(
                action_result, "行动与结果描述", "用行动、方法和结果描述经历"
            ),
            "quantified_results": _quality_finding(
                quantified_result, "同源量化结果", "补充可核验的同项目量化结果"
            ),
            "clarity": _quality_finding(clarity, "表达清晰度", "精简重复或过短描述并说明上下文"),
            "timeline_technical_consistency": _quality_finding(
                consistency, "时间线与技术表述", "补充经历时间和对应技术说明"
            ),
        }
        return ResumeQualityDiagnostic(
            score=min(10.0, max(1.0, sum(breakdown.values()))),
            breakdown=breakdown,
            findings=findings,
        )

    def grade_for_score(self, total_score: float) -> GradeInfo:
        rounded = round(total_score, 1)
        for grade in ("A+", "A", "B", "C", "D", "F"):
            threshold = self.config.grade_thresholds[grade]
            lower, upper = threshold.range
            if lower <= rounded <= upper:
                return GradeInfo(
                    grade=grade,
                    label=threshold.label,
                    description=threshold.description,
                    range=(lower, upper),
                )
        threshold = self.config.grade_thresholds["F"]
        return GradeInfo(
            grade="F",
            label=threshold.label,
            description=threshold.description,
            range=(threshold.range[0], threshold.range[1]),
        )


def _group_source_contexts(evidence: Sequence[Evidence]) -> Dict[str, List[Evidence]]:
    grouped: Dict[str, List[Evidence]] = {}
    for item in evidence:
        grouped.setdefault(item.source_id, []).append(item)
    return grouped


def _source_texts(resume: Resume) -> Dict[str, str]:
    grouped: Dict[str, List[str]] = {}
    for record in iter_resume_records(resume):
        safe_sentences = [
            sentence
            for sentence, _ in iter_sentences(record.text)
            if not is_instruction_like(sentence)
        ]
        grouped.setdefault(record.source_id, []).extend(safe_sentences)
    return {source_id: " ".join(parts) for source_id, parts in grouped.items()}


def _is_complete_student_project(items: Sequence[Evidence], text: str) -> bool:
    if not items or items[0].source_kind == "skills":
        return False
    return bool(
        _OWNERSHIP_DESIGN.search(text)
        and _TROUBLESHOOTING.search(text)
        and _VALIDATION.search(text)
        and any(item.level != EvidenceLevel.mention for item in items)
    )


def _has_real_world_result(items: Sequence[Evidence], text: str) -> bool:
    if not items or items[0].source_kind == "skills":
        return False
    return bool(
        _REAL_WORLD.search(text)
        or any(item.quantified and item.level == EvidenceLevel.outcome for item in items)
    )


def _coverage_cap(applied_group_count: int) -> float:
    """Cap high evidence depth when it is narrow in technical capability breadth."""

    if applied_group_count <= 0:
        return 2.0
    if applied_group_count == 1:
        return 8.0
    if applied_group_count == 2:
        return 9.0
    return 10.0


def _quality_finding(score: float, positive: str, improvement: str) -> str:
    if score >= 2.0:
        return f"较完整：{positive}。"
    if score >= 1.0:
        return f"部分体现：{positive}；建议{improvement}。"
    return f"尚未体现：建议{improvement}。"
