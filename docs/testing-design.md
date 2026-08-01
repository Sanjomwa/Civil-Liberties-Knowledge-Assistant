# Test suite design (pre-implementation reference)

**Status: design only, 2026-08-01, revised 2026-08-02 after an Opus 5
review. No `tests/` directory exists yet.** This mirrors
`retrieval-design.md`/`deployment-design.md`'s own pre-implementation
pattern — written before a line of test code exists, so a future
session (or Claude Code) can implement directly from this rather than
re-deriving scope from scratch. See ADR-0020 for the decision this
design formalizes.

**Revision note, 2026-08-02:** the first version of this doc (2026-08-01)
skipped an advisor consult on the reasoning that scoping a test suite
was low-complexity. Sam asked for an Opus 5 pass before implementation
started anyway — it found three real implementation blockers and two
real scoping errors, all folded in below rather than left as a separate
addendum, since they change the actual plan, not just add commentary on
it. Full review transcript and reasoning: `decisionlog.md`, 2026-08-02.

## Why this, why now

Not a rubric requirement — confirmed directly against the verbatim
`project.md` Evaluation Criteria (2026-07-29 re-audit): no Testing or
CI/CD scoring line exists at all. This is real engineering debt, kept
on the tracked list per Sam's explicit instruction to hold this project
to a standard beyond what the course grades.

**What this is not replacing.** Three real correctness checks already
exist and stay authoritative for RAG *behavior*: the retrieval
evaluation (Hit Rate/MRR against a 101-question ground truth), the
LLM-evaluation judge (claim-level citation precision against the real
corpus and a real OpenAI key), and the ADR-0015 behavioral suite (25
scripted questions against `answer()` directly). All three are
correct, expensive (real API spend), and manual by design — nothing
here should try to replace them or run them on every push.

**What this is filling in.** Underneath those three, this project has
zero automated coverage of its own deterministic logic — the plain
Python functions that parse, classify, chunk, and score, with no API
call and one correct answer per input. Two of those functions have
each broken silently once already and were only caught by a human
noticing a downstream symptom, not by a test:

- `src/ingestion/chunk.py` — a real stamp-ordering bug (2026-07-22,
  caught and fixed the same day it was introduced).
- `src/retrieval/ground_truth.py`'s `classify_category()` — a real
  OONI case-sensitivity bug (caught during the retrieval phase,
  fixed).

Both are exactly the class of regression a cheap, fast unit test
exists to catch on the next change, before it silently reaches a real
evaluation run and gets misread as a retrieval-quality problem instead
of a classification bug.

## Framework

`pytest` — already listed in `pyproject.toml`'s `dev` dependency group,
unused until now. No new dependency to add.

## Implementation prerequisite — import strategy (found by the Opus 5
review, blocks the first test if skipped)

Nothing in `src/` has an `__init__.py`. Every existing module imports
its siblings as bare names (e.g. `from citations import ...`) that only
resolve because scripts manually `sys.path.insert` their own directory
at runtime — confirmed directly against `run_behavioral_tests.py`'s own
`sys.path.insert(0, ...)` lines. A test file written the normal way
cannot import any of these modules as the repo stands today.

Fix, before writing a single test: add to `pyproject.toml`:

```toml
[tool.pytest.ini_options]
pythonpath = ["src", "src/generation", "src/retrieval", "src/ingestion", "src/interface"]
testpaths = ["tests"]
```

and run pytest with `--import-mode=importlib` (or set it in the same
`ini_options` block) rather than requiring an `__init__.py` in every
`tests/` subdirectory — the modern, less brittle fix for the same-
basename-file collision risk this repo's flat-module-per-directory
layout would otherwise create.

## Scope, in priority order

**Priority 0 — the highest-value test in this whole design, found by
the Opus 5 review, not in the original plan.** `src/generation/
prompts.py`'s `build_user_prompt()` numbers retrieved excerpts via
`enumerate(chunks, start=1)`; `citations.py`'s `parse_citations()`
independently maps a written marker `n` back to `chunks[n-1]`. ADR-0009's
entire citation-integrity claim rests on those two numbering schemes
staying identical — and nothing currently checks that they agree.
A silent drift between them would make the system produce answers that
*look* correctly cited while actually pointing at the wrong document,
and the citation-precision judge would not catch it either, since it's
only ever handed whichever chunk the (wrong) marker resolves to. Both
functions are pure, no fixtures needed — write this contract test
first, before anything else below.

**Tier 1 — pure logic, zero I/O, zero mocking.**

- `src/generation/citations.py`: `parse_citations()` (marker
  extraction and range validation against `1..len(chunks)`) and
  `sourcing_footer()`'s three distinct branches (single document,
  single-org/multi-doc, multi-org). **Caveat found by the review:**
  `render_sources()` and `sourcing_footer()` both actually call
  `_load_doc_metadata()`, which reads `data/metadata/{doc_id}.json` and
  is `@lru_cache`d — this is not zero-I/O as originally claimed. Either
  add an autouse fixture that calls `_load_doc_metadata.cache_clear()`
  between tests, or (preferred, since it also makes the function
  properly unit-testable rather than just carefully sequenced) add an
  optional injectable metadata-loader parameter defaulting to the
  current file-reading behavior.
- `src/retrieval/ground_truth.py`: `classify_category()` — the
  documented OONI case-sensitivity regression.
- `src/ingestion/chunk.py`: `make_windows()` specifically (the pure
  boundary-math function) — **not** `chunk_document()`, which does
  real filesystem writes/`rmtree` and moves to Tier 2 below. This is a
  real correction: the stamp-ordering bug that originally justified
  testing this module manifests inside `chunk_document()`, not
  `make_windows()` — the original Tier 1 placement would not have
  caught the bug it was named after. `stamp_chunking_block`'s call to
  `date.today()` also needs an injectable/monkeypatched date, not a
  bare call, or the test becomes flaky by design.
