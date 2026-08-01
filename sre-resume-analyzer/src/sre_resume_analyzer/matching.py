"""Deterministic, language-aware evidence matching for canonical resumes."""

from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass
from typing import Dict, Iterator, List, Mapping, Optional, Sequence, Tuple

from .models import DimensionName, Evidence, EvidenceLevel, Resume, SourceKind
from .security import is_instruction_like

MATCHING_CONFIG_VERSION = "3.0.0"

# Variants that represent the same concept are grouped under one canonical key.
DEFAULT_DIMENSION_KEYWORDS: Dict[str, Dict[str, Tuple[str, ...]]] = {
    "monitoring": {
        "prometheus": ("prometheus",),
        "grafana": ("grafana",),
        "zabbix": ("zabbix",),
        "datadog": ("datadog",),
        "opentelemetry": ("opentelemetry", "otel"),
        "distributed tracing": ("distributed tracing", "分布式追踪", "分布式链路追踪"),
        "observability": ("observability", "可观测性"),
        "sli/slo": ("sli", "slo", "服务等级目标"),
        "metrics": ("metrics", "指标监控", "监控指标"),
        "logging": ("log aggregation", "日志聚合", "loki", "elk", "efk"),
    },
    "alerting": {
        "alertmanager": ("alertmanager",),
        "pagerduty": ("pagerduty",),
        "opsgenie": ("opsgenie",),
        "alert rules": ("alert rules", "告警规则"),
        "on-call": ("on-call", "on call", "值班"),
        "runbook": ("runbook", "playbook", "处置手册"),
        "alert routing": ("alert routing", "告警路由"),
        "alert deduplication": ("alert deduplication", "告警收敛", "告警降噪"),
        "escalation": ("escalation", "告警升级", "告警分级"),
    },
    "automation": {
        "python": ("python",),
        "go": ("golang", "go"),
        "shell": ("shell", "bash"),
        "jenkins": ("jenkins",),
        "gitlab ci": ("gitlab ci",),
        "github actions": ("github actions",),
        "argocd": ("argocd", "argo cd"),
        "terraform": ("terraform",),
        "ansible": ("ansible",),
        "iac": ("infrastructure as code", "iac", "基础设施即代码"),
        "ci/cd": ("ci/cd", "cicd", "持续集成", "持续交付"),
        "automation": ("automation", "自动化"),
    },
    "containerization": {
        "docker": ("docker",),
        "kubernetes": ("kubernetes", "k8s"),
        "containerd": ("containerd",),
        "helm": ("helm",),
        "kustomize": ("kustomize",),
        "service mesh": ("service mesh", "服务网格"),
        "istio": ("istio",),
        "gitops": ("gitops",),
        "aws": ("aws", "amazon web services"),
        "gcp": ("gcp", "google cloud"),
        "azure": ("azure",),
        "cloud native": ("cloud native", "云原生"),
    },
    "incident_handling": {
        "incident response": ("incident response", "故障响应", "应急响应"),
        "troubleshooting": ("troubleshooting", "故障排查", "问题定位"),
        "root cause analysis": ("root cause analysis", "rca", "根因分析"),
        "postmortem": ("postmortem", "复盘"),
        "disaster recovery": ("disaster recovery", "灾难恢复", "容灾"),
        "failover": ("failover", "故障切换"),
        "high availability": ("high availability", "高可用"),
        "chaos engineering": ("chaos engineering", "故障演练", "混沌工程"),
        "debugging": ("debugging", "debug", "调试"),
    },
}

DEFAULT_AI_KEYWORDS: Dict[str, Tuple[str, ...]] = {
    "llm": (
        "llm",
        "gpt",
        "claude",
        "chatgpt",
        "rag",
        "langchain",
        "large language model",
        "大语言模型",
        "检索增强生成",
    ),
    "ai_agents": (
        "ai agent",
        "intelligent agent",
        "multi-agent",
        "agent orchestration",
        "function calling",
        "智能体",
        "多智能体",
    ),
    "ai_ide": (
        "cursor",
        "github copilot",
        "codeium",
        "tabnine",
        "codewhisperer",
        "ai-assisted coding",
        "ai 辅助编程",
    ),
    "ml_ops": (
        "machine learning",
        "deep learning",
        "tensorflow",
        "pytorch",
        "anomaly detection",
        "time series forecasting",
        "机器学习",
        "异常检测",
        "时序预测",
    ),
    "aiops": (
        "aiops",
        "intelligent monitoring",
        "smart alerting",
        "automated diagnosis",
        "predictive maintenance",
        "智能监控",
        "智能告警",
        "自动诊断",
        "预测性维护",
    ),
}

