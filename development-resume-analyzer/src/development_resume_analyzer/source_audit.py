"""Development canonical-fact adapter for the shared source-mapping audit core."""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any

from .errors import SourceMappingAuditError
from .models import ProjectCategory, Resume
from .security import SECURITY_WARNING, is_instruction_like, is_strong_instruction_like
from .source_audit_core import (
    MAX_RAW_EXTRACTION_BYTES,
    SOURCE_MAPPING_AUDIT_VERSION,
    AuditViolation,
    FactClaim,
    RawExtraction,
    SourceMappingAuditResult,
    anchored_record_scope,
    audit_canonical_mapping,
    filter_instruction_like_evidence,
    load_raw_extraction,
    record_collection_scopes,
    section_state,
)

_PROJECT_SECTION = re.compile(
    r"项目[^\S\n]*(?:经历|经验|实践|竞赛|比赛|介绍|内容|描述)|"
    r"课程[^\S\n]*设计|课设|开源[^\S\n]*经历|"
    r"(?m:^[^\S\n]*(?:项目|研究[^\S\n]*经历|个人[^\S\n]*项目|开源[^\S\n]*项目|"
    r"课程[^\S\n]*项目|毕业[^\S\n]*设计)"
    r"[^\S\n]*(?:[:\uff1a])?[^\S\n]*$)|\bprojects?(?:\s+experience)?\b",
    re.I,
)
_INTERNSHIP_SECTION = re.compile(
    r"实习[^\S\n]*经历|工作[^\S\n]*(?:经历|经验)|"
    r"(?m:^[^\S\n]*实习[^\S\n]*(?:[:\uff1a])?[^\S\n]*$)|"
    r"\binternship experience\b|\bwork experience\b",
    re.I,
)
_SKILLS_SECTION = re.compile(
    r"专业[^\S\n]*技能|个人[^\S\n]*技能|技能(?:[^\S\n]*(?:清单|总结))?|"
    r"技术[^\S\n]*栈|\b(?:skills?|technologies)\b",
    re.I,
)
_EDUCATION_SECTION = re.compile(
    r"教育[^\S\n]*(?:经历|背景)|(?m:^[^\S\n]*教育[^\S\n]*(?:[:\uff1a])?[^\S\n]*$)|"
    r"\beducation\b",
    re.I,
)
_ALL_HEADINGS = re.compile(
    r"个人[^\S\n]*(?:信息|简介|概况|总结|评价)|基本[^\S\n]*信息|求职[^\S\n]*意向|"
    r"教育[^\S\n]*(?:经历|背景)|专业[^\S\n]*技能|个人[^\S\n]*技能|"
    r"技能(?:[^\S\n]*(?:清单|总结))?|技术[^\S\n]*栈|证书|获奖(?:经历|情况)?|荣誉|"
    r"校园(?:经历|实践)|社会实践|自我评价|兴趣爱好|开源经历|"
    r"项目[^\S\n]*(?:经历|经验|实践|竞赛|比赛|介绍|内容|描述)|"
    r"课程[^\S\n]*设计|课设|(?m:^[^\S\n]*(?:项目|研究[^\S\n]*经历|"
    r"个人[^\S\n]*项目|开源[^\S\n]*项目|课程[^\S\n]*项目|毕业[^\S\n]*设计|实习|教育)"
    r"[^\S\n]*(?:[:\uff1a])?[^\S\n]*$)|实习[^\S\n]*经历|工作[^\S\n]*(?:经历|经验)|"
    r"\b(?:profile|summary|objective|education|skills?|technologies|certifications?|"
    r"awards?|projects?|internship experience|work experience|open source)\b",
    re.I,
)
_INSTITUTION = re.compile(r"[\u4e00-\u9fff]{2,24}(?:大学|学院|学校)")
_DEGREE_POLLUTION = re.compile(r"本科|专科|学士|硕士|研究生|博士")
_EMAIL = re.compile(r"(?<![\w.+-])[\w.+-]+@[\w.-]+\.[A-Za-z]{2,}(?![\w.-])")
_PHONE = re.compile(r"(?<!\d)1[3-9]\d{9}(?!\d)")
_CATEGORY_SIGNALS: dict[ProjectCategory, tuple[str, ...]] = {
    ProjectCategory.course_project: ("课程项目", "课程设计", "课设", "course project"),
    ProjectCategory.personal_project: ("个人项目", "独立项目", "personal project"),
    ProjectCategory.open_source: ("开源", "open source"),
    ProjectCategory.competition: ("竞赛", "比赛", "competition"),
    ProjectCategory.research: ("研究", "科研", "research"),
    ProjectCategory.hackathon: ("黑客松", "hackathon"),
    ProjectCategory.internship_project: ("实习项目", "internship project"),
}


