# Query Rewriting — Pre-Implementation Design

Written 2026-07-26, before `rewrite_query()` exists — mirrors
`retrieval-design.md`/`generation-design.md`/`evaluation-design.md`/
`interface-design.md`'s shape. Covers ADR-0012 Tier 3's query-rewriting
best-practice item. Full decision rationale, including the position on
the `multi_country` finding: `docs/adr/0017-query-rewriting-design.md`.
Design produced via the same single deep Fable consult as
`deployment-design.md` — transcript basis in `decisionlog.md`,
2026-07-26.

## Scope boundary

Ends at: a `rewrite_query()` function called once per query, before
retrieval, plus an evaluation showing whether it helps. Does not touch
`search.py` (the frozen, evaluated retrieval interface), the RRF
default (`k=10`), or the country-boost re-rank. Does not attempt to fix
the `multi_country` MRR gap directly — ADR-0017 explains why that's a
structural, not a rewriting-fixable, property of the current metric.

## Decisions

**1. One function, one call site.** `rewrite_query(query: str) -> str`
lives in `src/generation/generate.py`, called once inside `answer()`,
immediately before the existing `search()` call. `search()` itself is
never modified.

**2. Single rewrite, not decomposition.** The function makes one small,
cheap LLM call that normalizes the raw query into corpus
report-vocabulary (expand abbreviations, make an implied country
explicit, strip conversational filler) and returns a single rewritten
query string. It does not split a query into per-country sub-queries —
see ADR-0017 for why decomposition is a documented, optional future
experiment, not the primary build here.

**3. Fail-open, always.** On any error — timeout (~2s budget), API
error, empty/malformed response — return the original raw query
unchanged. The rewrite step must never be able to block or degrade an
answer; it can only help or be a no-op. Same fail-safe discipline as
the out-of-scope disclosure mechanism (ADR-0015): additive, never a
point of failure for the base path.

**4. Unconditional application.** Every query gets rewritten — no
classifier deciding whether to bother. Reasoning (full detail in
ADR-0017): the added cost of a small-model call (~$0.0001, a fraction
of a second) doesn't justify the complexity of a conditional trigger
that would itself need its own classification step and failure
handling.

**5. Logging: one additive Postgres column.** Both the raw query
(already logged) and the rewritten query get stored — a new column,
not a replacement of the existing `query` field. Matches the
established additive-field pattern (`retrieved_chunks`, `timings`,
hybrid-path `score` from Tier 2).

**6. Evaluation: two separate runs, reusing the existing harness.**

- *Regression gate*: full existing ground truth (`evaluate.py`), raw
  vs. rewritten queries, Hit Rate/MRR overall and per category. Pass
  condition: deltas within noise. This run is a safety check, not the
  place a gain is expected — the ground truth is already well-formed,
  report-style phrasing.
- *Real comparison*: a new ~30-50 question adversarial set, built by
  degrading existing ground-truth questions (colloquial phrasing,
  dropped country names, abbreviations) while keeping their original
  chunk labels. Raw vs. rewritten on this set is the honest before/after
  — this is where a real gain, if any, should actually show up, and
  it's the number that satisfies the rubric's query-rewriting item.

## Open items for implementation (not decided here)

Per ADR-0017's own list:

- Exact rewrite-model choice and prompt wording.
- Whether the rewritten query feeds both the BM25 and vector legs of
  hybrid search, or just BM25 (where messy phrasing loses the most
  ground) — a real implementation-time call, not fixed here.
- Method for building the degraded adversarial set (manual degradation
  vs. LLM-assisted generation with a human spot-check pass) — consult
  Opus if a design question comes up building this, per the same
  process split as deployment.

## The multi_country position, restated briefly

Decomposing a multi-country query by country will not improve the
existing chunk-level Hit Rate/MRR metric on the `multi_country`
category, because that category is defined by the *cited chunk*
spanning multiple countries — decomposition steers retrieval toward
single-country chunks, away from the one the ground truth calls
correct. This is a structural property of the metric, not a claim that
decomposition produces worse real answers. Full reasoning: ADR-0017.
