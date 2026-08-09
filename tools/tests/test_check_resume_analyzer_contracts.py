"""Regression tests for the repository-level resume analyzer contract checker."""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

TOOLS_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(TOOLS_DIR))

import check_resume_analyzer_contracts as contracts


class AgentYamlContractTests(unittest.TestCase):
    def _errors(self, text: str) -> list[str]:
        errors = contracts.ContractErrors()
        contracts._check_agent_yaml(
            text,
            label="example-resume-analyzer",
            skill_name="example-resume-analyzer",
            errors=errors,
        )
        return errors.items

    def test_accepts_structured_agent_metadata(self) -> None:
        self.assertEqual(
            self._errors(
                """\
interface:
  display_name: Example Resume Analyzer
  short_description: Source-audited resume analysis
  default_prompt: >-
    Use $example-resume-analyzer to audit this resume.
"""
            ),
            [],
        )

    def test_rejects_invalid_yaml(self) -> None:
        errors = self._errors("interface: [")

        self.assertTrue(any("invalid YAML" in error for error in errors), errors)

    def test_rejects_non_mapping_root_and_interface(self) -> None:
        for text, expected in (
            ("- interface", "root must be a mapping"),
            ("interface: []", "interface must be a mapping"),
        ):
            with self.subTest(text=text):
                self.assertTrue(any(expected in error for error in self._errors(text)))

    def test_requires_non_empty_string_interface_fields(self) -> None:
        cases = {
            "display_name": "display_name: '   '",
            "short_description": "short_description: []",
            "default_prompt": "default_prompt:",
        }
        base = {
            "display_name": "display_name: Example Resume Analyzer",
            "short_description": "short_description: Source audit",
            "default_prompt": "default_prompt: Use $example-resume-analyzer",
        }
        for field, replacement in cases.items():
            values = base | {field: replacement}
            text = "interface:\n" + "".join(f"  {value}\n" for value in values.values())
            with self.subTest(field=field):
                expected = f"interface.{field} must be a non-empty string"
                self.assertTrue(any(expected in error for error in self._errors(text)))

    def test_requires_exact_skill_invocation_token(self) -> None:
        for prompt in (
            "Use $other-resume-analyzer",
            "Use $example-resume-analyzer-extra",
            "Use $example-resume-analyzer_suffix",
        ):
            text = f"""\
interface:
  display_name: Example Resume Analyzer
  short_description: Source audit
  default_prompt: {prompt}
"""
            with self.subTest(prompt=prompt):
                expected = "default_prompt must invoke $example-resume-analyzer"
                self.assertTrue(any(expected in error for error in self._errors(text)))


if __name__ == "__main__":
    unittest.main()
