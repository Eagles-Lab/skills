"""
关键词匹配器
Keyword Matcher

负责从简历文本中匹配 SRE 相关关键词
"""

import yaml
import json
import re
from pathlib import Path
from typing import Dict, List, Tuple, Set
from collections import defaultdict
import sys

# 添加父目录到系统路径
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from config.config_manager import ConfigManager
from config.dimension_constants import SCORING_DIMENSIONS, KEYWORD_WEIGHTS


class KeywordMatcher:
    """关键词匹配器，负责从简历中提取和匹配 SRE 关键词"""

    def __init__(self, config_dir: str = None):
        """
        初始化关键词匹配器

        Args:
            config_dir: 配置文件目录路径
        """
        if config_dir is None:
            config_dir = Path(__file__).parent.parent.parent / "config"
        else:
            config_dir = Path(config_dir)

        self.config_dir = config_dir
        self.keywords_config = self._load_keywords_config()
        self.weights_config = self._load_weights_config()

    def _load_keywords_config(self) -> dict:
        """加载关键词配置文件"""
        keywords_file = self.config_dir / "sre_keywords.yaml"
        if not keywords_file.exists():
            raise FileNotFoundError(f"关键词配置文件不存在: {keywords_file}")

        with open(keywords_file, 'r', encoding='utf-8') as f:
            return yaml.safe_load(f)

    def _load_weights_config(self) -> dict:
        """加载权重配置文件"""
        weights_file = self.config_dir / "scoring_weights.json"
        if not weights_file.exists():
            raise FileNotFoundError(f"权重配置文件不存在: {weights_file}")

        with open(weights_file, 'r', encoding='utf-8') as f:
            return json.load(f)

    def match_keywords(self, text: str, case_sensitive: bool = False) -> Dict:
        """
        从文本中匹配所有关键词

        Args:
            text: 待匹配的文本
            case_sensitive: 是否区分大小写

        Returns:
            匹配结果字典，包含各类别关键词的匹配信息
        """
        if not case_sensitive:
            text = text.lower()

        result = {
            "total_matches": 0,
            "categories": {},
            "dimension_keywords": {},
            "weighted_keywords": {
                "high": [],
                "medium": [],
                "low": []
            },
            "evidence": []
        }

        # 匹配 AI 相关关键词
        result["categories"]["ai"] = self._match_ai_keywords(text, case_sensitive)

        # 匹配各维度关键词
        for dimension in SCORING_DIMENSIONS:
            matches = self._match_dimension_keywords(text, dimension, case_sensitive)
            result["dimension_keywords"][dimension] = matches
            if matches["keywords"]:
                result["evidence"].extend([
                    {
                        "dimension": dimension,
                        "keyword": kw,
                        "weight": matches["weight"]
                    }
                    for kw in matches["keywords"]
                ])

        # 匹配权重关键词
        for weight in KEYWORD_WEIGHTS:
            weight_keywords = self.keywords_config.get("keyword_weights", {}).get(weight, [])
            matches = self._match_keyword_list(text, weight_keywords, case_sensitive)
            result["weighted_keywords"][weight] = matches

        # 计算总匹配数
        result["total_matches"] = sum(
            len(matches.get("keywords", []))
            for matches in result["dimension_keywords"].values()
        )

        return result

    def _match_ai_keywords(self, text: str, case_sensitive: bool = False) -> Dict:
        """
        匹配 AI 相关关键词

        Args:
            text: 待匹配的文本
            case_sensitive: 是否区分大小写

        Returns:
            AI 关键词匹配结果
        """
        ai_config = self.keywords_config.get("ai_and_intelligent_ops", {})
        ai_categories = self.weights_config.get("ai_bonus", {}).get("categories", {})

        result = {
            "categories": {},
            "total_count": 0,
            "category_count": 0
        }

        for category_key in ai_categories.keys():
            keywords = ai_config.get(category_key, [])
            matches = self._match_keyword_list(text, keywords, case_sensitive)

            if matches:
                result["categories"][category_key] = {
                    "keywords": matches,
                    "count": len(matches)
                }
                result["total_count"] += len(matches)

        result["category_count"] = len(result["categories"])

        return result

    def _match_dimension_keywords(self, text: str, dimension: str, case_sensitive: bool = False) -> Dict:
        """
        匹配特定维度的关键词

        Args:
            text: 待匹配的文本
            dimension: 维度名称 (monitoring, alerting, automation, containerization, incident_handling)
            case_sensitive: 是否区分大小写

        Returns:
            维度关键词匹配结果
        """
        dimension_config = self.keywords_config.get(dimension, {})

        result = {
            "keywords": [],
            "categories": {},
            "weight": "low"  # 默认低权重
        }

        all_keywords = []

        for category, keywords in dimension_config.items():
            matches = self._match_keyword_list(text, keywords, case_sensitive)
            if matches:
                result["categories"][category] = matches
                all_keywords.extend(matches)

        # 去重
        result["keywords"] = list(set(all_keywords))

        # 根据匹配的关键词数量和类型判断权重
        if len(result["keywords"]) >= 3:
            result["weight"] = "high"
        elif len(result["keywords"]) >= 1:
            result["weight"] = "medium"

        return result

    def _match_keyword_list(self, text: str, keywords: List[str], case_sensitive: bool = False) -> List[str]:
        """
        从文本中匹配关键词列表

        Args:
            text: 待匹配的文本
            keywords: 关键词列表
            case_sensitive: 是否区分大小写

        Returns:
            匹配到的关键词列表
        """
        matches = []
        search_text = text if case_sensitive else text.lower()

        for keyword in keywords:
            search_keyword = keyword if case_sensitive else keyword.lower()

            # 使用词边界匹配，避免部分匹配
            pattern = r'\b' + re.escape(search_keyword) + r'\b'
            if re.search(pattern, search_text):
                matches.append(keyword)

        return matches

    def get_keyword_evidence(self, text: str, dimension: str, case_sensitive: bool = False) -> List[Dict]:
        """
        获取特定维度的关键词证据

        Args:
            text: 待匹配的文本
            dimension: 维度名称
            case_sensitive: 是否区分大小写

        Returns:
            证据列表，包含关键词和上下文
        """
        matches = self._match_dimension_keywords(text, dimension, case_sensitive)
        evidence = []

        for keyword in matches["keywords"]:
            search_keyword = keyword if case_sensitive else keyword.lower()
            search_text = text if case_sensitive else text.lower()

            # 查找关键词在文本中的位置和上下文
            pattern = r'\b' + re.escape(search_keyword) + r'\b'
            for match in re.finditer(pattern, search_text):
                start = max(0, match.start() - 50)
                end = min(len(text), match.end() + 50)
                context = text[start:end].strip()

                evidence.append({
                    "keyword": keyword,
                    "context": context,
                    "position": match.start()
                })

        return evidence

    def analyze_text_coverage(self, text: str, case_sensitive: bool = False) -> Dict:
        """
        分析文本的关键词覆盖率

        Args:
            text: 待分析的文本
            case_sensitive: 是否区分大小写

        Returns:
            覆盖率分析结果
        """
        match_result = self.match_keywords(text, case_sensitive)

        # 计算各维度的覆盖率
        dimension_coverage = {}
        for dimension, matches in match_result["dimension_keywords"].items():
            dimension_config = self.keywords_config.get(dimension, {})
            total_keywords = sum(len(kw_list) for kw_list in dimension_config.values())
            matched_keywords = len(matches["keywords"])

            dimension_coverage[dimension] = {
                "total_keywords": total_keywords,
                "matched_keywords": matched_keywords,
                "coverage_rate": matched_keywords / total_keywords if total_keywords > 0 else 0
            }

        # 计算 AI 类别的覆盖率
        ai_coverage = {}
        ai_config = self.keywords_config.get("ai_and_intelligent_ops", {})
        ai_categories = self.weights_config.get("ai_bonus", {}).get("categories", {})

        for category_key in ai_categories.keys():
            total_keywords = len(ai_config.get(category_key, []))
            matched_keywords = match_result["categories"]["ai"]["categories"].get(category_key, {}).get("count", 0)

            ai_coverage[category_key] = {
                "total_keywords": total_keywords,
                "matched_keywords": matched_keywords,
                "coverage_rate": matched_keywords / total_keywords if total_keywords > 0 else 0
            }

        return {
            "dimension_coverage": dimension_coverage,
            "ai_coverage": ai_coverage,
            "total_matches": match_result["total_matches"],
            "ai_category_count": match_result["categories"]["ai"]["category_count"]
        }
