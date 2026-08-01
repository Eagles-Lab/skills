"""Deterministic Markdown rendering for analyzer reports."""
# ruff: noqa: RUF001

from __future__ import annotations

import hashlib
import json
import random
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Mapping, Optional, Sequence

from jinja2 import Environment, FileSystemLoader, PackageLoader, StrictUndefined, TemplateError

from .security import sanitize_report_list, sanitize_report_text

DIMENSION_LABELS = {
    "monitoring": "监控相关经验",
    "alerting": "告警设计能力",
    "automation": "自动化能力",
    "containerization": "容器化/云原生",
    "incident_handling": "故障处理经验",
    "resume_quality": "简历整体质量",
}

IMPROVEMENT_SUGGESTIONS = {
    "monitoring": "补充监控指标、SLI/SLO、仪表盘以及生产规模的具体证据。",
    "alerting": "说明告警分级、降噪、值班响应和 Runbook 的设计与效果。",
    "automation": "补充脚本、CI/CD 或 IaC 的实现范围以及可量化结果。",
    "containerization": "说明容器平台的设计、部署、排障和生产运维责任。",
    "incident_handling": "使用时间线描述故障发现、止损、根因和复盘改进。",
    "resume_quality": "用行动、范围和结果重写薄弱经历，避免只罗列工具名。",
}

QUESTION_BANK = {
    "monitoring": [
        "请基于一次实际经历说明你如何选择 SLI，并将它映射到 SLO。",
        "你如何验证监控指标能够在用户受影响前发现异常？",
        "请说明一个仪表盘从需求、实现到持续维护的完整过程。",
    ],
    "alerting": [
        "请说明你如何设计告警分级、去重和升级策略。",
        "遇到告警风暴时，你会如何止损并验证降噪效果？",
        "一个可执行的 Runbook 应包含哪些信息？请结合实际案例回答。",
    ],
    "automation": [
        "请介绍一个你亲自实现的自动化流程，以及失败回滚机制。",
        "你如何测试 IaC 或 CI/CD 变更，避免把错误带入生产？",
        "请说明一个自动化项目的投入、覆盖范围和量化收益。",
    ],
    "containerization": [
        "请描述一次 Kubernetes 工作负载异常的定位过程。",
        "如何为容器化服务设计资源请求、限制和扩缩容策略？",
        "请说明一次云原生平台设计中的取舍以及验证方式。",
    ],
    "incident_handling": [
        "请按时间线描述一次故障处理，并区分现象、根因和修复。",
        "如何判断故障已经真正恢复，而不是指标暂时回落？",
        "复盘中的改进项如何跟踪到完成并验证有效性？",
    ],
    "resume_quality": [
        "请选择一段经历，用 STAR 方法补充你的个人行动和结果。",
        "简历中的量化结果如何采集，怎样证明它可归因于你的工作？",
        "请区分你了解、参与和主导的技术，并分别给出证据。",
    ],
}

GENERAL_QUESTIONS = [
    "请介绍一个你最有把握的 SRE 项目，明确你的个人职责和交付结果。",
    "当信息不完整时，你如何组织一次线上问题调查？",
    "请举例说明你如何在交付速度与系统可靠性之间做取舍。",
    "你如何验证一个可靠性改进在长期运行中仍然有效？",
    "最近一次技术判断失误是什么？你如何发现并纠正它？",
    "请说明你如何与开发团队共同定义并落实可靠性目标。",
    "如何判断一项重复工作值得自动化？",
    "如果入职后只能先改善一个可靠性问题，你会如何选择？",
    "请描述你如何把一次故障经验沉淀为团队能力。",
    "面对未知系统，你会如何建立可观测性和排障基线？",
]


class RenderingError(RuntimeError):
    """A report template could not be rendered."""


@dataclass(frozen=True)
class RenderedReports:
    """The two Markdown artifacts produced for one analysis."""

    suggestions: str
    interview_questions: str