- `src/retrieval/search.py`: RRF fusion math and the
  `_boost_by_country` re-rank — confirmed pure functions over
  in-memory lists of dicts. Same `lru_cache`/file-read caveat as
  `citations.py` applies to `_load_index_metadata()` if any test
  touches it — same fix (cache-clear fixture or injectable parameter).
- `src/interface/db.py`'s `est_cost_usd()` — **moved up from Tier 2**:
  it's pure arithmetic given a model name and token counts, no
  fixture file needed. Deliberately built to *raise* rather than
  silently log a zero cost on an unrecognized model — the test that
  matters most here is proving that raise actually fires, not just the
  happy-path math.
- `src/generation/generate.py`'s `_detect_out_of_scope_countries()`
  and `_out_of_scope_disclosure()` (ADR-0015) — **pulled out of Tier 3
  and into Tier 1**: both are pure regex/string logic with no API call,
  despite living in a module whose other functions genuinely need
  Tier 3. This pair also has the highest documented bug density on
  this whole list — a real Niger-in-Nigeria/Mali-in-Somalia substring
  bug was already caught and fixed once (ADR-0015 round 3) — which
  makes it a stronger regression-test candidate than most of the
  originally-planned Tier 1 scope, not a weaker one.

**Tier 2 — needs fixture files (tmp directories, small sample data),
still no network/API.**

- `src/ingestion/chunk.py`'s `chunk_document()` — the actual site of
  the stamp-ordering bug; needs a temp directory fixture since it
  writes/removes files for real.
- `src/ingestion/metadata.py` / `validate.py` — SimHash duplicate
  detection and the per-org checksum-gate branch (`raw_bytes_stable`,
  per ADR-0007) against small synthetic fixture files, not real corpus
  documents.

**Tier 3 — needs real OpenAI mocking. Not this pass.**

- The remainder of `src/generation/generate.py` (the actual `answer()`
  call chain) and `src/evaluation/judge.py` — genuinely valuable
  eventually, but mocking `openai.OpenAI()` responses well enough to be
  trustworthy is real design work on its own. Deliberately deferred
  rather than mocked shallowly just to claim coverage.

**Explicitly out of scope for any tier:** anything requiring a live
OpenAI call, a live network fetch, or a live DB connection. That
territory stays covered by the existing manual evaluation runs, the
behavioral suite, and the Tier 2/3 deploy rehearsals already on record
— this suite is not trying to duplicate them.

## Layout

`tests/` mirrors `src/`'s own module structure — `tests/generation/
test_citations.py`, `tests/retrieval/test_ground_truth.py`,
`tests/ingestion/test_chunk.py`, and so on — standard pytest
convention, and it keeps a future contributor's mental model identical
between the two trees. A `tests/fixtures/` directory holds small,
synthetic sample data (e.g., a two-entry fake `metadata/*.json` for
`citations.py` tests) — never real corpus documents, so tests never
depend on `corpus/` or `data/` being populated.

## Mocking strategy

Tier 1 and Tier 2 need no mocking at all — pure functions or small
local fixture files. When Tier 3 is eventually tackled, use `pytest`'s
`monkeypatch` or `unittest.mock` to replace `openai.OpenAI()` calls.

**The original safeguard idea here was wrong, per the Opus 5 review,
and is corrected rather than kept as originally written.** The first
draft proposed a `conftest.py` fixture that fails loudly if a test
reads `OPENAI_API_KEY` from the environment. Two real problems with
that: several modules (`ground_truth.py`, `generate.py`, `judge.py`,
`db.py`) call `load_dotenv()` at *module import* time, which fires
during pytest's collection phase, before any fixture — including this
one — ever runs, so it would silently populate `os.environ` from the
real `.env` regardless. And the actual risk was never the presence of
a key — `client or OpenAI()` patterns mean a key can be passed in
directly, bypassing an env check entirely. The real risk is a network
call happening at all.

**Corrected approach:** an autouse `conftest.py` fixture that blocks
the actual network connection (monkeypatching `socket.socket.connect`
to raise, or adopting the `pytest-socket` package if the hand-rolled
version proves fragile) for the whole test session, plus
`monkeypatch.setenv("OPENAI_API_KEY", "dummy-test-key")` so any
module-scope `load_dotenv()` call is harmless either way. This
actually enforces "no real API call, ever," instead of checking a
proxy for it that has known bypasses.

## CI integration — deferred until tests exist

Once a first real batch of Tier 1 tests lands, add a third job to
`.github/workflows/ci.yml` (`unit-tests`: `uv run pytest tests/`)
alongside the existing `syntax-check`/`docker-build` jobs. Not added
in this design pass — same discipline used when CI/CD itself was
added: don't claim a CI job for tests that don't exist yet.

## Definition of done for a first real milestone

Not "100% coverage" — a concrete, bounded bar, revised to include the
Priority 0 finding: the `prompts.py`/`citations.py` numbering-contract
test, plus real coverage of the modules with a documented history of a
silent bug (`chunk.py`'s `make_windows()` and `chunk_document()`,
`ground_truth.py`'s `classify_category()`), `citations.py`'s three
sourcing-footer branches, and the two pulled-forward `generate.py`
scope-detection functions. That's a real, scoped first pass, not an
open-ended "add tests" task with no defined finish line.

## Open questions, deliberately not resolved here

- Whether Tier 2/3 are worth doing at all before the course deadline,
  given they're not rubric-scored — Sam's call when Tier 1 is done,
  not decided now.
- Whether a coverage-percentage tool (`pytest-cov`) is worth adding —
  deferred; the definition-of-done above doesn't need a percentage to
  be meaningful.
