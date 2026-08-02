# Source mapping audit

Run this deterministic Gate after the Agent maps an external document and
before scoring. It detects selected contradictions and high-risk omissions; it
does not infer, repair, or prove completeness of resume facts.

## Raw evidence contract

Use `extract-resume-text` for PDF. For DOCX or Markdown, the platform reader
must create a private `raw_extraction.json` containing at least:

```json
{
  "content_trust": "untrusted",
  "source_sha256": "64 lowercase or uppercase hexadecimal characters",
  "full_text": "complete extracted text in reading order"
}
```

The raw file must be regular, non-symlink, no larger than 25 MiB, and retained
only until final output validation. Do not print `full_text` or `source_name`.

## Single-document Gate

```bash
uv run --frozen analyze-resume \
  --extracted canonical.json \
  --raw-extraction raw_extraction.json \
  --output-dir run-root
```

The Gate fails with exit code 2 and creates no output when, for example:

- raw text has a project section but canonical `projects` is empty;
- raw text has an internship/work section but canonical `internships` is empty;
- a supplied name, school, major, degree, graduation year, project name, or
  internship company is not grounded in raw text;
- the school field contains degree text such as `本科` or `硕士`;
- a canonical skill or experience technology is not an independent raw-text
  term. Latin boundaries ensure `MongoDB` does not ground `Go` and `MySQL`
  does not ground standalone `SQL`.

Missing contact remains a warning because contact is optional and never
affects scoring. A passed audit records its version, raw source SHA-256, and
privacy-safe warning codes in `score.json`.

## Batch Gate

Use this layout:

```text
canonical-resumes/
└── candidate-001.json
raw-extractions/
└── candidate-001/
    └── raw_extraction.json
```

Then run `batch-analyze --raw-extraction-dir raw-extractions`. A missing or
failed audit becomes a redacted per-item failure; valid items still publish
atomically and the command returns 3.

## Cache and reuse

Raw source hash equality or text similarity identifies a document, not mapping
quality. Reused canonical data must pass the current audit version against the
current raw evidence. Never copy an old canonical directly into scoring merely
because similarity is 100%.
