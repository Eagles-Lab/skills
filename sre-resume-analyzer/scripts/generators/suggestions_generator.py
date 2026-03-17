"""
建议报告生成器
Suggestions Report Generator

负责根据评分结果生成优化建议报告
"""

from datetime import datetime
from pathlib import Path
from typing import Dict, List


class SuggestionsGenerator:
    """建议报告生成器，负责生成简历优化建议"""

    def __init__(self, template_dir: str = None):
        """
        初始化建议报告生成器

        Args:
            template_dir: 模板文件目录路径
        """
        if template_dir is None:
            template_dir = Path(__file__).parent.parent.parent / "templates"
        else:
            template_dir = Path(template_dir)

        self.template_dir = template_dir
        self.template = self._load_template()

    def _load_template(self) -> str:
        """加载建议模板"""
        template_file = self.template_dir / "suggestions_template.md"
        if not template_file.exists():
            raise FileNotFoundError(f"建议模板文件不存在: {template_file}")

        with open(template_file, 'r', encoding='utf-8') as f:
            return f.read()

    def generate_suggestions(self, extracted_data: Dict, score_data: Dict, analysis_data: Dict = None) -> str:
        """
        生成优化建议报告

        Args:
            extracted_data: 结构化的简历数据 (extracted.json)
            score_data: 评分数据 (score.json)
            analysis_data: 分析数据 (analysis.json，可选)

        Returns:
            格式化的建议 Markdown 文本
        """
        # 提取基本信息
        basic_info = extracted_data.get("basic_info", {})

        # 生成各部分内容
        strengths = self._generate_strengths(score_data, extracted_data)
        high_priority = self._generate_priority_tasks(score_data, "high")
        medium_priority = self._generate_priority_tasks(score_data, "medium")
        low_priority = self._generate_priority_tasks(score_data, "low")

        # 生成 AI 类别列表
        ai_categories_list = self._format_ai_categories(score_data)
        unrecognized_categories = self._get_unrecognized_categories(score_data)

        # 计算百分位
        percentile = self._estimate_percentile(score_data.get("total_score", 0))

        # 生成维度详细分析
        dimension_analysis = self._generate_dimension_analysis(score_data, extracted_data)

        # 填充模板
        template_data = {
            # 基本信息
            "name": basic_info.get("name", "未知"),
            "school": basic_info.get("education", "未知").split()[0] if basic_info.get("education") else "未知",
            "major": basic_info.get("education", "未知").split()[1] if len(basic_info.get("education", "").split()) > 1 else "未知",
            "degree": "本科",  # 默认值，可根据实际情况调整
            "graduation_year": "2024",  # 默认值，可根据实际情况调整
            "resume_id": extracted_data.get("resume_id", "unknown"),
            "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "batch_id": "batch_001",  # 默认批次 ID

            # 综合评分
            "total_score": score_data.get("total_score", 0),
            "overall_grade": score_data.get("grade", {}).get("grade", "F"),
            "grade_label": score_data.get("grade", {}).get("label", "需改进"),
            "percentile": percentile,
            "base_score": score_data.get("base_score", 0),

            # 六大维度得分
            "monitoring_score": score_data["dimension_scores"]["monitoring"]["score"],
            "alerting_score": score_data["dimension_scores"]["alerting"]["score"],
            "automation_score": score_data["dimension_scores"]["automation"]["score"],
            "containerization_score": score_data["dimension_scores"]["containerization"]["score"],
            "incident_score": score_data["dimension_scores"]["incident_handling"]["score"],
            "quality_score": score_data["dimension_scores"]["resume_quality"]["score"],

            "monitoring_weighted": f"{score_data['dimension_scores']['monitoring']['weighted_score']:.1f}",
            "alerting_weighted": f"{score_data['dimension_scores']['alerting']['weighted_score']:.1f}",
            "automation_weighted": f"{score_data['dimension_scores']['automation']['weighted_score']:.1f}",
            "containerization_weighted": f"{score_data['dimension_scores']['containerization']['weighted_score']:.1f}",
            "incident_weighted": f"{score_data['dimension_scores']['incident_handling']['weighted_score']:.1f}",
            "quality_weighted": f"{score_data['dimension_scores']['resume_quality']['weighted_score']:.1f}",

            "monitoring_grade": self._score_to_grade(score_data["dimension_scores"]["monitoring"]["score"]),
            "alerting_grade": self._score_to_grade(score_data["dimension_scores"]["alerting"]["score"]),
            "automation_grade": self._score_to_grade(score_data["dimension_scores"]["automation"]["score"]),
            "containerization_grade": self._score_to_grade(score_data["dimension_scores"]["containerization"]["score"]),
            "incident_grade": self._score_to_grade(score_data["dimension_scores"]["incident_handling"]["score"]),
            "quality_grade": self._score_to_grade(score_data["dimension_scores"]["resume_quality"]["score"]),

            # AI 加分
            "ai_bonus_score": score_data.get("ai_bonus", {}).get("score", 0),
            "ai_categories_list": ai_categories_list,
            "unrecognized_categories": unrecognized_categories,

            # 优势和改进
            "strengths_section": strengths,
            "high_priority_tasks": high_priority,
            "medium_priority_tasks": medium_priority,
            "low_priority_tasks": low_priority,

            # 维度详细分析
            "monitoring_evidence": dimension_analysis.get("monitoring", ""),
            "alerting_evidence": dimension_analysis.get("alerting", ""),
            "automation_evidence": dimension_analysis.get("automation", ""),
            "containerization_evidence": dimension_analysis.get("containerization", ""),
            "incident_evidence": dimension_analysis.get("incident_handling", ""),
            "quality_evidence": dimension_analysis.get("resume_quality", "")
        }

        return self.template.format(**template_data)

    def _generate_strengths(self, score_data: Dict, extracted_data: Dict) -> str:
        """
        生成优势亮点

        Args:
            score_data: 评分数据
            extracted_data: 结构化数据

        Returns:
            优势亮点文本
        """
        strengths = []

        # 找出高分维度
        dimension_scores = score_data.get("dimension_scores", {})
        strong_dimensions = [
            (dim, info) for dim, info in dimension_scores.items()
            if info.get("score", 0) >= 8.0
        ]

        dimension_names = {
            "monitoring": "监控相关经验",
            "alerting": "告警设计能力",
            "automation": "自动化能力",
            "containerization": "容器化/云原生",
            "incident_handling": "故障处理经验",
            "resume_quality": "简历整体质量"
        }

        for dim, info in strong_dimensions:
            evidence = info.get("evidence", [])
            if evidence:
                keywords = [e.get("keyword", "") for e in evidence[:3]]
                strengths.append(
                    f"- **{dimension_names.get(dim, dim)}** ({info['score']}/10): "
                    f"掌握 {', '.join(keywords)} 等核心技术"
                )

        # AI 加分优势
        ai_bonus = score_data.get("ai_bonus", {})
        if ai_bonus.get("score", 0) > 0:
            categories = list(ai_bonus.get("applications", {}).keys())
            strengths.append(
                f"- **AI 技术应用** (+{ai_bonus['score']}): "
                f"在 {', '.join(categories)} 领域有实际应用经验"
            )

        # 项目经验优势
        projects = extracted_data.get("projects", [])
        if len(projects) >= 2:
            strengths.append(f"- **项目经验丰富**: 参与过 {len(projects)} 个项目，涵盖多种技术栈")

        # 实习经验优势
        internships = extracted_data.get("internships", [])
        if len(internships) >= 1:
            companies = [i.get("company", "") for i in internships]
            strengths.append(f"- **实习经历**: 在 {', '.join(companies)} 有实际工作经验")

        if not strengths:
            strengths.append("- 综合能力均衡，持续学习和实践")

        return "\n".join(strengths)

    def _generate_priority_tasks(self, score_data: Dict, priority: str) -> str:
        """
        生成优先级改进任务

        Args:
            score_data: 评分数据
            priority: 优先级 (high/medium/low)

        Returns:
            改进任务文本
        """
        dimension_scores = score_data.get("dimension_scores", {})

        dimension_names = {
            "monitoring": "监控相关经验",
            "alerting": "告警设计能力",
            "automation": "自动化能力",
            "containerization": "容器化/云原生",
            "incident_handling": "故障处理经验",
            "resume_quality": "简历整体质量"
        }

        suggestions = {
            "monitoring": {
                "high": "系统学习 Prometheus + Grafana，搭建完整的监控体系",
                "medium": "深入了解 SLI/SLO 设计，提升监控指标设计能力",
                "low": "学习分布式追踪技术（Jaeger/Zipkin）"
            },
            "alerting": {
                "high": "学习 Alertmanager，设计告警分级和收敛策略",
                "medium": "编写 Runbook，建立 On-call 机制",
                "low": "了解智能告警和告警降噪技术"
            },
            "automation": {
                "high": "深入学习 Terraform/Ansible，实践 IaC",
                "medium": "完善 CI/CD 流水线，提升自动化测试覆盖率",
                "low": "学习高级脚本编程，提升代码质量"
            },
            "containerization": {
                "high": "系统学习 Kubernetes，获得 CKA 认证",
                "medium": "学习微服务架构设计，实践 Service Mesh",
                "low": "了解云原生安全最佳实践"
            },
            "incident_handling": {
                "high": "学习故障排查方法论，参与实战演练",
                "medium": "学习 RCA 和 Postmortem 编写",
                "low": "了解混沌工程和故障注入技术"
            },
            "resume_quality": {
                "high": "使用 STAR 原则重构项目描述",
                "medium": "量化所有项目成果，添加具体数据",
                "low": "优化简历排版和语言表达"
            }
        }

        tasks = []

        if priority == "high":
            # 高优先级：得分 < 7.0 的维度
            weak_dimensions = [
                (dim, info) for dim, info in dimension_scores.items()
                if info.get("score", 0) < 7.0
            ]
            for dim, info in weak_dimensions:
                suggestion = suggestions.get(dim, {}).get("high", f"提升{dimension_names.get(dim, dim)}")
                tasks.append(f"- {suggestion} (当前得分: {info['score']}/10)")

        elif priority == "medium":
            # 中优先级：得分 7.0-8.4 的维度
            medium_dimensions = [
                (dim, info) for dim, info in dimension_scores.items()
                if 7.0 <= info.get("score", 0) < 8.5
            ]
            for dim, info in medium_dimensions:
                suggestion = suggestions.get(dim, {}).get("medium", f"进一步提升{dimension_names.get(dim, dim)}")
                tasks.append(f"- {suggestion} (当前得分: {info['score']}/10)")

        else:  # low
            # 低优先级：得分 >= 8.5 的维度
            strong_dimensions = [
                (dim, info) for dim, info in dimension_scores.items()
                if info.get("score", 0) >= 8.5
            ]
            for dim, info in strong_dimensions:
                suggestion = suggestions.get(dim, {}).get("low", f"深化{dimension_names.get(dim, dim)}")
                tasks.append(f"- {suggestion} (可选)")

        if not tasks:
            tasks.append(f"- 无{priority}优先级任务")

        return "\n".join(tasks)

    def _format_ai_categories(self, score_data: Dict) -> str:
        """
        格式化 AI 类别列表

        Args:
            score_data: 评分数据

        Returns:
            格式化的 AI 类别文本
        """
        ai_applications = score_data.get("ai_bonus", {}).get("applications", {})

        if not ai_applications:
            return "- 未识别到 AI 技术应用"

        formatted = []
        for category, app_info in ai_applications.items():
            match_count = app_info.get("match_count", 0)
            formatted.append(f"- **{category}**: 匹配 {match_count} 个关键词")

        return "\n".join(formatted)

    def _get_unrecognized_categories(self, score_data: Dict) -> str:
        """
        获取未识别到的 AI 类别

        Args:
            score_data: 评分数据

        Returns:
            未识别到的类别文本
        """
        all_categories = ["llm", "ai_agents", "ai_ide", "ml_ops", "aiops"]
        recognized_categories = set(score_data.get("ai_bonus", {}).get("applications", {}).keys())

        unrecognized = [cat for cat in all_categories if cat not in recognized_categories]

        if not unrecognized:
            return "无"

        return ", ".join(unrecognized)

    def _estimate_percentile(self, total_score: float) -> int:
        """
        估算百分位

        Args:
            total_score: 总分

        Returns:
            百分位 (1-100)
        """
        if total_score >= 9.5:
            return 5
        elif total_score >= 8.5:
            return 10
        elif total_score >= 7.0:
            return 30
        elif total_score >= 6.0:
            return 50
        elif total_score >= 5.0:
            return 70
        else:
            return 90

    def _score_to_grade(self, score: float) -> str:
        """
        将分数转换为等级

        Args:
            score: 分数

        Returns:
            等级 (A/B/C/D/F)
        """
        if score >= 9.0:
            return "A"
        elif score >= 7.0:
            return "B"
        elif score >= 5.0:
            return "C"
        elif score >= 3.0:
            return "D"
        else:
            return "F"

    def _generate_dimension_analysis(self, score_data: Dict, extracted_data: Dict) -> Dict[str, str]:
        """
        生成各维度详细分析

        Args:
            score_data: 评分数据
            extracted_data: 结构化数据

        Returns:
            维度分析字典
        """
        analysis = {}
        dimension_scores = score_data.get("dimension_scores", {})

        dimension_names = {
            "monitoring": "监控相关经验",
            "alerting": "告警设计能力",
            "automation": "自动化能力",
            "containerization": "容器化/云原生",
            "incident_handling": "故障处理经验",
            "resume_quality": "简历整体质量"
        }

        for dimension, info in dimension_scores.items():
            evidence_list = info.get("evidence", [])
            evidence_text = []

            if evidence_list:
                evidence_text.append(f"**匹配关键词**: {len(evidence_list)} 个")

                # 展示前 3 个证据
                for i, evidence in enumerate(evidence_list[:3], 1):
                    if evidence.get("type") == "keyword_match":
                        evidence_text.append(
                            f"{i}. 关键词: {evidence.get('keyword', 'N/A')} "
                            f"(权重: {evidence.get('weight', 'N/A')})"
                        )
                    elif evidence.get("type") == "project":
                        evidence_text.append(
                            f"{i}. 项目: {evidence.get('name', 'N/A')} - "
                            f"{evidence.get('description', 'N/A')[:100]}"
                        )
                    elif evidence.get("type") == "internship":
                        evidence_text.append(
                            f"{i}. 实习: {evidence.get('company', 'N/A')} - "
                            f"{evidence.get('position', 'N/A')}"
                        )

            analysis[dimension] = "\n".join(evidence_text) if evidence_text else "暂无相关证据"

        return analysis
