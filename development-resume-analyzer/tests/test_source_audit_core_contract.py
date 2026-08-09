from __future__ import annotations

import importlib
import json
import re
from pathlib import Path
from typing import Any

import pytest

PACKAGE_BY_SKILL = {
    "sre-resume-analyzer": "sre_resume_analyzer",
    "security-resume-analyzer": "security_resume_analyzer",
    "development-resume-analyzer": "development_resume_analyzer",
}
PACKAGE = PACKAGE_BY_SKILL[Path(__file__).resolve().parents[1].name]
CORE = importlib.import_module(f"{PACKAGE}.source_audit_core")


def write_raw(path: Path, payload: Any) -> Path:
    if isinstance(payload, bytes):
        path.write_bytes(payload)
    elif isinstance(payload, str):
        path.write_text(payload, encoding="utf-8")
    else:
        path.write_text(json.dumps(payload), encoding="utf-8")
    return path


@pytest.mark.parametrize(
    ("payload", "code"),
    [
        ("not-json", "raw_extraction_invalid_json"),
        ([], "raw_extraction_root_not_object"),
        (
            {"content_trust": "trusted", "source_sha256": "a" * 64, "full_text": "x"},
            "raw_extraction_trust_invalid",
        ),
        (
            {"content_trust": "untrusted", "source_sha256": "a" * 64, "full_text": ""},
            "raw_extraction_full_text_invalid",
        ),
        (
            {"content_trust": "untrusted", "source_sha256": "bad", "full_text": "x"},
            "raw_extraction_sha256_invalid",
        ),
        (b"\xff\xfe", "raw_extraction_unreadable"),
    ],
)
def test_raw_extraction_validation_is_sanitized(tmp_path: Path, payload: Any, code: str) -> None:
    source = write_raw(tmp_path / "raw.json", payload)
    with pytest.raises(ValueError, match=code):
        CORE.load_raw_extraction(source, ValueError)


def test_raw_extraction_rejects_missing_and_non_regular_paths(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="raw_extraction_missing"):
        CORE.load_raw_extraction(tmp_path / "missing.json", ValueError)
    directory = tmp_path / "directory"
    directory.mkdir()
    with pytest.raises(ValueError, match="raw_extraction_not_regular"):
        CORE.load_raw_extraction(directory, ValueError)


def test_raw_extraction_allows_regular_leaf_below_resolved_parent(tmp_path: Path) -> None:
    real = tmp_path / "real"
    real.mkdir()
    source = write_raw(
        real / "raw.json",
        {"content_trust": "untrusted", "source_sha256": "a" * 64, "full_text": "x"},
    )
    alias = tmp_path / "alias"
    alias.symlink_to(real, target_is_directory=True)
    assert CORE.load_raw_extraction(alias / source.name, ValueError).full_text == "x"


