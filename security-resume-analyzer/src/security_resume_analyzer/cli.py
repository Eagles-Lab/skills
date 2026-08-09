"""Privacy-safe CLI entry points and stable exit semantics."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Sequence

from .analyzer import SecurityResumeAnalyzer
from .batch import BatchProcessor
from .calibration import evaluate, render_markdown
from .errors import (
    AnalyzerError,
    ExitCode,
    InputValidationError,
    OutputSafetyError,
    PDFExtractionError,
)
from .output import write_private_directory_bundle
from .pdf import PDFLimits, write_raw_extraction


def _positive(value: str) -> int:
    parsed = int(value)
    if parsed < 1:
        raise argparse.ArgumentTypeError("value must be at least 1")
    return parsed


def _error(prefix: str, exc: object) -> None:
    print(f"{prefix}: {exc}", file=sys.stderr)


def analyze_main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="analyze-security-resume",
        description="Analyze one canonical security resume v1 JSON document.",
    )
    parser.add_argument("--extracted", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument(
        "--raw-extraction",
        type=Path,
        help="raw_extraction.json used to audit source/canonical grounding",
    )
    parser.add_argument("--include-contact", action="store_true")
    parser.add_argument("--overwrite", action="store_true")
    parser.add_argument("--seed")
    args = parser.parse_args(argv)
    try:
        SecurityResumeAnalyzer(args.output_dir).analyze(
            args.extracted,
            include_contact=args.include_contact,
            overwrite=args.overwrite,
            seed=args.seed,
            raw_extraction_path=args.raw_extraction,
        )
    except InputValidationError as exc:
        _error("input error", exc)
        return int(ExitCode.INPUT_ERROR)
    except OutputSafetyError as exc:
        _error("output error", exc)
        return int(ExitCode.OUTPUT_ERROR)
    except AnalyzerError as exc:
        _error("analysis error", exc)
        return int(ExitCode.INTERNAL_ERROR)
    except Exception as exc:
        _error("internal error", type(exc).__name__)
        return int(ExitCode.INTERNAL_ERROR)
    print(
        json.dumps(
            {"status": "success", "output_dir": str(args.output_dir), "successful": 1},
            sort_keys=True,
        )
    )
    return int(ExitCode.SUCCESS)


def batch_main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="batch-analyze-security",
        description="Deduplicate and analyze canonical security resumes.",
    )
    parser.add_argument("--input-dir", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--parallel", type=_positive, default=3)
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
        _error("input error", exc)
        return int(ExitCode.INPUT_ERROR)
    except OutputSafetyError as exc:
        _error("output error", exc)
        return int(ExitCode.OUTPUT_ERROR)
    except Exception as exc:
        _error("internal error", type(exc).__name__)
        return int(ExitCode.INTERNAL_ERROR)
    public = {
        "status": "partial" if summary["failed"] else "success",
        "raw_file_count": summary["raw_file_count"],
        "unique_candidate_count": summary["unique_candidate_count"],
        "successful": summary["successful"],
        "failed": summary["failed"],
        "output_dir": str(args.output_dir),
    }
    print(json.dumps(public, sort_keys=True))
    return int(ExitCode.PARTIAL_BATCH_FAILURE if summary["failed"] else ExitCode.SUCCESS)


def extract_main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="extract-security-resume-text",
        description="Extract untrusted PDF text; no resume facts are inferred.",
    )
    parser.add_argument("pdf", type=Path)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--overwrite", action="store_true")
    parser.add_argument("--max-pages", type=_positive, default=40)
    parser.add_argument("--timeout-seconds", type=float, default=30.0)
    args = parser.parse_args(argv)
    try:
        output = write_raw_extraction(
            args.pdf,
            args.output,
            overwrite=args.overwrite,
            limits=PDFLimits(max_pages=args.max_pages, timeout_seconds=args.timeout_seconds),
        )
    except OutputSafetyError as exc:
        _error("output error", exc)
        return int(ExitCode.OUTPUT_ERROR)
    except (PDFExtractionError, ValueError) as exc:
        _error("PDF extraction error", exc)
        return int(ExitCode.PDF_EXTRACTION_ERROR)
    except Exception as exc:
        _error("internal error", type(exc).__name__)
        return int(ExitCode.INTERNAL_ERROR)
    print(json.dumps({"status": "success", "output": str(output)}, sort_keys=True))
    return int(ExitCode.SUCCESS)


def calibrate_main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="calibrate-security-scoring",
        description="Evaluate private two-reviewer security scoring calibration.",
    )
    parser.add_argument("--resumes", type=Path, required=True)
    parser.add_argument("--reviews", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--overwrite", action="store_true")
    args = parser.parse_args(argv)
    try:
        report = evaluate(args.resumes, args.reviews)
        write_private_directory_bundle(
            args.output_dir,
            {
                "calibration_report.json": json.dumps(
                    report, ensure_ascii=False, indent=2, sort_keys=True
                ),
                "calibration_report.md": render_markdown(report),
            },
            overwrite=args.overwrite,
        )
    except (InputValidationError, OSError, ValueError) as exc:
        _error("input error", exc)
        return int(ExitCode.INPUT_ERROR)
    except OutputSafetyError as exc:
        _error("output error", exc)
        return int(ExitCode.OUTPUT_ERROR)
    except Exception as exc:
        _error("internal error", type(exc).__name__)
        return int(ExitCode.INTERNAL_ERROR)
    print(
        json.dumps(
            {"status": report["calibration_status"], "output_dir": str(args.output_dir)},
            sort_keys=True,
        )
    )
    return int(ExitCode.SUCCESS if report["passed"] else ExitCode.INTERNAL_ERROR)
