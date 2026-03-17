"""
AI 加分评估器
AI Bonus Evaluator

负责评估简历中的 AI 技术应用，计算 AI 加分
"""

import re
from typing import Dict, List
from pathlib import Path
import yaml
import json


class AIBonusEvaluator:
    """AI 加分评估器，负责评估候选人在 AI 技术方面的应用深度"""

    def __init__(self, config_dir: str = None):
        """
        初始化 AI 加分评估器

        Args:
            config_dir: 配置文件目录路径
        """
        if config_dir is None:
            config_dir = Path(__file__).parent.parent.parent / "config"
        else:
            config_dir = Path(config_dir)

        self.config_dir = config_dir
        self.weights_config = self._load_weights_config()
        self.keywords_config = self._load_keywords_config()

    def _load_weights_config(self) -> dict:
        """加载权重配置文件"""
        weights_file = self.config_dir / "scoring_weights.json"
        if not weights_file.exists():
            raise FileNotFoundError(f"权重配置文件不存在: {weights_file}")

        with open(weights_file, 'r', encoding='utf-8') as f:
            return json.load(f)

    def _load_keywords_config(self) -> dict:
        """加载关键词配置文件"""
        keywords_file = self.config_dir / "sre_keywords.yaml"
        if not keywords_file.exists():
            raise FileNotFoundError(f"关键词配置文件不存在: {keywords_file}")

        with open(keywords_file, 'r', encoding='utf-8') as f:
            return yaml.safe_load(f)

    def evaluate_ai_bonus(self, extracted_data: Dict, resume_text: str = None) -> Dict:
        """
        评估 AI 技术加分

        Args:
            extracted_data: 结构化的简历数据
            resume_text: 简历原文文本（可选）

        Returns:
            AI 加分评估结果
        """
        # 合并所有文本
        full_text = self._extract_full_text(extracted_data, resume_text)

        # 检测 AI 类别应用
        ai_applications = self._detect_ai_applications(full_text)

        # 分析应用深度
        depth_analysis = self._analyze_application_depth(ai_applications, full_text)

        # 检测量化成果
        quantification = self._detect_quantification(full_text)

        # 计算加分
        bonus_score = self._calculate_bonus_score(ai_applications, depth_analysis, quantification)

        return {
            "score": bonus_score["score"],
            "level": bonus_score["level"],
            "category_count": len(ai_applications),
            "applications": ai_applications,
            "depth_analysis": depth_analysis,
            "quantification": quantification,
            "max_score": self.weights_config["ai_bonus"]["max_score"],
            "evidence": self._collect_evidence(ai_applications, full_text)
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

        # 实习经历
        if "internships" in extracted_data:
            for internship in extracted_data["internships"]:
                text_parts.append(internship.get("description", ""))

        # 项目经历
        if "projects" in extracted_data:
            for project in extracted_data["projects"]:
                text_parts.append(project.get("description", ""))
                text_parts.extend(project.get("technologies", []))

        # 技能
        if "skills" in extracted_data:
            text_parts.extend(extracted_data["skills"])

        return " ".join(text_parts)

    def _detect_ai_applications(self, text: str) -> Dict[str, Dict]:
        """
        检测文本中的 AI 类别应用

        Args:
            text: 待检测的文本

        Returns:
            AI 类别应用检测结果
        """
        ai_config = self.keywords_config.get("ai_and_intelligent_ops", {})
        ai_categories = self.weights_config.get("ai_bonus", {}).get("categories", {})

        applications = {}
        text_lower = text.lower()

        for category_key, category_description in ai_categories.items():
            keywords = ai_config.get(category_key, [])
            matches = []

            for keyword in keywords:
                # 使用词边界匹配
                pattern = r'\b' + re.escape(keyword.lower()) + r'\b'
                if re.search(pattern, text_lower):
                    # 获取关键词上下文
                    for match in re.finditer(pattern, text_lower):
                        start = max(0, match.start() - 100)
                        end = min(len(text), match.end() + 100)
                        context = text[start:end].strip()

                        matches.append({
                            "keyword": keyword,
                            "context": context,
                            "position": match.start()
                        })

            if matches:
                applications[category_key] = {
                    "description": category_description,
                    "keyword_matches": matches,
                    "match_count": len(matches)
                }

        return applications

    def _analyze_application_depth(self, ai_applications: Dict, text: str) -> Dict:
        """
        分析 AI 应用的深度

        Args:
            ai_applications: AI 应用检测结果
            text: 完整文本

        Returns:
            应用深度分析结果
        """
        depth_analysis = {}

        for category, app_info in ai_applications.items():
            matches = app_info["keyword_matches"]
            match_count = len(matches)

            # 判断深度：基于匹配次数和上下文
            if match_count >= 5:
                depth = "深度应用"
            elif match_count >= 3:
                depth = "熟练应用"
            elif match_count >= 1:
                depth = "基本应用"
            else:
                depth = "无"

            # 检查是否有具体实现描述
            has_implementation = any(
                word in text.lower()
                for word in ["实现", "开发", "设计", "构建", "部署", "训练", "优化"]
            )

            # 检查是否有业务场景描述
            has_scenario = any(
                word in text.lower()
                for word in ["场景", "问题", "需求", "挑战", "解决"]
            )

            depth_analysis[category] = {
                "depth": depth,
                "match_count": match_count,
                "has_implementation": has_implementation,
                "has_scenario": has_scenario,
                "confidence": self._calculate_confidence(match_count, has_implementation, has_scenario)
            }

        return depth_analysis

    def _calculate_confidence(self, match_count: int, has_implementation: bool, has_scenario: bool) -> str:
        """
        计算评估置信度

        Args:
            match_count: 匹配次数
            has_implementation: 是否有实现描述
            has_scenario: 是否有场景描述

        Returns:
            置信度等级（高/中/低）
        """
        score = 0

        if match_count >= 5:
            score += 3
        elif match_count >= 3:
            score += 2
        elif match_count >= 1:
            score += 1

        if has_implementation:
            score += 1

        if has_scenario:
            score += 1

        if score >= 4:
            return "高"
        elif score >= 2:
            return "中"
        else:
            return "低"

    def _detect_quantification(self, text: str) -> Dict:
        """
        检测量化成果

        Args:
            text: 完整文本

        Returns:
            量化成果检测结果
        """
        quantification_patterns = [
            (r'(\d+(?:\.\d+)?)\s*%', '百分比'),
            (r'(\d+(?:\.\d+)?)\s*[xX×]', '倍数'),
            (r'提升\s*(\d+(?:\.\d+)?)', '提升'),
            (r'降低\s*(\d+(?:\.\d+)?)', '降低'),
            (r'节省\s*(\d+(?:\.\d+)?)', '节省'),
            (r'提高\s*(\d+(?:\.\d+)?)', '提高'),
            (r'优化\s*(\d+(?:\.\d+)?)', '优化'),
        ]

        findings = []

        for pattern, label in quantification_patterns:
            matches = re.finditer(pattern, text)
            for match in matches:
                start = max(0, match.start() - 50)
                end = min(len(text), match.end() + 50)
                context = text[start:end].strip()

                findings.append({
                    "type": label,
                    "value": match.group(1),
                    "context": context
                })

        return {
            "has_quantification": len(findings) > 0,
            "finding_count": len(findings),
            "findings": findings[:10]  # 限制数量
        }

    def _calculate_bonus_score(self, ai_applications: Dict, depth_analysis: Dict, quantification: Dict) -> Dict:
        """
        计算 AI 加分

        Args:
            ai_applications: AI 应用检测结果
            depth_analysis: 深度分析结果
            quantification: 量化成果

        Returns:
            加分结果
        """
        category_count = len(ai_applications)

        # 根据类别数量和量化成果确定加分
        if category_count >= 3:
            if quantification["has_quantification"]:
                return {
                    "score": 1.5,
                    "level": "深度应用（3+类别，有量化成果）"
                }
            else:
                return {
                    "score": 1.0,
                    "level": "应用（3+类别，无量化成果）"
                }
        elif category_count == 2:
            return {
                "score": 1.0,
                "level": "应用（2类别）"
            }
        elif category_count == 1:
            return {
                "score": 0.5,
                "level": "应用（1类别）"
            }
        else:
            return {
                "score": 0.0,
                "level": "无AI技术应用"
            }

    def _collect_evidence(self, ai_applications: Dict, text: str) -> List[Dict]:
        """
        收集 AI 应用证据

        Args:
            ai_applications: AI 应用检测结果
            text: 完整文本

        Returns:
            证据列表
        """
        evidence = []

        for category, app_info in ai_applications.items():
            for match in app_info["keyword_matches"][:3]:  # 每个类别最多3个证据
                evidence.append({
                    "category": category,
                    "keyword": match["keyword"],
                    "context": match["context"]
                })

        return evidence
