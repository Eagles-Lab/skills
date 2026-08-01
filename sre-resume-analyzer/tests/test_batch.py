import json
import shutil
from datetime import datetime, timezone
from pathlib import Path

import pytest

from sre_resume_analyzer.analyzer import ResumeAnalyzer
from sre_resume_analyzer.batch import BatchPreflightError, BatchProcessor

FIXTURES = Path(__file__).parent / "fixtures"
FIXED_TIME = datetime(2026, 8, 2, tzinfo=timezone.utc)


class FakeCalculator:
    def calculate(self, resume):
        return json.loads((FIXTURES / "runtime_score.json").read_text(encoding="utf-8"))


def _factory(instances):
    def create(root):
        analyzer = ResumeAnalyzer(root, calculator=FakeCalculator(), clock=lambda: FIXED_TIME)
        instances.append(analyzer)
        return analyzer

    return create


def test_batch_is_sorted_partial_and_uses_isolated_analyzers(tmp_path):
    source = tmp_path / "input"
    source.mkdir()
    shutil.copy(FIXTURES / "runtime_complete.json", source / "b.json")
    shutil.copy(FIXTURES / "runtime_minimal.json", source / "a.json")
    (source / "c.json").write_text("{}", encoding="utf-8")
    instances = []
    processor = BatchProcessor(
        tmp_path / "out",
        max_workers=3,
        analyzer_factory=_factory(instances),
        clock=lambda: FIXED_TIME,
    )

    summary = processor.process_directory(source)

    assert summary["total"] == 3
    assert summary["successful"] == 2
    assert summary["failed"] == 1
    assert [item["file"] for item in summary["results"]] == sorted(
        item["file"] for item in summary["results"]
    )
    assert len(instances) == 2
    assert len({id(instance) for instance in instances}) == 2


def test_reusing_processor_does_not_accumulate_state(tmp_path):
    source = tmp_path / "input"
    source.mkdir()
    shutil.copy(FIXTURES / "runtime_minimal.json", source / "a.json")
    processor = BatchProcessor(
        tmp_path / "out",
        overwrite=True,
        analyzer_factory=_factory([]),
        clock=lambda: FIXED_TIME,
    )

    first = processor.process_directory(source)
    second = processor.process_directory(source)

    assert first["total"] == second["total"] == 1
    assert first["results"] == second["results"]


def test_duplicate_ids_abort_before_workers_start(tmp_path):
    source = tmp_path / "input"
    source.mkdir()
    data = json.loads((FIXTURES / "runtime_complete.json").read_text(encoding="utf-8"))
    (source / "a.json").write_text(json.dumps(data), encoding="utf-8")
    data["basic_info"]["name"] = "different"
    (source / "b.json").write_text(json.dumps(data), encoding="utf-8")
    instances = []
    processor = BatchProcessor(
        tmp_path / "out", analyzer_factory=_factory(instances), clock=lambda: FIXED_TIME
    )

    with pytest.raises(BatchPreflightError, match="duplicate"):
        processor.process_directory(source)
    assert instances == []
    assert not (tmp_path / "out" / "batch_summary.json").exists()


def test_parallelism_must_be_positive(tmp_path):
    with pytest.raises(ValueError, match="at least 1"):
        BatchProcessor(tmp_path, max_workers=0)
