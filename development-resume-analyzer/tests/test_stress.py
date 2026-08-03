from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path

from development_resume_analyzer.analyzer import DevelopmentResumeAnalyzer, load_resume
from development_resume_analyzer.batch import BatchProcessor
from development_resume_analyzer.output import sha256_file

FIXTURES = Path(__file__).parent / "fixtures"
FIXED = datetime(2026, 8, 2, tzinfo=UTC)


def test_one_hundred_artifact_builds_are_semantically_identical(tmp_path: Path) -> None:
    source = FIXTURES / "complete.json"
    resume = load_resume(source)
    digest = sha256_file(source)
    analyzer = DevelopmentResumeAnalyzer(tmp_path / "unused", clock=lambda: FIXED)
    baseline = analyzer.build_artifacts(resume, (digest,), seed="stable")
    expected = {
        "score": baseline.score,
        "analysis": baseline.analysis,
        "suggestions": baseline.suggestions,
        "interview_questions": baseline.interview_questions,
    }
    for _ in range(99):
        actual = analyzer.build_artifacts(resume, (digest,), seed="stable")
        assert {
            "score": actual.score,
            "analysis": actual.analysis,
            "suggestions": actual.suggestions,
            "interview_questions": actual.interview_questions,
        } == expected


def test_batch_processor_reuse_has_no_historical_state(tmp_path: Path) -> None:
    inputs = tmp_path / "inputs"
    inputs.mkdir()
    (inputs / "one.json").write_text(json.dumps({"basic_info": {"name": "同学"}}))
    output = tmp_path / "run"
    processor = BatchProcessor(output, overwrite=True, clock=lambda: FIXED)
    first = processor.process_directory(inputs)
    second = processor.process_directory(inputs)
    assert first == second
    assert second["raw_file_count"] == 1
    assert second["unique_candidate_count"] == 1
