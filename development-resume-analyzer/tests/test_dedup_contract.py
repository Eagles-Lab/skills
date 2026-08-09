from __future__ import annotations

import importlib
from pathlib import Path
from typing import Any

import pytest

PACKAGE_BY_SKILL = {
    "sre-resume-analyzer": "sre_resume_analyzer",
    "security-resume-analyzer": "security_resume_analyzer",
    "development-resume-analyzer": "development_resume_analyzer",
}
PACKAGE = PACKAGE_BY_SKILL[Path(__file__).resolve().parents[1].name]
DEDUP = importlib.import_module(f"{PACKAGE}.dedup")
DEDUP_CORE = importlib.import_module(f"{PACKAGE}.dedup_core")
MODELS = importlib.import_module(f"{PACKAGE}.models")


class RawResume:
    """Minimal model-dump adapter for defensive canonical-payload cases."""

    def __init__(self, payload: dict[str, Any]) -> None:
        self.payload = payload

    def model_dump(self, *, mode: str, exclude: set[str]) -> dict[str, Any]:
        assert mode == "json"
        return {key: value for key, value in self.payload.items() if key not in exclude}


def record(
    canonical: str,
    source: str,
    payload: dict[str, Any],
    *,
    kind: str,
) -> Any:
    return DEDUP.SourceRecord(
        path=Path(f"{canonical}.json"),
        canonical_sha256=canonical * 64,
        source_sha256=source * 64,
        source_identity_kind=kind,
        resume=MODELS.Resume.model_validate(payload),
    )


def test_raw_hash_identity_deduplicates_records_but_not_source_hashes() -> None:
    sources = [
        record("b", "a", {}, kind="raw_document_sha256"),
        record("c", "a", {}, kind="raw_document_sha256"),
    ]
    merged, failures = DEDUP.merge_candidates(sources)
    assert failures == []
    assert len(merged) == 1
    candidate = merged[0]
    assert candidate.source_hashes == ("a" * 64,)
    assert candidate.source_record_count == 2
    assert candidate.unique_source_count == 1
    assert candidate.deduplicated_source_count == 1
    assert candidate.aggregate_sha256 == DEDUP.aggregate_source_sha256(candidate.source_hashes)


def test_same_canonical_hash_alone_is_not_identity() -> None:
    sources = [
        record("a", "a", {}, kind="canonical_json_sha256"),
        record("a", "a", {}, kind="canonical_json_sha256"),
    ]
    merged, failures = DEDUP.merge_candidates(sources)
    assert merged == []
    assert len(failures) == 2
    assert all(item.fields == ("insufficient_identity",) for item in failures)


def test_transitive_group_detects_contact_conflict() -> None:
    shared = {"name": "候选甲", "school": "示例大学", "major": "计算机"}
    sources = [
        record(
            "a",
            "a",
            {"basic_info": {**shared, "contact": {"email": "same@example.test"}}},
            kind="canonical_json_sha256",
        ),
        record(
            "b",
            "b",
            {
                "basic_info": {
                    **shared,
                    "contact": {"email": "same@example.test", "phone": "13800000000"},
                }
            },
            kind="canonical_json_sha256",
        ),
        record(
            "c",
            "c",
            {
                "basic_info": {
                    **shared,
                    "contact": {"email": "other@example.test", "phone": "13800000000"},
                }
            },
            kind="canonical_json_sha256",
        ),
    ]
    merged, failures = DEDUP.merge_candidates(sources)
    assert merged == []
    assert len(failures) == 1
    assert failures[0].fields == ("contact.email",)


def test_multiple_explicit_resume_ids_fail_the_group() -> None:
    sources = [
        record(
            "a",
            "a",
            {
                "resume_id": "first",
                "basic_info": {"contact": {"email": "same@example.test"}},
            },
            kind="canonical_json_sha256",
        ),
        record(
            "b",
            "b",
            {
                "resume_id": "second",
                "basic_info": {"contact": {"email": "same@example.test"}},
            },
            kind="canonical_json_sha256",
        ),
    ]
    merged, failures = DEDUP.merge_candidates(sources)
    assert merged == []
    assert failures[0].fields == ("resume_id",)


