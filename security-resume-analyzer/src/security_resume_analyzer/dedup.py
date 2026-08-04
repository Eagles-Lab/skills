"""Deterministic cross-format candidate identity and fact de-duplication."""

from __future__ import annotations

import hashlib
import json
import re
import unicodedata
from dataclasses import dataclass
from difflib import SequenceMatcher
from pathlib import Path
from typing import Any, Iterable

from .models import Resume
from .output import sanitize_display_name


@dataclass(frozen=True)
class ResumeSource:
    path: Path
    sha256: str
    resume: Resume


@dataclass(frozen=True)
class MergedCandidate:
    resume: Resume
    source_hashes: tuple[str, ...]
    primary_sha256: str
    output_name: str
    conflicts: tuple[dict[str, str], ...]

    @property
    def deduplicated_source_count(self) -> int:
        return max(0, len(self.source_hashes) - 1)


class IdentityConflictError(ValueError):
    def __init__(self, source_hashes: Iterable[str], fields: Iterable[str]) -> None:
        self.source_hashes = tuple(sorted(source_hashes))
        self.fields = tuple(sorted(set(fields)))
        super().__init__("candidate identity conflict requires manual confirmation")


def normalize_email(value: str | None) -> str | None:
    return unicodedata.normalize("NFKC", value).strip().casefold() if value else None


def normalize_phone(value: str | None) -> str | None:
    digits = re.sub(r"\D", "", unicodedata.normalize("NFKC", value or ""))
    return digits[-11:] if len(digits) >= 7 else None


def canonical_similarity(left: Resume, right: Resume) -> float:
    def payload(resume: Resume) -> str:
        data = resume.model_dump(mode="json", exclude={"resume_id"})
        data["basic_info"].pop("contact", None)
        text = json.dumps(data, ensure_ascii=False, sort_keys=True)
        return re.sub(r"\s+", "", unicodedata.normalize("NFKC", text).casefold())

    return SequenceMatcher(None, payload(left), payload(right), autojunk=False).ratio()


def same_candidate(left: Resume, right: Resume) -> bool:
    left_contact = left.basic_info.contact
    right_contact = right.basic_info.contact
    emails = (
        normalize_email(left_contact.email) if left_contact else None,
        normalize_email(right_contact.email) if right_contact else None,
    )
    phones = (
        normalize_phone(left_contact.phone) if left_contact else None,
        normalize_phone(right_contact.phone) if right_contact else None,
    )
    if emails[0] and emails[0] == emails[1]:
        return True
    if phones[0] and phones[0] == phones[1]:
        return True
    if any((*emails, *phones)):
        return False
    identity = ("name", "school", "major", "graduation_year")
    values = [(getattr(left.basic_info, key), getattr(right.basic_info, key)) for key in identity]
    return (
        all(
            a is not None and b is not None and _identity_value(a) == _identity_value(b)
            for a, b in values
        )
        and canonical_similarity(left, right) >= 0.80
    )


def merge_candidates(
    sources: list[ResumeSource],
) -> tuple[list[MergedCandidate], list[IdentityConflictError]]:
    groups: list[list[ResumeSource]] = []
    for source in sorted(sources, key=lambda item: item.sha256):
        matches = [
            group
            for group in groups
            if any(
                source.sha256 == item.sha256 or same_candidate(source.resume, item.resume)
                for item in group
            )
        ]
        if not matches:
            groups.append([source])
            continue
        primary = matches[0]
        primary.append(source)
        for extra in matches[1:]:
            primary.extend(extra)
            groups.remove(extra)

    merged: list[MergedCandidate] = []
    failures: list[IdentityConflictError] = []
    for group in groups:
        conflicts = _identity_conflicts(group)
        if conflicts:
            failures.append(IdentityConflictError((item.sha256 for item in group), conflicts))
            continue
        merged.append(_merge_group(group))
    return sorted(merged, key=lambda item: item.output_name), failures


