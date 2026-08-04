# Cross-format candidate deduplication

Deduplication runs before scoring and workers.

High-confidence identity is either:

1. exact normalized email or phone; or
2. when both records lack contact identifiers, exact normalized name, school,
   major, and graduation year plus canonical similarity at least 0.80.

Name equality alone never merges. Different supplied contacts block the
metadata fallback.

For each group, select the canonical with highest fact coverage. Break ties by
source SHA-256 lexical order. Secondary records fill missing facts and confirm
equal facts. Duplicate experiences use organization, name, and duration as the
key.

Keep a primary description when another description conflicts. Record a
structured `kept_primary` conflict; never concatenate and double-score it.

Conflicting identity fields fail that candidate for manual confirmation.
Other candidates continue.

The visible suffix is the first eight characters of SHA-256 over the sorted,
concatenated full source hashes. This keeps cross-format reruns deterministic.

`batch_summary.json` reports raw file count, unique candidate count,
deduplicated source count, conflict failure count, successes, and failures.
