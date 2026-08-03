# Cross-format candidate deduplication

Run deduplication before scoring.

1. Normalize email with NFKC, trimming, and case-folding.
2. Normalize phone to digits and compare the stable trailing number.
3. Treat an exact normalized email or phone as high-confidence identity.
4. Without contact, require name, school, major, and graduation year to match
   and canonical similarity to be at least `0.80`.
5. Never merge on name alone. Different non-empty contacts block fallback.

Choose the primary canonical with the highest non-empty fact coverage; break
ties by SHA-256 lexical order. Fill only missing facts from secondary sources.
Merge experiences by organization, name, and duration. Remove exact duplicate
experiences before scoring.

Fail conflicting identity fields for manual confirmation. For other conflicting
descriptions, keep the primary value and record `kept_primary`; do not concatenate
both versions or double count evidence.

Derive the visible output suffix from SHA-256 over all sorted source hashes.
Report raw files, unique candidates, deduplicated sources, conflict failures,
successes, and failures without logging names or contact information.
