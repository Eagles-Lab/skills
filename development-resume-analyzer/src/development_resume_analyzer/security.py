"""Deterministic handling for instruction-like untrusted resume content."""

from __future__ import annotations

import html
import re
import unicodedata
from collections.abc import Mapping, Sequence
from typing import Any

SECURITY_WARNING = "untrusted_instruction_like_content_detected"
OMITTED_REPORT_TEXT = "[untrusted content omitted]"

_STRONG_PATTERNS = (
    re.compile(r"\b(?:instruction|instructions)\s+to\s+(?:the\s+)?(?:analyzer|agent|model)\b"),
    re.compile(r"\bignore\s+(?:all\s+)?(?:previous|prior|system)\s+instructions?\b"),
    re.compile(r"\b(?:reveal|print|disclose)\b.{0,32}\b(?:system prompt|system message|secret)\b"),
    re.compile(r"\b(?:change|set|assign)\b.{0,24}\b(?:final\s+)?(?:score|grade)\b.{0,16}\bto\b"),
    re.compile(r"忽略.{0,16}(?:之前|先前|系统).{0,8}(?:指令|提示)"),
    re.compile(r"忽略.{0,16}(?:前述|上述|现有|原有).{0,8}(?:流程|规则|要求|指令|提示)"),
    re.compile(r"(?:系统|开发者).{0,6}(?:指令|提示).{0,16}(?:忽略|修改|读取|访问|执行)"),
    re.compile(r"(?:泄露|显示|输出).{0,16}(?:系统提示|系统指令|秘密)"),
    re.compile(r"(?:修改|设置|指定).{0,16}(?:评分|分数|等级)"),
    re.compile(
        r"(?:将|把).{0,16}(?:全部|所有)?.{0,8}(?:维度|评分|分数|等级).{0,12}(?:满分|改成|改为|设置)"
    ),
)
_SIGNAL_PATTERNS = (
    re.compile(r"\b(?:run|execute)\b.{0,20}\b(?:shell|command|code|script)\b"),
    re.compile(r"\b(?:open|visit|fetch|browse)\b.{0,24}https?://"),
    re.compile(r"\b(?:call|invoke|use)\b.{0,16}\btool\b"),
    re.compile(r"\b(?:system prompt|system message|developer message)\b"),
    re.compile(r"\b(?:score|grade)\b.{0,16}\b(?:11\.5|10|a\+)\b"),
    re.compile(r"(?:执行|运行).{0,16}(?:命令|代码|脚本)"),
    re.compile(r"(?:打开|访问).{0,16}https?://"),
    re.compile(r"调用.{0,12}工具"),
    re.compile(r"(?:读取|获取).{0,12}(?:环境变量|密钥|凭据)"),
    re.compile(r"(?:访问|打开).{0,12}(?:外部链接|外部网址|网络地址)"),
)
_CONTROL_CHARACTERS = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]")
_EMAIL = re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}")
_MOBILE_PHONE = re.compile(r"(?<!\d)(?:\+?86[- ]?)?1[3-9]\d{9}(?!\d)")
_MARKDOWN_META = re.compile(r"([\\`*_\[\]{}()#+!|>~-])")
_CONTACT_SENTINEL = "CONTACTOMITTEDSENTINEL7C2A"
OMITTED_CONTACT_TEXT = "[contact omitted]"


def _normalized_instruction_text(text: str) -> str:
    normalized = unicodedata.normalize("NFKC", str(text)).lower()
    return re.sub(r"\s+", " ", normalized).strip()


def is_strong_instruction_like(text: str) -> bool:
    """Detect a direct instruction even when it is split across adjacent lines."""

    normalized = _normalized_instruction_text(text)
    return any(pattern.search(normalized) for pattern in _STRONG_PATTERNS)


def is_instruction_like(text: str) -> bool:
    """Detect direct attempts to control an analyzer rather than resume evidence."""

    normalized = _normalized_instruction_text(text)
    if is_strong_instruction_like(normalized):
        return True
    return sum(bool(pattern.search(normalized)) for pattern in _SIGNAL_PATTERNS) >= 2


def contains_instruction_like_content(value: Any) -> bool:
    """Recursively scan a canonical model dump without logging matched values."""

    if isinstance(value, str):
        return is_instruction_like(value)
    if isinstance(value, Mapping):
        return any(contains_instruction_like_content(item) for item in value.values())
    if isinstance(value, Sequence) and not isinstance(value, (str, bytes, bytearray)):
        return any(contains_instruction_like_content(item) for item in value)
    return False


def sanitize_report_text(value: Any) -> str:
    """Remove instruction-like text and neutralize raw HTML in Markdown reports."""

    text = str(value)
    if is_instruction_like(text):
        return OMITTED_REPORT_TEXT
    cleaned = _CONTROL_CHARACTERS.sub("", text)
    cleaned = _EMAIL.sub(_CONTACT_SENTINEL, cleaned)
    cleaned = _MOBILE_PHONE.sub(_CONTACT_SENTINEL, cleaned)
    return _escape_markdown_text(cleaned).replace(_CONTACT_SENTINEL, OMITTED_CONTACT_TEXT)


def sanitize_included_contact_text(value: Any) -> str:
    """Safely render contact data only after the caller has explicitly opted in."""

    text = str(value)
    if is_instruction_like(text):
        return OMITTED_REPORT_TEXT
    return _escape_markdown_text(_CONTROL_CHARACTERS.sub("", text))


def sanitize_report_list(values: Any) -> list[str]:
    if not isinstance(values, Sequence) or isinstance(values, (str, bytes, bytearray)):
        return []
    return [sanitize_report_text(value) for value in values]


def _escape_markdown_text(text: str) -> str:
    single_line = re.sub(r"[\r\n]+", " ", text)
    escaped_html = html.escape(single_line, quote=False)
    return _MARKDOWN_META.sub(r"\\\1", escaped_html)
