# ADR-0009: Index-Only Citation Protocol and Split Thin/Contradictory Evidence Flagging

**Status:** Accepted, 2026-07-24.

## Context

The architecture's core acceptance principle: every answer must cite
its sources, and when evidence is thin or contradictory, the system
must say so explicitly rather than smoothing over the uncertainty. This
is the project's stated reason for existing, not one requirement among
many. Two real design questions block any generation implementation:
how does the system produce a citation without an LLM being free to
fabricate one, and how does it decide whether to caveat an answer as
thin or contradictory.

A Fable design consult was run 2026-07-24 (full transcript in
`decisionlog.md`, same date) specifically because both questions are
genuinely novel design surfaces for this project, not extensions of an
already-decided pattern, and this is the one phase where a citation
mistake directly contradicts the project's own stated purpose.

## Decision

### Citation protocol: the LLM never writes a citation, only an index

Retrieved chunks are numbered `[1]`..`[10]` in the generation prompt.
The model is instructed to attach `[n]` markers to claims in its answer,
referring only to those numbered excerpts. It is never asked to produce
a title, page number, or URL directly. `citations.py` parses every
`[n]` marker mechanically after generation and resolves it to the real
chunk (`chunk_id`, `doc_id`, `pages`) and the real document metadata
(`data/metadata/{doc_id}.json`'s `declared` block: `title`, `url`,
`organization`, `publication_date`) to render the actual citation.

This makes a fabricated page number or title structurally impossible —
the model has no channel to produce one, since it never generates
citation text itself, only a reference to something that already
exists. Any `[n]` outside the valid 1-10 range is dropped by the
validator; any claim-bearing paragraph with zero markers is flagged as
a real signal worth surfacing.

**Rejected: a second LLM grounding/verification pass**, which would
catch a different failure mode (a real citation whose source doesn't
actually support the claim made). Rejected for now on cost/complexity
grounds (2x latency and API cost, a new failure surface of its own) and
because the evaluation plan's own human-reviewed citation-precision
check is the more trustworthy mechanism for exactly this failure mode,
per that plan's explicit preference for human review over LLM-judge
review on citation trustworthiness specifically. Kept as the documented
fallback if that review finds a real, non-trivial error rate.

### Thin evidence: mechanical, computed on the cited subset, not the retrieved one

**Rejected approach, considered first:** a pre-generation check reusing
retrieval's own source-diversity@10 metric (distinct orgs/docs in the
*retrieved* top-10) to decide, before the LLM sees the prompt, whether
to inject a "sourcing is thin" instruction. Rejected because it measures
availability, not what the answer actually depends on — retrieval
always returns 10 chunks regardless of the eventual citation count, so
this would misfire in both directions: flagging "thin" when broad
retrieval existed but only 2 strong sources were genuinely needed, and
missing real thinness when most of the 10 retrieved chunks go unused.

**Adopted:** after `citations.py` parses the actual `[n]` markers used
in the generated answer, compute distinct organizations, distinct
documents, and publication-date spread over that **cited** subset only.
Render this as a factual sourcing footer the LLM never touches or
influences — e.g. "Sourcing: all cited evidence comes from one
organization (OONI), across 3 reports (2023-2025)" — rather than a
binary thin/not-thin verdict. A factual statement resolves a case a
boolean can't distinguish: one genuinely strong single source and three
same-organization reports spanning years both count as "single-org" by
a naive check, but they are not the same situation for a researcher
evaluating the answer, and stating the fact lets them judge it rather
than trusting an automated verdict. A stronger, explicit caveat is
added specifically when the cited-*document* count (not just
organization count) is 1.

### Contradictory evidence: prompted behavior, verified by evaluation — deliberately not mechanically detected

No feasible mechanical check for "do these two excerpts disagree"
exists short of real NLI (natural language inference) machinery, which
is out of proportion to build against this phase's timeline. Handled
via explicit prompt instruction: when cited excerpts disagree, state
both positions with their own separate citations, and never average or
silently resolve to one. `project_evaluation_plan.md`'s own dedicated
contradictory-evidence ground-truth slice is the actual verification
mechanism for whether this holds in practice on real generated answers
— this ADR does not claim the prompt instruction alone guarantees
correct behavior, only that it's the proportionate mechanism given no
cheap mechanical alternative exists.

Thin and contradictory evidence are treated as genuinely different
problems (a counting problem vs. a semantic-disagreement problem) with
different mechanisms, deliberately not folded into one "confidence"
signal — consistent with this project's standing preference for a
mechanical check wherever one is feasible (thin evidence) and an
LLM-plus-evaluation approach only where it isn't (contradiction).

## Consequences

- New module: `src/generation/citations.py` — the only place marker
  parsing, document-metadata lookup, and sourcing-footer logic live.
- Generation's return shape is a structured dict (`answer_markdown`,
  `citations`, `sourcing`, `usage`), not bare prose — a forward
  requirement on the interface, monitoring, and LLM-evaluation phases,
  none of which are built yet, the same way ADR-0001 noted a forward
  requirement on generation itself before generation existed.
- A real citation whose source doesn't support the claim (as opposed to
  a fabricated one) is NOT caught by this design — only surfaced later,
  by human-reviewed evaluation. This is a known, accepted gap, not an
  oversight — see the Fable consult's own reasoning above.
- Architecture document version increments v1.8 → v1.9.
- No NLI-based contradiction detection exists or is planned near-term;
  contradiction handling is prompt-only until the evaluation phase
  produces evidence one way or the other about whether that's
  sufficient.

## Fable consult

Consulted 2026-07-24 (full generation-phase design consult; this ADR
covers the two decisions from that consult judged to cross the
"real design decision" bar, per the project's own stated ADR-worthiness
threshold — see `decisionlog.md`, 2026-07-24, for the complete
transcript including context-size and file-structure decisions that
didn't need an ADR). Found, before design began, that chunks don't
carry `title`/`url` (those live in `data/metadata/{doc_id}.json`, not
the chunk record) by reading `metadata.py` directly rather than trusting
the brief — informs the citation-lookup mechanism above directly.
Directly challenged the source-diversity-on-retrieved-set pre-check
idea that motivated this consult in the first place; the adopted
cited-subset mechanism is Fable's proposed alternative, not the
starting framing.

## What would trigger a revisit

- If human-reviewed citation-precision evaluation finds a real,
  non-trivial rate of citations that are structurally valid but don't
  actually support the claim made — build the second LLM verification
  pass explicitly deferred above.
- If the sourcing-footer thresholds (single-org, single-doc) fire too
  often or too rarely against real generated answers once evaluated —
  tune the threshold values, not the underlying mechanism.
- If NLI-quality contradiction detection becomes cheap enough to add
  without a real time cost before the submission deadline — revisit the
  prompt-only approach to contradictory evidence.
