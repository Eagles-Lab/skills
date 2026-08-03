"""Console entry points with stable exit semantics and privacy-safe output."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Optional, Sequence

from .analyzer import ResumeAnalyzer
from .batch import BatchProcessor
from .errors import (
    AnalyzerError,
    ExitCode,
    InputValidationError,
    OutputSafetyError,
    PDFExtractionError,
)
from .pdf import PDFLimits, write_raw_extraction


def _positive_integer(value: str) -> int:
    parsed = int(value)
    if parsed < 1:
        raise argparse.ArgumentTypeError("value must be at least 1")
    return parsed


def _print_error(prefix: str, error: object) -> None:
    print(f"{prefix}: {error}", file=sys.stderr)


def analyze_main(argv: Optional[Sequence[str]] = None) -> int:
    parser = argparse.ArgumentParser(
        prog="analyze-resume",
        description="Validate and analyze one canonical v3 resume JSON document.",
    )
    parser.add_argument("--extracted", type=Path, required=True, help="canonical v3 JSON")
    parser.add_argument(
        "--raw-extraction",
        type=Path,
        help="raw_extraction.json used to audit source/canonical grounding",
    )
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--include-contact", action="store_true")
    parser.add_argument("--overwrite", action="store_true")
    parser.add_argument("--seed", help="explicit deterministic interview-question seed")
    args = parser.parse_args(argv)
    try:
        ResumeAnalyzer(args.output_dir).analyze(
            args.extracted,
            raw_extraction_path=args.raw_extraction,
            include_contact=args.include_contact,
            overwrite=args.overwrite,
            seed=args.seed,
        )
    except InputValidationError as exc:
        _print_error("input error", exc)
        return int(ExitCode.INPUT_ERROR)
    except OutputSafetyError as exc:
        _print_error("output error", exc)
        return int(ExitCode.OUTPUT_ERROR)
    except AnalyzerError as exc:
        _print_error("analysis error", exc)
        return int(ExitCode.INTERNAL_ERROR)
    except KeyboardInterrupt:
        return 130
    except Exception as exc:  # defensive CLI boundary
        _print_error("internal error", type(exc).__name__)
        return int(ExitCode.INTERNAL_ERROR)

    print(
        json.dumps(
            {"status": "success", "output_dir": str(args.output_dir), "successful": 1},
            sort_keys=True,
        )
    )
    return int(ExitCode.SUCCESS)


def extract_main(argv: Optional[Sequence[str]] = None) -> int:
    parser = argparse.ArgumentParser(
        prog="extract-resume-text",
        description="Extract untrusted raw text and tables from a PDF; no resume parsing is done.",
    )
    parser.add_argument("pdf", type=Path)
    parser.add_argument("--output", type=Path, required=True, help="raw_extraction.json path")
    parser.add_argument("--overwrite", action="store_true")
    parser.add_argument("--max-pages", type=_positive_integer, default=40)
    parser.add_argument("--timeout-seconds", type=float, default=30.0)
    args = parser.parse_args(argv)
    try:
        limits = PDFLimits(max_pages=args.max_pages, timeout_seconds=args.timeout_seconds)
        output = write_raw_extraction(
            args.pdf,
            args.output,
            overwrite=args.overwrite,
            limits=limits,
        )
    except OutputSafetyError as exc:
        _print_error("output error", exc)
        return int(ExitCode.OUTPUT_ERROR)
    except (PDFExtractionError, ValueError) as exc:
        _print_error("PDF extraction error", exc)
        return int(ExitCode.PDF_EXTRACTION_ERROR)
    except KeyboardInterrupt:
        return 130
    except Exception as exc:
        _print_error("internal error", type(exc).__name__)
        return int(ExitCode.INTERNAL_ERROR)

    print(json.dumps({"status": "success", "output": str(output)}, sort_keys=True))
    return int(ExitCode.SUCCESS)


def batch_main(argv: Optional[Sequence[str]] = None) -> int:
    parser = argparse.ArgumentParser(
        prog="batch-analyze",
        description="Analyze a sorted directory of canonical v3 resume JSON documents.",
    )
    parser.add_argument("--input-dir", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--parallel", type=_positive_integer, default=3)
    parser.add_argument("--overwrite", action="store_true")
    parser.add_argument(
        "--raw-extraction-dir",
        type=Path,
        help="directory containing <canonical-stem>/raw_extraction.json audit inputs",
    )
    args = parser.parse_args(argv)
    try:
        summary = BatchProcessor(
            args.output_dir,
            max_workers=args.parallel,
            overwrite=args.overwrite,
            raw_extraction_dir=args.raw_extraction_dir,
        ).process_directory(args.input_dir)
    except InputValidationError as exc:
        _print_error("input error", exc)
        return int(ExitCode.INPUT_ERROR)
    except OutputSafetyError as exc:
        _print_error("output error", exc)
        return int(ExitCode.OUTPUT_ERROR)
    except KeyboardInterrupt:
        return 130
    except Exception as exc:
        _print_error("internal error", type(exc).__name__)
        return int(ExitCode.INTERNAL_ERROR)

    print(
        json.dumps(
            {
                "status": "partial" if summary["failed"] else "success",
                "total": summary["total"],
                "successful": summary["successful"],
                "failed": summary["failed"],
                "output_dir": str(args.output_dir),
            },
            sort_keys=True,
        )
    )
    if summary["failed"]:
        return int(ExitCode.PARTIAL_BATCH_FAILURE)
    return int(ExitCode.SUCCESS)
