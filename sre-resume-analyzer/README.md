# SRE Resume Analyzer

Experimental `3.0.0-rc.2` analyzer for domestic internship and campus-hire SRE
resume evidence. It is a review aid, not a ranking or hiring-decision system.

The Agent maps explicit facts from PDF, DOCX, Markdown, or user-supplied content
to canonical v3 JSON. Python only validates canonical JSON, scores it
deterministically with profile `cn-campus-sre`, renders reports, and atomically
publishes a model-free staging run. For the complete Skill, the current local
Codex/Claude generates cited guidance increments and the offline finalizer
validates them and atomically publishes one unified `suggestions.md` with the
report-version footer last. No model API or additional API Key is used.

## Environment

The package fixes Python at 3.13.13 through uv:

```bash
uv python install
uv sync --frozen --extra dev
```

## Canonical input

All factual fields may be missing or `null`; missing lists normalize to `[]`.
Missing data produces structured reminders and does not stop analysis. Unknown
fields, wrong supplied types, v2 fields, malformed JSON, and unsafe identifiers
fail closed.

See [schema.md](references/schema.md) and the generated
[JSON Schema](references/extracted_resume.schema.json).

## Single analysis

```bash
uv run --frozen analyze-resume \
  --extracted canonical.json \
  --raw-extraction raw_extraction.json \
  --output-dir candidate-run
```

Use `--raw-extraction` for PDF, DOCX, Markdown, and cached mappings. It rejects
high-risk omissions and selected ungrounded facts before scoring. It is a
consistency Gate, not proof that every source fact was mapped. Canonical-only
inputs may omit it when JSON is the supplied source of truth.

The complete run root must not exist unless `--overwrite` is explicit. Contact
details are excluded from Markdown unless `--include-contact` is explicit.

## Batch analysis

```bash
uv run --frozen batch-analyze \
  --input-dir canonical-resumes \
  --raw-extraction-dir raw-extractions \
  --output-dir batch-run \
  --parallel 3
```

A partial batch returns 3 and atomically publishes complete successes plus a
redacted `batch_summary.json`.

## Deterministic Python output

```text
RUN_ROOT/
├── resume_analysis/
│   └── 安全姓名-1234abcd/
│       ├── extracted.json
│       ├── score.json
│       ├── analysis.json
│       └── suggestions.md
├── interview_questions/
│   └── 安全姓名-1234abcd.md
└── batch_summary.json  # batch only
```

The whole root is built in a private sibling temporary directory and published
once. Directories use `0700`; files use `0600`.

This is the stable legacy CLI contract. Its `suggestions.md` and interview file
come from deterministic templates and remain available without a model.

## Complete Skill output

Read [local-guidance-layer.md](references/local-guidance-layer.md). After the
deterministic run, the current Codex or Claude produces private per-candidate
incremental drafts with citations to canonical facts, scores, and optionally
raw source lines. The suggestions draft contains only per-experience critique,
rewrite examples, growth advice, and its evidence index. It must not repeat the
deterministic overview or scores, change JSON, or invent experience.

Publish with:

```bash
uv run --frozen python scripts/finalize_guidance.py \
  --deterministic-run deterministic-run \
  --draft-dir guidance-drafts \
  --output-dir complete-run \
  --generator codex \
  --raw-extraction-dir raw-extractions
```

The finalizer is offline. It validates candidate membership, UTF-8, file size,
JSON Pointer and raw-line citations, exact increment headings, score
restatement, exactly ten interview questions, contact leakage, instruction-like
content, symlinks, permissions, and paths. On success, final `suggestions.md`
keeps the deterministic report body, appends `## 个性化建议增强`, and moves the
original report-version footer to the final line. It contains no visible
generator or success-mode banner. A single invalid draft uses a subtle
deterministic fallback note without changing that candidate's score.

```text
COMPLETE_RUN/
├── resume_analysis/<candidate>/
│   ├── extracted.json
│   ├── score.json
│   ├── analysis.json
│   └── suggestions.md
├── interview_questions/<candidate>.md
├── guidance_manifest.json
└── batch_summary.json
```

`guidance_manifest.json` records the requested generator, LLM/fallback counts,
sanitized per-candidate modes, source hashes, citation counts, and final artifact
SHA-256 values without storing contact details or raw excerpts. The deterministic
Markdown inputs remain private staging artifacts; only their source hashes are
carried into the final manifest.

## Scoring

The six fixed technical weights are:

- systems/network foundations: 22%;
- programming/automation: 18%;
- troubleshooting: 18%;
- cloud/distributed infrastructure: 14%;
- reliability engineering: 18%;
- AI engineering/AIOps: 10%.

Technical total is 1.0–10.0. Resume quality is a separate weight-zero diagnosis
with five explained items. There is no AI bonus or legacy monitoring/alerting
dimension contract. See [scoring-rubric.md](references/scoring-rubric.md).

Each dimension separately records evidence depth and applied capability-group
coverage. Skills-list mentions never count as applied coverage. Coverage caps
the final dimension score at 2 for zero applied groups, 8 for one, 9 for two,
and 10 for three or more. Structured missing-data warnings remain in JSON but
are temporarily omitted from Markdown reports.

## External document mapping

Use the platform's installed reader. Python does not infer resume fields from
PDF or DOCX. The local text-PDF fallback is:

```bash
uv run --frozen extract-resume-text resume.pdf --output raw_extraction.json
```

Never use raw extraction as canonical `--extracted` input. See the [PDF
workflow](references/pdf-workflow.md) and [document
workflow](references/document-workflow.md). Pass it separately through
`--raw-extraction` so the source/canonical consistency Gate runs before scoring.

## Status boundary

Human-review calibration is intentionally outside the current product scope.
There is no calibration command, reviewer workflow, dataset requirement, or
calibration Gate before analysis and publication.

The package remains `experimental` because its deterministic score describes
resume evidence coverage; it is not a validated predictor of job performance
and must not be used for candidate ranking or hiring decisions.

## Validation

```bash
uv run --frozen ruff format --check .
uv run --frozen ruff check .
uv run --frozen mypy src
uv run --frozen pytest --cov=sre_resume_analyzer --cov-fail-under=85
```

CI also enforces at least 95% coverage for schema, matching, scoring, and output
modules; Bandit, dependency audit, wheel installation, CLI E2E, Skill
validation, and Markdown links.

## Exit codes

| Code | Meaning |
|---:|---|
| 0 | Success |
| 1 | Internal error |
| 2 | Input/schema error |
| 3 | Partial batch failure |
| 4 | PDF extraction failure |
| 5 | Unsafe/conflicting output or write failure |

Read [SKILL.md](SKILL.md) for the complete agent workflow and
[privacy-and-security.md](references/privacy-and-security.md) before handling
real candidate data.
