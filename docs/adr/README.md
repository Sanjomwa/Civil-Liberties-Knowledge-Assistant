# Architecture Decision Records

Referenced by the frozen architecture doc (`docs/archituecture.md.docx`) but
did not exist until this scaffolding pass (2026-07-11). This directory is
where any deviation from the frozen v1.0 design gets recorded — no silent
changes to the approved architecture.

## When an ADR is required

Any time implementation departs from what `archituecture.md.docx` v1.0
specifies — a different extraction library, a changed chunking parameter, a
new data source, a pipeline stage reordered or added. If it's not written
down here, it isn't an approved deviation, regardless of what's in the code.

Not required for decisions that were already open per the architecture
(e.g., filling in something the doc left unspecified) — only for actual
departures from what it does specify.

## Format

Plain markdown, one file per decision, named `NNNN-short-title.md`
(zero-padded, sequential). Each ADR should cover:

- **Status** — proposed / accepted / superseded.
- **Context** — what prompted the deviation (e.g., "pdfplumber fails badly
  on Freedom House's PDF layout").
- **Decision** — what was chosen instead.
- **Consequences** — what this changes downstream, what it doesn't. May
  note that a follow-up artifact is implied (e.g., "this implies a
  `check_drift.py` script"), but don't use this section to track *whether*
  that follow-up has been built — ADRs are historical records and don't
  get revisited after acceptance, so a present-tense status claim here
  will silently go stale the moment the thing actually ships. Live build
  status belongs in `docs/PROJECT_CONTINUITY.md` Section 7. (Caught in
  ADR-0003, 2026-07-11, after the fact — worth getting right from the
  start on future ADRs.)
- **Opus consult** — this project's practice requires an independent
  advisor-model consult (a second, higher-capability model reviewing the
  proposed decision) before any ADR deviating from the frozen architecture
  is marked accepted. Note whether that happened and what it recommended. Not every
  ADR needs one — corrections and pure clarifications (see ADR-0004) don't
  cross the threshold; real design decisions do.
- **What would trigger a revisit** — every ADR should end with this,
  concretely. "Revisit if it stops working" is not calibration. See example
  thresholds below.

## Example trigger thresholds (resolves architecture-review item 9)

The architecture requires every ADR to state what would trigger a revisit,
but gave no worked examples of what a good threshold looks like versus
normal implementation variance. A few, so future ADRs have something to
calibrate against:

- **Extraction failure rate.** If more than ~15% of documents from a single
  organization fail extraction (`validate.py` Tier 1), that's a signal the
  extraction method (pdfplumber for that org's PDF layout) needs
  reconsidering — not a one-off document problem. A single failed document
  is normal variance; a cluster from one source is a design signal.
- **Corpus-size shortfall.** The architecture targets 40 documents minimum,
  60 at freeze. If acquisition + review is trending toward finishing below
  40 for the target countries/years, that's a trigger to revisit acquisition
  rules (e.g., loosening the "exclude data notes under 500 words" rule) —
  not a reason to silently ship a smaller corpus without a documented
  decision.
- **Chunk-size dissatisfaction.** The architecture already marks
  `chunk_size=1500/step=750` as provisional. A concrete trigger: if manual
  review of retrieval quality (once retrieval exists) shows chunks
  routinely cutting a citation-relevant sentence in half, or so large that
  a single chunk mixes multiple unrelated incidents, that's the signal —
  not "chunking felt arbitrary," which is too vague to act on.
- **Tier-2 human-review volume.** If ADR-0002's Tier 2 checks (language,
  length, near-duplicate) are flagging a large fraction of documents for
  human review — enough that it's clearly a bottleneck rather than an
  occasional judgment call — that's a signal to revisit the tiering or the
  underlying detection methods, not just push through the backlog.

These are starting calibration points, not hard rules — the point is that
"what would trigger a revisit" should name a number, a pattern, or an
observable condition, not just a feeling that something isn't working.

## Status

**Fifteen ADRs exist as of 2026-07-26.**
`0015-corpus-scope-prompt-card-and-behavioral-test-suite.md` — a real
user query ("what countries are under this corpus's scope?") surfaced a
genuine gap: the app answered from whatever was retrieved (a ~38-country
list from CIPESA's pan-continental reports) instead of the true 5-country
curated scope, because curation facts aren't stated in any document's
text. Fable consulted (Sam's explicit choice this instance) — **disagreed
with the blunt "5 countries only, say I don't know otherwise" fix Sam
first proposed**, since a hard country filter would strip real, cited,
useful comparative context and wouldn't fix the actual problem (a
category of question evidence-only retrieval can't answer). Adopted
instead: a small scope-card addition to `SYSTEM_PROMPT` plus a soft
out-of-scope-country rule, no retrieval changes, a new 25-question
behavioral test suite (`docs/behavioral-test-suite.md`), and a mandatory
full re-evaluation run since this touches the already-measured (0.946)
generation phase.

**Fourteen ADRs exist as of 2026-07-25 (later same day).**
`0014-judge-rubric-v2-headline-citation-precision.md` — the human-
calibration check ADR-0011 requires never happened as designed (an
AI-vs-AI substitute produced too high a disagreement rate to be a cheap
stand-in); a second Opus 5 consult found the disagreement was driven by a
real, confirmed defect in the judge's prompt (a "partial" catch-all
absorbing both one-step fact synthesis and unscored negation claims), not
rater bias. Fixed, validated in two stages (cheap 47-row check, then a
full 481-claim re-run), and adopted: 0.946 (the fixed rubric) is now the
headline citation-precision result, with 0.879 (the original) disclosed
as the superseded methodology, not deleted. Judge-validity against real
human judgment remains explicitly open under this ADR — the fix is a
documented rubric correction, not a substitute for that check.

**Thirteen ADRs existed as of 2026-07-25 (earlier same day).**
`0013-tiered-corpus-release.md` — found, before executing ADR-0012's
"ship the processed corpus" Tier 1 item, that this project's own two
governance documents disagreed on the scope of Freedom House's
permission-gate (`docs/licensing.md`'s broader "any public-facing
redistribution" vs. a narrowed "CLIO-facing" restatement in
`docs/PROJECT_CONTINUITY.md`) — resolved toward the stricter original
reading. Consulted Opus 5 given the compliance stakes; adopted a tiered
release (full chunk text for OONI/CIPESA, hash-verified metadata-only +
a new `rehydrate.py` for Freedom House/Access Now) that solves the
reproducibility rubric criterion without redistributing permission-gated
text. A follow-up email to Freedom House was sent the same day.

**Twelve ADRs existed as of 2026-07-24.**
`0012-rubric-driven-completion-plan.md` — a full rubric audit against the
real, verbatim `project.md` Evaluation Criteria (fetched and checked
directly, not assumed) found LLM evaluation is genuinely 1/2 despite feeling
closed (only one generation approach was ever compared), plus real gaps in
Problem description/Reproducibility (a 306-byte README) and confirmed 0/2 on
Interface/Containerization. An Opus 5 consult produced a ranked completion
plan: a Prompt A/B comparison to fix LLM evaluation properly, a
README rewrite per Alexey Grigorev's README-structure article
(`docs/readme-plan.md`), a 2026-08-02 feature-freeze gate ahead of the
confirmed 2026-08-11 02:00 deadline, and a posts-7+8 merge in the
learning-in-public series. Architecture doc stays at v1.9 — this is a
completion-plan/methodology decision, not an architecture-document change.

**Eleven ADRs existed as of 2026-07-23 (architecture doc still at v1.9 —
ADR-0011, like ADR-0010, is a methodology decision, not an architecture-
document change).**
`0001-english-only-corpus-disclosure.md`,
`0002-tiered-validation-routing.md`,
`0003-provenance-lifecycle-metadata.md`,
`0004-editorial-corrections.md`, all written during architecture review,
before implementation started, plus four written during ingestion
implementation (all 2026-07-20, all prompted by real findings rather than
architecture review): `0005-content-checksum-for-cdn-served-html.md` (a
real acquisition-time finding), `0006-extend-corpus-window-to-2026.md` (a
real document found during research that the frozen 2022-2025 window
excluded on a date technicality), `0007-pipeline-consistency-fixes.md`
and `0008-page-level-citation-provenance.md` (both prompted by an
independent Opus+Fable review of the completed ingestion phase — see
`decisionlog.md`, 2026-07-20 — fixing four internal data-flow/storage
inconsistencies and adding page-level citation provenance for
PDF-sourced chunks, respectively). Note: ADR-0005 declared a v1.4->v1.5
architecture-doc bump that was never actually applied to
`archituecture.md.docx` until ADR-0006's own edit caught and fixed it
in the same pass — all bumps are now correctly reflected
(v1.4 -> v1.5 -> v1.6 -> v1.7 -> v1.8).

Two more written since, one per later phase, both Opus-consulted:
`0009-generation-citation-protocol-and-evidence-flagging.md` (2026-07-24,
v1.8->v1.9) — the index-only `[n]`-marker citation protocol that makes a
fabricated citation structurally impossible, plus the split
mechanical-thin-evidence / prompted-contradiction-handling design.
`0010-citation-judge-protocol-and-contradiction-test-gap.md` (2026-07-23,
no version bump — a methodology/evaluation-design decision, not an
architecture-document change) — the per-citation isolated-entailment
LLM-judge protocol for the evaluation phase, and the decision to document
(not fabricate a fix for) the fact that no genuine cross-source
contradiction had yet been confirmed in the real corpus at design time.

One more, same day: `0011-claim-level-precision-and-judge-validity-fallbacks.md`
— a second Opus 5 review pass (run once Opus 5 became the project's
advisor model) found real gaps in ADR-0010 before any code existed
against it: the judge's own inputs (claim text, cited chunk text) weren't
persisted anywhere, multi-marker claims would have been mis-scored by
per-marker isolation, and Cohen's κ risked being statistically degenerate
under the low-disagreement-prevalence condition this project's own
zero-fabrication smoke-test result makes likely. ADR-0011 amends ADR-0010's
judge signature to claim-level (union of a claim's cited chunks, not one
chunk per call), adds a raw-agreement-plus-error-direction fallback for
when κ is uninformative, and replaces three inconsistent judge-model
descriptions across the project's documents with one checked,
ordered-fallback policy.
