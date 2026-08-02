"""Language-aware, deterministic security evidence matching."""

from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass
from typing import Iterator, Sequence

from .models import (
    DimensionName,
    Evidence,
    EvidenceLevel,
    Experience,
    Resume,
    SecurityCategory,
    SecurityEnvironment,
    SourceKind,
)
from .security import is_instruction_like

DimensionConcepts = dict[str, dict[str, dict[str, tuple[str, ...]]]]

DIMENSION_CONCEPTS: DimensionConcepts = {
    "systems_network_security_foundation": {
        "operating_systems": {
            "operating_systems": ("linux", "unix", "进程", "线程", "文件系统", "内存管理"),
        },
        "network_http_tls": {
            "networking": ("tcp/ip", "tcp", "udp", "dns", "http", "https", "tls", "网络协议"),
        },
        "authentication_cryptography": {
            "authentication": ("authentication", "认证", "oauth", "oidc", "jwt"),
            "cryptography": ("cryptography", "密码学", "加密", "哈希", "数字签名", "pki"),
        },
        "database_storage": {
            "database": ("mysql", "postgresql", "redis", "数据库", "sql"),
            "storage": ("storage", "存储", "filesystem", "对象存储"),
        },
        "security_principles": {
            "security_principles": (
                "least privilege",
                "最小权限",
                "defense in depth",
                "纵深防御",
                "零信任",
                "threat model",
                "威胁建模",
            ),
        },
    },
    "programming_security_engineering_automation": {
        "programming": {
            "programming": (
                "python",
                "golang",
                "go",
                "java",
                "c++",
                "rust",
                "javascript",
                "typescript",
            ),
        },
        "scripting_tools": {
            "scripting": ("shell", "bash", "powershell", "脚本", "自动化"),
            "tooling": ("cli", "sdk", "api", "工具", "工具开发"),
        },
        "testing": {
            "testing": (
                "unit test",
                "integration test",
                "fuzz",
                "fuzzing",
                "单元测试",
                "集成测试",
                "模糊测试",
            ),
        },
        "devsecops": {
            "devsecops": (
                "devsecops",
                "ci/cd",
                "github actions",
                "gitlab ci",
                "sast",
                "dast",
                "iac scanning",
                "依赖扫描",
            ),
        },
        "data_processing": {
            "data_processing": ("etl", "数据清洗", "日志解析", "规则引擎", "pipeline"),
        },
        "security_tool_audit": {
            "tool_audit": ("code review", "代码审查", "安全工具评估", "规则验证", "误报分析"),
        },
    },
    "application_security_offensive": {
        "web_vulnerabilities": {
            "web_vulnerabilities": (
                "sql injection",
                "sqli",
                "xss",
                "ssrf",
                "csrf",
                "idor",
                "rce",
                "反序列化",
                "命令注入",
                "越权漏洞",
            ),
        },
        "code_audit": {
            "code_audit": ("code audit", "source code audit", "代码审计", "污点分析", "静态分析"),
        },
        "penetration_methodology": {
            "penetration": (
                "penetration test",
                "渗透测试",
                "attack surface",
                "攻击面",
                "资产测绘",
                "burp suite",
                "nmap",
            ),
        },
        "reproduction": {
            "reproduction": ("poc", "proof of concept", "漏洞复现", "复现漏洞", "exploit"),
        },
        "remediation_validation": {
            "remediation": ("修复验证", "修复建议", "回归测试", "remediation", "retest"),
        },
        "ctf_cve_bounty": {
            "ctf": ("ctf", "靶场"),
            "cve_bounty": ("cve", "bug bounty", "漏洞赏金", "漏洞披露", "cnvd", "cnnvd"),
        },
    },
    "detection_defense_incident_response": {
        "logs_siem": {
            "logs_siem": ("siem", "splunk", "elk", "日志分析", "日志检索", "安全日志"),
        },
        "network_endpoint_detection": {
            "network_detection": (
                "ids",
                "ips",
                "nids",
                "流量检测",
                "wireshark",
                "zeek",
                "suricata",
            ),
            "endpoint_detection": ("edr", "endpoint detection", "主机检测", "sysmon"),
        },
        "detection_rules": {
            "detection_rules": ("sigma", "yara", "snort rule", "检测规则", "告警规则", "关联规则"),
        },
        "incident_response": {
            "incident_response": (
                "incident response",
                "应急响应",
                "事件处置",
                "隔离",
                "遏制",
                "根因分析",
            ),
        },
        "threat_hunting": {
            "threat_hunting": ("threat hunting", "威胁狩猎", "ioc", "ttp", "attack mapping"),
        },
        "forensics": {
            "forensics": (
                "forensics",
                "取证",
                "memory forensics",
                "内存取证",
                "磁盘取证",
                "volatility",
            ),
        },
    },
    "cloud_identity_data_supply_chain": {
        "iam_secrets": {
            "iam": ("iam", "rbac", "abac", "identity", "身份治理", "权限治理"),
            "secrets": ("secret management", "密钥管理", "vault", "kms", "凭据轮换"),
        },
        "cloud_boundary": {
            "cloud_security": (
                "aws security",
                "azure security",
                "gcp security",
                "云安全",
                "安全组",
                "waf",
                "云防火墙",
            ),
        },
        "container_kubernetes": {
            "container_security": (
                "container security",
                "容器安全",
                "docker",
                "kubernetes",
                "k8s",
                "pod security",
            ),
        },
        "data_privacy": {
            "data_security": (
                "data security",
                "数据安全",
                "数据分类分级",
                "dlp",
                "privacy",
                "隐私保护",
                "脱敏",
            ),
        },
        "risk_standards": {
            "risk_standards": ("risk assessment", "风险评估", "iso 27001", "nist", "等保", "合规"),
        },
        "software_supply_chain": {
            "supply_chain": (
                "software supply chain",
                "软件供应链",
                "sbom",
                "slsa",
                "dependency scanning",
                "依赖漏洞",
            ),
        },
    },
    "ai_assisted_security_ai_system_security": {
        "ai_assisted_analysis": {
            "ai_assisted": (
                "chatgpt",
                "claude",
                "copilot",
                "cursor",
                "ai 辅助",
                "llm 辅助",
                "智能分析",
            ),
        },
        "llm_application_attack_surface": {
            "llm_security": (
                "prompt injection",
                "提示注入",
                "jailbreak",
                "越狱",
                "rag poisoning",
                "检索投毒",
                "llm security",
                "大模型安全",
            ),
        },
        "agent_permissions": {
            "agent_security": (
                "agent",
                "agent security",
                "agent 权限",
                "tool permission",
                "工具权限",
                "human approval",
                "人工确认",
            ),
        },
        "model_data_supply_chain": {
            "model_supply_chain": (
                "model supply chain",
                "模型供应链",
                "training data poisoning",
                "训练数据投毒",
                "模型签名",
            ),
        },
        "evaluation_red_team": {
            "ai_evaluation": (
                "llm evaluation",
                "模型评测",
                "红队评测",
                "adversarial testing",
                "对抗测试",
                "评测集",
            ),
        },
        "monitoring_fallback": {
            "ai_guardrails": (
                "guardrail",
                "护栏",
                "monitoring",
                "监控",
                "fallback",
                "降级",
                "rollback",
                "回滚",
                "sandbox",
                "隔离",
            ),
        },
    },
}

