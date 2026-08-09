"""Domain-neutral source identity, candidate grouping, and deterministic merge core."""

from __future__ import annotations

import hashlib
import json
import re
import unicodedata
from collections import Counter
from dataclasses import dataclass
from difflib import SequenceMatcher
from pathlib import Path
from typing import Any, Callable, Iterable, Literal, Mapping, Sequence

SourceIdentityKind = Literal["raw_document_sha256", "canonical_json_sha256"]
_SHA256 = re.compile(r"^[a-f0-9]{64}$")


@dataclass(frozen=True)
class SourceRecord:
    """One canonical mapping plus the source identity used for grouping."""

    path: Path
    canonical_sha256: str
    source_sha256: str
    source_identity_kind: SourceIdentityKind
    resume: Any
    audit_metadata: Mapping[str, Any] | None = None

    def __post_init__(self) -> None:
        if not _SHA256.fullmatch(self.canonical_sha256):
            raise ValueError("canonical_sha256 must be a lowercase SHA-256 digest")
        if not _SHA256.fullmatch(self.source_sha256):
            raise ValueError("source_sha256 must be a lowercase SHA-256 digest")


@dataclass(frozen=True)
class MergedCandidateRecord:
    """One candidate after identity grouping and primary-first fact merging."""

    resume: Any
    source_hashes: tuple[str, ...]
    source_record_count: int
    primary_sha256: str
    primary_canonical_sha256: str
    output_name: str
    conflicts: tuple[dict[str, str], ...]
    source_mapping_audits: tuple[dict[str, Any], ...]
    source_identity_kind: SourceIdentityKind
    aggregate_sha256: str

    @property
    def unique_source_count(self) -> int:
        return len(self.source_hashes)

    @property
    def deduplicated_source_count(self) -> int:
        return max(0, self.source_record_count - 1)


class IdentityConflictError(ValueError):
    """A grouped or colliding candidate cannot be resolved without a human."""

    def __init__(
        self,
        source_hashes: Iterable[str],
        fields: Iterable[str],
        *,
        source_record_count: int | None = None,
    ) -> None:
        self.source_hashes = tuple(sorted(set(source_hashes)))
        self.fields = tuple(sorted(set(fields)))
        self.source_record_count = source_record_count or len(self.source_hashes)
        super().__init__("candidate identity conflict requires manual confirmation")

    @property
    def unique_source_count(self) -> int:
        return len(self.source_hashes)

    @property
    def deduplicated_source_count(self) -> int:
        return max(0, self.source_record_count - 1)


def aggregate_source_sha256(source_hashes: Iterable[str]) -> str:
    """Hash the sorted unique fixed-width source identities."""

    unique = tuple(sorted(set(source_hashes)))
    if not unique or any(not _SHA256.fullmatch(value) for value in unique):
        raise ValueError("source hashes must contain lowercase SHA-256 digests")
    return hashlib.sha256("".join(unique).encode()).hexdigest()


def normalize_email(value: str | None) -> str | None:
    normalized = unicodedata.normalize("NFKC", value).strip().casefold() if value else ""
    if normalized.count("@") != 1 or len(normalized) > 320:
        return None
    local, domain = normalized.split("@")
    if (
        not local
        or len(local) > 64
        or local.startswith(".")
        or local.endswith(".")
        or ".." in local
        or not re.fullmatch(r"[a-z0-9.!#$%&'*+/=?^_`{|}~-]+", local)
    ):
        return None
    labels = domain.split(".")
    if len(labels) < 2 or any(
        not label
        or label.startswith("-")
        or label.endswith("-")
        or not re.fullmatch(r"[a-z0-9-]+", label)
        for label in labels
    ):
        return None
    return normalized if re.fullmatch(r"[a-z]{2,}", labels[-1]) else None


def normalize_phone(value: str | None) -> str | None:
    normalized = unicodedata.normalize("NFKC", value or "")
    base = re.sub(
        r"(?i)\s*(?:ext\.?|extension|x|转|分机)\s*\d+\s*$",
        "",
        normalized,
    )
    base = base.strip()
    digits = re.sub(r"\D", "", base)
    if len(digits) < 7 or len(set(digits)) == 1:
        return None
    if base.startswith("+"):
        if digits.startswith("86"):
            domestic = digits[2:]
            if len(domestic) >= 7 and len(set(domestic)) == 1:
                return None
            if re.fullmatch(r"1[3-9]\d{9}", domestic):
                return f"cn:{domestic}"
        return f"intl:+{digits}" if 8 <= len(digits) <= 15 else None
    if base.startswith("00"):
        international = digits[2:]
        if international.startswith("86"):
            domestic = international[2:]
            if len(domestic) >= 7 and len(set(domestic)) == 1:
                return None
            if re.fullmatch(r"1[3-9]\d{9}", domestic):
                return f"cn:{domestic}"
        return f"intl:+{international}" if 8 <= len(international) <= 15 else None
    if re.fullmatch(r"1[3-9]\d{9}", digits):
        return f"cn:{digits}"
    if len(digits) < 10:
        return None
    return f"local:{digits}"


