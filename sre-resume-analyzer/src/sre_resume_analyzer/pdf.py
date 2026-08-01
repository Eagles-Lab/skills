"""Bounded PDF text extraction into an untrusted raw interchange format."""

from __future__ import annotations

import signal
import threading
import time
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path
from types import FrameType
from typing import Any, Dict, Iterator, List, Optional

from .errors import OutputSafetyError, PDFExtractionError
from .output import sha256_file, write_json_atomically

RAW_EXTRACTION_SCHEMA_VERSION = "1.0"


@contextmanager
def _extraction_timeout(seconds: float) -> Iterator[None]:
    """Interrupt a stuck parser on the main thread; deadline checks cover workers."""

    can_interrupt = (
        threading.current_thread() is threading.main_thread()
        and hasattr(signal, "SIGALRM")
        and hasattr(signal, "setitimer")
    )
    if not can_interrupt:
        yield
        return
    previous_timer = signal.getitimer(signal.ITIMER_REAL)
    if previous_timer[0] > 0:
        yield
        return
    previous_handler = signal.getsignal(signal.SIGALRM)

    def timeout_handler(_signum: int, _frame: Optional[FrameType]) -> None:
        raise PDFExtractionError(f"PDF extraction exceeded the {seconds:g} second limit")

    signal.signal(signal.SIGALRM, timeout_handler)
    signal.setitimer(signal.ITIMER_REAL, seconds)
    try:
        yield
    finally:
        signal.setitimer(signal.ITIMER_REAL, 0)
        signal.signal(signal.SIGALRM, previous_handler)


@dataclass(frozen=True)
class PDFLimits:
    max_file_bytes: int = 20 * 1024 * 1024
    max_pages: int = 40
    max_chars_per_page: int = 100_000
    max_tables_per_page: int = 20
    max_table_cells: int = 50_000
    timeout_seconds: float = 30.0
    min_total_chars: int = 100

    def __post_init__(self) -> None:
        for field_name in (
            "max_file_bytes",
            "max_pages",
            "max_chars_per_page",
            "max_tables_per_page",
            "max_table_cells",
            "min_total_chars",
        ):
            if getattr(self, field_name) < 1:
                raise ValueError(f"{field_name} must be positive")
        if self.timeout_seconds <= 0:
            raise ValueError("timeout_seconds must be positive")


def _validate_pdf_path(path: Path, limits: PDFLimits) -> Path:
    source = Path(path)
    if not source.exists() or not source.is_file():
        raise PDFExtractionError("PDF input does not exist or is not a file")
    if source.is_symlink():
        raise PDFExtractionError("PDF input must be a regular file, not a symlink")
    if source.suffix.lower() != ".pdf":
        raise PDFExtractionError("input must have a .pdf extension")
    size = source.stat().st_size
    if size == 0:
        raise PDFExtractionError("PDF input is empty")
    if size > limits.max_file_bytes:
        raise PDFExtractionError(
            f"PDF exceeds the {limits.max_file_bytes // (1024 * 1024)} MiB limit"
        )
    return source


def _check_deadline(started_at: float, limits: PDFLimits) -> None:
    if time.monotonic() - started_at > limits.timeout_seconds:
        raise PDFExtractionError(
            f"PDF extraction exceeded the {limits.timeout_seconds:g} second limit"
        )


def _count_table_cells(table: List[List[Any]]) -> int:
    return sum(len(row) for row in table if isinstance(row, list))


def extract_raw_pdf(path: Path, *, limits: Optional[PDFLimits] = None) -> Dict[str, Any]:
    """Extract raw text/tables only; no resume semantics are inferred here."""

    limits = limits or PDFLimits()
    source = _validate_pdf_path(path, limits)
    try:
        import pdfplumber
    except ImportError as exc:  # pragma: no cover - packaging smoke test covers this path
        raise PDFExtractionError("pdfplumber is required for PDF extraction") from exc

    started_at = time.monotonic()
    digest = sha256_file(source)
    pages: List[Dict[str, Any]] = []
    full_text_parts: List[str] = []
    total_tables = 0
    total_cells = 0

    try:
        with (
            _extraction_timeout(limits.timeout_seconds),
            pdfplumber.open(source) as document,
        ):
            page_count = len(document.pages)
            if page_count == 0:
                raise PDFExtractionError("PDF contains no pages")
            if page_count > limits.max_pages:
                raise PDFExtractionError(f"PDF exceeds the {limits.max_pages} page limit")

            for index, page in enumerate(document.pages, start=1):
                _check_deadline(started_at, limits)
                text = page.extract_text() or ""
                if len(text) > limits.max_chars_per_page:
                    raise PDFExtractionError(
                        f"PDF page {index} exceeds the {limits.max_chars_per_page} character limit"
                    )
                tables = [table for table in (page.extract_tables() or []) if table]
                if len(tables) > limits.max_tables_per_page:
                    raise PDFExtractionError(
                        f"PDF page {index} exceeds the {limits.max_tables_per_page} table limit"
                    )
                page_cells = sum(_count_table_cells(table) for table in tables)
                total_cells += page_cells
                if total_cells > limits.max_table_cells:
                    raise PDFExtractionError(
                        f"PDF exceeds the {limits.max_table_cells} extracted table-cell limit"
                    )
                total_tables += len(tables)
                pages.append(
                    {
                        "page_number": index,
                        "text": text,
                        "char_count": len(text),
                        "tables": tables,
                    }
                )
                full_text_parts.append(text)
                _check_deadline(started_at, limits)
    except PDFExtractionError:
        raise
    except Exception as exc:
        # Do not use the removed pdfplumber.PdfError symbol and do not leak PDF text.
        raise PDFExtractionError(f"PDF parsing failed: {type(exc).__name__}") from exc

    full_text = "\n\n".join(full_text_parts)
    if len(full_text.strip()) < limits.min_total_chars:
        raise PDFExtractionError("PDF produced too little text; scanned PDFs/OCR are not supported")
    return {
        "schema_version": RAW_EXTRACTION_SCHEMA_VERSION,
        "content_trust": "untrusted",
        "extraction_method": "pdfplumber",
        "source_name": source.name,
        "source_sha256": digest,
        "total_pages": len(pages),
        "total_char_count": len(full_text),
        "total_tables": total_tables,
        "pages": pages,
        "full_text": full_text,
    }


def write_raw_extraction(
    pdf_path: Path,
    output_path: Path,
    *,
    overwrite: bool = False,
    limits: Optional[PDFLimits] = None,
) -> Path:
    """Extract a PDF and atomically persist only raw_extraction.json data."""

    if Path(output_path).name != "raw_extraction.json":
        raise OutputSafetyError(
            "PDF output must be named raw_extraction.json and must never be named extracted.json"
        )
    result = extract_raw_pdf(pdf_path, limits=limits)
    return write_json_atomically(Path(output_path), result, overwrite=overwrite)


# A descriptive compatibility alias for callers that imported the old verb.
extract_pdf = extract_raw_pdf
