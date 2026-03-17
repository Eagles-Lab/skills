#!/usr/bin/env python3
"""
维度常量定义
Dimension Constants

统一管理所有评分维度的名称和映射
"""

# 评分维度列表（顺序重要）
SCORING_DIMENSIONS = [
    "monitoring",
    "alerting",
    "automation",
    "containerization",
    "incident_handling",
    "resume_quality"
]

# 维度中文名称映射
DIMENSION_NAMES = {
    "monitoring": "监控相关经验",
    "alerting": "告警设计能力",
    "automation": "自动化能力",
    "containerization": "容器化/云原生",
    "incident_handling": "故障处理经验",
    "resume_quality": "简历整体质量"
}

# 关键词权重
KEYWORD_WEIGHTS = ["high", "medium", "low"]

# AI 类别
AI_CATEGORIES = ["llm", "ai_agents", "ai_ide", "ml_ops", "aiops"]

# AI 类别中文名称映射
AI_CATEGORY_NAMES = {
    "llm": "大语言模型应用",
    "ai_agents": "AI Agent 开发",
    "ai_ide": "AI 辅助开发工具",
    "ml_ops": "机器学习运维",
    "aiops": "智能运维"
}
