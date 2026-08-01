import json
import stat
from pathlib import Path

import pytest

from sre_resume_analyzer import output
from sre_resume_analyzer.errors import OutputConflictError, OutputSafetyError


def _payload(marker="one"):
    return {
        "extracted": {"marker": marker},
        "score": {"marker": marker},
        "analysis": {"marker": marker},
        "suggestions": marker,
        "interview_questions": marker,
    }


def test_bundle_is_exact_private_and_conflict_safe(tmp_path):
    paths = output.write_output_bundle(tmp_path, "safe_id", **_payload())
    bundle = tmp_path / "safe_id"

    assert sorted(path.name for path in bundle.iterdir()) == sorted(output.OUTPUT_FILENAMES)
    assert set(paths) == {"extracted", "score", "analysis", "suggestions", "interview_questions"}
    assert stat.S_IMODE(bundle.stat().st_mode) == 0o700
    assert all(stat.S_IMODE(path.stat().st_mode) == 0o600 for path in bundle.iterdir())
    with pytest.raises(OutputConflictError):
        output.write_output_bundle(tmp_path, "safe_id", **_payload())


def test_overwrite_replaces_every_artifact(tmp_path):
    output.write_output_bundle(tmp_path, "safe_id", **_payload("old"))
    output.write_output_bundle(tmp_path, "safe_id", overwrite=True, **_payload("new"))

    assert json.loads((tmp_path / "safe_id" / "score.json").read_text())["marker"] == "new"
    assert (tmp_path / "safe_id" / "suggestions.md").read_text().strip() == "new"


@pytest.mark.parametrize("resume_id", ["../escape", "/tmp/escape", "bad/name", "bad\nname", ""])
def test_resume_id_cannot_escape(tmp_path, resume_id):
    with pytest.raises(OutputSafetyError):
        output.write_output_bundle(tmp_path, resume_id, **_payload())


@pytest.mark.parametrize("fail_on", range(1, len(output.OUTPUT_FILENAMES) + 1))
def test_write_failure_leaves_no_visible_partial_bundle(tmp_path, monkeypatch, fail_on):
    original = output._write_private
    calls = 0

    def fail_second(path, content):
        nonlocal calls
        calls += 1
        if calls == fail_on:
            raise OSError("synthetic failure")
        original(path, content)

    monkeypatch.setattr(output, "_write_private", fail_second)
    with pytest.raises(OutputSafetyError):
        output.write_output_bundle(tmp_path, "safe_id", **_payload())

    assert not (tmp_path / "safe_id").exists()
    assert not list(tmp_path.glob(".tmp-*"))


def test_output_symlink_is_rejected(tmp_path):
    real = tmp_path / "real"
    real.mkdir()
    (tmp_path / "safe_id").symlink_to(real, target_is_directory=True)
    with pytest.raises(OutputSafetyError):
        output.write_output_bundle(tmp_path, "safe_id", overwrite=True, **_payload())


def test_identifier_fallback_hash_and_invalid_root(tmp_path):
    generated = output.derive_resume_id("测试", "not-a-valid-digest")
    assert generated.startswith("resume-")
    assert len(generated.rsplit("-", 1)[1]) == 8

    root_file = tmp_path / "file"
    root_file.write_text("not a directory")
    with pytest.raises(OutputSafetyError, match="output root"):
        output.write_output_bundle(root_file, "safe_id", **_payload())


def test_containment_check_fails_closed(tmp_path, monkeypatch):
    original = output.Path.relative_to

    def synthetic_escape(path, other):
        if path.name == "safe_id":
            raise ValueError("synthetic escape")
        return original(path, other)

    monkeypatch.setattr(output.Path, "relative_to", synthetic_escape)
    with pytest.raises(OutputSafetyError, match="escapes"):
        output.resolve_bundle_path(tmp_path, "safe_id")


def test_target_file_and_contract_mismatch_are_rejected(tmp_path, monkeypatch):
    (tmp_path / "safe_id").write_text("file")
    with pytest.raises(OutputSafetyError, match="not a directory"):
        output.write_output_bundle(tmp_path, "safe_id", overwrite=True, **_payload())

    monkeypatch.setattr(output, "OUTPUT_FILENAMES", ("unexpected",))
    with pytest.raises(OutputSafetyError, match="exactly five"):
        output._bundle_payloads(**_payload())


def test_private_writer_closes_descriptor_on_failure(tmp_path, monkeypatch):
    path = tmp_path / "private"

    def fail_fdopen(*args, **kwargs):
        raise RuntimeError("synthetic fdopen failure")

    monkeypatch.setattr(output.os, "fdopen", fail_fdopen)
    with pytest.raises(RuntimeError, match="synthetic"):
        output._write_private(path, "value")
    path.unlink()


def test_overwrite_commit_failure_restores_old_bundle(tmp_path, monkeypatch):
    output.write_output_bundle(tmp_path, "safe_id", **_payload("old"))
    original = output.os.replace
    calls = 0

    def fail_new_commit(source, destination):
        nonlocal calls
        calls += 1
        if calls == 2:
            raise OSError("synthetic commit failure")
        return original(source, destination)

    monkeypatch.setattr(output.os, "replace", fail_new_commit)
    with pytest.raises(OutputSafetyError, match="failed to commit"):
        output.write_output_bundle(tmp_path, "safe_id", overwrite=True, **_payload("new"))

    assert json.loads((tmp_path / "safe_id" / "score.json").read_text())["marker"] == "old"
    assert not list(tmp_path.glob(".backup-*"))


