"""Determinism and concurrency gates that exercise production-sized batches."""

import json
from datetime import UTC, datetime
from pathlib import Path

from sre_resume_analyzer.analyzer import ResumeAnalyzer
from sre_resume_analyzer.batch import BatchProcessor
from sre_resume_analyzer.output import OUTPUT_FILENAMES

FIXTURES = Path(__file__).parent / "fixtures"
FIXED_TIME = datetime(2026, 8, 2, tzinfo=UTC)


def _fixed_analyzer(root):
    return ResumeAnalyzer(root, clock=lambda: FIXED_TIME)


def test_same_input_is_semantically_identical_across_100_overwrites(tmp_path):
    analyzer = _fixed_analyzer(tmp_path / "out")
    paths = analyzer.analyze(FIXTURES / "runtime_complete.json")
    expected = {name: Path(path).read_bytes() for name, path in paths.items()}

    for _ in range(99):
        paths = analyzer.analyze(FIXTURES / "runtime_complete.json", overwrite=True)
        assert {name: Path(path).read_bytes() for name, path in paths.items()} == expected

    assert not list((tmp_path / "out").glob(".tmp-*"))
    assert not list((tmp_path / "out").glob(".backup-*"))


def test_100_inputs_match_at_parallelism_1_3_and_16(tmp_path):
    source = tmp_path / "inputs"
    source.mkdir()
    fixture = json.loads((FIXTURES / "runtime_complete.json").read_text(encoding="utf-8"))
    resume_ids = []
    for index in range(100):
        resume_id = f"candidate_{index:03d}"
        resume_ids.append(resume_id)
        value = json.loads(json.dumps(fixture))
        value["resume_id"] = resume_id
        (source / f"resume-{index:03d}.json").write_text(
            json.dumps(value, ensure_ascii=False),
            encoding="utf-8",
        )

    summaries = {}
    roots = {}
    for workers in (1, 3, 16):
        output_root = tmp_path / f"out-{workers}"
        roots[workers] = output_root
        summaries[workers] = BatchProcessor(
            output_root,
            max_workers=workers,
            analyzer_factory=_fixed_analyzer,
            clock=lambda: FIXED_TIME,
        ).process_directory(source)
        assert summaries[workers]["successful"] == 100
        assert summaries[workers]["failed"] == 0
        assert not list(output_root.glob(".tmp-*"))
        assert not list(output_root.glob(".backup-*"))

    normalized = {
        workers: [
            (item["resume_id"], item["status"], item["total_score"], item["grade"])
            for item in summary["results"]
        ]
        for workers, summary in summaries.items()
    }
    assert normalized[1] == normalized[3] == normalized[16]

    for resume_id in resume_ids:
        for filename in OUTPUT_FILENAMES:
            expected = (roots[1] / resume_id / filename).read_bytes()
            assert (roots[3] / resume_id / filename).read_bytes() == expected
            assert (roots[16] / resume_id / filename).read_bytes() == expected
