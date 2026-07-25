# ADR-0012: Rubric-Driven Completion Plan — LLM-Evaluation Second Approach, Timeline Gate, README Standard

**Status:** Accepted, 2026-07-24.

## Context

Four phases (ingestion, retrieval, generation, LLM evaluation) were built and
individually closed against their own design docs, but never against the one
document that actually determines the grade: `project.md`'s Evaluation
Criteria section, the fixed public rubric three peer reviewers will literally
score this project against. That gap was closed today by reading the rubric's
exact point definitions and checking them directly against the real code
(not against what the design docs claimed).

Real findings, code-verified: Retrieval flow, Retrieval evaluation, and
Ingestion pipeline are genuinely at 2/2. Best practices' hybrid-search point
is earned. But three things are real gaps, not just "not started yet":

1. **LLM evaluation is 1/2, not 2/2, despite feeling closed.**
   `generate.py`'s own docstring states "no model/prompt comparison (that's
   the LLM evaluation phase's job, not this one's)" — and the evaluation
   phase built under ADR-0010/ADR-0011 only ever judges **one** fixed
   generation approach. The rubric's 2-point bar is explicitly "multiple
   approaches are evaluated, and the best one is used." 0.879 claim-level
   citation precision is a real, rigorous number, but it answers "how good
   is this one approach," not the rubric's actual question. This is a
   design gap, not a finishing-touch gap — the phase needs a genuine second
   compared approach, not a relabeling of what already exists.
2. **Problem description and Reproducibility are under-scoring for
   documentation reasons, not substance reasons.** `README.md` is a single
   306-byte sentence — no elaboration, no setup instructions, no mention of
   the OONI 429/manual-acquisition constraint that could block a peer
   reviewer's own reproduction attempt.
3. **Interface and Containerization are genuinely at 0/2** — no CLI/UI
   anywhere in `src/` (`generate.py` is explicitly library-only), no
   Dockerfile or docker-compose anywhere in the repo.

Separately, the real, confirmed submission deadline was re-verified directly
against the course-management site: **Project Attempt 2, 2026-08-11, 02:00
(Sam's local timezone)** — the target this project has been building toward
since Attempt 1 was judged too tight in an earlier session. ~17 days out from
this ADR's date.

An Opus 5 advisory consult (per this project's standing advisor pattern,
`CLAUDE.md` Section 1) was run to produce a ranked, points-per-hour completion
plan covering both the peer-review audience and the fact that this project
doubles as a portfolio piece for Sam's AI-Data-Engineering job search (see
workspace-root `career/research_notes.md`) — two different readers with
different attention spans, worth reconciling deliberately rather than
assuming one plan serves both. Full transcript in `decisionlog.md`,
2026-07-24.

Separately, Sam surfaced Alexey Grigorev's "How to Write a Good README"
article (Substack, `alexeyondata.substack.com`, read 2026-07-24) as the
standard to implement for this project's README rewrite — its structure maps
closely onto exactly the Problem description / Reproducibility gaps found in
this same session's rubric audit, so adopting it here rather than treating it
as a separate decision.

## Decision

### 1. `project.md`'s Evaluation Criteria section is now the explicit, authoritative implementation guide

For every remaining phase (interface, monitoring, containerization, best
practices, bonus) and for retrospective audit of what's already built, the
rubric's own point definitions are the checklist — not an informal sense of
"is this good engineering." This doesn't change engineering standards
(a phase can still be well-built and under-score if it doesn't hit what the
rubric literally asks for, as LLM evaluation shows) — it adds the rubric as a
second, mandatory lens alongside the project's own design docs.

### 2. LLM-evaluation phase amendment: add a second compared generation approach

Per the Opus 5 consult's recommendation: hold the model fixed
(`gpt-5.4-mini`, the existing recorded default) and compare two **prompts**,
not two models (a model-vs-model comparison would confound cost/latency with
answer quality and duplicate the existing judge-model self-judging
limitation already disclosed under ADR-0011).

- **Prompt A** — the current, already-shipped prompt (`prompts.py`,
  unchanged).
- **Prompt B** — an evidence-first variant: enumerate the retrieved evidence
  explicitly before writing any claim, write only claims traceable to that
  enumerated evidence, and include an explicit abstention clause for
  thin-evidence cases (extending, not replacing, ADR-0009's existing
  thin-evidence flagging).

