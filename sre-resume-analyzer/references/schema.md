# Canonical resume schema 3.0

`Resume` is the only accepted structured analyzer input. Pydantic validates it
in strict mode with unknown fields forbidden and surrounding string whitespace
removed. Empty or whitespace-only strings are rejected, including strings
inside lists. v2 input is intentionally rejected; no implicit migration
exists.

The generated machine-readable contract is
`references/extracted_resume.schema.json`.

## Top-level object

| Field | Type | Required | Rules |
|---|---|---:|---|
| `resume_id` | string or null | No | `[A-Za-z0-9_-]{1,64}` |
| `basic_info` | object | Yes | Exact `BasicInfo` shape |
| `internships` | array | Yes | May be empty; items are `Internship` |
| `projects` | array | Yes | May be empty; items are `Project` |
| `skills` | object | Yes | Exact `Skills` shape |

Reject unknown top-level fields. When `resume_id` is absent or null, let the CLI
derive a stable safe identifier from the input hash and a sanitized name slug.

## Basic information

`basic_info` requires:

| Field | Type | Constraints |
|---|---|---|
| `name` | string | 1–256 characters |
| `school` | string | 1–512 characters |
| `major` | string | 1–256 characters |
| `degree` | string | 1–128 characters |
| `graduation_year` | integer | 1900–2200 |
| `contact` | object or null | Optional |

When present, `contact` requires both:

| Field | Type | Constraints |
|---|---|---|
| `phone` | string | 1–128 characters |
| `email` | string | 1–320 characters |

Contact fields are stored for authorized reporting only. They never contribute
to scores. Omit `contact` rather than inventing or partially guessing it.

## Internships

Every `internships` item requires:

| Field | Type | Constraints |
|---|---|---|
| `company` | string | 1–512 characters |
| `role` | string | 1–256 characters |
| `duration` | string | 1–256 characters |
| `description` | string | 1–20,000 characters |
| `tech_stack` | array of strings | Required; may be empty |
| `achievements` | array of strings | Required; may be empty |

Use the exact key `role`, not v2 `position`. Use the exact key `tech_stack`, not
v2 `technologies`. Keep outcomes in the internship that explicitly states them.

## Projects

Every `projects` item requires:

| Field | Type | Constraints |
|---|---|---|
| `name` | string | 1–512 characters |
| `role` | string | 1–256 characters |
| `duration` | string | 1–256 characters |
| `description` | string | 1–20,000 characters |
| `tech_stack` | array of strings | Required; may be empty |
| `achievements` | array of strings | Required; may be empty |

Do not merge separate projects merely because they use the same technology.
Evidence identity and AI outcome attribution depend on record boundaries.

## Skills

`skills` requires five arrays, each of which may be empty:

- `programming_languages`
- `monitoring_tools`
- `container_tech`
- `cloud_platforms`
- `cicd_tools`

Reject the v2 list form of `skills`. A skill-list entry is a mention only; it
does not establish implementation, ownership, production use, or outcome.

## Minimal valid example

```json
{
  "basic_info": {
    "name": "Candidate Example",
    "school": "Example University",
    "major": "Computer Science",
    "degree": "Bachelor",
    "graduation_year": 2027
  },
  "internships": [],
  "projects": [],
  "skills": {
    "programming_languages": [],
    "monitoring_tools": [],
    "container_tech": [],
    "cloud_platforms": [],
    "cicd_tools": []
  }
}
```

## Complete example

```json
{
  "resume_id": "candidate-example-2f8a8c01",
  "basic_info": {
    "name": "Candidate Example",
    "school": "Example University",
    "major": "Computer Science",
    "degree": "Bachelor",
    "graduation_year": 2027,
    "contact": {
      "phone": "+00 000 000 000",
      "email": "candidate@example.invalid"
    }
  },
  "internships": [
    {
      "company": "Example Systems",
      "role": "SRE Intern",
      "duration": "2026-01 to 2026-04",
      "description": "Implemented service dashboards and deployment checks.",
      "tech_stack": ["Prometheus", "Grafana", "Python"],
      "achievements": ["Reduced deployment verification time by 30% in the stated workflow."]
    }
  ],
  "projects": [
    {
      "name": "Local Kubernetes Reliability Lab",
      "role": "Project owner",
      "duration": "2025-09 to 2025-12",
      "description": "Built and tested monitoring and rollback paths in a local lab.",
      "tech_stack": ["Kubernetes", "Helm", "Prometheus"],
      "achievements": ["Documented three injected failure scenarios and recovery checks."]
    }
  ],
  "skills": {
    "programming_languages": ["Python"],
    "monitoring_tools": ["Prometheus", "Grafana"],
    "container_tech": ["Docker", "Kubernetes"],
    "cloud_platforms": [],
    "cicd_tools": ["GitHub Actions"]
  }
}
```

The domains use `.invalid` and fictional organizations deliberately. Do not use
real candidate data in examples or tests.

## Validation behavior

Return exit code 2 for malformed JSON, wrong types, missing required fields,
unknown fields, invalid identifiers, or v2 shapes. Report concise JSON paths,
not the full input value. A validation failure must create no final output
directory.
