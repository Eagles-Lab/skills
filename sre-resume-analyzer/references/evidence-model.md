# Evidence model

The analyzer scores evidence, not technology-name frequency. Keyword matching
finds candidate passages; context determines whether a passage demonstrates
mention, use, implementation, ownership, production responsibility, or outcome.

## Evidence record

Each positive record contains:

| Field | Meaning |
|---|---|
| `dimension` | One of the five technical dimensions |
| `keyword` | Canonical matched term or synonym |
| `source_kind` | `skills`, `internship`, or `project` |
| `source_id` | Stable identity of the originating field or record |
| `context` | Sanitized sentence or field text supporting the match |
| `level` | `mention`, `usage`, `implementation`, `ownership`, `production`, or `outcome` |
| `position` | Stable match offset used for ordering |
| `quantified` | Whether the same source contains a numeric outcome |

Never use `basic_info`, contact data, employer reputation, or school reputation
as technical evidence.

## Match normalization

Normalize text and configured terms consistently:

- apply Unicode NFKC normalization;
- compare Latin text case-insensitively;
- normalize common whitespace and dash variants;
- match CJK terms as normalized substrings;
- match Latin terms with explicit alphanumeric lookarounds;
- expand configured aliases such as `K8s` and `Kubernetes` to one canonical
  concept;
- preserve the original safe context for audit output.

Do not use a single `\b` expression for both Latin and CJK text. It misses
Chinese text adjacent to Latin technology names.

## Negation and weak claims

Discard a positive match when its local context expresses negation, absence, or
explicit non-use, for example:

- `不会`, `未使用`, `无经验`, `没有接触`;
- `no experience`, `not used`, `never deployed`, `unfamiliar`.

Treat weak learning language as at most a mention:

- `了解`, `熟悉概念`, `学习中`, `课程接触`;
- `basic understanding`, `learning`, `familiar with the concept`.

Negation handling must be local to the matched concept. A negation attached to
one tool must not suppress an unrelated positive statement elsewhere.

## Evidence levels

| Level | Meaning | Typical signal | Initial score ceiling |
|---|---|---|---:|
| `mention` | A name is listed without action | Skill list or isolated noun | 2 |
| `usage` | The candidate says they used it | Used, operated, queried | 4 |
| `implementation` | A concrete system or workflow was built/configured | Implemented, deployed, configured | 6 |
| `ownership` | Personal design or responsibility is explicit | Designed, led, owned, responsible for | 8 |
| `production` | Production scope or operational responsibility is explicit | Production, on-call, SLO, fleet scale | 9 |
| `outcome` | A result is quantified and attributable in the same source | Reduced latency 30%, cut MTTR from X to Y | 9 |

Choose the strongest supported level for one normalized concept in one source.
Do not promote a claim merely because it contains a high-profile keyword.

## Independence and deduplication

Deduplicate repeated matches by normalized concept and source. Repeating
`Prometheus` in one skills list, sentence, project, or internship produces one
piece of evidence for that source.

Treat project and internship records as independent only when they represent
different records. Two strong records may support the cross-source bonus. Two
sentences copied within the same record may not.

Stable-sort evidence by source order, position, canonical keyword, and level so
the same input yields the same output.

## Quantification and attribution

A number alone is not a valid outcome. Require an outcome phrase that connects
the metric to an action, scope, or before/after comparison in the same project
or internship.

Keep attribution local:

- do not attach an internship metric to a project;
- do not attach a non-AI metric to an AI application elsewhere;
- do not interpret dates, version numbers, IP addresses, counts of listed tools,
  or availability targets alone as achieved outcomes;
- do not infer that team results were solely the candidate's work.

## Dimension routing

Route evidence by its operational meaning:

- `monitoring`: metrics, logging, tracing, dashboards, SLI/SLO, observability;
- `alerting`: alert rules, routing, severity, on-call, escalation, runbooks;
- `automation`: scripts, CI/CD, infrastructure as code, automated workflows;
- `containerization`: containers, orchestration, cloud-native deployment and
  operations;
- `incident_handling`: response, diagnosis, mitigation, RCA, postmortem,
  recovery, and drills.

One passage may support multiple dimensions only when it contains distinct
concepts for each. Do not duplicate the same concept across dimensions to
inflate the base score.

`resume_quality` uses structural criteria instead of keyword evidence; see the
scoring rubric.

## Adversarial examples

These examples must not score as strong evidence:

```text
Prometheus Prometheus Prometheus
No experience with Kubernetes or Terraform.
了解 Grafana，正在学习中。
Cursor, Copilot, LLM
Built an LLM demo. Another unrelated task reduced latency by 30%.
```

These examples may qualify when the context supports them:

```text
使用 Prometheus 为课程集群实现服务指标采集并验证告警触发。
Designed the alert routing policy and owned its on-call rollout in production.
Automated a deployment check, reducing that workflow from 20 minutes to 8 minutes.
```

The analyzer evaluates only what the resume demonstrates. Missing evidence does
not prove missing ability.
