"""Deterministic Markdown rendering for campus SRE reports."""
# ruff: noqa: RUF001

from __future__ import annotations

import hashlib
import json
import random
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Mapping, Optional, Sequence

from jinja2 import Environment, FileSystemLoader, PackageLoader, StrictUndefined, TemplateError

from .security import (
    sanitize_included_contact_text,
    sanitize_report_list,
    sanitize_report_text,
)

MISSING_DISPLAY = "未提供或未可靠识别，请后续补充。"

DIMENSION_LABELS = {
    "systems_network_foundation": "计算机系统与网络基础",
    "programming_automation": "编程与自动化工程",
    "troubleshooting": "故障分析与问题解决",
    "cloud_distributed_infrastructure": "云基础设施与分布式系统",
    "reliability_engineering": "可靠性工程实践",
    "ai_engineering_aiops": "AI 辅助工程与 AIOps 实践",
}

IMPROVEMENT_SUGGESTIONS = {
    "systems_network_foundation": (
        "结合课程实验或项目说明 Linux、网络、并发、存储等基础原理如何用于实际判断。"
    ),
    "programming_automation": "补充可运行代码、测试、自动化边界、失败处理和验证结果。",
    "troubleshooting": "按现象、假设、证据、根因、修复与回归验证描述一次排障。",
    "cloud_distributed_infrastructure": "说明容器、云或分布式组件的设计取舍、部署过程和故障验证。",
    "reliability_engineering": "补充监控告警、SLI/SLO、容量、容灾或复盘的具体实践与结果。",
    "ai_engineering_aiops": (
        "说明 AI 在编码或运维流程中的输入、评测、人工确认、安全边界和降级方案。"
    ),
}

QUESTION_BANK = {
    "systems_network_foundation": [
        "TCP 连接建立后服务仍超时，你会从哪些系统和网络证据开始排查？",
        "进程、线程与协程有什么差异？请结合一个项目说明你的选择。",
        "DNS 解析异常可能出现在哪些层次？你会如何逐层验证？",
        "请解释一次你用操作系统或数据结构知识解决实际问题的经历。",
    ],
    "programming_automation": [
        "请介绍一个你实现的自动化工具，并说明输入校验、测试和失败恢复。",
        "如何判断一项重复工作值得自动化？如何验证自动化没有放大风险？",
        "请说明你最熟悉语言中的并发、错误处理和可测试性设计。",
        "CI/CD 变更如何做到可审查、可回滚和结果可验证？",
    ],
    "troubleshooting": [
        "请按时间线描述一次排障，区分现象、假设、证据和根因。",
        "日志、指标和调用链结论冲突时，你如何设计下一步实验？",
        "如何证明故障已经真正恢复，而不是指标暂时回落？",
        "面对完全陌生的系统，你会如何建立最小排障路径？",
    ],
    "cloud_distributed_infrastructure": [
        "请描述一次容器或 Kubernetes 工作负载异常的定位过程。",
        "分布式系统中超时、重试和幂等应如何共同设计？",
        "如何为服务设置资源请求、限制和扩缩容策略并验证？",
        "请说明一个云基础设施设计中的取舍及失败场景。",
    ],
    "reliability_engineering": [
        "如何从用户体验定义 SLI，并把它映射到 SLO 和告警？",
        "遇到告警风暴时，你会如何止损并验证降噪效果？",
        "一次故障复盘如何形成可追踪、可验证的改进项？",
        "请设计一次容量或容灾演练，并说明成功判据。",
    ],
    "ai_engineering_aiops": [
        "你如何验证 AI 生成的代码、测试或排障建议，而不是直接信任结果？",
        "请设计一个告警摘要或自动诊断流程，说明评测集和人工确认点。",
        "RAG 或 Agent 接入运维数据时，权限、脱敏和提示注入如何处理？",
        "AI 服务不可用或输出低置信度时，系统如何降级或回滚？",
    ],
}

