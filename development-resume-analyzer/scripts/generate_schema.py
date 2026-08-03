#!/usr/bin/env python3
"""Generate the checked-in canonical resume JSON Schema."""

from __future__ import annotations

import json
from pathlib import Path

from development_resume_analyzer.models import Resume


def main() -> int:
    skill_root = Path(__file__).resolve().parent.parent
    destination = skill_root / "references" / "extracted_resume.schema.json"
    payload = json.dumps(Resume.model_json_schema(), ensure_ascii=False, indent=2, sort_keys=True)
    destination.write_text(payload + "\n", encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
