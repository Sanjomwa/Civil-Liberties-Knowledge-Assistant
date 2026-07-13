# Project Continuity — Civil Liberties Knowledge Assistant

Purpose: if this project goes idle for any length of time — a week, a
year — this doc should let anyone picking it up, including the original
author, resume without reconstructing context from memory or old history.
Read this file first, in full, when resuming cold.

Last updated: 2026-07-13.

---

## 1. Current state (snapshot)

**Implementation status: does not exist yet.** As of this update, the
project folder contains:
- `docs/archituecture.md.docx` — frozen architecture, now **v1.4** (amended
  2026-07-11 via ADR-0001 through ADR-0004 — see Section 5).
- `docs/ingestion-design.md` — pre-implementation pipeline reference,
  synthesizing the architecture plus all four ADRs, with a diagram.
- `docs/licensing.md` — per-organization source licensing findings.
- `docs/corpus-inclusion-rubric.md` — concrete criteria for the semantic
  review stage (topic relevance, coverage contribution).
- `docs/PROJECT_CONTINUITY.md` — this file.
- `docs/data_governance.md` — governance policy.
- `docs/adr/` — four ADRs (see Section 5), plus `README.md` (process + example
  trigger thresholds).
- `pyproject.toml` / `uv.lock` — Python dependencies declared and locked
  (129 packages, `requires-python = ">=3.10,<3.13"`). Verified 2026-07-13
  with `uv sync` against CPython 3.12.3 — clean install, no conflicts.

No `src/`, no `corpus/`, no `data/`, no notebooks — dependency scaffolding
exists, pipeline code doesn't yet. No data has been acquired. No code has
been written. The architecture document's own closing
line states the next artifact is `src/ingestion/` — implementation has not
started as of this snapshot. The full architecture review (9 items) is
complete; implementation is the next real step, not yet begun.

**Two unrelated version numbers, don't conflate them:** the architecture
document has its own revision version (`Document version`, now v1.4,
incremented once per ADR — a tracking number for the *document itself*).
Separately, the architecture's own content defines a corpus-scope version
("v1" sources: OONI/Access Now/CIPESA/Freedom House; "v1.1" deferred
addition: Netblocks/Citizen Lab — a scope milestone for the *corpus*, set
by the architecture, not by ADRs). "The architecture is at v1.4" and "the
corpus is still v1, not yet v1.1" are both true at the same time and mean
different things.

**What is decided and stable:** the architecture (now v1.4, "Approved.
Future changes via ADR only.") — scope (Kenya, Uganda, Tanzania, Ethiopia,
Rwanda; 2022–2025), sources (OONI, Access Now, CIPESA, Freedom House for
v1; Netblocks + Citizen Lab deferred to v1.1), pipeline shape (`acquire.py`
→ `extract.py` → `validate.py` → `metadata.py` → `chunk.py`), doc ID scheme
(`{org}-{country_iso2}-{year}-{slug}`), and the core acceptance principle:
every answer must cite sources, thin/contradictory evidence must be
flagged, not smoothed over. Refined by four ADRs since the original freeze:
tiered (not uniform) validation routing, a `lifecycle` metadata block for
supersession, a `corpus_version` stamp on chunks for drift detection, a
`license` field, and an explicit disclosure of the English-only corpus
limitation. See `docs/ingestion-design.md` for the synthesized picture.

## 2. How to resume from cold

1. Read this file in full.
2. Read `docs/ingestion-design.md` first for the synthesized picture, then
   `docs/archituecture.md.docx` (the actual design — now v1.4, amended
   2026-07-11 via ADR-0001 through ADR-0004) for full detail.
3. Check `docs/adr/` for any deviations recorded since the architecture was
   frozen — if it's non-empty, those changes supersede the relevant part of
   the architecture doc. As of this update, four ADRs exist:
   `0001-english-only-corpus-disclosure.md`,
   `0002-tiered-validation-routing.md`,
   `0003-provenance-lifecycle-metadata.md`,
   `0004-editorial-corrections.md`.
4. Check Section 1 of this file (once populated with real progress) against what
   actually exists on disk (`ls -R` the project folder) — if they disagree,
   trust the filesystem, fix this doc, don't assume the doc is right.