def test_primary_selection_fills_missing_values_without_overwrite() -> None:
    rich = record(
        "b",
        "b",
        {
            "basic_info": {
                "name": "候选乙",
                "school": "示例大学",
                "contact": {"email": "same@example.test"},
            },
            "skills": {"programming_languages": ["Python", "Go"]},
        },
        kind="canonical_json_sha256",
    )
    sparse = record(
        "a",
        "a",
        {
            "resume_id": "preserved",
            "basic_info": {
                "name": "候选乙",
                "contact": {"email": "same@example.test", "phone": "13800000000"},
            },
            "skills": {"programming_languages": ["Rust"]},
        },
        kind="canonical_json_sha256",
    )
    merged, failures = DEDUP.merge_candidates([sparse, rich])
    assert failures == []
    candidate = merged[0]
    assert candidate.primary_sha256 == "b" * 64
    assert candidate.resume.resume_id == "preserved"
    assert candidate.resume.basic_info.contact.phone == "13800000000"
    assert candidate.resume.skills.programming_languages == ["Python", "Go"]
    assert any(item["resolution"] == "kept_primary" for item in candidate.conflicts)


def test_singleton_primary_collapses_exact_duplicate_experience() -> None:
    project = {
        "name": "共享项目",
        "duration": "2025",
        "description": "使用 Python 完成开发",
        "tech_stack": ["Python"],
    }
    merged, failures = DEDUP.merge_candidates(
        [record("a", "a", {"projects": [project, project]}, kind="canonical_json_sha256")]
    )

    assert failures == []
    assert len(merged) == 1
    assert len(merged[0].resume.projects) == 1


def test_duration_only_experiences_merge_only_when_exactly_equal() -> None:
    contact = {"email": "same@example.test"}
    first = {
        "duration": "2025",
        "description": "使用 Python 构建后端服务",
        "tech_stack": ["Python"],
    }
    second = {
        "duration": "2025",
        "description": "使用 Go 构建客户端工具",
        "tech_stack": ["Go"],
    }
    merged, failures = DEDUP.merge_candidates(
        [
            record(
                "a",
                "a",
                {"basic_info": {"contact": contact}, "projects": [first, first]},
                kind="canonical_json_sha256",
            ),
            record(
                "b",
                "b",
                {"basic_info": {"contact": contact}, "projects": [second]},
                kind="canonical_json_sha256",
            ),
        ]
    )

    assert failures == []
    assert len(merged) == 1
    assert len(merged[0].resume.projects) == 2
    assert {item.description for item in merged[0].resume.projects} == {
        first["description"],
        second["description"],
    }


@pytest.mark.parametrize("collection", ("projects", "security_activities"))
def test_unnamed_same_organization_and_duration_records_stay_distinct(collection: str) -> None:
    if PACKAGE == "sre_resume_analyzer" or (
        collection == "security_activities" and PACKAGE != "security_resume_analyzer"
    ):
        pytest.skip("collection shape is not available in this analyzer")
    contact = {"email": "same@example.test"}
    first = {
        "organization": "示例实验室",
        "duration": "2025",
        "description": "使用 Python 构建后端服务",
        "tech_stack": ["Python"],
    }
    second = {
        "organization": "示例实验室",
        "duration": "2025",
        "description": "使用 Go 构建客户端工具",
        "tech_stack": ["Go"],
    }
    merged, failures = DEDUP.merge_candidates(
        [
            record(
                "a",
                "a",
                {"basic_info": {"contact": contact}, collection: [first]},
                kind="canonical_json_sha256",
            ),
            record(
                "b",
                "b",
                {"basic_info": {"contact": contact}, collection: [second]},
                kind="canonical_json_sha256",
            ),
        ]
    )

    assert failures == []
    assert len(merged) == 1
    records = getattr(merged[0].resume, collection)
    assert len(records) == 2
    assert {item.description for item in records} == {
        first["description"],
        second["description"],
    }


def test_internship_organization_and_duration_remain_a_strong_key() -> None:
    organization_field = "company" if PACKAGE == "sre_resume_analyzer" else "organization"
    contact = {"email": "same@example.test"}
    first = {
        organization_field: "示例公司",
        "duration": "2025",
        "description": "负责自动化平台",
    }
    second = {**first, "tech_stack": ["Python"]}
    merged, failures = DEDUP.merge_candidates(
        [
            record(
                "a",
                "a",
                {"basic_info": {"contact": contact}, "internships": [first]},
                kind="canonical_json_sha256",
            ),
            record(
                "b",
                "b",
                {"basic_info": {"contact": contact}, "internships": [second]},
                kind="canonical_json_sha256",
            ),
        ]
    )

    assert failures == []
    assert len(merged[0].resume.internships) == 1
    assert merged[0].resume.internships[0].tech_stack == ["Python"]