def _to_mapping(value: Any) -> Dict[str, Any]:
    if hasattr(value, "model_dump"):
        dumped = value.model_dump(mode="json")
        return dict(dumped)
    if isinstance(value, Mapping):
        return dict(value)
    raise TypeError(f"expected a model or mapping, got {type(value).__name__}")


def _grade_for_dimension(score: float) -> str:
    if score >= 9:
        return "A"
    if score >= 7:
        return "B"
    if score >= 5:
        return "C"
    if score >= 3:
        return "D"
    return "F"


def _evidence_text(item: Mapping[str, Any]) -> str:
    for key in ("text", "context", "description", "keyword"):
        value = item.get(key)
        if value:
            return sanitize_report_text(value)
    return "已识别到结构化证据"


class ReportRenderer:
    """Render report templates with strict, deterministic inputs."""

    def __init__(self, template_dir: Optional[Path] = None) -> None:
        loader = (
            PackageLoader("sre_resume_analyzer", "templates")
            if template_dir is None
            else FileSystemLoader(str(Path(template_dir)))
        )
        # The templates render Markdown files only; HTML autoescape would corrupt evidence text.
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
        generated_at: str,
        analyzer_version: str,
        input_sha256: str,
        seed: Optional[str] = None,
        include_contact: bool = False,
    ) -> RenderedReports:
        resume_data = _to_mapping(resume)
        score_data = _to_mapping(score)
        context = self._suggestions_context(
            resume_data,
            score_data,
            analysis,
            resume_id=resume_id,
            generated_at=generated_at,
            analyzer_version=analyzer_version,
            include_contact=include_contact,
        )
        questions = self._build_questions(
            resume_data,
            score_data,
            seed=seed if seed is not None else input_sha256,
        )
        question_context = {
            "basic_info": self._safe_basic_info(resume_data["basic_info"]),
            "resume_id": resume_id,
            "generated_at": generated_at,
            "analyzer_version": analyzer_version,
            "contact": self._safe_contact(resume_data["basic_info"].get("contact"))
            if include_contact
            else None,
            "questions": questions,
            "focus_areas": self._focus_areas(score_data),
            "security_warnings": list(analysis.get("warnings", [])),
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
        resume_id: str,
        generated_at: str,
        analyzer_version: str,
        include_contact: bool,
    ) -> Dict[str, Any]:
        dimensions = []
        raw_dimensions = score.get("dimension_scores", {})
        for name in DIMENSION_LABELS:
            info = dict(raw_dimensions.get(name, {}))
            numeric_score = float(info.get("score", 1.0))
            evidence = [
                _evidence_text(item)
                for item in info.get("evidence", [])
                if isinstance(item, Mapping)
            ]
            dimensions.append(
                {
                    "name": name,
                    "label": DIMENSION_LABELS[name],
                    "score": numeric_score,
                    "weight_percent": round(float(info.get("weight", 0)) * 100),
                    "grade": _grade_for_dimension(numeric_score),
                    "evidence": evidence,
                    "suggestion": IMPROVEMENT_SUGGESTIONS[name],
                }
            )

        ai_bonus = dict(score.get("ai_bonus", {}))
        applications = ai_bonus.get("applications", {})
        if isinstance(applications, Mapping):
            application_names = sorted(str(key) for key in applications)
        elif isinstance(applications, Sequence) and not isinstance(applications, str):
            application_names = sorted(str(item) for item in applications)
        else:
            application_names = []

        return {
            "basic_info": self._safe_basic_info(resume["basic_info"]),
            "resume_id": resume_id,
            "generated_at": generated_at,
            "analyzer_version": analyzer_version,
            "contact": self._safe_contact(resume["basic_info"].get("contact"))
            if include_contact
            else None,
            "total_score": score.get("total_score", 1.0),
            "base_score": score.get("base_score", 1.0),
            "grade": score.get("grade", {}),
            "ai_bonus_score": ai_bonus.get("score", 0.0),
            "ai_applications": application_names,
            "dimensions": dimensions,
            "strengths": self._safe_analysis_items(analysis.get("strengths", [])),
            "weaknesses": self._safe_analysis_items(analysis.get("weaknesses", [])),
            "project_suggestions": self._project_suggestions(resume),
            "status_notice": "本报告衡量简历中的证据覆盖度，不能单独用于招聘决策。",
            "security_warnings": list(analysis.get("warnings", [])),
        }

    @staticmethod
    def _safe_basic_info(value: Mapping[str, Any]) -> Dict[str, Any]:
        return {
            "name": sanitize_report_text(value.get("name", "")),
            "school": sanitize_report_text(value.get("school", "")),
            "major": sanitize_report_text(value.get("major", "")),
            "degree": sanitize_report_text(value.get("degree", "")),
            "graduation_year": value.get("graduation_year", ""),
        }

    @staticmethod
    def _safe_contact(value: Any) -> Optional[Dict[str, str]]:
        if not isinstance(value, Mapping):
            return None
        return {
            "email": sanitize_report_text(value.get("email", "")),
            "phone": sanitize_report_text(value.get("phone", "")),
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
            return ["补充至少一个能够说明个人职责、实施过程和结果的 SRE 项目。"]
        suggestions = []
        for project in projects:
            name = sanitize_report_text(project.get("name", "未命名项目"))
            achievements = project.get("achievements", [])
            if not achievements:
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
            company = sanitize_report_text(internship.get("company", "该公司"))
            role = sanitize_report_text(internship.get("role", "该岗位"))
            candidates.extend(
                [
                    {
                        "category": "实习经历",
                        "question": f"请说明你在{company}担任{role}期间承担的具体责任。",
                        "context": sanitize_report_text(internship.get("description", "")),
                        "expected_keywords": sanitize_report_list(internship.get("tech_stack", [])),
                    },
                    {
                        "category": "实习经历",
                        "question": f"请描述你在{company}遇到的一次可靠性问题及验证结果。",
                        "context": sanitize_report_text(internship.get("description", "")),
                        "expected_keywords": sanitize_report_list(
                            internship.get("achievements", [])
                        ),
                    },
                ]
            )

        for project in resume.get("projects", []):
            name = sanitize_report_text(project.get("name", "该项目"))
            candidates.extend(
                [
                    {
                        "category": "项目经历",
                        "question": f"请说明{name}中你的角色、关键决策和责任边界。",
                        "context": sanitize_report_text(project.get("description", "")),
                        "expected_keywords": sanitize_report_list(project.get("tech_stack", [])),
                    },
                    {
                        "category": "项目经历",
                        "question": f"如果重新实现{name}，你会改变什么？如何验证改进有效？",
                        "context": sanitize_report_text(project.get("description", "")),
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
            dimension_score = dimensions.get(dimension, {}).get("score", 1.0)
            candidates.extend(
                {
                    "category": DIMENSION_LABELS[dimension],
                    "question": question,
                    "context": f"该维度简历证据得分：{dimension_score}/10",
                    "expected_keywords": [],
                }
                for question in bank
            )

        general = list(GENERAL_QUESTIONS)
        rng.shuffle(general)
        candidates.extend(
            {
                "category": "综合能力",
                "question": question,
                "context": "",
                "expected_keywords": [],
            }
            for question in general
        )

        rng.shuffle(candidates)
        selected: List[Dict[str, Any]] = []
        seen = set()
        for candidate in candidates:
            question = candidate["question"]
            if question in seen:
                continue
            seen.add(question)
            candidate = dict(candidate)
            candidate["id"] = len(selected) + 1
            candidate["difficulty"] = "中等"
            candidate["answer_guidance"] = "说明情境、个人行动、验证方式和可归因结果。"
            selected.append(candidate)
            if len(selected) == 10:
                break
        return selected


def stable_render_fingerprint(reports: RenderedReports) -> str:
    """Return a stable digest useful for regression tests and audit logs."""

    payload = json.dumps(
        {
            "suggestions": reports.suggestions,
            "interview_questions": reports.interview_questions,
        },
        ensure_ascii=False,
        sort_keys=True,
    )
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()
