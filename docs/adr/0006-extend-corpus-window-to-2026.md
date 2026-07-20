# ADR-0006: Extend Corpus Date Window to 2022-2026

**Status:** Accepted, 2026-07-20.

## Context

The frozen architecture's temporal scope — "2022-2025 (closed corpus)" —
was set when the project started, meant to bound "the recent past" to a
tractable, citable window for a course project. It was written without
an explicit revisit trigger, on the implicit assumption that the project
would finish before the calendar caught up with the upper bound.

It has now. Current date is 2026-07-20. While researching Access Now and
OONI candidate documents for the next corpus batch, a real, well-
documented OONI investigation was found — network measurements showing
Uganda shut down internet access nationwide from January 13-18, 2026
(spanning the January 15 general election), followed by continued
blocking of WhatsApp, Facebook, Instagram, and X once connectivity was
restored. This is exactly the kind of censorship event the corpus exists
to document — election-related, target country, technically documented
by an approved v1 source — excluded purely because it falls seven months
past a boundary that was never meant to be permanent.

Consulted Opus (per this project's standing practice for real design
decisions, not a single-turn lookup) on two options:

- **(A) Static bump** — change the frozen scope to "2022-2026" as a
  one-time ADR decision, same shape as ADR-0001's disclosure amendment.
  If the project runs long enough that this goes stale again, write
  another ADR then.
- **(B) Rolling window** — redefine scope relative to the present date
  (e.g., "current year minus 4"), so it never needs manual revisiting.

Opus's recommendation, adopted directly: **(A)**. The corpus is an
evidentiary archive, not a current-state tracker — a 2022 document
documenting a real censorship event doesn't decay in relevance as time
passes, so there's no principled reason to age it out or to make future
eligibility a function of "now." Worse, (B) would make the corpus
non-reproducible: the same architecture doc and the same source YAMLs
would yield a different eligible set depending on what date the pipeline
happens to run, which directly undermines the provenance/drift-detection
design ADR-0003 already invested in (`corpus_version` stamps are only a
meaningful drift signal if the corpus's own eligibility rules are a
fixed fact, not a moving target).

**Separately flagged by the same consult, and worth stating plainly:**
window extension is a small, secondary lever for reaching the 40-60
document target the architecture specifies. The corpus currently sits at
18-21 documents against that target, and the actual constraint is
under-sampling *within* the existing window — most organizations still
hold only 1-4 documents each, when substantially more real, in-window
material exists per org. Extending the boundary makes a handful of
additional documents eligible; deepening per-org research passes inside
2022-2025 is where the other 20-40 documents actually are. This ADR
should not be read as a capacity-planning move — it's a separate,
smaller scope decision, motivated by one specific excluded document, not
a "stay current" policy.

## Decision

1. The corpus temporal scope changes from "2022-2025" to "2022-2026" — a
   static, one-time extension, not a rolling or relative window.
2. Framed as event-motivated, not calendar-motivated: the trigger is a
   specific, real, thematically in-scope document being excluded on a
   date technicality, not a general "keep pace with today" policy. Future
   staleness (if the project runs past 2026) should be resolved the same
   way — a new ADR making a deliberate, event-motivated call — not by
   converting this into a rolling window after the fact.
3. `docs/corpus-inclusion-rubric.md` Section 1's window definition is
   updated (2022-2025 -> 2022-2026); its Include/Exclude examples and
   underlying reasoning are otherwise unchanged.
4. The architecture document's "Temporal coverage" line and OONI
   Acquisition Rule (which independently restates "2022-2025") are both
   updated to "2022-2026."
5. No retroactive re-review of already-Included documents. Nothing
   currently in the corpus falls outside either window, so this changes
   eligibility for new candidates only.
6. Per the architecture's own change-management rule, the document
   version increments. This ADR bumps it to v1.6 — but see the note
   below: it was found, while making this edit, that ADR-0005's own
   v1.4->v1.5 bump was never actually applied to the document, only
   declared in the ADR text. Both bumps are applied in the same pass as
   this ADR, corrected in sequence (v1.4 -> v1.5 -> v1.6), not silently
   folded into a single v1.4 -> v1.6 jump that would erase the record of
   ADR-0005's own change.

## Consequences

- The Uganda January 2026 election-shutdown document (and any other real,
  thematically in-scope 2026 material) becomes eligible for the next
  semantic review pass — not automatically included, still subject to
  the rubric's ordinary Section 4 process.
- No change to any already-Included document, its metadata, or its
  chunks.
- Does not address the corpus-size shortfall (18-21 of 40-60 documents)
  — that remains a separate, larger problem, tracked in
  `PROJECT_CONTINUITY.md` Section 7, requiring deeper per-org sampling
  within the window rather than a boundary change.
- Surfaced and fixed, as a side effect of this edit: `archituecture.md.docx`
  had drifted from its own ADR record (ADR-0005 declared a v1.5 bump that
  was never physically applied). Both this project's own documented
  lesson ("comprehensive planning documents can accidentally describe a
  future state in present tense") and its "does this doc match reality"
  discipline apply directly here — logged in `decisionlog.md`.

## Opus consult

Consulted 2026-07-20. Ranked (A) over (B) on archival-vs-current-state
reasoning and reproducibility grounds (see Context above); separately
flagged that window extension is the smaller lever for the corpus-size
goal, and that under-sampling within the existing window is the bigger,
separate problem. Both points adopted as-is — no conflict between the
consult and the primary reviewer's (Claude's) own leaning, which matched
before the consult was even run.

## What would trigger a revisit

If the corpus/project timeline extends meaningfully past 2026 (the
project becomes a genuinely multi-year effort rather than a bounded
course deliverable), or if a second real, thematically in-scope document
gets excluded purely because the window has gone stale again — at that
point, write a new ADR making the same kind of deliberate, event-
motivated call. Do not silently let the window drift, and do not convert
to a rolling window as a one-off patch at that time either — if a rolling
window is ever genuinely warranted, that's its own design decision,
deserving its own Opus consult on its own merits, not a default fallback
once static bumps start feeling repetitive.
