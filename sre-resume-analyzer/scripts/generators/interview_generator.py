"""
面试题生成器
Interview Questions Generator

负责根据简历内容生成个性化面试题
"""

from datetime import datetime
from pathlib import Path
from typing import Dict, List
import random


class InterviewGenerator:
    """面试题生成器，负责根据简历内容生成个性化面试题"""

    def __init__(self, template_dir: str = None):
        """
        初始化面试题生成器

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
        """加载面试题模板"""
        template_file = self.template_dir / "interview_questions_template.md"
        if not template_file.exists():
            raise FileNotFoundError(f"面试题模板文件不存在: {template_file}")

        with open(template_file, 'r', encoding='utf-8') as f:
            return f.read()

    def generate_interview_questions(self, extracted_data: Dict, score_data: Dict) -> str:
        """
        生成面试题

        Args:
            extracted_data: 结构化的简历数据 (extracted.json)
            score_data: 评分数据 (score.json)

        Returns:
            格式化的面试题 Markdown 文本
        """
        # 分析简历内容，确定题目分配策略
        allocation = self._analyze_content_allocation(extracted_data)

        # 生成面试题
        questions = self._generate_questions(extracted_data, score_data, allocation)

        # 生成面试建议
        focus_areas = self._generate_focus_areas(score_data)
        expected_answers = self._generate_expected_answers(questions, extracted_data)

        # 填充模板
        basic_info = extracted_data.get("basic_info", {})

        template_data = {
            "name": basic_info.get("name", "未知"),
            "school": basic_info.get("education", "未知").split()[0] if basic_info.get("education") else "未知",
            "major": basic_info.get("education", "未知").split()[1] if len(basic_info.get("education", "").split()) > 1 else "未知",
            "resume_id": extracted_data.get("resume_id", "unknown"),
            "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "interview_questions": self._format_questions(questions),
            "interview_focus_areas": focus_areas,
            "expected_answers": expected_answers,
            "total_questions": len(questions)
        }

        return self.template.format(**template_data)

    def _analyze_content_allocation(self, extracted_data: Dict) -> Dict:
        """
        分析简历内容，确定题目分配策略

        Args:
            extracted_data: 结构化的简历数据

        Returns:
            题目分配策略
        """
        has_internships = len(extracted_data.get("internships", [])) > 0
        has_projects = len(extracted_data.get("projects", [])) > 0
        has_skills = len(extracted_data.get("skills", [])) > 0

        # 根据内容情况分配题目数量（总共不超过 10 题）
        allocation = {
            "internship": 0,
            "project": 0,
            "skill": 0
        }

        if has_internships and has_projects and has_skills:
            # 有实习+有项目+有技能 → 3 + 4 + 3
            allocation = {"internship": 3, "project": 4, "skill": 3}
        elif not has_internships and has_projects and has_skills:
            # 无实习+有项目+有技能 → 6 + 4
            allocation = {"internship": 0, "project": 6, "skill": 4}
        elif not has_internships and not has_projects and has_skills:
            # 无实习+无项目+有技能 → 10
            allocation = {"internship": 0, "project": 0, "skill": 10}
        elif has_internships and not has_projects and has_skills:
            # 有实习+无项目+有技能 → 5 + 5
            allocation = {"internship": 5, "project": 0, "skill": 5}
        elif has_internships and has_projects and not has_skills:
            # 有实习+有项目+无技能 → 5 + 5
            allocation = {"internship": 5, "project": 5, "skill": 0}
        else:
            # 其他情况，平均分配
            allocation = {"internship": 3, "project": 4, "skill": 3}

        return allocation

    def _generate_questions(self, extracted_data: Dict, score_data: Dict, allocation: Dict) -> List[Dict]:
        """
        生成面试题

        Args:
            extracted_data: 结构化的简历数据
            score_data: 评分数据
            allocation: 题目分配策略

        Returns:
            面试题列表
        """
        questions = []
        question_id = 1

        # 生成实习经历题目
        if allocation["internship"] > 0:
            internship_questions = self._generate_internship_questions(
                extracted_data.get("internships", []),
                allocation["internship"]
            )
            for q in internship_questions:
                q["id"] = question_id
                q["category"] = "实习经历"
                questions.append(q)
                question_id += 1

        # 生成项目经历题目
        if allocation["project"] > 0:
            project_questions = self._generate_project_questions(
                extracted_data.get("projects", []),
                allocation["project"]
            )
            for q in project_questions:
                q["id"] = question_id
                q["category"] = "项目经历"
                questions.append(q)
                question_id += 1

        # 生成技能题目
        if allocation["skill"] > 0:
            skill_questions = self._generate_skill_questions(
                extracted_data.get("skills", []),
                score_data,
                allocation["skill"]
            )
            for q in skill_questions:
                q["id"] = question_id
                q["category"] = "技术技能"
                questions.append(q)
                question_id += 1

        return questions

    def _generate_internship_questions(self, internships: List[Dict], count: int) -> List[Dict]:
        """
        生成实习经历相关题目

        Args:
            internships: 实习经历列表
            count: 题目数量

        Returns:
            实习经历题目列表
        """
        questions = []
        templates = [
            "请详细介绍一下你在{company}的{position}实习经历，主要负责哪些工作？",
            "在{company}实习期间，你遇到的最大技术挑战是什么？是如何解决的？",
            "你在{company}的项目中使用了哪些技术栈？为什么选择这些技术？",
            "描述一下你在{company}参与的最有成就感的项目，以及你的贡献。",
            "在{company}实习期间，你如何与团队成员协作？遇到过什么沟通问题吗？"
        ]

        if not internships:
            return questions

        # 选择题目模板并填充
        selected_templates = random.sample(templates, min(count, len(templates)))

        for i, template in enumerate(selected_templates[:count]):
            internship = internships[i % len(internships)]
            question_text = template.format(
                company=internship.get("company", "公司"),
                position=internship.get("position", "职位")
            )

            questions.append({
                "question": question_text,
                "context": internship.get("description", ""),
                "difficulty": "中等",
                "expected_keywords": self._extract_keywords_from_description(internship.get("description", ""))
            })

        return questions

    def _generate_project_questions(self, projects: List[Dict], count: int) -> List[Dict]:
        """
        生成项目经历相关题目

        Args:
            projects: 项目经历列表
            count: 题目数量

        Returns:
            项目经历题目列表
        """
        questions = []
        templates = [
            "请详细介绍{project_name}项目，你的角色和职责是什么？",
            "在{project_name}项目中，你遇到的最大技术难点是什么？如何解决的？",
            "{project_name}项目使用了{technologies}，为什么选择这些技术？有什么优缺点？",
            "如果让你重新设计{project_name}项目，你会做哪些改进？",
            "{project_name}项目的性能指标如何？有没有做过性能优化？",
            "在{project_name}项目中，你是如何保证代码质量和系统稳定性的？"
        ]

        if not projects:
            return questions

        # 选择题目模板并填充
        selected_templates = random.sample(templates, min(count, len(templates)))

        for i, template in enumerate(selected_templates[:count]):
            project = projects[i % len(projects)]
            question_text = template.format(
                project_name=project.get("name", "项目"),
                technologies="、".join(project.get("technologies", ["技术"]))
            )

            questions.append({
                "question": question_text,
                "context": project.get("description", ""),
                "difficulty": "中等",
                "expected_keywords": project.get("technologies", [])
            })

        return questions

    def _generate_skill_questions(self, skills: List[str], score_data: Dict, count: int) -> List[Dict]:
        """
        生成技能相关题目

        Args:
            skills: 技能列表
            score_data: 评分数据
            count: 题目数量

        Returns:
            技能题目列表
        """
        questions = []

        # 根据评分数据中的维度得分，选择薄弱维度进行重点考察
        dimension_scores = score_data.get("dimension_scores", {})

        # 找出得分较低的维度
        weak_dimensions = sorted(
            dimension_scores.items(),
            key=lambda x: x[1].get("score", 0)
        )[:count]

        dimension_templates = {
            "monitoring": [
                "请介绍你熟悉的监控工具（如 Prometheus、Grafana）及其使用场景。",
                "什么是 SLI/SLO？如何设计合理的监控指标？",
                "如何设计一个完整的监控系统？需要考虑哪些方面？"
            ],
            "alerting": [
                "如何设计合理的告警规则？告警分级的原则是什么？",
                "遇到过告警风暴吗？如何进行告警收敛？",
                "什么是 On-call 机制？如何设计有效的 Runbook？"
            ],
            "automation": [
                "请介绍你使用过的 CI/CD 工具和流程。",
                "如何实现基础设施即代码（IaC）？使用过哪些工具？",
                "如何编写高质量的自动化脚本？有哪些最佳实践？"
            ],
            "containerization": [
                "Docker 和 Kubernetes 的区别是什么？各自的适用场景？",
                "如何设计微服务架构？有哪些挑战和解决方案？",
                "什么是 Service Mesh？它解决了什么问题？"
            ],
            "incident_handling": [
                "描述一次你参与的重大故障处理过程。",
                "什么是 Postmortem？如何进行根因分析（RCA）？",
                "如何设计高可用系统？有哪些关键要素？"
            ],
            "resume_quality": [
                "请用 STAR 原则描述一个你参与的项目。",
                "如何量化项目成果？举例说明。",
                "简历中提到的某个技能，请详细介绍你的使用经验。"
            ]
        }

        for dimension, score_info in weak_dimensions:
            if dimension in dimension_templates:
                template = random.choice(dimension_templates[dimension])
                questions.append({
                    "question": template,
                    "context": f"维度得分: {score_info.get('score', 0)}/10",
                    "difficulty": "中等",
                    "expected_keywords": score_info.get("evidence", [{}])[0].get("keyword", "") if score_info.get("evidence") else ""
                })

        # 如果技能题目不够，补充通用技术题
        if len(questions) < count:
            general_questions = [
                "请介绍你最有信心的技术栈，以及你在实际项目中的应用经验。",
                "如何保持技术更新？最近学习了哪些新技术？",
                "描述一个你解决过的复杂技术问题，你的思路和方法是什么？"
            ]

            for i in range(count - len(questions)):
                questions.append({
                    "question": general_questions[i % len(general_questions)],
                    "context": "",
                    "difficulty": "中等",
                    "expected_keywords": skills[:5] if skills else []
                })

        return questions[:count]

    def _extract_keywords_from_description(self, description: str) -> List[str]:
        """
        从描述中提取关键词

        Args:
            description: 描述文本

        Returns:
            关键词列表
        """
        # 简单的关键词提取：按空格分词，过滤常见词
        words = description.split()
        keywords = [word for word in words if len(word) > 3 and word.isalpha()]
        return keywords[:5]

    def _format_questions(self, questions: List[Dict]) -> str:
        """
        格式化题目列表为 Markdown

        Args:
            questions: 题目列表

        Returns:
            格式化的 Markdown 文本
        """
        formatted = []

        for q in questions:
            formatted.append(f"### {q['id']}. {q['category']} ({q['difficulty']})\n")
            formatted.append(f"**问题**: {q['question']}\n")
            if q.get("context"):
                formatted.append(f"**背景**: {q['context']}\n")
            if q.get("expected_keywords"):
                keywords = q['expected_keywords'] if isinstance(q['expected_keywords'], list) else [q['expected_keywords']]
                formatted.append(f"**预期关键词**: {', '.join(keywords)}\n")
            formatted.append("")

        return "\n".join(formatted)

    def _generate_focus_areas(self, score_data: Dict) -> str:
        """
        生成面试考察重点

        Args:
            score_data: 评分数据

        Returns:
            考察重点文本
        """
        dimension_scores = score_data.get("dimension_scores", {})

        # 找出薄弱维度
        weak_dimensions = [
            (dim, info) for dim, info in dimension_scores.items()
            if info.get("score", 0) < 7.0
        ]

        focus_areas = []

        dimension_names = {
            "monitoring": "监控相关经验",
            "alerting": "告警设计能力",
            "automation": "自动化能力",
            "containerization": "容器化/云原生",
            "incident_handling": "故障处理经验",
            "resume_quality": "简历整体质量"
        }

        for dim, info in weak_dimensions[:3]:  # 最多3个重点
            focus_areas.append(f"- **{dimension_names.get(dim, dim)}**: 得分 {info['score']}/10，需要重点考察")

        if not focus_areas:
            focus_areas.append("- 综合能力较强，重点关注项目经验和技术深度")

        return "\n".join(focus_areas)

    def _generate_expected_answers(self, questions: List[Dict], extracted_data: Dict) -> str:
        """
        生成预期回答要点

        Args:
            questions: 题目列表
            extracted_data: 结构化数据

        Returns:
            预期回答要点文本
        """
        answer_points = []

        for q in questions[:5]:  # 最多5个回答要点
            points = []

            if q.get("expected_keywords"):
                keywords = q['expected_keywords'] if isinstance(q['expected_keywords'], list) else [q['expected_keywords']]
                points.append(f"  - 关键词: {', '.join(keywords)}")

            points.append(f"  - 回答结构: 使用 STAR 原则（情境-任务-行动-结果）")
            points.append(f"  - 量化成果: 提供具体数据和结果")

            answer_points.append(f"{q['id']}. {q['question']}\n" + "\n".join(points))

        return "\n\n".join(answer_points)
