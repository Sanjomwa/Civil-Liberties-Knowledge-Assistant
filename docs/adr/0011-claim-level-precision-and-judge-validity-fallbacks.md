# ADR-0011: Claim-Level Citation Precision, Judge-Validity Statistical Fallback, and Judge-Model Fallback Policy

**Status:** Accepted, 2026-07-23.

## Context

Before handing `docs/evaluation-design.md` and ADR-0010 to Claude Code, a
second Opus 5 review pass (per Sam's own request, now that Opus 5 is the
project's advisor model — see root workspace `CLAUDE.md`) was run
specifically to catch anything a cold execution session would have to
guess on. It found three problems severe or subtle enough to change what
the evaluation phase's numbers actually mean, not just how the code is
organized — crossing this project's "genuinely novel decision" bar the
same way ADR-0009 and ADR-0010 did. Full review in `decisionlog.md`,
2026-07-23 (second entry that date).

First: ADR-0010 defined citation precision as "per-citation," but the
review found this was underspecified in a way that actively produces a
wrong number. `citations.py`'s `parse_citations()` dedupes to one record
per distinct marker number for the whole answer — the mapping from a
specific claim (sentence) to the marker(s) attached to it is discarded
after that function runs. A judge built directly on that structure has no
claim text to score against, and would either have to reinvent claim
extraction inconsistently or silently misdefine the metric. Separately,
the prompt (`prompts.py`) actively encourages multi-marker citations like
`[4][7]` for claims with corroborating sources — judging each cited chunk
of a multi-marker claim in isolation would mark a genuinely
well-supported, multiply-corroborated claim as "partial" for a
measurement artifact, not a real precision failure.

Second: ADR-0010 set Cohen's κ ≥ ~0.7 as the judge-validation go/no-go
threshold. The review flagged a real statistical risk: given the
generation phase's own zero-fabrication smoke-test result, the
human-review sample is likely to skew heavily toward `supported` on both
the judge's and the human's side. Under that kind of low-prevalence-of-
disagreement condition, κ can be mathematically unstable or degenerate
(near-zero or undefined) even when raw agreement is high — a known
property of the statistic, not a sign the judge is actually unreliable. A
hard κ-based gate risks blocking the phase two weeks before the 10 August
deadline over a statistical artifact, not a real problem.

Third: the three project documents (`evaluation-design.md`, ADR-0010, the
handoff prompt) each described the calibration judge model slightly
differently ("stronger/cross-provider," "full `gpt-5.4`," "stronger/
different") with no stated fallback if that model isn't actually enabled
on this OpenAI account/project — a real, precedented risk, since
`generate.py`'s own code comment already records that `gpt-4o-mini` 403'd
on this exact account. "Cross-provider" is also likely infeasible in
practice with a single OpenAI API key.

## Decision

### Citation precision is defined at the claim level, using the union of that claim's cited chunks

A **claim** is a sentence (or clause ending in terminal punctuation) in
`answer_markdown` that contains at least one valid `[n]` marker (`1` to
`len(chunks)`, same validity rule as `citations.py`'s `MARKER_RE`) —
extracted freshly from the raw answer text, not derived from
`parse_citations()`'s deduped output. If a claim carries multiple markers
(`[4][7]`), the judge receives the **union** of all cited chunks' text in
one call and renders a single verdict for that claim as a whole — never
one call per marker, never scoring a multi-source claim against only one
of its sources in isolation.

```
judge(claim_text: str, cited_chunk_texts: list[str]) -> {"verdict": "supported" | "partial" | "unsupported", "reason": str}
citation_precision = supported_claims / (supported_claims + partial_claims + unsupported_claims)
```

This redefines the unit of ADR-0010's original `judge()` signature
(`cited_chunk_text: str` becomes `cited_chunk_texts: list[str]`) and the
precision denominator (claims, not raw marker occurrences or
`parse_citations()`'s deduped citation count). ADR-0010's three-way
verdict, isolated-entailment framing (no full answer, no question, no
other retrieved chunks passed in), and the general judge-model-choice
reasoning are otherwise unchanged — this ADR amends the input shape and
metric unit, not the underlying protocol design.

**Consequence for data flow:** `run_answers.py` must independently call
`search()` (same query, recorded default hybrid k=10) to reconstruct and
persist the retrieved chunk texts (`{chunk_id: text}`) alongside each
`answer()` result — `answer()` itself is not modified, since generation
is a closed, real-smoke-tested phase and this project's standing rule is
that closed phases get a new ADR for any real change, not a silent edit.
Calling `search()` a second time is cheap (local embedding + `minsearch`,
no API cost) and deterministic given the same corpus and recorded
default, so it reliably reconstructs the same top-10 set `answer()` used
internally.

### Judge-validity fallback when Cohen's κ is statistically uninformative

Report the full 3×3 confusion matrix (judge verdict × human verdict), raw
percent agreement, and `n` alongside κ, always — not κ alone. If the
off-diagonal (disagreement) cell count is small (fewer than ~10 total
disagreements across the sample) or κ is undefined/degenerate despite
high raw agreement, label κ explicitly **"uninformative under this
sample's low disagreement prevalence"** rather than treating a low or
undefined κ as an automatic fail. In that specific case, fall back to a
raw-agreement-plus-error-direction check as the actual go/no-go: raw
agreement ≥ ~90% **and** zero cases where the judge said `supported` but
the human said `unsupported` (the single costliest error direction for a
citation-trust system — a false "supported" is worse than a false
"partial" or a missed `partial`/`unsupported` distinction). Gwet's AC1
may optionally be computed and reported alongside κ as a more
prevalence-robust alternative, but is not required to unblock the phase.

### Judge model: one ordered, checked preference list — no more inconsistent phrasing across documents

Replace every "stronger/cross-provider," "full `gpt-5.4`," and
"stronger/different" phrasing across `evaluation-design.md`, ADR-0010,
and the handoff prompt with one policy, checked empirically before use
(same discovery method `ground_truth.py`'s `LLM_MODEL` was found with —
don't assume availability): **try `gpt-5.4` first** (a stronger,
same-provider model — simplest integration, no new API key or client
needed). **If `gpt-5.4` is not enabled on this OpenAI account/project,
fall back to `gpt-5.4-mini`** (the same model the generator uses) **and
explicitly record self-judging as a named, reported limitation** in the
evaluation report — not a silent fallback. Drop "cross-provider" from the
policy entirely; it is almost certainly infeasible with a single OpenAI
key and was never a real option, just imprecise phrasing.

## Consequences

- `src/evaluation/judge.py`'s real signature is
  `judge(claim_text: str, cited_chunk_texts: list[str]) -> {verdict, reason}`,
  not the single-chunk-text signature ADR-0010 originally specified.
- `src/evaluation/run_answers.py` must persist retrieved chunk text per
  query (a second `search()` call, not a modification to `generate.py`).
- Citation precision's reported unit is **claims**, not raw citation
  markers — this must be stated explicitly in the evaluation report's own
  methodology section, since it's a real definitional choice a reader
  could otherwise misread as "per citation marker."
- The evaluation report's judge-validation section must show the
  confusion matrix and raw agreement unconditionally, with κ (or the
  fallback verdict) reported alongside, not κ alone.
- If `gpt-5.4` isn't available and the `gpt-5.4-mini` self-judging
  fallback is used, the evaluation report must say so in plain language,
  not bury it in a log line.

## Opus 5 consult

Consulted 2026-07-23 (second review pass, run specifically to check
`evaluation-design.md`, ADR-0010, and `next-session-handoff.md` together
before handoff — the project's now-updated advisor model, Claude Opus 5,
per Sam's same-day instruction to move off the prior Opus version). The
review read the real code directly (`generate.py`, `citations.py`,
`prompts.py`, `search.py`, `.gitignore`) rather than reasoning from the
design docs alone, and found five ranked issues; this ADR covers the
three that change what the evaluation phase's numbers mean or claim, not
just how the code is organized. The other findings (claim/chunk
persistence mechanics beyond the ADR-level data-flow consequence above,
the metric-2 coverage/refusal dataset gap, contradiction-search budget,
run resumability, human-review file format and a real gitignore/licensing
risk, labeled-supplement category tagging, and reporting
`invalid_markers`/`unsupported_paragraphs`) are folded directly into
`docs/evaluation-design.md` and `next-session-handoff.md`, not here — see
`decisionlog.md`, 2026-07-23, for the full review transcript and the
complete list.

## What would trigger a revisit

- If claim extraction (sentence-splitting on `answer_markdown`) turns out
  to missegment real generated answers often enough to produce nonsense
  claim text (e.g., abbreviations breaking sentence-boundary detection) —
  revisit the extraction method, not the underlying claim-level unit
  decision.
- If `gpt-5.4` becomes available on this OpenAI account after an initial
  `gpt-5.4-mini`-fallback run — re-run the calibration subset with the
  stronger model and compare, rather than assuming the fallback result
  stands permanently.
- If the raw-agreement-plus-error-direction fallback itself proves too
  permissive in practice (e.g., real disagreement volume turns out higher
  than expected and κ becomes well-defined and low) — trust the
  well-defined κ over the fallback at that point; the fallback exists for
  the low-disagreement-prevalence case specifically, not as a permanent
  replacement for κ.
