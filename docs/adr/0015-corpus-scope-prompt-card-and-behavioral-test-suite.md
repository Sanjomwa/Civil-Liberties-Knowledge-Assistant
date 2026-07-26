# ADR-0015: Corpus-Scope Prompt Card and Advertised-vs-Delivered Behavioral Test Suite

**Status:** Accepted, 2026-07-26.

## Context

Found through real, direct use of the deployed Streamlit app (not a
planned test): asked "what are the countries under this corpus scope?"
The app's declared scope (README, and the Streamlit caption) is five
countries — Kenya, Uganda, Tanzania, Ethiopia, Rwanda, 2022-2026. The
real answer instead listed roughly 38 African countries, drawn from
CIPESA's pan-continental "State of Internet Freedom in Africa" reports,
which are legitimately part of the corpus (included for their sections
relevant to the five target countries) but whose full text also covers
comparative regional context for dozens of other countries.

Root cause, confirmed directly, not assumed: the five-country scope is a
fact about how documents were *curated* into the corpus
(`corpus/sources/*.yaml`), not a fact stated in any document's own text.
`search()` correctly retrieved the chunks most textually similar to a
question about "countries" and "scope" — real, on-topic passages — but
no chunk exists that actually answers a meta-question about the
pipeline's own curation choices. Retrieval scores on this query were
unusually low (0.015-0.025 vs. the typical 0.1+), itself a signal that
nothing retrieved was a good match, and `generate()`'s response was an
honest, correctly-hedged answer per its existing design (ADR-0009) — not
a hallucination. This is a real gap, but not the gap it first looked
like: the system didn't fabricate wrong information, it had no way to
answer a question about itself from evidence-only retrieval.

**This touches the generation phase's system prompt, which was closed**
after a real, measured Prompt A/B comparison (2026-07-25): the current
prompt ("Prompt A") beat a second design 0.893 vs. 0.869 on claim-level
citation precision, and a later judge-rubric fix (ADR-0014) moved the
headline number to 0.946 — measured against this exact, unmodified
prompt. Any prompt change means that number no longer describes the live
system until re-measured. Per this project's standing practice, an
advisor consult was required before touching a previously-closed,
already-measured phase.

## Fable consult (Sam's explicit choice this instance, not Opus — see
`decisionlog.md`, 2026-07-26, for the full transcript)

Fable **disagreed with the blunt version of the fix Sam initially
proposed** (a hard "answer only the five countries, say 'I don't know'
otherwise" rule, modeled on the course's FAQ-bot pattern) — this is
recorded because the disagreement is real and load-bearing, not smoothed
into agreement after the fact. Reasoning: a hard country filter would
strip real, correctly-cited, useful comparative context (e.g. a Pegasus-
surveillance answer legitimately citing that Morocco, Mozambique, and
Zambia have also been reported to operate it) without fixing the actual
incident, since the incident was never about the model failing to
recognize country names — it was about a category of question (meta/
curation questions) that evidence-only retrieval structurally cannot
answer. Fable also ruled out a retrieval-level country filter or
`boost_country`-style deprioritization: CIPESA's reports aren't
single-country documents, so filtering by country would silently degrade
genuinely in-scope answers, not just suppress noise.

Fable's recommendation, adopted in full: a small, prompt-only addition —
a literal "scope card" the model can answer meta-questions from directly
(so it stops trying to infer curation facts from excerpt text), plus a
soft boundary rule (a question *primarily* about an out-of-scope country
gets a plain "the corpus doesn't cover that"; comparative mentions of
other countries inside an otherwise in-scope answer stay untouched and
cited normally). No retrieval changes. A full re-evaluation run was
recommended over disclosing the 0.946 number as merely "stale" — the
harness already exists (`run_answers`/`judge`/`evaluate_generation`), so
a real re-run is cheap enough that skipping it isn't the honest minimum.

## Decision

1. **`SYSTEM_PROMPT` in `src/generation/prompts.py` gets two additions**,
   both prompt-only, no retrieval or citation-mechanism changes:
   - A scope-card paragraph stating the real five-country/date/source
     scope, instructing the model to answer meta-questions about the
     corpus from that statement directly rather than inferring a country
     list from excerpts.
   - A new rule: a question primarily about an out-of-scope country gets
     a plain statement that the corpus doesn't cover it; comparative
     mentions of other countries inside an in-scope answer remain fine
     and are cited normally, not stripped.
   `SYSTEM_PROMPT_B` (the already-rejected Prompt B from the A/B
   comparison) is left untouched — it's a historical comparison
   artifact, not something this decision revives.
2. **A new behavioral test suite** (`docs/behavioral-test-suite.md`, 25
   questions: 10 in-scope core, 5 boundary/meta — including a direct
   regression test for this exact incident — 5 explicitly out-of-scope,
   5 adversarial) is added, scripted against `answer()` directly, to
   check that what the project advertises (README's stated scope,
   ADR-0009's evidence-grounding guarantees) is what it actually
   delivers. Sized for a solo capstone, not a new evaluation phase: run
   once now, once before the 2026-08-02 feature-freeze gate.
3. **A full re-run of the existing evaluation harness is required**
   after the prompt change — the 0.946 citation-precision figure is
   retired as "measured against the pre-scope-card prompt" and replaced
   with a fresh number measured against the real, current system. If the
   new number moves by more than roughly 2 points from 0.946, that's
   investigated before anything ships, not shipped first and explained
   later.

## Consequences

- README's Evaluation/LLM-evaluation section, `docs/presentation-
  reference.md`, and any other submission-facing citation-precision
  reference must be updated once the re-run completes — 0.946 becomes a
  named prior result, the same way 0.879 already is under ADR-0014, not
  silently overwritten.
- `docs/behavioral-test-suite.md` becomes a real, reusable project
  artifact — also usable as README evidence for the reproducibility
  rubric line, per Fable's own suggestion.
- Judge-validity against real human judgment (still open per ADR-0011's
  addendum) is unaffected by this decision — it's a separate, still-open
  limitation, not resolved or touched by the scope-card fix.
- `src/retrieval/search.py`'s existing `boost_country` re-ranking
  parameter is explicitly NOT touched by this decision — Fable's
  reasoning for ruling out retrieval-level filtering applies to it too,
  and it stays exactly as the retrieval phase left it.

## What would trigger a revisit

- If the post-fix re-evaluation run shows citation precision drops
  meaningfully (more than ~2 points) from 0.946, or the behavioral test
  suite's boundary/meta or out-of-scope categories fail at a
  non-trivial rate — that's a signal the scope-card wording itself needs
  iteration, not just a note in the report.
- If a future real user query surfaces a comparative-context case where
  the soft boundary rule strips something genuinely useful (the failure
  mode Fable specifically warned a hard filter would cause) — that's a
  signal the rule's wording is too strict, not evidence the whole
  approach was wrong.
- If the behavioral test suite itself starts feeling stale relative to
  real usage patterns (e.g., real users ask a class of question none of
  the 25 cover) — extend it rather than treating 25 as a permanently
  fixed set.