def test_grounding_primitives_cover_alias_and_boundary_modes() -> None:
    assert not CORE.fact_is_grounded("", "source")
    assert CORE.fact_is_grounded("Kubernetes", "K8s")
    assert not CORE.fact_is_grounded("Kubernetes", "K8s", aliases=False)
    assert CORE.fact_is_grounded("完成部署", "完成\uff0c\n部署", aliases=False)
    assert not CORE.fact_is_grounded("错误率从 3.0% 降到 1%", "错误率从 30% 降到 1%")
    assert not CORE.fact_is_grounded("版本 1.10", "版本 110")
    assert not CORE.fact_is_grounded("提升 50%", "提升 50")
    assert CORE.fact_is_grounded("提升 50%", "提升 50 %")
    assert CORE.fact_is_grounded("版本 1.10", "版本 1 . 10")
    assert CORE.fact_is_grounded("比例 1:10", "比例 1 : 10")
    assert CORE.fact_is_grounded("日期 2024-01", "日期 2024 - 01")
    assert not CORE.graduation_year_is_grounded(2027, "2027")
    assert not CORE.graduation_year_is_grounded(2027, "2027 年入学")
    assert not CORE.graduation_year_is_grounded(2027, "2027 年入学\uff0c预计 2031 年毕业")
    assert CORE.graduation_year_is_grounded(2027, "2027 届")
    assert CORE.graduation_year_is_grounded(2027, "27 届")
    assert CORE.graduation_year_is_grounded(2027, "预计 2027 年毕业")
    assert CORE.graduation_year_is_grounded(2027, "毕业时间\uff1a2027")
    assert not CORE.graduation_year_is_grounded(2027, "2023.09-2027.06")
    assert CORE.graduation_year_is_grounded(2027, "教育经历\n示例大学 2023-2027")
    assert not CORE.graduation_year_is_grounded(2027, "项目经历\n平台 2023-2027")
    assert not CORE.graduation_year_is_grounded(2027, "2028")
    assert not CORE.controlled_signal_is_grounded(
        CORE.FactClaim("/category", "course", match_kind="controlled"),
        "课程设计",
    )
    claim = CORE.FactClaim(
        "/category",
        "course",
        match_kind="controlled",
        candidates=("课程设计",),
        scope_text="本项目属于课程设计",
        scope_values=("本项目属于课程设计",),
        raw_scope_text="项目经历 本项目属于课程设计",
    )
    assert CORE.controlled_signal_is_grounded(claim, "项目经历 本项目属于课程设计")
    unrelated = CORE.FactClaim(
        "/category",
        "course",
        match_kind="controlled",
        candidates=("课程设计",),
        scope_text="普通平台项目",
        scope_values=("普通平台项目",),
        raw_scope_text="当前记录是普通平台项目",
    )
    assert not CORE.controlled_signal_is_grounded(
        unrelated, "其他经历是课程设计\uff1b当前记录是普通平台项目"
    )


def test_direct_facts_reject_dropped_negation_without_overmatching_names() -> None:
    assert not CORE.direct_fact_is_grounded("使用 Python", "未使用 Python")
    assert not CORE.direct_fact_is_grounded("Redis", "不熟悉 Redis")
    assert not CORE.direct_fact_is_grounded("Python", "无 Python 经验")
    assert not CORE.direct_fact_is_grounded("Python", "尚无 Python 经验")
    assert not CORE.direct_fact_is_grounded("Python", "不懂 Python")
    assert not CORE.direct_fact_is_grounded("负责开发", "非本人负责开发")
    assert not CORE.direct_fact_is_grounded("使用 20%", "未使用 20 %")
    assert not CORE.direct_fact_is_grounded("提升 20%", "未提升 20 %")
    assert not CORE.direct_fact_is_grounded("版本 1.10", "不是版本 1 . 10")
    assert not CORE.direct_fact_is_grounded("部署 Kubernetes", "不部署 Kubernetes")
    assert not CORE.direct_fact_is_grounded("研究 AI", "不研究 AI")
    assert not CORE.direct_fact_is_grounded("开源", "不开源")
    assert CORE.direct_fact_is_grounded("使用 Python", "不仅使用 Python")
    assert CORE.direct_fact_is_grounded("Python", "无锡大学 使用 Python")
    assert CORE.direct_fact_is_grounded("Python", "不断使用 Python")
    assert CORE.direct_fact_is_grounded("Python", "不负责运维\uff0c使用 Python 开发")
    assert CORE.direct_fact_is_grounded("Python", "未参与需求评审\uff0c负责 Python 开发")
    assert CORE.direct_fact_is_grounded("部署 Kubernetes", "不仅部署 Kubernetes")
    assert CORE.direct_fact_is_grounded("部署 Kubernetes", "不但部署 Kubernetes")
    assert CORE.direct_fact_is_grounded("部署 Kubernetes", "不得不部署 Kubernetes")
    assert CORE.direct_fact_is_grounded("部署 Kubernetes", "无不部署 Kubernetes")


