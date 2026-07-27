# README Plan — Civil Liberties Knowledge Assistant

**Status: Stage 1 (Tier 1 sections) written, 2026-07-25.** `README.md` now
has real content for title/description, problem, architecture, project
structure, decisions/trade-offs, data/config (including the OONI
disclosure), the retrieval half of evaluation, and the full limitations
list. Explicitly left as honest placeholders, not written yet: the Demo
section (needs one real verified example pulled from
`data/eval/generation_results.jsonl`, which doesn't sync to Cowork — a
WSL-side follow-up), the LLM-evaluation half (blocked on the Prompt A/B
comparison, ADR-0012 Decision 2), Monitoring, the final Quickstart run
command, Self-evaluation, and Future work (the last two deliberately
deferred to submission time per this plan's own build order).
**Deployment written and verified live 2026-07-28** (ADR-0016/0018,
`deploy/gcp-deploy.sh`) — removed from this placeholder list. Testing and CI/CD were checked directly (no `tests/`, no
`.github/workflows/` found) and both sections state their absence
plainly, per the article's own rule. Original plan, adopted 2026-07-24
per
ADR-0012, section-by-section, from Alexey Grigorev's "How to Write a Good
README" (<https://alexeyondata.substack.com/p/how-to-write-a-good-readme>,
read 2026-07-24, exact URL confirmed by Sam 2026-07-28). Maps that article's
structure onto what actually exists in this project right now, so the
rewrite (Tier 1, ADR-0012) starts from real content, not a blank template.
Every section below states: what to write, the real source material for it
in this repo, and whether it's blocked on something not built yet.

The article's own framing, worth keeping in mind while writing: three
audiences at once — a peer reviewer scoring against `project.md`'s rubric,
a hiring-team reader who gives a repo under 2 minutes before deciding
whether to look closer, and future-Sam returning to this project after
months away. Optimizing for the peer reviewer (clear evidence, one place
per criterion) turns out to serve the other two as well.

---

## Part 1: What is this project?

### 1. Title and description

**Write:** one or two sentences — user, problem, solution — not a
technology list. Formula from the article: "[Project name] is a [type of
system] that helps [specific user] do [task]."

**Real material:** the current one-liner ("RAG assistant answering
questions about internet censorship and digital rights in East Africa
(2022–2025)...") names the domain but not the user or the actual problem.
Real user, from the architecture doc and `docs/corpus-inclusion-rubric.md`:
researchers, journalists, and civic-tech practitioners investigating
digital rights in East Africa, who currently have to manually cross-check
fragmented reports across OONI, Access Now, CIPESA, and Freedom House.
**Also fix the stale date range** — the description still says 2022–2025;
ADR-0006 extended the corpus window to 2022–2026 and this was never
propagated into the one-liner.

### 2. Problem

**Write:** what the user is trying to do, what makes it hard, why existing
options fall short, who's affected — a few concrete paragraphs, not a
market analysis.

**Real material:** LinkedIn post 1's hook already did this work — "the
evidentiary gap" framing, why answers need to cite-or-flag-thin-evidence
rather than smooth over contradictory or single-sourced claims. Pull from
that post and from the architecture doc's own problem framing, condensed.

### 3. Demo

**Write:** show it working before asking the reader to install anything —
live link, video, GIF, screenshots, or sample input/output.

**Blocked:** no UI exists yet (Interface is 0/2, Tier 2 per ADR-0012) and
no cloud deployment exists yet (Tier 3). **Interim option, usable now:**
real sample input/output already exists from the LLM-evaluation run —
`reports.md` and the evaluation artifacts contain real questions with real
generated answers, citations, and sourcing footers. Use 2-3 of these
verbatim as a text-based demo until the Streamlit interface ships, then
replace with a screenshot/video per the article's stated preference for
richer formats once available.

---

## Part 2: Does it work well?

### 4. Evaluation

**Write:** the evaluation dataset and what it covers, what changed between
a baseline and the final approach, headline numbers, links to the
underlying scripts/data.

**Real material — this is the project's strongest section, already has
real numbers to report:**
- Retrieval: text vs. vector vs. hybrid evaluated on a 130-question ground
  truth set (`src/retrieval/ground_truth.py`, `evaluate.py`). Recorded
  default: hybrid, RRF k=10. Aggregate Hit Rate ~0.644–0.66, neighbor-aware
  Relaxed Hit Rate ~0.812. Per-slice breakdown and the `multi_country` MRR
  finding (a real, root-caused, not-retrieval-fixable limitation) both
  belong here — the article's own guidance is to show the progression, not
  just the final number.
- LLM evaluation: **write this section only after ADR-0012 Decision 2 is
  built** — Prompt A vs. Prompt B compared with the existing claim-level
  judge, both numbers reported, winner stated. Until then, this section
  would only have one approach's number (0.879 for Prompt A), which is
  exactly the 1/2-not-2/2 gap ADR-0012 exists to close — don't publish this
  section prematurely with only one approach in it.
- Link to `docs/evaluation-design.md`, `docs/retrieval-design.md`, and the
  real result files, not just narrate the numbers in prose.

### 5. Testing

**Write:** what automated tests exist and the one command to run them, or
state plainly that none exist yet.

**Needs a real check before writing:** `pyproject.toml` lists `pytest` as a
dev dependency, but whether any `tests/` files actually exist wasn't
confirmed in this session's audit. Check first. If none exist, follow the
article's own example directly — Fitness Assistant states "no automated
tests" as a named limitation rather than implying more coverage than
exists. Do the same here rather than write a vague "testing is planned"
sentence.

### 6. Monitoring

**Blocked** — Monitoring is 0/2, Tier 2 per ADR-0012. Write this section
once the feedback-collection + 5-chart dashboard ships: what's captured,
where it's stored (reuse Module 5's Postgres+Grafana pattern per the
Opus 5 consult), a dashboard screenshot, what each panel shows.

