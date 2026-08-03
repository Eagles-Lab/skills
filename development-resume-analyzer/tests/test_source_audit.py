from __future__ import annotations

import json
from pathlib import Path

import pytest

from development_resume_analyzer.errors import SourceMappingAuditError
from development_resume_analyzer.models import Resume
from development_resume_analyzer.source_audit import (
    MAX_RAW_EXTRACTION_BYTES,
    _grounded,
    audit_source_mapping,
)


def raw_extraction(path: Path, text: str) -> Path:
    path.write_text(
        json.dumps(
            {
                "schema_version": "1.0",
                "content_trust": "untrusted",
                "source_sha256": "a" * 64,
                "full_text": text,
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    return path


def test_accepts_grounded_project_and_aliases(tmp_path: Path) -> None:
    raw = raw_extraction(
        tmp_path / "raw_extraction.json",
        "张三 示例大学 软件工程 本科 2027 项目经历 平台 使用 Python 和 K8s 完成部署",
    )
    resume = Resume.model_validate(
        {
            "basic_info": {
                "name": "张三",
                "school": "示例大学",
                "major": "软件工程",
                "degree": "本科",
                "graduation_year": 2027,
            },
            "projects": [
                {
                    "name": "平台",
                    "description": "使用 Python 和 Kubernetes 完成部署",
                    "tech_stack": ["Python", "Kubernetes"],
                }
            ],
            "skills": {
                "programming_languages": ["Python"],
                "engineering_devops": ["Kubernetes"],
            },
        }
    )
    result = audit_source_mapping(raw, resume)
    assert result.raw_source_sha256 == "a" * 64
    assert result.public_metadata()["passed"] is True


def test_rejects_ungrounded_and_incomplete_mapping(tmp_path: Path) -> None:
    raw = raw_extraction(
        tmp_path / "raw_extraction.json",
        "候选人甲 示例大学 软件工程 本科 2028 项目经历 平台 Python Docker",
    )
    resume = Resume.model_validate(
        {
            "basic_info": {
                "name": "候选人甲",
                "school": "软件工程 本科 示例学院",
                "major": "软件工程",
                "degree": "本科",
                "graduation_year": 2028,
            },
            "skills": {"programming_languages": ["Python", "Rust"]},
        }
    )
    with pytest.raises(SourceMappingAuditError) as error:
        audit_source_mapping(raw, resume)
    message = str(error.value)
    assert "raw_has_project_section_but_canonical_projects_empty" in message
    assert "canonical_school_contains_degree_text" in message
    assert "canonical_technology_not_grounded" in message


@pytest.mark.parametrize(
    "text",
    [
        "项目经历: 待补充 个人技能 Python",
        "暂无项目经历",
        "No project experience",
        "无实习经历",
        "No internship experience",
    ],
)
def test_explicit_absence_is_not_an_omission(text: str, tmp_path: Path) -> None:
    raw = raw_extraction(tmp_path / "raw_extraction.json", text)
    assert audit_source_mapping(raw, Resume()).public_metadata()["passed"] is True


def test_rejects_experience_created_from_empty_section(tmp_path: Path) -> None:
    raw = raw_extraction(tmp_path / "raw_extraction.json", "项目经历: 待补充 个人技能 Python")
    resume = Resume.model_validate({"projects": [{"description": "Python"}]})
    with pytest.raises(
        SourceMappingAuditError, match="canonical_projects_present_but_source_section_empty"
    ):
        audit_source_mapping(raw, resume)


def test_missing_contact_and_school_are_warnings(tmp_path: Path) -> None:
    raw = raw_extraction(
        tmp_path / "raw_extraction.json",
        "张三 示例大学 13800138000 candidate@example.com",
    )
    result = audit_source_mapping(raw, Resume.model_validate({"basic_info": {"name": "张三"}}))
    assert result.warning_codes == (
        "raw_has_email_but_canonical_email_missing",
        "raw_has_institution_but_canonical_school_missing",
        "raw_has_phone_but_canonical_phone_missing",
    )


def test_accepts_two_digit_graduation_cohort_and_nfkc(tmp_path: Path) -> None:
    raw = raw_extraction(
        tmp_path / "raw_extraction.json", "张三 示例大学 软件工程 28 届 项目经历 平台 Ｐｙｔｈｏｎ"
    )
    resume = Resume.model_validate(
        {
            "basic_info": {
                "name": "张三",
                "school": "示例大学",
                "major": "软件工程",
                "graduation_year": 2028,
            },
            "projects": [{"name": "平台", "tech_stack": ["Python"]}],
        }
    )
    assert audit_source_mapping(raw, resume).public_metadata()["passed"] is True


@pytest.mark.parametrize(
    ("value", "message"),
    [
        ([], "root must be an object"),
        (
            {"content_trust": "trusted", "source_sha256": "a" * 64, "full_text": "x"},
            "content_trust",
        ),
        ({"content_trust": "untrusted", "source_sha256": "a" * 64}, "full_text"),
        ({"content_trust": "untrusted", "source_sha256": "bad", "full_text": "x"}, "source_sha256"),
    ],
)
def test_rejects_malformed_raw_extraction(tmp_path: Path, value: object, message: str) -> None:
    raw = tmp_path / "raw_extraction.json"
    raw.write_text(json.dumps(value), encoding="utf-8")
    with pytest.raises(SourceMappingAuditError, match=message):
        audit_source_mapping(raw, Resume())


def test_rejects_missing_symlink_invalid_json_and_oversize(tmp_path: Path) -> None:
    with pytest.raises(SourceMappingAuditError, match="regular JSON"):
        audit_source_mapping(tmp_path / "missing.json", Resume())
    target = raw_extraction(tmp_path / "target.json", "text")
    link = tmp_path / "link.json"
    link.symlink_to(target)
    with pytest.raises(SourceMappingAuditError, match="regular JSON"):
        audit_source_mapping(link, Resume())
    invalid = tmp_path / "invalid.json"
    invalid.write_text("not-json")
    with pytest.raises(SourceMappingAuditError, match="JSONDecodeError"):
        audit_source_mapping(invalid, Resume())
    oversized = tmp_path / "oversized.json"
    with oversized.open("wb") as stream:
        stream.truncate(MAX_RAW_EXTRACTION_BYTES + 1)
    with pytest.raises(SourceMappingAuditError, match="25 MiB"):
        audit_source_mapping(oversized, Resume())


def test_rejects_ungrounded_experience_names_and_organization(tmp_path: Path) -> None:
    raw = raw_extraction(tmp_path / "raw_extraction.json", "项目经历 平台 工作经历 示例公司 Python")
    resume = Resume.model_validate(
        {
            "projects": [{"name": "其他平台", "tech_stack": ["Rust"]}],
            "internships": [{"organization": "其他公司", "name": "服务"}],
        }
    )
    with pytest.raises(SourceMappingAuditError) as error:
        audit_source_mapping(raw, resume)
    message = str(error.value)
    assert "canonical_experience_name_not_grounded" in message
    assert "canonical_experience_organization_not_grounded" in message
    assert "canonical_technology_not_grounded" in message


def test_grounding_helper_rejects_blank() -> None:
    assert not _grounded(" ", "raw text")
