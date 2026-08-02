from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path

import pytest

from sre_resume_analyzer.analyzer import ResumeAnalyzer
from sre_resume_analyzer.batch import BatchPreflightError, BatchProcessor
from sre_resume_analyzer.errors import OutputConflictError

FIXED = datetime(2026, 8, 2, tzinfo=UTC)


def write(path: Path, value: object) -> None:
    path.write_text(json.dumps(value, ensure_ascii=False), encoding="utf-8")


def processor(output: Path, workers: int = 3, overwrite: bool = False) -> BatchProcessor:
    return BatchProcessor(
        output,
        max_workers=workers,
        overwrite=overwrite,
        clock=lambda: FIXED,
        analyzer_factory=lambda root: ResumeAnalyzer(root, clock=lambda: FIXED),
    )


def test_partial_batch_atomically_publishes_successes_and_redacted_failure(tmp_path: Path):
    inputs = tmp_path / "inputs"
    inputs.mkdir()
    write(inputs / "candidate-a.json", {"basic_info": {"name": "张三"}})
    write(inputs / "candidate-secret-name.json", {"skills": ["Python"]})
    output = tmp_path / "run"
    summary = processor(output).process_directory(inputs)
    assert summary["total"] == 2
    assert summary["successful"] == 1
    assert summary["failed"] == 1
    failed = next(item for item in summary["results"] if item["status"] == "failed")
    assert set(failed) == {"input_sha256", "status", "error_category"}
    assert "candidate-secret-name" not in json.dumps(summary)
    assert (output / "batch_summary.json").is_file()
    assert len(list((output / "resume_analysis").iterdir())) == 1
    assert len(list((output / "interview_questions").iterdir())) == 1


def test_duplicate_content_fails_before_workers_and_writes_nothing(tmp_path: Path):
    inputs = tmp_path / "inputs"
    inputs.mkdir()
    content = {"basic_info": {"name": "张三"}}
    write(inputs / "a.json", content)
    write(inputs / "b.json", content)
    output = tmp_path / "run"
    with pytest.raises(BatchPreflightError, match="duplicate input"):
        processor(output).process_directory(inputs)
    assert not output.exists()


def test_existing_run_conflicts_before_analysis(tmp_path: Path):
    inputs = tmp_path / "inputs"
    inputs.mkdir()
    write(inputs / "a.json", {})
    output = tmp_path / "run"
    processor(output).process_directory(inputs)
    with pytest.raises(OutputConflictError):
        processor(output).process_directory(inputs)


def test_same_processor_instance_does_not_accumulate_results(tmp_path: Path):
    inputs = tmp_path / "inputs"
    inputs.mkdir()
    write(inputs / "a.json", {})
    instance = processor(tmp_path / "run", overwrite=True)
    first = instance.process_directory(inputs)
    first_result_count = len(first["results"])
    write(inputs / "b.json", {"basic_info": {"name": "李四"}})
    second = instance.process_directory(inputs)
    assert first_result_count == 1
    assert second["total"] == 2
    assert len(second["results"]) == 2


def normalized_files(root: Path) -> dict[str, object]:
    values: dict[str, object] = {}
    for path in sorted(root.rglob("*")):
        if not path.is_file():
            continue
        relative = path.relative_to(root).as_posix()
        if path.suffix == ".json":
            value = json.loads(path.read_text())
            if isinstance(value, dict):
                value.pop("generated_at", None)
            values[relative] = value
        else:
            values[relative] = path.read_text().replace("2026-08-02T00:00:00Z", "TIME")
    return values


def test_parallelism_one_three_sixteen_produces_same_results(tmp_path: Path):
    inputs = tmp_path / "inputs"
    inputs.mkdir()
    for index in range(12):
        write(
            inputs / f"{index:02}.json",
            {
                "basic_info": {"name": f"候选人{index}"},
                "projects": [{"description": f"实现 Python 自动化工具 {index}"}],
            },
        )
    outputs = []
    for workers in (1, 3, 16):
        root = tmp_path / f"run-{workers}"
        processor(root, workers=workers).process_directory(inputs)
        outputs.append(normalized_files(root))
    assert outputs[0] == outputs[1] == outputs[2]


def test_invalid_worker_count():
    with pytest.raises(ValueError):
        BatchProcessor(Path("unused"), max_workers=0)
