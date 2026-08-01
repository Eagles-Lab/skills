#!/usr/bin/env python3
"""Compatibility wrapper for the v3 analyze-resume command."""

from sre_resume_analyzer.cli import analyze_main

if __name__ == "__main__":
    raise SystemExit(analyze_main())
