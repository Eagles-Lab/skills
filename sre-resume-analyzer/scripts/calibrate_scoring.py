#!/usr/bin/env python3
"""Compatibility wrapper for the v3 calibrate-scoring command."""

from sre_resume_analyzer.cli import calibrate_main

if __name__ == "__main__":
    raise SystemExit(calibrate_main())
