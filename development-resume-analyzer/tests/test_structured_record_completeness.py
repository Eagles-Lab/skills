from __future__ import annotations

import json
from pathlib import Path

import pytest

from development_resume_analyzer.errors import SourceMappingAuditError
from development_resume_analyzer.models import Resume
from development_resume_analyzer.source_audit import audit_source_mapping


def _raw(path: Path, text: str) -> Path:
    path.write_text(
        json.dumps(
            {
                "content_trust": "untrusted",
                "source_sha256": "a" * 64,
                "full_text": text,
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    return path


def test_markdown_peer_heading_rejects_unmapped_project(tmp_path: Path) -> None:
    raw = _raw(
        tmp_path / "raw.json",
        "## 项目经历\n### 监控平台\n实现采集\n### 发布平台\n实现部署",
    )
    resume = Resume.model_validate({"projects": [{"name": "监控平台", "description": "实现采集"}]})

    with pytest.raises(SourceMappingAuditError, match=r"raw_record_not_mapped@/projects"):
        audit_source_mapping(raw, resume)


def test_markdown_nested_detail_heading_does_not_split_project(tmp_path: Path) -> None:
    raw = _raw(
        tmp_path / "raw.json",
        "## 项目经历\n### 监控平台\n#### 项目背景\n实现采集\n#### 项目成果\n完成验证",
    )
    resume = Resume.model_validate(
        {
            "projects": [
                {
                    "name": "监控平台",
                    "description": "实现采集",
                    "achievements": ["完成验证"],
                }
            ]
        }
    )

    assert audit_source_mapping(raw, resume).public_metadata()["passed"] is True


def test_bold_peer_heading_rejects_unmapped_project(tmp_path: Path) -> None:
    raw = _raw(
        tmp_path / "raw.json",
        "项目经历\n**监控平台**\n实现采集\n**发布平台**\n实现部署",
    )
    resume = Resume.model_validate({"projects": [{"name": "监控平台", "description": "实现采集"}]})

    with pytest.raises(SourceMappingAuditError, match=r"raw_record_not_mapped@/projects"):
        audit_source_mapping(raw, resume)


def test_raw_record_body_rejects_anchor_only_mapping(tmp_path: Path) -> None:
    raw = _raw(tmp_path / "raw.json", "## 项目经历\n### 监控平台\n实现采集")
    resume = Resume.model_validate({"projects": [{"name": "监控平台"}]})

    with pytest.raises(
        SourceMappingAuditError,
        match=r"canonical_record_details_missing@/projects/0",
    ):
        audit_source_mapping(raw, resume)


def test_plain_text_record_body_rejects_anchor_only_mapping(tmp_path: Path) -> None:
    raw = _raw(tmp_path / "raw.json", "项目经历\n监控平台 2025\n实现采集")
    resume = Resume.model_validate({"projects": [{"name": "监控平台", "duration": "2025"}]})

    with pytest.raises(
        SourceMappingAuditError,
        match=r"canonical_record_details_missing@/projects/0",
    ):
        audit_source_mapping(raw, resume)


def test_role_and_duration_do_not_satisfy_substantive_record_body(tmp_path: Path) -> None:
    raw = _raw(
        tmp_path / "raw.json",
        "## 项目经历\n### 监控平台 | 开发工程师 | 2025\n实现采集",
    )
    resume = Resume.model_validate(
        {"projects": [{"name": "监控平台", "role": "开发工程师", "duration": "2025"}]}
    )

    with pytest.raises(
        SourceMappingAuditError,
        match=r"canonical_record_details_missing@/projects/0",
    ):
        audit_source_mapping(raw, resume)


def test_plain_text_record_with_grounded_description_passes(tmp_path: Path) -> None:
    raw = _raw(tmp_path / "raw.json", "项目经历\n监控平台 2025\n实现采集")
    resume = Resume.model_validate(
        {"projects": [{"name": "监控平台", "duration": "2025", "description": "实现采集"}]}
    )

    assert audit_source_mapping(raw, resume).public_metadata()["passed"] is True


def test_multiline_description_can_ground_one_substantive_body_line(tmp_path: Path) -> None:
    raw = _raw(tmp_path / "raw.json", "## 项目经历\n### 监控平台\n#### 项目背景\n实现采集")
    resume = Resume.model_validate(
        {"projects": [{"name": "监控平台", "description": "项目背景\n实现采集"}]}
    )

    assert audit_source_mapping(raw, resume).public_metadata()["passed"] is True


def test_sparse_record_without_body_remains_valid(tmp_path: Path) -> None:
    raw = _raw(tmp_path / "raw.json", "项目经历\n监控平台")
    resume = Resume.model_validate({"projects": [{"name": "监控平台"}]})

    assert audit_source_mapping(raw, resume).public_metadata()["passed"] is True
