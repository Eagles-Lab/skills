"""Isolated batch scoring with preflight de-duplication and atomic publication."""

from __future__ import annotations

import hashlib
from concurrent.futures import Future, ThreadPoolExecutor, as_completed
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Callable

from .analyzer import AnalysisArtifacts, SecurityResumeAnalyzer, load_resume
from .dedup import IdentityConflictError, MergedCandidate, ResumeSource, merge_candidates
from .errors import InputValidationError, OutputConflictError, OutputSafetyError
from .models import Track
from .output import sha256_file, write_run_output


class BatchPreflightError(InputValidationError):
    pass


class BatchProcessor:
    def __init__(
        self,
        output_dir: Path,
        track: Track | str,
        *,
        max_workers: int = 3,
        overwrite: bool = False,
        clock: Callable[[], datetime] | None = None,
    ) -> None:
        if max_workers < 1:
            raise ValueError("max_workers must be at least 1")
        self.output_dir = Path(output_dir)
        self.track = Track(track)
        self.max_workers = max_workers
        self.overwrite = overwrite
        self.clock = clock or (lambda: datetime.now(UTC))

    def process_directory(self, input_dir: Path) -> dict[str, Any]:
        source_dir = Path(input_dir)
        if not source_dir.exists() or not source_dir.is_dir() or source_dir.is_symlink():
            raise BatchPreflightError("input directory must be a real directory")
        if self.output_dir.is_symlink():
            raise OutputSafetyError("refusing to replace an output symlink")
        if self.output_dir.exists() and not self.overwrite:
            raise OutputConflictError(f"output run already exists: {self.output_dir}")
        files = sorted(source_dir.glob("*.json"), key=lambda path: path.as_posix())
        sources: list[ResumeSource] = []
        failures: list[dict[str, Any]] = []
        for path in files:
            if path.is_symlink() or not path.is_file():
                digest = hashlib.sha256(f"unsafe-entry:{path.name}".encode()).hexdigest()
                failures.append(
                    {
                        "source_hashes": [digest],
                        "status": "failed",
                        "error_category": "UnsafeInputEntry",
                    }
                )
                continue
            digest = sha256_file(path)
            try:
                sources.append(ResumeSource(path, digest, load_resume(path)))
            except Exception as exc:
                failures.append(
                    {
                        "source_hashes": [digest],
                        "status": "failed",
                        "error_category": type(exc).__name__,
                    }
                )
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
            "schema_version": "1.0",
            "target_track": self.track.value,
            "generated_at": generated_at,
            "raw_file_count": len(files),
            "unique_candidate_count": len(candidates) + len(identity_failures),
            "successful": len(successful),
            "failed": len(results) - len(successful),
            "deduplicated_source_count": sum(
                candidate.deduplicated_source_count for candidate in candidates
            ),
            "conflict_failure_count": len(identity_failures),
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
        analyzer = SecurityResumeAnalyzer(self.output_dir, self.track, clock=self.clock)
        return analyzer.build_artifacts(
            candidate.resume,
            candidate.source_hashes,
            output_name=candidate.output_name,
            primary_sha256=candidate.primary_sha256,
            conflicts=candidate.conflicts,
        )


def _identity_failure(error: IdentityConflictError) -> dict[str, Any]:
    return {
        "source_hashes": list(error.source_hashes),
        "status": "failed",
        "error_category": type(error).__name__,
        "conflict_fields": list(error.fields),
    }
