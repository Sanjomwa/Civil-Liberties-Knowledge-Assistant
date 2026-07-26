# ADR-0017: Query Rewriting Design

**Status:** Accepted, 2026-07-26.

## Context

ADR-0012's Tier 3 names query rewriting as an optional best-practice
rubric item (1 point), alongside hybrid search (already shipped, the
retrieval-phase default) and re-ranking (already shipped and labeled —
the P2 country-metadata boost in `search.py`). Query rewriting is the
one best-practice item not yet attempted.

**Current real state:** the user's raw query string goes directly into
`search()` — hybrid BM25 + dense-vector retrieval, combined via
reciprocal rank fusion at the recorded default `k=10`. No query
transformation happens before that call today.

**A real, relevant prior finding this design has to engage with
directly, not just cite:** the retrieval-evaluation phase already
measured and closed a gap on the `multi_country` category (questions
whose *cited source chunk* — not the question's own wording — covers
multiple countries, per `ground_truth.py`'s `classify_category()`).
Plain keyword search beats the hybrid/vector default on this category's
MRR. That gap was concluded to be "a real, non-fixable category-sampling
property" of the evaluation slice, not a retrieval defect — but that
conclusion was reached without query rewriting as an option on the
table, which this design needs to either confirm or overturn honestly,
not just repeat.

Per the same process decision as ADR-0016 (Sam's 2026-07-26 call,
logged in this project's `CLAUDE.md` Section 3): this design comes from
a single deep Fable consult, not the usual Opus-does-design path.

## Decision

### Position on the multi_country conclusion: it holds, for a structural reason, not a sampling-luck reason

**Query decomposition (splitting a multi-country question into
per-country sub-queries, searching each, merging results) will not
overturn the multi_country finding — and a naive test of it would be
structurally biased, not just likely to fail.** The `multi_country`
category is defined by the *cited chunk* spanning multiple countries,
and Hit Rate/MRR reward finding *that one designated chunk*.
Decomposing a query by country steers retrieval toward single-country
chunks — actively away from the multi-country survey chunk the ground
truth calls correct. Decomposition may well produce *better answers*
in practice (per-country evidence assembled from several chunks is
arguably more complete grounding for a comparative question), but the
existing chunk-level metric will score that as flat-to-worse, by
construction. This is a real, testable, cheap experiment if it's ever
worth confirming empirically (decompose per detected country, reusing
the existing country-detection keyword mechanism from ADR-0015's
out-of-scope check, RRF-merge the per-country result lists, measure
just the `multi_country` slice) — but it is not the primary design
target, and a result that comes back "flat or worse" should not be read
as a new problem, just confirmation of the mechanism above.

**Where query rewriting's real value actually is: normalizing messy,
real, colloquial user queries into the corpus's own report-style
vocabulary.** The existing ground-truth question set is already
well-formed, report-style phrasing (it was generated to be), which is
exactly why rewriting won't move the existing Hit Rate/MRR numbers much
— there's little room for it to help on already-clean queries. Its
value shows up on the kind of query a real visitor, not a ground-truth
generator, actually types: colloquial phrasing, dropped country names,
abbreviations, implied context.

### What to build: a single unconditional rewrite step, not decomposition

A `rewrite_query(q) -> str` function: one small-model LLM call that
normalizes a raw query into corpus report-vocabulary (expands
abbreviations, makes an implied country explicit, strips conversational
filler), with a strict low `max_tokens` budget and a short timeout
(target ~2 seconds), and **fails open to the original raw query on any
error** (timeout, API error, empty response) — the same fail-safe
principle already used elsewhere in this project (e.g., the
out-of-scope disclosure never blocks an answer, only supplements it).
This primarily helps the BM25/keyword leg of hybrid search, which is
where messy real-world phrasing loses the most ground relative to
dense retrieval.

**Insertion point:** inside `answer()` in `src/generation/generate.py`,
immediately before the existing `search()` call. `search()` itself is
untouched — it remains the evaluated, frozen retrieval interface this
project has already measured and defaulted (`k=10` hybrid). Both the
raw and rewritten query get logged as an additive Postgres column
(matching the established additive-field pattern already used for
`retrieved_chunks`/`timings`/hybrid-path `score` — no change to
existing logging behavior, a new column only).

**Applied unconditionally, not conditionally.** A conditional trigger
(e.g., "only rewrite if the query looks like it references multiple
countries") would need its own classification step — a second failure
surface — to save what a single small-model call actually costs:
roughly $0.0001 and a fraction of a second, against a pipeline whose
generation step alone already runs multiple seconds and costs
meaningfully more per query. The added complexity of conditional
triggering isn't justified by what it would save.

### Evaluation: two runs, both against the existing harness

1. **Regression gate** — the full existing ground-truth set, raw vs.
   rewritten, Hit Rate/MRR overall and per category (same harness,
   `evaluate.py`, already built). Success condition: deltas within
   noise. Expected result: little to no change here, precisely because
   the ground-truth questions are already well-formed report-style
   phrasing — this run exists to catch a regression, not to prove a
   gain.
2. **Where the real gain should show** — a new, smaller (~30-50
   question) adversarial set built by *degrading* existing ground-truth
   questions (colloquialize phrasing, drop explicit country names,
   abbreviate) while keeping their original chunk labels. Raw vs.
   rewritten on this degraded set is the honest before/after
   comparison, and directly satisfies the rubric's query-rewriting
   item in this project's established measured-comparison style (same
   shape as the Prompt A/B generation comparison, ADR before this one).

## Consequences

- `src/generation/generate.py` gains a new `rewrite_query()` function
  and one new call site in `answer()`. No change to `search()`,
  `embed.py`, or the frozen retrieval default.
- Postgres logging (`db.py`) gains one additive column (rewritten
  query text) — no change to any existing column or query.
- A new adversarial evaluation set needs to be built (degraded
  ground-truth questions) — not yet built, an implementation-phase task.
- The `multi_country` "non-fixable" finding stays as previously
  concluded; this ADR adds the structural reason it holds, rather than
  reopening or re-testing it as the primary goal of this work. The cheap
  decomposition experiment described above is optional, not required.

## Fable design consult

Consulted 2026-07-26, same single deep-design pass as ADR-0016 (see
that ADR's Context for the process rationale). Took an explicit,
undodged position when asked directly whether decomposition would
overturn the multi_country finding — concluded it would not, and gave
the structural (metric-definition) reason rather than hedging with "it
depends." Full transcript in `decisionlog.md`, 2026-07-26.

## What would trigger a revisit

- **If the regression-gate run shows a real (non-noise) drop on the
  existing ground truth** — that would mean the rewrite step is hurting
  well-formed queries, not just failing to help them; worth pausing to
  diagnose before shipping, not something to absorb quietly.
- **If the adversarial-set comparison shows little to no gain either**
  — that would be a genuine null result for query rewriting itself
  (same honest-null-result standard as the Prompt A/B generation
  comparison), worth reporting as exactly that rather than reframed.
- **If a future need arises to actually fix the `multi_country` MRR gap
  itself** (not just normalize messy queries) — the decomposition
  experiment described above is the documented next thing to try, with
  the explicit expectation set here that it likely won't move the
  chunk-level metric even if it improves real answer quality.
