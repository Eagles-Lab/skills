#!/usr/bin/env python3
"""
文本提取工具
Text Extraction Utilities

提供从简历结构化数据中提取文本的工具函数
"""

from typing import Dict, Optional


def extract_full_text_from_data(extracted_data: Dict, resume_text: str = None) -> str:
    """
    从提取的结构化数据中生成完整文本用于关键词匹配

    Args:
        extracted_data: 结构化的简历数据
        resume_text: 原始简历文本（可选，如果提供则直接返回）

    Returns:
        用于匹配的完整文本
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
            info.get("phone", ""),
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
