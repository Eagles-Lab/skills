# Security evidence model

Each dimension is divided into capability groups. Synonymous concepts collapse
within a source. A skills-list or certificate name is mention-only.

- Foundations: operating systems; network/HTTP/TLS; authentication and
  cryptography; database/storage; security principles.
- Engineering: programming; scripting/tools; testing; DevSecOps; data
  processing; security-tool audit.
- Offensive: Web vulnerabilities; code audit; penetration methodology;
  reproduction; remediation validation; CTF/CVE/bounty.
- Defense: logs/SIEM; network/endpoint detection; detection rules; incident
  response; threat hunting; forensics.
- Cloud/identity/data: IAM/secrets; cloud boundary; container/Kubernetes;
  data/privacy; risk/standards; software supply chain.
- AI security: assisted analysis; LLM attack surface; Agent permissions;
  model/data supply chain; evaluation/red team; monitoring/fallback.

Depth scale:

| Score | Requirement |
|---:|---|
| 1 | No positive evidence. |
| 2 | Skill, certificate, course, or tool mention. |
| 4 | Actual use or experiment. Unknown-scope offensive work is capped here. |
| 6 | Reproducible tool, authorized test, detection rule, or complete lab. |
| 8 | One source shows ownership, method, validation, and remediation/defense closure. |
| 9 | Same source adds a real environment or attributable result. |
| 10 | Two independent sources score at least 6 and one reaches 8. |

Applied group count caps the dimension: 0→2, 1→8, 2→9, 3+→10. Final score is
`min(depth_score, coverage_cap)`.

Negated statements, repeated keywords, instruction-like content, identity,
and explicit illegal activity are not positive evidence. Results must stay in
the same source as the action; never attribute metrics across projects.

AI-specific caps are 2 for mention, 4 for human-validated use, 6 for a runnable
security workflow, 8 for evaluation plus permission/isolation/fallback guards,
and 9 for a real same-source result.
