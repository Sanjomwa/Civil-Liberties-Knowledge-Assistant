# ADR-0003: Provenance and Lifecycle Metadata for Supersession and Corpus-Version Drift

**Status:** Accepted, 2026-07-11.

## Context

Two gaps from the architecture review, both the same class of problem: the
metadata schema records source facts (title, org, extraction method) but
has no field for editorial/version provenance.

**Gap A — no supersession policy.** The architecture has two hard
invariants: `data/raw/` is immutable (never modified after download), and
document IDs are permanent (`{org}-{country_iso2}-{year}-{slug}`, once
assigned, never changed, all downstream artifacts reference it). Real
human-rights reports do get retracted or reissued with corrections — an
org might republish a shutdown report with corrected casualty figures.
Nothing in the architecture handles this without breaking one of the two
invariants above.

**Gap B — `CORPUS_VERSION` isn't tied to derived artifacts.** Documents
already carry a `declared.corpus_version` field. `data/chunks/` doesn't. If
the corpus is updated to a new `CORPUS_VERSION` later without re-chunking
every document, nothing detects that existing chunks are now stale
relative to the documents they came from.

Combined into one ADR because both are the same kind of fix — schema
additions for provenance/lineage, both backward-compatible with sane
defaults, neither touches raw files or existing IDs, neither needs new
infrastructure. Splitting them would restate the same invariant reasoning
(why IDs stay permanent, why raw stays immutable) twice for no benefit.

## Decision

### Supersession (Gap A)

Model supersession as **a new, ordinary document with a pointer** —
never an edit to an existing one.

- A corrected or reissued report gets a normal new `doc_id`
  (`ooni-ke-2024-election-report` alongside the original
  `ooni-ke-2023-election-report`). Distinct download, distinct raw file,
  distinct checksum. No existing ID moves. No raw file is touched.
- A new `lifecycle` block is added to the metadata schema (a third
  category alongside `declared` and `derived`, since this is an editorial
  relationship, not a source fact or an extraction fact):
  ```json
  "lifecycle": {
    "status": "active",
    "superseded_by": null,
    "supersedes": null,
    "reason": null,
    "effective_date": null
  }
  ```
  On the old document once superseded: `status: "superseded"`,
  `superseded_by: "ooni-ke-2024-election-report"`. On the new one:
  `supersedes: "ooni-ke-2023-election-report"`. `status: "retracted"` uses
  the same block with no `superseded_by`, for a report pulled outright
  rather than corrected.
- Default `status` is `"active"` — no backfill needed for documents
  processed before this ADR, once implementation exists.
- **Chunks and embeddings of a superseded document are not deleted.**
  Deleting them would break the "IDs are permanent, downstream artifacts
  stable" invariant, and destroys the audit trail this project is supposed
  to preserve. Instead, retrieval excludes `status != "active"` by default
  — a one-line filter, not a re-index. A query that explicitly wants
  historical versions can still reach them. This is a *policy* choice, not
  a technical necessity: superseded chunks continue to physically exist in
  `data/chunks/`, just excluded from default retrieval. Worth stating
  plainly so a future reader doesn't assume superseded content is gone.

### Corpus-version drift (Gap B)

Add `corpus_version` to the `chunking` metadata block, copied from
`declared.corpus_version` at the moment chunking actually runs:

```json
"chunking": {
  "strategy": "fixed_overlap",
  "chunk_size": 1500,
  "chunk_step": 750,
  "total_chunks": 24,
  "chunking_date": "2025-06-15",
  "corpus_version": "v1.0"
}
```

Drift becomes a trivial check: for each document, assert
`chunking.corpus_version == declared.corpus_version`. Any mismatch means
that document's chunks are stale relative to a corpus update and should be
regenerated. This is intentionally detection, not automatic prevention or
regeneration — a small standalone script (`check_drift.py`, run before
freezing an evaluation) is enough for a project at this scale. No
orchestration framework, consistent with the architecture's existing
"sequential and simple" principle.

## Consequences

- Metadata schema gains one new top-level block (`lifecycle`) and one new
  field (`chunking.corpus_version`). Both are additive with safe defaults
  — no existing planned behavior changes.
- Retrieval logic (once it exists, later module) needs to know to filter on
  `lifecycle.status`. Noted here so it isn't rediscovered as a surprise
  when the retrieval layer is actually built.
- A superseded document's raw file and chunks remain on disk permanently —
  a storage cost, not a correctness problem, and consistent with the
  project's evidentiary/audit-trail purpose.
- This ADR implies two small follow-up utilities: `check_drift.py`
  (alongside `chunk.py`) and the retrieval-time `lifecycle.status` filter
  (alongside the retrieval layer). **Build status for both is tracked in
  `docs/PROJECT_CONTINUITY.md` Section 7, not here** — this ADR is a historical
  record of the decision and won't be edited later to reflect whether
  they've since been built. A "not built yet" claim written here would go
  stale the moment either one ships, since nothing re-visits ADRs after
  acceptance.
- Document version increments 1.2 → 1.3.
- The metadata JSON's own `schema_version` field increments 1.0 → 1.1,
  since the shape of a metadata record genuinely changed (new `lifecycle`
  block, new `chunking.corpus_version` field). Caught and fixed during the
  post-review documentation consistency pass (2026-07-11), not in the
  original edit — worth noting so the same miss doesn't repeat: a schema
  version and a document version are different things, and changing one
  doesn't automatically prompt updating the other.

## Opus consult

Consulted 2026-07-11. Recommended exactly this shape — new-document-plus-
pointer for supersession rather than any form of in-place edit or
versioned ID, retrieval-time filtering over deletion or re-indexing, and a
single combined ADR rather than two. Adopted directly; no divergence
between the consult and the primary reviewer's read this time.

## What would trigger a revisit

If a future need arises to reconstruct exactly what the corpus looked like
at a past point in time (not just "what's currently active"), the
retrieval-filter approach here would need to grow into something more
structured (e.g., a real versioned snapshot mechanism). Not needed at this
project's current scale — revisit only if that requirement actually shows
up.
