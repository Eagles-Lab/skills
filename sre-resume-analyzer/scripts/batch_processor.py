#!/usr/bin/env python3
"""Compatibility wrapper for the v3 batch-analyze command."""

from sre_resume_analyzer.cli import batch_main

if __name__ == "__main__":
    raise SystemExit(batch_main())