def test_similarity_and_grouping_are_symmetric_under_source_hash_order() -> None:
    shared = {
        "name": "候选甲",
        "school": "示例大学",
        "major": "计算机",
        "graduation_year": 2027,
    }
    left = {
        "basic_info": shared,
        "projects": [{"description": "dcbcacacdacbbccabdbadcacaabcbd"}],
    }
    right = {
        "basic_info": shared,
        "projects": [{"description": "dcbcacadacbdccabdbaacdcadbadbbd"}],
    }
    left_resume = MODELS.Resume.model_validate(left)
    right_resume = MODELS.Resume.model_validate(right)

    assert DEDUP.canonical_similarity(left_resume, right_resume) == DEDUP.canonical_similarity(
        right_resume, left_resume
    )
    assert not DEDUP.same_candidate(left_resume, right_resume)
    first, first_failures = DEDUP.merge_candidates(
        [
            record("a", "a", left, kind="canonical_json_sha256"),
            record("b", "b", right, kind="canonical_json_sha256"),
        ]
    )
    second, second_failures = DEDUP.merge_candidates(
        [
            record("b", "b", left, kind="canonical_json_sha256"),
            record("a", "a", right, kind="canonical_json_sha256"),
        ]
    )
    assert (len(first), len(first_failures)) == (len(second), len(second_failures)) == (2, 0)


def test_similarity_preserves_project_field_associations() -> None:
    basic_info = {
        "name": "候选甲",
        "school": "示例大学",
        "major": "计算机",
        "graduation_year": 2027,
    }
    left = MODELS.Resume.model_validate(
        {
            "basic_info": basic_info,
            "projects": [
                {
                    "name": "课程设计",
                    "role": "后端",
                    "duration": "2024",
                    "description": "使用 Python 构建服务",
                    "tech_stack": ["Python"],
                },
                {
                    "name": "毕业设计",
                    "role": "客户端",
                    "duration": "2025",
                    "description": "使用 Go 构建工具",
                    "tech_stack": ["Go"],
                },
            ],
        }
    )
    right = MODELS.Resume.model_validate(
        {
            "basic_info": basic_info,
            "projects": [
                {
                    "name": "课程设计",
                    "role": "客户端",
                    "duration": "2024",
                    "description": "使用 Go 构建工具",
                    "tech_stack": ["Go"],
                },
                {
                    "name": "毕业设计",
                    "role": "后端",
                    "duration": "2025",
                    "description": "使用 Python 构建服务",
                    "tech_stack": ["Python"],
                },
            ],
        }
    )

    assert DEDUP.canonical_similarity(left, right) < 0.80
    assert not DEDUP.same_candidate(left, right)


def test_similarity_preserves_value_slots_within_a_project() -> None:
    basic_info = {
        "name": "候选甲",
        "school": "示例大学",
        "major": "计算机",
        "graduation_year": 2027,
    }
    left = MODELS.Resume.model_validate(
        {
            "basic_info": basic_info,
            "projects": [
                {
                    "name": "课程设计",
                    "duration": "2025",
                    "role": "后端开发负责人",
                    "description": "使用 Python 构建监控告警服务",
                }
            ],
        }
    )
    right = MODELS.Resume.model_validate(
        {
            "basic_info": basic_info,
            "projects": [
                {
                    "name": "课程设计",
                    "duration": "2025",
                    "role": "使用 Python 构建监控告警服务",
                    "description": "后端开发负责人",
                }
            ],
        }
    )

    assert DEDUP.canonical_similarity(left, right) < 0.80
    assert not DEDUP.same_candidate(left, right)


def test_similarity_normalization_and_pruning_are_default_free() -> None:
    for empty in (None, "", " \t", "other", "UNKNOWN"):
        assert DEDUP_CORE._normalize_similarity_scalar(empty) is None
    assert DEDUP_CORE._normalize_similarity_scalar(" \uff30ython \n") == "python"
    assert DEDUP_CORE._prune_similarity_value(
        {
            "empty": None,
            "nested": {"blank": " ", "kept": " \uff30ython "},
            "values": [None, "Go", "go", {}, []],
        }
    ) == {"nested": {"kept": "python"}, "values": ["go"]}


