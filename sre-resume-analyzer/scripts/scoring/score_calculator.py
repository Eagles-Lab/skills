"""
评分计算器
Score Calculator

负责根据匹配结果计算各维度分数
"""

import yaml
import json
from pathlib import Path
from typing import Dict, List
from .keyword_matcher import KeywordMatcher


class ScoreCalculator:
    """评分计算器，负责计算简历的各维度得分"""

    def __init__(self, config_dir: str = None):
        """
        初始化评分计算器

        Args:
            config_dir: 配置文件目录路径
        """
        if config_dir is None:
            config_dir = Path(__file__).parent.parent.parent / "config"
        else:
            config_dir = Path(config_dir)

        self.config_dir = config_dir
        self.weights_config = self._load_weights_config()
        self.criteria_config = self._load_criteria_config()
        self.keyword_matcher = KeywordMatcher(str(config_dir))

    def _load_weights_config(self) -> dict:
        """加载权重配置文件"""
        weights_file = self.config_dir / "scoring_weights.json"
        if not weights_file.exists():
            raise FileNotFoundError(f"权重配置文件不存在: {weights_file}")

        with open(weights_file, 'r', encoding='utf-8') as f:
            return json.load(f)

    def _load_criteria_config(self) -> dict:
        """加载评分标准配置文件"""
        criteria_file = self.config_dir / "scoring_criteria.yaml"
        if not criteria_file.exists():
            raise FileNotFoundError(f"评分标准配置文件不存在: {criteria_file}")

        with open(criteria_file, 'r', encoding='utf-8') as f:
            return yaml.safe_load(f)

    def calculate_scores(self, extracted_data: Dict, resume_text: str = None) -> Dict:
        """
        计算简历的各维度得分

        Args:
            extracted_data: 结构化的简历数据 (extracted.json 内容)
            resume_text: 简历原文文本（可选，用于更精确的关键词匹配）

        Returns:
            评分结果字典
        """
        # 合并所有文本用于关键词匹配
        full_text = self._extract_full_text(extracted_data, resume_text)

        # 匹配关键词
        keyword_matches = self.keyword_matcher.match_keywords(full_text)

        # 计算各维度得分
        dimension_scores = {}
        for dimension in ["monitoring", "alerting", "automation", "containerization", "incident_handling", "resume_quality"]:
            score_result = self._calculate_dimension_score(dimension, keyword_matches, extracted_data, full_text)
            dimension_scores[dimension] = score_result

        # 计算基础总分（加权平均）
        base_score = self._calculate_base_score(dimension_scores)

        # 评估 AI 加分
        ai_bonus = self._evaluate_ai_bonus(keyword_matches, full_text)

        # 计算最终总分
        total_score = base_score + ai_bonus["score"]

        # 确定等级
        grade = self._determine_grade(total_score)

        return {
            "base_score": round(base_score, 1),
            "ai_bonus": ai_bonus,
            "total_score": round(total_score, 1),
            "dimension_scores": dimension_scores,
            "grade": grade,
            "keyword_matches": keyword_matches
        }

    def _extract_full_text(self, extracted_data: Dict, resume_text: str = None) -> str:
        """
        从结构化数据中提取完整文本

        Args:
            extracted_data: 结构化的简历数据
            resume_text: 简历原文

        Returns:
            完整的文本内容
        """
        if resume_text:
            return resume_text

        text_parts = []

        # 基本信息
        if "basic_info" in extracted_data:
            info = extracted_data["basic_info"]
            text_parts.extend([
                info.get("name", ""),
                info.get("email", ""),
                info.get("education", "")
            ])

        # 实习经历
        if "internships" in extracted_data:
            for internship in extracted_data["internships"]:
                text_parts.extend([
                    internship.get("company", ""),
                    internship.get("position", ""),
                    internship.get("description", "")
                ])

        # 项目经历
        if "projects" in extracted_data:
            for project in extracted_data["projects"]:
                text_parts.extend([
                    project.get("name", ""),
                    project.get("description", ""),
                    " ".join(project.get("technologies", []))
                ])

        # 技能
        if "skills" in extracted_data:
            text_parts.append(" ".join(extracted_data["skills"]))

        return " ".join(text_parts)

    def _calculate_dimension_score(self, dimension: str, keyword_matches: Dict, extracted_data: Dict, full_text: str) -> Dict:
        """
        计算单个维度的得分

        Args:
            dimension: 维度名称
            keyword_matches: 关键词匹配结果
            extracted_data: 结构化的简历数据
            full_text: 完整文本

        Returns:
            维度评分结果
        """
        dimension_matches = keyword_matches["dimension_keywords"].get(dimension, {})
        dimension_config = self.criteria_config["dimensions"].get(dimension, {})

        # 获取关键词证据
        evidence = self._gather_evidence(dimension, dimension_matches, extracted_data, full_text)

        # 根据关键词匹配情况和证据质量估算分数
        score = self._estimate_score_from_matches(dimension_matches, evidence, dimension_config)

        # 获取权重
        weight = self.weights_config["dimensions"].get(dimension, {}).get("weight", 0.15)

        return {
            "score": round(score, 1),
            "weight": weight,
            "weighted_score": round(score * weight, 1),
            "evidence": evidence,
            "keyword_count": len(dimension_matches.get("keywords", [])),
            "keyword_weight": dimension_matches.get("weight", "low")
        }

    def _gather_evidence(self, dimension: str, matches: Dict, extracted_data: Dict, full_text: str) -> List[Dict]:
        """
        收集维度证据

        Args:
            dimension: 维度名称
            matches: 关键词匹配结果
            extracted_data: 结构化数据
            full_text: 完整文本

        Returns:
            证据列表
        """
        evidence = []

        # 从关键词匹配中获取证据
        for keyword in matches.get("keywords", []):
            # 获取关键词上下文
            context_evidence = self.keyword_matcher.get_keyword_evidence(full_text, dimension)
            for item in context_evidence:
                if item["keyword"] == keyword:
                    evidence.append({
                        "type": "keyword_match",
                        "keyword": keyword,
                        "context": item["context"],
                        "weight": matches.get("weight", "low")
                    })

        # 从实习经历中获取证据
        if "internships" in extracted_data:
            for internship in extracted_data["internships"]:
                description = internship.get("description", "")
                if any(keyword.lower() in description.lower() for keyword in matches.get("keywords", [])):
                    evidence.append({
                        "type": "internship",
                        "company": internship.get("company", ""),
                        "position": internship.get("position", ""),
                        "description": description
                    })

        # 从项目经历中获取证据
        if "projects" in extracted_data:
            for project in extracted_data["projects"]:
                description = project.get("description", "")
                if any(keyword.lower() in description.lower() for keyword in matches.get("keywords", [])):
                    evidence.append({
                        "type": "project",
                        "name": project.get("name", ""),
                        "description": description,
                        "technologies": project.get("technologies", [])
                    })

        return evidence[:10]  # 限制证据数量，避免过多

    def _estimate_score_from_matches(self, matches: Dict, evidence: List, dimension_config: Dict) -> float:
        """
        根据关键词匹配和证据估算分数

        Args:
            matches: 关键词匹配结果
            evidence: 证据列表
            dimension_config: 维度配置

        Returns:
            估算的分数 (1.0 - 10.0)
        """
        keyword_count = len(matches.get("keywords", []))
        keyword_weight = matches.get("weight", "low")
        evidence_count = len(evidence)

        # 根据关键词数量和权重估算分数
        if keyword_count == 0 or evidence_count == 0:
            return 1.0  # 最低分

        if keyword_weight == "high" and evidence_count >= 3:
            return 9.5  # 优秀
        elif keyword_weight == "high" and evidence_count >= 2:
            return 8.5  # 良好偏上
        elif keyword_weight == "medium" and evidence_count >= 3:
            return 8.0  # 良好
        elif keyword_weight == "medium" and evidence_count >= 2:
            return 7.0  # 良好偏下
        elif keyword_count >= 2 and evidence_count >= 2:
            return 6.0  # 中等
        elif keyword_count >= 1 and evidence_count >= 1:
            return 5.0  # 中等偏下
        else:
            return 3.0  # 需改进

    def _calculate_base_score(self, dimension_scores: Dict) -> float:
        """
        计算基础总分（加权平均）

        Args:
            dimension_scores: 各维度得分

        Returns:
            基础总分
        """
        total_weighted_score = sum(
            score["weighted_score"] for score in dimension_scores.values()
        )

        return total_weighted_score

    def _evaluate_ai_bonus(self, keyword_matches: Dict, full_text: str) -> Dict:
        """
        评估 AI 技术加分

        Args:
            keyword_matches: 关键词匹配结果
            full_text: 完整文本

        Returns:
            AI 加分结果
        """
        ai_matches = keyword_matches["categories"]["ai"]
        category_count = ai_matches["category_count"]

        # 根据类别数量和匹配深度评估加分
        score = 0.0
        level = "无"

        if category_count >= 3:
            # 检查是否有量化成果
            has_quantification = any(
                word in full_text.lower()
                for word in ["提升", "提高", "优化", "降低", "节省", "%", "倍", "x"]
            )
            if has_quantification:
                score = 1.5
                level = "深度应用（3+类别，有量化成果）"
            else:
                score = 1.0
                level = "应用（3+类别）"
        elif category_count == 2:
            score = 1.0
            level = "应用（2类别）"
        elif category_count == 1:
            score = 0.5
            level = "应用（1类别）"

        return {
            "score": score,
            "level": level,
            "category_count": category_count,
            "categories": ai_matches["categories"],
            "max_score": self.weights_config["ai_bonus"]["max_score"]
        }

    def _determine_grade(self, total_score: float) -> Dict:
        """
        根据总分确定等级

        Args:
            total_score: 总分

        Returns:
            等级信息
        """
        grade_thresholds = self.weights_config["grade_thresholds"]

        for grade, info in grade_thresholds.items():
            min_score, max_score = info["range"]
            if min_score <= total_score <= max_score:
                return {
                    "grade": grade,
                    "label": info["label"],
                    "description": info["description"],
                    "range": info["range"]
                }

        # 默认返回 F 等级
        return {
            "grade": "F",
            "label": "需大幅改进",
            "description": "建议重新准备",
            "range": [0.0, 3.9]
        }
