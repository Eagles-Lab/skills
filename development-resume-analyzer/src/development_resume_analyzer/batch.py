"""Isolated batch scoring with source-aware de-duplication and atomic publication."""

from __future__ import annotations

from concurrent.futures import Future, ThreadPoolExecutor, as_completed
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Callable

from .analyzer import AnalysisArtifacts, DevelopmentResumeAnalyzer, load_resume
from .dedup import IdentityConflictError, MergedCandidate, SourceRecord, merge_candidates
from .dedup_core import SourceIdentityKind
from .errors import (
    InputValidationError,
    OutputConflictError,
    OutputSafetyError,
    SourceMappingAuditError,
)
from .models import SCORING_PROFILE
from .output import sha256_file, write_run_output
from .source_audit import audit_source_mapping
from .source_audit_core import load_raw_extraction


class BatchPreflightError(InputValidationError):
    pass


class BatchProcessor:
    def __init__(
        self,
        output_dir: Path,
        *,
        max_workers: int = 3,
        overwrite: bool = False,
        clock: Callable[[], datetime] | None = None,
        raw_extraction_dir: Path | None = None,
    ) -> None:
        if max_workers < 1:
            raise ValueError("max_workers must be at least 1")
        self.output_dir = Path(output_dir)
        self.max_workers = max_workers
        self.overwrite = overwrite
        self.clock = clock or (lambda: datetime.now(UTC))
        self.raw_extraction_dir = Path(raw_extraction_dir) if raw_extraction_dir else None

    def process_directory(self, input_dir: Path) -> dict[str, Any]:
        source_dir = Path(input_dir)
        if not source_dir.exists() or not source_dir.is_dir() or source_dir.is_symlink():
            raise BatchPreflightError("input directory must be a real directory")
        if self.output_dir.is_symlink():
            raise OutputSafetyError("refusing to replace an output symlink")
        if self.output_dir.exists() and not self.overwrite:
            raise OutputConflictError(f"output run already exists: {self.output_dir}")
        if self.raw_extraction_dir is not None and (
            not self.raw_extraction_dir.exists()
            or not self.raw_extraction_dir.is_dir()
            or self.raw_extraction_dir.is_symlink()
        ):
            raise BatchPreflightError("raw extraction directory must be a real directory")

        identity_kind: SourceIdentityKind = (
            "raw_document_sha256"
            if self.raw_extraction_dir is not None
            else "canonical_json_sha256"
        )
        files = sorted(source_dir.glob("*.json"), key=lambda path: path.as_posix())
        sources: list[SourceRecord] = []
        failures: list[dict[str, Any]] = []
        for path in files:
            if path.is_symlink() or not path.is_file():
                failures.append(_input_failure([], "UnsafeInputEntry"))
                continue
            canonical_digest = sha256_file(path)
            failure_hashes = [canonical_digest] if identity_kind == "canonical_json_sha256" else []
            try:
                resume = load_resume(path)
                audit_metadata = None
                source_digest = canonical_digest
                if self.raw_extraction_dir is not None:
                    raw_path = self._raw_extraction_path(path.stem)
                    raw = load_raw_extraction(raw_path, SourceMappingAuditError)
                    failure_hashes = [raw.source_sha256]
                    audit = audit_source_mapping(raw_path, resume)
                    audit_metadata = audit.public_metadata()
                    source_digest = audit.raw_source_sha256
                sources.append(
                    SourceRecord(
                        path=path,
                        canonical_sha256=canonical_digest,
                        source_sha256=source_digest,
                        source_identity_kind=identity_kind,
                        resume=resume,
                        audit_metadata=audit_metadata,
                    )
                )
            except Exception as exc:
                failures.append(_input_failure(failure_hashes, type(exc).__name__))

        candidates, identity_failures = merge_candidates(sources)
        failures.extend(_identity_failure(value) for value in identity_failures)
        artifacts: list[AnalysisArtifacts] = []
        results = list(failures)
        with ThreadPoolExecutor(max_workers=self.max_workers) as executor:
            futures: dict[Future[AnalysisArtifacts], MergedCandidate] = {
                executor.submit(self._process_one, candidate): candidate for candidate in candidates
            }
            for future in as_completed(futures):
                candidate = futures[future]
                try:
                    artifact = future.result()
                    artifacts.append(artifact)
                    results.append(
                        {
                            "source_hashes": list(candidate.source_hashes),
                            "status": "success",
                            "output_name": artifact.output_name,
                            "total_score": artifact.score["total_score"],
                            "grade": artifact.score["grade"]["grade"],
                        }
                    )
                except Exception as exc:
                    results.append(
                        {
                            "source_hashes": list(candidate.source_hashes),
                            "status": "failed",
                            "error_category": type(exc).__name__,
                        }
                    )
        results.sort(key=lambda item: (item["source_hashes"], item["status"]))
        successful = [item for item in results if item["status"] == "success"]
        generated_at = (
            self.clock().astimezone(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")
        )
        summary = {
            "schema_version": "1.1",
            "scoring_profile": SCORING_PROFILE,
            "generated_at": generated_at,
            "raw_file_count": len(files),
            "unique_candidate_count": len(results),
            "successful": len(successful),
            "failed": len(results) - len(successful),
            "deduplicated_source_count": sum(
                candidate.deduplicated_source_count for candidate in candidates
            )
            + sum(error.deduplicated_source_count for error in identity_failures),
            "conflict_failure_count": len(identity_failures),
            "source_mapping_audit_count": sum(
                1 for source in sources if source.audit_metadata is not None
            ),
            "source_identity_kind": identity_kind,
            "results": results,
        }
        write_run_output(
            self.output_dir,
            [item.output_payload() for item in artifacts],
            batch_summary=summary,
            overwrite=self.overwrite,
        )
        return summary

    def _process_one(self, candidate: MergedCandidate) -> AnalysisArtifacts:
        analyzer = DevelopmentResumeAnalyzer(self.output_dir, clock=self.clock)
        return analyzer.build_artifacts(
            candidate.resume,
            candidate.source_hashes,
            output_name=candidate.output_name,
            primary_sha256=candidate.primary_sha256,
            primary_canonical_sha256=candidate.primary_canonical_sha256,
            source_record_count=candidate.source_record_count,
            source_identity_kind=candidate.source_identity_kind,
            conflicts=candidate.conflicts,
            source_mapping_audits=candidate.source_mapping_audits,
        )

    def _raw_extraction_path(self, canonical_stem: str) -> Path:
        if self.raw_extraction_dir is None:  # pragma: no cover - caller guards this
            raise BatchPreflightError("raw extraction directory is not configured")
        root = self.raw_extraction_dir.resolve(strict=True)
        candidate = self.raw_extraction_dir / canonical_stem
        try:
            resolved = candidate.resolve(strict=True)
            resolved.relative_to(root)
        except (OSError, ValueError) as exc:
            raise BatchPreflightError("raw extraction path is missing or unsafe") from exc
        if candidate.is_symlink() or not resolved.is_dir():
            raise BatchPreflightError("raw extraction candidate path must be a real directory")
        return resolved / "raw_extraction.json"


def _input_failure(source_hashes: list[str], category: str) -> dict[str, Any]:
    return {"source_hashes": source_hashes, "status": "failed", "error_category": category}


def _identity_failure(error: IdentityConflictError) -> dict[str, Any]:
    return {
        "source_hashes": list(error.source_hashes),
        "status": "failed",
        "error_category": type(error).__name__,
        "conflict_fields": list(error.fields),
    }
