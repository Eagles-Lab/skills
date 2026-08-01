"""Safe, transactional output bundle handling."""

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
from typing import Any, Dict, Mapping, Optional

from .errors import OutputConflictError, OutputSafetyError

SAFE_RESUME_ID = re.compile(r"^[A-Za-z0-9_-]{1,64}$")
OUTPUT_FILENAMES = (
    "extracted.json",
    "score.json",
    "analysis.json",
    "suggestions.md",
    "interview_questions.md",
)


def sha256_file(path: Path) -> str:
    """Hash an input without retaining its sensitive contents in logs."""

    digest = hashlib.sha256()
    with Path(path).open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def validate_resume_id(resume_id: str) -> str:
    """Validate an externally supplied output identifier."""

    if not isinstance(resume_id, str) or not SAFE_RESUME_ID.fullmatch(resume_id):
        raise OutputSafetyError(
            "resume_id must match [A-Za-z0-9_-]{1,64}; paths and control characters are forbidden"
        )
    return resume_id


def derive_resume_id(name: str, input_sha256: str) -> str:
    """Generate a stable safe identifier from a display name and input digest."""

    normalized = unicodedata.normalize("NFKD", name or "resume")
    ascii_name = normalized.encode("ascii", "ignore").decode("ascii").lower()
    slug = re.sub(r"[^a-z0-9]+", "-", ascii_name).strip("-") or "resume"
    digest = re.sub(r"[^a-fA-F0-9]", "", input_sha256)[:8].lower()
    if len(digest) != 8:
        digest = hashlib.sha256(input_sha256.encode("utf-8")).hexdigest()[:8]
    return validate_resume_id(f"{slug[:55]}-{digest}")


def resolve_bundle_path(output_root: Path, resume_id: str) -> Path:
    """Resolve a candidate bundle and prove it remains below the output root."""

    validated = validate_resume_id(resume_id)
    root = Path(output_root).expanduser()
    if root.exists() and (root.is_symlink() or not root.is_dir()):
        raise OutputSafetyError("output root must be a real directory, not a symlink or file")
    root.mkdir(parents=True, exist_ok=True)
    resolved_root = root.resolve(strict=True)
    target = resolved_root / validated
    try:
        target.relative_to(resolved_root)
    except ValueError as exc:  # defensive even though the identifier is strict
        raise OutputSafetyError("resolved output path escapes the output root") from exc
    if target.is_symlink():
        raise OutputSafetyError("refusing to write through an output symlink")
    return target


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


def _bundle_payloads(
    *,
    extracted: Mapping[str, Any],
    score: Mapping[str, Any],
    analysis: Mapping[str, Any],
    suggestions: str,
    interview_questions: str,
) -> Dict[str, str]:
    payloads = {
        "extracted.json": _stable_json(extracted),
        "score.json": _stable_json(score),
        "analysis.json": _stable_json(analysis),
        "suggestions.md": suggestions.rstrip() + "\n",
        "interview_questions.md": interview_questions.rstrip() + "\n",
    }
    if tuple(payloads) != OUTPUT_FILENAMES:
        raise OutputSafetyError("output bundle contract must contain exactly five artifacts")
    return payloads


def write_output_bundle(
    output_root: Path,
    resume_id: str,
    *,
    extracted: Mapping[str, Any],
    score: Mapping[str, Any],
    analysis: Mapping[str, Any],
    suggestions: str,
    interview_questions: str,
    overwrite: bool = False,
) -> Dict[str, str]:
    """Write all five artifacts and reveal them only after every write succeeds."""

    final_dir = resolve_bundle_path(output_root, resume_id)
    root = final_dir.parent
    if final_dir.exists() and not overwrite:
        raise OutputConflictError(f"output bundle already exists: {final_dir}")
    if final_dir.exists() and not final_dir.is_dir():
        raise OutputSafetyError(f"output target is not a directory: {final_dir}")

    payloads = _bundle_payloads(
        extracted=extracted,
        score=score,
        analysis=analysis,
        suggestions=suggestions,
        interview_questions=interview_questions,
    )
    temporary = Path(tempfile.mkdtemp(prefix=f".tmp-{resume_id}-", dir=str(root)))
    os.chmod(temporary, 0o700)
    backup: Optional[Path] = None
    committed = False
    try:
        for filename in OUTPUT_FILENAMES:
            _write_private(temporary / filename, payloads[filename])

        if final_dir.exists():
            if final_dir.is_symlink():
                raise OutputSafetyError("refusing to overwrite an output symlink")
            backup = root / f".backup-{resume_id}-{uuid.uuid4().hex}"
            os.replace(final_dir, backup)
        try:
            os.replace(temporary, final_dir)
            committed = True
        except Exception:
            if backup is not None and backup.exists() and not final_dir.exists():
                os.replace(backup, final_dir)
                backup = None
            raise
        if backup is not None:
            shutil.rmtree(backup, ignore_errors=True)
            backup = None
    except OutputSafetyError:
        raise
    except OSError as exc:
        raise OutputSafetyError(f"failed to commit output bundle: {exc}") from exc
    finally:
        if not committed and temporary.exists():
            shutil.rmtree(temporary, ignore_errors=True)
        if backup is not None and backup.exists() and not final_dir.exists():
            os.replace(backup, final_dir)

    return {
        filename.removesuffix(Path(filename).suffix): str(final_dir / filename)
        for filename in OUTPUT_FILENAMES
    }


