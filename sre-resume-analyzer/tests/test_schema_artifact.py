"""Checks for generated and published interface artifacts."""

import json
from pathlib import Path

from sre_resume_analyzer.models import SCHEMA_VERSION, Resume
from sre_resume_analyzer.version import SCHEMA_VERSION as PUBLIC_SCHEMA_VERSION

SKILL_ROOT = Path(__file__).resolve().parent.parent


def test_checked_in_json_schema_is_current() -> None:
    published = json.loads(
        (SKILL_ROOT / "references" / "extracted_resume.schema.json").read_text(encoding="utf-8")
    )
    assert published == Resume.model_json_schema()


def test_schema_version_has_one_source_of_truth() -> None:
    assert SCHEMA_VERSION == PUBLIC_SCHEMA_VERSION == "3.0"
