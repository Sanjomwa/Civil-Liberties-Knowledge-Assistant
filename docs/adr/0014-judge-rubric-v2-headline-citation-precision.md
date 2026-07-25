# ADR-0014: Judge Rubric v2 as the Headline Citation-Precision Result

**Status:** Accepted, 2026-07-25.

## Context

ADR-0011 required an independent human-calibration check against the
judge's (`gpt-5.4-mini`) 0.879 aggregate claim-level citation precision
(481 claims, real corpus, real API run, 2026-07-24). That check did not
happen as designed. Two same-day pivots, both logged in `decisionlog.md`
(2026-07-25) and ADR-0011's addendum:

1. Sam found the full 65-row human read unsustainable and substituted an
   independent AI reviewer (a separate Claude instance, blind to the
   judge's verdicts). Raw agreement between the two: 28.6% (18/63 scored
   rows), with a striking property — 100% of the 45 disagreements ran one
   direction (the AI reviewer said "supported" wherever the judge said
   "partial" or "unsupported," never the reverse).
2. Sam declined to review even the resulting 47-row disagreement subset
   and asked directly why the gap was so lopsided. A second Opus 5
   consult, reading `judge.py`'s real prompt text, diagnosed a genuine
   rubric defect rather than rater bias, and recommended fixing the
   judge's prompt and re-running the full claim set instead of spending
   more owner review time.

That fix was implemented and validated (full detail in `reports.md`,
2026-07-25, and the empirical claim-shape cross-check in
`decisionlog.md`). Two real defects were confirmed directly against the
verbatim prompt text, not assumed: the `"partial"` verdict's catch-all
clause ("loosely or indirectly support it") was broad enough to mark a
claim "partial" merely for combining two separately-and-explicitly-stated
facts into one sentence — a normal one-step synthesis, not a real
precision failure — and separately, claims asserting an absence ("the
excerpts do not say X") had no explicit scoring rule and defaulted to
under-scoring even when factually accurate. Both defects were confirmed
empirically, not just diagnosed: a manual claim-shape categorization
(23 negation/hedge claims, 26 direct-match claims, 3 compound-hedge
claims, all 52 of my own "supported" reads from the original review) was
cross-tabulated against the real judge/AI-reviewer disagreement data
*before* any prompt change was made, and confirmed both defects were
real and roughly equally sized contributors (63-67% of disagreements
flipped once fixed, spread evenly across shapes, not concentrated in
negation cases as first guessed).

The fix (`JUDGE_SYSTEM_PROMPT_V2`) was validated in two stages before
being treated as real: first cheaply on the 47 known-disagreement rows
(confirmed the fix corrects real scoring mistakes without over-crediting
false claims — spot-checked a case where a claim wrongly asserted an
absence that the excerpt actually contradicted, and v2 correctly still
scored it "unsupported"), then for real across all 481 claims. Result:
citation precision moved from **0.879 (v1) to 0.946 (v2)**. Every
question category improved. Of 481 claims, 33 moved to "supported" under
v2 that weren't under v1; exactly 1 moved the other way, and that single
case held up as a legitimate, defensible judge call on inspection, not a
regression the prompt edit introduced.

## Decision

**0.946 (v2, the corrected rubric) is the headline reported
claim-level citation-precision result** in the README and any
submission-facing documentation, going forward. **0.879 (v1, the
original rubric) is retained and disclosed as the prior methodology,
superseded after a documented, empirically-validated defect was found in
it — not deleted, not silently dropped.** Both prompt versions
(`JUDGE_SYSTEM_PROMPT_V1`, `JUDGE_SYSTEM_PROMPT_V2`) remain in
`src/evaluation/judge.py`; `judge()` defaults to v1 unless
`prompt_version="v2"` is passed explicitly, so v1 remains reproducible on
demand, not overwritten.

This decision is Sam's, made directly (not a default or an
Opus-recommended path taken silently): offered three options — feature
v2 as headline with v1 disclosed as superseded; keep v1 as headline with
v2 as a secondary note; or report both with equal weight, no single
headline. Sam chose the first.

**Judge-validity remains explicitly OPEN under this ADR — this decision
does not close it.** Neither 0.879 nor 0.946 has been checked against
independent human judgment; ADR-0011's addendum already establishes that
AI-vs-AI agreement (including the validation work described above) does
not substitute for that check. Whatever document reports 0.946 as
headline must also disclose this in the same breath, not as a buried
footnote — the strength of this decision rests on the fix being a
documented, evidenced correction to a specific rubric defect, not on the
number being independently validated.

## Consequences

- README's Evaluation/LLM-evaluation section, `docs/evaluation-design.md`,
  and any other submission-facing reference to citation precision must
  report 0.946 as the primary figure, with 0.879 named explicitly as the
  original result and the reason it was superseded (not simply removed).
- The judge-validity limitation (open, no human calibration performed)
  must be stated in the same section that reports 0.946 — this is a
  disclosure requirement, not optional context.
- `data/eval/judgments_v2.jsonl` (481 rows, v2 verdicts) is the new
  source-of-record for the headline number; `judgments.jsonl` (v1)
  remains on disk, unmodified, as the historical record.
- Future evaluation-phase work (e.g., any eventual real human-calibration
  pass) should be run against v2 by default, since that is now the
  standing rubric — unless the specific purpose of that future work is
  itself to compare v1 vs. v2 again.

## Opus 5 consult

Two consults, both already covered under ADR-0011's addendum and
`decisionlog.md` (2026-07-25, two entries) — not repeated here. This ADR
formalizes the headline-number decision that followed the real v1/v2 run
those consults led to; it does not add new advisor input of its own
beyond what's already recorded there.

## What would trigger a revisit

- If a future real human-calibration pass (whenever Sam has the time or
  chooses to prioritize it) finds v2 has its own systematic bias — e.g.,
  now over-crediting claims that require a genuine inferential leap,
  not just a one-step synthesis — that would trigger a v3 rubric attempt
  or a reversion to reporting v1 as more conservative, not a silent
  continuation of v2 as-is.
- If `gpt-5.4` becomes available on this OpenAI account (currently
  403s, `gpt-5.4-mini` used throughout) — re-run both v1 and v2 with the
  stronger model and compare, since the current 0.946 is entirely a
  self-judging result on the same model family used for generation.
- If a future claim shape is found (beyond the three categorized here)
  where v2 still misscores — document it the same way this ADR
  documents the original two defects, rather than assuming v2 is a
  complete fix.