def _claim(
    claims: list[FactClaim],
    pointer: str,
    value: str | int | None,
    *,
    raw_scope_text: str | None = None,
) -> None:
    if value is not None and value != "":
        claims.append(FactClaim(pointer, value, raw_scope_text=raw_scope_text))


def _record_scope_values(record: object) -> tuple[str, ...]:
    values: list[str] = []
    for field in ("organization", "name", "role", "duration", "description"):
        value = getattr(record, field, None)
        if value:
            values.append(value)
    values.extend(getattr(record, "tech_stack", ()))
    values.extend(getattr(record, "achievements", ()))
    return tuple(values)


def _record_anchors(record: object) -> tuple[str, ...]:
    identity = tuple(
        value for field in ("organization", "name") if (value := getattr(record, field, None))
    )
    if not identity:
        return ()
    duration = getattr(record, "duration", None)
    return (*identity, duration) if duration else identity


def _claims(resume: Resume, raw_text: str) -> tuple[list[FactClaim], list[AuditViolation]]:
    claims: list[FactClaim] = []
    violations: list[AuditViolation] = []
    basic = resume.basic_info
    for field in ("name", "school", "major", "degree"):
        _claim(claims, f"/basic_info/{field}", getattr(basic, field))
    if basic.graduation_year is not None:
        claims.append(
            FactClaim(
                "/basic_info/graduation_year",
                basic.graduation_year,
                match_kind="graduation_year",
            )
        )
    if basic.contact is not None:
        for field in ("phone", "email"):
            _claim(claims, f"/basic_info/contact/{field}", getattr(basic.contact, field))
    for collection_name, records in (
        ("internships", resume.internships),
        ("projects", resume.projects),
    ):
        heading_pattern = (
            _INTERNSHIP_SECTION if collection_name == "internships" else _PROJECT_SECTION
        )
        record_scope_result = record_collection_scopes(
            raw_text,
            tuple(_record_anchors(record) for record in records),
            collection_pointer=f"/{collection_name}",
            heading_pattern=heading_pattern,
            all_headings_pattern=_ALL_HEADINGS,
        )
        violations.extend(record_scope_result.violations)
        for index, (record, raw_scope) in enumerate(
            zip(records, record_scope_result.scopes, strict=True)
        ):
            prefix = f"/{collection_name}/{index}"
            for field in ("organization", "name", "role", "duration", "description"):
                _claim(
                    claims,
                    f"{prefix}/{field}",
                    getattr(record, field),
                    raw_scope_text=raw_scope,
                )
            for field in ("tech_stack", "achievements"):
                for item_index, value in enumerate(getattr(record, field)):
                    _claim(
                        claims,
                        f"{prefix}/{field}/{item_index}",
                        value,
                        raw_scope_text=raw_scope,
                    )
            category = getattr(record, "category", None)
            if category is not None and category is not ProjectCategory.other:
                scope_values = _record_scope_values(record)
                classification_scope = anchored_record_scope(raw_text, _record_anchors(record))
                claims.append(
                    FactClaim(
                        f"{prefix}/category",
                        category.value,
                        match_kind="controlled",
                        candidates=_CATEGORY_SIGNALS[category],
                        scope_text="\n".join(scope_values),
                        scope_values=scope_values,
                        raw_scope_text=classification_scope,
                    )
                )
    for group, values in resume.skills.model_dump(mode="python").items():
        for index, value in enumerate(values):
            _claim(claims, f"/skills/{group}/{index}", value)
    return claims, violations


