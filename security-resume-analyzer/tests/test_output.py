from __future__ import annotations

import json
import os
from pathlib import Path

import pytest

from security_resume_analyzer import output
from security_resume_analyzer.errors import OutputConflictError, OutputSafetyError


def candidate(name: str = "张三-a1b2c3d4", marker: str = "old") -> dict[str, object]:
    return {
        "output_name": name,
        "extracted": {"marker": marker},
        "score": {"marker": marker},
        "analysis": {"marker": marker},
        "suggestions": f"suggestion {marker}",
        "interview_questions": f"question {marker}",
    }


@pytest.mark.parametrize(
    "name,expected",
    [
        ("张 三", "张-三-abcdef12"),
        (None, "未知姓名-abcdef12"),
        ("../王/五", "王-五-abcdef12"),
        ("CON", "未知姓名-abcdef12"),
        ("Ａ：Ｂ\x00", "A-B-abcdef12"),
    ],
)
def test_output_name_is_unicode_preserving_and_safe(name, expected):
    assert output.derive_output_name(name, "abcdef12" + "0" * 56) == expected


def test_run_layout_permissions_and_content(tmp_path: Path):
    target = tmp_path / "run"
    paths = output.write_run_output(target, [candidate()], batch_summary={"successful": 1})
    assert set(paths["张三-a1b2c3d4"]) == {
        "extracted",
        "score",
        "analysis",
        "suggestions",
        "interview_questions",
    }
    assert json.loads((target / "batch_summary.json").read_text())["successful"] == 1
    assert sorted(
        path.name for path in (target / "resume_analysis" / "张三-a1b2c3d4").iterdir()
    ) == [
        "analysis.json",
        "extracted.json",
        "score.json",
        "suggestions.md",
    ]
    assert (target / "interview_questions" / "张三-a1b2c3d4.md").is_file()
    assert (target.stat().st_mode & 0o777) == 0o700
    for path in target.rglob("*"):
        expected = 0o700 if path.is_dir() else 0o600
        assert (path.stat().st_mode & 0o777) == expected


def test_existing_target_requires_overwrite_and_overwrite_replaces_whole_run(tmp_path: Path):
    target = tmp_path / "run"
    output.write_run_output(target, [candidate(marker="old")])
    with pytest.raises(OutputConflictError):
        output.write_run_output(target, [candidate(marker="new")])
    stale = target / "stale.txt"
    stale.write_text("stale")
    output.write_run_output(target, [candidate(marker="new")], overwrite=True)
    assert not stale.exists()
    assert (
        json.loads(next(target.glob("resume_analysis/*/score.json")).read_text())["marker"] == "new"
    )


def test_write_failure_never_reveals_partial_target(tmp_path: Path, monkeypatch):
    target = tmp_path / "run"
    original = output._write_private
    calls = 0

    def fail(path: Path, content: str) -> None:
        nonlocal calls
        calls += 1
        if calls == 3:
            raise OSError("fault")
        original(path, content)

    monkeypatch.setattr(output, "_write_private", fail)
    with pytest.raises(OutputSafetyError):
        output.write_run_output(target, [candidate()])
    assert not target.exists()
    assert not list(tmp_path.glob(".tmp-*"))


def test_overwrite_publish_failure_restores_old_run(tmp_path: Path, monkeypatch):
    target = tmp_path / "run"
    output.write_run_output(target, [candidate(marker="old")])
    original_replace = os.replace

    def fail_publish(source, destination):
        if Path(destination) == target and Path(source).name.startswith(".tmp-"):
            raise OSError("publish fault")
        original_replace(source, destination)

    monkeypatch.setattr(output.os, "replace", fail_publish)
    with pytest.raises(OutputSafetyError):
        output.write_run_output(target, [candidate(marker="new")], overwrite=True)
    assert (
        json.loads(next(target.glob("resume_analysis/*/score.json")).read_text())["marker"] == "old"
    )


@pytest.mark.parametrize("name", ["../x", "/tmp/x", "a/b", "a\\b", "a\x00b", ".."])
def test_unsafe_supplied_output_name_fails_closed(tmp_path: Path, name: str):
    with pytest.raises(OutputSafetyError):
        output.write_run_output(tmp_path / "run", [candidate(name=name)])
    assert not (tmp_path / "run").exists()