DEFAULT_MATCHING_CONFIG: Dict[str, object] = {
    "version": MATCHING_CONFIG_VERSION,
    "dimension_keywords": {
        dimension: {canonical: list(variants) for canonical, variants in concepts.items()}
        for dimension, concepts in DEFAULT_DIMENSION_KEYWORDS.items()
    },
    "ai_keywords": {category: list(terms) for category, terms in DEFAULT_AI_KEYWORDS.items()},
}

_SENTENCE_PATTERN = re.compile(r"[^\n。\uFF01\uFF1F!?\uFF1B;]+")
_CJK_PATTERN = re.compile(r"[\u3400-\u9fff]")
_QUANTIFIED_PATTERN = re.compile(
    r"(?:\d+(?:\.\d+)?\s*(?:%|\uFF05|倍|x|ms|s|秒|分钟|小时|个|台|节点|服务|集群|qps|rps))",
    re.IGNORECASE,
)
_ACTION_PATTERN = re.compile(
    r"使用|运用|基于|维护|操作|参与|处理|"
    r"\b(?:use[ds]?|using|operate[ds]?|maintain(?:ed|s)?|participat(?:e|ed|ing)|handle[ds]?)\b",
    re.IGNORECASE,
)
_IMPLEMENTATION_PATTERN = re.compile(
    r"实现|搭建|部署|配置|开发|构建|编写|创建|迁移|集成|自动化|"
    r"\b(?:implement(?:ed|s|ing)?|build|built|deploy(?:ed|s|ing)?|configur(?:e|ed|ing)|"
    r"develop(?:ed|s|ing)?|creat(?:e|ed|ing)|migrat(?:e|ed|ing)|integrat(?:e|ed|ing)|automate[ds]?)\b",
    re.IGNORECASE,
)
_OWNERSHIP_PATTERN = re.compile(
    r"主导|负责|设计|架构|牵头|独立完成|"
    r"\b(?:lead|led|own(?:ed|s)?|design(?:ed|s|ing)?|architect(?:ed|s|ing)?)\b",
    re.IGNORECASE,
)
_PRODUCTION_PATTERN = re.compile(
    r"生产环境|生产集群|线上环境|线上系统|大规模|值班|"
    r"\b(?:production|prod|at scale|on-call|on call)\b",
    re.IGNORECASE,
)
_OUTCOME_PATTERN = re.compile(
    r"提升|提高|降低|减少|节省|缩短|优化至|增长|"
    r"\b(?:increase[ds]?|improv(?:e|ed)|reduc(?:e|ed)|decreas(?:e|ed)|sav(?:e|ed)|cut)\b",
    re.IGNORECASE,
)

_CHINESE_NEGATION = re.compile(
    r"(?:不|未|无|没有|并未|从未|仅|只)(?:熟悉|了解|使用|接触|配置|部署|掌握|有经验|学习)?"
    r"[^\uFF0C,。\uFF1B;\n]{0,12}$"
)
_CHINESE_POST_NEGATION = re.compile(r"^(?:并)?(?:不|未)(?:熟悉|了解|会|使用|掌握|有经验)")
_ENGLISH_NEGATION = re.compile(
    r"(?:\bno experience(?:\s+\w+){0,3}\s+(?:with|in)|\bnot(?:\s+\w+){0,4}|\bnever|"
    r"\bwithout|\black(?:s|ed|ing)?|\bbasic understanding(?:\s+of)?)\s*$",
    re.IGNORECASE,
)
_ENGLISH_NEGATION_LIST = re.compile(
    r"\b(?:no experience (?:with|in)|not familiar with)\b[^.!?;]*$",
    re.IGNORECASE,
)
_ENGLISH_POST_NEGATION = re.compile(
    r"^\s*(?:is\s+)?not\s+(?:familiar|used|known|experienced)",
    re.IGNORECASE,
)
_CONTRAST_BOUNDARY = re.compile(
    r"(?:但是|但|然而|不过|却|\bbut\b|\bhowever\b|\byet\b|\balthough\b|\bwhile\b)",
    re.IGNORECASE,
)


