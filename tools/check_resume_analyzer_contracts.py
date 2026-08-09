#!/usr/bin/env python3
"""Fail when the three resume analyzers drift from their shared public contract."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import subprocess
import sys
from collections.abc import Mapping
from pathlib import Path
from typing import Any

try:
    import yaml
except ModuleNotFoundError:
    yaml = None  # type: ignore[assignment]

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_MANIFEST = ROOT / "contracts" / "resume-analyzers.json"
_YAML_BOOTSTRAP_ENV = "RESUME_CONTRACT_YAML_BOOTSTRAPPED"


class ContractErrors:
    def __init__(self) -> None:
        self.items: list[str] = []

    def require(self, condition: bool, message: str) -> None:
        if not condition:
            self.items.append(message)


def _read_text(path: Path, errors: ContractErrors) -> str:
    try:
        return path.read_text(encoding="utf-8")
    except (OSError, UnicodeError) as exc:
        errors.items.append(f"{path.relative_to(ROOT)}: cannot read UTF-8 text: {exc}")
        return ""


def _rerun_with_pyyaml() -> int:
    """Keep the documented ``python3`` entry point usable without a root environment."""
    if os.environ.get(_YAML_BOOTSTRAP_ENV):
        print("contract dependency error: PyYAML>=6,<7 is unavailable", file=sys.stderr)
        return 2

    environment = os.environ.copy()
    environment[_YAML_BOOTSTRAP_ENV] = "1"
    command = [
        "uv",
        "run",
        "--isolated",
        "--no-project",
        "--python",
        sys.executable,
        "--with",
        "PyYAML>=6,<7",
        "python",
        str(Path(__file__).resolve()),
        *sys.argv[1:],
    ]
    try:
        completed = subprocess.run(command, check=False, env=environment)
    except FileNotFoundError:
        print(
            "contract dependency error: PyYAML is unavailable and uv was not found",
            file=sys.stderr,
        )
        return 2
    return completed.returncode


def _check_agent_yaml(
    text: str,
    *,
    label: str,
    skill_name: str,
    errors: ContractErrors,
) -> None:
    if yaml is None:
        errors.items.append(f"{label}/agents/openai.yaml: PyYAML is unavailable")
        return

    try:
        document = yaml.safe_load(text)
    except yaml.YAMLError as exc:
        errors.items.append(f"{label}/agents/openai.yaml: invalid YAML: {exc}")
        return

    if not isinstance(document, Mapping):
        errors.items.append(f"{label}/agents/openai.yaml: root must be a mapping")
        return
    interface = document.get("interface")
    if not isinstance(interface, Mapping):
        errors.items.append(f"{label}/agents/openai.yaml: interface must be a mapping")
        return

    fields: dict[str, str] = {}
    for field in ("display_name", "short_description", "default_prompt"):
        value = interface.get(field)
        if not isinstance(value, str) or not value.strip():
            errors.items.append(
                f"{label}/agents/openai.yaml: interface.{field} must be a non-empty string"
            )
            continue
        fields[field] = value

    prompt = fields.get("default_prompt")
    if prompt is None:
        return
    invocation = re.compile(
        rf"(?<![A-Za-z0-9_-])\${re.escape(skill_name)}(?![A-Za-z0-9_-])"
    )
    errors.require(
        invocation.search(prompt) is not None,
        f"{label}/agents/openai.yaml: default_prompt must invoke ${skill_name}",
    )


def _frontmatter(text: str) -> dict[str, str]:
    match = re.match(r"\A---\n(?P<body>.*?)\n---\n", text, re.DOTALL)
    if match is None:
        return {}
    result: dict[str, str] = {}
    for line in match.group("body").splitlines():
        key, separator, value = line.partition(":")
        if separator:
            result[key.strip()] = value.strip()
    return result


def _project_metadata(path: Path) -> tuple[str | None, str | None, dict[str, str]]:
    text = path.read_text(encoding="utf-8")
    version_match = re.search(r'^version\s*=\s*"([^"]+)"', text, re.MULTILINE)
    readme_match = re.search(r'^readme\s*=\s*"([^"]+)"', text, re.MULTILINE)
    scripts_match = re.search(
        r"^\[project\.scripts\]\n(?P<body>.*?)(?=^\[|\Z)",
        text,
        re.MULTILINE | re.DOTALL,
    )
    scripts: dict[str, str] = {}
    if scripts_match is not None:
        for name, target in re.findall(
            r'^([a-z0-9-]+)\s*=\s*"([^"]+)"', scripts_match.group("body"), re.MULTILINE
        ):
            scripts[name] = target
    return (
        version_match.group(1) if version_match else None,
        readme_match.group(1) if readme_match else None,
        scripts,
    )


def _markdown_targets(text: str) -> set[str]:
    return {
        target.split("#", 1)[0]
        for target in re.findall(r"!?\[[^\]]*\]\(([^)\s]+)", text)
        if target and not re.match(r"(?:https?|mailto):", target)
    }


def _check_analyzer(
    analyzer: dict[str, Any], manifest: dict[str, Any], errors: ContractErrors
) -> None:
    directory = ROOT / analyzer["directory"]
    label = analyzer["directory"]
    errors.require(directory.is_dir(), f"{label}: analyzer directory is missing")

    for relative in manifest["required_files"]:
        errors.require((directory / relative).exists(), f"{label}: missing required {relative}")
    for relative in manifest["forbidden_skill_files"]:
        errors.require(not (directory / relative).exists(), f"{label}: forbidden legacy file {relative}")

    readme = _read_text(directory / "README.md", errors)
    readme_lines = len(readme.splitlines())
    readme_contract = manifest["readme_contract"]
    errors.require(
        readme_contract["min_lines"] <= readme_lines <= readme_contract["max_lines"],
        f"{label}/README.md: expected {readme_contract['min_lines']}-"
        f"{readme_contract['max_lines']} lines, got {readme_lines}",
    )
    for fragment in readme_contract["required_fragments"]:
        errors.require(fragment in readme, f"{label}/README.md: missing {fragment!r}")
    for pattern in readme_contract["forbidden_patterns"]:
        errors.require(
            re.search(pattern, readme, re.IGNORECASE) is None,
            f"{label}/README.md: non-normative boundary violated by /{pattern}/",
        )
    readme_headings = re.findall(r"^## (.+)$", readme, re.MULTILINE)
    errors.require(
        readme_headings == readme_contract["sections"],
        f"{label}/README.md: overview sections drifted: {readme_headings!r}",
    )

    skill = _read_text(directory / "SKILL.md", errors)
    frontmatter = _frontmatter(skill)
    errors.require(
        set(frontmatter) == {"name", "description"},
        f"{label}/SKILL.md: frontmatter must contain only name and description",
    )
    errors.require(
        frontmatter.get("name") == analyzer["skill_name"],
        f"{label}/SKILL.md: wrong frontmatter name",
    )
    headings = re.findall(r"^## (.+)$", skill, re.MULTILINE)
    errors.require(
        headings == manifest["skill_sections"],
        f"{label}/SKILL.md: H2 workflow sections drifted: {headings!r}",
    )
    for fragment in manifest["skill_required_fragments"]:
        errors.require(fragment in skill, f"{label}/SKILL.md: missing contract token {fragment}")
    errors.require(
        analyzer["scoring_profile"] in skill,
        f"{label}/SKILL.md: missing scoring profile {analyzer['scoring_profile']}",
    )
    errors.require(analyzer["status"] in skill, f"{label}/SKILL.md: missing release status")
    if "calibration_status" in analyzer:
        errors.require(
            analyzer["calibration_status"] in skill,
            f"{label}/SKILL.md: missing calibration status",
        )

    linked = _markdown_targets(skill)
    for relative in manifest["required_files"]:
        if relative.startswith("references/"):
            errors.require(relative in linked, f"{label}/SKILL.md: must directly link {relative}")

    agent_yaml = _read_text(directory / "agents" / "openai.yaml", errors)
    _check_agent_yaml(
        agent_yaml,
        label=label,
        skill_name=analyzer["skill_name"],
        errors=errors,
    )

    try:
        version, readme_name, scripts = _project_metadata(directory / "pyproject.toml")
    except (OSError, UnicodeError) as exc:
        errors.items.append(f"{label}/pyproject.toml: cannot parse: {exc}")
    else:
        errors.require(version == analyzer["version"], f"{label}: version is {version!r}")
        errors.require(readme_name == "README.md", f"{label}: project.readme must be README.md")
        errors.require(scripts == analyzer["scripts"], f"{label}: project.scripts drifted: {scripts!r}")

    source_text = "\n".join(
        path.read_text(encoding="utf-8")
        for path in sorted((directory / "src").rglob("*.py"))
    )
    for token in manifest["runtime_contract_tokens"]:
        errors.require(token in source_text, f"{label}/src: missing public runtime token {token}")
    for token in analyzer.get("runtime_required_tokens", []):
        errors.require(token in source_text, f"{label}/src: missing analyzer token {token}")

    workflow = _read_text(ROOT / analyzer["workflow"], errors)
    for token in manifest["workflow_contract_tokens"]:
        errors.require(token in workflow, f"{label}/workflow: missing required gate {token!r}")

    finalizer = _read_text(directory / "scripts" / "finalize_guidance.py", errors)
    for token in manifest["finalizer_contract_tokens"]:
        errors.require(token in finalizer, f"{label}/finalizer: missing manifest token {token}")

    coverage_gate = _read_text(directory / "scripts" / "check_coverage_gates.py", errors)
    for module, minimum in manifest["critical_coverage_modules"].items():
        expected = f'"src/{analyzer["package"]}/{module}": {minimum:.1f}'
        errors.require(
            expected in coverage_gate,
            f"{label}/coverage: missing critical gate {module}>={minimum:.1f}",
        )

    expected_references = {
        relative.removeprefix("references/")
        for relative in manifest["required_files"]
        if relative.startswith("references/")
    }
    actual_references = {
        path.name for path in (directory / "references").iterdir() if path.is_file()
    }
    errors.require(
        actual_references == expected_references,
        f"{label}/references: expected {sorted(expected_references)!r}, "
        f"got {sorted(actual_references)!r}",
    )


def _check_shared_files(manifest: dict[str, Any], errors: ContractErrors) -> None:
    analyzers = manifest["analyzers"]
    for template in manifest["shared_files"]:
        values: list[tuple[str, str]] = []
        for analyzer in analyzers:
            relative = template.format(package=analyzer["package"])
            path = ROOT / analyzer["directory"] / relative
            if not path.is_file():
                errors.items.append(f"{analyzer['directory']}: missing exact-shared file {relative}")
                continue
            values.append((analyzer["directory"], hashlib.sha256(path.read_bytes()).hexdigest()))
        if len(values) == len(analyzers):
            hashes = {digest for _, digest in values}
            errors.require(
                len(hashes) == 1,
                f"shared file drift for {template}: "
                + ", ".join(f"{name}={digest[:12]}" for name, digest in values),
            )


def _run_help(command: list[str], cwd: Path) -> tuple[int, str]:
    environment = os.environ.copy()
    environment.pop("VIRTUAL_ENV", None)
    try:
        completed = subprocess.run(
            command,
            cwd=cwd,
            check=False,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            encoding="utf-8",
            env=environment,
            timeout=120,
        )
    except FileNotFoundError as exc:
        return 127, str(exc)
    except subprocess.TimeoutExpired as exc:
        return 124, str(exc)
    return completed.returncode, completed.stdout


def _check_help_flags(
    label: str, output: str, expected: list[str], errors: ContractErrors
) -> None:
    expected_options = {value for value in expected if value.startswith("--")} | {"--help"}
    actual_options = set(re.findall(r"(?<![\w-])--[a-z][a-z-]+", output))
    errors.require(
        actual_options == expected_options,
        f"{label}: option drift; expected {sorted(expected_options)!r}, "
        f"got {sorted(actual_options)!r}",
    )
    for positional in (value for value in expected if not value.startswith("--")):
        errors.require(positional in output, f"{label}: --help missing positional {positional}")


def _check_cli_help(manifest: dict[str, Any], errors: ContractErrors) -> None:
    for analyzer in manifest["analyzers"]:
        directory = ROOT / analyzer["directory"]
        for command, flags in analyzer["cli_flags"].items():
            code, output = _run_help(["uv", "run", "--frozen", command, "--help"], directory)
            errors.require(code == 0, f"{analyzer['directory']}/{command}: --help exited {code}")
            _check_help_flags(f"{analyzer['directory']}/{command}", output, flags, errors)
        code, output = _run_help(
            ["uv", "run", "--frozen", "python", "scripts/finalize_guidance.py", "--help"],
            directory,
        )
        errors.require(code == 0, f"{analyzer['directory']}/finalizer: --help exited {code}")
        _check_help_flags(
            f"{analyzer['directory']}/finalizer",
            output,
            manifest["finalizer_flags"],
            errors,
        )


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", type=Path, default=DEFAULT_MANIFEST)
    parser.add_argument("--check-cli-help", action="store_true")
    args = parser.parse_args()

    if yaml is None:
        return _rerun_with_pyyaml()

    try:
        manifest = json.loads(args.manifest.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        print(f"contract manifest error: {exc}", file=sys.stderr)
        return 2

    errors = ContractErrors()
    errors.require(manifest.get("schema_version") == "1.0", "unsupported manifest schema")
    for relative in manifest.get("required_root_files", []):
        errors.require((ROOT / relative).exists(), f"repository: missing required {relative}")
    gitignore_lines = set(_read_text(ROOT / ".gitignore", errors).splitlines())
    for pattern in manifest.get("required_gitignore_patterns", []):
        errors.require(pattern in gitignore_lines, f"repository/.gitignore: missing {pattern}")
    for analyzer in manifest.get("analyzers", []):
        _check_analyzer(analyzer, manifest, errors)
    _check_shared_files(manifest, errors)
    if args.check_cli_help:
        _check_cli_help(manifest, errors)

    if errors.items:
        print("resume analyzer public contract drift:", file=sys.stderr)
        for item in errors.items:
            print(f"- {item}", file=sys.stderr)
        return 1
    print("resume analyzer public contracts are synchronized")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