_SENTENCE = re.compile(r"[^\n。！？!?；;]+")
_CJK = re.compile(r"[\u3400-\u9fff]")
_QUANTIFIED = re.compile(r"\d+(?:\.\d+)?\s*(?:%|％|个|次|条|台|小时|天|ms|s|x|倍|万|qps)", re.I)
_ACTION = re.compile(
    r"使用|分析|检测|排查|验证|测试|复现|审计|处置|编写|研究|参与|\b(?:used?|analy[sz]ed?|detect(?:ed)?|test(?:ed)?|audit(?:ed)?|investigat(?:ed)?)\b",
    re.I,
)
_IMPLEMENT = re.compile(
    r"实现|开发|构建|部署|配置|编写|设计|搭建|集成|修复|\b(?:implement(?:ed)?|develop(?:ed)?|build|built|deploy(?:ed)?|configur(?:ed)?|design(?:ed)?|remediat(?:ed)?)\b",
    re.I,
)
_OWN = re.compile(r"主导|负责|独立完成|牵头|设计|\b(?:owned?|led|lead|designed?)\b", re.I)
_PRODUCTION = re.compile(
    r"生产|线上|真实业务|客户|用户|应急|\b(?:production|real[- ]world|customer|incident)\b", re.I
)
_OUTCOME = re.compile(
    r"提升|降低|减少|发现|阻断|修复|避免|\b(?:improved?|reduced?|found|blocked|fixed|prevented?)\b",
    re.I,
)
_NEGATION = re.compile(
    r"(?:不|未|无|没有|仅了解|学习中)[^，。;；\n]{0,16}$|\b(?:no experience|not familiar|never|without)\b[^.!?;]*$",
    re.I,
)
_UNAUTHORIZED = re.compile(
    r"未授权|未经授权|越权攻击|入侵他人|非法攻击|黑产|\b(?:unauthori[sz]ed|without permission|illegal hacking)\b",
    re.I,
)


def normalize_text(text: str) -> str:
    value = unicodedata.normalize("NFKC", text).lower()
    value = re.sub(r"[‐‑‒–—−]", "-", value)
    return re.sub(r"[\t\r ]+", " ", value).strip()


def term_pattern(term: str) -> re.Pattern[str]:
    term = normalize_text(term)
    escaped = re.escape(term).replace(r"\ ", r"\s+")
    if _CJK.search(term):
        return re.compile(escaped, re.I)
    return re.compile(r"(?<![A-Za-z0-9_])" + escaped + r"(?![A-Za-z0-9_])", re.I)


