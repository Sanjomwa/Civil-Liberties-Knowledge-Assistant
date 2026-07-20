# Project Continuity — Civil Liberties Knowledge Assistant

Purpose: if this project goes idle for any length of time — a week, a
year — this doc should let anyone picking it up, including the original
author, resume without reconstructing context from memory or old history.
Read this file first, in full, when resuming cold.

Last updated: 2026-07-13.

---

## 1. Current state (snapshot)

**Implementation status: walking-skeleton milestone AND the 10-document/
4-org acquisition-method milestone are both complete.** All six ingestion
modules exist in `src/ingestion/` — `acquire.py`, `extract.py`,
`validate.py`, `metadata.py`, `chunk.py`, `pipeline.py` — and 10 real
documents across all four v1 orgs have flowed through every stage
successfully: 1671 chunks total. See Section 6a (walking skeleton, 1
document) and Section 6b (10-document/4-org pass) for full detail. Project
folder now also contains:
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
- `data/raw/`, `data/processed/`, `data/metadata/`, `data/chunks/` — 10
  real documents' worth of output at each stage (Sam's machine only —
  these directories are gitignored and don't sync into the Cowork
  workspace mirror; see the repo's own `.gitignore`).
- `corpus/sources/accessnow.yaml`, `cipesa.yaml`, `freedomhouse.yaml` —
  three new source files, alongside the original `ooni.yaml` (now with a
  second document). All four now use a top-level `default_acquisition`
  field (`auto` for Access Now/CIPESA/Freedom House, `manual` for OONI) —
  see Section 6b for how that was determined.

Not yet started: acquiring the remaining ~30-49 documents to build out the
full 40-60 document corpus (this pass deliberately tested 2-4 documents per
org to determine auto-vs-manual acquisition, per Section 6b's stated
purpose, not to complete the corpus), and `pipeline.py`'s sibling utility
`check_drift.py` (correctly deferred — only meaningful once a corpus
version change actually exists to detect drift against).

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

10 documents acquired across all four v1 orgs as of 2026-07-13 (walking
skeleton + the 10-document/4-org pass, Section 6b) — not yet the full
40-60 document corpus, but enough to settle the auto-vs-manual question per
org. Per-source table:

- **OONI** — base URL `ooni.org`. Access method: **manual**, confirmed
  twice on two different URLs (both returned HTTP 429 to a single
  reconnaissance GET with browser-like headers, no retry loop). 2
  documents: `ooni-tz-2025-x-platform-blocking` (sha256
  `17109f2a...a44f`) and `ooni-ke-2025-telegram-kcse-blocking` (sha256
  `7769f47a...c320e`), both acquired via real browser save (Save As →
  Webpage, HTML Only), never curl or `requests`.
- **Access Now** — base URL `accessnow.org`. Access method: **auto** —
  single reconnaissance GET returned clean HTTP 200 + valid PDF content for
  both documents tested. 2 documents: `accessnow-africa-2023-keepiton-
  shutdowns`, `accessnow-africa-2024-keepiton-shutdowns`.
- **CIPESA** — base URL `cipesa.org`. Access method: **auto** — same clean
  result as Access Now. 2 documents: `cipesa-africa-2024-sifa-elections`,
  `cipesa-africa-2025-sifa-ai`. Note: CIPESA's PDF filenames/URLs don't
  reliably carry a year — a URL a search engine associated with their 2023
  report now serves the 2025 report instead. Always verify a CIPESA PDF's
  own title page before trusting a year from its URL or a search result.
- **Freedom House** — base URL `freedomhouse.org`. Access method: **auto**
  — clean HTTP 200 + real HTML (no bot-challenge phrases) for all four
  documents tested. 4 documents, one per country except Tanzania (see
  Section 6b — Freedom House has no "Freedom on the Net" chapter for
  Tanzania at all, a real scope finding, not an oversight).

`corpus/sources/*.yaml` now resolve acquisition mode as: the document's own
`acquisition` field if present, else the YAML's top-level
`default_acquisition`, else `"auto"` — added specifically because this
pass showed acquisition mode is a server/org property, not a per-document
one (see `src/ingestion/acquire.py`'s own docstring, and the Opus consult
in `decisionlog.md`, 2026-07-13).

