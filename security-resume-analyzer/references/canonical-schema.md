# Canonical security resume schema v1

The authoritative machine contract is
[`extracted_resume.schema.json`](extracted_resume.schema.json), generated from
`security_resume_analyzer.models.Resume`.

Top-level `extra` fields and wrong types are rejected. Optional scalar text is
normalized from blank to `null`; `null` collections normalize to empty
collections.

```text
Resume
├── resume_id?
├── basic_info
├── internships[]
├── projects[]
├── security_activities[]
│   ├── category?
│   ├── environment?
│   ├── organization / name / role / duration?
│   ├── description?
│   ├── tech_stack[]
│   └── achievements[]
└── skills
    ├── programming_languages[]
    ├── systems_networking[]
    ├── appsec_offensive[]
    ├── defense_ir[]
    ├── cloud_identity_data[]
    ├── security_engineering_tools[]
    ├── ai_security[]
    └── governance_standards[]
```

`category` values: `ctf`, `lab`, `vulnerability_disclosure`, `bug_bounty`,
`authorized_testing`, `open_source`, `security_competition`, `certification`,
`paper`, and `other`.

`environment` values: `lab`, `ctf`, `bug_bounty`, `authorized`,
`production_defense`, `academic`, `open_source`, and `unknown`.

Use `unknown` when the source does not establish scope. Do not infer
authorization from a tool name, target name, or successful exploit.

`resume_id`, when present, must match `[A-Za-z0-9_-]{1,64}`. It is internal;
visible paths are based on the sanitized name and source hashes.
