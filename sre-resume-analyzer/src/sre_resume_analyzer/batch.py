"""Deterministic, isolated batch processing."""

from __future__ import annotations

import json
from concurrent.futures import Future, ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Tuple

from .analyzer import ResumeAnalyzer, load_resume
from .errors import InputValidationError, OutputConflictError, OutputSafetyError
from .output import derive_resume_id, sha256_file, validate_resume_id, write_json_atomically


class BatchPreflightError(InputValidationError):
    """The batch cannot start without ambiguous or destructive output."""


AnalyzerFactory = Callable[[Path], ResumeAnalyzer]


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


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

        summary_path = self.output_dir / "batch_summary.json"
        if summary_path.is_symlink():
            raise OutputSafetyError("refusing to replace a batch summary symlink")
        if summary_path.exists() and not self.overwrite:
            raise OutputConflictError(f"batch summary already exists: {summary_path}")

        input_files = sorted(
            (path for path in source_dir.glob(pattern) if path.is_file()),
            key=lambda path: path.as_posix(),
        )
        valid, failures = self._preflight(input_files)
        results: List[Dict[str, Any]] = list(failures)

        with ThreadPoolExecutor(max_workers=self.max_workers) as executor:
            futures: Dict[Future[Dict[str, Any]], Tuple[Path, str]] = {
                executor.submit(self._process_one, path, resume_id): (path, resume_id)
                for path, resume_id in valid
            }
            for future in as_completed(futures):
                path, resume_id = futures[future]
                try:
                    results.append(future.result())
                except Exception as exc:
                    results.append(
                        {
                            "file": str(path),
                            "resume_id": resume_id,
                            "status": "failed",
                            "error_type": type(exc).__name__,
                            "error": str(exc),
                        }
                    )

        results.sort(key=lambda item: item["file"])
        summary = self._summary(results)
        write_json_atomically(summary_path, summary, overwrite=self.overwrite)
        return summary

    def _preflight(
        self, input_files: List[Path]
    ) -> Tuple[List[Tuple[Path, str]], List[Dict[str, Any]]]:
        valid: List[Tuple[Path, str]] = []
        failures: List[Dict[str, Any]] = []
        owners: Dict[str, Path] = {}
        duplicates: List[str] = []

        for path in input_files:
            try:
                resume = load_resume(path)
                digest = sha256_file(path)
                resume_id = (
                    validate_resume_id(resume.resume_id)
                    if resume.resume_id is not None
                    else derive_resume_id(resume.basic_info.name, digest)
                )
                if resume_id in owners:
                    duplicates.append(resume_id)
                else:
                    owners[resume_id] = path
                    valid.append((path, resume_id))
            except Exception as exc:
                failures.append(
                    {
                        "file": str(path),
                        "status": "failed",
                        "error_type": type(exc).__name__,
                        "error": str(exc),
                    }
                )

        if duplicates:
            unique = ", ".join(sorted(set(duplicates)))
            raise BatchPreflightError(f"duplicate output resume_id values: {unique}")
        return valid, failures

    def _process_one(self, path: Path, expected_resume_id: str) -> Dict[str, Any]:
        # Every task gets a fresh analyzer, scorer, renderer, and temporary directory.
        analyzer = self.analyzer_factory(self.output_dir)
        output_files = analyzer.analyze(path, overwrite=self.overwrite)
        with Path(output_files["score"]).open("r", encoding="utf-8") as handle:
            score = json.load(handle)
        actual_resume_id = score.get("resume_id")
        if actual_resume_id != expected_resume_id:
            raise RuntimeError("resume identifier changed after batch preflight")
        grade = score.get("grade", {})
        return {
            "file": str(path),
            "resume_id": expected_resume_id,
            "status": "success",
            "total_score": score.get("total_score", 1.0),
            "grade": grade.get("grade", "F"),
            "output_files": output_files,
        }

    def _summary(self, results: List[Dict[str, Any]]) -> Dict[str, Any]:
        successful = [item for item in results if item["status"] == "success"]
        failed = len(results) - len(successful)
        scores = [float(item["total_score"]) for item in successful]
        grade_distribution: Dict[str, int] = {}
        for item in successful:
            grade = str(item["grade"])
            grade_distribution[grade] = grade_distribution.get(grade, 0) + 1
        generated_at = self.clock().astimezone(timezone.utc).replace(microsecond=0).isoformat()
        return {
            "generated_at": generated_at.replace("+00:00", "Z"),
            "total": len(results),
            "successful": len(successful),
            "failed": failed,
            "success_rate": round(len(successful) / len(results), 4) if results else 0.0,
            "average_score": round(sum(scores) / len(scores), 1) if scores else 0.0,
            "grade_distribution": dict(sorted(grade_distribution.items())),
            "results": results,
        }