## 3. Data source re-acquisition

Not yet applicable — no data has been acquired. Once `acquire.py` exists,
this section must be populated with, per source:
- Source name and base URL.
- Access method (API, scrape, manual download).
- SHA-256 checksums of acquired files (per the architecture's reproducibility
  requirement).
- `CORPUS_VERSION` at time of acquisition.
- Any rate limits, auth requirements, or terms-of-use constraints that
  affect re-acquisition.

This section is a placeholder until ingestion exists — do not let it drift
into aspirational/present-tense language describing a pipeline that isn't
built yet. Documentation that describes a future state in the present
tense makes a system look more built than it is; that mistake is cheap to
avoid and expensive to unwind once several docs repeat it.

## 4. Attribution and licensing status

Not yet applicable — to be populated per source once acquisition begins.
Each of the five v1 sources (OONI, Access Now, CIPESA, Freedom House,
+2 deferred) has its own data licensing terms; these must be recorded here
before any content derived from them is published or redistributed.

## 5. Decision records

Two records, each authoritative for a different thing — don't duplicate
across them:
- **Architecture decisions**: `docs/adr/` — four exist as of this update
  (`0001` English-only disclosure, `0002` tiered validation routing, `0003`
  provenance/lifecycle metadata, `0004` editorial corrections). See
  `docs/adr/README.md` for format and example trigger thresholds. ADRs are
  historical and don't get edited after acceptance — they may mention that
  a follow-up is implied, but this file's Section 7 (not the ADR) is where build
  status for that follow-up actually lives.
- **Current status** (this file): the only one of the two meant to be
  edited in place as things change. If the two ever disagree, trust this
  file for "what's true now" and `docs/adr/` for "what was decided and
  why" — ADRs are frozen at acceptance and won't be revised to match later
  developments.

## 6. Known gaps as of this snapshot

- No data governance enforcement mechanism exists yet — `data_governance.md`
  states policy, but nothing in code checks compliance with it, because no
  code exists.
- This file's Section 3 and Section 4 are placeholders, not content, until ingestion
  starts.
- Generation-layer disclaimer capability (ADR-0001, item 3) is a noted
  future requirement, not built — nothing to build yet since the generation
  layer itself doesn't exist. Don't lose track of it once that layer starts.

## 6a. First implementation milestone (walking skeleton)

Defined 2026-07-11, before any code exists — the target to build against,
not a retrospective status report. Update the status line below in place
once work starts; don't let this section drift into describing a milestone
that's already passed.

**Status: in progress — acquire.py done (2026-07-13), extract.py next.**

**Definition of success:** one real document flows through the entire
pipeline — `acquire.py` → `extract.py` → `validate.py` → `metadata.py` →
`chunk.py` — via `pipeline.py` as a single command, before any work goes
into acquiring the full 40-60 document corpus. Proves the pipeline's shape
and every ADR's design actually holds together, before paying the cost of
scaling it up.

**Document choice:** one OONI or CIPESA PDF country report — not an HTML
methodology page (OONI-only, minority code path; PDF is the primary format
for all four orgs), and deliberately not a Freedom House document (its
licensing has an open action item — see Section 7 — and using it here would
tangle a technical proof-of-concept with an unresolved external
dependency).

**Checklist — all of these, not just "it ran":**
- [x] `data/raw/` has the file, checksum matches the manifest. Done
  2026-07-13 — `acquire.py` written, ran clean against
  `ooni-tz-2025-x-platform-blocking`. One real wrinkle worth keeping: OONI's
  server sustained a 429 against scripted downloads even with a proper
  User-Agent and no retry-loop abuse, so `acquire.py` now supports a
  per-document `acquisition: auto | manual` mode (Opus-consulted) —
  `manual` means fetched once by hand, script only verifies the checksum.
  This document is `manual`; `corpus/manifest.csv` and
  `corpus/checksums.sha256` generated successfully.
- `data/processed/` has non-empty, plausible extracted text.
- Tier 1 checks (extraction success, file integrity) ran and passed.
- Tier 2 checks (language, length, near-duplicate) actually ran and
  produced a report — even a clean document passing trivially still proves
  ADR-0002's routing logic executes, not just that it exists on paper.
