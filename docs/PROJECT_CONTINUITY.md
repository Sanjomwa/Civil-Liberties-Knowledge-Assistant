# Project Continuity — Civil Liberties Knowledge Assistant

Purpose: if this project goes idle for any length of time — a week, a
year — this doc should let anyone picking it up, including the original
author, resume without reconstructing context from memory or old history.
Read this file first, in full, when resuming cold.

Last updated: 2026-07-25 (later still) — **judge rubric v2 run for real
and adopted as the headline result (ADR-0014).** A documented defect in
the judge's original "partial" catch-all (absorbing both one-step fact
synthesis and unscored negation claims — found via two Opus 5 consults
plus an empirical cross-check, not assumed) was fixed and validated in
two stages before being trusted: cheaply on a 47-row known-disagreement
subset, then for real across all 481 claims. **Citation precision moved
from 0.879 (v1, original) to 0.946 (v2, fixed) — every category
improved, 33/481 claims moved to "supported," exactly 1 moved the other
way (a defensible edge case).** Sam chose 0.946 as the headline
reported number, with 0.879 disclosed as the superseded original
methodology, not deleted. **Judge-validity against independent human
judgment remains explicitly OPEN** — this fix closes "is the rubric
itself sound," not "has a human confirmed this," and both must be
disclosed together wherever 0.946 is reported. Full numbers in
`reports.md`/`decisionlog.md`, 2026-07-25, and ADR-0014. The rubric-gap
half of LLM evaluation's definition of done was already closed earlier
today (Prompt A/B comparison — Prompt A won, 0.893 vs 0.869, see below).
Prior update (2026-07-24, later same day): a full rubric audit against the real, verbatim `project.md`
Evaluation Criteria found the LLM evaluation phase was genuinely 1/2, not
2/2 (only one generation approach had ever been compared — see
ADR-0012); an Opus 5 consult produced the ranked completion plan now in
force (Prompt A/B comparison, README rewrite per `docs/readme-plan.md`,
2026-08-02 feature-freeze gate ahead of the confirmed 2026-08-11 02:00
deadline, a posts-7+8 merge in the learning-in-public series). Prior
update (2026-07-23) brought this file current after a full
documentation-sync pass covering the retrieval and generation phases.

**Known process gap, found 2026-07-25:** this file's edits from earlier
today (the same headline update this replaces, plus an ADR-0011
addendum) were lost — reverted to their pre-edit state, almost certainly
by a `sync.sh pull` that ran after the Cowork-side edits were made but
before they were ever pushed to WSL. `decisionlog.md` was unaffected
(lives outside `repo/`, never synced). Practical takeaway: push any
pending Cowork-side doc edits to WSL before the next pull, not after —
otherwise they're silently overwritten with no error. Not yet fixed at
the tooling level; Sam's call whether that's worth automating.

---

## 1. Current state (snapshot)

**Ingestion, retrieval, and generation phases are CLOSED. LLM evaluation
is built and real-run against the real corpus and API — both rubric gaps
identified in the 2026-07-24 audit (ADR-0012) are now addressed.** The
"compare multiple approaches" gap closed via the Prompt A/B comparison
(2026-07-25 — Prompt A won, 0.893 vs 0.869, and stays the default). The
judge-scoring-quality question closed via judge rubric v2 (ADR-0014,
2026-07-25, later same day) — a real, confirmed defect in the original
judge prompt was found and fixed, validated in two stages, and re-run for
real: **citation precision moved from 0.879 (v1) to 0.946 (v2)**, now the
headline reported number. **What remains open: judge-validity against
independent human judgment.** ADR-0011's human-calibration requirement
was never satisfied by a real human read — two same-day substitute
attempts (an AI-reviewer read, then a disagreement-only subset) both
proved impractical, and Sam explicitly chose to invest further effort in
fixing the judge's rubric instead of more review time. This is disclosed
as an open limitation everywhere the 0.946 figure is reported, not
smoothed over. Full detail: ADR-0011's addendum, ADR-0014, `reports.md`
and `decisionlog.md`, 2026-07-25. The overall project plan (build order,
timeline, README standard) runs against `project.md`'s Evaluation
Criteria explicitly, not informally — full completion plan in ADR-0012.

- **Ingestion:** CLOSED 2026-07-20, verified clean. All six modules in
  `src/ingestion/` (`acquire.py`, `extract.py`, `validate.py`,
  `metadata.py`, `chunk.py`, `pipeline.py`) plus on-demand
  `reconcile.py`. **Corpus: 35 documents, 3,783 chunks** across all four
  v1 orgs (Access Now 4, CIPESA 9, Freedom House 16, OONI 6). Re-run end
  to end after the end-of-ingestion-phase Opus+Fable review's six
  findings were fixed (ADR-0007, ADR-0008) — zero content-drift, zero
  cross-surface disagreement (`reconcile.py`).
  **Post-closure addition, 2026-07-25 (ADR-0013): tiered corpus release +
  `src/ingestion/rehydrate.py`, real run.** New module `rehydrate.py`
  (`--org freedomhouse|accessnow`) re-runs acquire → extract → metadata →
  chunk for one org's documents and verifies the result: `content_sha256`
  for Freedom House (`raw_bytes_stable: false` — the org whose raw HTML is
  CDN-randomized per request, so content_sha256 is the mechanism that
  survives that noise), the existing raw-`sha256` gate for Access Now
  (`raw_bytes_stable: true` by default — content_sha256 was never tracked
  for it, by design, since stable raw bytes deterministically produce
  stable text). Smoke-tested for real against one live Freedom House doc
  and one live Access Now doc: genuine fresh re-download + re-extraction +
  re-chunking reproduced byte-identical chunk text and the correct chunk
  count both times (146 and 161 chunks respectively), and a deliberately
  corrupted re-fetched text was correctly caught and raised loudly (not a
  warning) in both a baseline-tampering test and a literal one-byte text
  corruption test. **Real pre-existing bug found and fixed along the
  way** (not something rehydrate.py introduced): `acquire.py`'s
  `acquire_document()` gated a fresh Freedom House download against the
  stale, historical `doc["sha256"]` value instead of accepting new bytes
  under the trust-on-first-use policy `raw_bytes_stable: false` is
  supposed to grant — this silently broke the exact fresh-clone/re-fetch
  scenario rehydrate.py needs (proved live: deleting the local raw file
  and re-running `acquire_document()` raised a false `AcquisitionFailure`
  on a perfectly good download). Consulted Opus 5 before touching closed
  ingestion code; fix moves the format check ahead of the checksum gate
  (so a bot-challenge page still can't be recorded as a legitimate
  baseline) and branches the gate itself on `raw_bytes_stable`, plus fixes
  a second bug on the same lines (the returned row didn't carry the new
  `sha256`, so a volatile org's rotated baseline never reached
  `corpus/manifest.csv`/`corpus/checksums.sha256`). Verified: all three
  scenarios pass (volatile+missing-file, volatile+corrupted-local/
  redownload path, stable+real-mismatch-still-raises), `reconcile.py`
  re-run clean after the fix. Release artifact built for real via new
  `scripts/build_release_artifact.py` — `dist/corpus-release-v1.zip`
  (gitignored, not published; Sam attaches it to a GitHub Release by
  hand): 1,520 full-text chunks (OONI + CIPESA, 15 docs, license string
  per record) + 2,263 metadata-only chunks (Freedom House + Access Now,
  20 docs, `content_sha256` but no text/vector) = 3,783, matching the
  full corpus exactly. Full reasoning: `docs/adr/0013-tiered-corpus-release.md`.
