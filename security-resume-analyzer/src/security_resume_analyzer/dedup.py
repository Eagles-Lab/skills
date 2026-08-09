"""Security-resume adapter for the shared source identity and merge core."""

from __future__ import annotations

from pathlib import Path
from typing import Any, Mapping

from .dedup_core import (
    IdentityConflictError,
    MergedCandidateRecord,
    SourceRecord,
    aggregate_source_sha256,
    canonical_similarity,
    fact_coverage,
    merge_source_records,
    normalize_email,
    normalize_phone,
    same_candidate,
)
from .models import Resume
from .output import sanitize_display_name

MergedCandidate = MergedCandidateRecord


def ResumeSource(
    path: Path,
    sha256: str,
    resume: Resume,
    source_mapping_audit: Mapping[str, Any] | None = None,
) -> SourceRecord:
    """Compatibility constructor for canonical-only internal callers."""

    return SourceRecord(
        path=path,
        canonical_sha256=sha256,
        source_sha256=sha256,
        source_identity_kind="canonical_json_sha256",
        resume=resume,
        audit_metadata=source_mapping_audit,
    )


def merge_candidates(
    sources: list[SourceRecord],
) -> tuple[list[MergedCandidateRecord], list[IdentityConflictError]]:
    return merge_source_records(
        sources,
        experience_collections=("internships", "projects", "security_activities"),
        validate_resume=Resume.model_validate,
        sanitize_display_name=sanitize_display_name,
    )


__all__ = [
    "IdentityConflictError",
    "MergedCandidate",
    "ResumeSource",
    "SourceRecord",
    "aggregate_source_sha256",
    "canonical_similarity",
    "fact_coverage",
    "merge_candidates",
    "normalize_email",
    "normalize_phone",
    "same_candidate",
]
