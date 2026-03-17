"""
Jinja2 模板管理器
Jinja2 Template Manager

提供 Jinja2 模板加载和渲染功能
"""

from jinja2 import Environment, FileSystemLoader, Template
from pathlib import Path
from typing import Dict, Any


class TemplateManager:
    """Jinja2 模板管理器"""

    def __init__(self, template_dir: str = None):
        """
        初始化模板管理器

        Args:
            template_dir: 模板文件目录
        """
        if template_dir is None:
            template_dir = Path(__file__).parent.parent / "templates"
        else:
            template_dir = Path(template_dir)

        # 创建 Jinja2 环境
        self.env = Environment(
            loader=FileSystemLoader(str(template_dir)),
            autoescape=True,
            trim_blocks=True,
            lstrip_blocks=True
        )

        # 添加自定义过滤器
        self._add_custom_filters()

    def _add_custom_filters(self):
        """添加自定义过滤器"""
        # 颜色过滤器（仅用于调试）
        # self.env.filters['debug'] = lambda x: f"[DEBUG] {x}"

    def render_template(self, template_name: str, context: Dict[str, Any]) -> str:
        """
        渲染模板

        Args:
            template_name: 模板名称（不含扩展名）
            context: 模板上下文数据

        Returns:
            渲染后的文本
        """
        template = self.env.get_template(f"{template_name}.md")
        return template.render(**context)

    def render_string(self, template_string: str, context: Dict[str, Any]) -> str:
        """
        渲染字符串模板

        Args:
            template_string: 模板字符串
            context: 模板上下文数据

        Returns:
            渲染后的文本
        """
        template = Template(template_string)
        return template.render(**context)


# 全局模板管理器实例
_template_manager = None


def get_template_manager(template_dir: str = None) -> TemplateManager:
    """
    获取模板管理器实例

    Args:
        template_dir: 模板文件目录

    Returns:
        TemplateManager 实例
    """
    global _template_manager

    if _template_manager is None:
        _template_manager = TemplateManager(template_dir)

    return _template_manager
