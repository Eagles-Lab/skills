#!/usr/bin/env python3
"""
配置管理器
Configuration Manager

统一管理所有配置文件的加载、缓存和查询
"""

import yaml
import json
from pathlib import Path
from typing import Dict, Any, Optional
from threading import Lock


class ConfigManager:
    """
    配置管理器（单例模式）

    统一管理所有配置文件的加载、缓存和查询
    """

    _instance = None
    _lock = Lock()

    def __new__(cls, config_dir: str = None):
        """
        单例模式实现

        Args:
            config_dir: 配置文件目录

        Returns:
            ConfigManager 实例
        """
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super(ConfigManager, cls).__new__(cls)
        return cls._instance

    def __init__(self, config_dir: str = None):
        """
        初始化配置管理器

        Args:
            config_dir: 配置文件目录
        """
        if hasattr(self, '_initialized') and self._initialized:
            return

        self.config_dir = Path(config_dir) if config_dir else Path(__file__).parent
        self._configs: Dict[str, Any] = {}
        self._initialized = True

    def load_all_configs(self) -> None:
        """加载所有配置文件"""
        self.get_keywords_config()
        self.get_weights_config()
        self.get_criteria_config()

    def get_keywords_config(self) -> Dict:
        """
        获取关键词配置

        Returns:
            关键词配置字典
        """
        if "keywords" not in self._configs:
            config_file = self.config_dir / "sre_keywords.yaml"
            if not config_file.exists():
                raise FileNotFoundError(f"关键词配置文件不存在: {config_file}")

            with open(config_file, 'r', encoding='utf-8') as f:
                self._configs["keywords"] = yaml.safe_load(f)

        return self._configs["keywords"]

    def get_weights_config(self) -> Dict:
        """
        获取权重配置

        Returns:
            权重配置字典
        """
        if "weights" not in self._configs:
            config_file = self.config_dir / "scoring_weights.json"
            if not config_file.exists():
                raise FileNotFoundError(f"权重配置文件不存在: {config_file}")

            with open(config_file, 'r', encoding='utf-8') as f:
                self._configs["weights"] = json.load(f)

        return self._configs["weights"]

    def get_criteria_config(self) -> Dict:
        """
        获取评分标准配置

        Returns:
            评分标准配置字典
        """
        if "criteria" not in self._configs:
            config_file = self.config_dir / "scoring_criteria.yaml"
            if not config_file.exists():
                raise FileNotFoundError(f"评分标准配置文件不存在: {config_file}")

            with open(config_file, 'r', encoding='utf-8') as f:
                self._configs["criteria"] = yaml.safe_load(f)

        return self._configs["criteria"]

    def get_dimension_config(self, dimension: str) -> Optional[Dict]:
        """
        获取特定维度的配置

        Args:
            dimension: 维度名称

        Returns:
            维度配置字典，如果不存在则返回 None
        """
        # 从权重配置获取维度权重
        weights = self.get_weights_config()
        dimension_weights = weights.get("dimensions", {}).get(dimension)

        # 从评分标准获取详细配置
        criteria = self.get_criteria_config()
        dimension_criteria = criteria.get("dimensions", {}).get(dimension)

        if dimension_weights and dimension_criteria:
            return {
                "weight": dimension_weights.get("weight"),
                "name": dimension_weights.get("name"),
                "keywords": dimension_criteria.get("keywords", {}),
                "scoring": dimension_criteria.get("scoring", {})
            }

        return None

    def get_ai_categories(self) -> Dict:
        """
        获取 AI 类别定义

        Returns:
            AI 类别字典
        """
        weights = self.get_weights_config()
        return weights.get("ai_bonus", {}).get("categories", {})

    def get_grade_thresholds(self) -> Dict:
        """
        获取等级阈值

        Returns:
            等级阈值字典
        """
        weights = self.get_weights_config()
        return weights.get("grade_thresholds", {})

    def get_grade_for_score(self, score: float) -> Optional[Dict]:
        """
        根据分数获取等级信息

        Args:
            score: 分数

        Returns:
            等级信息字典
        """
        thresholds = self.get_grade_thresholds()

        for grade, info in thresholds.items():
            min_score, max_score = info["range"]
            if min_score <= score <= max_score:
                return {
                    "grade": grade,
                    "label": info["label"],
                    "description": info["description"],
                    "range": info["range"]
                }

        return None

    def reload_configs(self) -> None:
        """重新加载所有配置"""
        self._configs.clear()
        self.load_all_configs()

    def get_config(self, config_type: str) -> Optional[Dict]:
        """
        获取指定类型的配置

        Args:
            config_type: 配置类型（keywords/weights/criteria）

        Returns:
            配置字典
        """
        config_map = {
            "keywords": self.get_keywords_config,
            "weights": self.get_weights_config,
            "criteria": self.get_criteria_config
        }

        if config_type in config_map:
            return config_map[config_type]()

        return None


# 全局配置管理器实例
_config_manager: Optional[ConfigManager] = None


def get_config_manager(config_dir: str = None) -> ConfigManager:
    """
    获取配置管理器实例

    Args:
        config_dir: 配置文件目录

    Returns:
        ConfigManager 实例
    """
    global _config_manager

    if _config_manager is None:
        _config_manager = ConfigManager(config_dir)

    return _config_manager
