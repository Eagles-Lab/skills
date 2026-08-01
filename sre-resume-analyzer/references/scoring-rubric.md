# Scoring rubric 3.0

This rubric measures evidence present in a resume. It does not measure actual
job performance, verify truth, or produce a hiring decision.

## Base dimensions

| Key | Label | Weight |
|---|---|---:|
| `monitoring` | Monitoring experience | 20% |
| `alerting` | Alerting design | 15% |
| `automation` | Automation | 20% |
| `containerization` | Containers and cloud native | 15% |
| `incident_handling` | Incident handling | 15% |
| `resume_quality` | Resume evidence quality | 15% |

Compute all unrounded dimension values first:

```text
base = monitoring*0.20
     + alerting*0.15
     + automation*0.20
     + containerization*0.15
     + incident_handling*0.15
     + resume_quality*0.15

total = base + ai_bonus
```

Clamp the base to 1.0–10.0, AI bonus to 0.0–1.5, and total to 1.0–11.5.
Round persisted summary scores to one decimal only after the weighted sum. Do
not round weighted components before summation.

## Technical dimension scores

Start from the strongest supported evidence level in that dimension:

| Strongest supported evidence | Initial score |
|---|---:|
| No positive evidence | 1 |
| Mention only | 2 |
| Actual usage | 4 |
| Implementation or deployment | 6 |
| Ownership or design | 8 |
| Production responsibility or attributable outcome | 9 |

Apply these constraints:

- Require at least two independent sources to exceed 6.
- Require at least one ownership, production, or outcome record to exceed 8.
- Add one point, capped at 10, when two different project or internship records
  each contain implementation-level or stronger evidence.
- Count one normalized concept once per source.
- Give no positive evidence for a negated statement.
- Cap weak learning language at mention.
- Do not convert a skill-list keyword directly into implementation evidence.

Use the configured scoring criteria to classify evidence and explain the result.
Do not treat a criteria file as unused documentation.

### Dimension guidance

`monitoring` rewards implementation of metrics, logs, traces, dashboards,
SLI/SLO, or observability systems. A tool name alone is a mention. Production
scale, custom instrumentation, or demonstrated coverage may support a stronger
level when explicitly stated.

`alerting` rewards rule design, severity, routing, deduplication, escalation,
on-call operation, and executable runbooks. Receiving notifications alone is
usage, not alert-system ownership.

`automation` rewards implemented scripts, CI/CD, infrastructure as code, and
repeatable operational workflows. Listing a programming language is a mention;
an implemented pipeline or platform with scope is stronger.

`containerization` rewards building, deploying, and operating containers,
Kubernetes, and cloud-native platforms. Course or local lab work is valid but
must not be labeled production experience.

`incident_handling` rewards detection, diagnosis, mitigation, recovery,
root-cause analysis, postmortems, drills, and verified corrective actions.
Generic troubleshooting without an incident context is usage-level evidence.

## Resume quality

Score five criteria from 0 to 2, sum them, then clamp the dimension to 1–10:

| Criterion | 0 | 1 | 2 |
|---|---|---|---|
| Completeness | Required sections provide little usable content | Some fields or records are thin | Core information and experience records are usable |
| Action/STAR | No personal action | Action is present but context or result is weak | Context, responsibility, action, and result are clear |
| Quantification | No useful outcomes | Numbers lack comparison or attribution | Same-record, attributable outcome with scope or comparison |
| Clarity | Repetitive or vague wording dominates | Mostly understandable with gaps | Concise, specific, and internally consistent wording |
| Timeline/technical consistency | Contradictions or unusable chronology | Minor ambiguity | Dates, role, technology, and claims align |

Do not score visual design, font choice, photograph, school prestige, employer
prestige, or contact completeness. Canonical JSON cannot reliably preserve PDF
visual design.

## AI bonus

Recognize these application categories only in project or internship evidence:

- `llm`
- `ai_agents`
- `ai_ide`
- `ml_ops`
- `aiops`

Award:

| Evidence | Bonus |
|---|---:|
| Mention only or no applied category | 0.0 |
| One category with usage-or-stronger evidence | 0.5 |
| Two distinct categories with usage-or-stronger evidence | 1.0 |
| Three distinct categories, with at least one same-source attributable quantified outcome | 1.5 |

Do not award a bonus for listing Cursor, Copilot, an LLM, or another AI tool in
the skills object. Do not attach a quantified result from an unrelated record to
an AI application. Persist the collection under `applications`, never the old
`categories` field.

## Grades

Assign grade after adding AI bonus:

| Total | Grade | Meaning |
|---:|:---:|---|
| 9.5–11.5 | A+ | Very high documented evidence coverage |
| 8.5–9.4 | A | High documented evidence coverage |
| 7.0–8.4 | B | Good documented evidence coverage |
| 5.5–6.9 | C | Partial documented evidence coverage |
| 4.0–5.4 | D | Limited documented evidence coverage |
| 1.0–3.9 | F | Minimal documented evidence coverage |

Use the exact phrase "evidence coverage" in reports. Do not translate a grade
into "hire", "reject", "ready for production", or an unsupported percentile.

## Calibration gate

Stable release requires 40–60 de-identified resumes independently reviewed by
two SRE reviewers. Reviewers must not see one another's scores or analyzer
results until their reviews are locked.

The review CSV contains:

```text
resume_id,reviewer_id,monitoring,alerting,automation,containerization,
incident_handling,resume_quality,ai_bonus,overall_grade,notes
```

Run:

```bash
calibrate-scoring \
  --resumes ./calibration-private/resumes \
  --reviews ./calibration-private/reviews.csv \
  --output-dir ./calibration-private/report
```

For a scoring-rule experiment, pass `--baseline-config OLD` and
`--candidate-config NEW`. Score with the candidate and include a stable nested
configuration diff in the report. Prefer a calibration set with at least 10
resumes whose canonical JSON was produced from PDF inputs.

The validator keeps the six dimension weights and grade boundaries fixed.
Calibration candidates may change matching aliases or evidence-strength rules,
but cannot move those contractual weights or boundaries.

Write `calibration_report.json` and `calibration_report.md` atomically. Refuse
existing reports unless `--overwrite` is explicit. Exit 1 when valid inputs do
not meet the thresholds, 2 for invalid inputs, and 5 for unsafe or conflicting
output.

Require all gates:

- reviewer weighted kappa at least 0.70;
- analyzer versus mean human total Spearman correlation at least 0.75;
- total-score median absolute error at most 1.0;
- exact grade agreement at least 80%;
- semantically equivalent Chinese and English fixture difference at most 0.5;
- negated evidence dimension score at most 4;
- keyword-spam fixture grade below B.

Generate aggregate agreement metrics, dimension errors, a grade confusion
matrix, language/type slices, and a sanitized report. Keep raw resumes, reviews,
per-candidate evidence, and notes outside version control.

If any metric or required platform forward test is absent or fails, retain the
`experimental` status. Never change expected results merely to make the current
implementation pass.
