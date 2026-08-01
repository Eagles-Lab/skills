from copy import deepcopy

import pytest
from pydantic import ValidationError

from sre_resume_analyzer.models import SCHEMA_VERSION, Resume


def canonical_resume():
    return {
        "resume_id": "candidate_001",
        "basic_info": {
            "name": "Candidate",
            "school": "Example University",
            "major": "Computer Science",
            "degree": "Bachelor",
            "graduation_year": 2026,
            "contact": {"phone": "000-0000", "email": "candidate@example.invalid"},
        },
        "internships": [],
        "projects": [],
        "skills": {
            "programming_languages": ["Python"],
            "monitoring_tools": ["Prometheus"],
            "container_tech": ["Kubernetes"],
            "cloud_platforms": ["AWS"],
            "cicd_tools": ["GitHub Actions"],
        },
    }


def test_canonical_v3_model_accepts_exact_contract():
    resume = Resume.model_validate(canonical_resume())

    assert resume.resume_id == "candidate_001"
    assert resume.basic_info.graduation_year == 2026
    assert SCHEMA_VERSION == "3.0"


@pytest.mark.parametrize(
    "mutator",
    [
        lambda data: data["projects"].append(
            {
                "name": "legacy",
                "position": "owner",
                "duration": "2025",
                "description": "legacy fields",
                "technologies": ["Prometheus"],
                "achievements": [],
            }
        ),
        lambda data: data.update({"skills": ["Prometheus"]}),
        lambda data: data.update({"unknown": True}),
        lambda data: data.update({"resume_id": "../escape"}),
        lambda data: data["basic_info"].update({"graduation_year": "2026"}),
    ],
)
def test_v2_extra_and_non_strict_fields_are_rejected(mutator):
    value = deepcopy(canonical_resume())
    mutator(value)

    with pytest.raises(ValidationError):
        Resume.model_validate(value)


def test_generated_json_schema_forbids_extra_fields():
    schema = Resume.model_json_schema()

    assert schema["additionalProperties"] is False
    assert schema["$defs"]["Project"]["additionalProperties"] is False
    assert set(schema["required"]) == {"basic_info", "internships", "projects", "skills"}


def test_nested_strings_are_trimmed_and_empty_list_items_are_rejected():
    value = canonical_resume()
    value["skills"]["monitoring_tools"] = ["  Prometheus  "]
    resume = Resume.model_validate(value)
    assert resume.skills.monitoring_tools == ["Prometheus"]

    value["skills"]["monitoring_tools"] = ["   "]
    with pytest.raises(ValidationError):
        Resume.model_validate(value)