@dataclass(frozen=True)
class ResumeTextRecord:
    source_kind: SourceKind
    source_id: str
    text: str
    mention_only: bool = False


@dataclass(frozen=True)
class TermMatch:
    canonical: str
    variant: str
    start: int
    end: int


def normalize_text(text: str) -> str:
    """Normalize text without language-specific tokenization assumptions."""

    normalized = unicodedata.normalize("NFKC", text).lower()
    normalized = re.sub(r"[\u2010\u2011\u2012\u2013\u2014\u2212]", "-", normalized)
    return re.sub(r"[\t\r ]+", " ", normalized).strip()


def contains_cjk(text: str) -> bool:
    return bool(_CJK_PATTERN.search(text))


def term_pattern(term: str) -> re.Pattern[str]:
    """Build a CJK substring or Latin alphanumeric-boundary expression."""

    term = normalize_text(term)
    escaped = re.escape(term).replace(r"\ ", r"\s+")
    if contains_cjk(term):
        return re.compile(escaped, re.IGNORECASE)
    return re.compile(r"(?<![A-Za-z0-9_])" + escaped + r"(?![A-Za-z0-9_])", re.IGNORECASE)


def is_negated(text: str, start: int, end: int) -> bool:
    """Return true when a local negation or weak-knowledge phrase scopes a match."""

    prefix = text[max(0, start - 64) : start]
    prefix = _CONTRAST_BOUNDARY.split(prefix)[-1]
    suffix = text[end : min(len(text), end + 32)]
    return bool(
        _CHINESE_NEGATION.search(prefix)
        or _CHINESE_POST_NEGATION.search(suffix)
        or _ENGLISH_NEGATION.search(prefix)
        or _ENGLISH_NEGATION_LIST.search(prefix)
        or _ENGLISH_POST_NEGATION.search(suffix)
    )


def is_quantified(text: str) -> bool:
    return bool(_QUANTIFIED_PATTERN.search(text))


def classify_evidence(text: str, mention_only: bool = False) -> EvidenceLevel:
    """Classify evidence from explicit language, not keyword frequency."""

    if mention_only:
        return EvidenceLevel.mention
    has_action = bool(
        _ACTION_PATTERN.search(text)
        or _IMPLEMENTATION_PATTERN.search(text)
        or _OWNERSHIP_PATTERN.search(text)
        or _OUTCOME_PATTERN.search(text)
    )
    if has_action and is_quantified(text) and _OUTCOME_PATTERN.search(text):
        return EvidenceLevel.outcome
    if has_action and _PRODUCTION_PATTERN.search(text):
        return EvidenceLevel.production
    if _OWNERSHIP_PATTERN.search(text):
        return EvidenceLevel.ownership
    if _IMPLEMENTATION_PATTERN.search(text):
        return EvidenceLevel.implementation
    if _ACTION_PATTERN.search(text):
        return EvidenceLevel.usage
    return EvidenceLevel.mention


def iter_sentences(text: str) -> Iterator[Tuple[str, int]]:
    for match in _SENTENCE_PATTERN.finditer(text):
        sentence = match.group(0).strip(" ,\uff0c:\t")
        if sentence:
            leading = len(match.group(0)) - len(match.group(0).lstrip(" ,\uff0c:\t"))
            yield sentence, match.start() + leading


