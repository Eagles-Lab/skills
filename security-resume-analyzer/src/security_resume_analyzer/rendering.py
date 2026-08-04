"""Strict Markdown rendering and deterministic security interview questions."""

from __future__ import annotations

import hashlib
import random
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping

from jinja2 import Environment, FileSystemLoader, PackageLoader, StrictUndefined, TemplateError

from .security import sanitize_included_contact_text, sanitize_report_text

DIMENSION_LABELS = {
    "systems_network_security_foundation": "系统、网络与安全基础",
    "programming_security_engineering_automation": "编程、安全工程与自动化",
    "vulnerability_research_security_assessment": "漏洞研究与安全评估实践",
    "detection_defense_incident_response": "检测、防御与应急响应",
    "cloud_identity_data_supply_chain": "云、身份、数据与供应链安全",
    "ai_assisted_security_ai_system_security": "AI 辅助安全与 AI 系统安全",
}
GROUP_LABELS = {
    "operating_systems": "操作系统",
    "network_http_tls": "网络/HTTP/TLS",
    "authentication_cryptography": "认证与密码学",
    "database_storage": "数据库与存储",
    "security_principles": "安全原则",
    "programming": "编程",
    "scripting_tools": "脚本与工具",
    "testing": "测试",
    "devsecops": "DevSecOps",
    "data_processing": "数据处理",
    "security_tool_audit": "安全工具审计",
    "web_vulnerabilities": "Web 漏洞",
    "code_audit": "代码审计",
    "binary_system_mobile_iot": "二进制/系统/移动与 IoT 安全",
    "penetration_methodology": "渗透方法",
    "reproduction": "漏洞复现",
    "remediation_validation": "修复验证",
    "ctf_cve_bounty": "CTF/CVE/赏金",
    "logs_siem": "日志与 SIEM",
    "network_endpoint_detection": "网络与端点检测",
    "detection_rules": "检测规则",
    "incident_response": "事件响应",
    "threat_hunting": "威胁狩猎",
    "forensics": "取证分析",
    "iam_secrets": "IAM 与密钥",
    "cloud_boundary": "云边界",
    "container_kubernetes": "容器/Kubernetes",
    "data_privacy": "数据与隐私",
    "risk_standards": "风险与标准",
    "software_supply_chain": "软件供应链",
    "ai_assisted_analysis": "AI 辅助分析",
    "llm_application_attack_surface": "LLM 应用攻击面",
    "agent_permissions": "Agent 权限",
    "model_data_supply_chain": "模型数据供应链",
    "evaluation_red_team": "评测红队",
    "monitoring_fallback": "监控降级",
}
SUGGESTIONS = {
    key: text
    for key, text in zip(
        DIMENSION_LABELS,
        (
            "结合实验或项目说明系统、协议、认证或安全原则如何影响判断。",
            "补充可运行代码、测试、失败处理、审查和自动化验证。",
            "明确授权范围，并按方法、复现、修复和复测形成闭环。",
            "说明日志/流量证据、检测逻辑、处置步骤和恢复验证。",
            "补充 IAM、云边界、数据或供应链控制的设计与验证。",
            "说明 AI 输入、人工确认、评测、权限隔离和降级边界。",
        ),
        strict=True,
    )
}

QUESTION_BANK = {
    "systems_network_security_foundation": [
        "TLS 握手失败如何分层定位？",
        "解释最小权限如何落地并验证。",
        "DNS 劫持有哪些证据与缓解方式？",
    ],
    "programming_security_engineering_automation": [
        "介绍一个安全工具的输入校验、测试和失败恢复。",
        "如何验证自动化扫描没有放大误报风险？",
        "代码审查如何识别并修复安全缺陷？",
    ],
    "vulnerability_research_security_assessment": [
        "请在明确授权边界后描述一次漏洞复现与修复复测。",
        "代码审计如何从入口追踪到危险汇点？",
        "二进制、移动或 IoT 漏洞研究中如何复现并控制影响？",
    ],
    "detection_defense_incident_response": [
        "设计一条检测规则并说明误报验证。",
        "按时间线描述一次事件响应与恢复确认。",
        "日志、流量和端点证据冲突时如何调查？",
    ],
    "cloud_identity_data_supply_chain": [
        "云 IAM 越权如何检测、止损和验证修复？",
        "Kubernetes 工作负载需要哪些安全边界？",
        "如何用 SBOM 与签名降低供应链风险？",
    ],
    "ai_assisted_security_ai_system_security": [
        "提示注入如何跨数据、工具和 Agent 权限传播？",
        "AI 辅助告警研判如何评测并保留人工确认？",
        "模型或 RAG 数据污染如何检测与降级？",
    ],
}


class RenderingError(RuntimeError):
    pass