@pytest.mark.parametrize(
    "raw",
    (
        "Python 并未使用",
        "Python 实际未使用",
        "Python 尚未实际使用",
        "Python 从未用于项目",
        "Python 不曾使用",
        "Python 并不熟悉",
        "Python 其实不会",
        "Python 经验并无",
        "Python 目前未使用",
        "Python 暂未使用",
        "Python 尚不会",
        "Python 并没有使用",
        "Python 从来没有用过",
        "Python 当前不熟悉",
        "Python 目前不掌握",
        "Python 完全不懂",
        "Python was never used",
        "Python has not been used",
        "Python is not familiar",
        "Python is currently not used",
        "Python was not actually used",
        "Python has never actually been used",
        "Python is completely unfamiliar",
        "Python currently has no experience",
        "Python is definitely not mastered",
    ),
)
def test_direct_facts_reject_common_suffix_negation(raw: str) -> None:
    assert not CORE.direct_fact_is_grounded("Python", raw)


def test_direct_facts_keep_positive_suffix_usage() -> None:
    assert CORE.direct_fact_is_grounded("Python", "Python is used")
    assert CORE.direct_fact_is_grounded("Python", "Python 熟练使用")
    assert CORE.direct_fact_is_grounded("Python", "Python is not only used for scripts")


@pytest.mark.parametrize(
    ("canonical", "claims", "code"),
    (
        (
            {"projects": [{"name": "Alpha"}, {"name": "Alpha"}]},
            (
                CORE.FactClaim("/projects/0/name", "Alpha"),
                CORE.FactClaim("/projects/1/name", "Alpha"),
            ),
            r"canonical_duplicate_record@/projects/1",
        ),
        (
            {"skills": {"languages": ["Python", "Python"]}},
            (
                CORE.FactClaim("/skills/languages/0", "Python"),
                CORE.FactClaim("/skills/languages/1", "Python"),
            ),
            r"canonical_duplicate_list_item@/skills/languages/1",
        ),
        (
            {
                "internships": [
                    {
                        "organization": "Acme",
                        "duration": "2025",
                        "role": "Intern",
                    },
                    {
                        "organization": "Acme",
                        "duration": "2025",
                        "role": "Owner",
                    },
                ],
            },
            (
                CORE.FactClaim("/internships/0/organization", "Acme"),
                CORE.FactClaim("/internships/0/duration", "2025"),
                CORE.FactClaim("/internships/0/role", "Intern"),
                CORE.FactClaim("/internships/1/organization", "Acme"),
                CORE.FactClaim("/internships/1/duration", "2025"),
                CORE.FactClaim("/internships/1/role", "Owner"),
            ),
            r"canonical_duplicate_record@/internships/1",
        ),
    ),
)
def test_audit_rejects_reused_canonical_facts(
    canonical: dict[str, Any],
    claims: tuple[Any, ...],
    code: str,
) -> None:
    raw = CORE.RawExtraction(full_text="Alpha Python", source_sha256="a" * 64)
    with pytest.raises(ValueError, match=code):
        CORE.audit_canonical_mapping(raw, canonical, claims, error_type=ValueError)


def test_duplicate_identity_uses_collection_specific_strong_keys() -> None:
    canonical = {
        "internships": [
            {"organization": "Acme", "duration": "2025", "role": "Intern"},
            {"organization": "Acme", "duration": "2025", "role": "Owner"},
        ],
        "projects": [
            {
                "organization": "Acme",
                "name": "Platform",
                "duration": "2024",
                "role": "Owner",
            },
            {
                "organization": "Acme",
                "name": "Platform",
                "duration": "2024",
                "role": "Developer",
            },
        ],
        "security_activities": [
            {"name": "Blue Team", "duration": "2024", "role": "Analyst"},
            {"name": "Blue Team", "duration": "2024", "role": "Owner"},
        ],
    }

    assert CORE.duplicate_canonical_violations(canonical) == (
        CORE.AuditViolation("canonical_duplicate_record", "/internships/1"),
        CORE.AuditViolation("canonical_duplicate_record", "/projects/1"),
        CORE.AuditViolation("canonical_duplicate_record", "/security_activities/1"),
    )


def test_strong_identity_compares_the_full_tuple() -> None:
    canonical = {
        "internships": [
            {"organization": "Acme", "name": "Intern A", "duration": "2025"},
            {"organization": "Acme", "name": "Intern B", "duration": "2025"},
        ],
        "projects": [
            {"organization": "Acme", "name": "Platform", "duration": "2024"},
            {"organization": "Acme", "name": "Platform", "duration": "2025"},
        ],
        "security_activities": [
            {"organization": "Acme", "name": "Security Lab", "duration": "2025"},
        ],
    }

    assert CORE.duplicate_canonical_violations(canonical) == ()