- **Retrieval:** CLOSED 2026-07-23. `src/retrieval/{embed,search,
  ground_truth,evaluate}.py`. Recorded default: **hybrid search, RRF
  k=10** (`data/eval/default_method.json`), chosen for best-or-near-best
  MRR across all three question-category slices, not just the aggregate.
  Real measured numbers: aggregate Hit Rate ~0.644-0.66 depending on k;
  neighbor-aware Relaxed Hit Rate ~0.812 (most of the strict/relaxed gap
  is same-document chunk-overlap scoring, not true misses, per Opus's
  own mechanism check). A `multi_country` MRR gap (plain text search
  beats every hybrid config there) was investigated across two rounds of
  diagnostics and root-caused as a real, **not retrieval-fixable**
  category-sampling property (RRF concentrates on cross-backend
  agreement, not an embedding-smoothness defect) — documented as a known
  limitation, not resolved. A country-metadata boost (P2) was built and
  verified correct with zero regressions, but doesn't touch the actual
  cause. **Re-ranking best-practice ablation done 2026-07-25** (real run,
  `data/eval/reranking-ablation-report.md`): three-arm comparison
  (unexpanded-pool/no-boost baseline vs. expanded-pool/no-boost vs.
  today's expanded-pool+boost) against the 101-question filtered ground
  truth, isolating the boost's own effect from the candidate-pool
  expansion it rides on. Metadata coverage checked first: 100%
  (3,783/3,783) chunks carry non-empty `countries`, so the flagged
  demotion-risk regression doesn't materialize here. On the 65-of-101
  "firing" subset (query names a country AND the candidate pool actually
  has a matching chunk — the only questions the boost can affect): Hit
  Rate 0.631→0.646, MRR 0.266→0.269, 3 wins/0 losses/62 ties per-question.
  Full-set (diluted): 0.644→0.653 / 0.270→0.272. Bit-identical assertion
  (arms b/c on the non-firing subset) passed with zero mismatches. Ground
  truth was generated+circularity-reviewed 2026-07-22, one day before the
  boost existed (`756b28e`, 2026-07-23) and never calls `search()` itself
  — no circularity risk. Small, real, positive result with zero
  regressions; kept as the shipped default. Hybrid's narrower source-diversity@10 (vs. plain text search)
  was **deliberately not retrieval-fixed** — explicitly deferred to the
  generation phase as "flag thin/single-sourced evidence is generation's
  job, not retrieval's."
- **Generation:** built and real-smoke-tested 2026-07-24, per ADR-0009
  ("Index-Only Citation Protocol and Split Thin/Contradictory Evidence
  Flagging"). `src/generation/{prompts,generate,citations}.py`.
  `answer(query) -> dict`. Core mechanism: the LLM only ever picks `[n]`
  citation markers from numbered retrieved excerpts — it never writes a
  citation itself, so a fabricated title/page/URL is structurally
  impossible, not just discouraged. Thin evidence is a mechanical check
  computed on the **cited** chunk subset (not the retrieved one).
  Contradictory evidence is prompt-instructed only (no NLI machinery),
  left for the evaluation phase to actually verify. `reports.md`
  (2026-07-23/24) documents four real queries against the real corpus
  and a real OpenAI API key, exit 0 each time: every citation
  independently spot-checked against real chunk text (zero fabrications,
  zero misattributions); the sourcing footer correctly distinguished all
  three designed cases (single-org/multi-doc, single-org/single-doc —
  the strongest caveat, multi-org/multi-doc) on live data. **This was a
  smoke test only — no ground truth, no correctness scoring. That gap is
  exactly what the evaluation phase now exists to close.**
- **LLM evaluation: built and real-run 2026-07-24, per ADR-0010 (as
  amended by ADR-0011).** `src/evaluation/{run_answers,judge,
  contradiction_search,evaluate_generation}.py`. Real run: 122 questions
  (101 general/multi_country/ooni_methodology reuse from
  `ground_truth_filtered.json` + 12 hand-authored synthesis-supplement +
  9 hand-authored refusal-slice questions), 481 claims extracted and
  judged. **Claim-level citation precision: 0.879 aggregate** (423
  supported / 37 partial / 21 unsupported) — general 0.912, multi_country
  0.886, ooni_methodology 0.930, synthesis_supplement 0.806, refusal
  0.565 (low refusal-category precision is expected/not fabrication — see
  `reports.md`, 2026-07-24). Judge model: **`gpt-5.4-mini`, not `gpt-5.4`**
  — `gpt-5.4` returned a real, confirmed 403 on this OpenAI project,
  checked empirically per ADR-0011; calibration is therefore
  self-judging, a named limitation. Manual spot-checking of judge verdicts
  against real chunk text (per `reports.md`) confirmed the judge catches
  real precision failures (a real named-individual misattribution, a real
  overclaim) but also surfaced a real methodological nuance: negative/
  hedge claims ("the excerpts do not say X") are frequently scored
  `unsupported` under strict isolated entailment even when accurate,
  meaning 0.879 likely understates true precision somewhat. Refusal slice
  (9 questions): manually reviewed one-by-one, not just via the
  heuristic — 5 clearly correct declines, 2 revealed a flaw in the test
  design itself (Somalia/DRC questions assumed zero corpus evidence, but
  continent-wide reports do mention these countries in passing, and the
  system answered those real facts accurately), 1 appropriately hedged, 1
  a minor caveat-ordering quibble — **zero cases of confident
  fabrication**. Contradiction search (Decision 4/ADR-0010): bounded
  search (7 candidate events, 37 of a 50-call budget) flagged 9
  candidates; all 9 manually verified against real chunk text and found
  to be false positives (mostly two distinct real events sharing
  keywords, not one event reported inconsistently) — **no real
  cross-source contradiction confirmed in this corpus**; the mechanism
  itself was verified via a synthetic fixture, which passed. Cost: ~648
  total API calls, ~1,028,000 input / ~51,150 output tokens (the
  `run_answers.py` portion — 122 calls, 453,261/24,552 tokens — is exact
  from real API `usage`; the judge/contradiction-search portion is a
  disclosed, reconstructed estimate, not exact — see `reports.md` for why).
  Human-review sample files written (judge-calibration: 65 rows stratified
  by verdict; deployment: 75 rows, 15/category) — Sam's actual review is
  the next real step (`--score-review` flag ready). **Real gap found and
  reported, not fabricated around: `decisionlog.md` does not exist
  anywhere (not in this repo, not in git history, not in the Cowork mirror
  per a real `sync.sh pull`) despite being referenced dozens of times as
  the authoritative transcript — see `reports.md` Section 0.** Full detail,
  the verbatim refusal-slice reads, and the contradiction-search
  verification notes are in `reports.md`, 2026-07-24 — see that file and
  `docs/evaluation-design.md`/ADR-0010/ADR-0011 for the full design
  reasoning behind these numbers.
  **CLOSED for real, 2026-07-25 (ADR-0012 Decision 2 / docs/
  evaluation-design.md Decision 6): the rubric's actual gap -- only one
  generation approach was ever compared -- is fixed.** New
  `src/evaluation/compare_prompts.py` and `SYSTEM_PROMPT_B` in
  `prompts.py` (copied verbatim from the design doc). Real run: a
  stratified 40-question subset (largest-remainder allocation preserving
  each of the 5 categories' real share of the 122-question set:
  general 22, multi_country 7, ooni_methodology 4, synthesis_supplement
  4, refusal 3), retrieval held fixed per question (one `search()` call
  reused for both arms), judged by the same unmodified `judge.py`.
  **Result: Prompt A won, kept as the default -- Prompt B did NOT win,
  and that's the real, reported outcome, not a cherry-picked one.**
  Precision: A 0.893 vs B 0.869 (177 vs 160 claims judged); A also
  produced *more* claims per answer (4.43 vs 4.00), ruling out a
  fewer-claims/hedging explanation for B's lower score. Abstention
  rate near-identical (A 0.00, B 0.03 -- 1/40, a correct refusal-slice
  decline). Token cost: B's completion tokens ran ~1.7x A's (235 vs 411
  mean), for a worse result. Manual spot-check (7+ real cases read
  directly against chunk text, both directions) found the concrete
  mechanism: Prompt B's compact one-line-per-fact EVIDENCE list
  repeatedly attributed several distinct facts -- which actually span two
  adjacent, half-overlapping real chunks (chunk_size=1500/chunk_step=750)
  -- to a single citation marker (e.g. `general-0068`: 6 distinct legal
  penalties in Rwanda's penal code all attributed to one marker, when
  Prompt A correctly split them across the real 2-3 chunks the passage
  actually spans; `general-0065`: several named individuals' facts
  attributed to the wrong marker number in a 19-line EVIDENCE list). No
  restatement-laundering or over-abstention found in the spot-checked
  supported/refusal cases -- those verdicts held up under direct
  re-verification. **A real bug in this run's own harness was found and
  fixed before reporting**: the first abstention-rate measurement reused
  `evaluate_generation.py`'s `DECLINE_PHRASES` heuristic per-answer,
  which that module's own docstring already caveats as needing a human
  reader alongside it for the small refusal slice -- applied blindly here
  it false-positived on 5 of Prompt A's fully substantive, cited answers
  (each contained one bounded qualifier phrase like "do not provide a
  specific penalty" inside an otherwise complete answer). Fixed to a
  zero-citations-only definition, recomputed from already-persisted data
  (no re-spend). `generate.py`'s `SYSTEM_PROMPT` usage is unchanged, with
  a comment documenting the real decision (same discipline as every other
  post-closure change). Full numbers and every spot-checked case:
  `data/eval/prompt-comparison-report.md` and `reports.md`, 2026-07-25.

**Known gap, now fixed by this update:** this file's own headline
snapshot said "ingestion CLOSED, retrieval is next" from 2026-07-20 all
the way through the retrieval phase closing (2026-07-23) and the
generation phase being built and verified (2026-07-24) — only individual
file-listing bullets and Section 7 entries were kept current in that
window, not this section's opening framing or the "Last updated" date
itself. Caught 2026-07-23 while preparing for the evaluation phase. Same
category of drift Section 3/6 of the root workspace `CLAUDE.md` already
warns about — worth a standing habit of checking this section's own
opening paragraph against Section 7's latest entries, not just trusting
that keeping Section 7 current is sufficient on its own.

Project folder now also contains:
- `docs/archituecture.md.docx` — frozen architecture, now **v1.9**
  (amended 2026-07-11 via ADR-0001–0004; amended 2026-07-20 via
  ADR-0005–0008; amended 2026-07-24 via ADR-0009 — see Section 5 and
  `docs/adr/README.md`).
- `docs/ingestion-design.md` — pipeline reference, synthesizing the
  architecture plus all ADRs relevant to ingestion, with a diagram,
  updated 2026-07-20 for ADR-0007/0008's new artifacts
  (`corpus/validation-results.json`, `corpus/derived-checksums/
  {org}.json`, `.pages.json` sidecars, `reconcile.py`).
- `docs/retrieval-design.md` — pre-implementation design reference for
  `src/retrieval/`, written 2026-07-22 before that code existed. Phase now
  CLOSED (implemented, evaluated, default method recorded) — this doc
  is historical design reference, not a live status page; see this
  section above and Section 7 for the real outcome.
- `docs/generation-design.md` — pre-implementation design reference for
  `src/generation/`, written 2026-07-24 before that code existed. Phase
  now built and smoke-tested — same historical-reference relationship
  to Section 1/7 as `retrieval-design.md`.
- `docs/evaluation-design.md` — written 2026-07-23, revised same day after
  a second review. Pre-implementation design reference for
  `src/evaluation/`, mirroring `retrieval-design.md`/`generation-design.md`'s
  shape exactly. Phase now built and real-run (2026-07-24) — this doc is
  historical design reference, not a live status page; see Section 1
  above and `reports.md` for the real outcome. Full design detail in that
  file and both
  `docs/adr/0010-citation-judge-protocol-and-contradiction-test-gap.md`
  and `docs/adr/0011-claim-level-precision-and-judge-validity-fallbacks.md`;
  both Opus consult transcripts were meant to be in `decisionlog.md`,
  2026-07-23, but that file was found to be completely absent when this
  phase went to add its own entry — see `reports.md` Section 0, 2026-07-24.
- `docs/licensing.md` — per-organization source licensing findings
  (Freedom House permission request still pending a reply — see Section 4).
- `docs/corpus-inclusion-rubric.md` — concrete criteria for the semantic
  review stage (topic relevance, coverage contribution).
- `docs/readme-plan.md` — **new, 2026-07-24.** Section-by-section README
  rewrite spec (ADR-0012 Decision 4), mapping Alexey Grigorev's
  README-structure article onto this project's real content per section,
  flagging what's blocked on Tier 2/3 build items. Plan only — `README.md`
  itself hasn't been rewritten yet.
- `docs/PROJECT_CONTINUITY.md` — this file.
- `docs/data_governance.md` — governance policy.
- `docs/adr/` — **twelve** ADRs (see Section 5), plus `README.md` (process +
  example trigger thresholds).
- `pyproject.toml` / `uv.lock` — Python dependencies declared and locked;
  updated for retrieval's `fastembed`/`minsearch`/`numpy` additions.
- `src/ingestion/` — seven modules (six pipeline stages + `reconcile.py`),
  all real-corpus tested as of the 2026-07-20 re-run.
- `src/retrieval/` — four modules (`embed.py`, `search.py`,
  `ground_truth.py`, `evaluate.py`), all real-corpus tested, phase closed
  2026-07-23.
- `src/generation/` — three modules (`prompts.py`, `generate.py`,
  `citations.py`), real-smoke-tested against the real corpus and a real
  API key, 2026-07-24. `reports.md` (repo root) holds the verbatim
  smoke-test transcript.
- `src/evaluation/` — four modules (`run_answers.py`, `judge.py`,
  `contradiction_search.py`, `evaluate_generation.py`), real-run against
  the real corpus and a real API key, 2026-07-24 (122 questions, 481
  claims judged). `reports.md` (repo root, same file, overwritten for this
  phase) holds the verbatim real-run transcript and cost accounting.
- `corpus/sources/*.yaml` (four orgs), `corpus/CORPUS_VERSION`,
  `corpus/acquisition-log.md`, `corpus/manifest.csv`,
  `corpus/checksums.sha256`, `corpus/validation-report.md`,
  `corpus/validation-results.json` (ADR-0007),
  `corpus/derived-checksums/freedomhouse.json` (ADR-0007) — all
  generated/current as of the 2026-07-20 real pipeline run.
- `data/raw/`, `data/processed/` (including `.pages.json` sidecars for all
  13 PDF-sourced documents, ADR-0008), `data/metadata/`, `data/chunks/`
  (chunk records carry a `"pages"` field), `data/index/` (retrieval
  vectors + `index_metadata.json` stamp), `data/eval/`
  (`ground_truth.json`, `ground_truth_filtered.json`,
  `default_method.json`, `eval_supplement_questions.json`,
  `generation_results.jsonl`, `judgments.jsonl`,
  `contradiction_search_results.json`, the judge-calibration/deployment
  review-sample CSVs, `generation-evaluation-report.md`) — real output at
  each stage; most of `data/` doesn't sync into the Cowork mirror
  regardless of git status (see the repo's own `sync.sh`), and the
  evaluation-phase files carrying real chunk excerpts
  (`generation_results.jsonl`, `judgments.jsonl`,
  `contradiction_search_results.json`, the `*_full.csv` review samples)
  are additionally gitignored for licensing reasons, same as
  `data/chunks/` — see `.gitignore` and `reports.md`, 2026-07-24.

**Not started yet:** interface, monitoring, containerization, and
`pipeline.py`'s sibling utility `check_drift.py`
(still correctly deferred — no corpus version change yet to detect drift
against). Also not started: growing the corpus further — 35 documents was
judged sufficient to close the ingestion phase and move on, per Sam's own
call (see Section 7); the architecture's 40-60 document target was a
planning estimate, not a hard gate on advancing.

**Two unrelated version numbers, don't conflate them:** the architecture
document has its own revision version (`Document version`, now v1.8,
incremented once per ADR — a tracking number for the *document itself*).
Separately, the architecture's own content defines a corpus-scope version
("v1" sources: OONI/Access Now/CIPESA/Freedom House; "v1.1" deferred
addition: Netblocks/Citizen Lab — a scope milestone for the *corpus*, set
by the architecture, not by ADRs). "The architecture is at v1.8" and "the
corpus is still v1, not yet v1.1" are both true at the same time and mean
different things.

**What is decided and stable:** the architecture (now v1.9, "Approved.
Future changes via ADR only.") — scope (Kenya, Uganda, Tanzania, Ethiopia,
Rwanda; **2022–2026**, extended from 2022–2025 by ADR-0006), sources
(OONI, Access Now, CIPESA, Freedom House for v1; Netblocks + Citizen Lab
deferred to v1.1), pipeline shape (`acquire.py` → `extract.py` →
`validate.py` → `metadata.py` → `chunk.py`, plus on-demand
`reconcile.py`), doc ID scheme (`{org}-{country_iso2}-{year}-{slug}`), and
the core acceptance principle: every answer must cite sources,
thin/contradictory evidence must be flagged, not smoothed over. Refined by
nine ADRs since the original freeze (a tenth, ADR-0010, is an evaluation
methodology decision that doesn't touch the architecture document itself
— see below): tiered (not uniform) validation routing, a `lifecycle`
metadata block for supersession, a `corpus_version` stamp on chunks for
drift detection, a `license` field, an explicit disclosure of the
English-only corpus limitation, a content-checksum mechanism for
CDN-served HTML, the 2022–2026 window extension, four pipeline data-flow
consistency fixes, page-level citation provenance for PDF-sourced chunks,
and (ADR-0009, v1.8→v1.9) the index-only `[n]`-marker generation citation
protocol plus the split mechanical-thin-evidence/prompted-contradiction
design. See `docs/ingestion-design.md`, `docs/retrieval-design.md`,
`docs/generation-design.md`, and `docs/evaluation-design.md` for the
per-phase synthesized picture.

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
- **Architecture decisions**: `docs/adr/` — ten exist as of 2026-07-23.
  Deliberately not re-listing all ten here (that's exactly the
  duplication-drift this project's documentation-consistency discipline
  warns against) — see `docs/adr/README.md`'s own Status section for the
  current, authoritative list and count; that file is updated every time
  a new ADR lands, this line is not. ADRs are
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

- **DONE, 2026-07-25: re-ranking best practice — ablation run for real,
  Tier 1 item closed.** `search.py` gained a `boost_country: bool = True`
  parameter (default True, shipped behavior unchanged) so `_detect_countries`
  can be disabled per-call; `evaluate.py` gained `run_reranking_ablation()`
  and a `--rerank-ablation` CLI flag. Real run against the 101-question
  filtered ground truth (note: the prompt that specified this task said
  "130-question set" — a stale figure from before the set was later
  re-run to 150 and mechanically filtered to 101; corrected before running,
  confirmed with Sam). Metadata coverage: 100% (3,783/3,783) chunks carry
  non-empty `countries` — the flagged demotion-risk regression is
  negligible in this corpus. On the 65-of-101 firing subset: Hit Rate
  0.631→0.646, MRR 0.266→0.269, 3 wins/0 losses/62 ties (arm c vs b,
  per-question). Full-set (diluted): 0.644→0.653 / 0.270→0.272. Arm (c)'s
  full-set numbers exactly match the existing `evaluation-report.md`
  hybrid(k=10) row (0.653/0.272/n=101) — a real cross-check that the
  ablation harness genuinely reproduces shipped behavior. Bit-identical
  assertion (arms b/c, non-firing subset) passed with zero mismatches, no
  fix needed. Provenance checked: ground truth predates the boost
  (generated+reviewed 2026-07-22, boost added 2026-07-23,
  `ground_truth.py` never calls `search()`) — no circularity risk.
  Small, real, positive result, zero regressions found; kept as default.
  Full report: `data/eval/reranking-ablation-report.md`. README's
  Evaluation/Retrieval and Decisions-and-trade-offs sections updated with
  the real numbers.
- **NEW, 2026-07-25: README Tier 1 pass done.** `README.md` rewritten with
  real content per `docs/readme-plan.md` Stage 1 — title/description
  (fixed the stale 2022–2025 date range), problem, architecture diagram,
  project structure, decisions/trade-offs, data/config (OONI disclosure
  included), retrieval half of evaluation, full limitations list. Testing
  and CI/CD sections state their real absence (checked directly — no
  `tests/`, no `.github/workflows/`) rather than being silently omitted.
  **DONE, 2026-07-25: Demo section written for real.** Pulled question
  `general-0094` ("What surveillance tools is the Rwandan government
  known to use?") from `data/eval/generation_results.jsonl` — a
  `general`-category, non-refusal, well-corroborated answer (4 documents,
  2 orgs). All 8 citation markers ([1][2][3][5][6][8][9][10]) spot-checked
  by hand against the real chunk text in `data/chunks/` before
  publishing — every claim genuinely traces to its cited excerpt,
  including [9]'s two distinct claims (SIM registration, 2021 Uganda
  malware targeting) both confirmed in the same CIPESA chunk. One nuance
  the answer doesn't surface (found during spot-checking, not a citation
  error): marker [5]'s own excerpt also notes NSO Group said Rwanda
  hasn't been a client since 2021, per Citizen Lab — disclosed in the
  README rather than smoothed over, and consistent with the 0.879 (not
  1.0) claim-precision score. Sources list pulled via the real
  `citations.render_sources()` call, not hand-typed. **Still open:**
  Monitoring, Deployment, the final Quickstart run command,
  Self-evaluation, and Future work (the last two deliberately held for
  submission time).
- **DONE, 2026-07-25: LLM evaluation's rubric gap actually closed —
  Prompt A/B comparison run for real (ADR-0012 Decision 2).** See the
  Evaluation entry in Section 1 above for the full real-run detail
  (`src/evaluation/compare_prompts.py`, stratified 40-question subset,
  retrieval held fixed, judged by the unmodified `judge.py`). Real
  result: **Prompt A won and stays the default** — Prompt B (the
  evidence-first hypothesis) measured *worse* on citation precision
  (0.869 vs 0.893) with a concrete, spot-check-confirmed mechanism
  (marker misattribution across adjacent overlapping chunks), not a
  cherry-picked or flattering outcome. `generate.py` updated with a
  comment documenting the decision (no functional change, since the
  existing prompt already won). README's LLM evaluation subsection and
  Decisions-and-trade-offs section updated with the real numbers.
  **DONE, 2026-07-25: processed corpus shipped as a tiered release
  artifact (ADR-0013)** — see the Ingestion entry above in this section
  for the full real-run detail (rehydrate.py, the acquire.py bug fix,
  the release build). README's Data and configuration section updated
  with the real tiered description.
- **NEW, 2026-07-24: rubric-driven completion plan in force (ADR-0012) —
  the real punch list for the ~17 days to the confirmed 2026-08-11 02:00
  deadline.** In priority order: (1) README rewrite per
  `docs/readme-plan.md` — Problem description 1→2, half of Reproducibility;
  (2) ship the processed corpus/chunks + disclose the OONI 429/manual-
  acquisition constraint explicitly; (3) label + evaluate the existing
  `search.py` country re-rank as the rubric's re-ranking best practice;
  (4) fix LLM evaluation from 1/2 to 2/2 — build Prompt B (evidence-first,
  explicit thin-evidence abstention), judge it against the current Prompt A
  with the existing claim-level judge on a stated subset, report both, pick
  a winner, make it `generate.py`'s new default; (5) Streamlit interface +
  thumbs up/down feedback (Interface 0→2, Monitoring 0→1 together); (6)
  5-chart monitoring dashboard; (7) docker-compose for everything; (8) if
  time allows past 2026-08-02: cloud deployment (2-point bonus + the
  highest-value portfolio signal), then query rewriting. **Hard gate:
  everything worth 2 points done by 2026-08-02, then 08-03–05 is a
  clean-clone reproducibility dry run, 08-06–07 is buffer only.** Full
  reasoning and the complete Opus 5 consult transcript in `decisionlog.md`
  and ADR-0012, both 2026-07-24.
- **NEW, 2026-07-20: end-of-ingestion-phase Opus+Fable review complete —
  both recommend moving to the next phase after a short pre-flight fix
  list, not a rebuild.** Six independently-converged findings (highest
  priority first): (1) seed `langdetect` (`DetectorFactory.seed = 0`) —
  currently non-deterministic on the code-switched text ADR-0002 treats
  as normal; (2) `metadata.py` re-implements validation instead of
  consuming `validate.py`'s output — two independent computations of the
  same fact; (3) ADR-0005's stated content-drift-routes-to-Tier-2 design
  isn't implemented — `extract.py`'s content_sha256 mismatch only prints
  to stderr; (4) no reconciliation check across the four places corpus
  state lives (source YAMLs, manifest, acquisition-log, metadata dir) —
  a hand-edit typo in `INCLUDED_HEADING_RE`'s em-dash match, or a
  transient acquire.py failure, can silently drop a document from one
  list while it persists in another; (5) `write_yaml_field()`'s regex
  YAML surgery is the most fragile code in the pipeline, solving a
  problem that wouldn't exist if derived checksums lived in a separate
  file instead of being written back into the declared source YAML; (6)
  **most mission-relevant**: `extract_pdf_text()` discards page
  boundaries, so no chunk can be cited back to a specific page —
  cheap to fix now, expensive after chunking/embedding freezes. Also
  flagged, one model each: `chunk.py` freezes `lifecycle.status` into
  every chunk at chunk time, so a superseded document's chunks never
  reflect that unless manually re-chunked (tension with ADR-0003's own
  retrieval-time filter design); Freedom House's 46%-of-corpus
  concentration compounds with it being the one org with unresolved
  licensing; no stated policy for named individuals (activists/
  journalists) appearing in report content. Full detail in
  `decisionlog.md`, 2026-07-20. **Sam's call which of these to act on
  before starting retrieval/embedding** — none are blocking per either
  model's own bottom line, but (1), (3), and (6) are the cheapest-now/
  most-expensive-later group.
- **UPDATE, 2026-07-20: Sam's call was all six, before the next phase —
  all six now implemented in `src/ingestion/*.py`, code complete and
  smoke-tested, not yet run against the real 35-document corpus.**
  ADR-0007 (findings 2, 3, 4, 5) and ADR-0008 (finding 6) written and
  accepted first (both Opus-consulted); finding 1 (langdetect seeding)
  needed no ADR, treated as a pure bug fix. Implementation, in order:
  `acquire.py` (new `corpus/derived-checksums/{org}.json` storage +
  `resolve_stable_baseline_sha256()` migration path for existing
  Freedom House hashes), `extract.py` (`extract_pdf_text()` now returns
  page breakpoints + writes `.pages.json` sidecars; content-drift now
  also appends to `acquisition-log.md`; self-migrating re-extraction for
  any pre-ADR-0008 `.txt` with no sidecar yet), `validate.py`
  (`DetectorFactory.seed = 0`; new `corpus/validation-results.json`
  machine-readable output; content-drift now a real Tier 2 flag),
  `metadata.py` (`build_derived()` no longer calls `langdetect` at all —
  reads `validate.py`'s results, fails loudly on a missing entry),
  `chunk.py` (new `"pages"` field per chunk, resolved via
  `src/ingestion/pages.py`), and a new standalone `reconcile.py`
  (four cross-surface agreement checks, on-demand, not wired into
  `pipeline.py`'s automatic stages).

  **Verified via a synthetic-corpus smoke test** (Cowork sandbox,
  monkeypatched path constants, a real 2-page PDF via `reportlab` with
  a deliberately blank middle page, plus one HTML doc for a mocked
  `raw_bytes_stable: false` org) before handing off for a real run —
  confirmed: (a) the blank page is correctly excluded from breakpoints
  and true PDF page numbers survive the skip (`[1, 3]`, not `[1, 2]`);
  (b) a mutated HTML doc's `content_sha256` mismatch appends to
  `acquisition-log.md` *and* shows up as a `validate.py` Tier 2 flag,
  not just a stderr print; (c) `metadata.py`'s written
  `validation_warnings` visibly carry the drift flag through from
  `validate.py`'s own output, confirming the single-source-of-truth
  fix; (d) chunk records get real `"pages": [1, 3]` for the PDF doc and
  `"pages": null` for the HTML doc; (e) `reconcile.py` reports clean on
  a consistent fixture, then correctly catches both an
  included-vs-metadata and a metadata-vs-chunks disagreement after a
  metadata file was deliberately deleted mid-test. Full driver script
  not kept (temporary, `/tmp` only) — this paragraph is the record of
  what it verified.

  **DONE, same day — real pipeline re-run confirmed clean.** Claude Code
  ran `pipeline.py --all` + `reconcile.py` against the real corpus.
  Result, independently re-verified from the Cowork side by reading the
  pushed `corpus/validation-results.json` (35 entries, 0 drifted),
  `corpus/derived-checksums/freedomhouse.json` (16 entries, every one
  with both `sha256` and `content_sha256`), `corpus/acquisition-log.md`
  (0 `content-drift flagged` lines), and `corpus/manifest.csv` (36
  lines = 35 docs + header) directly, not just trusting `reports.md`'s
  prose: **35 documents, 3,783 chunks — both exactly match the
  pre-fix baseline, zero content-drift, `reconcile.py` clean.** All 13
  PDF-sourced documents (4 Access Now + 9 CIPESA) forced through
  re-extraction as designed and got real `.pages.json` sidecars; all 16
  Freedom House documents' pre-ADR-0007 `sha256`/`content_sha256`
  baselines migrated into `corpus/derived-checksums/freedomhouse.json`
  cleanly, once each. One minor process gap, not a data problem:
  `reports.md`'s own final "standing-rule verification" section was
  left as an unfilled stub (the read-back-after-push step the WSL
  CLAUDE.md requires) — covered by the independent Cowork-side
  verification above instead, but worth a note back to the WSL side
  next time this comes up, since the whole point of that rule is not
  needing a second party to catch it. **Ingestion phase is clean.
  Ready for retrieval/embedding.**
- **DONE, 2026-07-20: two Tanzania OONI documents acquired, validated,
  Included, pipelined — corpus now at 35 documents / 3,783 chunks.**
  Neither new document flagged as a near-duplicate of topically
  overlapping existing entries (LGBTIQ report vs. platform-blocking TZ
  entries; Aug 2024 Twitter/X block vs. the existing 2025 entry) —
  confirms genuinely distinct content. One real find worth remembering:
  the Twitter/X incident extracted to 514 words, notably lower than the
  ~750 estimated during research — Claude Code checked the actual
  extracted text (not just the number) and confirmed it's a complete,
  non-truncated write-up, just a naturally short OONI Findings piece.
  Per-org: Access Now 4 (668), CIPESA 9 (1,299), Freedom House 16
  (1,595), OONI 6 (221). Rwanda's zero-OONI-coverage gap stands
  confirmed as a real source gap, not pursued further. See
  `decisionlog.md`, 2026-07-20, for detail.
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
  analysis; the still-open constraint is **no public-facing redistribution
  of Freedom House content — through the CLIO API boundary or any other
  channel, including this project's own GitHub Release** — until permission
  is actually confirmed, not just requested. **Corrected 2026-07-25
  (ADR-0013):** this line previously narrowed the constraint to
  "CLIO-facing redistribution" only, which didn't match `docs/licensing.md`'s
  actual broader wording — a real documentation-drift bug, caught before it
  caused an actual mistake (the corpus-release task), not after. A follow-up
  email to Freedom House was sent the same day (twelve days of silence on
  the original request).
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
- **RESOLVED, 2026-07-22 — retrieval-layer storage decided.** In-memory,
  persisted-to-disk vectors (`data/index/vectors.npy` + a
  `index_metadata.json` stamp), not a standalone vector database —
  matches the course's own explicit allowance for in-memory/lightweight
  stores and the architecture's "no infrastructure beyond what's
  necessary" principle. Full design in `docs/retrieval-design.md`.
- **UPDATE, 2026-07-22, later same day: `embed.py` succeeded against the
  real corpus — 3,783 chunks embedded, `data/index/` built.** A real
  WSL/VS Code disconnect incident preceded this (two failed attempts,
  diagnosed via Opus as WSL2 memory pressure from leftover VM state that
  `wsl --shutdown` alone cleared, 90%→45% memory drop confirmed in Task
  Manager) — fixed with a `.wslconfig` memory cap plus a smaller,
  progress-printing batch size in `embed.py` itself. Clean run after
  that: `[ok] embedded — shape (3783, 384)`, all three index artifacts
  written. Full incident detail in `decisionlog.md`, 2026-07-22. Next:
  `ground_truth.py`, then Sam's mandatory circularity review before
  `evaluate.py`.
- **UPDATE, 2026-07-22, later same day: `ground_truth.py`'s first real run
  hard-failed on a wrong model name, fixed, re-run succeeded clean.**
  `LLM_MODEL` was hardcoded to `gpt-4o-mini`, which Sam's OpenAI
  project doesn't have enabled (403 `model_not_found` on every call, ~130
  identical failures before Sam interrupted the run). Root cause found by
  checking `LLM-ZOOMCAMP-2026-main.zip`'s real course code directly
  (`rag_helper.py`, `evaluation_utils.py`) — both use `gpt-5.4-mini`,
  which Sam had deliberately set up for lower credit usage. Fixed
  `LLM_MODEL = "gpt-5.4-mini"`; no other retrieval-phase file calls an
  LLM. Also added a fail-fast guard (aborts after 3 consecutive identical
  failures instead of burning through the full sample) so a future
  systemic account/model issue surfaces immediately. Re-run succeeded:
  130/130 questions generated, `data/eval/ground_truth.json` +
  `ground_truth_review_sample.json` (25 pairs) both written cleanly.
  **Known, accepted gap:** the `ooni_methodology` stratum sampled 0/20 —
  confirmed via `corpus/sources/ooni.yaml` that all 6 OONI documents in
  the corpus are incident/country reports, not a dedicated methodology
  page (one was named in the yaml's own acquisition-scope comment but
  never actually acquired). Sam's decision: leave it rather than reopen
  the closed 35-document ingestion phase to backfill one document.
  Documented in `docs/retrieval-design.md`'s `ground_truth.py` section —
  `evaluate.py`'s per-slice report will correctly show this stratum as
  0-sample, expected, not a bug. Full detail in `decisionlog.md`,
  2026-07-22. **Next, required before `evaluate.py`:** Sam's manual
  circularity review of the 25-pair sample — not yet done.
- **UPDATE, 2026-07-22, later same day: review sample itself was
  unusable, fixed.** The 25-pair `ground_truth_review_sample.json` had
  no chunk text attached — impossible to judge "does this question echo
  the passage" without the passage. Found when Sam pasted the sample
  back for review. `ground_truth.py` now attaches `chunk_text` to each
  reviewed pair (`write_review_sample()`), and a new
  `--regenerate-review-sample` flag rebuilds the sample from the
  existing `ground_truth.json` for free (no OpenAI calls, same seed —
  identical 25 pairs, just enriched). **Not yet re-run.** Next: Claude
  Code runs `--regenerate-review-sample`, then Sam does the actual
  circularity review against real passage text.
- **UPDATE, 2026-07-22, later same day: Sam's manual review done —
  found a real classify_category() bug AND a real circularity-rate
  problem, both requiring a decision before `evaluate.py`.** (1) A
  case-sensitivity bug (`chunk["organization"] == "ooni"` vs. the real
  `"OONI"` value) meant `ooni_methodology` could never populate on any
  run, contradicting the earlier "genuine corpus gap, accept it"
  decision — fixed (`.lower()`), but that earlier decision is now
  superseded, not confirmed; needs a fresh run to actually know if
  methodology content exists. (2) ~20%+ of the 25-pair sample showed
  severe circularity (near-verbatim phrase lifts) despite the
  paraphrase-only prompt instruction, plus 3 uses of explicitly-forbidden
  self-referential phrasing ("according to this passage"), plus 2
  footnote-dominated chunks producing possibly-ungrounded questions.
  Full detail in `decisionlog.md`. **Not yet decided:** whether to
  strengthen `QUESTION_SYSTEM_PROMPT` and fully re-run `ground_truth.py`,
  or proceed with the current 130 questions as-is with caveats. Blocking
  `evaluate.py` either way until Sam decides.
- **UPDATE, 2026-07-22, later same day: full re-run (150 questions,
  strengthened prompt) done, second review done, mechanical filter
  built and run, decision made — clear to run `evaluate.py`.** Full
  chain: (1) full regenerate confirmed the `classify_category()` fix —
  `ooni_methodology` went 0/20 → 20/20, total 150 questions (matches
  `STRATUM_TARGETS` sum now that all strata populate). (2) Second manual
  review: self-referential phrasing fully eliminated, verbatim-lift
  circularity roughly halved, but a new pattern (echoing a passage's own
  survey-question/citation-title header) emerged at similar volume —
  still ~24% flagged overall. (3) Decided against a third re-run;
  instead added `src/retrieval/filter_ground_truth.py` (mechanical
  4+-word phrase-overlap filter, proper nouns/dates exempted) plus one
  more prompt rule for future runs. (4) Filter ran: 97/150 kept, 53
  dropped — more aggressive than the ~24% estimate (some false
  positives from the exemption logic being too strict), and
  disproportionately hit the just-fixed `ooni_methodology` stratum (10
  of its 20 dropped). Sam's decision: accept 97/150 as final rather than
  hand-review the OONI drops or re-engineer filter precision — the
  asymmetric risk (dropping a borderline-fine question costs less than
  keeping a genuinely circular one) favors proceeding. Full reasoning in
  `decisionlog.md`. **Next: hand off `evaluate.py` to Claude Code** —
  the last step of the retrieval phase before a human (Sam) picks the
  default search method from the per-slice report.
- **UPDATE, 2026-07-22, later same day: real evaluation results in —
  no method wins uniformly.** `evaluate.py` ran clean against 97
  questions (22/11/64 across multi_country/ooni_methodology/general).
  Aggregate: hybrid beats both solo methods clearly (best ~k=10-30, Hit
  Rate 0.649-0.660 vs. text 0.536 / vector 0.515). Per-slice split:
  `general` and `ooni_methodology` both strongly favor hybrid
  (`ooni_methodology` Hit Rate up to 0.909 with hybrid vs. 0.636 text —
  though n=11 is thin, read directionally); `multi_country` is the
  exception — plain text has the best MRR (0.267), beating every hybrid
  k and vector outright. RRF k sensitivity isn't uniform either:
  `multi_country` gets *worse* as k increases past 1, opposite of the
  other two slices. Full numbers in `decisionlog.md`. Also fixed a real
  cosmetic bug Claude Code's own verification caught: the report's own
  header text hardcoded `ground_truth.json` even when it correctly
  loaded from `ground_truth_filtered.json` — `load_ground_truth()` now
  returns the actual path used. **Next, final step of retrieval phase:**
  Sam picks the default method (`evaluate.py --set-default ...`) — not
  yet decided.
- **UPDATE, 2026-07-22, later same day: default method decided —
  hybrid, RRF k=10.** Chosen over k=30 for best-or-near-best MRR across
  all three slices (not just aggregate), closest any hybrid config gets
  to text's real `multi_country` MRR advantage while keeping hybrid's
  clear wins elsewhere. That `multi_country` gap (no config beats
  text's MRR there) is documented as a known limitation, not resolved —
  worth revisiting if a later phase adds query-type-aware routing. Full
  reasoning in `decisionlog.md`. **Retrieval phase is now functionally
  complete** — implementation, evaluation, and the default-method
  decision are all done, pending the mechanical `--set-default` command
  recording it to `data/eval/default_method.json`. Next real phase after
  that: generation (citation-grounded answer synthesis), not started.
- **UPDATE, 2026-07-22, later same day: `default_method.json` confirmed
  written and verified — retrieval phase is fully closed.** Claude Code
  read the file back directly (not assumed from the command's success
  message): `{"method": "hybrid", "rrf_k": 10}`, exact match. Nothing
  else pending on retrieval implementation/evaluation/decision-making.
  **Open item, flagged not started:** Sam asked why aggregate MRR is
  low (~0.275 best case); working hypothesis is that most of the loss
  comes from the ~35% total-miss rate (not poor ranking among actual
  hits), plausibly caused by 50%-overlapping chunking scored against a
  strict single-correct-chunk-id ground truth — a retrieved neighbor
  chunk covering the same passage would count as a full miss. Also
  named: today's own circularity-hardening made the eval set genuinely
  harder by design, plus the deliberate small-local-embedder and
  no-reranker tradeoffs from the design phase. Diagnostic script to
  test the overlap hypothesis not yet built — Sam wants to hold off and
  revisit explicitly, not proceed unprompted. Full detail in
  `decisionlog.md`.
- **UPDATE, 2026-07-22, later same day: full Opus consult on the
  retrieval phase done — verdict "honest, not alarming," concrete
  prioritized fixes proposed, none started yet.** Opus pushed back on
  the "low ceiling" framing: the ~0.66 aggregate Hit Rate looks low
  only against soft/circular ground truth, and this project
  specifically hardened its GT against that shortcut this session — a
  lower number on a harder test isn't evidence of worse retrieval.
  Confirmed the HR/MRR-gap math: ranking-among-hits is fine (rank ~2-3
  when found), the real problem is the ~35% miss rate (recall, not
  ranking). My overlap-chunking hypothesis judged plausible but
  probably not dominant (~1/3 to 1/2 of misses at most) — explicit
  instruction to measure via a neighbor-aware relaxed Hit Rate (credit
  a hit if the gold chunk or its same-doc ±1 neighbor appears in
  results) rather than argue it further. Ranked other suspects:
  minsearch's plain-TF-IDF text backend (real, moderate drag, not
  BM25), the ground-truth filter's own ~35%-drop false-positive rate
  (now itself adding eval noise, shrank `ooni_methodology` to n=11),
  embedding model choice (ranked LOW — bge-small is "near the top of
  MTEB for its size class," not the bottleneck). `multi_country`'s
  favor-text/worse-with-higher-k pattern judged a genuinely distinct,
  mechanistically-explained problem (entity-dense proper-noun matching
  where TF-IDF has a real edge over dense embeddings) — fix isn't a
  different k, it's using the `countries` metadata already on every
  chunk to filter/boost the candidate pool at query time (not yet
  built — only `lifecycle_status` is filtered today). Prioritized,
  effort-ranked fixes proposed: P0 neighbor-aware Hit Rate (~1hr, do
  first), P1 country-metadata query filtering, P2 swap minsearch's text
  backend for real BM25, P3 optional bge-base upgrade, P4 manually
  rescue the filter's false-positive drops. Explicitly recommended
  AGAINST re-chunking, reranking, and HyDE for now — none earn their
  risk/effort before the Aug 10 deadline, and Opus's read is that
  reopening ingestion (which Sam had explicitly authorized considering)
  isn't actually where the leverage is. Recorded default (hybrid,
  k=10) unchanged — Opus said keep it pending P1. Full write-up in
  `decisionlog.md`. **Not yet decided: which of P0-P4 to actually
  build, if any — Sam's call, nothing started.**
- **UPDATE, 2026-07-22, later same day: Fable consult (phase-boundary
  spend) built on Opus's findings and found two real, code-verified
  bugs — both fixed same session.** Fable actually read `search.py`/
  `evaluate.py`/`filter_ground_truth.py` rather than reasoning from the
  brief alone. (1) The ground-truth filter's proper-noun exemption
  required every token in a 4-gram to be capitalized, so multi-word
  terms with lowercase connectors ("Freedom on the Net", "web
  connectivity test") were never exempt — likely the real cause of
  `ooni_methodology` losing half its questions to the filter, since
  methodology questions structurally can't avoid that vocabulary. Fixed
  in `filter_ground_truth.py` (function-word-aware exemption + a terms-
  of-art whitelist), smoke-tested against 4 known cases. (2)
  `search.py`'s `DEFAULT_RRF_K=60` constant silently disagreed with the
  actually-recorded decision (hybrid k=10) — any future caller not
  passing `rrf_k` explicitly would get the wrong default. Fixed:
  `search()` now reads `data/eval/default_method.json` at call time
  (same pattern as the existing corpus-freshness check), falling back
  to a renamed `FALLBACK_RRF_K` only pre-evaluation. Also expanded
  `evaluate.py` with neighbor-aware relaxed Hit Rate, HR@3/HR@5,
  bootstrap 95% CIs, and a new source-diversity@10 metric (ties
  evaluation to the project's own citation/thin-evidence-flagging
  priority, which single-gold Hit Rate is silent on). All new logic
  smoke-tested standalone; all three files compile clean. **Not yet run
  against the real corpus.** Declined re-chunking again (sharper
  argument: ground truth is keyed to `correct_chunk_id`, so re-chunking
  invalidates the whole eval harness, not just risks regressions).
  Merged priority order and full reasoning in `decisionlog.md`. Next:
  hand off to Claude Code — re-run the repaired filter against the
  original 150 questions, then re-run the expanded `evaluate.py`.
- **UPDATE, 2026-07-22, later same day: real corpus re-run in — the
  specific `ooni_methodology` hypothesis was tested and falsified; two
  genuinely new findings surfaced instead.** Claude Code diffed old vs.
  new dropped-question lists precisely rather than trusting the count:
  **all 10 `ooni_methodology` drops are identical before and after the
  exemption fix** — none were ever flagged on a proper-noun/term-of-art
  phrase, their flagged phrases are generic event/date descriptions
  ("2024 kcse exam period" etc.), a different failure mode the fix
  doesn't touch. The fix itself is correct and did rescue 4 unrelated
  genuine false positives (Anti-Terrorism Act, COVID-19, a film title, a
  report title) — just not the stratum it was hypothesized to fix. A
  residual gap also found: the Kenya "Freedom on the Net" question is
  still dropped, due to a possessive-`'s` tokenization offset, not
  covered by the whitelist. `ooni_methodology`'s thinness (n=11) stays
  accepted, now understood as possibly-legitimate filtering (OONI's
  event-specific reporting style shares generic phrasing with its own
  source text) rather than a fixable bug. **Two real findings did land:**
  (1) neighbor-aware Relaxed Hit Rate is 16.8pts above strict Hit Rate
  for the recorded default (0.812 vs. 0.644) — lands inside Opus's own
  "a third to half of misses" estimate, substantially confirming the
  overlap-chunking artifact is real, not a minor factor. (2) HR@3/HR@5
  are well below the HR@10 aggregate (0.366 / 0.465 vs. 0.644) — new,
  not predicted by either advisor, real signal for generation-phase
  chunk-count decisions. **Also new, not yet discussed with Sam:**
  text search shows meaningfully higher source-diversity@10 (1.59
  orgs/4.28 docs) than the recorded hybrid default (1.50/3.68) — a real
  tension between the Hit-Rate-optimal method and the project's own
  stated top safety priority (surfacing corroborating/contradictory
  sources), not weighed into the method decision yet. Aggregate
  Hit Rate/MRR essentially unchanged from the pre-fix run (0.644/0.270
  vs. 0.649/0.275 — within CI). Recorded default (hybrid, k=10) left
  unchanged. Full numbers and CIs in `decisionlog.md`. **Not yet
  decided: what to do about the source-diversity tension or whether to
  pursue P2 (country-metadata filtering)/P3 (BM25 swap) — Sam's call.**
- **UPDATE, 2026-07-22, later same day: diversity diagnostic run — the
  vector-backend hypothesis refuted too; real cause is RRF concentration
  on cross-backend agreement, not embedding smoothness.** Hybrid's
  top-10 doc set actually overlapped more with text's (29/101) than
  vector's (18/101) across the real 101 questions — the opposite of the
  predicted direction, 54/101 tied. Concrete examples show hybrid
  concentrating on the smaller set both backends independently agree is
  strong, which is usually a subset of *either* backend's own wider
  list, not a copy of vector's specifically. Read as a structural
  precision-for-diversity trade inherent to RRF fusion, not a defect in
  the embedding model. No code changed — read-only diagnostic, as
  instructed; Claude Code also correctly followed `sync.sh` over the
  handoff prompt's literal `git pull`/`git push` wording and flagged
  rather than pushing to GitHub directly, matching the established
  policy that only Sam pushes to the real remote. Full detail in
  `decisionlog.md`. **Not yet decided: whether this is worth addressing
  before the Aug 10 deadline, given it's an inherent RRF property
  rather than a bug — Sam's call.**
- **UPDATE, 2026-07-22, later same day: decided — build P2, defer the
  diversity tension to generation, P2 implemented and smoke-tested.**
  Sam's call: country-metadata boost is worth building now (small,
  both advisors converged on it, targets multi_country's real cause);
  the source-diversity tension is deliberately NOT retrieval-fixed —
  forcing extra sources into top-10 would dilute relevance where
  evidence genuinely concentrates in 1-2 docs, and "flag thin/
  single-sourced evidence" is already the generation phase's job per
  the architecture, not retrieval's. `src/retrieval/search.py`: new
  `_detect_countries()`/`_boost_by_country()` — a stable re-rank
  (matches promoted, nothing ever dropped) triggered only when a query
  names one of the 5 corpus countries; no-op otherwise. 5 smoke tests
  passed, compiles clean. **Not yet run against the real corpus.**
  Next: Claude Code re-runs `evaluate.py`, specifically checking the
  `multi_country` slice improves. Full reasoning in `decisionlog.md`.

**UPDATE, 2026-07-23: P2 run against the real corpus — implementation
verified correct, zero regressions, but the `multi_country` gap has a
different real cause than assumed, and P2 can't touch it.** Full
detail in `decisionlog.md`. Also: a benign stray file
(`docs/ziM3eRpl`, an orphaned docx-write temp artifact from
2026-07-20's architecture-doc editing, confirmed via matching
`docProps/core.xml` metadata against `archituecture.md.docx` — same
creator/timestamp, not a foreign or malicious file) surfaced in the
sync pull and was investigated and deleted on both sides, along with
the empty `archituecture-new.docx` leftover from the same incident.
- **UPDATE, 2026-07-24: generation phase designed and built same
  session — Fable consult, `docs/generation-design.md`, ADR-0009
  (v1.8→v1.9), `src/generation/{prompts,generate,citations}.py`, all
  smoke-tested, not yet run against the real corpus/API key.** Full
  design detail and a real docstring-vs-implementation bug caught
  during smoke-testing (fixed) are in `decisionlog.md`, 2026-07-24.
  Core mechanism: the LLM only picks `[n]` citation markers from
  numbered excerpts, never writes citation text itself — fabrication
  is structurally impossible, not just discouraged. Thin evidence is
  computed mechanically on the CITED chunk subset (not the retrieved
  one — a real correction to this project's own starting idea, made
  during the consult); contradictory evidence is prompt-instructed and
  left to the evaluation phase to verify. **Next: hand off to Claude
  Code for a real smoke run** — a few real questions, checking
  citations resolve to real pages and the sourcing footer fires
  sensibly, per Fable's own stated completion bar for this phase.
- **UPDATE, 2026-07-24: real smoke test in — clean, every mechanism
  verified against real source text, generation phase's completion bar
  met.** Four real queries, real corpus, real `gpt-5.4-mini` calls, exit
  0 each time. Citation accuracy (not just presence) checked directly
  against real chunk text — zero fabrications/misattributions found.
  The sourcing footer correctly distinguished all three real cases:
  single-org/multi-doc, single-org/single-doc (the strongest caveat,
  deliberately tested on a real thin topic), and multi-org/multi-doc.
  `unsupported_paragraphs` fired twice, both on harmless meta-commentary
  (not dropped claims); `invalid_markers` never fired; no
  metadata-lookup degraded path ever hit. Full detail in
  `decisionlog.md`, 2026-07-24. **Next real step: LLM evaluation**
  (the course's own next rubric item) — not started.
- **NEW, 2026-07-23: full documentation-sync pass, plus the LLM
  evaluation phase's design — ready for implementation next session,
  nothing built yet.** Requested by Sam directly: bring every project doc
  current, then prepare thoroughly for the evaluation phase so it can
  start immediately in a future session even if this one isn't available.
  Three things happened: (1) this file's own Section 1 snapshot and
  header date, caught genuinely stale (see the "Known gap, now fixed"
  note in Section 1 above) — the retrieval-close and generation-build
  events had been logged in Section 7 and `decisionlog.md` correctly, but
  never propagated up into this file's headline framing; fixed. (2)
  `docs/adr/README.md`'s Status section, also stale (still said "eight
  ADRs" after ADR-0009 shipped) — fixed, now correctly lists all ten.
  (3) The evaluation phase itself designed: `docs/evaluation-design.md`
  drafted first (mirroring `retrieval-design.md`/`generation-design.md`'s
  pre-implementation-reference pattern), then an Opus consult on four
  explicitly open questions (reuse-vs-fresh ground truth; LLM-judge
  protocol and self-judging risk; human-review sample size/
  stratification; how to test contradiction-handling given no confirmed
  real contradiction in the corpus). Two of the four crossed this
  project's "genuinely novel decision" bar and became
  `docs/adr/0010-citation-judge-protocol-and-contradiction-test-gap.md`
  — a per-citation, isolated-entailment LLM-judge protocol (3-way
  supported/partial/unsupported verdict, a stronger/different judge model
  for the human-reviewed calibration subset specifically, to
  structurally avoid self-preference bias rather than argue it away) and
  a firm decision **not** to fabricate a contradictory-evidence test case
  if a real one can't be found in the corpus — document the gap honestly
  instead, backed by a synthetic-fixture unit test of the mechanism only,
  kept structurally separate from real-corpus metrics. The other two
  questions resolved as refinements within already-open design space, no
  ADR needed: reuse the existing 97-question retrieval ground truth
  (`data/eval/ground_truth_filtered.json`) plus a small ~10-15-question
  labeled multi-chunk-synthesis supplement, and stratify human review by
  verdict (judge calibration) or by category (deployment review), not by
  a flat percentage. Full Opus transcript and reasoning trail in
  `decisionlog.md`, 2026-07-23. **No `src/evaluation/` code exists yet —
  the design is the deliverable of this pass, ready for a Claude Code
  handoff (prompt drafted, see below) whenever the next session starts
  implementation.**
- **UPDATE, 2026-07-24: LLM evaluation phase built and run for real —
  0.879 aggregate claim-level citation precision, one step short of
  fully closed.** `src/evaluation/{run_answers,judge,
  contradiction_search,evaluate_generation}.py` built and run against
  the real corpus, real OpenAI API, 122 real questions, 481 real claims
  judged. Full numbers, the judge-model fallback (`gpt-5.4` 403'd,
  `gpt-5.4-mini` used, self-judging disclosed), the contradiction-search
  result (none found in the real corpus, mechanism verified via
  synthetic fixture), and the refusal-slice review are all in Section 1
  above and `reports.md`, 2026-07-24 — not restated here. **A real
  process gap surfaced and was fixed**: the handoff prompt incorrectly
  asked Claude Code to update `decisionlog.md`, a file that structurally
  cannot sync to WSL (lives outside `repo/` by design) — Claude Code
  correctly refused to guess and reported the gap in `reports.md`
  Section 0 instead of fabricating an entry; the real decisionlog entry
  was written from the Cowork side afterward. **What's left before this
  phase is fully closed:** Sam fills in `human_verdict` in
  `data/eval/judge_calibration_sample_full.csv` (real chunk text
  included, local-only, gitignored), then runs
  `uv run python src/evaluation/evaluate_generation.py --score-review`
  for the confusion matrix / raw agreement / Cohen's κ-or-ADR-0011-fallback
  verdict. `data/eval/deployment_review_sample_full.csv` is separately
  ready for the deployment citation-precision review
  `evaluation_checklist.md` calls for, independent of the calibration
  step. **Known, deliberately-unfixed asymmetry, flagged for a future
  call:** `data/eval/eval_supplement_questions.json` (real, curated
  question-set substance, committed to the real git repo) never reaches
  the Cowork mirror via `sync.sh push`, since `push` excludes all of
  `data/` by design — unlike `corpus/sources/*.yaml`, a comparably
  curated artifact that does sync. Not fixed this pass; Sam's call
  whether it's worth a future revision.
- **UPDATE, 2026-07-25: human-calibration path changed twice, ended on a
  judge-prompt fix instead of more human review time.** Attempt 1: Sam
  found the full 65-row human read unsustainable, substituted an
  independent AI reviewer read (blind to the judge), and an Opus 5
  consult recommended a disagreement-only human read as the cheap
  alternative — implemented, but the real disagreement rate (45/63 rows,
  28.6% raw agreement) made the "cheap" subset not actually cheap.
  Attempt 2: Sam declined that too and asked why the disagreement was
  100% one-directional. A second Opus 5 consult, grounded in the real
  `judge.py` prompt, found a genuine protocol issue (the "partial"
  catch-all clause, and structural inability to verify negative/absence
  claims under isolated entailment) and recommended fixing the judge's
  prompt and re-running all 481 claims instead — adopted, ranked above a
  smaller human sample (explicitly advised against: too close to
  ADR-0011's own degenerate-κ case at this population's disagreement
  prevalence) and above stopping at a documented limitation (held in
  reserve for whatever gap remains after the fix attempt, not skipped
  outright). Empirical cross-check run before accepting the hypothesis:
  my own 52 "supported" verdicts from the original review were
  categorized by claim shape and handed to the fix's implementation for
  a real per-shape breakdown, not taken on Opus's word alone. **Judge-
  validity status: OPEN**, not yet run as of this update. Full transcripts
  in `decisionlog.md`, 2026-07-25 (two entries), ADR-0011's addendum.
- **UPDATE, 2026-07-25 (later still): judge rubric v2 run for real,
  adopted as the headline citation-precision result (ADR-0014).** The
  fix from the entry above was implemented, validated cheaply on the
  47-row disagreement subset first (gap narrowed 63-67% evenly across all
  three claim shapes, no overshoot found on spot-check), then re-run
  across all 481 claims. **Citation precision: 0.879 (v1) → 0.946 (v2)**,
  every category improved, 33/481 claims moved to "supported," 1 moved
  the other way (a defensible edge case on inspection). Sam chose 0.946
  as the headline reported number (offered three options directly, didn't
  default to one); 0.879 stays disclosed as the superseded original
  methodology. **Judge-validity against independent human judgment
  remains explicitly OPEN** — this closes "is the rubric sound," not "has
  a human confirmed this," and both statements must appear together
  wherever 0.946 is reported (README, `docs/evaluation-design.md`).
  Full numbers, the verbatim prompt diff, and per-category/per-shape
  breakdown in `reports.md`, 2026-07-25. **Separately, a real process gap
  found and fixed this pass:** this file's own headline snapshot and
  ADR-0011's addendum, both written earlier today, had been silently
  reverted by an un-pushed `sync.sh pull` — redone; see the "Known
  process gap" note at the top of this file.
- **UPDATE, 2026-07-22, later same day: `src/ingestion/chunk.py` itself
  fixed (Sam's call), not yet re-run against the real corpus.** The
  `chunking` block now gets stamped into `metadata` before any chunk
  file is written (new `stamp_chunking_block()`, called from inside
  `chunk_document()`), so every chunk file's own embedded
  `document_metadata` will carry `chunking` too, matching
  `data/metadata/{doc_id}.json` — previously it didn't. No ADR (a bug
  fix restoring already-documented intended behavior, same precedent as
  ADR-0007's langdetect-seeding fix). Smoke-tested on a synthetic
  fixture: chunk boundaries/pages/text unaffected, fully idempotent on
  rerun. **Retrieval code (`embed.py`/`ground_truth.py`) needs no
  changes** — it already reads the stamp from `data/metadata/` directly,
  which was already correct before this fix. Next: Claude Code re-runs
  `chunk.py` across the real 35-document corpus (cheap — no PDF
  re-extraction), then proceeds with the unchanged retrieval steps. Full
  detail in `decisionlog.md`, 2026-07-22 (third entry that date).
- **UPDATE, 2026-07-22, later same day: first real WSL run hard-failed as
  designed — root cause found and fixed, one issue flagged not fixed.**
  `embed.py` correctly hard-failed against all 35 real documents (not a
  partial subset). Root cause: a real bug in already-shipped
  `src/ingestion/chunk.py` — the `chunking.corpus_version` stamp
  (ADR-0003) never actually reaches chunk files' embedded
  `document_metadata`, only the separate `data/metadata/{doc_id}.json`
  (confirmed: zero of 3,783 real chunk files have a `"chunking"` key at
  all), plus a separate wrong assumption about `corpus/CORPUS_VERSION`'s
  real format (`"v1.0 2026-07-13"`, not a bare version string — never
  previously read programmatically by any script). Fixed in
  `src/retrieval/{embed,ground_truth,search}.py`: the stamp is now read
  from `data/metadata/{doc_id}.json` directly (cached per doc_id), and
  `CORPUS_VERSION` parsing takes only the leading token. Re-smoke-tested
  against a corrected synthetic fixture matching the real schema gap
  (including a deliberately-stale document) — confirmed correct.
  **Flagged, not fixed:** whether to also fix `chunk.py` itself (cheap
  re-run — no PDF re-extraction involved — but touches a phase already
  marked "closed, verified clean") is Sam's call, not blocking retrieval
  either way. Full detail in `decisionlog.md`, 2026-07-22 (second entry
  that date). Next: Claude Code re-runs from `embed.py` with the
  corrected code.
- **DONE, 2026-07-22: retrieval phase implemented, smoke-tested, handed to
  Claude Code — not yet run against the real corpus.** All four modules
  written in `src/retrieval/` (`embed.py`, `search.py`, `ground_truth.py`,
  `evaluate.py`), matching `docs/retrieval-design.md` exactly. Uses real
  library APIs confirmed by reading their actual source (`fastembed`'s
  `TextEmbedding.embed()`/`query_embed()`, `minsearch`'s `Index`/
  `VectorSearch` fit/search/save/load) — not assumed from memory. Every
  chunk-schema field access (`chunk_id`, `document_metadata.declared/
  lifecycle/chunking`) matches the real schema, read directly from
  `chunk.py`/`metadata.py`'s own source, not the earlier design doc's
  (slightly wrong) guess at the chunk_id format. Logic smoke-tested in the
  Cowork sandbox against a synthetic 4-chunk fixture with `fastembed`/
  `minsearch` stubbed out (their real installs need `huggingface.co`
  network access this sandbox doesn't have, and scipy's own download kept
  timing out here) — confirmed: RRF combine math, the corpus_version
  freshness hard-fail (both embed.py's and search.py's), category
  classification, stratified sampling with per-category caps, and
  evaluate.py's per-slice Hit Rate/MRR + `--set-default` all work
  correctly. `pyproject.toml` updated with `fastembed`, `minsearch`,
  `numpy`; `uv.lock` regeneration deferred to Claude Code (`uv sync` in
  WSL, where real network access exists). Next: Claude Code runs the real
  pipeline against the actual 3,783-chunk corpus (handoff prompt in
  `decisionlog.md`, 2026-07-22) — nothing run against real data yet.
- **DONE, 2026-07-22: retrieval phase design finalized, no code yet.**
  `docs/retrieval-design.md` written — phase named "retrieval" (embedding
  is one internal stage, not the phase name), module breakdown
  `embed.py` → `search.py` → `ground_truth.py` → `evaluate.py`, Opus
  design review complete (three fixes folded in: paraphrase-based ground
  truth to avoid circularity + manual spot-check, a
  corpus_version/embedding-model stamp on `data/index/` with a hard-fail
  on mismatch, and per-slice Hit Rate/MRR reporting so method selection
  isn't aggregate-only). Embedding model decided: `BAAI/bge-small-en-v1.5`
  (Xenova ONNX port) over the course's `all-MiniLM-L6-v2` — this corpus's
  1500-char chunks exceed MiniLM's 256-token window, real truncation
  risk; BGE is also trained specifically for asymmetric query/passage
  retrieval, a better task fit. RRF explicit in `search.py`'s hybrid
  backend, `k` swept in `evaluate.py`. Phase boundary stated explicitly:
  ends at a working, evaluated `search()` with a chosen default method;
  generation, LLM evaluation, reranking, and query rewriting are later,
  separate phases. Full reasoning in `decisionlog.md`, 2026-07-22. Next
  step: implementation of `src/retrieval/`, not yet started.
