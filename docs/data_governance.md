# Data Governance — Civil Liberties Knowledge Assistant

Policy, not implementation. States what is and isn't allowed to happen with
data in this project. Once ingestion code exists, it should enforce these
rules programmatically where feasible (e.g., source allowlist checks in
`acquire.py`) — until then, this is the standard any implementation must be
reviewed against.

Last updated: 2026-07-11. Status: policy drafted pre-implementation: no
code exists yet to enforce it (see `PROJECT_CONTINUITY.md` Section 6).

---

## 1. Sourcing restrictions

Data may only be acquired from the organizations named in the frozen
architecture's v1 source scope: OONI, Access Now, CIPESA, Freedom House.
Netblocks and Citizen Lab are deferred to v1.1 and are not in scope until
that version is explicitly opened. (Note: "v1"/"v1.1" here is the
architecture's own corpus-scope versioning, unrelated to the document's own
revision version — now v1.4 after four ADRs. Two separate axes; see
`PROJECT_CONTINUITY.md` Section 1 if this is confusing.)

**Licensing per source is reviewed in `licensing.md`** (added 2026-07-11,
resolving architecture-review item #1). Summary: OONI (CC BY-NC-SA 4.0,
non-commercial only), CIPESA (CC BY 4.0, low risk), Access Now (CC BY 4.0
for site media, report text not explicitly confirmed the same way — treat
conservatively), Freedom House (permission-gated, not CC-licensed — fine
for non-commercial course use now, but **requires an explicit written
permission request before any CLIO-facing redistribution phase**). See
`licensing.md` for full detail and action items.

No other source may be added without an ADR. This is deliberate — the
architecture's credibility depends on a known, auditable source list, not
an open-ended crawl.

**Explicitly prohibited, regardless of source:**
- Scraping or ingesting individual activists', journalists', or private
  citizens' personal social media accounts, even if referenced by one of
  the approved orgs' reports.
- Any live/real-time API integration (explicitly out of scope for v1 per
  the architecture — OONI's live API is deferred).
- OCR or any pipeline stage not already defined in the frozen architecture,
  without an ADR first.

## 2. Retention and deletion

- Acquired source documents are retained under their original org's license
  terms (to be recorded per-source in `PROJECT_CONTINUITY.md` Section 4 once
  acquisition begins).
- If a source organization issues a retraction, correction, or takedown
  request for content already ingested, that content must be removed from
  the corpus and the removal logged (date, source, reason) — not silently
  deleted without a record.
- No personal data beyond what the source organizations themselves have
  already published is to be retained, derived, or inferred.

## 3. Correction process

If a cited source is later found to be wrong, outdated, or superseded, the
mechanism is now concrete (`docs/adr/0003-provenance-lifecycle-metadata.md`,
added 2026-07-11 — this section originally left the mechanism as "TBD,"
resolved by that ADR):
1. The corrected or retracted document gets its own new `doc_id` — never an
   edit to the original. The original's metadata gets a `lifecycle` block:
   `status: "superseded"` (or `"retracted"` if pulled outright, no
   replacement), `superseded_by` pointing to the new `doc_id`, `reason`,
   `effective_date`. Nothing is silently edited or deleted.
2. This *is* the log — the `lifecycle` block on the affected document's own
   metadata record, not a separate corrections file. `docs/adr/0003...md`
   has the full schema.
3. Superseded chunks/embeddings aren't deleted (audit trail preserved) but
   are excluded from default retrieval once retrieval exists — a policy
   decision, not a technical necessity, documented in the same ADR.
4. If the assistant has already been used to answer questions based on the
   now-superseded data, that's a signal to re-run affected evaluations, not
   just patch the source silently.

## 4. Publication constraint

No public output of this project — a chat answer, a demo, or a
build-in-public post — may assert a country's censorship or digital-rights
status as verified fact from partial-corpus results. This mirrors the
architecture's own internal requirement (cite sources, flag thin/
contradictory evidence) applied to everything public-facing, not just
in-system answers.

## 5. Review cadence

This document should be reviewed (not necessarily changed) at two points:
before `acquire.py` is implemented (does the policy still match the actual
sources being integrated), and before any v1.1 scope expansion (Netblocks,
Citizen Lab) is opened. Both reviews go through this project's mandatory
independent advisor-model checkpoint before being finalized.
