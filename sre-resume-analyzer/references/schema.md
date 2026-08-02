# Canonical resume schema v3

This is the sole structured input contract for Python scoring. The generated
machine-readable form is [extracted_resume.schema.json](extracted_resume.schema.json).

## Normalized shape

```text
Resume
├── resume_id?: string
├── basic_info
│   ├── name?: string | null
│   ├── school?: string | null
│   ├── major?: string | null
│   ├── degree?: string | null
│   ├── graduation_year?: integer | null
│   └── contact?
│       ├── phone?: string | null
│       └── email?: string | null
├── internships[]
│   ├── company?: string | null
│   ├── role?: string | null
│   ├── duration?: string | null
│   ├── description?: string | null
│   ├── tech_stack[]
│   └── achievements[]
├── projects[]
│   ├── name?: string | null
│   ├── role?: string | null
│   ├── duration?: string | null
│   ├── description?: string | null
│   ├── tech_stack[]
│   └── achievements[]
└── skills
    ├── programming_languages[]
    ├── monitoring_tools[]
    ├── container_tech[]
    ├── cloud_platforms[]
    ├── cicd_tools[]
    └── ai_tools[]
```

`basic_info`, `internships`, `projects`, and `skills` may be omitted and receive
empty defaults. Every factual scalar may be omitted or `null`. Blank optional
text is normalized to `null`; a missing or `null` list is normalized to `[]`.

Missing facts do not invalidate an otherwise well-formed document. The analyzer
emits structured reminders. Supplied wrong types and unknown fields remain
errors.

## Valid minimal input

```json
{}
```

Its normalized `extracted.json` contains empty objects/lists and the generated
internal `resume_id`. It still receives a complete six-dimension score at the
minimum evidence floor.

## Valid partial input

```json
{
  "basic_info": {
    "name": "张三",
    "school": null,
    "graduation_year": 2027
  },
  "projects": [
    {
      "name": "课程平台",
      "description": "实现并测试了一个容器化服务",
      "tech_stack": ["Python", "Docker"]
    }
  ],
  "skills": {
    "programming_languages": ["Python"],
    "ai_tools": ["Cursor"]
  }
}
```

Do not guess the missing education, project role, duration, or achievements.

## Internal and visible identifiers

An explicit `resume_id` must match `[A-Za-z0-9_-]{1,64}`. It remains in JSON and
calibration data but is not shown in Markdown and is not a path.

Visible output name is computed as `{safe_name}-{input_sha256[:8]}`. The safe
name uses Unicode NFKC, preserves Chinese, removes separators/control
characters and cross-platform reserved names, and has a length limit. Missing
or unusable name becomes `未知姓名`.

## Deliberately rejected v2 shapes

The following are schema errors:

- top-level `position`;
- list-valued `skills`;
- experience `technologies`;
- string `graduation_year`;
- mapping-valued `projects` or `internships`;
- any unknown field.

Do not migrate these implicitly because v3 is a breaking contract.

## Data quality warnings

Warnings contain exactly:

```json
{
  "code": "missing_basic_info_school",
  "path": "basic_info.school",
  "message": "未提供或未可靠识别，请后续补充。"
}
```

Missing scalars receive individual paths. Empty experience and skill groups are
summarized at their group paths to avoid report noise. Warnings appear in
`score.json`, `analysis.json`, and the suggestions report. They do not appear in
`extracted.json`, which contains normalized facts only.

## Canonical-only Python boundary

Platform document capabilities are responsible for reading PDF, DOCX, or
Markdown and producing this schema. The Python CLI does not infer resume facts
from those formats. `extract-resume-text` creates untrusted
`raw_extraction.json`, which is never valid canonical input.
