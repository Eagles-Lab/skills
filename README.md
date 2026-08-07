# Skills

Reusable agent skills maintained in this repository.

## SRE Resume Analyzer

[`sre-resume-analyzer`](sre-resume-analyzer/README.md) is an **experimental**
v3.0 skill for evidence-based analysis of SRE, DevOps, platform engineering,
and operations resumes.

The workflow separates untrusted document extraction, deterministic analysis,
and local-model guidance:

```text
document -> agent mapping -> canonical JSON -> deterministic Python staging
         -> current Codex/Claude incremental drafts -> offline validation -> enriched run
```

The current release candidate is `3.0.0-rc.2`. It rejects v2 input and must not
be used as the sole basis for hiring decisions. Stable release requires private,
de-identified calibration and real Codex and Claude forward tests.

See the skill README for installation, commands, limits, and privacy guidance.

## Security Resume Analyzer

[`security-resume-analyzer`](security-resume-analyzer/SKILL.md) is a stable
v1.0 runtime for evidence-based analysis of domestic security internship and
campus-hire resumes. It uses one fixed `cn-campus-security-general` profile
covering foundations, engineering, assessment, defense, cloud, and AI security.

The runtime contract is stable, but scoring is not human-calibrated. Every
result declares `calibration_status: not_calibrated` and must not be used for
candidate ranking or hiring decisions.

The complete Skill adds individualized, evidence-cited suggestions and ten
interview questions through the current local Codex/Claude context. The Python
CLI remains deterministic and backward-compatible; invalid model drafts fall
back per candidate.

## Development Resume Analyzer

[`development-resume-analyzer`](development-resume-analyzer/SKILL.md) is a
stable-interface, deterministic analyzer for Chinese software-development
internship and campus-hire resumes. It uses one general profile across frontend,
backend, client, full-stack, and AI application development.

The score is explicitly `not_calibrated`: it measures documented evidence
coverage and must not be used for candidate ranking or hiring decisions. Raw
PDF, DOCX, and Markdown workflows require source-to-canonical grounding audits.

## Deterministic CLI versus complete Skill

All three Python CLIs keep their original candidate contract:
`extracted.json`, `score.json`, `analysis.json`, deterministic
`suggestions.md`, and one deterministic interview file. They do not call a
model API and do not need an API Key.

When the complete Skill runs, the current Codex or Claude instance generates
incremental guidance drafts from the original evidence and deterministic JSON.
The offline `scripts/finalize_guidance.py` in each Skill validates citations,
raw hashes and line ranges, score restatement, ten-question structure, privacy,
instruction-like content, paths, symlinks, and permissions before atomically
publishing an enriched run. Final `suggestions.md` preserves the Python report
body, appends `## 个性化建议增强`, and moves the original report-version
footer to the end. It is the only published suggestions report: deterministic
Markdown stays in private staging, while its hashes remain in the manifest.
Successful Markdown does not display the generator or a mode banner. The
manifest records per-candidate modes, and the finalizer never modifies scores.