## 4. Attribution and licensing status

All four v1 orgs now have at least one real document in the corpus (see
Section 3). OONI's measurement *data* license (CC BY-NC-SA 4.0) is
confirmed in `docs/licensing.md`; the exact license variant for OONI's
*content* (reports, as opposed to raw measurements) is still an open
action item — see Section 7. Freedom House content is permission-gated,
not Creative Commons — permission requested 2026-07-13, still awaiting
response (Section 7); the four Freedom House documents acquired in
Section 6b are for internal course-project use only, not any CLIO-facing
redistribution, until that permission is confirmed. Access Now and CIPESA
licensing terms not yet independently re-verified against the specific
documents acquired this pass — `docs/licensing.md`'s original per-org
findings should be checked against these specific URLs before any
redistribution, not assumed to carry over automatically.

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

## 6b. Second implementation milestone (10-document / 4-org acquisition pass)

Defined and completed same-day, 2026-07-13, at Sam's explicit request right
after Section 6a finished — Opus-consulted first (see decisionlog.md) on
what to change before scaling past one org.

**Status: COMPLETE.** All 10 documents flowed through all six stages;
1671 total chunks written.

**Superseded by Section 7's 2026-07-20 entry below — corpus is now 18
documents / 2661 chunks**, not 10/1671. Left here as the original
milestone record rather than edited in place, since it's still the
correct description of what the walking-skeleton-to-10-doc pass itself
proved (auto-vs-manual acquisition method per org).

**Purpose:** the walking skeleton (Section 6a) proved the pipeline's shape
on one document from one org. This pass's specific goal, per Sam's own
framing, was to settle **which orgs can use scripted `acquisition: auto`
and which need `acquisition: manual`** — a real operational question before
committing to acquiring the full 40-60 document corpus, where a wrong
guess here could mean many documents needing slow manual handling.

**Method:** a single reconnaissance request per document (browser-like
headers, no retry loop — the same discipline `acquire.py` itself now
follows) rather than looping or guessing. Result, per org (full detail in
Section 3):
- OONI: manual (429 on two different URLs, confirmed twice).
- Access Now: auto (clean 200 + valid PDF, both documents tested).
- CIPESA: auto (clean 200 + valid PDF, both documents tested).
- Freedom House: auto (clean 200 + valid HTML, all four documents tested).

**Design changes this pass motivated** (Opus-consulted, see decisionlog.md):
- `acquire.py`: added a per-org `default_acquisition` field (YAML
  top-level), with the existing per-document `acquisition` field now
  acting as an override rather than the only mechanism — acquisition mode
  turned out to be a server property, not a per-document one.
- `acquire.py`: a single document's acquisition failure no longer stops the
  whole run (previously `sys.exit(1)` on the first exception) — now logs
  the failure with a specific reason to `corpus/acquisition-log.md` and
  continues with the rest. At one document this didn't matter; at 4 orgs
  it would have meant one bad OONI document blocking every other org's
  documents in the same run.
- `looks_like_declared_format()` now returns *why* a format check failed
  (specific challenge phrase matched, or bad magic bytes), not just a bare
  boolean — makes the acquisition log a real empirical record instead of a
  silent gate.

**Real bug found and fixed:** `validate.py` crashed (`OverflowError`) the
first time it ran against real multi-thousand-word documents with more
than one document to compare — the `simhash` library's default
`large_weight_cutoff` (50) routes any token appearing more than 50 times
through a code path that overflows under modern numpy. Never surfaced on
the single walking-skeleton document (4,445 words, never exercised the
multi-document near-duplicate comparison at all). Fixed by raising
`Simhash.large_weight_cutoff` to a value no real document will ever reach.
Full detail in decisionlog.md, 2026-07-13.

**Other real findings, not bugs, just things learned:**
- Freedom House has no "Freedom on the Net" chapter for Tanzania — a
  genuine gap in the architecture's original assumption of "one FOTN
  chapter per target country, all five." Resolved by using FOTN chapters
  for the four countries that have them, not by substituting a
  differently-scoped Freedom House product for Tanzania.
