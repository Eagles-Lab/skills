from __future__ import annotations

# ruff: noqa: RUF001
import json
from datetime import UTC, datetime
from pathlib import Path

from sre_resume_analyzer.analyzer import ResumeAnalyzer
from sre_resume_analyzer.batch import BatchProcessor

FIXED = datetime(2026, 8, 2, tzinfo=UTC)


def write(path: Path, value: object) -> None:
    path.write_text(json.dumps(value, ensure_ascii=False), encoding="utf-8")


def test_same_input_builds_semantically_identical_artifacts_100_times(tmp_path: Path):
    source = tmp_path / "resume.json"
    write(
        source,
        {
            "basic_info": {"name": "稳定性测试"},
            "projects": [{"description": "实现并部署 Python Kubernetes 自动化工具"}],
        },
    )
    analyzer = ResumeAnalyzer(tmp_path / "unused", clock=lambda: FIXED)
    first = analyzer.build_artifacts(source).output_payload()
    for _ in range(99):
        assert analyzer.build_artifacts(source).output_payload() == first


def test_one_hundred_parallel_inputs_have_unique_isolated_outputs(tmp_path: Path):
    inputs = tmp_path / "inputs"
    inputs.mkdir()
    for index in range(100):
        write(
            inputs / f"resume-{index:03}.json",
            {
                "basic_info": {"name": "同名候选人"},
                "projects": [{"description": f"实现 Python 工具并测试验证，编号 {index}"}],
            },
        )
    output = tmp_path / "run"
    summary = BatchProcessor(
        output,
        max_workers=16,
        clock=lambda: FIXED,
        analyzer_factory=lambda root: ResumeAnalyzer(root, clock=lambda: FIXED),
    ).process_directory(inputs)
    assert summary["successful"] == 100
    analysis_dirs = list((output / "resume_analysis").iterdir())
    interview_files = list((output / "interview_questions").iterdir())
    assert len(analysis_dirs) == len({path.name for path in analysis_dirs}) == 100
    assert len(interview_files) == len({path.name for path in interview_files}) == 100
    assert all(len(list(path.iterdir())) == 4 for path in analysis_dirs)
