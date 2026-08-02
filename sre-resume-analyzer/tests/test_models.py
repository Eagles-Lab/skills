from __future__ import annotations

import pytest
from pydantic import ValidationError

from sre_resume_analyzer.models import Resume


def test_empty_canonical_is_valid_and_normalized():
    resume = Resume.model_validate({})
    assert resume.basic_info.name is None
    assert resume.internships == []
    assert resume.projects == []
    assert resume.skills.ai_tools == []


def test_nullable_top_level_fact_groups_normalize_to_empty_defaults():
    resume = Resume.model_validate(
        {"basic_info": None, "internships": None, "projects": None, "skills": None}
    )
    assert resume.basic_info.name is None
    assert resume.internships == []
    assert resume.projects == []
    assert resume.skills.ai_tools == []


def test_blank_optional_text_and_null_lists_are_normalized():
    resume = Resume.model_validate(
        {
            "basic_info": {"name": "  ", "school": " 示例大学 "},
            "skills": {"programming_languages": None, "ai_tools": [" Cursor "]},
            "projects": [{"name": " ", "tech_stack": None, "achievements": None}],
        }
    )
    assert resume.basic_info.name is None
    assert resume.basic_info.school == "示例大学"
    assert resume.skills.programming_languages == []
    assert resume.skills.ai_tools == ["Cursor"]
    assert resume.projects[0].name is None


@pytest.mark.parametrize(
    "value",
    [
        {"position": "SRE"},
        {"skills": ["Python"]},
        {"projects": [{"technologies": ["Docker"]}]},
        {"basic_info": {"graduation_year": "2027"}},
        {"internships": {}},
        {"skills": {"programming_languages": "Python"}},
    ],
)
def test_v2_unknown_and_wrong_types_fail_closed(value):
    with pytest.raises(ValidationError):
        Resume.model_validate(value)


@pytest.mark.parametrize("resume_id", ["../x", "/tmp/x", "a/b", "a\x00b", "", "a" * 65])
def test_resume_id_remains_strict_internal_identifier(resume_id):
    with pytest.raises(ValidationError):
        Resume.model_validate({"resume_id": resume_id})
