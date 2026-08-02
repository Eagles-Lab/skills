"""Deterministic, isolated batch processing with one atomic run publication."""

from __future__ import annotations

from concurrent.futures import Future, ThreadPoolExecutor, as_completed
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Tuple

from .analyzer import AnalysisArtifacts, ResumeAnalyzer, load_resume
from .errors import InputValidationError, OutputConflictError, OutputSafetyError
from .output import (
    derive_output_name,
    derive_resume_id,
    sha256_file,
    validate_resume_id,
    write_run_output,
)


class BatchPreflightError(InputValidationError):
    """The batch cannot start without ambiguous or destructive output."""


AnalyzerFactory = Callable[[Path], ResumeAnalyzer]
PreflightItem = Tuple[Path, str, str, str]


def _utc_now() -> datetime:
    return datetime.now(UTC)


class BatchProcessor:
    """Process canonical JSON files without retaining state between calls."""

    def __init__(
        self,
        output_dir: Path,
        *,
        max_workers: int = 3,
        overwrite: bool = False,
        analyzer_factory: Optional[AnalyzerFactory] = None,
        clock: Callable[[], datetime] = _utc_now,
    ) -> None:
        if max_workers < 1:
            raise ValueError("max_workers must be at least 1")
        self.output_dir = Path(output_dir)
        self.max_workers = max_workers
        self.overwrite = overwrite
        self.analyzer_factory = analyzer_factory or (lambda root: ResumeAnalyzer(root))
        self.clock = clock

    def process_directory(
        self,
        input_dir: Path,
        *,
        pattern: str = "*.json",
    ) -> Dict[str, Any]:
        source_dir = Path(input_dir)
        if not source_dir.exists() or not source_dir.is_dir():
            raise BatchPreflightError(f"input directory does not exist: {source_dir}")
        if self.output_dir.is_symlink():
            raise OutputSafetyError("refusing to replace an output symlink")
        if self.output_dir.exists() and not self.overwrite:
            raise OutputConflictError(f"output run already exists: {self.output_dir}")

        input_files = sorted(
            (path for path in source_dir.glob(pattern) if path.is_file()),
            key=lambda path: path.as_posix(),
        )
        valid, failures = self._preflight(input_files)
        artifacts: List[AnalysisArtifacts] = []
        results: List[Dict[str, Any]] = list(failures)

        with ThreadPoolExecutor(max_workers=self.max_workers) as executor:
            futures: Dict[Future[AnalysisArtifacts], PreflightItem] = {
                executor.submit(self._process_one, item): item for item in valid
            }
            for future in as_completed(futures):
                _path, resume_id, output_name, digest = futures[future]
                try:
                    artifact = future.result()
                    if artifact.resume_id != resume_id or artifact.output_name != output_name:
                        raise RuntimeError("preflight identity changed during analysis")
                    artifacts.append(artifact)
                    score = artifact.score
                    grade = score.get("grade", {})
                    results.append(
                        {
                            "input_sha256": digest,
                            "resume_id": resume_id,
                            "output_name": output_name,
                            "status": "success",
                            "total_score": score.get("total_score", 1.0),
                            "grade": grade.get("grade", "F"),
                            "data_quality_warning_count": len(
                                score.get("data_quality_warnings", [])
                            ),
                        }
                    )
                except Exception as exc:
                    results.append(
                        {
                            "input_sha256": digest,
                            "status": "failed",
                            "error_category": type(exc).__name__,
                        }
                    )

        results.sort(key=lambda item: (str(item.get("input_sha256", "")), item["status"]))
        summary = self._summary(results)
        write_run_output(
            self.output_dir,
            [item.output_payload() for item in artifacts],
            batch_summary=summary,
            overwrite=self.overwrite,
        )
        return summary

    def _preflight(
        self, input_files: List[Path]
    ) -> Tuple[List[PreflightItem], List[Dict[str, Any]]]:
        valid: List[PreflightItem] = []
        failures: List[Dict[str, Any]] = []
        output_owners: Dict[str, Path] = {}
        digest_owners: Dict[str, Path] = {}
        duplicate_outputs: List[str] = []
        duplicate_digests: List[str] = []

        for path in input_files:
            digest = sha256_file(path)
            try:
                resume = load_resume(path)
                resume_id = (
                    validate_resume_id(resume.resume_id)
                    if resume.resume_id is not None
                    else derive_resume_id(resume.basic_info.name, digest)
                )
                output_name = derive_output_name(resume.basic_info.name, digest)
                if output_name in output_owners:
                    duplicate_outputs.append(output_name)
                if digest in digest_owners:
                    duplicate_digests.append(digest[:12])
                if output_name not in output_owners and digest not in digest_owners:
                    output_owners[output_name] = path
                    digest_owners[digest] = path
                    valid.append((path, resume_id, output_name, digest))
            except Exception as exc:
                failures.append(
                    {
                        "input_sha256": digest,
                        "status": "failed",
                        "error_category": type(exc).__name__,
                    }
                )

        if duplicate_outputs or duplicate_digests:
            categories = []
            if duplicate_outputs:
                categories.append("output-name collision")
            if duplicate_digests:
                categories.append("duplicate input")
            raise BatchPreflightError("batch preflight rejected: " + " and ".join(categories))
        return valid, failures

    def _process_one(self, item: PreflightItem) -> AnalysisArtifacts:
        path, _resume_id, _output_name, _digest = item
        analyzer = self.analyzer_factory(self.output_dir)
        return analyzer.build_artifacts(path)

    def _summary(self, results: List[Dict[str, Any]]) -> Dict[str, Any]:
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
            "generated_at": generated_at.replace("+00:00", "Z"),
            "total": len(results),
            "successful": len(successful),
            "failed": failed,
            "success_rate": round(len(successful) / len(results), 4) if results else 0.0,
            "average_score": round(sum(scores) / len(scores), 1) if scores else 0.0,
            "grade_distribution": dict(sorted(grade_distribution.items())),
            "data_quality_warning_count_distribution": dict(
                sorted(warning_distribution.items(), key=lambda pair: int(pair[0]))
            ),
            "results": results,
        }
