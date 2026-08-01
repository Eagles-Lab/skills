"""Console entry points with stable exit semantics and privacy-safe output."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Optional, Sequence

from .analyzer import ResumeAnalyzer, load_resume
from .batch import BatchProcessor
from .errors import (
    AnalyzerError,
    ExitCode,
    InputValidationError,
    OutputSafetyError,
    PDFExtractionError,
)
from .output import (
    derive_resume_id,
    sha256_file,
    validate_resume_id,
    write_private_directory_bundle,
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
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--include-contact", action="store_true")
    parser.add_argument("--overwrite", action="store_true")
    parser.add_argument("--seed", help="explicit deterministic interview-question seed")
    args = parser.parse_args(argv)
    try:
        outputs = ResumeAnalyzer(args.output_dir).analyze(
            args.extracted,
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

    print(json.dumps({"status": "success", "outputs": outputs}, sort_keys=True))
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
    args = parser.parse_args(argv)
    try:
        summary = BatchProcessor(
            args.output_dir,
            max_workers=args.parallel,
            overwrite=args.overwrite,
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
                "summary": str(args.output_dir / "batch_summary.json"),
            },
            sort_keys=True,
        )
    )
    if summary["failed"]:
        return int(ExitCode.PARTIAL_BATCH_FAILURE)
    return int(ExitCode.SUCCESS)


def calibrate_main(argv: Optional[Sequence[str]] = None) -> int:
    """Evaluate private human reviews against already-generated score files."""

    parser = argparse.ArgumentParser(
        prog="calibrate-scoring",
        description="Compare two-reviewer calibration CSV data with analyzer score files.",
    )
    parser.add_argument("--reviews", type=Path, required=True)
    parser.add_argument("--resumes", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--baseline-config", type=Path)
    parser.add_argument("--candidate-config", type=Path)
    parser.add_argument("--overwrite", action="store_true")
    args = parser.parse_args(argv)
    try:
        from .calibration import (
            CalibrationError,
            evaluate_calibration_csv,
            render_calibration_markdown,
            scoring_config_diff,
        )
        from .scoring import ScoreCalculator, ScoringConfig

        if not args.resumes.exists() or not args.resumes.is_dir():
            raise InputValidationError("canonical resumes directory does not exist")
        scores = {}
        metadata = {}
        baseline_config = ScoringConfig.from_source(args.baseline_config)
        candidate_config = ScoringConfig.from_source(args.candidate_config)
        calculator = ScoreCalculator(candidate_config)
        for path in sorted(args.resumes.glob("*.json")):
            resume = load_resume(path)
            digest = sha256_file(path)
            resume_id = (
                validate_resume_id(resume.resume_id)
                if resume.resume_id is not None
                else derive_resume_id(resume.basic_info.name, digest)
            )
            if resume_id in scores:
                raise InputValidationError(f"duplicate canonical resume_id: {resume_id}")
            scores[resume_id] = calculator.calculate(resume)
            resume_text = json.dumps(resume.model_dump(mode="json"), ensure_ascii=False)
            if resume.internships and resume.projects:
                resume_type = "internship_and_project"
            elif resume.internships:
                resume_type = "internship_only"
            elif resume.projects:
                resume_type = "project_only"
            else:
                resume_type = "skills_only"
            metadata[resume_id] = {
                "language": (
                    "zh"
                    if any("\u4e00" <= character <= "\u9fff" for character in resume_text)
                    else "en"
                ),
                "resume_type": resume_type,
            }
        if not scores:
            raise InputValidationError("resumes directory contains no canonical JSON files")

        report = evaluate_calibration_csv(
            args.reviews,
            scores,
            metadata=metadata,
            config_diff=scoring_config_diff(baseline_config, candidate_config),
        )
        write_private_directory_bundle(
            args.output_dir,
            {
                "calibration_report.json": json.dumps(
                    report.model_dump(mode="json"),
                    ensure_ascii=False,
                    indent=2,
                    sort_keys=True,
                ),
                "calibration_report.md": render_calibration_markdown(report),
            },
            overwrite=args.overwrite,
        )
    except (InputValidationError, CalibrationError, OSError, ValueError) as exc:
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
                "status": "pass" if report.passed else "fail",
                "report": str(args.output_dir / "calibration_report.json"),
            },
            sort_keys=True,
        )
    )
    return int(ExitCode.SUCCESS if report.passed else ExitCode.INTERNAL_ERROR)
