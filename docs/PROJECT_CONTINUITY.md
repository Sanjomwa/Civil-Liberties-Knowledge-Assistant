# Project Continuity — Civil Liberties Knowledge Assistant

Purpose: if this project goes idle for any length of time — a week, a
year — this doc should let anyone picking it up, including the original
author, resume without reconstructing context from memory or old history.
Read this file first, in full, when resuming cold.

Last updated: 2026-07-13.

---

## 1. Current state (snapshot)

**Implementation status: walking-skeleton milestone complete.** As of this
update, all six ingestion modules exist in `src/ingestion/` — `acquire.py`,
`extract.py`, `validate.py`, `metadata.py`, `chunk.py`, `pipeline.py` — and
one real document (`ooni-tz-2025-x-platform-blocking`) has flowed through
every stage successfully. See Section 6a for the full checklist and
real-run results. Project folder now also contains:
- `docs/archituecture.md.docx` — frozen architecture, now **v1.4** (amended
  2026-07-11 via ADR-0001 through ADR-0004 — see Section 5).
- `docs/ingestion-design.md` — pipeline reference, synthesizing the
  architecture plus all four ADRs, with a diagram.
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
- `src/ingestion/` — six modules, all tested (synthetically and/or against
  the real document — see Section 6a for which).
- `corpus/sources/ooni.yaml`, `corpus/CORPUS_VERSION`,
  `corpus/acquisition-log.md`, `corpus/manifest.csv`,
  `corpus/checksums.sha256`, `corpus/validation-report.md` — generated or
  hand-written artifacts from the real walking-skeleton run.
- `data/raw/`, `data/processed/`, `data/metadata/`, `data/chunks/` — one
  real document's worth of output at each stage (Sam's machine only —
  these directories are gitignored and don't sync into the Cowork
  workspace mirror; see the repo's own `.gitignore`).

Not yet started: acquiring the remaining ~40-59 documents to build out the
full corpus (this milestone deliberately proved the pipeline shape on one
document first, per Section 6a's own stated purpose), and `pipeline.py`'s
sibling utility `check_drift.py` (correctly deferred — only meaningful once
a corpus version change actually exists to detect drift against).

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

One document acquired so far (the walking-skeleton milestone, Section 6a),
not yet the full corpus — this section will grow into a real per-source
table once acquisition scales past one document. Current precedent:

- **OONI** — base URL `ooni.org`. Access method: **manual**, not
  scripted — OONI's server sustained a 429 against repeated scripted
  requests (including a proper User-Agent, no retry loop), and separately,
  two different URLs on the site turned out to sit behind bot-challenge
  pages under automated access. `corpus/sources/ooni.yaml` marks this
  org's documents `acquisition: manual` accordingly; `acquire.py` only
  verifies checksums for them, never fetches. Real document:
  `ooni-tz-2025-x-platform-blocking`, sha256
  `17109f2a365e5959c4d218c412cf6e851e3d51e49cc070e2ff26bda72a90a44f`,
  acquired via a real browser save (Save As → Webpage, HTML Only), not
  curl or `requests`. `CORPUS_VERSION` at acquisition: `v1.0`.
- Access Now, CIPESA, Freedom House — no documents acquired yet. Don't
  assume OONI's manual-acquisition requirement generalizes to these; each
  org's server behavior needs its own real test before deciding auto vs.
  manual (see the decisionlog.md 2026-07-13 entry answering Sam's question
  on exactly this point).

## 4. Attribution and licensing status

One document's worth of precedent (OONI, see Section 3) — full per-source
table still pending until acquisition scales past the walking-skeleton
milestone. OONI's measurement *data* license (CC BY-NC-SA 4.0) is
confirmed in `docs/licensing.md`; the exact license variant for OONI's
*content* (reports, as opposed to raw measurements) is still an open
action item — see Section 7. Each of the five v1 sources (OONI, Access Now,
CIPESA, Freedom House, +2 deferred) has its own data licensing terms; these
must be recorded here before any content derived from them is published or
redistributed.

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

**Status: COMPLETE (2026-07-13).** One real document flowed through
every stage, including `pipeline.py` itself. All checklist items below are
done.

**Definition of success:** one real document flows through the entire
pipeline — `acquire.py` → `extract.py` → `validate.py` → `metadata.py` →
`chunk.py` — via `pipeline.py` as a single command, before any work goes
into acquiring the full 40-60 document corpus. Proves the pipeline's shape
and every ADR's design actually holds together, before paying the cost of
scaling it up.

**Document choice:** ended up `ooni-tz-2025-x-platform-blocking`, HTML not
PDF (see the acquire.py note below for why) — a deliberate departure from
this section's original PDF-first preference, forced by OONI's PDF path
sitting behind a bot challenge. Still not Freedom House, per the original
reasoning (licensing action item still open — see Section 7).

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
- [x] `data/processed/` has non-empty, plausible extracted text. Done
  2026-07-13 — 4,445 words extracted via `trafilatura` (the document ended
  up `source_format: html`, not `pdf` — see the acquire.py note above).
  Real wrinkle: `ooni.org` turned out to challenge scripted HTML requests
  too, inconsistently, so a second bot-challenge page (different from the
  first) got treated as verified content until checked by actual text, not
  just file type — `acquire.py` now checks HTML content for known
  challenge phrases, the same way it checks PDF magic bytes.
- [x] Tier 1 checks (extraction success, file integrity) ran and passed.
  Done 2026-07-13 — `validate.py` tested synthetically first (pass path and
  auto-exclude path with a deliberately bad checksum), then run for real:
  Tier 1 passed against the actual document.
- [x] Tier 2 checks (language, length, near-duplicate) actually ran and
  produced a report. Done 2026-07-13 — real run shows "Tier 1 passed, Tier
  2: clean" in `corpus/validation-report.md` (English, 4,445 words, 0
  near-duplicates — trivially true with one document, but proves the
  routing logic executes, not just that it exists on paper).