SimilarityToken = tuple[str, tuple[int, ...], str, str]
_EXPERIENCE_COLLECTIONS = frozenset({"internships", "projects", "security_activities"})


def _normalize_similarity_scalar(value: Any) -> str | None:
    if value is None:
        return None
    normalized = re.sub(
        r"\s+",
        "",
        unicodedata.normalize("NFKC", str(value)).casefold(),
    )
    if not normalized or normalized in {"other", "unknown"}:
        return None
    return normalized


def _prune_similarity_value(value: Any) -> Any:
    if isinstance(value, Mapping):
        populated = {
            str(key): item
            for key in sorted(value)
            if (item := _prune_similarity_value(value[key])) is not None
        }
        return populated or None
    if isinstance(value, list):
        unique: dict[str, Any] = {}
        for raw_item in value:
            item = _prune_similarity_value(raw_item)
            if item is None:
                continue
            stable = json.dumps(item, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
            unique.setdefault(stable, item)
        return [unique[key] for key in sorted(unique)] or None
    return _normalize_similarity_scalar(value)


def _append_similarity_tokens(
    tokens: list[SimilarityToken], value: Any, *, scope: str, slot: tuple[int, ...]
) -> None:
    if isinstance(value, Mapping):
        children: list[SimilarityToken] = []
        for ordinal, key in enumerate(sorted(value)):
            _append_similarity_tokens(
                children,
                value[key],
                scope=scope,
                slot=(*slot, ordinal),
            )
        if children:
            tokens.append((scope, slot, "group", "start"))
            tokens.extend(children)
        return
    if isinstance(value, list):
        children = []
        unique: dict[str, Any] = {}
        for raw_item in value:
            item = _prune_similarity_value(raw_item)
            if item is None:
                continue
            stable = json.dumps(item, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
            unique.setdefault(stable, raw_item)
        for stable in sorted(unique):
            children.append((scope, slot, "item", "start"))
            _append_similarity_tokens(children, unique[stable], scope=scope, slot=slot)
            children.append((scope, slot, "item", "end"))
        if children:
            tokens.append((scope, slot, "group", "start"))
            tokens.extend(children)
        return
    normalized = _normalize_similarity_scalar(value)
    if normalized is None:
        return
    tokens.extend((scope, slot, "value", character) for character in normalized)


def _append_experience_similarity_tokens(
    tokens: list[SimilarityToken],
    collection: str,
    raw_records: list[Any],
    *,
    slot: tuple[int, ...],
) -> None:
    records: dict[str, tuple[tuple[str, str, str], bool, Mapping[str, Any]]] = {}
    for raw_record in raw_records:
        if not isinstance(raw_record, Mapping):
            continue
        record = _prune_similarity_value(raw_record)
        if not isinstance(record, Mapping):
            continue
        stable = json.dumps(record, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
        key = _experience_key(raw_record)
        records.setdefault(stable, (key, _has_strong_experience_key(key, collection), record))
    if not records:
        return
    ordered = sorted(
        records.items(),
        key=lambda item: (
            not item[1][1],
            item[1][0] if item[1][1] else ("", "", ""),
            item[0],
        ),
    )
    weak_index = 0
    for _stable, (key, strong, record) in ordered:
        identity = "\x1e".join(key) if strong else str(weak_index)
        if not strong:
            weak_index += 1
        scope = f"{collection}\x1f{'strong' if strong else 'weak'}\x1f{identity}"
        tokens.append((scope, slot, "record", "start"))
        for ordinal, field in enumerate(sorted(raw_records[0])):
            if field not in record:
                continue
            _append_similarity_tokens(
                tokens,
                record[field],
                scope=scope,
                slot=(*slot, ordinal),
            )


def _similarity_payload(resume: Any) -> tuple[SimilarityToken, ...]:
    data = resume.model_dump(mode="json", exclude={"resume_id"})
    data.pop("basic_info", None)
    tokens: list[SimilarityToken] = []
    for ordinal, field in enumerate(sorted(data)):
        raw_value = data[field]
        value = _prune_similarity_value(raw_value)
        if value is None:
            continue
        slot = (ordinal,)
        if field in _EXPERIENCE_COLLECTIONS and isinstance(raw_value, list):
            _append_experience_similarity_tokens(tokens, field, raw_value, slot=slot)
            continue
        _append_similarity_tokens(tokens, raw_value, scope="resume", slot=slot)
    return tuple(tokens)


def canonical_similarity(left: Any, right: Any) -> float:
    """Compare substantive value slots while preserving record-field associations."""

    left_payload = _similarity_payload(left)
    right_payload = _similarity_payload(right)
    if not left_payload or not right_payload:
        return 0.0
    forward = SequenceMatcher(None, left_payload, right_payload, autojunk=False).ratio()
    reverse = SequenceMatcher(None, right_payload, left_payload, autojunk=False).ratio()
    return min(forward, reverse)


def same_candidate(left: Any, right: Any) -> bool:
    """Apply contact identity or the strict no-contact metadata fallback."""

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
    supplied_contacts = tuple(
        getattr(contact, field, None) if contact else None
        for contact in (left_contact, right_contact)
        for field in ("email", "phone")
    )
    if any(value is not None and str(value).strip() for value in supplied_contacts):
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


def fact_coverage(resume: Any) -> int:
    """Count unique populated canonical leaves for deterministic primary selection."""

    return _populated_coverage(resume.model_dump(mode="python", exclude={"resume_id"}))


def _populated_coverage(value: Any) -> int:
    if value in (None, "", [], {}):
        return 0
    if isinstance(value, dict):
        return sum(_populated_coverage(item) for item in value.values())
    if isinstance(value, list):
        unique = {
            json.dumps(item, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
            for item in value
        }
        return sum(_populated_coverage(json.loads(item)) for item in unique)
    return 1


def _merge_fact_coverage(resume: Any, experience_collections: Sequence[str]) -> int:
    data = resume.model_dump(mode="python", exclude={"resume_id"})
    for collection in experience_collections:
        data[collection] = _merge_experiences([], data[collection], collection, [])
    return _populated_coverage(data)


def merge_source_records(
    sources: Sequence[SourceRecord],
    *,
    experience_collections: Sequence[str],
    validate_resume: Callable[[Mapping[str, Any]], Any],
    sanitize_display_name: Callable[[str | None], str],
) -> tuple[list[MergedCandidateRecord], list[IdentityConflictError]]:
    """Group by the public identity rules, merge missing facts, and flag collisions."""

    kinds = {item.source_identity_kind for item in sources}
    if len(kinds) > 1:
        raise ValueError("a batch must use exactly one source identity kind")
    groups: list[list[SourceRecord]] = []
    for source in sorted(
        sources,
        key=lambda item: (item.source_sha256, item.canonical_sha256, item.path.as_posix()),
    ):
        matches = [
            group for group in groups if any(_same_source_candidate(source, item) for item in group)
        ]
        if not matches:
            groups.append([source])
            continue
        primary = matches[0]
        primary.append(source)
        for extra in matches[1:]:
            primary.extend(extra)
            groups.remove(extra)

    merged: list[MergedCandidateRecord] = []
    failures: list[IdentityConflictError] = []
    for group in groups:
        conflicts = _identity_conflicts(group)
        if conflicts:
            failures.append(
                IdentityConflictError(
                    (item.source_sha256 for item in group),
                    conflicts,
                    source_record_count=len(group),
                )
            )
            continue
        merged.append(
            _merge_group(
                group,
                experience_collections=experience_collections,
                validate_resume=validate_resume,
                sanitize_display_name=sanitize_display_name,
            )
        )

    output_name_counts = Counter(item.output_name for item in merged)
    unambiguous: list[MergedCandidateRecord] = []
    for candidate in merged:
        if output_name_counts[candidate.output_name] > 1:
            failures.append(
                IdentityConflictError(
                    candidate.source_hashes,
                    ("insufficient_identity",),
                    source_record_count=candidate.source_record_count,
                )
            )
        else:
            unambiguous.append(candidate)
    return sorted(unambiguous, key=lambda item: item.output_name), failures


def _same_source_candidate(left: SourceRecord, right: SourceRecord) -> bool:
    if (
        left.source_identity_kind == "raw_document_sha256"
        and right.source_identity_kind == "raw_document_sha256"
        and left.source_sha256 == right.source_sha256
    ):
        return True
    return same_candidate(left.resume, right.resume)


def _identity_value(value: object) -> str:
    return unicodedata.normalize("NFKC", str(value)).strip().casefold()


def _identity_conflicts(group: Sequence[SourceRecord]) -> list[str]:
    conflicts: list[str] = []
    resume_ids = {
        item.resume.resume_id for item in group if getattr(item.resume, "resume_id", None)
    }
    if len(resume_ids) > 1:
        conflicts.append("resume_id")
    for field in ("name", "school", "major", "graduation_year"):
        values = {
            _identity_value(value)
            for item in group
            if (value := getattr(item.resume.basic_info, field)) is not None
        }
        if len(values) > 1:
            conflicts.append(field)
    for field, normalizer in (("email", normalize_email), ("phone", normalize_phone)):
        contact_values: set[str] = set()
        for item in group:
            contact = item.resume.basic_info.contact
            raw_value = getattr(contact, field) if contact else None
            normalized = normalizer(raw_value)
            if raw_value is not None and str(raw_value).strip():
                contact_values.add(normalized or f"invalid:{_identity_value(raw_value)}")
        if len(contact_values) > 1:
            conflicts.append(f"contact.{field}")
    return conflicts


def _merge_group(
    group: Sequence[SourceRecord],
    *,
    experience_collections: Sequence[str],
    validate_resume: Callable[[Mapping[str, Any]], Any],
    sanitize_display_name: Callable[[str | None], str],
) -> MergedCandidateRecord:
    ranked = sorted(
        group,
        key=lambda item: (
            -_merge_fact_coverage(item.resume, experience_collections),
            item.source_sha256,
            item.canonical_sha256,
        ),
    )
    primary = ranked[0]
    data = primary.resume.model_dump(mode="python")
    conflicts: list[dict[str, str]] = []
    for collection in experience_collections:
        data[collection] = _merge_experiences([], data[collection], collection, conflicts)
    for secondary in ranked[1:]:
        secondary_data = secondary.resume.model_dump(mode="python")
        _fill_mapping(data["basic_info"], secondary_data["basic_info"], "basic_info", conflicts)
        _fill_mapping(data["skills"], secondary_data["skills"], "skills", conflicts)
        if not data.get("resume_id") and secondary_data.get("resume_id"):
            data["resume_id"] = secondary_data["resume_id"]
        for collection in experience_collections:
            data[collection] = _merge_experiences(
                data[collection], secondary_data[collection], collection, conflicts
            )
    resume = validate_resume(data)
    source_hashes = tuple(sorted({item.source_sha256 for item in group}))
    aggregate = aggregate_source_sha256(source_hashes)
    output_name = f"{sanitize_display_name(resume.basic_info.name)}-{aggregate[:8]}"
    audits = tuple(
        dict(item.audit_metadata)
        for item in sorted(
            group,
            key=lambda value: (
                value.source_sha256,
                value.canonical_sha256,
                value.path.as_posix(),
            ),
        )
        if item.audit_metadata is not None
    )
    return MergedCandidateRecord(
        resume=resume,
        source_hashes=source_hashes,
        source_record_count=len(group),
        primary_sha256=primary.source_sha256,
        primary_canonical_sha256=primary.canonical_sha256,
        output_name=output_name,
        conflicts=tuple(conflicts),
        source_mapping_audits=audits,
        source_identity_kind=primary.source_identity_kind,
        aggregate_sha256=aggregate,
    )


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


def _experience_key(value: Mapping[str, Any]) -> tuple[str, str, str]:
    organization = value.get("organization") or value.get("company") or ""
    return (
        _identity_value(organization),
        _identity_value(value.get("name") or ""),
        _identity_value(value.get("duration") or ""),
    )


def _has_strong_experience_key(key: tuple[str, str, str], path: str) -> bool:
    organization, name, duration = key
    collection = path.partition(".")[0]
    if collection == "internships":
        return bool(organization and duration)
    if collection in {"projects", "security_activities"}:
        return bool(name and (organization or duration))
    return False


def _merge_experiences(
    target: list[dict[str, Any]],
    source: list[dict[str, Any]],
    path: str,
    conflicts: list[dict[str, str]],
) -> list[dict[str, Any]]:
    result = list(target)
    positions: dict[tuple[str, str, str], int] = {}
    for index, value in enumerate(result):
        key = _experience_key(value)
        if _has_strong_experience_key(key, path):
            positions[key] = index
    for value in source:
        key = _experience_key(value)
        if not _has_strong_experience_key(key, path):
            if value not in result:
                result.append(value)
            continue
        if key not in positions:
            positions[key] = len(result)
            result.append(value)
            continue
        index = positions[key]
        _fill_mapping(result[index], value, f"{path}.{index}", conflicts)
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
