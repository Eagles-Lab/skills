from __future__ import annotations

import json
from pathlib import Path

import pytest

from sre_resume_analyzer.cli import analyze_main, batch_main, extract_main
from sre_resume_analyzer.errors import ExitCode


def write_json(path: Path, value: object) -> Path:
    path.write_text(json.dumps(value, ensure_ascii=False), encoding="utf-8")
    return path


def test_analyze_cli_success_stdout_has_root_and_count_but_no_name(tmp_path: Path, capsys):
    source = write_json(tmp_path / "resume.json", {"basic_info": {"name": "秘密姓名"}})
    output = tmp_path / "run"
    code = analyze_main(["--extracted", str(source), "--output-dir", str(output)])
    captured = capsys.readouterr()
    assert code == ExitCode.SUCCESS
    payload = json.loads(captured.out)
    assert payload == {"status": "success", "output_dir": str(output), "successful": 1}
    assert "秘密姓名" not in captured.out + captured.err


def test_schema_error_exit_two_and_no_output(tmp_path: Path, capsys):
    source = write_json(tmp_path / "bad.json", {"position": "SRE"})
    output = tmp_path / "run"
    assert analyze_main(["--extracted", str(source), "--output-dir", str(output)]) == 2
    assert "input error" in capsys.readouterr().err
    assert not output.exists()


def test_output_conflict_exit_five(tmp_path: Path, capsys):
    source = write_json(tmp_path / "resume.json", {})
    output = tmp_path / "run"
    assert analyze_main(["--extracted", str(source), "--output-dir", str(output)]) == 0
    assert analyze_main(["--extracted", str(source), "--output-dir", str(output)]) == 5
    assert "output error" in capsys.readouterr().err


def test_overwrite_replaces_complete_run(tmp_path: Path):
    source = write_json(tmp_path / "resume.json", {})
    output = tmp_path / "run"
    assert analyze_main(["--extracted", str(source), "--output-dir", str(output)]) == 0
    (output / "stale").write_text("stale")
    assert (
        analyze_main(["--extracted", str(source), "--output-dir", str(output), "--overwrite"]) == 0
    )
    assert not (output / "stale").exists()


def test_batch_partial_exit_three_and_privacy_safe_stdout(tmp_path: Path, capsys):
    inputs = tmp_path / "inputs"
    inputs.mkdir()
    write_json(inputs / "good.json", {"basic_info": {"name": "秘密姓名"}})
    write_json(inputs / "bad.json", {"skills": ["Python"]})
    output = tmp_path / "run"
    code = batch_main(["--input-dir", str(inputs), "--output-dir", str(output), "--parallel", "3"])
    captured = capsys.readouterr()
    assert code == ExitCode.PARTIAL_BATCH_FAILURE
    payload = json.loads(captured.out)
    assert payload["successful"] == 1
    assert payload["failed"] == 1
    assert payload["output_dir"] == str(output)
    assert "秘密姓名" not in captured.out + captured.err


def test_batch_empty_directory_is_successful_empty_run(tmp_path: Path):
    inputs = tmp_path / "inputs"
    inputs.mkdir()
    output = tmp_path / "run"
    assert batch_main(["--input-dir", str(inputs), "--output-dir", str(output)]) == 0
    assert json.loads((output / "batch_summary.json").read_text())["total"] == 0


def test_pdf_extract_error_exit_four_without_raw_output(tmp_path: Path, capsys):
    source = tmp_path / "broken.pdf"
    source.write_bytes(b"not a pdf")
    output = tmp_path / "raw_extraction.json"
    assert extract_main([str(source), "--output", str(output)]) == 4
    assert "PDF extraction error" in capsys.readouterr().err
    assert not output.exists()


@pytest.mark.parametrize("main", [analyze_main, batch_main, extract_main])
def test_help_exits_success(main):
    with pytest.raises(SystemExit) as error:
        main(["--help"])
    assert error.value.code == 0