GENERAL_QUESTIONS = [
    "请介绍一个你最有把握的项目，明确个人职责、关键决策和验证结果。",
    "当信息不完整时，你如何组织一次线上问题调查？",
    "请举例说明你如何在交付速度与系统可靠性之间做取舍。",
    "最近一次技术判断失误是什么？你如何发现并纠正它？",
    "课程项目与真实环境有哪些差异？你会如何补齐验证？",
    "请区分你了解、实际使用和独立负责的技术，并分别给出证据。",
]


class RenderingError(RuntimeError):
    """A report template could not be rendered."""


@dataclass(frozen=True)
class RenderedReports:
    suggestions: str
    interview_questions: str


def _to_mapping(value: Any) -> Dict[str, Any]:
    if hasattr(value, "model_dump"):
        return dict(value.model_dump(mode="json"))
    if isinstance(value, Mapping):
        return dict(value)
    raise TypeError(f"expected a model or mapping, got {type(value).__name__}")


def _display(value: Any) -> str:
    return sanitize_report_text(value) if value not in (None, "") else MISSING_DISPLAY


def _evidence_text(item: Mapping[str, Any]) -> str:
    for key in ("context", "description", "keyword"):
        if item.get(key):
            return sanitize_report_text(item[key])
    return "已识别到结构化证据。"


def _evidence_level(score: float) -> str:
    if score >= 10:
        return "多来源强证据"
    if score >= 9:
        return "真实环境或同源结果"
    if score >= 8:
        return "完整项目与验证"
    if score >= 6:
        return "可运行实现"
    if score >= 4:
        return "实际使用"
    if score >= 2:
        return "课程、技能或工具提及"
    return "未识别到相关证据"


