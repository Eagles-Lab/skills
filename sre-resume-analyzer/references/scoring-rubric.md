# cn-campus-sre scoring rubric

Configuration version: `cn-campus-sre-1.1.0`
Analyzer version: `3.0.0-rc.3`
Status: `experimental`

## Technical dimensions

| Key | Dimension | Weight |
|---|---|---:|
| `systems_network_foundation` | Computer systems and networking foundations | 22% |
| `programming_automation` | Programming and automation engineering | 18% |
| `troubleshooting` | Troubleshooting and problem solving | 18% |
| `cloud_distributed_infrastructure` | Cloud infrastructure and distributed systems | 14% |
| `reliability_engineering` | Reliability engineering practice | 18% |
| `ai_engineering_aiops` | AI-assisted engineering and AIOps | 10% |

The weights are fixed and sum to 100%. Compute all six scores first, calculate
the weighted sum, clamp it to 1.0–10.0, and round only the final total to one
decimal. Resume quality is a separate weight-zero diagnostic.

## Grade boundaries

| Total | Grade | Meaning |
|---:|---|---|
| 9.5–10.0 | A+ | Exceptional documented evidence coverage. |
| 8.5–9.4 | A | Very strong documented evidence coverage. |
| 7.0–8.4 | B | Good documented evidence coverage. |
| 5.5–6.9 | C | Moderate documented evidence coverage. |
| 4.0–5.4 | D | Limited documented evidence coverage. |
| 1.0–3.9 | F | Insufficient documented evidence. |

Grades apply only to the overall evidence coverage. Individual dimensions show
the numeric score and evidence-level label, not A/B/C/D/F.

## Campus interpretation

Use the evidence levels and AI caps in [evidence-model.md](evidence-model.md).
Do not require senior ownership or production duty for a useful campus score.
A rigorous course or personal project can score 4–8 when it is runnable,
personally attributable, troubleshot, and validated.

Pure skill-list keyword stacking remains near level 2 and must not reach B.
Negated evidence contributes nothing.

## Evidence-group coverage

Each dimension first computes its evidence depth, then counts distinct
capability groups with actual-use evidence from a project or internship.
Skills-list mentions are visible as covered concepts but do not count as
applied groups. Synonymous tools in the same capability group count once.

Applied-group coverage caps the final dimension score:

| Applied groups | Maximum dimension score |
|---:|---:|
| 0 | 2 |
| 1 | 8 |
| 2 | 9 |
| 3 or more | 10 |

The final dimension score is `min(depth_score, coverage_cap)`. This preserves a
complete single student project at level 8, requires broader applied evidence
for level 9, and requires at least three groups plus the existing independent
source rule for level 10. Breadth never upgrades weak evidence depth.

## Tencent reference snapshot

Snapshot date: **2026-08-02**.

The profile was informed by Tencent's official [campus recruitment
portal](https://careers.tencent.com/campusrecruit.html) and the official
[Tencent Careers job search](https://careers.tencent.com/search.html). Tencent
also identifies `join.qq.com` as its permanent China campus-recruiting domain
in its official careers FAQ.

These links establish the domestic campus/internship audience and provide a
review point for role language. Dynamic job listings can change or disappear.
The six dimensions are this analyzer's documented competency interpretation,
not a quotation of a currently open Tencent role, a promise that Tencent uses
these weights, or a conclusion about present hiring.

AI receives 10% even if a particular public job description has not yet added
equivalent language. This is an explicit forward-looking analyzer design
choice, not an empirical claim about present hiring criteria.

## score.json contract

The public score artifact includes:

- `schema_version`;
- `analyzer_version` and experimental status;
- `scoring_profile: "cn-campus-sre"`;
- `scoring_config_version: "cn-campus-sre-1.1.0"`;
- internal `resume_id` and visible `output_name`;
- input SHA-256 and UTC generation time;
- for raw-document runs, passed `source_mapping_audits[]` entries with audit
  version, raw and canonical-fact SHA-256, checked count, and privacy-safe
  warning codes;
- six `dimension_scores` with evidence, depth score, evidence-group scores,
  applied coverage, missing groups, and coverage cap;
- weight-zero `resume_quality` with breakdown and findings;
- `data_quality_warnings` and sanitized security warnings;
- `total_score` and overall `grade`.

There is no `base_score`, `ai_bonus`, legacy dimension, or per-dimension grade.

## Validation boundary

Human-review calibration is not implemented or required in the current scope.
Do not describe these scores as benchmarked accuracy, predicted performance,
percentiles, or hiring recommendations. Keep `experimental` until maintainers
explicitly adopt a different evidence-backed product status.

Validate deterministic behavior directly: schema rejection, source grounding,
Chinese and English matching, negation, coverage caps, security controls,
atomic publication, and raw-document forward tests.
