#!/usr/bin/env python3
"""Enforce higher coverage floors for critical v1 contract modules."""

from __future__ import annotations

import json
import sys
from pathlib import Path

CRITICAL_THRESHOLDS = {
    "src/security_resume_analyzer/models.py": 95.0,
    "src/security_resume_analyzer/matching.py": 95.0,
    "src/security_resume_analyzer/scoring.py": 95.0,
    "src/security_resume_analyzer/output.py": 95.0,
    "src/security_resume_analyzer/dedup.py": 95.0,
}


def main() -> int:
    if len(sys.argv) != 2:
        raise SystemExit("usage: check_coverage_gates.py COVERAGE_JSON")
    report = json.loads(Path(sys.argv[1]).read_text(encoding="utf-8"))
    files = report.get("files", {})
    failures = []
    for filename, minimum in CRITICAL_THRESHOLDS.items():
        summary = files.get(filename, {}).get("summary")
        if summary is None:
            failures.append(f"{filename}: missing from coverage report")
            continue
        actual = float(summary["percent_covered"])
        if actual < minimum:
            failures.append(f"{filename}: {actual:.2f}% is below {minimum:.2f}%")
    if failures:
        raise SystemExit("\n".join(failures))
    print("Critical module coverage gates passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