- A human (Sam) does the semantic review for real, using
  `corpus-inclusion-rubric.md`, marks it Included, and that reasoning is
  logged in `corpus/acquisition-log.md` — proves the human-in-the-loop step
  is a real step, not silently bypassed.
- `data/metadata/{doc_id}.json` matches the amended schema (schema_version
  1.1): `declared` (including `license`, populated from `licensing.md`),
  `derived`, `lifecycle` (defaulting to `active`).
- `data/chunks/{doc_id}/*.json` exist, each carrying the `corpus_version`
  stamp from ADR-0003.
- Idempotency: rerun `acquire.py` (or the whole pipeline) on the same
  document a second time — confirm it's a no-op (skips the download,
  doesn't reprocess). Cheap to verify now, while there's only one document
  to reason about.
- A second, synthetic, deliberately-bad input (a corrupted checksum or an
  artificially short file) run through `validate.py` alone, to confirm a
  Tier 1 failure actually auto-excludes and a Tier 2 failure actually
  surfaces to the report rather than silently vanishing. Not a second real
  document — a cheap fixture built to break one specific check, since the
  branching logic (the actual point of ADR-0002) is otherwise never tested
  by a single clean document.

**Explicitly out of scope for this milestone** (don't let it creep):
the full corpus, cross-document near-duplicate detection actually firing
(nothing to compare against with one document), `check_drift.py` (only
meaningful across a corpus version change), anything retrieval/
embedding-related (already out of scope for the whole pipeline).

## 7. Open action items (don't lose track of these)

- **Freedom House permission request — sent 2026-07-13** (drafted
  2026-07-11, sent by Sam directly from Gmail — no send capability was
  available to Claude, only draft creation, so this was Sam's own action).
  Sent to `press@freedomhouse.org`, subject "Permission Request: Samwel
  Njogu Mwaniki, Civil Liberties Knowledge Assistant." Requested permission
  for one "Freedom on the Net" country chapter per target country
  (2022-2025), non-commercial use stated clearly. **Now awaiting Freedom
  House's response** — no reply yet as of this update. Per their own FAQ,
  response time isn't guaranteed ("we are unable to immediately respond to
  every permission request"). Until a reply arrives: current non-commercial
  course-project use stays low-risk per `docs/licensing.md`'s original
  analysis; the still-open constraint is no CLIO-facing redistribution of
  Freedom House content until permission is actually confirmed, not just
  requested.
- **OONI content-license variant unconfirmed.** `licensing.md` confirms
  OONI's measurement *data* is CC BY-NC-SA 4.0 but not the exact variant for
  their *content* (reports) specifically. Two-minute check before corpus
  freeze: `github.com/ooni/license/tree/master/content`.
- **`check_drift.py` not yet written.** Implied by ADR-0003 — a small
  standalone script asserting `chunking.corpus_version == declared.
  corpus_version` per document. Write it alongside `chunk.py`, not before.
- **Retrieval-time `lifecycle.status` filter not yet built.** Implied by
  ADR-0003 — retrieval should exclude `status != "active"` by default.
  Nothing to build yet since the retrieval layer itself doesn't exist
  (later module) — noted here so it isn't rediscovered as a surprise.
- **Retrieval-layer storage: deliberately deferred, not decided.** Ingestion
  uses JSON files (`data/metadata/`, `data/chunks/`) per the frozen
  architecture — the right call at this corpus size (40-60 documents, one
  ingest run, no concurrent writers), and not a trap: the `declared`/
  `derived`/`lifecycle` schema from ADR-0003 gives any later migration a
  clean, stable `doc_id`-keyed structure to load from, so this doesn't lock
  anything in. The real open question is what retrieval uses once that
  stage is designed — a local index file, or a vector database, depending
  on whether retrieval ends up doing lexical or vector search (or both).
  Not decided now because retrieval hasn't been designed yet. Revisit when
  that design starts, not before — and worth weighing this course's own
  Module 4 finding (keyword search beat vector search on the lesson corpus)
  as one data point against assuming a vector database is obviously needed,
  rather than deciding on intuition alone.
