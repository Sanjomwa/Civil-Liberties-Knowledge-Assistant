# ADR-0010: Per-Citation Isolated-Entailment Judge Protocol, and the Contradiction-Testing Gap

**Status:** Accepted, 2026-07-23.

## Context

The LLM evaluation phase's core job, per `04-evaluation/project/
project_evaluation_plan.md`'s pre-existing design, is to measure citation
precision — of all citations a generated answer produces, what fraction
are both structurally valid (already guaranteed mechanically by
`citations.py`) and semantically supported by the chunk they cite. Two
questions block implementation, both judged during design (an Opus
consult, 2026-07-23, full transcript in `decisionlog.md`) to cross this
project's own "genuinely novel design decision" threshold — the same bar
ADR-0009 applied to generation's citation protocol — rather than being
ordinary parameter choices within already-decided space.

First: how should an LLM judge actually score a citation, and does
judging with the same model that generated the answer (`gpt-5.4-mini`,
already established for `ground_truth.py` and `generate.py`) introduce a
self-preference bias the project should design around. Second: the
architecture's core requirement includes correctly handling
*contradictory* evidence (ADR-0009's prompt-only mechanism: state both
positions, never average), but the real smoke test never happened to hit
a genuine cross-source contradiction, and it isn't yet confirmed the real
35-document corpus contains one at all — leaving this specific mechanism
unverified against real data, with a real risk of either fabricating a
test case (breaking every prior phase's "real corpus, real citations"
discipline) or silently skipping the check.

## Decision

### Judge protocol: per-citation, isolated entailment, 3-way verdict

The judge is called once per citation, not once per whole answer —
matching the evaluation plan's own per-citation definition of precision
exactly. Each call receives **only the claim text and the cited chunk's
text**, nothing else (not the full answer, not the other retrieved
chunks, not the question). Isolating the task to a pure entailment
question (does this specific chunk support this specific claim)
structurally removes the self-preference risk a whole-answer judge would
carry, rather than trying to mitigate it after the fact.

Verdict is **three-way** — `supported | partial | unsupported` — not
binary. A chunk that supports part of a claim but not all of it is a real
and common case; collapsing it into a binary would hide exactly the
precision failures this metric exists to catch.

```
judge(claim_text: str, cited_chunk_text: str) -> {"verdict": "supported" | "partial" | "unsupported", "reason": str}
citation_precision = supported / (supported + partial + unsupported)   # partial reported separately, not silently folded in
```

**Judge model: different from the generator, at least for the calibration
subset.** The isolated-entailment framing above makes the bias risk
structurally low even under self-judging, per the consult's own read —
but switching judges costs almost nothing at this granularity (one short
call, not a whole-answer judgment) and removes a reviewer's obvious first
objection to the whole evaluation. Use a stronger or cross-provider model
(full `gpt-5.4`, not `gpt-5.4-mini`) for the human-reviewed calibration
sample (see below); the full-scale run may still use `gpt-5.4-mini` once
calibration confirms agreement, cost being a real constraint against the
Aug 10 deadline.

### Judge validation: stratify by verdict, report Cohen's κ, not raw agreement

Sample ~50-80 citation-judgments for human review, **oversampling every
`unsupported`/`partial` verdict** (rare, decision-critical, the failure
mode that actually matters) plus a random sample of `supported`
verdicts. Report **Cohen's κ**, not raw percent agreement — raw agreement
inflates trivially when `supported` dominates the verdict distribution,
which it's expected to given the generation phase's own zero-fabrication
smoke-test result. Rough go/no-go threshold: κ ≥ ~0.7; below that,
redesign the judge prompt/protocol before trusting further judge-only
runs at scale.

### Contradiction testing: search empirically first; if none found, document the gap and test the mechanism only

Before assuming no real contradiction exists in the corpus, actually look
for one: target likely axes where independent organizations plausibly
report the same event differently (a shared shutdown's exact dates,
which party is blamed, its stated scale/duration) by retrieving
cross-organization chunks on shared real events, running a cheap
pairwise "do these disagree on a checkable fact" scan, and human-verifying
any survivor.

**If no real contradiction survives that search:** the project does
**not** fabricate one by editing real chunk text — that would violate the
real-corpus, real-citation discipline every prior phase has held to, for
the sake of a passing test. Instead: (a) document the absence explicitly
as a named, real evaluation gap — the contradiction-handling mechanism is
verified structurally (a prompt instruction reviewed at design time) but
not empirically confirmed against a real disagreement in this corpus; (b)
add a clearly-labeled **synthetic-fixture unit test** — a hand-built pair
of excerpts engineered to disagree — that verifies the *mechanism*
(does the model state both positions rather than averaging, given
excerpts that actually conflict) independent of whether the real corpus
happens to contain one. This fixture is explicitly excluded from the
real-corpus evaluation metrics and reported separately, so it can never
inflate or deflate the citation-precision number — it answers a different
question (does the mechanism work at all) than the real-corpus run
answers (does it hold up on this project's actual evidence).

## Consequences

- New module `src/evaluation/judge.py` implements `judge()` exactly as
  above — the one place the citation-faithfulness scoring logic lives.
- Citation precision is reported as a 3-way breakdown (supported /
  partial / unsupported), not collapsed to one number, matching
  retrieval's own established per-slice-not-just-aggregate discipline
  (the `multi_country` finding already proved aggregate-only numbers can
  mislead on this project).
- The evaluation report must carry an explicit, visible line stating
  whether a real cross-source contradiction was found and tested, or
  whether contradiction-handling rests on the synthetic fixture alone —
  this is a real, load-bearing caveat on what the project can honestly
  claim about ADR-0009's contradiction mechanism, not a footnote.
- Judge-model cost: calibration subset uses the more expensive model;
  full-scale run may use `gpt-5.4-mini` only after κ clears the ~0.7 bar
  on the calibration sample — cost is recorded per
  `evaluation_checklist.md`'s own requirement, not assumed cheap.

## Opus consult

Consulted 2026-07-23 (evaluation-phase design consult, briefed with the
full generation-phase interface, the real retrieval numbers, and four
explicit open questions — reuse-vs-fresh ground truth, judge design,
human-review sampling, and the contradiction-testing gap). This ADR
covers the two questions the consult judged to cross the "genuinely
novel decision" bar; the other two (ground-truth reuse with a small
labeled supplement, and stratified-by-category sampling for the
deployment citation-precision review) were judged refinements within
already-open design space and are recorded in `docs/evaluation-design.md`
directly, not here. Full transcript in `decisionlog.md`, 2026-07-23.

## What would trigger a revisit

- If the calibration sample's Cohen's κ comes in below ~0.7 — redesign
  the judge prompt or protocol before any further judge-only run, not a
  one-off retry.
- If a future corpus update introduces a genuine, confirmed cross-source
  contradiction — replace or supplement the synthetic fixture with a real
  case, and re-run the contradiction check against real data for the
  first time.
- If citation precision comes back low enough to warrant the second LLM
  verification/grounding pass `docs/generation-design.md` already
  documented as a deferred fallback — this phase's own results are the
  actual trigger condition for that deferred work.
