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

Six ADRs exist as of 2026-07-20 (architecture doc now at v1.6):
`0001-english-only-corpus-disclosure.md`,
`0002-tiered-validation-routing.md`,
`0003-provenance-lifecycle-metadata.md`,
`0004-editorial-corrections.md`, all written during architecture review,
before implementation started, plus two written during implementation
(both 2026-07-20, both prompted by real findings rather than
architecture review): `0005-content-checksum-for-cdn-served-html.md`
(a real acquisition-time finding), and
`0006-extend-corpus-window-to-2026.md` (a real document found during
research that the frozen 2022-2025 window excluded on a date
technicality). Note: ADR-0005 declared a v1.4->v1.5 architecture-doc
bump that was never actually applied to `archituecture.md.docx` until
ADR-0006's own edit caught and fixed it in the same pass — both bumps
are now correctly reflected (v1.4 -> v1.5 -> v1.6).