def test_strong_identity_rejects_a_cross_collection_copy() -> None:
    canonical = {
        "internships": [
            {
                "organization": "Acme",
                "name": "Platform",
                "duration": "2025",
                "role": "Intern",
            }
        ],
        "projects": [
            {
                "organization": "Acme",
                "name": "Platform",
                "duration": "2025",
                "role": "Owner",
            }
        ],
    }

    assert CORE.duplicate_canonical_violations(canonical) == (
        CORE.AuditViolation("canonical_duplicate_record", "/projects/0"),
    )


def test_weak_record_identity_only_rejects_an_exact_duplicate() -> None:
    distinct = {
        "projects": [
            {"name": "Platform", "description": "Python API"},
            {"name": "Platform", "description": "Go API"},
        ]
    }
    exact = {
        "projects": [
            {"name": "Platform", "description": "Python API"},
            {"name": "Platform", "description": "Python API"},
        ]
    }

    assert CORE.duplicate_canonical_violations(distinct) == ()
    assert CORE.duplicate_canonical_violations(exact) == (
        CORE.AuditViolation("canonical_duplicate_record", "/projects/1"),
    )


@pytest.mark.parametrize(
    ("alias", "canonical"),
    (
        ("K8s", "Kubernetes"),
        ("Golang", "Go"),
        ("JS", "JavaScript"),
        ("TS", "TypeScript"),
        ("Postgres", "PostgreSQL"),
        ("Bash", "Shell"),
    ),
)
def test_duplicate_lists_use_the_same_fixed_aliases_as_grounding(
    alias: str, canonical: str
) -> None:
    payload = {"skills": {"tools": [alias, canonical]}}

    assert CORE.duplicate_canonical_violations(payload) == (
        CORE.AuditViolation("canonical_duplicate_list_item", "/skills/tools/1"),
    )


@pytest.mark.parametrize(
    ("plain", "formatted"),
    (
        ("使用 Go 交付", "使用 Go\uff0c交付"),
        ("delivered with Go tooling", "delivered with Go, tooling"),
    ),
)
def test_duplicate_lists_use_the_same_punctuation_compaction_as_grounding(
    plain: str, formatted: str
) -> None:
    payload = {"skills": {"evidence": [plain, formatted]}}

    assert CORE.duplicate_canonical_violations(payload) == (
        CORE.AuditViolation("canonical_duplicate_list_item", "/skills/evidence/1"),
    )


def test_duplicate_normalization_is_consistent_for_record_lists() -> None:
    payload = {
        "projects": [
            {
                "name": "Platform",
                "duration": "2025",
                "tech_stack": ["\uff2b\uff18\uff53", "kubernetes"],
                "achievements": ["使用 Golang 交付", "使用  Go\n交付"],
            }
        ]
    }

    assert CORE.duplicate_canonical_violations(payload) == (
        CORE.AuditViolation("canonical_duplicate_list_item", "/projects/0/achievements/1"),
        CORE.AuditViolation("canonical_duplicate_list_item", "/projects/0/tech_stack/1"),
    )


@pytest.mark.parametrize(
    ("claim", "raw"),
    (
        ("1.10", "11.10"),
        ("1.10", "1.100"),
        ("20%", "120%"),
        ("2024-01", "12024-012"),
        ("foo@example.com", "xfoo@example.com"),
        ("foo@example.com", "foo@example.com.cn"),
        ("C++", "C++++"),
        ("20", "20%"),
        ("1", "1.10"),
        ("3", "3.0"),
        ("10", "1:10"),
        ("2024", "2024/01"),
        ("C", "C++"),
        ("C", "C#"),
        ("F", "F#"),
        ("NET", ".NET"),
        ("CI", "CI/CD"),
        ("CD", "CI/CD"),
        ("user", "user@example.com"),
        ("example", "user@example.com"),
    ),
)
def test_direct_facts_reject_substrings_of_longer_tokens(claim: str, raw: str) -> None:
    assert not CORE.fact_is_grounded(claim, raw)
    assert not CORE.direct_fact_is_grounded(claim, raw)


