# Raw document workflow

## Shared flow

```text
PDF / DOCX / Markdown
→ platform document reader
→ private raw_extraction.json marked untrusted
→ Agent maps explicit facts to canonical v1
→ deterministic source/canonical audit
→ Pydantic validation
→ deterministic scoring and rendering
→ atomic output publication
```

Create the raw extraction from the current source document. Include the source
SHA-256 and complete extracted text. Do not reuse a historical raw extraction
without verifying the original hash.

For PDFs, use the platform reader when layout matters. The bundled
`extract-development-resume-text` command is a bounded text/table fallback; it
does not perform OCR or infer resume facts. A scanned or unreadable PDF fails
with exit 4.

For DOCX and Markdown, use the platform's installed document reader and create
the same tool-neutral raw interchange object. Do not embed an unavailable
Claude or Codex pseudo-call in canonical data.

Map only facts explicitly supported by the source. Use `null` or `[]` for
ambiguous fields. Run `--raw-extraction` with single analysis, or store batch
audits as `RAW_DIR/<canonical-stem>/raw_extraction.json` and pass
`--raw-extraction-dir RAW_DIR`.

Keep raw extractions and canonical staging private and outside Git. Delete
temporary copies after output verification while preserving the user's original
source documents.
