"""Strict Markdown rendering and deterministic development interview questions."""

from __future__ import annotations

import hashlib
import random
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping

from jinja2 import Environment, FileSystemLoader, PackageLoader, StrictUndefined, TemplateError

from .security import sanitize_included_contact_text, sanitize_report_text

DIMENSION_LABELS = {
    "computer_science_software_foundation": "计算机与软件基础",
    "programming_code_quality": "编程实现与代码质量",
    "application_development_architecture": "应用开发与架构设计",
    "debugging_performance_problem_solving": "排障、性能与问题解决",
    "engineering_delivery_collaboration": "工程交付与协作",
    "ai_assisted_development_ai_engineering": "AI 辅助开发与 AI 应用工程",
}
GROUP_LABELS = {
    "data_structures_algorithms": "数据结构与算法",
    "operating_systems_concurrency": "操作系统与并发",
    "network_web_protocols": "网络与 Web 协议",
    "database_storage": "数据库与存储",
    "language_runtime": "语言运行时",
    "implementation": "实际编码",
    "abstraction_design": "抽象与设计",
    "api_contracts": "API 与契约",
    "error_handling_reliability": "异常处理与可靠性",
    "maintainability_refactoring": "可维护性与重构",
    "code_review_static_analysis": "代码审查与静态检查",
    "frontend_client": "前端与客户端",
    "backend_services": "后端服务",
    "data_modeling": "数据建模",
    "integration_distributed": "系统集成与分布式",
    "security_authentication": "安全与鉴权",
    "product_user_loop": "用户与业务闭环",
    "problem_decomposition": "问题拆解",
    "logs_debugging": "日志与调试",
    "root_cause_analysis": "根因定位",
    "profiling_performance": "性能分析",
    "experimentation_validation": "实验验证",
    "remediation_regression": "修复与回归",
    "testing": "测试",
    "version_control_collaboration": "版本控制与代码协作",
    "build_cicd": "构建与 CI/CD",
    "deployment_environment": "部署与环境",
    "documentation_observability": "文档与可观测性",
    "team_open_source": "团队与开源贡献",
    "ai_coding_assistance": "AI 编码辅助",
    "ai_testing_debugging": "AI 测试与调试",
    "llm_rag_application": "LLM/RAG 应用",
    "agent_tool_workflow": "Agent 与工具工作流",
    "evaluation": "评测",
    "controls_fallback": "权限、安全与降级",
}
SUGGESTIONS = {
    key: text
    for key, text in zip(
        DIMENSION_LABELS,
        (
            "结合课程或项目说明算法、系统、网络、数据库或运行时原理如何影响实现。",
            "补充关键代码、接口契约、失败处理、重构与代码质量验证。",
            "说明模块边界、数据模型、架构取舍、安全约束和面向用户的交付结果。",
            "按现象、假设、调试证据、根因、修复和回归验证描述问题解决过程。",
            "补充测试、版本协作、构建发布、环境管理、文档与可观测性证据。",
            "说明 AI 输入、人工验证、评测方法、权限边界以及失败时的降级策略。",
        ),
        strict=True,
    )
}

QUESTION_BANK = {
    "computer_science_software_foundation": [
        "一个 HTTP 请求从客户端到服务端会经过哪些关键步骤？",
        "线程、协程和进程分别适合什么场景，常见并发问题是什么？",
        "数据库索引为什么能加速查询，哪些情况下反而无效？",
        "请分析一个常用算法的时间和空间复杂度，并说明工程取舍。",
    ],
    "programming_code_quality": [
        "选择一段核心实现，说明模块边界、接口契约和异常处理。",
        "你如何判断一次重构没有改变外部行为？",
        "如何设计一个可重试且保持幂等的接口？",
        "代码审查和静态检查分别能发现哪些质量问题？",
    ],
    "application_development_architecture": [
        "选择一个项目，画出主要组件、数据流和关键技术取舍。",
        "前后端或客户端与服务端的状态一致性如何保证？",
        "用户量增长十倍后，当前架构最先出现的瓶颈可能是什么？",
        "项目中的认证、鉴权和敏感数据边界如何设计？",
    ],
    "debugging_performance_problem_solving": [
        "描述一次问题定位：现象、假设、证据、根因、修复和回归验证分别是什么？",
        "接口延迟突然升高时，如何设计逐层排查实验？",
        "如何用 profiler、日志或指标证明性能优化确实有效？",
        "无法稳定复现的缺陷应如何缩小范围并保留证据？",
    ],
    "engineering_delivery_collaboration": [
        "项目的单元、集成和端到端测试如何分工？",
        "从提交代码到发布上线，流水线有哪些质量 Gate？",
        "多人协作时如何拆分变更并控制合并风险？",
        "如何通过日志、指标、文档和回滚方案提高可维护性？",
    ],
    "ai_assisted_development_ai_engineering": [
        "使用 AI 生成代码时，如何验证正确性、安全性和可维护性？",
        "设计一个 RAG 或 Agent 应用，并说明数据流、评测和失败降级。",
        "AI 辅助调试给出错误结论时，如何通过实验确认根因？",
        "Agent 获得工具权限后，如何限制越权调用并保留人工确认？",
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
            PackageLoader("development_resume_analyzer", "templates")
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
            "factual_completeness": "事实与项目完整性",
            "personal_contribution": "个人贡献",
            "technical_detail_tradeoffs": "技术细节与取舍",
            "validation_results": "验证与结果",
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
                f"development report template rendering failed: {type(exc).__name__}"
            ) from exc
        return RenderedReports(suggestions, questions)

    def _questions(self, score: Mapping[str, Any], seed: str) -> list[dict[str, Any]]:
        rng = random.Random(int.from_bytes(hashlib.sha256(seed.encode()).digest()[:8], "big"))
        dimensions = sorted(
            DIMENSION_LABELS, key=lambda key: (score["dimension_scores"][key]["score"], key)
        )
        selected = [
            (DIMENSION_LABELS[key], rng.choice(QUESTION_BANK[key])) for key in DIMENSION_LABELS
        ]
        pool = [
            (key, DIMENSION_LABELS[key], question)
            for key in dimensions
            for question in QUESTION_BANK[key]
            if (DIMENSION_LABELS[key], question) not in selected
        ]
        rng.shuffle(pool)
        priority = {key: index for index, key in enumerate(dimensions)}
        pool.sort(key=lambda item: priority[item[0]])
        selected.extend((label, question) for _, label, question in pool[:3])
        selected.append(("综合", "选择一个项目，区分个人贡献、技术取舍、验证方法和结果。"))
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