def test_public_fact_coverage_counts_a_populated_resume() -> None:
    resume = MODELS.Resume.model_validate({"projects": [{"name": "示例项目"}]})

    assert DEDUP.fact_coverage(resume) > 0


def test_similarity_handles_nested_nonexperience_value_slots() -> None:
    left = RawResume(
        {
            "resume_id": "ignored",
            "basic_info": {"name": "identity-is-excluded"},
            "portfolio": {
                "empty_mapping": {"value": "unknown"},
                "empty_list": [None, "", "other", "unknown"],
                "facts": {"blank": None, "language": " \uff30ython "},
                "tags": [None, "Go", "go", {"label": "Service"}],
            },
        }
    )
    right = RawResume(
        {
            "portfolio": {
                "tags": [{"label": "service"}, "GO"],
                "facts": {"language": "python", "blank": ""},
                "empty_list": [],
                "empty_mapping": {"value": None},
            },
            "basic_info": {},
        }
    )

    assert DEDUP_CORE._similarity_payload(left) == DEDUP_CORE._similarity_payload(right)
    assert DEDUP.canonical_similarity(left, right) == 1.0


def test_similarity_ignores_invalid_or_empty_experience_entries() -> None:
    resume = RawResume(
        {
            "basic_info": {},
            "projects": [None, "not-a-record", {}, {"description": "other"}],
        }
    )

    assert DEDUP_CORE._similarity_payload(resume) == ()
    assert DEDUP.canonical_similarity(resume, resume) == 0.0


def test_similarity_orders_strong_and_weak_records_deterministically() -> None:
    strong_a = {"name": "项目甲", "duration": "2024", "description": "强记录甲"}
    strong_b = {"name": "项目乙", "duration": "2025", "description": "强记录乙"}
    weak_a = {"duration": "2025", "description": "弱记录甲"}
    weak_b = {"description": "弱记录乙"}
    left = MODELS.Resume.model_validate({"projects": [weak_b, strong_b, weak_a, strong_a, weak_a]})
    right = MODELS.Resume.model_validate({"projects": [strong_a, weak_a, strong_b, weak_b]})

    assert DEDUP_CORE._similarity_payload(left) == DEDUP_CORE._similarity_payload(right)
    assert DEDUP.canonical_similarity(left, right) == 1.0


def test_unknown_experience_collection_never_has_a_strong_key() -> None:
    assert not DEDUP_CORE._has_strong_experience_key(
        ("organization", "name", "duration"), "certifications"
    )


def test_duplicate_padding_cannot_select_a_weaker_primary() -> None:
    contact = {"email": "same@example.test"}
    repeated = {"name": "重复项目", "duration": "2025", "description": "重复事实"}
    padded = {
        "basic_info": {"contact": contact},
        "projects": [repeated, repeated, repeated],
        "skills": {"programming_languages": ["Rust"]},
    }
    richer = {
        "basic_info": {"contact": contact},
        "projects": [
            {"name": "项目甲", "description": "事实甲"},
            {"name": "项目乙", "description": "事实乙"},
        ],
        "skills": {"programming_languages": ["Python", "Go"]},
    }

    merged, failures = DEDUP.merge_candidates(
        [
            record("a", "a", padded, kind="canonical_json_sha256"),
            record("b", "b", richer, kind="canonical_json_sha256"),
        ]
    )

    assert failures == []
    assert merged[0].primary_sha256 == "b" * 64
    assert merged[0].resume.skills.programming_languages == ["Python", "Go"]


def test_mixed_identity_kinds_are_rejected() -> None:
    sources = [
        record("a", "a", {}, kind="canonical_json_sha256"),
        record("b", "b", {}, kind="raw_document_sha256"),
    ]
    with pytest.raises(ValueError, match="exactly one source identity kind"):
        DEDUP.merge_candidates(sources)


def test_invalid_hashes_fail_closed_and_conflict_counters_are_distinct() -> None:
    with pytest.raises(ValueError, match="canonical_sha256"):
        record("x", "a", {}, kind="canonical_json_sha256")
    with pytest.raises(ValueError, match="source_sha256"):
        record("a", "x", {}, kind="canonical_json_sha256")
    with pytest.raises(ValueError, match="source hashes"):
        DEDUP.aggregate_source_sha256(())
    conflict = DEDUP.IdentityConflictError(("a" * 64, "a" * 64), ("name",), source_record_count=3)
    assert conflict.unique_source_count == 1
    assert conflict.deduplicated_source_count == 2


