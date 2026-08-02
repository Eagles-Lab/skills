# Three-track campus security scoring rubric

This product taxonomy is informed by the [NIST NICE Framework
2.2.0](https://www.nist.gov/itl/applied-cybersecurity/nice/nice-framework-resource-center/nice-framework-current-versions),
[NIST CSF 2.0](https://www.nist.gov/news-events/news/2024/02/nist-releases-version-20-landmark-cybersecurity-framework),
[OWASP ASVS 5.0](https://owasp.org/www-project-application-security-verification-standard/),
[MITRE ATT&CK](https://attack.mitre.org/tactics/), and [OWASP LLM Top 10
2025](https://genai.owasp.org/download/43299/?tmstv=1731900559). Reference
snapshot: 2026-08-02.

The dimensions and weights are analyzer product decisions. They are not a
framework mapping, employer standard, hiring conclusion, or calibrated model.

| Dimension | AppSec/offensive | Defense/IR | Security engineering/cloud |
|---|---:|---:|---:|
| Systems, network, security foundations | 20% | 20% | 20% |
| Programming, security engineering, automation | 15% | 15% | 25% |
| Application security and offensive practice | 30% | 10% | 10% |
| Detection, defense, incident response | 10% | 30% | 10% |
| Cloud, identity, data, supply chain | 15% | 15% | 25% |
| AI-assisted security and AI-system security | 10% | 10% | 10% |

Track selection changes weights only. Evidence matching and dimension depth do
not change between tracks.

Resume quality has weight zero. It diagnoses personal contribution,
authorization, method, verification/remediation, and internal consistency.

All outputs declare `calibration_status: not_calibrated`. The overall letter
grade is a compact evidence-coverage label only and must not rank candidates.

Private calibration CSV requires `resume_id`, `reviewer_id`, `track`, the six
dimension keys, `resume_quality`, `overall_grade`, and `notes`. Each candidate
must have exactly two different blinded reviewers using the same explicit
track. Reviewers must not see each other's scores or analyzer results.

The calibration report measures reviewer agreement, tool-human Spearman,
median absolute error, grade agreement, and per-dimension mean absolute error.
Even when its thresholds pass, it reports the released product status as
`not_calibrated`; a separate reviewed release must change that contract.
