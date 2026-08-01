# ADR-0020: Unit Test Suite — Scope, Priority Tiers, and What This Doesn't Replace

**Status:** Accepted, 2026-08-01 (design only — implementation not started).

## Context

This project's real, existing correctness checks are all either
expensive (real OpenAI spend: retrieval evaluation, the LLM-evaluation
judge, the ADR-0015 behavioral suite) or manual by design. Nothing
covers the plain deterministic Python logic underneath them — parsing,
classification, chunking, scoring math — the kind of function with one
correct answer per input and no API call involved at all.

That gap is not hypothetical: `src/ingestion/chunk.py` (a stamp-
ordering bug) and `src/retrieval/ground_truth.py`'s
`classify_category()` (an OONI case-sensitivity bug) have each broken
silently once already, caught only by a human noticing a downstream
symptom.

This was never a rubric-scored gap — confirmed directly against the
verbatim `project.md` Evaluation Criteria during the 2026-07-29
tech-debt re-audit, which found no Testing or CI/CD scoring line at
all. It stays on this project's tracked debt list anyway, per Sam's
explicit instruction (2026-07-29) to hold the project to real
engineering rigor beyond what the course grades — the same basis the
CI/CD addition (`.github/workflows/ci.yml`, 2026-07-30, `decisionlog.md`
same date) was closed on.

## Decision

Add a `pytest`-based unit test suite (framework already a `pyproject.toml`
dev dependency, unused until now), scoped in three priority tiers by
mocking cost, not by module importance:

- **Tier 1** (pure logic, zero I/O, start here): `citations.py`'s
  marker parsing/validation and three-branch sourcing footer,
  `ground_truth.py`'s `classify_category()`, `chunk.py`'s boundary and
  stamp-ordering logic, `search.py`'s RRF fusion and country-boost
  re-rank.
- **Tier 2** (fixture files, still no network/API): `db.py`'s
  `est_cost_usd()` (including its deliberate raise-don't-silently-
  zero behavior on an unrecognized model), `metadata.py`/`validate.py`'s
  SimHash and checksum-gate branching.
- **Tier 3** (real OpenAI mocking required, deliberately deferred):
  `generate.py`, `judge.py`.

Full scope, module-by-module rationale, layout (`tests/` mirrors
`src/`), and the no-real-API-calls-ever mocking constraint are in
`docs/testing-design.md` — not restated here per this project's own
"ADRs point at the design doc, don't duplicate it" convention.

**What this explicitly does not replace:** the retrieval evaluation,
the LLM-evaluation judge, and the ADR-0015 behavioral suite remain the
authority on actual RAG output quality. This suite targets
function-level determinism underneath them, nothing about generation
or retrieval *quality* itself.

## Consequences

- No `tests/` directory exists yet — this ADR and `testing-design.md`
  are the design, not the implementation. Implementation is a separate,
  future task.
- CI integration (`.github/workflows/ci.yml`'s future `unit-tests` job)
  is deliberately deferred until real tests exist, matching the
  discipline already used when CI/CD itself was added — no job should
  ever claim to run tests that don't exist.
- Tier 2 and Tier 3 are explicitly optional/lower-priority — if time
  runs short before the course deadline, Tier 1 alone (which directly
  covers both modules with a documented history of a silent bug) is a
  real, defensible stopping point, not a partial failure.

## Advisor consult

**Original text, superseded — kept for the record, not deleted:**
"None run. This is a scoping/priority decision over already-read
source files... same class of low-complexity decision `docs/adr/
README.md` already carves out for ADR-0004/0019 (no consult needed)."

**Correction, 2026-08-02: that call was wrong, and Sam asked for a
consult anyway before implementation started.** An Opus 5 review,
grounded directly in the real source files rather than this design
doc's summary of them, found three real implementation blockers and
two real scoping errors — proof that "scoping over already-read files"
was not actually low-complexity here. Specifically:

1. No `src/` module has an `__init__.py`; the design as first written
   would not have been importable by a test file at all.
2. Two functions claimed as "zero I/O" (`citations.py`'s
   `render_sources()`/`sourcing_footer()`) actually read and
   `lru_cache` a metadata file, creating a real cross-test cache-
   leakage risk.
3. The proposed `OPENAI_API_KEY`-presence safeguard against accidental
   real API calls has two holes (module-scope `load_dotenv()` firing
   before any fixture; a key can bypass an env check by being passed
   directly) and needed to become a real network-connection block
   instead.
4. `chunk.py` was tiered by the wrong function — the actual stamp-
   ordering bug this suite is partly justified by lives in
   `chunk_document()`, not the pure `make_windows()` originally placed
   in Tier 1.
5. The single highest-value test in the whole design — that
   `prompts.py`'s citation numbering and `citations.py`'s citation
   parsing use the same scheme, the literal mechanism ADR-0009's
   citation-integrity claim depends on — was missing entirely.

All five are corrected directly in `docs/testing-design.md` rather than
kept as a separate addendum, since they change the actual plan. Full
transcript: `decisionlog.md`, 2026-08-02. Lesson for this project's own
advisor-consult judgment calls going forward: "I already read the
files" is not the same test as "is this actually low-complexity" —
worth remembering the next time a consult is skipped on that basis.

## What would trigger a revisit

- If Tier 1 implementation surfaces a module that isn't actually as
  pure as this design assumes (e.g., a hidden file read or global
  state) — rescope that module into Tier 2, don't force a Tier-1-style
  test past a false assumption.
- If a real regression later slips through in a Tier 3 module
  (`generate.py`/`judge.py`) — that's the concrete signal to stop
  deferring Tier 3 and actually design the OpenAI-mocking approach.