def _section_violations(resume: Resume, raw_text: str) -> list[AuditViolation]:
    violations: list[AuditViolation] = []
    states = {
        "projects": section_state(raw_text, _PROJECT_SECTION, _ALL_HEADINGS),
        "internships": section_state(raw_text, _INTERNSHIP_SECTION, _ALL_HEADINGS),
        "skills": section_state(raw_text, _SKILLS_SECTION, _ALL_HEADINGS),
        "education": section_state(raw_text, _EDUCATION_SECTION, _ALL_HEADINGS),
    }
    if states["projects"] == "populated" and not resume.projects:
        violations.append(
            AuditViolation("raw_has_project_section_but_canonical_projects_empty", "/projects")
        )
    if states["projects"] == "empty" and resume.projects:
        violations.append(
            AuditViolation("canonical_projects_present_but_source_section_empty", "/projects")
        )
    if states["internships"] == "populated" and not resume.internships:
        violations.append(
            AuditViolation(
                "raw_has_internship_section_but_canonical_internships_empty", "/internships"
            )
        )
    if states["internships"] == "empty" and resume.internships:
        violations.append(
            AuditViolation("canonical_internships_present_but_source_section_empty", "/internships")
        )
    if states["skills"] == "populated" and not any(
        resume.skills.model_dump(mode="python").values()
    ):
        violations.append(AuditViolation("raw_has_skills_but_canonical_skills_empty", "/skills"))
    education_values = (
        resume.basic_info.school,
        resume.basic_info.major,
        resume.basic_info.degree,
        resume.basic_info.graduation_year,
    )
    if states["education"] == "populated" and not any(education_values):
        violations.append(
            AuditViolation("raw_has_education_but_canonical_education_empty", "/basic_info")
        )
    if resume.basic_info.school and _DEGREE_POLLUTION.search(resume.basic_info.school):
        violations.append(
            AuditViolation("canonical_school_contains_degree_text", "/basic_info/school")
        )
    return violations


def _warnings(resume: Resume, raw_text: str) -> list[str]:
    warnings: list[str] = []
    if is_instruction_like(raw_text):
        warnings.append(SECURITY_WARNING)
    if not resume.basic_info.school and _INSTITUTION.search(raw_text):
        warnings.append("raw_has_institution_but_canonical_school_missing")
    contact = resume.basic_info.contact
    if _EMAIL.search(raw_text) and (contact is None or contact.email is None):
        warnings.append("raw_has_email_but_canonical_email_missing")
    if _PHONE.search(raw_text) and (contact is None or contact.phone is None):
        warnings.append("raw_has_phone_but_canonical_phone_missing")
    return warnings


def audit_source_mapping(raw_extraction_path: Path, resume: Resume) -> SourceMappingAuditResult:
    """Prove every populated development canonical fact is grounded in the raw resume."""

    raw = load_raw_extraction(raw_extraction_path, SourceMappingAuditError)
    evidence_text = filter_instruction_like_evidence(
        raw.full_text,
        is_instruction_like,
        is_strong_instruction_like,
    )
    evidence_raw = RawExtraction(
        full_text=evidence_text,
        source_sha256=raw.source_sha256,
    )
    canonical: dict[str, Any] = resume.model_dump(mode="json")
    claims, record_violations = _claims(resume, evidence_text)
    return audit_canonical_mapping(
        evidence_raw,
        canonical,
        claims,
        error_type=SourceMappingAuditError,
        violations=(*record_violations, *_section_violations(resume, evidence_text)),
        warning_codes=_warnings(resume, raw.full_text),
    )


__all__ = [
    "MAX_RAW_EXTRACTION_BYTES",
    "SOURCE_MAPPING_AUDIT_VERSION",
    "SourceMappingAuditResult",
    "audit_source_mapping",
]