def test_output_safety_error_during_write_cleans_temporary(tmp_path, monkeypatch):
    def fail_write(*args, **kwargs):
        raise OutputSafetyError("synthetic safety error")

    monkeypatch.setattr(output, "_write_private", fail_write)
    with pytest.raises(OutputSafetyError, match="synthetic"):
        output.write_output_bundle(tmp_path, "safe_id", **_payload())
    assert not list(tmp_path.glob(".tmp-*"))


def test_atomic_json_validates_parent_symlink_conflict_and_failure(tmp_path, monkeypatch):
    parent_file = tmp_path / "parent-file"
    parent_file.write_text("file")
    with pytest.raises(OutputSafetyError, match="JSON output parent"):
        output.write_json_atomically(parent_file / "x.json", {}, overwrite=False)

    destination = tmp_path / "value.json"
    output.write_json_atomically(destination, {"old": True}, overwrite=False)
    with pytest.raises(OutputConflictError):
        output.write_json_atomically(destination, {}, overwrite=False)

    link = tmp_path / "link.json"
    link.symlink_to(destination)
    with pytest.raises(OutputSafetyError, match="symlink"):
        output.write_json_atomically(link, {}, overwrite=True)

    original = output.os.replace

    def fail_replace(source, target):
        if Path(target).name == "failed.json":
            raise OSError("synthetic")
        return original(source, target)

    monkeypatch.setattr(output.os, "replace", fail_replace)
    with pytest.raises(OutputSafetyError, match="failed to write JSON"):
        output.write_json_atomically(tmp_path / "failed.json", {}, overwrite=False)
    assert not list(tmp_path.glob(".failed.json.*"))


def test_atomic_text_validates_parent_symlink_conflict_and_failure(tmp_path, monkeypatch):
    parent_file = tmp_path / "parent-file"
    parent_file.write_text("file")
    with pytest.raises(OutputSafetyError, match="text output parent"):
        output.write_text_atomically(parent_file / "x.md", "x", overwrite=False)

    destination = tmp_path / "value.md"
    output.write_text_atomically(destination, "old", overwrite=False)
    with pytest.raises(OutputConflictError):
        output.write_text_atomically(destination, "new", overwrite=False)

    link = tmp_path / "link.md"
    link.symlink_to(destination)
    with pytest.raises(OutputSafetyError, match="symlink"):
        output.write_text_atomically(link, "new", overwrite=True)

    monkeypatch.setattr(output.os, "replace", lambda *_: (_ for _ in ()).throw(OSError("x")))
    with pytest.raises(OutputSafetyError, match="failed to write text"):
        output.write_text_atomically(tmp_path / "failed.md", "x", overwrite=False)
    assert not list(tmp_path.glob(".failed.md.*"))


def test_private_directory_bundle_commits_and_overwrites_as_one_unit(tmp_path):
    destination = tmp_path / "calibration"
    paths = output.write_private_directory_bundle(
        destination,
        {"calibration_report.json": '{"old": true}', "calibration_report.md": "old"},
        overwrite=False,
    )
    assert set(paths) == {"calibration_report.json", "calibration_report.md"}
    assert destination.stat().st_mode & 0o777 == 0o700
    assert all(path.stat().st_mode & 0o777 == 0o600 for path in paths.values())
    with pytest.raises(OutputConflictError):
        output.write_private_directory_bundle(destination, {"new.txt": "new"}, overwrite=False)

    output.write_private_directory_bundle(
        destination,
        {"calibration_report.json": '{"new": true}', "calibration_report.md": "new"},
        overwrite=True,
    )
    assert sorted(path.name for path in destination.iterdir()) == [
        "calibration_report.json",
        "calibration_report.md",
    ]
    assert "new" in (destination / "calibration_report.json").read_text()


def test_private_directory_bundle_restores_old_directory_on_commit_failure(tmp_path, monkeypatch):
    destination = tmp_path / "calibration"
    output.write_private_directory_bundle(destination, {"report.txt": "old"}, overwrite=False)
    original = output.os.replace

    def fail_new_commit(source, target):
        if Path(source).name.startswith(".tmp-") and Path(target) == destination:
            raise OSError("synthetic commit failure")
        return original(source, target)

    monkeypatch.setattr(output.os, "replace", fail_new_commit)
    with pytest.raises(OutputSafetyError, match="failed to commit"):
        output.write_private_directory_bundle(destination, {"report.txt": "new"}, overwrite=True)
    assert (destination / "report.txt").read_text() == "old\n"
    assert not list(tmp_path.glob(".tmp-*"))
    assert not list(tmp_path.glob(".backup-*"))


def test_private_directory_bundle_rejects_unsafe_destinations(tmp_path):
    parent_file = tmp_path / "parent-file"
    parent_file.write_text("file")
    with pytest.raises(OutputSafetyError, match="bundle output parent"):
        output.write_private_directory_bundle(
            parent_file / "bundle", {"report.txt": "x"}, overwrite=False
        )

    real = tmp_path / "real"
    real.mkdir()
    link = tmp_path / "link"
    link.symlink_to(real, target_is_directory=True)
    with pytest.raises(OutputSafetyError, match="symlink"):
        output.write_private_directory_bundle(link, {"report.txt": "x"}, overwrite=True)

    with pytest.raises(OutputSafetyError, match="at least one"):
        output.write_private_directory_bundle(tmp_path / "empty", {}, overwrite=False)
    with pytest.raises(OutputSafetyError, match="unsafe output bundle filename"):
        output.write_private_directory_bundle(
            tmp_path / "unsafe", {"../report.txt": "x"}, overwrite=False
        )