def is_quantified(text: str) -> bool:
    return bool(_QUANTIFIED.search(text))


def is_unauthorized(text: str) -> bool:
    return bool(_UNAUTHORIZED.search(normalize_text(text)))


def classify_evidence(text: str, mention_only: bool = False) -> EvidenceLevel:
    if mention_only:
        return EvidenceLevel.mention
    if is_quantified(text) and _OUTCOME.search(text):
        return EvidenceLevel.outcome
    if _PRODUCTION.search(text) and (_ACTION.search(text) or _IMPLEMENT.search(text)):
        return EvidenceLevel.production
    if _OWN.search(text):
        return EvidenceLevel.ownership
    if _IMPLEMENT.search(text):
        return EvidenceLevel.implementation
    if _ACTION.search(text):
        return EvidenceLevel.usage
    return EvidenceLevel.mention


@dataclass(frozen=True)
class TextRecord:
    source_kind: SourceKind
    source_id: str
    text: str
    mention_only: bool = False
    authorization: SecurityEnvironment | None = None


def iter_resume_records(resume: Resume) -> Iterator[TextRecord]:
    for group, values in sorted(resume.skills.model_dump(mode="python").items()):
        for value in values:
            yield TextRecord("skills", f"skills:{group}", value, True)
    collections: tuple[tuple[SourceKind, Sequence[Experience]], ...] = (
        ("internship", resume.internships),
        ("project", resume.projects),
        ("security_activity", resume.security_activities),
    )
    for kind, records in collections:
        for index, record in enumerate(records):
            source_id = f"{kind}:{index}"
            authorization = getattr(record, "environment", None)
            certification_only = (
                kind == "security_activity"
                and getattr(record, "category", None) is SecurityCategory.certification
            )
            if record.name:
                yield TextRecord(kind, source_id, record.name, True, authorization)
            if record.description:
                yield TextRecord(
                    kind, source_id, record.description, certification_only, authorization
                )
            for value in record.achievements:
                yield TextRecord(kind, source_id, value, certification_only, authorization)
            for value in record.tech_stack:
                yield TextRecord(kind, source_id, value, True, authorization)


def iter_sentences(text: str) -> Iterator[tuple[str, int]]:
    for match in _SENTENCE.finditer(text):
        value = match.group(0).strip(" ,，:\t")
        if value:
            yield value, match.start()


class EvidenceMatcher:
    def __init__(self, concepts: DimensionConcepts | None = None) -> None:
        self.concepts = concepts or DIMENSION_CONCEPTS

    def find_evidence(self, resume: Resume, dimension: DimensionName) -> list[Evidence]:
        lookup: dict[str, tuple[str, tuple[str, ...]]] = {}
        for group, concepts in self.concepts[dimension].items():
            for concept, variants in concepts.items():
                lookup[concept] = (group, variants)
        best: dict[tuple[str, str], Evidence] = {}
        for record in iter_resume_records(resume):
            for sentence, offset in iter_sentences(record.text):
                normalized = normalize_text(sentence)
                if is_instruction_like(sentence) or is_unauthorized(sentence):
                    continue
                for concept in sorted(lookup):
                    group, variants = lookup[concept]
                    positions = []
                    for variant in sorted(set(variants), key=lambda value: (-len(value), value)):
                        for match in term_pattern(variant).finditer(normalized):
                            prefix = normalized[max(0, match.start() - 48) : match.start()]
                            if not _NEGATION.search(prefix):
                                positions.append(match.start())
                    if not positions:
                        continue
                    item = Evidence(
                        dimension=dimension,
                        concept=concept,
                        evidence_group=group,
                        source_kind=record.source_kind,
                        source_id=record.source_id,
                        context=sentence,
                        level=classify_evidence(sentence, record.mention_only),
                        position=offset + min(positions),
                        quantified=is_quantified(sentence),
                        authorization=record.authorization,
                    )
                    key = (record.source_id, concept)
                    previous = best.get(key)
                    if previous is None or _strength(item) > _strength(previous):
                        best[key] = item
        order = {"skills": 0, "internship": 1, "project": 2, "security_activity": 3}
        return sorted(
            best.values(),
            key=lambda item: (order[item.source_kind], item.source_id, item.position, item.concept),
        )


_LEVEL = {
    EvidenceLevel.mention: 2,
    EvidenceLevel.usage: 4,
    EvidenceLevel.implementation: 6,
    EvidenceLevel.ownership: 8,
    EvidenceLevel.production: 9,
    EvidenceLevel.outcome: 9,
}


def _strength(item: Evidence) -> tuple[int, int, int]:
    return (_LEVEL[item.level], int(item.quantified), -item.position)


def unsafe_offensive_statements(resume: Resume) -> list[str]:
    warnings = []
    for record in iter_resume_records(resume):
        if is_unauthorized(record.text):
            warnings.append(f"unsafe_offensive_claim:{record.source_id}")
    return sorted(set(warnings))