---

## Part 3: Can I run and reproduce it?

### 7. Quickstart

**Blocked on Interface** for the final "start the application" command,
but the earlier steps can be written now: `uv sync`, `.env` setup
(`OPENAI_API_KEY`), which Python version (`pyproject.toml`:
`>=3.10,<3.13`). Add the actual run command once Tier 2's Streamlit
interface exists.

### 8. Data and configuration

**Write:** every external input the reader needs, named explicitly, plus
required vs. optional environment variables.

**Real material and a real risk to disclose, not omit:** the corpus lives
in `corpus/sources/*.yaml` (per-org manifests) and `data/` (gitignored —
see `docs/data_governance.md` for why). **Concrete ADR-0012 Tier 1 action:
ship the processed corpus/chunks** (e.g., as a release artifact) so a
reviewer never has to run ingestion from scratch. **State plainly**: OONI's
source consistently 429s on scripted requests and requires manual
browser-save acquisition — a reviewer attempting a from-scratch
`pipeline.py` run against OONI specifically should expect this, per the
article's own principle that an honest documented limitation scores, while
a silently failing pipeline does not. `.env.example` should list
`OPENAI_API_KEY` as required; note there is currently no optional-service
distinction to make since there's no monitoring/cloud config yet.

### 9. Deployment

**Blocked** — Tier 3 per ADR-0012, attempted 2026-08-03–05 only if Tier 1–2
land on schedule. Until then, state plainly (per the article's own
Fitness Assistant example, which does the same for its own no-deployment
state): no public deployment yet; run via Docker Compose or locally.
Rewrite this section once cloud deployment ships — this is also the
section a hiring-team reader is most likely to act on, so it's worth
getting right once it exists, not just checking the box.

---

## Part 4: How was it built?

### 10. Architecture

**Write:** a diagram (Mermaid is fine) plus a short explanation of why
each component exists, not just what connects to what.

**Real material, already written, just needs condensing into README
form:** the pipeline is ingestion (`acquire → extract → validate →
metadata → chunk → pipeline`, `src/ingestion/`) → retrieval (`embed`,
in-memory numpy vectors + `minsearch` hybrid text/vector, `src/retrieval/`)
→ generation (`search → prompt → LLM call → citations.parse_citations()`,
index-only `[n]`-marker protocol per ADR-0009, `src/generation/`) →
evaluation (`run_answers → judge → evaluate_generation`, claim-level
citation-precision judge per ADR-0010/0011, `src/evaluation/`). Full detail
already exists in `docs/ingestion-design.md`, `retrieval-design.md`,
`generation-design.md`, `evaluation-design.md` — this section is a
condensed pointer to those, not a rewrite of them.

### 11. Project structure

**Write:** a simplified file tree with one-line descriptions per real
path, not the full `find` output.