- CIPESA's report PDFs don't reliably keep a year in their own filename or
  URL — a URL a search engine associated with CIPESA's 2023 report
  currently serves their 2025 report instead. Resolved by fetching and
  reading each candidate PDF's own title page before trusting a
  search-reported year, same discipline established during the OONI
  incident in Section 6a.
- Extraction was clean across every document and format this pass —
  including the two ~30,000-word CIPESA PDFs, which were a specific worry
  going in. No OCR/garbled-text issues surfaced.
- Near-duplicate detection did not false-flag any pair despite real
  topical overlap between Access Now's and CIPESA's 2024 reports (both
  document African shutdowns from the same general period) — correctly
  distinguishes genuine near-duplication from two orgs' different accounts
  of an overlapping period.

**Explicitly out of scope for this pass:** completing the full 40-60
document corpus (2-4 documents per org was enough to answer the
auto-vs-manual question; scaling further is future work, see Section 7),
`check_drift.py` (still no corpus version change to detect drift against).

## 7. Open action items (don't lose track of these)

- **PENDING ACQUISITION, 2026-07-20: two Tanzania OONI documents added
  to `ooni.yaml` (sha256 REPLACE_ME) — a 2024 LGBTIQ-censorship blog
  report and an August 2024 Twitter/X-blocking Findings incident, both
  content-verified.** Rwanda's zero-OONI-coverage gap reconfirmed as
  genuine (checked the full reports archive + all Findings incidents,
  not just a search miss). A real Kenya candidate (June 2025
  anti-government-protest Telegram block) was rejected for length
  (~320 words, below this corpus's 500-word floor). Next step:
  acquisition prompt to Claude Code — corpus would go from 33 to 35
  documents once done. See `decisionlog.md`, 2026-07-20, for detail.
- **DONE, 2026-07-20: Kenya and Ethiopia CIPESA SIFA AI country reports
  acquired, validated, Included, pipelined — corpus now at 33
  documents / 3,711 chunks.** Both passed Tier 1/Tier 2 validation
  clean, including a genuine near-duplicate check against the
  structurally similar Uganda companion already in the corpus (0
  near-dupes flagged despite the shared report template) — confirms
  distinct per-country content, not just distinct metadata. Real
  sha256 hashes replace the `REPLACE_ME` placeholders; byte sizes
  matched the prior research pass exactly (27,898,015 / 27,037,527),
  confirming stable content since verification. Chunk-count
  idempotency confirmed: 31 pre-existing documents still sum to 3,488
  unchanged, +223 new (125 Kenya, 98 Ethiopia) = 3,711. Per-org: Access
  Now 4 (668), CIPESA 9 (1,299), Freedom House 16 (1,595), OONI 4
  (149). See `decisionlog.md`, 2026-07-20, for the full detail.
- **DONE, 2026-07-20: 3 new CIPESA catalog documents (Tanzania UPR,
  Rwanda UPR, Uganda SIFA AI country report) through the pipeline —
  corpus now at 31 documents / 3,488 chunks.** Sam ran the acquisition
  prompt twice by accident; Claude Code caught it on the second run
  (checked for `REPLACE_ME`/existing `Included` entries first, found
  none pending, declined to re-append or re-run `metadata.py`/
  `chunk.py`) — confirmed via a fresh `acquire.py` run that all 31 docs
  hit `[skip]`, 0 downloads, 0 failures, no duplicate log entries. Final
  per-org: Access Now 4 (668), CIPESA 7 (1,076), Freedom House 16
  (1,595), OONI 4 (149). Kenya/Ethiopia's equivalent CIPESA 2025 SIFA AI
  country reports are the next candidate (Kenya's PDF fetch returned
  empty on first try, not yet resolved). See `decisionlog.md`,
  2026-07-20, for the full detail.
- **DONE, 2026-07-20: Freedom House 2025 batch (4 docs) reviewed,
  Included, pipelined — corpus now at 28 documents / 3336 chunks.**
  Real finding along the way: Freedom House abridged the entire 2025
  FOTN series for budget reasons (1,134-1,906 words vs. 9,220-14,312
  in 2022-2024) — reviewed anyway rather than assumed-fine or
  assumed-disqualified; all 4 contain genuine, specific, dated,
  footnoted findings not already in the corpus (confirmed with Sam).
  Per-org: Access Now 4 (668 chunks), CIPESA 4 (924), Freedom House 16
  (1,595), OONI 4 (149). See `decisionlog.md`, 2026-07-20, for the
  full review.
- **DONE, 2026-07-20: `acquire.py`/`extract.py`/`metadata.py` all
  support a third `source_format`: `json` — corpus now at 24
  documents, 3283 chunks, all fully pipelined.** Needed for OONI's
  newer "Findings" platform (JS-rendered SPA, real content only
  reachable via its own JSON API). `metadata.py`'s `build_derived()`
  was missed on the first pass (same binary pdf-vs-html pattern
  `acquire.py` had before its own fix) — caught by Claude Code
  actually running the pipeline end to end, fixed same day. Real
  process lesson: this extension-mapping logic exists in three places
  (`acquire.py` twice, `metadata.py` once, not two) — check all three
  next time a new source_format is added. See `decisionlog.md`,
  2026-07-20 (two entries), for the full incident and fix.
- **DONE, 2026-07-20: 2 new CIPESA documents through the pipeline —
  corpus now at 23 documents / 3253 chunks.** Both passed validation
  clean (0 flags, 0 near-dupes), logged Included, chunked; idempotency
  confirmed against the pre-existing 21-document/2977-chunk total.
  Per-org: Access Now 4 (668 chunks), CIPESA 4 (924), Freedom House 12
  (1,542), OONI 3 (119). CIPESA no longer the lowest-count org — OONI
  now is, capped by its manual-acquisition requirement (Section 3);
  that's the likelier next research target if scaling continues. See
  `decisionlog.md`, 2026-07-20, for the full detail.
- **DONE, 2026-07-20: `claude-code-wsl-CLAUDE.md` relocated into
  `repo/`; Research Questions docx drift fixed.** The retrospective's
  own v3 update (previous entry, below) hit a real blocker the same
  day: the file lived outside `repo/`, unreachable by `sync.sh pull`,
  so Claude Code correctly reported it couldn't find v3 rather than
  guessing at its content. Moved the canonical copy to
  `repo/claude-code-wsl-CLAUDE.md` (gitignored, excluded from `push`
  too so a stale WSL copy can't overwrite it), left a pointer stub at
  the old location, updated `.gitignore`, `sync.sh`'s comments, and
  project `CLAUDE.md` Section 9. Also fixed, from the same task's ADR-
  vs-reality audit: `docs/archituecture.md.docx`'s "Research
  Questions" section still said "between 2022 and 2025" after
  ADR-0006's window extension — updated to 2026, validated (307→307
  paragraphs, all checks PASSED), visually confirmed. See
  `decisionlog.md`, 2026-07-20, for the full incident.
- **Next: scale ingestion to the full 40-60 document corpus.** Both
  Section 6a (pipeline shape) and Section 6b (per-org auto-vs-manual) are
  complete. Access Now/CIPESA/Freedom House can be acquired via
  `acquisition: auto` with minimal manual effort; OONI documents need
  manual browser-save acquisition each time, per Section 3 — budget for
  that when planning how many more OONI documents to include. Not further
  pipeline development (`check_drift.py` excepted, see below).
- **DONE, 2026-07-20: ADR-0005 implemented, all 8 new Freedom House
  documents acquired/extracted/validated.** `docs/adr/
  0005-content-checksum-for-cdn-served-html.md` (splits the checksum
  into a raw-bytes local-integrity hash + a new `content_sha256` over
  canonicalized extracted text; `raw_bytes_stable: false` +
  trust-on-first-use bootstrap for Freedom House; positive
  title-presence check in `acquire.py`) implemented by Claude Code in
  WSL, first real test of the `sync.sh`-based workflow. `acquire.py`/
  `extract.py`/`validate.py` all ran clean. All 12 Freedom House
  documents (4 existing 2024 + 8 new 2022/2023) now have real `sha256`
  and `content_sha256` values, no `REPLACE_ME` left. The 4 existing
  documents passed the new positive title-check as a side effect of
  their skip-path re-run. `validate.py`'s Tier 2 near-duplicate check
  flagged 8 of the 12 (all but the three Rwanda entries and Ethiopia
  2024) for human review — expected, same-country year-over-year FOTN
  chapters share template boilerplate; not resolved automatically, per
  ADR-0002. Full run output in `decisionlog.md`, 2026-07-20.
- **Next, not yet started: semantic review (rubric Section 4) for all 8
  new Freedom House documents**, the 6 flagged ones especially — same
  real-overlap-vs-coverage-value judgment call already applied once this
  session to the Access Now/CIPESA 2024 pair. None of the 8 are marked
  Included/Excluded in `corpus/acquisition-log.md` yet. Access Now,
  CIPESA, and OONI batches are the next research passes after this one
  lands.
- **DONE, 2026-07-20: OONI `default_acquisition` confirmed and flipped
  to `auto`.** Root cause (Vercel bot-protection JS challenge) confirmed
  fixed by the OONI team via their public Slack; verified via the
  authoritative test — a real `requests.get()` with `acquire.py`'s own
  headers against a never-before-fetched OONI URL, HTTP 200, real
  content, no challenge markers. See `corpus/sources/ooni.yaml` and
  `decisionlog.md`, 2026-07-20, for the full evidence trail.
- **DONE, 2026-07-20: full pipeline completed for the 8 new Freedom
  House documents — corpus is now 18 documents / 2661 chunks.**
  `metadata.py` and `chunk.py` run for all 18 Included documents
  (idempotent full pass, not scoped to just the new 8). All 8 new
  documents: `validation_status: "valid"`, no warnings, populated
  `chunking` blocks (990 chunks total, 95-149 per document, scaling
  with word count as expected). The 10 pre-existing documents'
  chunk counts were byte-for-byte unchanged (1671, matching the
  original 10-document milestone exactly) — confirms the full-pass
  re-run didn't alter anything it wasn't supposed to. Corpus
  breakdown by org: Freedom House 12 (4 original + 8 new), Access Now
  2, CIPESA 2, OONI 2 — 18 total, 2661 chunks. Full verbatim run
  output in `reports.md`/`decisionlog.md`, 2026-07-20.
- **DONE, 2026-07-20: Access Now (2 new: 2022, 2025 annual reports) and
  OONI (1 new: Ethiopia 2023) fully through the pipeline — corpus now
  21 documents / 2977 chunks.** `corpus/sources/accessnow.yaml` now has
  4 documents (2022-2025, one flagship annual report per year);
  `corpus/sources/ooni.yaml` now has 3 (this org's first Ethiopia entry,
  a direct cross-org account of the same Feb-May 2023 platform block
  already in Freedom House's `et-2023-fotn` entry). All 3 acquired
  against the standard pre-declared-hash gate (neither org needed
  ADR-0005's trust-on-first-use treatment — confirmed via a double-fetch
  stability check on the OONI HTML document, not assumed). All 3 logged
  Included in `corpus/acquisition-log.md`, `validation_status: "valid"`
  with no warnings, 316 new chunks (161+147+8), 18 pre-existing
  documents' chunk counts unchanged (2661, confirming idempotency).
  316+2661=2977 matches `chunk.py`'s own total exactly. Full run output
  in `decisionlog.md`, 2026-07-20.
- **DONE, 2026-07-20: ADR-0006 — corpus date window extended 2022-2025
  → 2022-2026.** Static, one-time, event-motivated bump (Opus-consulted;
  not a rolling window — see the ADR for why), triggered by a real OONI
  document on Uganda's January 2026 election shutdown that was otherwise
  in-scope. `docs/corpus-inclusion-rubric.md` and `archituecture.md.docx`
  (now v1.6) both updated. Also fixed in the same pass: `archituecture.md.docx`
  had silently drifted from ADR-0005's own declared v1.5 bump (never
  actually applied) — both version bumps corrected together.
- **Next: continue scaling toward the 40-60 document target (18/40-60,
  heading to 21).** Per the Opus consult behind ADR-0006: the bigger
  lever here is under-sampling within the existing window, not the
  window itself — most orgs still hold only 1-4 documents when
  substantially more real in-window material exists per org. CIPESA is
  the org least touched this round (still 2 documents) — a good next
  research target, same shape as this pass (research here in Cowork,
  semantic review, then hand Claude Code the acquisition prompt). The
  Uganda January 2026 OONI document ADR-0006 makes newly eligible is
  also worth picking up in a future pass.
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
