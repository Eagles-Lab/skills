# SRE Resume Analyzer

Experimental `3.0.0-rc.2` analyzer for domestic internship and campus-hire SRE
resume evidence. It is a review aid, not a ranking or hiring-decision system.

The Agent maps explicit facts from PDF, DOCX, Markdown, or user-supplied content
to canonical v3 JSON. Python only validates canonical JSON, scores it
deterministically with profile `cn-campus-sre`, renders reports, and atomically
publishes a complete run.

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
  --output-dir candidate-run
```

The complete run root must not exist unless `--overwrite` is explicit. Contact
details are excluded from Markdown unless `--include-contact` is explicit.

## Batch analysis

```bash
uv run --frozen batch-analyze \
  --input-dir canonical-resumes \
  --output-dir batch-run \
  --parallel 3
```

A partial batch returns 3 and atomically publishes complete successes plus a
redacted `batch_summary.json`.

## Output layout

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

## External document mapping

Use the platform's installed reader. Python does not infer resume fields from
PDF or DOCX. The local text-PDF fallback is:

```bash
uv run --frozen extract-resume-text resume.pdf --output raw_extraction.json
```

Never pass raw extraction directly to the analyzer. See the [PDF
workflow](references/pdf-workflow.md) and [document
workflow](references/document-workflow.md).

## Calibration

Private calibration requires 40–60 de-identified domestic campus resumes and
two independent SRE reviewers:

```bash
uv run --frozen calibrate-scoring \
  --resumes calibration-private/resumes \
  --reviews calibration-private/reviews.csv \
  --output-dir calibration-private/report
```

Until calibration thresholds and isolated Codex/Claude forward tests pass, the
package remains `experimental`.

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
| 1 | Internal error or failed calibration gate |
| 2 | Input/schema error |
| 3 | Partial batch failure |
| 4 | PDF extraction failure |
| 5 | Unsafe/conflicting output or write failure |

Read [SKILL.md](SKILL.md) for the complete agent workflow and
[privacy-and-security.md](references/privacy-and-security.md) before handling
real candidate data.
