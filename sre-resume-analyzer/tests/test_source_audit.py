from __future__ import annotations

import json
from pathlib import Path

import pytest

from sre_resume_analyzer.errors import SourceMappingAuditError
from sre_resume_analyzer.models import Resume
from sre_resume_analyzer.source_audit import (
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


def test_rejects_incomplete_and_ungrounded_mapping(tmp_path: Path):
    raw = raw_extraction(
        tmp_path / "raw_extraction.json",
        (
            "候选人甲 示例科技大学 计算机科学与技术 本科 2028 项目竞赛经历 "
            "故障排查与恢复: Kubernetes 集群与业务连续性实战 "
            "Python Shell MySQL MongoDB Redis Ansible Docker Kubernetes Prometheus Zabbix"
        ),
    )
    resume = Resume.model_validate(
        {
            "basic_info": {
                "name": "候选人甲",
                "school": "计算机科学与技术 本科 计算机学院",
                "major": "计算机科学与技术",
                "degree": "本科",
                "graduation_year": 2028,
            },
            "projects": [],
            "skills": {
                "programming_languages": ["Python", "Go", "Shell", "SQL"],
                "monitoring_tools": ["Prometheus", "Zabbix"],
                "container_tech": ["Docker", "Kubernetes"],
                "cicd_tools": ["Ansible"],
            },
        }
    )

    with pytest.raises(SourceMappingAuditError) as error:
        audit_source_mapping(raw, resume)

    message = str(error.value)
    assert "raw_has_project_section_but_canonical_projects_empty" in message
    assert "canonical_school_contains_degree_text" in message
    assert "canonical_skill_not_grounded" in message


def test_accepts_grounded_project_and_latin_aliases(tmp_path: Path):
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
                "container_tech": ["Kubernetes"],
            },
        }
    )

    result = audit_source_mapping(raw, resume)

    assert result.raw_source_sha256 == "a" * 64
    assert result.public_metadata()["passed"] is True


def test_accepts_nfkc_equivalent_latin_source_text(tmp_path: Path):
    raw = raw_extraction(
        tmp_path / "raw_extraction.json",
        "项目经历 平台 使用 Ｐｙｔｈｏｎ",  # noqa: RUF001
    )
    resume = Resume.model_validate(
        {
            "projects": [{"name": "平台", "tech_stack": ["Python"]}],
            "skills": {"programming_languages": ["Python"]},
        }
    )

    assert audit_source_mapping(raw, resume).public_metadata()["passed"] is True


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
def test_explicit_absence_does_not_create_false_omission(text: str, tmp_path: Path):
    raw = raw_extraction(tmp_path / "raw_extraction.json", text)

    assert audit_source_mapping(raw, Resume.model_validate({})).public_metadata()["passed"] is True


def test_empty_internship_before_populated_project_is_not_an_omission(tmp_path: Path):
    raw = raw_extraction(tmp_path / "raw_extraction.json", "实习经历\n\n项目经历: 平台")
    resume = Resume.model_validate({"projects": [{"name": "平台"}]})

    assert audit_source_mapping(raw, resume).public_metadata()["passed"] is True


@pytest.mark.parametrize("heading", ["项目", "研究经历", "项目描述"])
def test_detects_alternate_project_section_headings(heading: str, tmp_path: Path):
    raw = raw_extraction(tmp_path / "raw_extraction.json", f"{heading}\n平台\n使用 Python")

    with pytest.raises(
        SourceMappingAuditError,
        match="raw_has_project_section_but_canonical_projects_empty",
    ):
        audit_source_mapping(raw, Resume.model_validate({}))


@pytest.mark.parametrize(
    ("text", "resume", "code"),
    [
        (
            "项目经历: 待补充 个人技能 Python",
            {"projects": [{"description": "Python"}]},
            "canonical_projects_present_but_source_section_empty",
        ),
        (
            "工作经验: 无 专业技能 Python",
            {"internships": [{"description": "Python"}]},
            "canonical_internships_present_but_source_section_empty",
        ),
    ],
)
def test_rejects_experience_created_from_empty_section(
    text: str, resume: dict[str, object], code: str, tmp_path: Path
):
    raw = raw_extraction(tmp_path / "raw_extraction.json", text)

    with pytest.raises(SourceMappingAuditError, match=code):
        audit_source_mapping(raw, Resume.model_validate(resume))


def test_missing_contact_is_a_warning_not_a_failure(tmp_path: Path):
    raw = raw_extraction(
        tmp_path / "raw_extraction.json",
        "张三 13800138000 candidate@example.com",
    )
    resume = Resume.model_validate({"basic_info": {"name": "张三"}})

    result = audit_source_mapping(raw, resume)

    assert result.warning_codes == (
        "raw_has_email_but_canonical_email_missing",
        "raw_has_phone_but_canonical_phone_missing",
    )