def write_private_directory_bundle(
    directory: Path,
    payloads: Mapping[str, str],
    *,
    overwrite: bool,
) -> Dict[str, Path]:
    """Commit a set of private files by atomically replacing their directory."""

    destination = Path(directory).expanduser()
    if not destination.name or destination.name in {".", ".."}:
        raise OutputSafetyError("bundle output must name a dedicated directory")
    parent = destination.parent
    if parent.exists() and (parent.is_symlink() or not parent.is_dir()):
        raise OutputSafetyError("bundle output parent must be a real directory")
    parent.mkdir(parents=True, exist_ok=True)
    resolved_parent = parent.resolve(strict=True)
    destination = resolved_parent / destination.name
    if destination.is_symlink():
        raise OutputSafetyError("refusing to replace a bundle output symlink")
    if destination.exists() and not overwrite:
        raise OutputConflictError(f"output bundle already exists: {destination}")
    if destination.exists() and not destination.is_dir():
        raise OutputSafetyError(f"output bundle target is not a directory: {destination}")
    if not payloads:
        raise OutputSafetyError("output bundle must contain at least one file")
    for filename in payloads:
        if Path(filename).name != filename or filename in {".", ".."}:
            raise OutputSafetyError(f"unsafe output bundle filename: {filename}")

    temporary = Path(tempfile.mkdtemp(prefix=f".tmp-{destination.name}-", dir=resolved_parent))
    os.chmod(temporary, 0o700)
    backup: Optional[Path] = None
    committed = False
    try:
        for filename, content in payloads.items():
            _write_private(temporary / filename, content.rstrip() + "\n")

        if destination.exists():
            backup = resolved_parent / f".backup-{destination.name}-{uuid.uuid4().hex}"
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
    except OutputSafetyError:
        raise
    except OSError as exc:
        raise OutputSafetyError(f"failed to commit output bundle: {exc}") from exc
    finally:
        if not committed and temporary.exists():
            shutil.rmtree(temporary, ignore_errors=True)
        if backup is not None and backup.exists() and not destination.exists():
            os.replace(backup, destination)

    return {filename: destination / filename for filename in payloads}


def write_json_atomically(path: Path, value: Mapping[str, Any], *, overwrite: bool) -> Path:
    """Atomically write a private standalone JSON artifact such as a batch summary."""

    destination = Path(path)
    parent = destination.parent
    if parent.exists() and (parent.is_symlink() or not parent.is_dir()):
        raise OutputSafetyError("JSON output parent must be a real directory")
    parent.mkdir(parents=True, exist_ok=True)
    destination = parent.resolve(strict=True) / destination.name
    if destination.is_symlink():
        raise OutputSafetyError("refusing to replace a JSON output symlink")
    if destination.exists() and not overwrite:
        raise OutputConflictError(f"output already exists: {destination}")

    descriptor, temporary_name = tempfile.mkstemp(prefix=f".{destination.name}.", dir=str(parent))
    temporary = Path(temporary_name)
    try:
        os.fchmod(descriptor, 0o600)
        with os.fdopen(descriptor, "w", encoding="utf-8", newline="\n") as handle:
            handle.write(_stable_json(value))
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, destination)
    except OSError as exc:
        raise OutputSafetyError(f"failed to write JSON output: {exc}") from exc
    finally:
        if temporary.exists():
            temporary.unlink()
    return destination


def write_text_atomically(path: Path, value: str, *, overwrite: bool) -> Path:
    """Atomically write one private UTF-8 text artifact."""

    destination = Path(path)
    parent = destination.parent
    if parent.exists() and (parent.is_symlink() or not parent.is_dir()):
        raise OutputSafetyError("text output parent must be a real directory")
    parent.mkdir(parents=True, exist_ok=True)
    destination = parent.resolve(strict=True) / destination.name
    if destination.is_symlink():
        raise OutputSafetyError("refusing to replace a text output symlink")
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
        raise OutputSafetyError(f"failed to write text output: {exc}") from exc
    finally:
        if temporary.exists():
            temporary.unlink()
    return destination