def test_direct_facts_keep_exact_ascii_formatting_equivalence() -> None:
    assert CORE.direct_fact_is_grounded("1.10", "1 . 10")
    assert CORE.direct_fact_is_grounded("C++", "C + +")
    assert CORE.direct_fact_is_grounded("Python", "Python: 熟练")
    assert CORE.direct_fact_is_grounded("Python", "Python.")
    assert CORE.direct_fact_is_grounded("Python", "Python, Go")
    assert CORE.direct_fact_is_grounded("Node.js", "Node.js.")
    for claim in ("P95 延迟下降 30%", "引用正确率达到 90%"):
        raw = f"{claim}。\n\n## 下一节"
        assert CORE.fact_is_grounded(claim, raw)
        assert CORE.direct_fact_is_grounded(claim, raw)
    for claim, raw in (
        ("Claude Code", "Tools: Cursor, Claude Code"),
        ("Burp Suite", "Nmap, Burp Suite, Wireshark"),
        ("Amazon Web Services", "Cloud: Amazon Web Services"),
        ("Visual Studio Code", "IDE: Visual Studio Code"),
        ("machine learning", "Focus: machine learning, systems"),
    ):
        assert CORE.direct_fact_is_grounded(claim, raw)
    for claim, raw in (
        ("使用 Python", "使用 Python\u3002\nSkills\nGo"),
        ("准确率提升 20%", "准确率提升 20%\u3002\nSkills"),
        ("错误率降到 1%", "错误率降到 1%\nGo"),
        ("使用 Python", "项目A 使用 Python\uff0cGo"),
        ("使用 Python", "项目A 使用 Python\uff1bGo"),
        ("使用 Python", "项目A 使用 Python / Go"),
        ("使用 Node.js (Express)", "项目使用 Node.js (Express) 开发"),
        ("基于 ASP.NET Core 开发", "基于 ASP.NET Core 开发服务"),
        ("使用 Vue.js 开发", "使用 Vue.js 开发前端"),
        ("维护 example.com 服务", "负责维护 example.com 服务"),
    ):
        assert CORE.direct_fact_is_grounded(claim, raw)


@pytest.mark.parametrize(
    "raw",
    (
        "doesn't deploy Kubernetes",
        "doesnt deploy Kubernetes",
        "don't deploy Kubernetes",
        "dont deploy Kubernetes",
        "won't deploy Kubernetes",
        "wont deploy Kubernetes",
        "shouldn't deploy Kubernetes",
        "shouldnt deploy Kubernetes",
        "couldn't deploy Kubernetes",
        "couldnt deploy Kubernetes",
    ),
)
def test_direct_facts_reject_common_english_contracted_negation(raw: str) -> None:
    assert not CORE.direct_fact_is_grounded("deploy Kubernetes", raw)


@pytest.mark.parametrize(
    "raw",
    (
        "吞吐提升 20% 左右",
        "吞吐提升 20% 以上",
        "吞吐提升 20% 以下",
        "吞吐提升 20%+",
        "吞吐提升 20%\uff08估算\uff09",
        "吞吐提升 20%-30%",
        "吞吐提升约为 20%",
        "吞吐提升 20% 起",
        "吞吐提升 20% 最少",
        "吞吐提升 20% 最多",
        "吞吐提升 20% 或更多",
        "吞吐提升 >=20%",
        "吞吐提升 ≤20%",
        "吞吐提升 ≧20%",
        "吞吐提升 ≦20%",
        "吞吐提升 ≈20%",
        "吞吐提升 ≃20%",
        "吞吐提升 ~20%",
    ),
)
def test_direct_numeric_facts_reject_dropped_qualifiers(raw: str) -> None:
    assert not CORE.direct_fact_is_grounded("吞吐提升 20%", raw)


def test_direct_numeric_facts_preserve_a_canonical_qualifier() -> None:
    assert CORE.direct_fact_is_grounded("吞吐提升 20% 左右", "吞吐提升 20% 左右")


