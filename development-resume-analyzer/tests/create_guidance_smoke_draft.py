#!/usr/bin/env python3
"""Create a private synthetic local-guidance draft for CI script smoke tests."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

FULLWIDTH_COLON = "\N{FULLWIDTH COLON}"


def _write_private(path: Path, text: str) -> None:
    path.write_text(text, encoding="utf-8")
    path.chmod(0o600)


def _first_experience_pointer(extracted: dict[str, Any]) -> str:
    for group in ("projects", "internships", "security_activities"):
        values = extracted.get(group)
        if isinstance(values, list) and values:
            return f"/{group}/0"
    raise ValueError("smoke fixture must contain at least one experience")


def _weak_dimension_pointer(score: dict[str, Any]) -> str:
    dimensions = score.get("dimension_scores")
    if not isinstance(dimensions, dict) or not dimensions:
        raise ValueError("smoke score must contain dimensions")
    ranked = sorted(
        (
            (float(value.get("score", 0)), key)
            for key, value in dimensions.items()
            if isinstance(key, str) and isinstance(value, dict)
        ),
    )
    if not ranked:
        raise ValueError("smoke score has no numeric dimension")
    return f"/dimension_scores/{ranked[0][1]}"


def create_draft(deterministic_run: Path, draft_root: Path) -> None:
    candidates = sorted((deterministic_run / "resume_analysis").iterdir())
    if len(candidates) != 1:
        raise ValueError("smoke run must contain exactly one candidate")
    candidate = candidates[0]
    extracted = json.loads((candidate / "extracted.json").read_text(encoding="utf-8"))
    score = json.loads((candidate / "score.json").read_text(encoding="utf-8"))
    experience = _first_experience_pointer(extracted)
    weak_dimension = _weak_dimension_pointer(score)

    draft_root.mkdir(mode=0o700)
    destination = draft_root / candidate.name
    destination.mkdir(mode=0o700)
    suggestions = f"""### 逐段经历点评

- 该经历提供了可核验的实现事实, 仍应明确个人边界和验收方式。[E1] [S1]
- 该经历的后续核验应区分已有事实、个人贡献和仍需确认的结果。[E1] [S1]

### 改写示例

- 改写时保留已有实现事实, 并使用【待补充{FULLWIDTH_COLON}个人职责和验收结果】标记缺口。[E1]

### 成长建议

- 建议补充可复现的验证记录, 以解决当前证据缺口。[S1]

### 证据索引

- [E1] extracted.json#{experience}
- [S1] score.json#{weak_dimension}
"""
    question_blocks = ["# 个性化面试题", ""]
    for index in range(1, 11):
        question_blocks.extend(
            [
                f"## {index}. 经历核验 {index}",
                "",
                f"- 主问题{FULLWIDTH_COLON}请说明该经历中的个人实现。[E1]",
                f"- 针对性追问{FULLWIDTH_COLON}你如何验证实现结果。[E1]",
                f"- 核验要点{FULLWIDTH_COLON}区分已证明事实和待补充边界。[S1]",
                "",
            ],
        )
    question_blocks.extend(
        [
            "## 证据索引",
            "",
            f"- [E1] extracted.json#{experience}",
            f"- [S1] score.json#{weak_dimension}",
        ],
    )
    _write_private(destination / "suggestions.md", suggestions)
    _write_private(destination / "interview_questions.md", "\n".join(question_blocks) + "\n")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--deterministic-run", type=Path, required=True)
    parser.add_argument("--draft-dir", type=Path, required=True)
    args = parser.parse_args()
    create_draft(args.deterministic_run, args.draft_dir)


if __name__ == "__main__":
    main()
