from __future__ import annotations

from pathlib import Path

from development_resume_analyzer.dedup import (
    ResumeSource,
    canonical_similarity,
    fact_coverage,
    merge_candidates,
    normalize_email,
    normalize_phone,
    same_candidate,
)
from development_resume_analyzer.models import Resume


def source(digest: str, payload: dict[str, object]) -> ResumeSource:
    return ResumeSource(Path(digest + ".json"), digest * 64, Resume.model_validate(payload))


def person(
    name: str = "张三",
    email: str | None = None,
    school: str = "示例大学",
    description: str = "使用 Python 编写开发工具",
) -> dict[str, object]:
    return {
        "basic_info": {
            "name": name,
            "school": school,
            "major": "计算机",
            "graduation_year": 2027,
            "contact": {"email": email} if email else None,
        },
        "projects": [
            {
                "organization": "实验室",
                "name": "项目",
                "duration": "2026",
                "description": description,
            }
        ],
    }


def test_contact_normalization() -> None:
    assert normalize_email(" A@EXAMPLE.TEST ") == "a@example.test"
    assert normalize_phone("+86 138-0000-0000") == "13800000000"
    assert normalize_phone("123") is None


def test_email_identifies_same_candidate() -> None:
    assert same_candidate(
        Resume.model_validate(person(email="A@example.test")),
        Resume.model_validate(person(email="a@example.test", description="不同描述")),
    )


def test_phone_identifies_same_candidate() -> None:
    left = Resume.model_validate({"basic_info": {"contact": {"phone": "+86 138-0000-0000"}}})
    right = Resume.model_validate({"basic_info": {"contact": {"phone": "13800000000"}}})
    assert same_candidate(left, right)


def test_name_alone_never_merges_and_different_contacts_block_fallback() -> None:
    left = Resume.model_validate({"basic_info": {"name": "同名"}})
    right = Resume.model_validate({"basic_info": {"name": "同名"}})
    assert not same_candidate(left, right)
    assert not same_candidate(
        Resume.model_validate(person(email="a@example.test")),
        Resume.model_validate(person(email="b@example.test")),
    )


def test_identity_plus_similarity_fallback_without_contacts() -> None:
    left = Resume.model_validate(person())
    right = Resume.model_validate(person(description="使用 Python 编写开发工具并测试"))
    assert canonical_similarity(left, right) >= 0.80
    assert same_candidate(left, right)


def test_primary_is_highest_coverage_then_hash_and_output_uses_all_hashes() -> None:
    sparse = source("a", {"basic_info": {"name": "张三"}, "resume_id": "one"})
    rich = source("b", person(email="same@example.test"))
    # Make exact contact available on sparse without increasing it beyond rich.
    sparse = source(
        "a",
        {
            "basic_info": {"name": "张三", "contact": {"email": "same@example.test"}},
            "resume_id": "one",
        },
    )
    merged, failures = merge_candidates([sparse, rich])
    assert failures == []
    assert len(merged) == 1
    assert merged[0].primary_sha256 == "b" * 64
    assert merged[0].deduplicated_source_count == 1
    assert merged[0].output_name.startswith("张三-")
    assert fact_coverage(merged[0].resume) >= fact_coverage(sparse.resume)


def test_identity_conflict_fails_manual_confirmation() -> None:
    left = source("a", person(email="same@example.test", school="学校甲"))
    right = source("b", person(email="same@example.test", school="学校乙"))
    merged, failures = merge_candidates([left, right])
    assert merged == []
    assert failures[0].fields == ("school",)


def test_description_conflict_keeps_primary_and_records_conflict() -> None:
    rich = person(
        email="same@example.test", description="负责使用 Python 编写开发工具并完成单元测试"
    )
    rich["skills"] = {"programming_languages": ["Python"]}
    secondary = person(email="same@example.test", description="另一份不一致描述")
    merged, _ = merge_candidates([source("a", rich), source("b", secondary)])
    result = merged[0]
    assert result.resume.projects[0].description == rich["projects"][0]["description"]  # type: ignore[index]
    description_conflicts = [
        item for item in result.conflicts if item["path"].endswith("description")
    ]
    assert len(description_conflicts) == 1


def test_exact_duplicate_experience_does_not_double_count() -> None:
    payload = person(email="same@example.test")
    merged, _ = merge_candidates([source("a", payload), source("b", payload)])
    assert len(merged[0].resume.projects) == 1


def test_secondary_unique_experience_is_added_once() -> None:
    first = person(email="same@example.test")
    second = person(email="same@example.test")
    second["projects"].append(  # type: ignore[union-attr]
        {
            "organization": "实验室",
            "name": "辅助项目",
            "duration": "2026",
            "description": "实现 Go 命令行工具",
        }
    )
    merged, _ = merge_candidates([source("a", first), source("b", second)])
    assert len(merged[0].resume.projects) == 2


def test_secondary_contact_fills_missing_nested_field() -> None:
    left = person(email="same@example.test")
    left["skills"] = {"programming_languages": ["Python", "Go"]}
    right = person(email="same@example.test")
    right["basic_info"]["contact"]["phone"] = "13800000000"  # type: ignore[index]
    merged, _ = merge_candidates([source("a", left), source("b", right)])
    assert merged[0].resume.basic_info.contact is not None
    assert merged[0].resume.basic_info.contact.phone == "13800000000"
