# General campus-security scoring rubric

The single scoring profile is `cn-campus-security-general`, configuration
version `cn-campus-security-general-1.0.1`. It is designed for Chinese security
internships and campus hiring; it does not select or infer a job track.

The product taxonomy is informed by the [NIST NICE Framework
2.2.0](https://www.nist.gov/itl/applied-cybersecurity/nice/nice-framework-resource-center/nice-framework-current-versions),
[NIST CSF 2.0](https://www.nist.gov/news-events/news/2024/02/nist-releases-version-20-landmark-cybersecurity-framework),
[OWASP ASVS 5.0](https://owasp.org/www-project-application-security-verification-standard/),
[MITRE ATT&CK](https://attack.mitre.org/tactics/), and [OWASP LLM Top 10
2025](https://genai.owasp.org/download/43299/?tmstv=1731900559).

The 2026-08-03 hiring-demand snapshot also reviewed:

- [QIANXIN technical security roles](https://research.qianxin.com/recruitment),
  which emphasize computer/network foundations, protocols, programming,
  security research, prototypes, reverse engineering, and AI;
- [360 security engineering and internship roles](https://src.360.cn/News/news/id/371),
  which cover vulnerabilities, Linux/logs, programming, detection, response,
  cloud-native security, automation, and AI-assisted operations;
- [Sangfor security-service capability baseline](https://www.sangfor.com.cn/security-service/safety-training-service/t2-training),
  which covers assessment, penetration testing, incident response, delivery,
  and AI/SOAR-enabled services;
- [NSFOCUS 2026 campus job families](https://career.hebut.edu.cn/home/correcruit/content/id/75397.html),
  which span research, development, assessment, application security,
  offensive security, operations, and service roles.

These sources guide capability coverage only. The weights are analyzer product
decisions, not a statistical job-posting frequency, employer standard,
framework mapping, hiring conclusion, or calibrated model.

| Dimension | Weight |
|---|---:|
| Systems, network, and security foundations | 20% |
| Programming, security engineering, and automation | 20% |
| Vulnerability research and security assessment | 15% |
| Detection, defense, and incident response | 20% |
| Cloud, identity, data, and supply-chain security | 15% |
| AI-assisted security and AI-system security | 10% |

Resume quality has weight zero. It diagnoses personal contribution,
authorization, method, verification/remediation, and internal consistency.

Administrative proximity is not authorization: managing or visiting a lab,
using its equipment or rooms, CTF registration/judging/photography, and
bug-bounty operations do not lift the offensive-evidence cap. Forged, fake,
invalid, not-yet-effective, expired, revoked, unclear-scope, or target-excluded
authorization denies the whole record even when an earlier statement is
positive.
Treat a discovered authorization-control or scope vulnerability as a tested
system defect, not as evidence that the candidate lacked testing permission.
Generic issue/risk wording, or continued testing after noticing unclear
permission, does not qualify for that finding exception.

All outputs declare `calibration_status: not_calibrated`. The overall letter
grade is a compact evidence-coverage label only and must not rank candidates.

Private calibration CSV requires `resume_id`, `reviewer_id`, the six dimension
keys, `resume_quality`, `overall_grade`, and `notes`. Each candidate must have
exactly two different blinded reviewers. Reviewers must not see each other's
scores or analyzer results.

The calibration report measures reviewer agreement, tool-human Spearman,
median absolute error, grade agreement, and per-dimension mean absolute error.
Even when its thresholds pass, it reports the released product status as
`not_calibrated`; a separate reviewed release must change that contract.
