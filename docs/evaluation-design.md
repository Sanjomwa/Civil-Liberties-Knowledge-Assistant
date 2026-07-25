# LLM Evaluation Phase Design (Pre-Implementation Reference)

**Status: design complete, reviewed twice, 2026-07-23 — not yet handed to
Claude Code, no code exists yet.** All four open questions in the first
pass were resolved via an Opus consult the same day (full transcript in
`decisionlog.md`, 2026-07-23); two of the four crossed this project's
"genuinely novel decision" threshold and are recorded in
`docs/adr/0010-citation-judge-protocol-and-contradiction-test-gap.md`. A
**second review pass**, run with Claude Opus 5 (the project's advisor
model as of today — see root workspace `CLAUDE.md`) specifically to catch
anything a cold execution session would have to guess on, found real
gaps in that first design — most seriously, that the judge's own two
inputs (claim text, cited chunk text) were never actually persisted
anywhere. Three of those findings changed what the evaluation numbers
mean, not just code organization, and are now
`docs/adr/0011-claim-level-precision-and-judge-validity-fallbacks.md`.
This document reflects both review passes — see that ADR for the fuller
reasoning behind the claim-level precision definition, the κ
statistical fallback, and the judge-model fallback policy. Synthesizes
`04-evaluation/project/project_evaluation_plan.md`'s pre-existing Tier 2
design (written before retrieval or generation existed, specifically so
evaluation wouldn't be retrofitted), `04-evaluation/project/
evaluation_checklist.md`'s "before adding a generation layer" checklist
(now directly actionable), and the real, already-built interfaces from
both prior phases. Mirrors the shape of `docs/retrieval-design.md` and
`docs/generation-design.md`, written the same way before code existed in
each of those phases. No code exists yet at time of writing.

**Frozen principles this phase inherits, unchanged:** sequential, simple
pipeline — no evaluation framework (Ragas/DeepEval/TruLens) is being
added; project_evaluation_plan.md's own explicit non-goal ("do not add an
evaluation framework... before there's a generation layer") is now
satisfied (generation exists), but that doesn't retroactively argue for
pulling one in now either — the plan below is hand-rolled, same as every
prior phase. Any real departure from what's already decided gets an ADR.

---

## What already exists, ready to reuse

**Generation:** `answer(query: str) -> dict` (`src/generation/generate.py`)
returns `{query, answer_markdown, citations, invalid_markers,
unsupported_paragraphs, sources, sourcing, usage}`. `citations` is a list
of `{marker, chunk_id, doc_id, pages}` — already resolved against real
chunk records, not raw model output.

**Real gap found on second review, worth stating plainly: `answer()`
does not return chunk text, and `citations()`'s own `parse_citations()`
dedupes to one record per distinct marker number for the whole answer —
the mapping from a specific claim (sentence) to the marker(s) attached to
it is discarded once that function runs.** Neither the judge's claim text
nor its chunk text exists in any saved artifact today. This phase's own
`run_answers.py` must independently call `search()` (same query, same
recorded default hybrid k=10) to reconstruct and persist the retrieved
chunk texts, and must extract claims freshly from `answer_markdown`
itself, not from `parse_citations()`'s deduped output. See ADR-0011 for
the full reasoning; see "Pipeline shape" and "File structure" below for
what this means concretely.

**Retrieval ground truth:** `data/eval/ground_truth_filtered.json` — 97
real questions, already stratified (`general` 64 / `multi_country` 22 /
`ooni_methodology` 11), already mechanically filtered for circularity
(the 4+-word phrase-overlap filter, function-word-aware exemption),
already manually reviewed twice by Sam. Each entry carries
`correct_chunk_id`. This set exists specifically because building good
ground truth was expensive (two full regenerate passes, two manual
circularity reviews, a mechanical filter, an Opus+Fable review) — reusing
it here rather than building a second, parallel set is the default
assumption below, flagged as an open question, not a settled decision.

**Known retrieval numbers already measured, relevant to judging what
generation does with what it's given:** recorded default hybrid/k=10,
strict Hit Rate ~0.644 / neighbor-aware Relaxed Hit Rate ~0.812 (most of
the gap is same-document chunk-overlap, not true misses); HR@3/HR@5
noticeably below HR@10; `multi_country` has a real, root-caused, not
retrieval-fixable MRR gap (text search still wins there); hybrid's
source-diversity@10 is narrower than plain text search's, deliberately
not retrieval-fixed — this phase inherits that tension directly, since
"flag thin/single-sourced evidence" was explicitly deferred here.

**Real generation smoke-test outputs already exist** (`reports.md`,
2026-07-24) — four real `answer()` calls, verified clean, spanning
exactly the sourcing-footer cases this phase needs to evaluate against:
single-org/multi-doc (Run 1), single-org/single-doc — the strongest thin
case (Run 3, OONI Tanzania LGBTIQ censorship), and multi-org/multi-doc
(Runs 2 and 4). These four are real, already-verified examples, not
hypothetical — useful as seed cases for the thin/contradictory slice
below, not just as smoke-test history.

---

## What this phase measures

Directly from `project_evaluation_plan.md`'s Tier 2 sections ("How
evidence quality should be measured," "How citation quality should be
measured") and `evaluation_checklist.md`'s "Before adding a generation
layer" items — this phase does not invent new evaluation goals, it
implements ones already specified:

1. **Citation precision** — of all citations a generated answer produces,
   what fraction are both structurally valid (real `doc_id`/`chunk_id`,
   already guaranteed by `citations.py`'s mechanical parsing) and
   semantically supported (the cited chunk's text actually supports the
   specific claim attached to it — not just related terms). This is the
   plan's own stated core acceptance metric, not one metric among many.
2. **Coverage/refusal correctness** — does the system correctly say "the
   evidence doesn't answer this" when that's true, without over-claiming
   or over-refusing. `unsupported_paragraphs` (already computed
   mechanically by `citations.py`) is a partial proxy; this phase adds
   the human-reviewed check the plan calls for. **Real gap found on
   second review: the 97-question reuse set and the synthesis supplement
   are both answerable-by-construction — nothing in the original design
   actually tested refusal.** Fixed by **Decision 5** below: a small,
   deliberately unanswerable/out-of-scope question slice.
3. **Thin/contradictory-evidence handling** — does the sourcing footer
   fire correctly (already smoke-tested against three real cases per
   `reports.md`), and separately, does the model's prose actually surface
   disagreement when cited excerpts disagree (ADR-0009's prompt-only
   mechanism — not yet verified against a real contradictory case, since
   none of the four smoke-test queries happened to hit one).

---

## Decision 1 — reuse the 97-question retrieval ground truth, plus a small labeled supplement

**Resolved: reuse as the primary set, supplement narrowly, don't rebuild.**
`correct_chunk_id` turns out to be irrelevant to citation precision — the
metric judges each citation against *what the answer actually cited*, not
against retrieval gold, so single-chunk-anchored questions don't
invalidate the set the way they might have for a retrieval-shaped metric.
The real weakness is that single-chunk questions under-exercise
multi-chunk synthesis, which is exactly where a mis-attached `[n]` marker
is most likely to appear. Fix: add ~10-15 open-ended "researcher
investigating internet freedom" synthesis questions as a clearly labeled
supplement (not folded silently into the 97), not a full fresh set — the
deadline doesn't justify rebuilding, and reuse keeps the direct tie-back
to retrieval's own already-measured per-question numbers (a
`multi_country` question retrieval already struggles with becomes a real
test of whether generation degrades gracefully on weak retrieval, not
just a repeated measurement). Judged a refinement within already-open
design space, not ADR-worthy.

## Decision 2 — LLM-judge design: per-claim, isolated entailment, different judge model for calibration

**Resolved — see `docs/adr/0010-...md` for the original protocol design
and `docs/adr/0011-claim-level-precision-and-judge-validity-fallbacks.md`
for a real correction found on second review, before this had been built
against.** The judge scores one **claim** at a time — a sentence in
`answer_markdown` carrying at least one valid `[n]` marker, extracted
freshly from the raw answer text, not from `parse_citations()`'s deduped
output (that function collapses to one record per marker *number* for
the whole answer, discarding which claim each marker was actually
attached to — a real gap ADR-0011 exists to fix). If a claim carries
multiple markers (`[4][7]`), the judge sees the **union** of all cited
chunks' text in one call and renders one verdict for the claim as a
whole — never per-marker in isolation, which would wrongly mark a
genuinely well-corroborated multi-source claim as `partial`. Each call
still sees only the claim text and its cited chunk text(s) — nothing
else (no full answer, no question, no other retrieved chunks) — which
structurally removes the self-preference risk a whole-answer judge would
carry. Three-way verdict (`supported | partial | unsupported`), not
binary.

```
judge(claim_text: str, cited_chunk_texts: list[str]) -> {"verdict": ..., "reason": str}
citation_precision = supported_claims / (supported_claims + partial_claims + unsupported_claims)
```

Judge model, per ADR-0011: try `gpt-5.4` first (checked against what's
actually enabled on this OpenAI account/project, same discovery method
`ground_truth.py`'s `LLM_MODEL` used — don't assume). If unavailable,
fall back to `gpt-5.4-mini` (the generator's own model) **and explicitly
record self-judging as a named limitation** in the evaluation report —
not a silent fallback. Judged genuinely novel — this is ADR-0010/0011.

## Decision 3 — human-review sampling: stratify by verdict for judge calibration, by category for deployment review

**Resolved: not a flat percentage in either case.** Judge-validation
sample: ~50-80 claim-judgments, **oversampling every
`unsupported`/`partial` verdict** (rare and decision-critical) plus a
random sample of `supported` verdicts. Report the full 3×3 confusion
matrix, raw percent agreement, and `n` **always**, with **Cohen's κ**
alongside — not κ alone. **Real risk found on second review, fixed in
ADR-0011:** given generation's own zero-fabrication smoke-test result,
this sample is likely to skew heavily `supported` on both sides, and κ
is mathematically unstable/degenerate under low disagreement prevalence
even when raw agreement is high — a property of the statistic, not
evidence the judge is unreliable. If disagreements are too few (fewer
than ~10 total) for κ to be informative, label it explicitly
"uninformative under this sample's low disagreement prevalence" and use
the fallback go/no-go instead: raw agreement ≥ ~90% **and** zero cases
where the judge said `supported` but the human said `unsupported` (the
single costliest error direction). Deployment citation-precision review
(the separate, `evaluation_checklist.md`-required human check before any
deployment/demo milestone): a fixed count per stratum (~15 each across
`general`/`multi_country`/`ooni_methodology`/the new supplement/the
refusal slice — see Decision 5), not a global percentage. Judged a
refinement within already-open design space beyond the κ-fallback piece
(which is ADR-0011), not independently ADR-worthy.

## Decision 5 — a small, deliberately unanswerable question slice, to actually test refusal correctness

**New, added on second review — closes a real gap: metric 2
(coverage/refusal correctness) was listed as in scope but had no
dataset.** Add ~8-10 questions deliberately outside the corpus's real
coverage or scope — e.g., a topic/country/time period the architecture
excludes, or a real known gap already documented in this project (Rwanda
has zero OONI coverage; Freedom House has no Tanzania FOTN chapter) —
each labeled with an expected "the system should decline or say the
evidence doesn't answer this" outcome, as a distinct labeled slice
alongside the 97-question reuse and the synthesis supplement. Reviewed
the same way as `unsupported_paragraphs`-flagged answers: does the system
correctly decline rather than stretch unrelated retrieved chunks into an
answer. Not ADR-worthy — a scope-closing addition within
`evaluation_checklist.md`'s own already-stated requirement, not a new
architectural decision.

## Decision 4 — thin/contradictory-evidence slice: construct thin deterministically, search for contradiction empirically, document the gap if none found

**Resolved — see ADR-0010 for the full reasoning; this is the ADR's
other half.** Thin-evidence cases: already have one real, confirmed
example (OONI's Tanzania LGBTIQ-censorship coverage — genuinely
single-document in the real corpus); generate ~5-8 more the same way,
deterministically, by identifying single-org/single-topic coverage
directly from corpus metadata — checkable, not guesswork.
Contradictory-evidence: search the real corpus first rather than assuming
none exists — target likely axes where independent orgs plausibly report
the same event differently (a shared shutdown's exact dates, attributed
cause, stated scale), retrieve cross-org chunks on shared real events, run
a cheap pairwise disagreement scan, human-verify any survivor. **If none
survive: do not fabricate one.** Document the absence as a real, named
evaluation gap, and add a clearly-labeled synthetic-fixture unit test that
verifies the contradiction-handling *mechanism* alone (a hand-built pair
of excerpts engineered to disagree) — explicitly excluded from the
real-corpus evaluation metrics, so it can never inflate or deflate the
real citation-precision number.

**Real gap found on second review: the search itself was unbounded and
could otherwise eat an unpredictable amount of a session.** Bounded,
concretely: name 5-8 candidate shared real events across organizations up
front — known recurring examples in this corpus include Kenya's June 2024
#RejectFinanceBill2024 shutdown, Uganda's January 2026 election shutdown,
Uganda's 2021 election blackout, and Ethiopia's 2023 social-media
blocking — `search()` each event, form cross-organization pairs from each
event's top-10 results, cap the pairwise disagreement scan at roughly 50
calls total, and declare the search complete (absence documented, not
retried) once that budget is spent, rather than searching indefinitely.

---

## Decision 6 — Prompt A/B comparison, added 2026-07-25 (ADR-0012 Decision 2)

**Why this decision exists:** a rubric audit (ADR-0012, 2026-07-24) found
this phase's own real run — 0.879 aggregate claim-level citation
precision — only ever evaluated **one** generation approach, when the
rubric's 2-point LLM-evaluation bar requires comparing multiple approaches
and picking a winner. This section amends the phase with the missing
comparison. ADR-0010/ADR-0011's judge protocol is unchanged — only a
second generation approach and a comparison harness are new.

**Model held fixed.** Both prompts run on `gpt-5.4-mini`, the existing
recorded default. A model-vs-model comparison was explicitly rejected
(Opus 5 consult, 2026-07-24) — it would confound cost/latency with prompt
quality and duplicate the judge's own already-disclosed self-judging
limitation. Isolating prompt design as the only variable is the point.

**Prompt B is a genuine, evidence-motivated hypothesis, not a cosmetic
rewrite.** A spot-check of Prompt A's real output (`reports.md`, Section
5) found two real precision failures, not measurement artifacts: a
misattribution (an allegation attributed to the wrong named individual
within a multi-entity chunk) and a universal-negative overclaim ("the
excerpts do not mention any other online services," when one did). Both
look like attention/tracking failures from writing fluent prose directly
across several excerpts, not fabrication. Prompt B (Opus 5-designed,
2026-07-25) targets these directly with a two-phase structure: an
explicit EVIDENCE phase enumerating, per named subject, exactly what each
relied-on excerpt states (forcing subject-binding to happen before fluent
prose is generated), followed by an ANSWER phase that may only make
claims traceable to an EVIDENCE line, plus an explicit, bounded rule for
negative claims (state the absence as bounded, and name any related item
that IS present rather than denying the whole category — the direct fix
for the X/Twitter overclaim). Full prompt text: `src/generation/prompts.py`,
`SYSTEM_PROMPT_B`.

```python
SYSTEM_PROMPT_B = """You are a research assistant answering questions about internet \
censorship and digital rights in East Africa, using only the numbered excerpts \
provided below. Your audience is researchers and journalists who will check your \
citations against the real source documents -- accuracy and honesty about the \
limits of the evidence matter more than a confident-sounding answer.

Work in two phases and output both, in this order.

PHASE 1 -- EVIDENCE
Before writing any answer, list the excerpts you will rely on, one line each:
[n] <subject> -- <what this excerpt actually states about that subject, in your own \
words, 25 words or fewer>
Rules for this list:
- Name the subject explicitly. If one excerpt concerns several people, \
organisations, countries or dates, write a separate line for each subject. Never \
carry a detail stated about one named subject over to another.
- Record only what the excerpt states. Do not infer, do not merge two excerpts \
into one line, do not complete a partial statement.
- List only excerpts you will actually cite. If nothing supports an answer, write \
exactly: [none]

PHASE 2 -- ANSWER
Then write the answer under the heading ANSWER.
- Every factual claim must correspond to a line you wrote in PHASE 1 and must \
carry that line's citation marker(s), like [2] or [4][7]. Cite by excerpt number \
only -- never invent a page number, title, or source; the citation text is \
generated separately from what you write.
- Attribute each statement to exactly the subject named on its PHASE 1 line.
- Do not claim the excerpts lack something unless you have checked every excerpt \
provided. If you do, write it as bounded ("none of the excerpts state X"), never \
as a claim about the world, and if any excerpt mentions a related item, name that \
item instead of denying it.
- If the excerpts disagree on a point, state both positions, each with its own \
citation. Never average, blend, or silently pick a side.
- If PHASE 1 is [none], or the evidence is too thin to answer, say so plainly and \
stop. Do not fill the gap with outside knowledge.
- Plain, direct prose. No markdown headers or bullet lists inside the answer \
unless the question asks for a list."""
```

**Real risks flagged, to watch for in the results, not just accept a
headline number:**
- *Denominator confound.* Citation precision's denominator is claims —
  Prompt B can "win" purely by making fewer, more hedged claims. Report
  **claims-per-answer and abstention rate alongside precision** for both
  arms; a precision gain paired with a materially lower claim count is
  unresolved, not a win.
- *Restatement laundering.* Near-verbatim EVIDENCE lines could make a
  weakly-supported claim look supported to a judge seeing only the claim
  text — worth a manual spot-check pass on a few Prompt B answers, same
  discipline as Prompt A's own spot-check.
- *Over-abstention.* The stricter negative-claim rule may cause Prompt B
  to abstain on genuinely answerable thin cases — this would show up as
  precision going up while genuinely useful answers go down; the refusal
  slice + a manual read of a few abstentions should catch this.
- *Token/latency cost.* The EVIDENCE phase roughly doubles output length
  — record and report token cost per arm, not just precision.

**Implementation requirement, not optional:** claim extraction for Prompt
B's answers must operate on the `ANSWER` section only, with the `PHASE 1
— EVIDENCE` block stripped first. The EVIDENCE lines contain `[n]`
markers too — naive sentence-splitting-plus-marker-detection (the
existing claim-extraction logic) would score EVIDENCE lines as claims,
corrupting the comparison. This is a real, specific parsing requirement,
not a suggestion.

**Methodology:** retrieval held fixed — call `search()` once per question
and reuse the identical retrieved chunk set for both prompts on that
question, so retrieval variance never confounds the prompt comparison.
Same `temperature=0.2` for both arms (unchanged from `generate.py`'s
existing default). Run on a stated subset of the question set (not
necessarily the full 122 — the report must state the exact N and the
sampling method, e.g. a stratified subset preserving category
proportions), judged with the existing, unmodified claim-level judge.
Report per-arm: aggregate citation precision, claims-per-answer,
abstention rate, and token cost — pick a winner explicitly and make it
`generate.py`'s new recorded default (same "closed phase gets a real,
documented change" discipline as every prior post-closure fix).

---

## Pipeline shape (resolved, per Decisions 1-4 above)

1. Run `answer()` over the evaluation question set — the 97-question
   reuse, the ~10-15 question labeled synthesis supplement (Decision 1),
   and the ~8-10 question refusal slice (Decision 5) — saving every real
   result (`answer_markdown`, `citations`, `sourcing`, `usage`, and a
   `category` tag) to a results file. **Also independently call
   `search()`** for the same query (same recorded default) and persist
   the retrieved `{chunk_id: text}` map alongside the result — ADR-0011's
   fix for the fact that `answer()` itself discards chunk text. Pure
   reuse of `generate.py`/`search.py`, no modification to either.
2. Extract claims freshly from each result's `answer_markdown` (sentences
   containing at least one valid `[n]` marker), and for each claim call
   the judge with the claim text and the **union** of its cited chunks'
   text — isolated entailment, three-way `supported | partial |
   unsupported` verdict with a short justification (Decision 2 /
   ADR-0010 / ADR-0011).
3. Compute citation precision at the **claim** level (aggregate and
   per-category, matching retrieval's own per-slice reporting discipline
   — a single aggregate number already proved misleading once this
   project, per the retrieval phase's `multi_country` finding). `partial`
   reported as its own count, never silently folded into `supported`.
   Also report `invalid_markers` and `unsupported_paragraphs` counts
   (already computed for free by `citations.py`, previously unused here)
   — direct evidence for the "structurally valid" half of citation
   precision. Separately, review the refusal slice (Decision 5): did the
   system correctly decline rather than fabricate.
4. Run the thin/contradictory-evidence slice (Decision 4 / ADR-0010)
   separately and report it distinctly, not folded into the main
   precision number — it's a different question (does the *sourcing
   footer and prose* correctly represent evidence quality) from citation
   precision (does each *citation* individually hold up). The evaluation
   report carries an explicit, visible line on whether a real
   contradiction was found and tested, or whether the contradiction
   mechanism rests on the synthetic fixture alone.
5. Sam performs the human-reviewed sample against judge verdicts
   (Decision 3): stratified by verdict for judge calibration (Cohen's κ,
   go/no-go ~0.7), by category for the deployment citation-precision
   review — same "Sam reviews for real, not a pro-forma pass" discipline
   the retrieval-phase circularity review established.

---

## Cost and latency

Explicitly an **offline, batch evaluation script**, not a live/online
judge in the request path — this phase does not touch `generate.py`'s
runtime behavior at all. Worth stating plainly because Module 5's own
lesson notes (`05-monitoring/notes/03_common_pitfalls.md`, pitfall #4,
"synchronous judge latency/cost") flag exactly this failure mode for a
*monitoring*-phase judge sitting in a live request path — not applicable
here by construction, but worth confirming this phase doesn't
accidentally set a precedent that gets copy-pasted into monitoring later
without re-examining the online/offline distinction.

Rough cost shape (not yet precise, and revised on second review): roughly
112 `answer()` calls (97 reuse + ~10-15 supplement, one `gpt-5.4-mini`
call each; the ~8-10 refusal-slice questions add a similar number) plus
roughly **1 judge call per claim** (a sentence carrying one or more
markers), not per raw citation marker — multi-marker claims collapse to
one call each (Decision 2/ADR-0011), so this is likely somewhat *fewer*
than the original per-marker estimate suggested, not more. **Real gap
found on second review: the original estimate only counted calls, not
tokens** — each `answer()` call's prompt carries all 10 retrieved chunks
(~1500 characters each), which dominates actual cost far more than call
count alone suggests; record real input/output token totals once run,
not just call counts, per `evaluation_checklist.md`'s own "cost per
evaluation run recorded" requirement. `run_answers.py` should be
**resumable** (JSONL append-per-question, not one large JSON written only
at the end, plus `--limit` and `--resume` flags) given the real time/cost
of a full run — a second real gap found on review, since neither
`ground_truth.py` nor `generate.py`'s own `main()` needed this at their
smaller/single-query scale.

---

## File structure (working draft)

New top-level `src/evaluation/`, matching `src/retrieval/`'s and
`src/generation/`'s one-responsibility-per-file pattern:

- **`run_answers.py`** — runs `answer()` over the chosen question set
  (97-reuse + synthesis supplement + refusal slice, each tagged with a
  `category`), **also independently calls `search()`** to persist
  retrieved chunk text (ADR-0011 — `answer()` itself doesn't return it),
  writes results incrementally (JSONL, resumable — `--limit`/`--resume`)
  to `data/eval/generation_results.jsonl`.
- **`judge.py`** — `judge(claim_text: str, cited_chunk_texts: list[str])
  -> {verdict, reason}` (ADR-0010/0011: isolated entailment, claim
  extracted fresh from `answer_markdown`, union of a claim's cited chunks
  passed together, no answer/question/other-claim context), the judge
  prompt, the ordered judge-model check-and-fallback (`gpt-5.4` →
  `gpt-5.4-mini`, ADR-0011), and `supported`/`partial`/`unsupported`
  parsing. Also owns the synthetic contradiction-mechanism fixture test
  (ADR-0010), kept structurally separate from real-corpus scoring.
- **`evaluate_generation.py`** — aggregates judge verdicts into
  claim-level citation precision (aggregate + per-category, 3-way
  breakdown), reports `invalid_markers`/`unsupported_paragraphs` counts,
  reviews the refusal slice (Decision 5), writes the human-review sample
  file stratified by verdict (CSV or JSONL, a stable `judgment_id`, a
  blank `human_verdict` column, mirroring `ground_truth.py`'s
  `write_review_sample()` pattern), and — once Sam's review is back —
  computes the confusion matrix, raw agreement, and Cohen's κ (or the
  ADR-0011 fallback verdict when κ is uninformative) via a
  `--score-review` flag, joining back on `judgment_id`. **Real risk found
  on second review: the human-review file will contain real cited chunk
  excerpts, and `data/eval/` is not gitignored** (unlike `data/chunks/`,
  which is, for licensing reasons — see `docs/licensing.md`) — either add
  the review-sample files to `.gitignore` explicitly, or keep the
  full-chunk-text version local-only and commit only `judgment_id`/
  verdict/reason columns. Decide and implement before the first real
  push, not after.

---

## Explicitly not building this phase

Mirrors both prior phases' "not now" calls, same deadline-proportionality
reasoning: no evaluation framework (Ragas/DeepEval/TruLens); no
generation prompt/model comparison (still explicitly deferred to "later,
if ever" per `generation-design.md`); no reranking evaluation (retrieval
scope); no online/production monitoring (a later, separate phase); no NLI
contradiction detection (still ADR-0009's deferred item).

## What would trigger a revisit

- If citation precision comes back low enough (threshold TBD, pending the
  Opus consult) to warrant the second LLM verification/grounding pass
  `generation-design.md` explicitly deferred — this phase is the actual
  trigger condition for that deferred work, not a hypothetical.
- If the human-reviewed sample disagrees with the LLM judge often enough
  to distrust it at scale — revisit judge model/prompt before trusting
  further judge-only runs.
- If Question 1's reuse decision turns out to under-exercise multi-chunk
  synthesis in practice (e.g., judge results cluster suspiciously high
  because questions are "too easy" for a single-chunk-anchored answer) —
  build the supplementary generation-specific question set then, not
  preemptively.
