"""Deterministic grounding checks between untrusted raw text and canonical facts."""

from __future__ import annotations

import json
import re
import unicodedata
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping, Sequence

from .errors import SourceMappingAuditError
from .matching import normalize_text, term_pattern
from .models import Resume

SOURCE_MAPPING_AUDIT_VERSION = "1.1.0"
MAX_RAW_EXTRACTION_BYTES = 25 * 1024 * 1024

_SHA256_PATTERN = re.compile(r"^[a-fA-F0-9]{64}$")
_PROJECT_SECTION_PATTERN = re.compile(
    r"项目(?:经历|经验|实践|竞赛|比赛|介绍|内容|描述)|课程设计|课设|"
    r"(?m:^[^\S\n]*(?:项目|研究经历)[^\S\n]*$)|"
    r"\bprojects?(?:\s+experience)?\b",
    re.IGNORECASE,
)
_INTERNSHIP_SECTION_PATTERN = re.compile(
    r"实习经历|工作经历|工作经验|\binternship experience\b|\bwork experience\b",
    re.IGNORECASE,
)
_SECTION_HEADING_PATTERN = re.compile(
    r"个人(?:信息|简介|概况|总结|评价)|基本信息|求职意向|教育(?:经历|背景)|"
    r"专业技能|个人技能|技能(?:清单|总结)?|证书|获奖(?:经历|情况)?|荣誉|"
    r"校园(?:经历|实践)|社会实践|自我评价|兴趣爱好|"
    r"项目(?:经历|经验|实践|竞赛|比赛|介绍|内容|描述)|课程设计|课设|"
    r"(?m:^[^\S\n]*(?:项目|研究经历)[^\S\n]*$)|"
    r"实习经历|工作经历|工作经验|"
    r"\b(?:profile|summary|objective|education|skills?|certifications?|awards?|"
    r"projects?|internship experience|work experience)\b",
    re.IGNORECASE,
)
_EMPTY_SECTION_CONTENT_PATTERN = re.compile(
    r"^(?:无|暂无|没有|未有|待补充|未填写|none|n/?a|not\s+provided)?$",
    re.IGNORECASE,
)
_INSTITUTION_PATTERN = re.compile(r"[\u4e00-\u9fff]{2,24}(?:大学|学院|学校)")
_DEGREE_POLLUTION_PATTERN = re.compile(r"本科|专科|学士|硕士|研究生|博士")
_EMAIL_PATTERN = re.compile(r"(?<![\w.+-])[\w.+-]+@[\w.-]+\.[A-Za-z]{2,}(?![\w.-])")
_PHONE_PATTERN = re.compile(r"(?<!\d)1[3-9]\d{9}(?!\d)")

_SKILL_ALIASES: Mapping[str, tuple[str, ...]] = {
    "kubernetes": ("kubernetes", "k8s"),
    "k8s": ("k8s", "kubernetes"),
    "golang": ("golang", "go"),
    "go": ("go", "golang"),
    "shell": ("shell", "bash"),
}


@dataclass(frozen=True)
class SourceMappingAuditResult:
    """Privacy-safe proof that supplied canonical facts are grounded in raw text."""

    raw_source_sha256: str
    warning_codes: tuple[str, ...]

    def public_metadata(self) -> dict[str, Any]:
        return {
            "audit_version": SOURCE_MAPPING_AUDIT_VERSION,
            "passed": True,
            "raw_source_sha256": self.raw_source_sha256,
            "warning_codes": list(self.warning_codes),
        }