@pytest.mark.parametrize(
    "raw",
    (
        "Python: 无",
        "Python\uff1a暂无",
        "Python经验\uff1a无",
        "Python: zero",
        "Python 未接触",
        "Python\uff1a未掌握",
        "Python\uff1a未了解",
        "Python\uff1a不了解",
        "Python\uff1a不懂",
        "Python\uff1a不具备",
        "Python\uff1a缺乏经验",
        "Python\uff1a零经验",
        "Python\uff1a尚未学习",
        "Python\uff1a从未使用",
        "Python\uff1a未曾使用",
        "Python: no",
        "Python: N/A",
        "Python: false",
        "Python: denied",
        "Python: not",
        "Python: never",
        "Python - absent",
        "Python: lacking",
        "Python experience: no",
        "Python experience: none",
    ),
)
def test_direct_facts_reject_suffix_absence_signals(raw: str) -> None:
    assert not CORE.direct_fact_is_grounded("Python", raw)


def test_section_states_cover_absent_empty_and_populated() -> None:
    heading = re.compile(r"技能")
    all_headings = re.compile(r"技能|项目")
    assert CORE.section_state("项目\n内容", heading, all_headings) == "absent"
    assert CORE.section_state("技能\n暂无\n项目\n内容", heading, all_headings) == "empty"
    assert CORE.section_state("技能\nPython\n项目\n内容", heading, all_headings) == "populated"


@pytest.mark.parametrize(
    ("candidate", "scope", "raw_scope"),
    (
        ("课程设计", "不是课程设计\uff0c是企业项目", "平台 不是课程设计\uff0c是企业项目"),
        ("课程设计", "课程设计", "平台 不是课程设计"),
        ("课程设计", "不算课程设计", "平台 不算课程设计"),
        ("ctf", "未参加 CTF", "平台 未参加 CTF"),
        ("ctf", "CTF 未参加", "平台 CTF 未参加"),
        ("ctf", "与 CTF 无关", "平台 与 CTF 无关"),
        ("ctf", "不是在 CTF 环境", "平台 不是在 CTF 环境"),
        ("ctf", "未参加过 CTF", "平台 未参加过 CTF"),
        ("ctf", "non-CTF", "平台 non-CTF"),
        ("课程设计", "课程设计\uff1a否", "平台 课程设计\uff1a否"),
        ("漏洞赏金", "不属于漏洞赏金范围", "平台 不属于漏洞赏金范围"),
        ("bug bounty", "not in bug bounty scope", "platform not in bug bounty scope"),
        ("ctf", "没有 CTF 经验", "平台 没有 CTF 经验"),
        ("ctf", "未接触 CTF", "平台 未接触 CTF"),
        ("ctf", "CTF\uff1a暂无", "平台 CTF\uff1a暂无"),
        ("ctf", "CTF 经验\uff1a无", "平台 CTF 经验\uff1a无"),
        ("ctf", "CTF: none", "platform CTF: none"),
        ("ctf", "CTF: zero", "platform CTF: zero"),
        ("开源", "不开源项目", "平台 不开源项目"),
    ),
)
def test_controlled_signals_reject_local_negation(
    candidate: str, scope: str, raw_scope: str
) -> None:
    claim = CORE.FactClaim(
        "/category",
        "controlled",
        match_kind="controlled",
        candidates=(candidate,),
        scope_values=(scope,),
        raw_scope_text=raw_scope,
    )
    assert not CORE.controlled_signal_is_grounded(claim, raw_scope)


def test_controlled_signals_keep_non_negating_bu_constructions() -> None:
    for scope in ("不仅开源", "不但开源", "不断开源"):
        claim = CORE.FactClaim(
            "/category",
            "open_source",
            match_kind="controlled",
            candidates=("开源",),
            scope_values=(scope,),
            raw_scope_text=f"平台 {scope}",
        )
        assert CORE.controlled_signal_is_grounded(claim, f"平台 {scope}")


