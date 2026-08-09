"""Deterministic source-aware batch processing with atomic run publication."""

from __future__ import annotations

from concurrent.futures import Future, ThreadPoolExecutor, as_completed
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Callable, Dict, Optional

from .analyzer import AnalysisArtifacts, ResumeAnalyzer, load_resume
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
    """The batch cannot safely enumerate or identify its inputs."""


AnalyzerFactory = Callable[[Path], ResumeAnalyzer]


def _utc_now() -> datetime:
    return datetime.now(UTC)


class BatchProcessor:
    """Audit, identify, merge, score, and publish one isolated batch."""

    def __init__(
        self,
        output_dir: Path,
        *,
        max_workers: int = 3,
        overwrite: bool = False,
        raw_extraction_dir: Optional[Path] = None,
        analyzer_factory: Optional[AnalyzerFactory] = None,
        clock: Callable[[], datetime] = _utc_now,
    ) -> None:
        if max_workers < 1:
            raise ValueError("max_workers must be at least 1")
        self.output_dir = Path(output_dir)
        self.max_workers = max_workers
        self.overwrite = overwrite
        self.raw_extraction_dir = (
            Path(raw_extraction_dir) if raw_extraction_dir is not None else None
        )
        self.analyzer_factory = analyzer_factory or (lambda root: ResumeAnalyzer(root))
        self.clock = clock

    def process_directory(
        self,
        input_dir: Path,
        *,
        pattern: str = "*.json",
    ) -> Dict[str, Any]:
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
        input_files = sorted(source_dir.glob(pattern), key=lambda path: path.as_posix())
        sources: list[SourceRecord] = []
        failures: list[dict[str, Any]] = []
        for path in input_files:
            if path.is_symlink() or not path.is_file():
                failures.append(_input_failure([], "UnsafeInputEntry"))
                continue
            canonical_digest = sha256_file(path)
            failure_hashes = [canonical_digest] if identity_kind == "canonical_json_sha256" else []
            try:
                resume = load_resume(path)
                source_digest = canonical_digest
                audit_metadata = None
                if self.raw_extraction_dir is not None:
                    raw_path = self._raw_extraction_path(path.stem)
                    raw = load_raw_extraction(raw_path, SourceMappingAuditError)
                    failure_hashes = [raw.source_sha256]
                    audit = audit_source_mapping(raw_path, resume)
                    source_digest = audit.raw_source_sha256
                    audit_metadata = audit.public_metadata()
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
        results: list[dict[str, Any]] = list(failures)
        with ThreadPoolExecutor(max_workers=self.max_workers) as executor:
            futures: dict[Future[AnalysisArtifacts], MergedCandidate] = {
                executor.submit(self._process_one, item): item for item in candidates
            }
            for future in as_completed(futures):
                candidate = futures[future]
                try:
                    artifact = future.result()
                    if artifact.output_name != candidate.output_name:
                        raise RuntimeError("candidate identity changed during analysis")
                    artifacts.append(artifact)
                    grade = artifact.score.get("grade", {})
                    results.append(
                        {
                            "source_hashes": list(candidate.source_hashes),
                            "status": "success",
                            "output_name": artifact.output_name,
                            "total_score": artifact.score.get("total_score", 1.0),
                            "grade": grade.get("grade", "F"),
                            "data_quality_warning_count": len(
                                artifact.score.get("data_quality_warnings", [])
                            ),
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
        summary = self._summary(
            results,
            raw_file_count=len(input_files),
            unique_candidate_count=len(results),
            deduplicated_source_count=sum(
                candidate.deduplicated_source_count for candidate in candidates
            )
            + sum(error.deduplicated_source_count for error in identity_failures),
            conflict_failure_count=len(identity_failures),
            source_mapping_audit_count=sum(
                1 for source in sources if source.audit_metadata is not None
            ),
            source_identity_kind=identity_kind,
        )
        write_run_output(
            self.output_dir,
            [item.output_payload() for item in artifacts],
            batch_summary=summary,
            overwrite=self.overwrite,
        )
        return summary

    def _raw_extraction_path(self, canonical_stem: str) -> Path:
        if self.raw_extraction_dir is None:  # pragma: no cover - guarded by caller
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

    def _process_one(self, candidate: MergedCandidate) -> AnalysisArtifacts:
        analyzer = self.analyzer_factory(self.output_dir)
        return analyzer.build_candidate_artifacts(
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

    def _summary(
        self,
        results: list[dict[str, Any]],
        *,
        raw_file_count: int,
        unique_candidate_count: int,
        deduplicated_source_count: int,
        conflict_failure_count: int,
        source_mapping_audit_count: int,
        source_identity_kind: SourceIdentityKind,
    ) -> Dict[str, Any]:
        successful = [item for item in results if item["status"] == "success"]
        failed = len(results) - len(successful)
        scores = [float(item["total_score"]) for item in successful]
        grade_distribution: Dict[str, int] = {}
        warning_distribution: Dict[str, int] = {}
        for item in successful:
            grade = str(item["grade"])
            grade_distribution[grade] = grade_distribution.get(grade, 0) + 1
            count = str(item["data_quality_warning_count"])
            warning_distribution[count] = warning_distribution.get(count, 0) + 1
        generated_at = self.clock().astimezone(UTC).replace(microsecond=0).isoformat()
        return {
            "schema_version": "1.1",
            "scoring_profile": SCORING_PROFILE,
            "generated_at": generated_at.replace("+00:00", "Z"),
            "raw_file_count": raw_file_count,
            "unique_candidate_count": unique_candidate_count,
            "successful": len(successful),
            "failed": failed,
            "deduplicated_source_count": deduplicated_source_count,
            "conflict_failure_count": conflict_failure_count,
            "source_mapping_audit_count": source_mapping_audit_count,
            "source_identity_kind": source_identity_kind,
            "results": results,
            # Additive compatibility statistics retained for existing SRE consumers.
            "total": len(results),
            "success_rate": round(len(successful) / len(results), 4) if results else 0.0,
            "average_score": round(sum(scores) / len(scores), 1) if scores else 0.0,
            "grade_distribution": dict(sorted(grade_distribution.items())),
            "data_quality_warning_count_distribution": dict(
                sorted(warning_distribution.items(), key=lambda pair: int(pair[0]))
            ),
        }


def _input_failure(source_hashes: list[str], category: str) -> dict[str, Any]:
    return {"source_hashes": source_hashes, "status": "failed", "error_category": category}


def _identity_failure(error: IdentityConflictError) -> dict[str, Any]:
    return {
        "source_hashes": list(error.source_hashes),
        "status": "failed",
        "error_category": type(error).__name__,
        "conflict_fields": list(error.fields),
    }
