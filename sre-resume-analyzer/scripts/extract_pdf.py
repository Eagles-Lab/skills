#!/usr/bin/env python3
"""Compatibility wrapper for the v3 extract-resume-text command."""

from sre_resume_analyzer.cli import extract_main

if __name__ == "__main__":
    raise SystemExit(extract_main())
