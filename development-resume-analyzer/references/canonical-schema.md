# Canonical development resume schema v1

The checked-in machine-readable schema is
[extracted_resume.schema.json](extracted_resume.schema.json).

```text
Resume
├── resume_id?
├── basic_info
│   ├── name / school / major / degree / graduation_year
│   └── contact? { phone?, email? }
├── internships[]
│   └── organization / name / role / duration / description / tech_stack[] / achievements[]
├── projects[]
│   ├── category?
│   └── organization / name / role / duration / description / tech_stack[] / achievements[]
└── skills
    ├── programming_languages[]
    ├── frontend_client_technologies[]
    ├── backend_technologies[]
    ├── frameworks_libraries[]
    ├── databases_storage[]
    ├── testing_quality[]
    ├── engineering_devops[]
    └── ai_tools[]
```

Project category values are `course_project`, `personal_project`, `open_source`,
`competition`, `research`, `hackathon`, `internship_project`, and `other`.

All fact fields may be omitted or `null`. Blank optional strings normalize to
`null`; missing lists normalize to `[]`. Wrong types, unknown fields, SRE-only
fields, and security-only fields fail validation.

`resume_id`, when present, must match `[A-Za-z0-9_-]{1,64}`. It is an internal
calibration identifier and never determines a visible path.

For raw documents, create a private `raw_extraction.json` with at least:

```json
{
  "content_trust": "untrusted",
  "source_sha256": "64 lowercase hexadecimal characters",
  "full_text": "complete extracted document text"
}
```

Pass that file through `--raw-extraction`; it is not canonical resume JSON.
