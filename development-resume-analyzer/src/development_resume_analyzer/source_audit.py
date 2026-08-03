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

SOURCE_MAPPING_AUDIT_VERSION = "1.0.0"
MAX_RAW_EXTRACTION_BYTES = 25 * 1024 * 1024

_SHA256 = re.compile(r"^[a-fA-F0-9]{64}$")
_PROJECT_SECTION = re.compile(
    r"项目(?:经历|经验|实践|竞赛|比赛|介绍|内容|描述)|课程设计|课设|开源经历|"
    r"(?m:^[^\S\n]*(?:项目|研究经历)[^\S\n]*$)|\bprojects?(?:\s+experience)?\b",
    re.I,
)
_INTERNSHIP_SECTION = re.compile(
    r"实习经历|工作经历|工作经验|\binternship experience\b|\bwork experience\b", re.I
)
_SECTION_HEADING = re.compile(
    r"个人(?:信息|简介|概况|总结|评价)|基本信息|求职意向|教育(?:经历|背景)|"
    r"专业技能|个人技能|技能(?:清单|总结)?|证书|获奖(?:经历|情况)?|荣誉|"
    r"校园(?:经历|实践)|社会实践|自我评价|兴趣爱好|开源经历|"
    r"项目(?:经历|经验|实践|竞赛|比赛|介绍|内容|描述)|课程设计|课设|"
    r"(?m:^[^\S\n]*(?:项目|研究经历)[^\S\n]*$)|实习经历|工作经历|工作经验|"
    r"\b(?:profile|summary|objective|education|skills?|certifications?|awards?|"
    r"projects?|internship experience|work experience|open source)\b",
    re.I,
)
_EMPTY_SECTION = re.compile(
    r"^(?:无|暂无|没有|未有|待补充|未填写|none|n/?a|not\s+provided)?$", re.I
)
_INSTITUTION = re.compile(r"[\u4e00-\u9fff]{2,24}(?:大学|学院|学校)")
_DEGREE_POLLUTION = re.compile(r"本科|专科|学士|硕士|研究生|博士")
_EMAIL = re.compile(r"(?<![\w.+-])[\w.+-]+@[\w.-]+\.[A-Za-z]{2,}(?![\w.-])")
_PHONE = re.compile(r"(?<!\d)1[3-9]\d{9}(?!\d)")
_SKILL_ALIASES: Mapping[str, tuple[str, ...]] = {
    "kubernetes": ("kubernetes", "k8s"),
    "k8s": ("k8s", "kubernetes"),
    "golang": ("golang", "go"),
    "go": ("go", "golang"),
    "javascript": ("javascript", "js"),
    "typescript": ("typescript", "ts"),
    "postgresql": ("postgresql", "postgres"),
}


@dataclass(frozen=True)
class SourceMappingAuditResult:
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
    if not source.exists() or not source.is_file() or source.is_symlink():
        raise SourceMappingAuditError("raw extraction must be a regular JSON file")
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
        raise SourceMappingAuditError("raw extraction full_text must be non-empty")
    digest = value.get("source_sha256")
    if not isinstance(digest, str) or not _SHA256.fullmatch(digest):
        raise SourceMappingAuditError("raw extraction source_sha256 must be a SHA-256 digest")
    return value


def _compact(value: str) -> str:
    normalized = unicodedata.normalize("NFKC", value).casefold()
    return "".join(character for character in normalized if character.isalnum())


def _grounded(value: str, raw_text: str, *, aliases: bool = False) -> bool:
    normalized = unicodedata.normalize("NFKC", value).strip()
    if not normalized:
        return False
    candidates: Sequence[str] = (normalized,)
    if aliases:
        candidates = _SKILL_ALIASES.get(normalized.casefold(), candidates)
    normalized_raw = normalize_text(raw_text)
    for candidate in candidates:
        if all(ord(character) < 128 for character in candidate):
            if term_pattern(candidate).search(normalized_raw):
                return True
        elif _compact(candidate) in _compact(raw_text):
            return True
    return False


def _section_state(raw_text: str, pattern: re.Pattern[str]) -> str:
    normalized = unicodedata.normalize("NFKC", raw_text)
    matches = tuple(pattern.finditer(normalized))
    if not matches:
        return "absent"
    for match in matches:
        next_heading = _SECTION_HEADING.search(normalized, match.end())
        end = next_heading.start() if next_heading else len(normalized)
        content = normalized[match.end() : end]
        compact = re.sub(r"[\s\W_]+", "", content, flags=re.UNICODE)
        if not _EMPTY_SECTION.fullmatch(compact):
            return "populated"
    return "empty"


def _audit_basic_info(resume: Resume, raw_text: str, errors: set[str], warnings: set[str]) -> None:
    basic = resume.basic_info
    for field in ("name", "major", "degree"):
        value = getattr(basic, field)
        if value and not _grounded(value, raw_text):
            errors.add(f"canonical_{field}_not_grounded")
    if basic.graduation_year is not None:
        cohort = f"{basic.graduation_year % 100:02d}"
        if str(basic.graduation_year) not in raw_text and not re.search(
            rf"(?<!\d){re.escape(cohort)}\s*届(?!\d)", raw_text
        ):
            errors.add("canonical_graduation_year_not_grounded")
    if basic.school:
        if _DEGREE_POLLUTION.search(basic.school):
            errors.add("canonical_school_contains_degree_text")
        if not _grounded(basic.school, raw_text):
            errors.add("canonical_school_not_grounded")
    elif _INSTITUTION.search(raw_text):
        warnings.add("raw_has_institution_but_canonical_school_missing")
    contact = basic.contact
    if _EMAIL.search(raw_text) and (contact is None or contact.email is None):
        warnings.add("raw_has_email_but_canonical_email_missing")
    if _PHONE.search(raw_text) and (contact is None or contact.phone is None):
        warnings.add("raw_has_phone_but_canonical_phone_missing")


def _audit_experiences(resume: Resume, raw_text: str, errors: set[str]) -> None:
    project_state = _section_state(raw_text, _PROJECT_SECTION)
    internship_state = _section_state(raw_text, _INTERNSHIP_SECTION)
    if project_state == "populated" and not resume.projects:
        errors.add("raw_has_project_section_but_canonical_projects_empty")
    if project_state == "empty" and resume.projects:
        errors.add("canonical_projects_present_but_source_section_empty")
    if internship_state == "populated" and not resume.internships:
        errors.add("raw_has_internship_section_but_canonical_internships_empty")
    if internship_state == "empty" and resume.internships:
        errors.add("canonical_internships_present_but_source_section_empty")
    for record in (*resume.projects, *resume.internships):
        if record.name and not _grounded(record.name, raw_text):
            errors.add("canonical_experience_name_not_grounded")
        if record.organization and not _grounded(record.organization, raw_text):
            errors.add("canonical_experience_organization_not_grounded")


def _audit_skills(resume: Resume, raw_text: str, errors: set[str]) -> None:
    values = [item for group in resume.skills.model_dump(mode="python").values() for item in group]
    values.extend(
        item for record in (*resume.internships, *resume.projects) for item in record.tech_stack
    )
    if any(not _grounded(value, raw_text, aliases=True) for value in values):
        errors.add("canonical_technology_not_grounded")


def audit_source_mapping(raw_extraction_path: Path, resume: Resume) -> SourceMappingAuditResult:
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
        raw_source_sha256=str(raw["source_sha256"]), warning_codes=tuple(sorted(warnings))
    )