def fact_coverage(resume: Resume) -> int:
    def count(value: Any) -> int:
        if value in (None, "", [], {}):
            return 0
        if isinstance(value, dict):
            return sum(count(item) for item in value.values())
        if isinstance(value, list):
            return sum(count(item) for item in value)
        return 1

    return count(resume.model_dump(mode="python", exclude={"resume_id"}))


def _identity_value(value: object) -> str:
    return unicodedata.normalize("NFKC", str(value)).strip().casefold()


def _identity_conflicts(group: list[ResumeSource]) -> list[str]:
    conflicts = []
    for field in ("name", "school", "major", "graduation_year"):
        values = {
            _identity_value(value)
            for item in group
            if (value := getattr(item.resume.basic_info, field)) is not None
        }
        if len(values) > 1:
            conflicts.append(field)
    contacts = [(item.resume.basic_info.contact, item.sha256) for item in group]
    for field, normalizer in (("email", normalize_email), ("phone", normalize_phone)):
        contact_values: set[str] = set()
        for contact, _ in contacts:
            normalized = normalizer(getattr(contact, field)) if contact else None
            if normalized:
                contact_values.add(normalized)
        if len(contact_values) > 1:
            conflicts.append(f"contact.{field}")
    return conflicts


def _merge_group(group: list[ResumeSource]) -> MergedCandidate:
    ranked = sorted(group, key=lambda item: (-fact_coverage(item.resume), item.sha256))
    primary = ranked[0]
    data = primary.resume.model_dump(mode="python")
    conflicts: list[dict[str, str]] = []
    for secondary in ranked[1:]:
        secondary_data = secondary.resume.model_dump(mode="python")
        _fill_mapping(data["basic_info"], secondary_data["basic_info"], "basic_info", conflicts)
        _fill_mapping(data["skills"], secondary_data["skills"], "skills", conflicts)
        for collection in ("internships", "projects", "security_activities"):
            data[collection] = _merge_experiences(
                data[collection], secondary_data[collection], collection, conflicts
            )
    resume = Resume.model_validate(data)
    source_hashes = tuple(sorted(item.sha256 for item in group))
    combined = hashlib.sha256("".join(source_hashes).encode()).hexdigest()[:8]
    output_name = f"{sanitize_display_name(resume.basic_info.name)}-{combined}"
    return MergedCandidate(resume, source_hashes, primary.sha256, output_name, tuple(conflicts))


def _fill_mapping(
    target: dict[str, Any], source: dict[str, Any], path: str, conflicts: list[dict[str, str]]
) -> None:
    for key, value in source.items():
        current = target.get(key)
        if current in (None, "", [], {}):
            target[key] = value
        elif isinstance(current, dict) and isinstance(value, dict):
            _fill_mapping(current, value, f"{path}.{key}", conflicts)
        elif value not in (None, "", [], {}) and current != value:
            conflicts.append({"path": f"{path}.{key}", "resolution": "kept_primary"})


def _experience_key(value: dict[str, Any]) -> tuple[str, str, str]:
    return tuple(
        _identity_value(value.get(key) or "") for key in ("organization", "name", "duration")
    )  # type: ignore[return-value]


def _merge_experiences(
    target: list[dict[str, Any]],
    source: list[dict[str, Any]],
    path: str,
    conflicts: list[dict[str, str]],
) -> list[dict[str, Any]]:
    result = list(target)
    positions = {_experience_key(value): index for index, value in enumerate(result)}
    for value in source:
        key = _experience_key(value)
        if key == ("", "", "") or key not in positions:
            positions[key] = len(result)
            result.append(value)
            continue
        index = positions[key]
        _fill_mapping(result[index], value, f"{path}.{index}", conflicts)
    # Canonicalization removes exact duplicates even when input order differs.
    unique: dict[str, dict[str, Any]] = {}
    for value in result:
        serialized = json.dumps(value, ensure_ascii=False, sort_keys=True)
        unique.setdefault(serialized, value)
    return sorted(
        unique.values(),
        key=lambda value: (
            _experience_key(value),
            json.dumps(value, ensure_ascii=False, sort_keys=True),
        ),
    )
