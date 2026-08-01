# Skills

Reusable agent skills maintained in this repository.

## SRE Resume Analyzer

[`sre-resume-analyzer`](sre-resume-analyzer/README.md) is an **experimental**
v3.0 skill for evidence-based analysis of SRE, DevOps, platform engineering,
and operations resumes.

The workflow separates untrusted document extraction from deterministic
analysis:

```text
PDF -> agent extraction -> canonical v3 JSON -> deterministic CLI -> five outputs
```

The current release candidate is `3.0.0-rc.1`. It rejects v2 input and must not
be used as the sole basis for hiring decisions. Stable release requires private,
de-identified calibration and real Codex and Claude forward tests.

See the skill README for installation, commands, limits, and privacy guidance.
