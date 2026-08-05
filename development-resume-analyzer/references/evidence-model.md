# Development evidence model

## Evidence groups

- Foundation: data structures and algorithms; operating systems and concurrency;
  network/Web protocols; databases/storage; language runtime.
- Programming: implementation; abstraction/design; API contracts; error
  handling/reliability; maintainability/refactoring; code review/static analysis.
- Application architecture: frontend/client; backend services; data modeling;
  integration/distributed systems; security/authentication; product/user loop.
- Problem solving: decomposition; logs/debugging; root-cause analysis;
  profiling/performance; experimentation/validation; remediation/regression.
- Delivery: testing; version-control collaboration; build/CI/CD; deployment and
  environments; documentation/observability; team/open-source contribution.
- AI engineering: coding assistance; testing/debugging assistance; LLM/RAG
  applications; Agent/tool workflows; evaluation; controls/fallback.

## Depth levels

| Score | Minimum evidence |
| ---: | --- |
| 1 | No positive evidence. |
| 2 | Course, skills-list, technology, or tool mention only. |
| 4 | Actual use in an experiment, assignment, project, or internship. |
| 6 | Runnable implementation, deployment, test, or engineering tool. |
| 8 | One source has method, ownership, implementation, validation, and closure. |
| 9 | The same source has real users/scale/performance or a quantitative result. |
| 10 | Two independent sources reach 6+, and at least one reaches 8+. |

Count only non-skills evidence above mention level as an applied group. Apply
coverage caps `0→2`, `1→8`, `2→9`, `3+→10`, then compute
`min(depth_score, coverage_cap)`.

Normalize Unicode, case, whitespace, and dash variants. Match CJK terms as
normalized substrings and Latin terms with alphanumeric lookarounds. Exclude
negated claims such as `不熟悉`, `未使用`, `无经验`, `仅了解`, `学习中`, `not
familiar`, and `never used`.

Deduplicate the same concept within one source. Do not transfer a result,
ownership statement, evaluation, or safeguard from one source to another.

## AI-specific limits

- Tool or skills-list mention: 2.
- Coding, testing, debugging, or review use with human validation: 4.
- Runnable RAG, Agent, or AI development workflow: 6.
- Evaluation plus permission/security/human-review/fallback controls: 8.
- Same-source real and quantified result: 9.
- Two independent strong sources, one at 8+: 10.