- [x] A human (Sam) does the semantic review for real, using
  `corpus-inclusion-rubric.md`, marks it Included, and that reasoning is
  logged in `corpus/acquisition-log.md`. Done 2026-07-13 — clean Include on
  both topic relevance and coverage contribution (first document in the
  corpus). While drafting this entry, found the rubric itself named the
  wrong path (`docs/acquisition-log.md` vs. the actual
  `corpus/acquisition-log.md`) — fixed in the rubric to match what got
  built.
- [x] `data/metadata/{doc_id}.json` matches the amended schema
  (schema_version 1.1): `declared`, `derived`, `lifecycle` (defaulting to
  `active`), `chunking` (added by `chunk.py`, not `metadata.py` — it isn't
  known yet at that point in the pipeline). Done 2026-07-13, verified
  against the real document's actual JSON output.
- [x] `data/chunks/{doc_id}/*.json` exist, each carrying the `corpus_version`
  stamp from ADR-0003. Done 2026-07-13 — 38 chunks for the real document
  (1500/750 fixed overlapping windows over ~28k extracted characters), each
  embedding the full `document_metadata` record.
- [x] Idempotency: rerun `acquire.py` (or the whole pipeline) on the same
  document a second time — confirm it's a no-op. Confirmed both
  synthetically (via a dedicated pipeline.py test fixture — four scenarios:
  stop-after-validate, `--all` continuation, idempotent rerun, and
  stop-on-failure with a deliberately corrupted checksum) and for real —
  Sam's second `extract.py`/`chunk.py` runs correctly skipped/regenerated
  rather than duplicating.
- [x] A second, synthetic, deliberately-bad input run through `validate.py`
  alone, confirming a Tier 1 failure actually auto-excludes. Done — tested
  when `validate.py` was first built (synthetic pass path + synthetic
  Tier-1-failure path with a bad checksum), and incidentally re-confirmed
  for real when a stale manifest checksum caused a genuine Tier 1 failure
  mid-debugging (see the acquire.py truncation-bug note below) before being
  fixed.

**Real bug found and fixed along the way, worth keeping the record of:** an
in-place edit to `acquire.py` left the file silently truncated (missing the
rest of `main()` and the `if __name__ == "__main__":` guard) — it ran with
zero output and exit code 0 instead of failing loudly, since the functions
were defined but never called. Took an extended remote debugging session to
catch (ruled out `uv run`, output buffering, and terminal display before
actually `cat`-ing the file revealed it just stopped mid-comment). The same
truncation happened again while writing `pipeline.py` — caught immediately
that time by checking line count / null bytes via bash right after every
edit, which is now standard practice for every file touched in this repo,
not just a one-off fix. Full sequence in `decisionlog.md`, 2026-07-13.

**Explicitly out of scope for this milestone** (don't let it creep):
the full corpus, cross-document near-duplicate detection actually firing
(nothing to compare against with one document), `check_drift.py` (only
meaningful across a corpus version change), anything retrieval/
embedding-related (already out of scope for the whole pipeline).

## 7. Open action items (don't lose track of these)

- **Next: scale ingestion past the walking-skeleton milestone.** Section 6a
  is complete — the six-stage pipeline works end to end on one document.
  The next real step is acquiring and running the remaining ~40-59
  documents across the four v1 sources, not further pipeline development
  (`check_drift.py` excepted, see below).
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
  corpus_version` per document. `chunk.py` itself is now done (2026-07-13),
  but this utility is only meaningful once a real `CORPUS_VERSION` change
  exists to detect drift against (explicitly out of scope for the
  walking-skeleton milestone) — still correctly deferred, not overdue.
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
