"""Safe, transactional output handling for complete analyzer runs."""

from __future__ import annotations

import hashlib
import json
import os
import re
import shutil
import tempfile
import unicodedata
import uuid
from contextlib import suppress
from pathlib import Path
from typing import Any, Iterable, Mapping

from .errors import OutputConflictError, OutputSafetyError

SAFE_RESUME_ID = re.compile(r"^[A-Za-z0-9_-]{1,64}$")
ANALYSIS_FILENAMES = (
    "extracted.json",
    "score.json",
    "analysis.json",
    "suggestions.md",
)
_WINDOWS_RESERVED = {
    "con",
    "prn",
    "aux",
    "nul",
    *(f"com{index}" for index in range(1, 10)),
    *(f"lpt{index}" for index in range(1, 10)),
}
_UNSAFE_NAME_CHARS = re.compile(r'[<>:"/\\|?*\x00-\x1f\x7f]')
_SEPARATORS = re.compile(r"[\s._-]+")


def sha256_file(path: Path) -> str:
    """Hash an input without retaining its sensitive contents in logs."""

    digest = hashlib.sha256()
    with Path(path).open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def validate_resume_id(resume_id: str) -> str:
    if not isinstance(resume_id, str) or not SAFE_RESUME_ID.fullmatch(resume_id):
        raise OutputSafetyError(
            "resume_id must match [A-Za-z0-9_-]{1,64}; paths and control characters are forbidden"
        )
    return resume_id


def _digest_prefix(input_sha256: str) -> str:
    digest = re.sub(r"[^a-fA-F0-9]", "", input_sha256)[:8].lower()
    return digest if len(digest) == 8 else hashlib.sha256(input_sha256.encode()).hexdigest()[:8]


def derive_resume_id(name: str | None, input_sha256: str) -> str:
    """Generate an internal stable identifier; it is never a visible path."""

    del name
    return validate_resume_id(f"resume-{_digest_prefix(input_sha256)}")


def sanitize_display_name(name: str | None) -> str:
    """Produce one Unicode-preserving cross-platform path component."""

    value = unicodedata.normalize("NFKC", name or "")
    value = "".join(char for char in value if unicodedata.category(char) != "Cf")
    value = _UNSAFE_NAME_CHARS.sub("-", value)
    value = _SEPARATORS.sub("-", value).strip(" .-")
    value = value.replace("..", "-")[:40].strip(" .-")
    if not value or value.casefold() in _WINDOWS_RESERVED:
        return "未知姓名"
    return value


def derive_output_name(name: str | None, input_sha256: str) -> str:
    return f"{sanitize_display_name(name)}-{_digest_prefix(input_sha256)}"


def validate_output_name(output_name: str) -> str:
    if (
        not isinstance(output_name, str)
        or not output_name
        or Path(output_name).name != output_name
        or output_name in {".", ".."}
        or _UNSAFE_NAME_CHARS.search(output_name)
        or output_name.casefold() in _WINDOWS_RESERVED
    ):
        raise OutputSafetyError("unsafe candidate output name")
    return output_name


def _stable_json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n"


def _write_private(path: Path, content: str) -> None:
    flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL
    descriptor = os.open(str(path), flags, 0o600)
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8", newline="\n") as handle:
            handle.write(content)
            handle.flush()
            os.fsync(handle.fileno())
    except Exception:
        with suppress(OSError):
            os.close(descriptor)
        raise


def _validate_run_target(output_root: Path, overwrite: bool) -> tuple[Path, Path]:
    destination = Path(output_root).expanduser()
    if not destination.name or destination.name in {".", ".."}:
        raise OutputSafetyError("output must name a dedicated run directory")
    parent = destination.parent
    if parent.exists() and (parent.is_symlink() or not parent.is_dir()):
        raise OutputSafetyError("output parent must be a real directory")
    parent.mkdir(parents=True, exist_ok=True)
    resolved_parent = parent.resolve(strict=True)
    destination = resolved_parent / destination.name
    if destination.is_symlink():
        raise OutputSafetyError("refusing to replace an output symlink")
    if destination.exists() and not overwrite:
        raise OutputConflictError(f"output run already exists: {destination}")
    if destination.exists() and not destination.is_dir():
        raise OutputSafetyError("output run target is not a directory")
    return destination, resolved_parent


