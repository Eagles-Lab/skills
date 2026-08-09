"""Deterministic general campus-security evidence scoring."""

from __future__ import annotations

import re
from collections import defaultdict
from typing import Sequence

from .authorization import (
    environment_is_authorized,
    has_negative_authorization_signal,
    has_positive_authorization_signal,
)
from .matching import (
    DIMENSION_CONCEPTS,
    EvidenceMatcher,
    is_quantified,
    iter_resume_records,
    iter_sentences,
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

DIMENSIONS: tuple[DimensionName, ...] = (
    "systems_network_security_foundation",
    "programming_security_engineering_automation",
    "vulnerability_research_security_assessment",
    "detection_defense_incident_response",
    "cloud_identity_data_supply_chain",
    "ai_assisted_security_ai_system_security",
)

DIMENSION_WEIGHTS: dict[DimensionName, float] = dict(
    zip(DIMENSIONS, (0.20, 0.20, 0.15, 0.20, 0.15, 0.10), strict=True)
)

LEVEL_SCORE = {
    EvidenceLevel.mention: 2.0,
    EvidenceLevel.usage: 4.0,
    EvidenceLevel.implementation: 6.0,
    EvidenceLevel.ownership: 8.0,
    EvidenceLevel.production: 9.0,
    EvidenceLevel.outcome: 9.0,
}

_METHOD = re.compile(
    r"方法|步骤|流程|假设|攻击链|检测逻辑|规则逻辑|\b(?:method|steps?|workflow|hypothesis|attack chain|detection logic)\b",
    re.I,
)
_VALIDATE = re.compile(
    r"验证|复测|回归|测试|评测|对照|复现|\b(?:validat|verif|retest|regression|evaluat|reproduc)",
    re.I,
)
_CLOSURE = re.compile(
    r"修复|缓解|防御|阻断|隔离|恢复|建议|\b(?:remediat|mitigat|defen[cs]e|block|contain|recover|recommend)",
    re.I,
)
_OWN = re.compile(r"负责|主导|设计|独立|\b(?:owned?|led|lead|designed?)\b", re.I)
_REAL = re.compile(
    r"生产|线上|真实业务|用户|客户|赏金|披露|应急|\b(?:production|real[- ]world|customer|bounty|disclos|incident)\b",
    re.I,
)
_AI_WORKFLOW = re.compile(
    r"rag|agent|智能体|自动分析|安全工作流|告警研判|漏洞分析|\b(?:workflow|pipeline|triage|rag|agent)\b",
    re.I,
)
_AI_HUMAN = re.compile(
    r"人工确认|人工审核|结果验证|代码审查|\b(?:human approval|human review|verified|code review)\b",
    re.I,
)
_AI_EVAL = re.compile(
    r"评测|测试集|红队|准确率|召回率|基线|\b(?:evaluation|benchmark|red team|accuracy|recall|baseline)\b",
    re.I,
)
_AI_GUARD = re.compile(
    r"权限|隔离|沙箱|降级|回滚|脱敏|监控|人工确认|\b(?:permission|sandbox|isolation|fallback|rollback|guardrail|monitoring)\b",
    re.I,
)


def coverage_cap(applied_group_count: int) -> float:
    return (2.0, 8.0, 9.0, 10.0)[min(max(applied_group_count, 0), 3)]


class ScoreCalculator:
    def __init__(self, matcher: EvidenceMatcher | None = None) -> None:
        self.weights = DIMENSION_WEIGHTS
        self.matcher = matcher or EvidenceMatcher()

    def calculate(self, resume: Resume) -> ScoreResult:
        dimensions = {
            dimension: self._score_dimension(
                dimension, self.matcher.find_evidence(resume, dimension), resume
            )
            for dimension in DIMENSIONS
        }
        total = round(
            max(1.0, min(10.0, sum(item.weighted_score for item in dimensions.values()))), 1
        )
        return ScoreResult(
            dimension_weights=self.weights,
            total_score=total,
            dimension_scores=dimensions,
            resume_quality=self._resume_quality(resume),
            grade=grade_for_score(total),
        )

    def _score_dimension(
        self, dimension: DimensionName, evidence: list[Evidence], resume: Resume
    ) -> DimensionScore:
        depth = self._depth_score(dimension, evidence, resume)
        group_names = list(DIMENSION_CONCEPTS[dimension])
        group_scores: dict[str, float] = {}
        covered: list[str] = []
        applied: list[str] = []
        missing: list[str] = []
        for group in group_names:
            values = [item for item in evidence if item.evidence_group == group]
            if not values:
                group_scores[group] = 0.0
                missing.append(group)
                continue
            group_scores[group] = max(LEVEL_SCORE[item.level] for item in values)
            covered.append(group)
            if any(
                item.source_kind != "skills" and item.level is not EvidenceLevel.mention
                for item in values
            ):
                applied.append(group)
        cap = coverage_cap(len(applied))
        score = min(depth, cap)
        strongest = max(
            (item.level for item in evidence),
            key=lambda level: LEVEL_SCORE[level],
            default=None,
        )
        weight = self.weights[dimension]
        return DimensionScore(
            score=score,
            depth_score=depth,
            coverage_cap=cap,
            weight=weight,
            weighted_score=score * weight,
            evidence=evidence,
            evidence_group_scores=group_scores,
            covered_evidence_groups=covered,
            applied_evidence_groups=applied,
            missing_evidence_groups=missing,
            evidence_coverage=len(applied) / len(group_names),
            strongest_evidence_level=strongest,
        )

    def _depth_score(
        self, dimension: DimensionName, evidence: Sequence[Evidence], resume: Resume
    ) -> float:
        if not evidence:
            return 1.0
        grouped: dict[str, list[Evidence]] = defaultdict(list)
        for item in evidence:
            grouped[item.source_id].append(item)
        texts = _source_texts(resume)
        scores = [
            self._source_score(dimension, source_id, items, texts.get(source_id, ""))
            for source_id, items in grouped.items()
        ]
        strong = sum(score >= 6.0 for score in scores)
        if strong >= 2 and max(scores) >= 8.0:
            return 10.0
        return max(scores)

    def _source_score(
        self, dimension: DimensionName, source_id: str, evidence: Sequence[Evidence], text: str
    ) -> float:
        if source_id.startswith("skills:"):
            return 2.0
        if dimension == "ai_assisted_security_ai_system_security":
            return _ai_source_score(evidence, text)
        score = max(LEVEL_SCORE[item.level] for item in evidence)
        score = min(score, 6.0)
        complete_loop = bool(
            _METHOD.search(text)
            and _VALIDATE.search(text)
            and _CLOSURE.search(text)
            and _OWN.search(text)
        )
        if complete_loop:
            score = 8.0
        if (
            score >= 6.0
            and _REAL.search(text)
            and (is_quantified(text) or any(item.quantified for item in evidence))
        ):
            score = 9.0
        if dimension == "vulnerability_research_security_assessment" and not _authorized_source(
            evidence, text
        ):
            score = min(score, 4.0)
        return score

    def _resume_quality(self, resume: Resume) -> ResumeQualityDiagnostic:
        applied_records = [
            record
            for record in iter_resume_records(resume)
            if not record.mention_only and not is_instruction_like(record.text)
        ]
        texts = [record.text for record in applied_records]
        personal = _two_point(
            any(_OWN.search(text) for text in texts),
            sum(bool(_OWN.search(text)) for text in texts) >= 2,
        )
        authorization = _two_point(
            any(has_positive_authorization_signal(text) for text in texts),
            any(environment_is_authorized(item.authorization) for item in applied_records),
        )
        methodology = _two_point(
            any(_METHOD.search(text) for text in texts),
            any(_METHOD.search(text) and _VALIDATE.search(text) for text in texts),
        )
        closure = _two_point(
            any(_VALIDATE.search(text) or _CLOSURE.search(text) for text in texts),
            any(_VALIDATE.search(text) and _CLOSURE.search(text) for text in texts),
        )
        normalized = [" ".join(text.split()) for text in texts if text.strip()]
        clarity = _two_point(
            bool(normalized),
            bool(normalized)
            and len(set(normalized)) == len(normalized)
            and all(12 <= len(text) <= 2000 for text in normalized),
        )
        breakdown = {
            "personal_contribution": personal,
            "authorization_scope": authorization,
            "methodology_process": methodology,
            "validation_remediation": closure,
            "clarity_consistency": clarity,
        }
        labels = {
            "personal_contribution": "个人贡献与责任边界",
            "authorization_scope": "授权范围",
            "methodology_process": "方法与过程",
            "validation_remediation": "验证与修复闭环",
            "clarity_consistency": "表述清晰和一致性",
        }
        findings = {key: _quality_finding(value, labels[key]) for key, value in breakdown.items()}
        return ResumeQualityDiagnostic(
            score=max(1.0, sum(breakdown.values())), breakdown=breakdown, findings=findings
        )


def _authorized_source(evidence: Sequence[Evidence], text: str) -> bool:
    del text
    return any(
        item.authorization is not None
        and environment_is_authorized(item.authorization)
        and not has_negative_authorization_signal(item.context)
        for item in evidence
    )


def _ai_source_score(evidence: Sequence[Evidence], text: str) -> float:
    if not evidence or evidence[0].source_kind == "skills":
        return 2.0
    score = (
        4.0
        if _AI_HUMAN.search(text)
        and any(item.level is not EvidenceLevel.mention for item in evidence)
        else 2.0
    )
    if _AI_WORKFLOW.search(text) and any(
        item.level
        in {
            EvidenceLevel.implementation,
            EvidenceLevel.ownership,
            EvidenceLevel.production,
            EvidenceLevel.outcome,
        }
        for item in evidence
    ):
        score = 6.0
    if score >= 6.0 and _AI_EVAL.search(text) and _AI_GUARD.search(text):
        score = 8.0
    if score >= 8.0 and _REAL.search(text) and is_quantified(text):
        score = 9.0
    return score


def _source_texts(resume: Resume) -> dict[str, str]:
    grouped: dict[str, list[str]] = defaultdict(list)
    for record in iter_resume_records(resume):
        for sentence, _ in iter_sentences(record.text):
            if not is_instruction_like(sentence) and not has_negative_authorization_signal(
                sentence
            ):
                grouped[record.source_id].append(sentence)
    return {key: " ".join(values) for key, values in grouped.items()}


def _two_point(partial: bool, full: bool) -> float:
    return 2.0 if full else (1.0 if partial else 0.0)


def _quality_finding(score: float, label: str) -> str:
    if score >= 2.0:
        return f"较完整：{label}有具体、相互一致的证据。"
    if score >= 1.0:
        return f"部分体现：{label}仍可补充范围、过程或验证结果。"
    return f"尚未体现：建议补充{label}的可核验事实。"


def grade_for_score(score: float) -> GradeInfo:
    boundaries = (
        ("A+", 9.5, 10.0, "卓越"),
        ("A", 8.5, 9.4, "优秀"),
        ("B", 7.0, 8.4, "良好"),
        ("C", 5.5, 6.9, "中等"),
        ("D", 4.0, 5.4, "有限"),
        ("F", 1.0, 3.9, "证据不足"),
    )
    rounded = round(score, 1)
    for grade, lower, upper, label in boundaries:
        if lower <= rounded <= upper:
            return GradeInfo(grade=grade, label=label, range=(lower, upper))  # type: ignore[arg-type]
    return GradeInfo(grade="F", label="证据不足", range=(1.0, 3.9))