def test_accepts_two_digit_graduation_cohort(tmp_path: Path):
    raw = raw_extraction(tmp_path / "raw_extraction.json", "张三 示例大学 软件工程 28 届")
    resume = Resume.model_validate(
        {
            "basic_info": {
                "name": "张三",
                "school": "示例大学",
                "major": "软件工程",
                "graduation_year": 2028,
            }
        }
    )

    assert audit_source_mapping(raw, resume).public_metadata()["passed"] is True


def test_rejects_invalid_or_untrusted_raw_extraction(tmp_path: Path):
    raw = tmp_path / "raw_extraction.json"
    raw.write_text(json.dumps({"content_trust": "trusted", "full_text": "text"}))

    with pytest.raises(SourceMappingAuditError, match="content_trust"):
        audit_source_mapping(raw, Resume.model_validate({}))


@pytest.mark.parametrize(
    ("value", "message"),
    [
        ([], "root must be an object"),
        ({"content_trust": "untrusted", "source_sha256": "a" * 64}, "full_text"),
        (
            {"content_trust": "untrusted", "full_text": "text", "source_sha256": "bad"},
            "source_sha256",
        ),
    ],
)
def test_rejects_malformed_raw_extraction_payloads(tmp_path: Path, value: object, message: str):
    raw = tmp_path / "raw_extraction.json"
    raw.write_text(json.dumps(value), encoding="utf-8")

    with pytest.raises(SourceMappingAuditError, match=message):
        audit_source_mapping(raw, Resume.model_validate({}))


def test_rejects_missing_symlink_invalid_json_and_oversize_raw_files(tmp_path: Path):
    resume = Resume.model_validate({})
    with pytest.raises(SourceMappingAuditError, match="does not exist"):
        audit_source_mapping(tmp_path / "missing.json", resume)

    target = raw_extraction(tmp_path / "target.json", "text")
    link = tmp_path / "link.json"
    link.symlink_to(target)
    with pytest.raises(SourceMappingAuditError, match="regular file"):
        audit_source_mapping(link, resume)

    invalid = tmp_path / "invalid.json"
    invalid.write_text("not-json", encoding="utf-8")
    with pytest.raises(SourceMappingAuditError, match="JSONDecodeError"):
        audit_source_mapping(invalid, resume)

    oversize = tmp_path / "oversize.json"
    with oversize.open("wb") as stream:
        stream.truncate(MAX_RAW_EXTRACTION_BYTES + 1)
    with pytest.raises(SourceMappingAuditError, match="25 MiB"):
        audit_source_mapping(oversize, resume)


def test_reports_all_grounding_and_experience_contradictions(tmp_path: Path):
    raw = raw_extraction(
        tmp_path / "raw_extraction.json",
        "张三 示例大学 软件工程 本科 2027 项目经历 平台 工作经历 示例公司 Python",
    )
    resume = Resume.model_validate(
        {
            "basic_info": {
                "name": "李四",
                "school": "其他大学 硕士",
                "major": "通信工程",
                "degree": "博士",
                "graduation_year": 2028,
            },
            "projects": [
                {
                    "name": "其他平台",
                    "tech_stack": ["Rust"],
                }
            ],
            "internships": [
                {
                    "company": "其他公司",
                    "tech_stack": ["Terraform"],
                }
            ],
            "skills": {"programming_languages": ["Go"]},
        }
    )

    with pytest.raises(SourceMappingAuditError) as error:
        audit_source_mapping(raw, resume)

    message = str(error.value)
    for code in (
        "canonical_name_not_grounded",
        "canonical_major_not_grounded",
        "canonical_degree_not_grounded",
        "canonical_graduation_year_not_grounded",
        "canonical_school_contains_degree_text",
        "canonical_school_not_grounded",
        "canonical_project_name_not_grounded",
        "canonical_internship_company_not_grounded",
        "canonical_skill_not_grounded",
        "canonical_experience_technology_not_grounded",
    ):
        assert code in message


def test_detects_empty_internships_and_warns_for_missing_school(tmp_path: Path):
    raw = raw_extraction(
        tmp_path / "raw_extraction.json",
        "张三 示例大学 工作经历 示例公司",
    )
    resume = Resume.model_validate({"basic_info": {"name": "张三"}})

    with pytest.raises(SourceMappingAuditError) as error:
        audit_source_mapping(raw, resume)

    assert "raw_has_internship_section_but_canonical_internships_empty" in str(error.value)


def test_private_grounding_helper_rejects_blank_values():
    assert not _grounded(" ", "raw text")