def write_run_output(
    output_root: Path,
    candidates: Iterable[Mapping[str, Any]],
    *,
    batch_summary: Mapping[str, Any] | None = None,
    overwrite: bool = False,
) -> dict[str, dict[str, str]]:
    """Build and atomically publish one complete single or batch run."""

    destination, parent = _validate_run_target(output_root, overwrite)
    prepared = sorted(candidates, key=lambda item: str(item["output_name"]))
    names = [validate_output_name(str(item["output_name"])) for item in prepared]
    if len(names) != len(set(names)):
        raise OutputSafetyError("duplicate candidate output names")

    temporary = Path(tempfile.mkdtemp(prefix=f".tmp-{destination.name}-", dir=str(parent)))
    os.chmod(temporary, 0o700)
    backup: Path | None = None
    committed = False
    output_paths: dict[str, dict[str, str]] = {}
    try:
        analyses = temporary / "resume_analysis"
        interviews = temporary / "interview_questions"
        analyses.mkdir(mode=0o700)
        interviews.mkdir(mode=0o700)
        for item, output_name in zip(prepared, names, strict=True):
            candidate_dir = analyses / output_name
            candidate_dir.mkdir(mode=0o700)
            payloads = {
                "extracted.json": _stable_json(item["extracted"]),
                "score.json": _stable_json(item["score"]),
                "analysis.json": _stable_json(item["analysis"]),
                "suggestions.md": str(item["suggestions"]).rstrip() + "\n",
            }
            for filename in ANALYSIS_FILENAMES:
                _write_private(candidate_dir / filename, payloads[filename])
            interview_name = f"{output_name}.md"
            _write_private(
                interviews / interview_name,
                str(item["interview_questions"]).rstrip() + "\n",
            )
            final_candidate = destination / "resume_analysis" / output_name
            output_paths[output_name] = {
                "extracted": str(final_candidate / "extracted.json"),
                "score": str(final_candidate / "score.json"),
                "analysis": str(final_candidate / "analysis.json"),
                "suggestions": str(final_candidate / "suggestions.md"),
                "interview_questions": str(destination / "interview_questions" / interview_name),
            }
        if batch_summary is not None:
            _write_private(temporary / "batch_summary.json", _stable_json(batch_summary))

        if destination.exists():
            backup = parent / f".backup-{destination.name}-{uuid.uuid4().hex}"
            os.replace(destination, backup)
        try:
            os.replace(temporary, destination)
            committed = True
        except Exception:
            if backup is not None and backup.exists() and not destination.exists():
                os.replace(backup, destination)
                backup = None
            raise
        if backup is not None:
            shutil.rmtree(backup, ignore_errors=True)
            backup = None
    except (OutputSafetyError, OutputConflictError):
        raise
    except OSError as exc:
        raise OutputSafetyError(f"failed to commit output run: {type(exc).__name__}") from exc
    finally:
        if not committed and temporary.exists():
            shutil.rmtree(temporary, ignore_errors=True)
        if backup is not None and backup.exists() and not destination.exists():
            os.replace(backup, destination)
    return output_paths


def write_private_directory_bundle(
    directory: Path,
    payloads: Mapping[str, str],
    *,
    overwrite: bool,
) -> dict[str, Path]:
    """Commit a set of private files by atomically replacing their directory."""

    destination, parent = _validate_run_target(directory, overwrite)
    if not payloads:
        raise OutputSafetyError("output bundle must contain at least one file")
    for filename in payloads:
        if Path(filename).name != filename or filename in {".", ".."}:
            raise OutputSafetyError(f"unsafe output bundle filename: {filename}")
    temporary = Path(tempfile.mkdtemp(prefix=f".tmp-{destination.name}-", dir=str(parent)))
    os.chmod(temporary, 0o700)
    backup: Path | None = None
    committed = False
    try:
        for filename, content in payloads.items():
            _write_private(temporary / filename, content.rstrip() + "\n")
        if destination.exists():
            backup = parent / f".backup-{destination.name}-{uuid.uuid4().hex}"
            os.replace(destination, backup)
        try:
            os.replace(temporary, destination)
            committed = True
        except Exception:
            if backup is not None and backup.exists() and not destination.exists():
                os.replace(backup, destination)
                backup = None
            raise
        if backup is not None:
            shutil.rmtree(backup, ignore_errors=True)
            backup = None
    except OSError as exc:
        raise OutputSafetyError(f"failed to commit output bundle: {type(exc).__name__}") from exc
    finally:
        if not committed and temporary.exists():
            shutil.rmtree(temporary, ignore_errors=True)
        if backup is not None and backup.exists() and not destination.exists():
            os.replace(backup, destination)
    return {filename: destination / filename for filename in payloads}


def write_json_atomically(path: Path, value: Mapping[str, Any], *, overwrite: bool) -> Path:
    destination = Path(path)
    return write_text_atomically(destination, _stable_json(value), overwrite=overwrite)


def write_text_atomically(path: Path, value: str, *, overwrite: bool) -> Path:
    destination = Path(path)
    parent = destination.parent
    if parent.exists() and (parent.is_symlink() or not parent.is_dir()):
        raise OutputSafetyError("text output parent must be a real directory")
    parent.mkdir(parents=True, exist_ok=True)
    destination = parent.resolve(strict=True) / destination.name
    if destination.is_symlink():
        raise OutputSafetyError("refusing to replace an output symlink")
    if destination.exists() and not overwrite:
        raise OutputConflictError(f"output already exists: {destination}")
    descriptor, temporary_name = tempfile.mkstemp(prefix=f".{destination.name}.", dir=str(parent))
    temporary = Path(temporary_name)
    try:
        os.fchmod(descriptor, 0o600)
        with os.fdopen(descriptor, "w", encoding="utf-8", newline="\n") as handle:
            handle.write(value.rstrip() + "\n")
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, destination)
    except OSError as exc:
        raise OutputSafetyError(f"failed to write text output: {type(exc).__name__}") from exc
    finally:
        if temporary.exists():
            temporary.unlink()
    return destination
