from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

from security_resume_analyzer.dedup import same_candidate
from security_resume_analyzer.models import Resume

VECTORS = Path(__file__).resolve().parents[2] / "contracts/fixtures/resume-identity-vectors.json"


@pytest.mark.parametrize(
    ("case"),
    json.loads(VECTORS.read_text(encoding="utf-8"))["same_candidate"],
    ids=lambda case: case["id"],
)
def test_shared_same_candidate_vectors(case: dict[str, Any]) -> None:
    left = Resume.model_validate(case["left"])
    right = Resume.model_validate(case["right"])
    assert same_candidate(left, right) is case["expected"]