@dataclass(frozen=True)
class RenderedReports:
    suggestions: str
    interview_questions: str


class ReportRenderer:
    def __init__(self, template_dir: Path | None = None) -> None:
        loader = (
            PackageLoader("security_resume_analyzer", "templates")
            if template_dir is None
            else FileSystemLoader(str(template_dir))
        )
        self.environment = Environment(
            loader=loader,
            undefined=StrictUndefined,
            autoescape=False,
            trim_blocks=True,
            lstrip_blocks=True,
            keep_trailing_newline=True,
        )  # nosec B701

    def render(
        self,
        resume: Any,
        score: Mapping[str, Any],
        *,
        analyzer_version: str,
        seed: str,
        include_contact: bool,
        security_warnings: list[str],
    ) -> RenderedReports:
        data = resume.model_dump(mode="json") if hasattr(resume, "model_dump") else dict(resume)
        basic = {
            key: sanitize_report_text(value) if value is not None else None
            for key, value in data["basic_info"].items()
            if key != "contact"
        }
        contact_data = data["basic_info"].get("contact")
        contact = (
            {
                key: sanitize_included_contact_text(value) if value else None
                for key, value in contact_data.items()
            }
            if include_contact and contact_data
            else None
        )
        dimensions = []
        for key, label in DIMENSION_LABELS.items():
            item = score["dimension_scores"][key]
            dimensions.append(
                {
                    "label": label,
                    "score": item["score"],
                    "weight_percent": round(item["weight"] * 100),
                    "depth_score": item["depth_score"],
                    "coverage_cap": item["coverage_cap"],
                    "applied_count": len(item["applied_evidence_groups"]),
                    "group_count": len(item["evidence_group_scores"]),
                    "applied_groups": [
                        GROUP_LABELS.get(value, value) for value in item["applied_evidence_groups"]
                    ],
                    "missing_groups": [
                        GROUP_LABELS.get(value, value) for value in item["missing_evidence_groups"]
                    ],
                    "evidence": _unique_contexts(item["evidence"]),
                    "suggestion": SUGGESTIONS[key],
                }
            )
        quality = score["resume_quality"]
        quality_labels = {
            "personal_contribution": "个人贡献",
            "authorization_scope": "授权范围",
            "methodology_process": "方法过程",
            "validation_remediation": "验证/修复结果",
            "clarity_consistency": "表述一致性",
        }
        common = {
            "scoring_profile": score["scoring_profile"],
            "analyzer_version": analyzer_version,
            "security_warnings": security_warnings,
        }
        try:
            suggestions = self.environment.get_template("suggestions_template.md").render(
                **common,
                basic_info=basic,
                contact=contact,
                total_score=score["total_score"],
                grade=score["grade"],
                dimensions=dimensions,
                quality_items=[
                    {
                        "label": quality_labels[key],
                        "score": value,
                        "finding": sanitize_report_text(quality["findings"][key]),
                    }
                    for key, value in quality["breakdown"].items()
                ],
            )
            questions = self.environment.get_template("interview_questions_template.md").render(
                **common,
                questions=self._questions(score, seed),
            )
        except TemplateError as exc:
            raise RenderingError(
                f"security report template rendering failed: {type(exc).__name__}"
            ) from exc
        return RenderedReports(suggestions, questions)

    def _questions(self, score: Mapping[str, Any], seed: str) -> list[dict[str, Any]]:
        rng = random.Random(int.from_bytes(hashlib.sha256(seed.encode()).digest()[:8], "big"))
        dimensions = sorted(
            DIMENSION_LABELS, key=lambda key: (score["dimension_scores"][key]["score"], key)
        )
        required = (
            "systems_network_security_foundation",
            "programming_security_engineering_automation",
            "vulnerability_research_security_assessment",
            "ai_assisted_security_ai_system_security",
        )
        selected = [(DIMENSION_LABELS[key], rng.choice(QUESTION_BANK[key])) for key in required]
        pool = [
            (key, DIMENSION_LABELS[key], question)
            for key in dimensions
            for question in QUESTION_BANK[key]
            if (DIMENSION_LABELS[key], question) not in selected
        ]
        rng.shuffle(pool)
        priority = {key: index for index, key in enumerate(dimensions)}
        pool.sort(key=lambda item: priority[item[0]])
        selected.extend((label, question) for _, label, question in pool[:5])
        selected.append(("综合", "选择一个项目，区分个人贡献、方法、验证和结果。"))
        rng.shuffle(selected)
        return [
            {"id": index, "category": category, "question": question}
            for index, (category, question) in enumerate(selected, 1)
        ]


def _unique_contexts(evidence: list[Mapping[str, Any]]) -> list[str]:
    values = []
    for item in evidence:
        context = sanitize_report_text(item.get("context", ""))
        if context and context not in values:
            values.append(context)
    return values