def test_canonical_hash_and_pointer_enumeration_are_stable() -> None:
    first = {
        "resume_id": "generated-a",
        "basic": {"name": "候选", "empty": "", "none": None, "x/y~z": "value"},
        "projects": [{"category": "other", "name": "项目"}],
        "environment": "unknown",
    }
    second = {**first, "resume_id": "generated-b"}
    assert CORE.canonical_facts_sha256(first) == CORE.canonical_facts_sha256(second)
    assert CORE.populated_leaf_pointers(first) == {
        "/basic/name",
        "/basic/x~1y~0z",
        "/projects/0/name",
    }


def test_audit_supports_all_match_kinds_and_sorted_metadata() -> None:
    raw = CORE.RawExtraction(
        full_text="候选 2027 届 课程设计",
        source_sha256="a" * 64,
    )
    canonical = {
        "name": "候选",
        "year": 2027,
        "category": "course",
        "reviewed": "internal",
    }
    claims = [
        CORE.FactClaim("/name", "候选"),
        CORE.FactClaim("/year", 2027, match_kind="graduation_year"),
        CORE.FactClaim(
            "/category",
            "course",
            match_kind="controlled",
            candidates=("课程设计",),
            scope_text="课程设计",
            scope_values=("课程设计",),
            raw_scope_text="候选 2027 届 课程设计",
        ),
        CORE.FactClaim("/reviewed", "internal", match_kind="registered"),
    ]
    result = CORE.audit_canonical_mapping(
        raw,
        canonical,
        claims,
        error_type=ValueError,
        warning_codes=("z_warning", "a_warning", "z_warning"),
    )
    assert result.checked_fact_count == 4
    assert result.warning_codes == ("a_warning", "z_warning")
    assert result.public_metadata()["passed"] is True


def test_audit_rejects_a_direct_fact_when_mapping_dropped_negation() -> None:
    with pytest.raises(ValueError, match=r"canonical_fact_not_grounded@/description"):
        CORE.audit_canonical_mapping(
            CORE.RawExtraction("未使用 Python", "a" * 64),
            {"description": "使用 Python"},
            [CORE.FactClaim("/description", "使用 Python")],
            error_type=ValueError,
        )


def test_anchored_record_scope_never_borrows_an_adjacent_line() -> None:
    raw = "项目经历\n支付平台\n另一项目 课程设计"
    assert CORE.anchored_record_scope(raw, ("支付平台",)) == "支付平台"
    assert CORE.anchored_record_scope(raw, ()) == ""
    assert CORE.anchored_record_scope("平台 甲\n平台 乙", ("平台",)) == ""
    assert CORE.anchored_record_scope("告警平台\n智能告警平台", ("告警平台",)) == "告警平台"


def test_record_scopes_reject_a_frankenrecord_built_from_peer_records() -> None:
    raw = "项目经历\nCompany A Project A Python\nCompany B Project B Go"
    result = CORE.record_collection_scopes(
        raw,
        (("Company A", "Project B"), ("Company B", "Project A")),
        collection_pointer="/projects",
        heading_pattern=re.compile("项目经历"),
        all_headings_pattern=re.compile("项目经历|专业技能"),
    )

    assert result.scopes == ("", "")
    assert result.violations == (
        CORE.AuditViolation("canonical_record_scope_not_found", "/projects/0"),
        CORE.AuditViolation("canonical_record_scope_not_found", "/projects/1"),
        CORE.AuditViolation("raw_record_not_mapped", "/projects"),
    )


def test_record_scopes_reject_an_explicit_unmapped_peer_record() -> None:
    raw = "项目经历\nCompany A Project A Python\nCompany B Project B Go"
    result = CORE.record_collection_scopes(
        raw,
        (("Company A", "Project A"),),
        collection_pointer="/projects",
        heading_pattern=re.compile("项目经历"),
        all_headings_pattern=re.compile("项目经历|专业技能"),
    )

    assert result.scopes == ("Company A Project A Python",)
    assert result.violations == (CORE.AuditViolation("raw_record_not_mapped", "/projects"),)


