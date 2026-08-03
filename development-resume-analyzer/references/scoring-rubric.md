# General campus-development scoring rubric

The single profile is `cn-campus-software-development-general`, configuration
version `cn-campus-software-development-general-1.0.0`.

It targets Chinese software-development internships and campus hiring without
selecting a frontend, backend, client, full-stack, or AI track.

## Recruitment reference snapshot

Snapshot date: `2026-08-03`.

- [Tencent campus recruitment](https://careers.tencent.com/campusrecruit.html)
- [Alibaba campus recruitment](https://campus-talent.alibaba.com/)
- [Baidu campus backend development role](https://talent.baidu.com/jobs/detail/GRADUATE/72145a13-5eb1-41ce-8853-d00aa7369281)
- [ByteDance campus recruitment](https://jobs.bytedance.com/campus/page-6272Gc)

These sources motivate coverage of fundamentals, programming, architecture,
problem solving, delivery, collaboration, and AI-era development. The weights
below are analyzer product decisions, not employer scoring standards.

## Fixed weights

| Key | Dimension | Weight |
| --- | --- | ---: |
| `computer_science_software_foundation` | Computer science and software foundation | 20% |
| `programming_code_quality` | Programming implementation and code quality | 20% |
| `application_development_architecture` | Application development and architecture | 15% |
| `debugging_performance_problem_solving` | Debugging, performance, and problem solving | 15% |
| `engineering_delivery_collaboration` | Engineering delivery and collaboration | 15% |
| `ai_assisted_development_ai_engineering` | AI-assisted development and AI application engineering | 15% |

Calculate all six dimensions, multiply by the fixed weights, sum, and round only
the final score to one decimal. Keep the technical total in `1.0..10.0`.

Use the depth and breadth rules in [evidence-model.md](evidence-model.md).
Skills-list breadth alone cannot exceed 2 in any dimension and cannot produce a
B overall grade.

## Overall evidence grade

| Score | Grade | Meaning |
| ---: | --- | --- |
| 9.5–10.0 | A+ | Exceptional documented evidence coverage |
| 8.5–9.4 | A | Very strong documented evidence coverage |
| 7.0–8.4 | B | Good documented evidence coverage |
| 5.5–6.9 | C | Moderate documented evidence coverage |
| 4.0–5.4 | D | Limited documented evidence coverage |
| 1.0–3.9 | F | Insufficient documented evidence |

The grade is not an employer-fit judgment and must not be used for ranking or
hiring decisions.

## Resume-quality diagnostic

Score each item `0..2`, clamp the sum to `1..10`, and keep weight 0:

- factual and project completeness;
- personal contribution and responsibility boundary;
- technical detail and trade-offs;
- validation and results;
- clarity and internal consistency.

Do not create technical evidence from quality prose.

## Calibration contract

Released score files state `calibration_status: "not_calibrated"`. Future
calibration uses 40–60 private, de-identified campus-development resumes and two
independent developer reviewers. Require weighted agreement ≥0.70,
tool-to-human Spearman ≥0.75, median absolute error ≤1.0, and grade agreement
≥80%. Passing a local report does not silently change the released status.
