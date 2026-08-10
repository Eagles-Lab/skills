from __future__ import annotations

import re
from pathlib import Path

SKILL_ROOT = Path(__file__).resolve().parents[1]


def test_core_skill_is_compact_and_all_direct_references_exist() -> None:
    skill = (SKILL_ROOT / "SKILL.md").read_text(encoding="utf-8")
    assert 200 <= len(skill.splitlines()) <= 300

    targets = re.findall(r"\[[^\]]+\]\((references/[^)#]+\.md)(?:#[^)]+)?\)", skill)
    assert set(targets) == {
        "references/canonical-schema.md",
        "references/claude.md",
        "references/codex.md",
        "references/deduplication.md",
        "references/document-workflow.md",
        "references/evidence-model.md",
        "references/local-guidance-layer.md",
        "references/privacy-security.md",
        "references/scoring-rubric.md",
        "references/source-audit.md",
    }
    assert all((SKILL_ROOT / target).is_file() for target in targets)


def test_codex_and_claude_adapters_share_the_neutral_handoff_contract() -> None:
    codex = (SKILL_ROOT / "references/codex.md").read_text(encoding="utf-8")
    claude = (SKILL_ROOT / "references/claude.md").read_text(encoding="utf-8")

    for adapter in (codex, claude):
        assert "extraction" in adapter
        assert "canonical development v1" in adapter
        assert "source audit" in adapter
        assert "ten" in adapter.lower()
        assert "untrusted" in adapter

    assert "capabilities installed" in claude
    assert "never hard-code a pseudo-tool" in claude
    assert "one deidentified raw artifact" in " ".join(claude.split())


def test_openai_agent_metadata_selects_the_development_skill() -> None:
    metadata = (SKILL_ROOT / "agents/openai.yaml").read_text(encoding="utf-8")
    assert 'display_name: "Development Resume Analyzer"' in metadata
    assert "$development-resume-analyzer" in metadata
    assert "security-resume-analyzer" not in metadata
    assert "sre-resume-analyzer" not in metadata