def iter_resume_records(resume: Resume) -> Iterator[ResumeTextRecord]:
    """Yield stable, privacy-minimized records; basic identity is intentionally excluded."""

    skill_groups = resume.skills.model_dump(mode="python")
    for group_name in sorted(skill_groups):
        for item in skill_groups[group_name]:
            yield ResumeTextRecord("skills", "skills:" + group_name, item, True)

    for index, internship in enumerate(resume.internships):
        source_id = "internship:" + str(index)
        yield ResumeTextRecord("internship", source_id, internship.description)
        for achievement in internship.achievements:
            yield ResumeTextRecord("internship", source_id, achievement)
        for item in internship.tech_stack:
            yield ResumeTextRecord("internship", source_id, item, True)

    for index, project in enumerate(resume.projects):
        source_id = "project:" + str(index)
        yield ResumeTextRecord("project", source_id, project.description)
        for achievement in project.achievements:
            yield ResumeTextRecord("project", source_id, achievement)
        for item in project.tech_stack:
            yield ResumeTextRecord("project", source_id, item, True)


class EvidenceMatcher:
    """Match stable, de-duplicated evidence from a canonical resume."""

    def __init__(
        self,
        dimension_keywords: Optional[Mapping[str, Mapping[str, Sequence[str]]]] = None,
    ):
        source = dimension_keywords or DEFAULT_DIMENSION_KEYWORDS
        self.dimension_keywords: Dict[str, Dict[str, Tuple[str, ...]]] = {
            dimension: {canonical: tuple(variants) for canonical, variants in concepts.items()}
            for dimension, concepts in source.items()
        }

    @staticmethod
    def match_terms(text: str, terms: Mapping[str, Sequence[str]]) -> List[TermMatch]:
        normalized = normalize_text(text)
        matches: List[TermMatch] = []
        for canonical in sorted(terms):
            for variant in sorted(
                set(terms[canonical]),
                key=lambda item: (len(item), item),
                reverse=True,
            ):
                for occurrence in term_pattern(variant).finditer(normalized):
                    if not is_negated(normalized, occurrence.start(), occurrence.end()):
                        matches.append(
                            TermMatch(canonical, variant, occurrence.start(), occurrence.end())
                        )
        # Prefer the longest synonymous variant at the same location.
        unique: Dict[Tuple[str, int], TermMatch] = {}
        for term_match in sorted(
            matches,
            key=lambda item: (item.start, -(item.end - item.start), item.canonical),
        ):
            unique.setdefault((term_match.canonical, term_match.start), term_match)
        return sorted(unique.values(), key=lambda item: (item.start, item.canonical, item.variant))

    def find_evidence(self, resume: Resume, dimension: DimensionName) -> List[Evidence]:
        if dimension == "resume_quality":
            return []
        terms = self.dimension_keywords.get(dimension, {})
        evidence: Dict[Tuple[str, str], Evidence] = {}
        for record in iter_resume_records(resume):
            for sentence, sentence_offset in iter_sentences(record.text):
                if is_instruction_like(sentence):
                    continue
                for match in self.match_terms(sentence, terms):
                    level = classify_evidence(sentence, record.mention_only)
                    item = Evidence(
                        dimension=dimension,
                        keyword=match.canonical,
                        source_kind=record.source_kind,
                        source_id=record.source_id,
                        context=sentence,
                        level=level,
                        position=sentence_offset + match.start,
                        quantified=is_quantified(sentence),
                    )
                    key = (record.source_id, match.canonical)
                    previous = evidence.get(key)
                    if previous is None or _evidence_sort_value(item) > _evidence_sort_value(
                        previous
                    ):
                        evidence[key] = item
        source_order = {"skills": 0, "internship": 1, "project": 2}
        return sorted(
            evidence.values(),
            key=lambda item: (
                source_order[item.source_kind],
                item.source_id,
                item.position,
                item.keyword,
            ),
        )


_LEVEL_ORDER = {
    EvidenceLevel.mention: 1,
    EvidenceLevel.usage: 2,
    EvidenceLevel.implementation: 3,
    EvidenceLevel.ownership: 4,
    EvidenceLevel.production: 5,
    EvidenceLevel.outcome: 6,
}


def _evidence_sort_value(evidence: Evidence) -> Tuple[int, int, int]:
    return (_LEVEL_ORDER[evidence.level], int(evidence.quantified), -evidence.position)