def test_phone_normalization_preserves_country_identity_and_ignores_extensions() -> None:
    domestic = "13800000000"
    assert DEDUP.normalize_phone(f"+86 {domestic}") == f"cn:{domestic}"
    assert DEDUP.normalize_phone(f"0086 {domestic}") == f"cn:{domestic}"
    assert DEDUP.normalize_phone(f"{domestic} ext 123") == f"cn:{domestic}"
    assert DEDUP.normalize_phone(f"+1 {domestic}") == f"intl:+1{domestic}"
    assert DEDUP.normalize_phone(f"+44 {domestic}") == f"intl:+44{domestic}"
    assert DEDUP.normalize_phone(f"+1 {domestic}") != DEDUP.normalize_phone(f"+86 {domestic}")
    assert DEDUP.normalize_phone("+86 12800000000") == "intl:+8612800000000"
    assert DEDUP.normalize_phone("0086 11111111111") is None
    assert DEDUP.normalize_phone("0086 12800000000") == "intl:+8612800000000"
    assert DEDUP.normalize_phone("0044 12345678") == "intl:+4412345678"
    for ambiguous_local in ("1234567", "12345678", "123456789"):
        assert DEDUP.normalize_phone(ambiguous_local) is None
    assert DEDUP.normalize_phone("4001234567") == "local:4001234567"
    for placeholder in ("0000000", "00000000000", "11111111111", "+86 11111111111"):
        assert DEDUP.normalize_phone(placeholder) is None


def test_email_normalization_rejects_ambiguous_invalid_addresses() -> None:
    assert DEDUP.normalize_email(" A@EXAMPLE.TEST ") == "a@example.test"
    for invalid in (
        "a@b..com",
        ".a@example.com",
        "a.@example.com",
        "a@example-.com",
        "a@-example.com",
        "a@example.123",
    ):
        assert DEDUP.normalize_email(invalid) is None


def test_bridge_record_joins_two_existing_identity_groups() -> None:
    sources = [
        record(
            "a",
            "a",
            {"basic_info": {"contact": {"email": "same@example.test"}}},
            kind="canonical_json_sha256",
        ),
        record(
            "b",
            "b",
            {"basic_info": {"contact": {"phone": "13800000000"}}},
            kind="canonical_json_sha256",
        ),
        record(
            "c",
            "c",
            {
                "basic_info": {
                    "contact": {
                        "email": "same@example.test",
                        "phone": "13800000000",
                    }
                }
            },
            kind="canonical_json_sha256",
        ),
    ]
    merged, failures = DEDUP.merge_candidates(sources)
    assert failures == []
    assert len(merged) == 1
    assert merged[0].source_record_count == 3


def test_grouped_identity_metadata_conflict_is_explicit() -> None:
    sources = [
        record(
            "a",
            "a",
            {
                "basic_info": {
                    "school": "第一大学",
                    "contact": {"email": "same@example.test"},
                }
            },
            kind="canonical_json_sha256",
        ),
        record(
            "b",
            "b",
            {
                "basic_info": {
                    "school": "第二大学",
                    "contact": {"email": "same@example.test"},
                }
            },
            kind="canonical_json_sha256",
        ),
    ]
    merged, failures = DEDUP.merge_candidates(sources)
    assert merged == []
    assert failures[0].fields == ("school",)


def test_experiences_merge_by_identity_key_and_keep_primary_conflicts() -> None:
    primary = record(
        "a",
        "a",
        {
            "basic_info": {"contact": {"email": "same@example.test"}},
            "projects": [
                {"name": "共享项目", "duration": "2025", "description": "主记录描述"},
                {"description": "无键主记录"},
            ],
        },
        kind="canonical_json_sha256",
    )
    secondary = record(
        "b",
        "b",
        {
            "basic_info": {"contact": {"email": "same@example.test"}},
            "projects": [
                {"name": "共享项目", "duration": "2025", "description": "次记录描述"},
                {"description": "无键次记录"},
                {"name": "新增项目", "duration": "2024"},
            ],
        },
        kind="canonical_json_sha256",
    )
    merged, failures = DEDUP.merge_candidates([primary, secondary])
    assert failures == []
    candidate = merged[0]
    shared = next(item for item in candidate.resume.projects if item.name == "共享项目")
    assert shared.description in {"主记录描述", "次记录描述"}
    assert len(candidate.resume.projects) == 4
    assert any(item["resolution"] == "kept_primary" for item in candidate.conflicts)
