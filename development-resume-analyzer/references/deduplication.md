# Source identity and candidate deduplication

Audit and validate every source before grouping. Represent each source as a
record containing `canonical_sha256`, `source_sha256`,
`source_identity_kind`, canonical resume, and audit metadata.

For original-document runs, use the audited raw-document SHA-256 and
`raw_document_sha256`. For direct canonical runs, use the canonical file
SHA-256 and `canonical_json_sha256`. A batch uses one identity kind. Missing or
failed raw evidence never falls back to canonical identity.

## Identity edges

Connect two records only when one rule holds:

1. their raw-document hashes are exactly equal in raw mode;
2. normalized email or phone is exactly equal; or
3. both lack contacts, normalized name, school, major, and graduation year all
   match, and canonical similarity is at least `0.80`.

Canonical similarity compares only populated substantive resume values; it
excludes identity/contact fields, schema keys, empty defaults, and
`other`/`unknown` placeholders. Both records must contain substantive evidence.
Its representation preserves collection, record, and field/value-slot
association. Strong experience records align only when their complete
normalized `(organization/company, name, duration)` tuples are equal, including
every populated tuple component; weak records use full-record stable ordering.
Values may be normalized and sorted within one slot, but leaf values are never
pooled or globally sorted across records or fields.
Matching metadata alone, or the same metadata with different experience and
skill content, never creates an identity edge.

Phone normalization removes a trailing extension. A bare valid 11-digit
Chinese mobile number and one with an explicit `+86`/`0086` prefix share a
Chinese identity. Preserve every other country code in an international
namespace; matching suffixes across countries are not identity. Only a
conservatively valid email, an 8-15 digit international number, or a
non-placeholder local number with at least 10 digits can create an exact
contact edge. Bare 7-9 digit local numbers are ambiguous and invalid. Any
non-empty invalid contact still blocks metadata fallback.

Different non-empty contacts block metadata fallback. Name, `resume_id`, or
canonical hash alone is never identity. Form groups by transitive closure, then
run identity-conflict checks. Multiple distinct explicit `resume_id` values in
one group fail for manual review.

## Deterministic merge

Choose the primary by descending unique fact coverage after exact-duplicate
normalization, then source SHA-256, then canonical SHA-256. Let secondary
records fill only missing values. Internship identity requires organization
plus duration. Project identity requires name plus either organization or
duration. Once a key qualifies as strong, compare its complete normalized
`(organization/company, name, duration)` tuple. For weaker partial keys,
collapse exact duplicates only. For
conflicting descriptions, retain the primary and record `kept_primary`. Never
concatenate facts or double-score evidence.

If unmerged sparse groups would produce the same output name, fail each
affected candidate with `IdentityConflictError` and
`conflict_fields: ["insufficient_identity"]`. A candidate conflict must not
abort other valid candidates.

## Hashes and summary

Store `source_hashes` as the sorted unique source hashes. Record
`source_record_count`, `unique_source_count`, and
`deduplicated_source_count = source_record_count - 1`. Compute the candidate
aggregate as SHA-256 over the concatenated sorted unique 64-character hashes;
derive automatic identifiers, `input_sha256`, and the visible suffix from it.

Use batch summary schema `1.1`. Report raw and unique counts, successes,
failures, deduplicated sources, identity conflicts, audit count, the single
source identity kind, and privacy-safe results. Do not include names, contacts,
filenames, or excerpts in failures.
