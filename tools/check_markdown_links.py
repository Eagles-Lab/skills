#!/usr/bin/env python3
"""Check repository-local Markdown links without network access."""

from __future__ import annotations

import re
import sys
from pathlib import Path
from urllib.parse import unquote

ROOT = Path(__file__).resolve().parents[1]
SKIP_PARTS = {
    ".git",
    ".mypy_cache",
    ".pytest_cache",
    ".ruff_cache",
    ".venv",
    "build",
    "dist",
    "htmlcov",
}
LINK_RE = re.compile(r"!?\[[^\]]*\]\((?P<target><[^>]+>|[^)\s]+)(?:\s+['\"][^)]*['\"])?\)")


def markdown_files() -> list[Path]:
    return sorted(
        path
        for path in ROOT.rglob("*.md")
        if not any(part in SKIP_PARTS for part in path.relative_to(ROOT).parts)
    )


def main() -> int:
    failures: list[str] = []
    for document in markdown_files():
        try:
            text = document.read_text(encoding="utf-8")
        except (OSError, UnicodeError) as exc:
            failures.append(f"{document.relative_to(ROOT)}: cannot read UTF-8 text: {exc}")
            continue
        for line_number, line in enumerate(text.splitlines(), start=1):
            for match in LINK_RE.finditer(line):
                raw = match.group("target").strip("<>")
                if raw.startswith(("http://", "https://", "mailto:", "#")):
                    continue
                target = unquote(raw.split("#", 1)[0])
                if not target:
                    continue
                resolved = (document.parent / target).resolve()
                try:
                    resolved.relative_to(ROOT.resolve())
                except ValueError:
                    failures.append(
                        f"{document.relative_to(ROOT)}:{line_number}: link escapes repository: {raw}"
                    )
                    continue
                if not resolved.exists():
                    failures.append(
                        f"{document.relative_to(ROOT)}:{line_number}: missing local target {raw}"
                    )
    if failures:
        print("Markdown link errors:", file=sys.stderr)
        for failure in failures:
            print(f"- {failure}", file=sys.stderr)
        return 1
    print(f"checked local links in {len(markdown_files())} Markdown files")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