Both are judged with the **existing** claim-level citation-precision judge
(`judge.py`, unchanged — ADR-0011's protocol is not being reopened) over a
stated subset of the question set (not necessarily the full 122 — the report
must state the exact N used and why). Report both approaches' precision,
unsupported-claim rate, and thin-evidence-flag correctness side by side, pick
a winner explicitly, and make the winner `generate.py`'s new recorded
default — same "closed phase gets a new ADR for a real change, not a silent
edit" discipline this project has followed since ADR-0007.

### 3. Timeline: 2026-08-07 internal target, 2026-08-02 feature-freeze gate

- **All rubric line items worth 2 points** (README/problem-description
  rewrite, data accessibility + OONI-constraint disclosure, the LLM-eval
  second-approach fix, Streamlit interface + feedback capture, monitoring
  dashboard, docker-compose) **done by 2026-08-02.**
- **2026-08-03 through 08-05: a clean-clone reproducibility dry run** — fresh
  checkout, follow the rewritten README literally, nothing from memory or
  local state. Reproducibility is the one criterion actively graded by
  someone trying to make it fail; this is the specific check for that.
- **2026-08-06–07: buffer only, not build** — absorbs real slippage without
  touching the confirmed 2026-08-11 02:00 deadline.
- Cloud deployment (the 2-point bonus, and per the career research the
  single highest-value portfolio signal — a live link is what a
  time-pressed recruiter actually clicks) and query rewriting are Tier 3,
  attempted 08-03–05 only if Tier 1–2 lands on schedule — first things cut,
  not things forced to hit a feature count.

### 4. README standard: Alexey Grigorev's structure, adapted to this project

Adopted as the project's README specification, detailed in a new
`docs/readme-plan.md` (mapping each of the article's sections — title/
description, problem, demo, evaluation, testing, monitoring, quickstart,
data/config, deployment, architecture, project structure, decisions/
trade-offs, CI/CD, limitations, future work, self-evaluation against the
rubric — to what evidence actually exists in this project right now, and
flagging what's still missing per section). Two principles from the article
carry particular weight given this project's own standing documentation
discipline (root `CLAUDE.md` Section 1: "never let docs describe something
that doesn't exist yet as if it does"): state limitations plainly rather than
omit them (the OONI acquisition constraint is the concrete case here), and
write a rubric self-evaluation section with evidence pointers, not just
claimed scores — the reviewer still verifies independently, but this makes
verification easy rather than requiring a search through the repo.

### 5. Learning-in-public: posts 6–14 stay in fixed order; posts 7 and 8 merge

Per the Opus 5 consult and Sam's own prior instruction (2026-07-24, logged
in `logs/linkedin_posts.md`) that the 14-post series stays sequential and
does not reorder to chase the freshest milestone: order is preserved. One
change, not a reordering — **posts 7 (generation ships) and 8 (LLM
evaluation) merge into one post**, since the citation-precision number is
weak context without the generation design it's measuring. The freed slot in
the calendar is used for the cloud-deployment post (with its live,
clickable link — the single asset a recruiter is most likely to act on, per
`career/research_notes.md`'s field-guide data). The DE-reframing writeup
(`career/README.md`'s deferred deliverable 3) is explicitly **not** added to
the post queue — it's a repo artifact with its own timeline, due before
submission, independent of posting cadence.

## Consequences

- `docs/evaluation-design.md` needs a new section documenting the Prompt
  A/B comparison methodology, added as an amendment note (not a rewrite —
  ADR-0010/ADR-0011's judge protocol is unchanged).
- `generate.py` will change once a winning prompt is picked — the first real
  code change to the generation phase since it closed under ADR-0009.
- `README.md` will be substantially rewritten per `docs/readme-plan.md`
  (separate file, this session).
- `logs/linkedin_posts.md`'s strategy table and calendar need the posts
  7+8 merge and the freed-slot reassignment reflected.
- `docs/PROJECT_CONTINUITY.md` Section 1/7 needs the full completion plan,
  the Aug 2 gate, and the confirmed Aug 11 02:00 deadline recorded.

## Opus 5 consult

Consulted 2026-07-24. Given the full verified rubric text, the code-checked
per-criterion status above, the confirmed timeline, and the dual
peer-review/portfolio audience context, it returned a ranked, points-per-hour
build order (README+data first as the cheapest points with the highest dual
payoff; the Prompt A/B design for the LLM-eval fix, chosen specifically to
avoid confounding with a model-vs-model comparison; Streamlit+feedback
before the monitoring dashboard to unlock two criteria in one build session;
docker-compose; cloud deployment last as Tier 3), the posts 7+8 merge
recommendation with reasoning, and a direct opinion on the internal deadline
(2026-08-07 sound, but the real risk is ordering, hence the Aug 2 gate and
the clean-clone dry run). Full transcript in `decisionlog.md`, 2026-07-24.

## What would trigger a revisit

- If Prompt B's evidence-first redesign turns out to require touching the
  citation-marker protocol itself (ADR-0009), not just the surrounding
  instructions — that's a bigger decision needing its own ADR, not something
  to fold silently into this one.
- If the 2026-08-02 feature-freeze gate slips by more than ~2 days — the
  signal is to cut Tier 3 scope (cloud deployment, query rewriting)
  immediately, not to compress the 08-03–05 reproducibility dry run.
- If the clean-clone dry run finds the OONI manual-acquisition constraint
  actually blocks reproduction outright (not just inconveniences it) — that
  needs a real fix (e.g., shipping the already-acquired raw documents in the
  repo or a release artifact), not just a disclosure note in the README.