def test_symlink_target_and_duplicate_names_fail_closed(tmp_path: Path):
    real = tmp_path / "real"
    real.mkdir()
    link = tmp_path / "run"
    link.symlink_to(real, target_is_directory=True)
    with pytest.raises(OutputSafetyError):
        output.write_run_output(link, [candidate()])
    with pytest.raises(OutputSafetyError):
        output.write_run_output(tmp_path / "other", [candidate(), candidate()])


def test_private_directory_and_standalone_helpers(tmp_path: Path):
    files = output.write_private_directory_bundle(
        tmp_path / "calibration", {"report.md": "ok"}, overwrite=False
    )
    assert files["report.md"].read_text() == "ok\n"
    path = output.write_json_atomically(tmp_path / "one.json", {"b": 2, "a": 1}, overwrite=False)
    assert json.loads(path.read_text()) == {"a": 1, "b": 2}


def test_identifier_digest_and_target_validation_edges(tmp_path: Path):
    with pytest.raises(OutputSafetyError):
        output.validate_resume_id("../unsafe")
    fallback = output.derive_resume_id(None, "not-a-sha")
    assert fallback.startswith("resume-") and len(fallback) == 15
    parent_file = tmp_path / "parent-file"
    parent_file.write_text("x")
    with pytest.raises(OutputSafetyError):
        output.write_run_output(parent_file / "run", [candidate()])
    target_file = tmp_path / "target-file"
    target_file.write_text("x")
    with pytest.raises(OutputSafetyError):
        output.write_run_output(target_file, [candidate()], overwrite=True)


def test_private_bundle_validation_conflict_overwrite_and_rollback(tmp_path: Path, monkeypatch):
    target = tmp_path / "bundle"
    with pytest.raises(OutputSafetyError):
        output.write_private_directory_bundle(target, {}, overwrite=False)
    with pytest.raises(OutputSafetyError):
        output.write_private_directory_bundle(target, {"../bad": "x"}, overwrite=False)
    output.write_private_directory_bundle(target, {"report.md": "old"}, overwrite=False)
    with pytest.raises(OutputConflictError):
        output.write_private_directory_bundle(target, {"report.md": "new"}, overwrite=False)
    output.write_private_directory_bundle(target, {"report.md": "new"}, overwrite=True)
    assert (target / "report.md").read_text() == "new\n"

    original_replace = os.replace

    def fail_publish(source, destination):
        if Path(destination) == target and Path(source).name.startswith(".tmp-"):
            raise OSError("fault")
        original_replace(source, destination)

    monkeypatch.setattr(output.os, "replace", fail_publish)
    with pytest.raises(OutputSafetyError):
        output.write_private_directory_bundle(target, {"report.md": "bad"}, overwrite=True)
    assert (target / "report.md").read_text() == "new\n"


def test_standalone_text_safety_conflict_overwrite_and_failure(tmp_path: Path, monkeypatch):
    parent_file = tmp_path / "parent"
    parent_file.write_text("x")
    with pytest.raises(OutputSafetyError):
        output.write_text_atomically(parent_file / "x", "x", overwrite=False)
    real = tmp_path / "real"
    real.write_text("real")
    link = tmp_path / "link"
    link.symlink_to(real)
    with pytest.raises(OutputSafetyError):
        output.write_text_atomically(link, "x", overwrite=True)
    target = tmp_path / "text"
    output.write_text_atomically(target, "old", overwrite=False)
    with pytest.raises(OutputConflictError):
        output.write_text_atomically(target, "new", overwrite=False)
    output.write_text_atomically(target, "new", overwrite=True)
    assert target.read_text() == "new\n"

    monkeypatch.setattr(output.os, "replace", lambda *_args: (_ for _ in ()).throw(OSError()))
    with pytest.raises(OutputSafetyError):
        output.write_text_atomically(tmp_path / "failed", "x", overwrite=False)
    assert not (tmp_path / "failed").exists()


def test_low_level_private_write_cleanup_on_stream_failure(tmp_path: Path, monkeypatch):
    class BrokenStream:
        def __enter__(self):
            return self

        def __exit__(self, *_args):
            return False

        def write(self, _content):
            raise OSError("write fault")

    monkeypatch.setattr(output.os, "fdopen", lambda *_args, **_kwargs: BrokenStream())
    with pytest.raises(OSError):
        output._write_private(tmp_path / "broken", "x")