**Real material:** `src/ingestion/*.py` (six modules + `reconcile.py`),
`src/retrieval/*.py` (four core modules + two diagnostic scripts),
`src/generation/*.py` (three modules), `src/evaluation/*.py` (four
modules), `corpus/sources/*.yaml`, `docs/adr/` (twelve ADRs), `docs/*.md`
(design docs per phase). Note there are no notebooks in this project at
all — every phase is standalone scripts, so the article's
"`notebook1.ipynb` vs. descriptive names" warning doesn't apply here, but
is worth a one-line note explaining why (namespace-package convention,
documented in `generate.py`'s own comments).

### 12. Decisions and trade-offs

**Write, using the article's own format:** "I chose X over Y because of
constraint Z. The downside was A. I accepted it because B." Pick the 3-4
decisions that actually shaped the project, not every ADR.

**Strongest real candidates, already fully reasoned in existing ADRs —
condense, don't rewrite from scratch:**
- In-memory numpy vectors instead of a vector database (matches the
  course's own explicit allowance; doesn't scale past a laptop-sized
  corpus without rework; the right call at 3,783 chunks).
- Hybrid RRF k=10 over pure text or pure vector search, despite text
  search winning outright on the `multi_country` slice — a real, disclosed
  trade-off, not a clean win (`docs/retrieval-design.md`,
  `PROJECT_CONTINUITY.md` Section 1).
- Index-only citation protocol (ADR-0009) — the LLM never writes a
  citation itself, only picks `[n]` markers from numbered excerpts, making
  fabricated citations structurally impossible at some cost in prompt
  rigidity.
- Claim-level (not per-marker) judge protocol (ADR-0011) — chosen after a
  second review found per-marker judging would mis-score well-corroborated
  multi-source claims as partial.

### 13. CI/CD

**Needs a real check first:** no `.github/workflows/` or equivalent was
found in this session's repo listing. If none exists, per the article's
own explicit rule, do not write a section implying otherwise — mention its
absence under Limitations instead.

---

## Nice to have

### 14. Limitations

**Write specific, not vague — name the boundary and its consequence.**

**Real limitations, already documented across ADRs/decisionlog, need
consolidating into the README rather than left scattered:**
- English-only corpus, a disclosed non-neutral scope limitation (ADR-0001).
- Freedom House is 46% of the corpus — a real concentration, compounded by
  being the one org with unresolved redistribution licensing
  (`docs/licensing.md`).
- OONI requires manual acquisition (429s on scripted requests) — see
  Data/config section above.
- `ooni_methodology` ground-truth stratum sampled 0/20 in the retrieval
  evaluation — the corpus has no dedicated OONI methodology document, a
  known, accepted gap (`PROJECT_CONTINUITY.md`).
- `multi_country` MRR gap — plain text search beats every hybrid config on
  this slice, root-caused as a real, not-retrieval-fixable category-
  sampling property, not an embedding defect.
- Judge self-judging risk — if `gpt-5.4` isn't available and the
  `gpt-5.4-mini` fallback fires (same model as the generator), this is a
  disclosed limitation per ADR-0011, not a silent one.
- No automated tests / no CI/CD, if confirmed absent (see sections 5, 13).
- No public deployment yet, until Tier 3 lands.

### 15. Future work

**Write, prioritized, tied to a real limitation or evaluation finding —
not a wishlist.** Candidates: query rewriting and further re-ranking work
(best practices, optional per ADR-0012 Tier 3); expanding the corpus with
Netblocks and Citizen Lab (deferred to v1.1 in the frozen architecture);
reuse inside the larger CLIO platform (the project's stated long-term
framing, kept separate and complementary per the 2026-07-20 decisionlog
entry).

### 16. Self-evaluation against the rubric

**Write this last, after the Tier 1/2 build items above actually ship —
not before, and not aspirationally.** Go through every line of
`project.md`'s Evaluation Criteria, state the score claimed, and point to
the exact evidence (a file, a number, a section of this same README). The
2026-07-24 rubric audit (ADR-0012, `decisionlog.md`) is the starting draft
— re-verify every claim against the actual state of the repo at
submission time, don't just copy the audit's numbers forward, since the
whole point of this ADR was catching a design that felt done but wasn't.
Per the article: a self-evaluation doesn't replace the reviewer's own
judgment, it just makes verification fast instead of requiring a search
through the repo.

---

## Build order for this document itself

Matches ADR-0012's tiers — don't try to write the whole README in one
pass before Tier 2 code exists:

1. **Now (Tier 1):** Title/description, Problem, interim text-based Demo,
   Retrieval half of Evaluation, Data/config (including the OONI
   disclosure and shipping the processed corpus), Architecture, Project
   structure, Decisions/trade-offs, the real-limitations list so far.
2. **After Tier 2 build items ship:** LLM-evaluation half of Evaluation
   (only once Prompt A/B exists), Testing/CI-CD sections (once checked),
   Monitoring, the real Quickstart run command.
3. **After Tier 3 (if it lands):** Deployment section, replace the interim
   text demo with a live link/screenshot/video.
4. **Last, at submission time:** Self-evaluation against the rubric,
   Future work, final Limitations pass.
