"""Security canonical-fact adapter for the shared source-mapping audit core."""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any

from .authorization import has_global_authorization_denial, source_is_authorized
from .errors import SourceMappingAuditError
from .models import Experience, Resume, SecurityCategory, SecurityEnvironment
from .security import SECURITY_WARNING, is_instruction_like
from .source_audit_core import (
    MAX_RAW_EXTRACTION_BYTES,
    SOURCE_MAPPING_AUDIT_VERSION,
    AuditViolation,
    FactClaim,
    SourceMappingAuditResult,
    audit_canonical_mapping,
    fact_is_grounded,
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
_SECURITY_SECTION = re.compile(
    r"安全[^\S\n]*(?:实践|经历|活动)|CTF[^\S\n]*(?:经历|竞赛)|"
    r"靶场[^\S\n]*(?:经历|项目)|漏洞(?:赏金|披露)[^\S\n]*(?:经历|项目)|"
    r"(?m:^[^\S\n]*(?:CTF(?:[^\S\n]*经历)?|靶场(?:[^\S\n]*(?:经历|项目))?|"
    r"漏洞赏金(?:[^\S\n]*(?:经历|项目))?|安全[^\S\n]*项目|竞赛[^\S\n]*经历)"
    r"[^\S\n]*(?:[:\uff1a])?[^\S\n]*$)|"
    r"\bsecurity (?:experience|activities)\b",
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
    r"安全[^\S\n]*(?:实践|经历|活动)|CTF[^\S\n]*(?:经历|竞赛)|"
    r"靶场[^\S\n]*(?:经历|项目)|漏洞(?:赏金|披露)[^\S\n]*(?:经历|项目)|"
    r"(?m:^[^\S\n]*(?:CTF(?:[^\S\n]*经历)?|靶场(?:[^\S\n]*(?:经历|项目))?|"
    r"漏洞赏金(?:[^\S\n]*(?:经历|项目))?|安全[^\S\n]*项目|竞赛[^\S\n]*经历)"
    r"[^\S\n]*(?:[:\uff1a])?[^\S\n]*$)|"
    r"\b(?:profile|summary|objective|education|skills?|technologies|certifications?|"
    r"awards?|projects?|internship experience|work experience|open source|"
    r"security experience|security activities)\b",
    re.I,
)
_INSTITUTION = re.compile(r"[\u4e00-\u9fff]{2,24}(?:大学|学院|学校)")
_DEGREE_POLLUTION = re.compile(r"本科|专科|学士|硕士|研究生|博士")
_EMAIL = re.compile(r"(?<![\w.+-])[\w.+-]+@[\w.-]+\.[A-Za-z]{2,}(?![\w.-])")
_PHONE = re.compile(r"(?<!\d)1[3-9]\d{9}(?!\d)")
_CATEGORY_SIGNALS: dict[SecurityCategory, tuple[str, ...]] = {
    SecurityCategory.ctf: ("ctf", "夺旗赛"),
    SecurityCategory.lab: ("靶场", "实验环境", "security lab"),
    SecurityCategory.vulnerability_disclosure: (
        "漏洞披露",
        "负责任披露",
        "vulnerability disclosure",
    ),
    SecurityCategory.bug_bounty: ("漏洞赏金", "bug bounty"),
    SecurityCategory.authorized_testing: ("授权测试", "授权范围", "authorized testing"),
    SecurityCategory.open_source: ("开源", "open source"),
    SecurityCategory.security_competition: ("安全竞赛", "security competition"),
    SecurityCategory.certification: ("认证", "certificate", "certification"),
    SecurityCategory.paper: ("论文", "paper"),
}
_ENVIRONMENT_SIGNALS: dict[SecurityEnvironment, tuple[str, ...]] = {
    SecurityEnvironment.lab: ("靶场", "实验环境", "security lab"),
    SecurityEnvironment.ctf: ("ctf", "夺旗赛"),
    SecurityEnvironment.bug_bounty: ("漏洞赏金", "bug bounty"),
    SecurityEnvironment.production_defense: (
        "生产防御",
        "线上防御",
        "应急响应",
        "production defense",
    ),
    SecurityEnvironment.academic: ("学术", "科研", "课程", "academic"),
    SecurityEnvironment.open_source: ("开源", "open source"),
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


def _authorization_grounded(scope_values: tuple[str, ...], raw_scope_text: str) -> bool:
    scope_text = "\n".join(scope_values)
    return (
        source_is_authorized("authorized", scope_text, require_explicit=True)
        and not has_global_authorization_denial(raw_scope_text)
        and source_is_authorized(None, raw_scope_text, require_explicit=True)
        and any(
            source_is_authorized(None, value, require_explicit=True)
            and fact_is_grounded(value, raw_scope_text)
            for value in scope_values
        )
    )


def _structured_authorization_denied(
    environment: str,
    scope_text: str,
    raw_scope_text: str,
) -> bool:
    return not source_is_authorized(environment, scope_text) or not source_is_authorized(
        environment, raw_scope_text
    )


def _append_experience_claims(
    claims: list[FactClaim], prefix: str, record: Experience, raw_scope: str
) -> None:
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


def _claims_and_violations(
    resume: Resume, raw_text: str
) -> tuple[list[FactClaim], list[AuditViolation]]:
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
        for index, (experience, raw_scope) in enumerate(
            zip(records, record_scope_result.scopes, strict=True)
        ):
            _append_experience_claims(
                claims,
                f"/{collection_name}/{index}",
                experience,
                raw_scope,
            )
    security_scope_result = record_collection_scopes(
        raw_text,
        tuple(_record_anchors(record) for record in resume.security_activities),
        collection_pointer="/security_activities",
        heading_pattern=_SECURITY_SECTION,
        all_headings_pattern=_ALL_HEADINGS,
    )
    violations.extend(security_scope_result.violations)
    for index, (activity, raw_scope) in enumerate(
        zip(resume.security_activities, security_scope_result.scopes, strict=True)
    ):
        prefix = f"/security_activities/{index}"
        _append_experience_claims(claims, prefix, activity, raw_scope)
        scope_values = _record_scope_values(activity)
        scope = "\n".join(scope_values)
        classification_scope = raw_scope
        category = activity.category
        if category is SecurityCategory.authorized_testing:
            pointer = f"{prefix}/category"
            claims.append(FactClaim(pointer, category.value, match_kind="registered"))
            if not _authorization_grounded(scope_values, classification_scope):
                violations.append(AuditViolation("canonical_authorization_not_grounded", pointer))
        elif category is not None and category is not SecurityCategory.other:
            claims.append(
                FactClaim(
                    f"{prefix}/category",
                    category.value,
                    match_kind="controlled",
                    candidates=_CATEGORY_SIGNALS[category],
                    scope_text=scope,
                    scope_values=scope_values,
                    raw_scope_text=classification_scope,
                )
            )
            if category in {
                SecurityCategory.ctf,
                SecurityCategory.lab,
                SecurityCategory.bug_bounty,
            } and _structured_authorization_denied(category.value, scope, classification_scope):
                violations.append(
                    AuditViolation("canonical_authorization_not_grounded", f"{prefix}/category")
                )
        environment = activity.environment
        if environment is SecurityEnvironment.authorized:
            pointer = f"{prefix}/environment"
            claims.append(FactClaim(pointer, environment.value, match_kind="registered"))
            if not _authorization_grounded(scope_values, classification_scope):
                violations.append(AuditViolation("canonical_authorization_not_grounded", pointer))
        elif environment is not None and environment is not SecurityEnvironment.unknown:
            claims.append(
                FactClaim(
                    f"{prefix}/environment",
                    environment.value,
                    match_kind="controlled",
                    candidates=_ENVIRONMENT_SIGNALS[environment],
                    scope_text=scope,
                    scope_values=scope_values,
                    raw_scope_text=classification_scope,
                )
            )
            if environment in {
                SecurityEnvironment.ctf,
                SecurityEnvironment.lab,
                SecurityEnvironment.bug_bounty,
            } and _structured_authorization_denied(environment.value, scope, classification_scope):
                violations.append(
                    AuditViolation("canonical_authorization_not_grounded", f"{prefix}/environment")
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
        "security_activities": section_state(raw_text, _SECURITY_SECTION, _ALL_HEADINGS),
        "skills": section_state(raw_text, _SKILLS_SECTION, _ALL_HEADINGS),
        "education": section_state(raw_text, _EDUCATION_SECTION, _ALL_HEADINGS),
    }
    for key, records, singular in (
        ("projects", resume.projects, "project"),
        ("internships", resume.internships, "internship"),
        ("security_activities", resume.security_activities, "security_activity"),
    ):
        if states[key] == "populated" and not records:
            violations.append(
                AuditViolation(f"raw_has_{singular}_section_but_canonical_{key}_empty", f"/{key}")
            )
        if states[key] == "empty" and records:
            violations.append(
                AuditViolation(f"canonical_{key}_present_but_source_section_empty", f"/{key}")
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
    """Prove every populated security canonical fact is grounded in the raw resume."""

    raw = load_raw_extraction(raw_extraction_path, SourceMappingAuditError)
    canonical: dict[str, Any] = resume.model_dump(mode="json")
    claims, classification_violations = _claims_and_violations(resume, raw.full_text)
    return audit_canonical_mapping(
        raw,
        canonical,
        claims,
        error_type=SourceMappingAuditError,
        violations=(*classification_violations, *_section_violations(resume, raw.full_text)),
        warning_codes=_warnings(resume, raw.full_text),
    )


__all__ = [
    "MAX_RAW_EXTRACTION_BYTES",
    "SOURCE_MAPPING_AUDIT_VERSION",
    "SourceMappingAuditResult",
    "audit_source_mapping",
]