def test_record_scopes_keep_a_normal_multiline_record_together() -> None:
    raw = """项目经历
Company A | Project A | 2025
负责 API 开发
使用 Python
Company B | Project B | 2024
负责服务开发
使用 Go
专业技能
Python Go
"""
    result = CORE.record_collection_scopes(
        raw,
        (("Company A", "Project A"), ("Company B", "Project B")),
        collection_pointer="/projects",
        heading_pattern=re.compile("项目经历"),
        all_headings_pattern=re.compile("项目经历|专业技能"),
    )

    assert result.violations == ()
    assert result.scopes == (
        "Company A | Project A | 2025\n负责 API 开发\n使用 Python",
        "Company B | Project B | 2024\n负责服务开发\n使用 Go",
    )


def test_record_scopes_do_not_split_wrapped_headers_or_bullet_fields() -> None:
    raw = """项目经历
Company A
Platform A
Backend Engineer | 2025 - Present
- 技术栈 | Python
- Built API service
"""
    result = CORE.record_collection_scopes(
        raw,
        (("Company A", "Platform A", "2025 - Present"),),
        collection_pointer="/projects",
        heading_pattern=re.compile("项目经历"),
        all_headings_pattern=re.compile("项目经历|专业技能"),
    )

    assert result.violations == ()
    assert result.scopes == (
        "Company A\nPlatform A\nBackend Engineer | 2025 - Present\n"
        "- 技术栈 | Python\n- Built API service",
    )


def test_record_scopes_ignore_an_anchor_repeated_in_record_body() -> None:
    raw = """项目经历
Project Alpha | Owner | 2024.01-2024.06
负责 Project Alpha 的 API 开发
使用 Python
"""
    result = CORE.record_collection_scopes(
        raw,
        (("Project Alpha", "2024.01-2024.06"),),
        collection_pointer="/projects",
        heading_pattern=re.compile("项目经历"),
        all_headings_pattern=re.compile("项目经历|专业技能"),
    )

    assert result.violations == ()
    assert result.scopes == (
        "Project Alpha | Owner | 2024.01-2024.06\n负责 Project Alpha 的 API 开发\n使用 Python",
    )


@pytest.mark.parametrize(
    ("anchor", "body"),
    (
        ("Project Alpha", "Project Alpha is an observability platform built with Python"),
        ("可观测平台", "可观测平台 使用 Python 构建告警服务"),
    ),
)
def test_record_scopes_use_only_the_first_single_anchor_occurrence(anchor: str, body: str) -> None:
    raw = f"项目经历\n{anchor}\n{body}"
    result = CORE.record_collection_scopes(
        raw,
        ((anchor,),),
        collection_pointer="/projects",
        heading_pattern=re.compile("项目经历"),
        all_headings_pattern=re.compile("项目经历|专业技能"),
    )

    assert result.violations == ()
    assert result.scopes == (f"{anchor}\n{body}",)


@pytest.mark.parametrize(
    ("canonical", "claims", "violation", "code"),
    [
        (
            {"name": "候选"},
            [
                CORE.FactClaim("/name", "候选"),
                CORE.FactClaim("/name", "候选"),
            ],
            None,
            "audit_contract_duplicate_field",
        ),
        (
            {"name": "候选"},
            [CORE.FactClaim("/name", "候选", match_kind="future")],
            None,
            "audit_contract_unknown_match_kind",
        ),
        (
            {},
            [CORE.FactClaim("/unexpected", "value", match_kind="registered")],
            None,
            "audit_contract_unexpected_field",
        ),
        (
            {"missing": "value"},
            [],
            None,
            "audit_contract_uncovered_field",
        ),
        (
            {},
            [],
            CORE.AuditViolation("section_missing", "/projects"),
            "section_missing@/projects",
        ),
    ],
)
def test_audit_contract_failures_are_machine_readable(
    canonical: dict[str, Any],
    claims: list[Any],
    violation: Any,
    code: str,
) -> None:
    violations = () if violation is None else (violation,)
    with pytest.raises(ValueError, match=re.escape(code)):
        CORE.audit_canonical_mapping(
            CORE.RawExtraction("候选", "a" * 64),
            canonical,
            claims,
            error_type=ValueError,
            violations=violations,
        )