class ReportRenderer:
    """Render strict, deterministic Markdown view models."""

    def __init__(self, template_dir: Optional[Path] = None) -> None:
        loader = (
            PackageLoader("sre_resume_analyzer", "templates")
            if template_dir is None
            else FileSystemLoader(str(Path(template_dir)))
        )
        self.environment = Environment(  # nosec B701
            loader=loader,
            undefined=StrictUndefined,
            autoescape=False,
            keep_trailing_newline=True,
            trim_blocks=True,
            lstrip_blocks=True,
        )

    def render(
        self,
        resume: Any,
        score: Any,
        analysis: Mapping[str, Any],
        *,
        resume_id: str,
        output_name: str,
        generated_at: str,
        analyzer_version: str,
        input_sha256: str,
        seed: Optional[str] = None,
        include_contact: bool = False,
    ) -> RenderedReports:
        del resume_id, output_name
        resume_data = _to_mapping(resume)
        score_data = _to_mapping(score)
        context = self._suggestions_context(
            resume_data,
            score_data,
            analysis,
            generated_at=generated_at,
            analyzer_version=analyzer_version,
            include_contact=include_contact,
        )
        question_context = {
            "basic_info": self._safe_basic_info(resume_data["basic_info"]),
            "generated_at": generated_at,
            "analyzer_version": analyzer_version,
            "contact": self._safe_contact(resume_data["basic_info"].get("contact"))
            if include_contact
            else None,
            "questions": self._build_questions(
                resume_data,
                score_data,
                seed=seed if seed is not None else input_sha256,
            ),
            "focus_areas": self._focus_areas(score_data),
            "security_warnings": list(analysis.get("security_warnings", [])),
        }
        try:
            suggestions = self.environment.get_template("suggestions_template.md").render(**context)
            interview = self.environment.get_template("interview_questions_template.md").render(
                **question_context
            )
        except TemplateError as exc:
            raise RenderingError(f"report template rendering failed: {exc}") from exc
        return RenderedReports(suggestions=suggestions, interview_questions=interview)

    def _suggestions_context(
        self,
        resume: Mapping[str, Any],
        score: Mapping[str, Any],
        analysis: Mapping[str, Any],
        *,
        generated_at: str,
        analyzer_version: str,
        include_contact: bool,
    ) -> Dict[str, Any]:
        raw_dimensions = score.get("dimension_scores", {})
        dimensions = []
        for name in DIMENSION_LABELS:
            info = dict(raw_dimensions.get(name, {}))
            numeric_score = float(info.get("score", 1.0))
            dimensions.append(
                {
                    "label": DIMENSION_LABELS[name],
                    "score": numeric_score,
                    "weight_percent": round(float(info.get("weight", 0)) * 100),
                    "evidence_level": _evidence_level(numeric_score),
                    "evidence": [
                        _evidence_text(item)
                        for item in info.get("evidence", [])
                        if isinstance(item, Mapping)
                    ],
                    "suggestion": IMPROVEMENT_SUGGESTIONS[name],
                }
            )
        quality = dict(score.get("resume_quality", {}))
        breakdown = quality.get("breakdown", {})
        findings = quality.get("findings", {})
        quality_items = [
            {
                "label": label,
                "score": float(breakdown.get(key, 0.0)),
                "finding": sanitize_report_text(findings.get(key, MISSING_DISPLAY)),
            }
            for key, label in (
                ("completeness", "信息完整性"),
                ("action_result", "STAR/行动描述"),
                ("quantified_results", "量化结果质量"),
                ("clarity", "表达清晰度"),
                ("timeline_technical_consistency", "时间线与技术表述一致性"),
            )
        ]
        return {
            "basic_info": self._safe_basic_info(resume["basic_info"]),
            "generated_at": generated_at,
            "analyzer_version": analyzer_version,
            "contact": self._safe_contact(resume["basic_info"].get("contact"))
            if include_contact
            else None,
            "total_score": score.get("total_score", 1.0),
            "grade": score.get("grade", {}),
            "dimensions": dimensions,
            "resume_quality_score": quality.get("score", 1.0),
            "quality_items": quality_items,
            "strengths": self._safe_analysis_items(analysis.get("strengths", [])),
            "weaknesses": self._safe_analysis_items(analysis.get("weaknesses", [])),
            "project_suggestions": self._project_suggestions(resume),
            "data_quality_warnings": [
                {
                    "path": sanitize_report_text(item.get("path", "")),
                    "message": sanitize_report_text(item.get("message", MISSING_DISPLAY)),
                }
                for item in analysis.get("data_quality_warnings", [])
                if isinstance(item, Mapping)
            ],
            "status_notice": "本报告衡量国内实习/校招 SRE 简历的证据覆盖度，不能单独用于招聘决策。",
            "security_warnings": list(analysis.get("security_warnings", [])),
        }

    @staticmethod
    def _safe_basic_info(value: Mapping[str, Any]) -> Dict[str, Any]:
        return {
            "name": _display(value.get("name")),
            "school": _display(value.get("school")),
            "major": _display(value.get("major")),
            "degree": _display(value.get("degree")),
            "graduation_year": value.get("graduation_year") or MISSING_DISPLAY,
        }

    @staticmethod
    def _safe_contact(value: Any) -> Optional[Dict[str, str]]:
        if not isinstance(value, Mapping):
            return None
        return {
            "email": sanitize_included_contact_text(value.get("email"))
            if value.get("email")
            else MISSING_DISPLAY,
            "phone": sanitize_included_contact_text(value.get("phone"))
            if value.get("phone")
            else MISSING_DISPLAY,
        }

    @staticmethod
    def _safe_analysis_items(values: Any) -> List[Dict[str, str]]:
        if not isinstance(values, Sequence) or isinstance(values, (str, bytes)):
            return []
        return [
            {
                "label": sanitize_report_text(item.get("label", "")),
                "summary": sanitize_report_text(item.get("summary", "")),
            }
            for item in values
            if isinstance(item, Mapping)
        ]

    def _project_suggestions(self, resume: Mapping[str, Any]) -> List[str]:
        projects = list(resume.get("projects", []))
        if not projects:
            return ["补充至少一个能够说明个人职责、实施过程和验证结果的项目。"]
        suggestions = []
        for project in projects:
            name = _display(project.get("name"))
            if not project.get("achievements"):
                suggestions.append(f"{name}：补充可验证的结果或运行指标。")
            if not project.get("role"):
                suggestions.append(f"{name}：明确个人角色和责任边界。")
        return suggestions or ["项目描述已包含角色和结果；继续补充规模与验证方式。"]

    def _focus_areas(self, score: Mapping[str, Any]) -> List[str]:
        dimensions = score.get("dimension_scores", {})
        ordered = sorted(
            dimensions.items(),
            key=lambda item: (float(item[1].get("score", 1.0)), item[0]),
        )
        return [DIMENSION_LABELS.get(name, name) for name, _ in ordered[:3]]

    def _build_questions(
        self,
        resume: Mapping[str, Any],
        score: Mapping[str, Any],
        *,
        seed: str,
    ) -> List[Dict[str, Any]]:
        canonical_seed = hashlib.sha256(str(seed).encode("utf-8")).digest()
        rng = random.Random(int.from_bytes(canonical_seed[:8], "big"))
        candidates: List[Dict[str, Any]] = []
        for internship in resume.get("internships", []):
            company = _display(internship.get("company"))
            candidates.append(
                {
                    "category": "实习经历",
                    "question": f"请说明你在{company}承担的具体责任、排障过程和验证结果。",
                    "context": _display(internship.get("description")),
                    "expected_keywords": sanitize_report_list(internship.get("tech_stack", [])),
                }
            )
        for project in resume.get("projects", []):
            name = _display(project.get("name"))
            candidates.extend(
                [
                    {
                        "category": "项目经历",
                        "question": f"请说明{name}中你的角色、关键决策和责任边界。",
                        "context": _display(project.get("description")),
                        "expected_keywords": sanitize_report_list(project.get("tech_stack", [])),
                    },
                    {
                        "category": "项目经历",
                        "question": f"如果重新实现{name}，你会改变什么？如何验证改进有效？",
                        "context": _display(project.get("description")),
                        "expected_keywords": sanitize_report_list(project.get("achievements", [])),
                    },
                ]
            )
        dimensions = score.get("dimension_scores", {})
        ordered_dimensions = sorted(
            DIMENSION_LABELS,
            key=lambda name: (float(dimensions.get(name, {}).get("score", 1.0)), name),
        )
        for dimension in ordered_dimensions:
            bank = list(QUESTION_BANK[dimension])
            rng.shuffle(bank)
            dimension_score = float(dimensions.get(dimension, {}).get("score", 1.0))
            candidates.extend(
                {
                    "category": DIMENSION_LABELS[dimension],
                    "question": question,
                    "context": f"该维度证据等级：{_evidence_level(dimension_score)}",
                    "expected_keywords": [],
                }
                for question in bank
            )
        general = list(GENERAL_QUESTIONS)
        rng.shuffle(general)
        candidates.extend(
            {"category": "综合能力", "question": question, "context": "", "expected_keywords": []}
            for question in general
        )
        rng.shuffle(candidates)
        selected: List[Dict[str, Any]] = []
        seen = set()
        for candidate in candidates:
            if candidate["question"] in seen:
                continue
            seen.add(candidate["question"])
            item = dict(candidate)
            item["id"] = len(selected) + 1
            item["difficulty"] = "校招"
            item["answer_guidance"] = "说明情境、个人行动、验证方式和可归因结果；不了解时明确边界。"
            selected.append(item)
            if len(selected) == 10:
                break
        return selected


def stable_render_fingerprint(reports: RenderedReports) -> str:
    payload = json.dumps(
        {"suggestions": reports.suggestions, "interview_questions": reports.interview_questions},
        ensure_ascii=False,
        sort_keys=True,
    )
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()