def _load_raw_extraction(path: Path) -> Mapping[str, Any]:
    source = Path(path)
    if not source.exists() or not source.is_file():
        raise SourceMappingAuditError("raw extraction does not exist or is not a file")
    if source.is_symlink():
        raise SourceMappingAuditError("raw extraction must be a regular file, not a symlink")
    if source.stat().st_size > MAX_RAW_EXTRACTION_BYTES:
        raise SourceMappingAuditError("raw extraction exceeds the 25 MiB limit")
    try:
        value = json.loads(source.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise SourceMappingAuditError(
            f"raw extraction could not be read: {type(exc).__name__}"
        ) from exc
    if not isinstance(value, Mapping):
        raise SourceMappingAuditError("raw extraction root must be an object")
    if value.get("content_trust") != "untrusted":
        raise SourceMappingAuditError("raw extraction content_trust must be untrusted")
    full_text = value.get("full_text")
    if not isinstance(full_text, str) or not full_text.strip():
        raise SourceMappingAuditError("raw extraction full_text must be a non-empty string")
    digest = value.get("source_sha256")
    if not isinstance(digest, str) or not _SHA256_PATTERN.fullmatch(digest):
        raise SourceMappingAuditError("raw extraction source_sha256 must be a SHA-256 digest")
    return value


def _compact(value: str) -> str:
    normalized = unicodedata.normalize("NFKC", value).casefold()
    return "".join(character for character in normalized if character.isalnum())


def _grounded(value: str, raw_text: str, *, aliases: bool = False) -> bool:
    normalized_value = unicodedata.normalize("NFKC", value).strip()
    if not normalized_value:
        return False
    candidates: Sequence[str] = (normalized_value,)
    if aliases:
        candidates = _SKILL_ALIASES.get(normalized_value.casefold(), candidates)
    normalized_raw_text = normalize_text(raw_text)
    for candidate in candidates:
        if all(ord(character) < 128 for character in candidate):
            if term_pattern(candidate).search(normalized_raw_text):
                return True
        elif _compact(candidate) in _compact(raw_text):
            return True
    return False


def _audit_basic_info(resume: Resume, raw_text: str, errors: set[str], warnings: set[str]) -> None:
    basic = resume.basic_info
    for field in ("name", "major", "degree"):
        value = getattr(basic, field)
        if value and not _grounded(value, raw_text):
            errors.add(f"canonical_{field}_not_grounded")
    if basic.graduation_year is not None:
        cohort_year = f"{basic.graduation_year % 100:02d}"
        cohort_pattern = re.compile(rf"(?<!\d){re.escape(cohort_year)}\s*届(?!\d)")
        if str(basic.graduation_year) not in raw_text and not cohort_pattern.search(raw_text):
            errors.add("canonical_graduation_year_not_grounded")
    if basic.school:
        if _DEGREE_POLLUTION_PATTERN.search(basic.school):
            errors.add("canonical_school_contains_degree_text")
        if not _grounded(basic.school, raw_text):
            errors.add("canonical_school_not_grounded")
    elif _INSTITUTION_PATTERN.search(raw_text):
        warnings.add("raw_has_institution_but_canonical_school_missing")

    contact = basic.contact
    if _EMAIL_PATTERN.search(raw_text) and (contact is None or contact.email is None):
        warnings.add("raw_has_email_but_canonical_email_missing")
    if _PHONE_PATTERN.search(raw_text) and (contact is None or contact.phone is None):
        warnings.add("raw_has_phone_but_canonical_phone_missing")


def _section_state(raw_text: str, heading_pattern: re.Pattern[str]) -> str:
    """Return absent, empty, or populated for a resume section."""

    normalized = unicodedata.normalize("NFKC", raw_text)
    matches = tuple(heading_pattern.finditer(normalized))
    if not matches:
        return "absent"
    for match in matches:
        next_heading = _SECTION_HEADING_PATTERN.search(normalized, match.end())
        end = next_heading.start() if next_heading else len(normalized)
        content = normalized[match.end() : end]
        compact_content = re.sub(r"[\s\W_]+", "", content, flags=re.UNICODE)
        if not _EMPTY_SECTION_CONTENT_PATTERN.fullmatch(compact_content):
            return "populated"
    return "empty"


def _audit_experiences(resume: Resume, raw_text: str, errors: set[str]) -> None:
    project_state = _section_state(raw_text, _PROJECT_SECTION_PATTERN)
    internship_state = _section_state(raw_text, _INTERNSHIP_SECTION_PATTERN)
    if project_state == "populated" and not resume.projects:
        errors.add("raw_has_project_section_but_canonical_projects_empty")
    if project_state == "empty" and resume.projects:
        errors.add("canonical_projects_present_but_source_section_empty")
    if internship_state == "populated" and not resume.internships:
        errors.add("raw_has_internship_section_but_canonical_internships_empty")
    if internship_state == "empty" and resume.internships:
        errors.add("canonical_internships_present_but_source_section_empty")
    for project in resume.projects:
        if project.name and not _grounded(project.name, raw_text):
            errors.add("canonical_project_name_not_grounded")
    for internship in resume.internships:
        if internship.company and not _grounded(internship.company, raw_text):
            errors.add("canonical_internship_company_not_grounded")


def _audit_skills(resume: Resume, raw_text: str, errors: set[str]) -> None:
    for values in resume.skills.model_dump(mode="python").values():
        for value in values:
            if not _grounded(value, raw_text, aliases=True):
                errors.add("canonical_skill_not_grounded")
    for internship in resume.internships:
        for value in internship.tech_stack:
            if not _grounded(value, raw_text, aliases=True):
                errors.add("canonical_experience_technology_not_grounded")
    for project in resume.projects:
        for value in project.tech_stack:
            if not _grounded(value, raw_text, aliases=True):
                errors.add("canonical_experience_technology_not_grounded")


def audit_source_mapping(raw_extraction_path: Path, resume: Resume) -> SourceMappingAuditResult:
    """Fail when explicit raw-source signals contradict supplied canonical facts."""

    raw = _load_raw_extraction(raw_extraction_path)
    raw_text = str(raw["full_text"])
    errors: set[str] = set()
    warnings: set[str] = set()
    _audit_basic_info(resume, raw_text, errors, warnings)
    _audit_experiences(resume, raw_text, errors)
    _audit_skills(resume, raw_text, errors)
    if errors:
        raise SourceMappingAuditError(
            "source/canonical mapping audit failed: " + ", ".join(sorted(errors))
        )
    return SourceMappingAuditResult(
        raw_source_sha256=str(raw["source_sha256"]),
        warning_codes=tuple(sorted(warnings)),
    )
