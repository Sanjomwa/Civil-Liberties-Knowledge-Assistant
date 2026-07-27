# Interface / Monitoring / Containerization — Pre-Implementation Design

Written 2026-07-26, before `src/interface/` exists — mirrors
`retrieval-design.md`/`generation-design.md`/`evaluation-design.md`'s
shape: a synthesized design reference, not a live status page. Covers
ADR-0012 Tier 2 (rubric-driven completion plan): interface, monitoring,
containerization. Design decided via an Opus 5 consult (grounded directly
in the real repo) followed by a Fable consult explicitly briefed to build
on, not repeat, Opus's findings. Full transcripts: `decisionlog.md`,
2026-07-25/26.

## Scope boundary

Ends at: a working Streamlit app answering real questions via the
existing, unchanged `answer()`; feedback captured to Postgres; a 5+-chart
dashboard (Streamlit-native, Grafana additive); `docker-compose up`
running all of it from a clean clone. Does not touch `generate.py`,
`search.py`, or the judge/evaluation code's actual behavior — this phase
consumes those functions, it doesn't change what they compute — except
three small, additive, non-breaking fields described below (Decision 4a),
found necessary only once real implementation hit a real gap: no
retrieval score was exposed anywhere in the pipeline.

**4a. Real gap found during implementation, 2026-07-26 — no retrieval
score is exposed anywhere, fixed with three additive touches, not a
redesign.** `search.py`'s `_rrf_combine()` computes a real RRF score
internally (`scores[chunk_id]`) but only uses it to sort results, then
discards it before returning the chunk dict — confirmed directly against
the real file, not assumed. `generate.py`'s `answer()` never returns the
raw retrieved-chunk list at all; `citations.py`'s `citations` entries are
`{marker, chunk_id, doc_id, pages}` — no score, no org field either
(org is derivable via `citations.py`'s own metadata lookup, already used
internally by `render_sources()`/`sourcing_footer()`). This blocks both
`retrieval_scores` (Decision 4's schema) and `citations_summary`'s score
field — a real gap in this design doc, not something to route around
silently.

Resolution, three touches, same additive-field class as the `timings`
addition:
1. `search.py`'s `_rrf_combine()`: attach the already-computed score to
   each returned chunk before returning it — `{**chunk_by_id[cid],
   "score": scores[cid]}`. Scoped to the hybrid path only (the recorded
   default and the only method this interface ever calls, since there's
   deliberately no method selector) — text/vector's return shape stays
   untouched; minsearch's `Index`/`VectorSearch` don't expose a score
   internally, and reimplementing that math would mean touching closed
   retrieval-phase internals for a path this interface never exercises.
2. `generate.py`'s `answer()`: a second additive field alongside
   `timings` — `"retrieved_chunks": [{"chunk_id": c["chunk_id"], "score":
   c.get("score")} for c in chunks]`. Chunk_id + score only, deliberately
   no text, same discipline `citations` already follows.
3. The interface layer (not `citations.py`) builds `citations_summary`'s
   score by joining each `parsed["citations"]` entry's `chunk_id` against
   the new `retrieved_chunks` field, and its org via `citations.py`'s
   existing metadata-lookup pattern. `citations.py`'s own contract is
   unchanged — this is composition at the interface layer, not a change
   to a closed module.

## Decisions

**1. Storage: Postgres, not SQLite.** Same build effort as SQLite, but
earns a real 3-service `docker-compose` (app + postgres + grafana)
instead of one, and matches what `README.md`'s Monitoring section already
commits to.

**2. Dashboard: Streamlit-native page built first, Grafana additive
second — not the reverse.** **Superseded 2026-07-27, ADR-0019**: once
Grafana was confirmed working end to end against real production data,
the Streamlit-native dashboard this decision hedged with was removed —
the risk it hedged against had resolved. This decision's reasoning was
correct under the real uncertainty at the time it was written; kept
here as the historical record, not rewritten. Postgres is the load-bearing piece (pays
twice: README promise + compose service count); Grafana is the
highest-risk, lowest-marginal-point piece. Building the ~1-hour
Streamlit dashboard first banks the monitoring points immediately;
Grafana is then attempted as a pure add-on with a hard cutoff, not a
cliff the whole monitoring score depends on.

**3. Interface: a single-page Streamlit app.** Contents: a scope/
limitations line (4 orgs, 5 countries, 2022–2026); 3–4 example-question
buttons pulled from real ground truth; a text input; the rendered
`answer_markdown`; the sourcing footer (`st.warning` if thin, `st.info`
if broad); the Sources list; an `st.expander` showing retrieved excerpts
+ scores; thumbs up/down; a caption with latency/tokens/model. Explicitly
excluded: chat history, multi-turn conversation, and a user-facing
retrieval-method selector (a knob that could make the recorded hybrid
default look worse live, with no rubric benefit).

Two implementation non-negotiables: `@st.cache_resource` around
index/embedding-model load (a plain `lru_cache` inside `search.py` won't
survive Streamlit's script-rerun model), and holding the last result in
`st.session_state` so a thumbs click doesn't re-call `answer()` — every
click would otherwise be a duplicate logged row and a duplicate real
OpenAI charge.

**4. One `interactions` table, a reduced projection — never the raw
`citations` payload verbatim.** `citations` (and `answer_markdown`, to a
lesser extent) can carry real corpus excerpt text, the same
licensing-sensitive class of data already excluded from the public repo
(`.gitignore`'s `*_full.csv`/`judgments.jsonl` pattern). Schema:

```sql
CREATE TABLE IF NOT EXISTS interactions (
    id                        BIGSERIAL PRIMARY KEY,
    ts                        TIMESTAMPTZ NOT NULL DEFAULT now(),
    query                     TEXT NOT NULL,
    answer_markdown           TEXT NOT NULL,
    latency_ms                INTEGER,
    retrieval_ms              INTEGER,
    llm_ms                    INTEGER,
    prompt_tokens             INTEGER,
    completion_tokens         INTEGER,
    total_tokens              INTEGER,
    model                     TEXT,
    est_cost_usd              NUMERIC(10, 6),
    retrieval_method          TEXT,
    top_k                     INTEGER,
    n_chunks                  INTEGER,
    retrieval_scores          JSONB,   -- full array, not just mean/max: feeds the distribution chart
    citations_summary         JSONB,   -- [{marker, doc_id, org, score}], no excerpt text
    source_orgs               TEXT[],
    citation_count            INTEGER,
    sourcing_status           TEXT,
    distinct_org_count        INTEGER,
    distinct_doc_count        INTEGER,
    invalid_marker_count      INTEGER,
    unsupported_paragraph_count INTEGER,
    feedback                  SMALLINT,  -- NULL until voted; +1/-1
    feedback_at               TIMESTAMPTZ
);
```

Feedback is an `UPDATE ... WHERE id = %s`, not a second table — exactly
one verdict per answer.

Two small, additive changes worth making now rather than backfilling
later: (a) `answer()` gains a `timings` key in its return (retrieval_ms,
llm_ms — non-breaking, ~4 lines in `generate.py`) so the latency chart
splits retrieval from generation instead of one flat bar; (b)
`est_cost_usd` is computed from an explicit per-model rate table that
**raises on an unknown model** rather than silently writing `0` — this
project's own `03_common_pitfalls.md` #2 (silent zero-cost for
unrecognized models) is exactly the failure mode to not repeat here.
`invalid_marker_count`/`unsupported_paragraph_count` are already computed
by `citations.py` for free — a sixth chart no other cohort project is
likely to have.

**5. The five committed charts, plus a sixth.** **Superseded 2026-07-27,
ADR-0019**: these six charts now live in Grafana only, not duplicated
in a Streamlit-native page — see Decision 2's superseded-note above. feedback over time
(daily up/down counts); latency (split by `retrieval_ms` vs `llm_ms`,
stacked); retrieval score distribution (histogram over the flattened
`retrieval_scores` array); source-org mix (count by `source_orgs`);
token/cost (`total_tokens` and `est_cost_usd` over time); and citation
data-quality (`invalid_marker_count`/`unsupported_paragraph_count` rate
over time) as the sixth, free chart.

**6. Docker-compose: three services — `app`, `postgres`, `grafana`.**
Schema created idempotently (`CREATE TABLE IF NOT EXISTS`, never
`DROP`/`--force`) at app startup, not via a separate migration step.
`.env` for `OPENAI_API_KEY`, never baked into the image. `.dockerignore`
added.

**7. Grafana provisioning traps (Fable, real-world-scale-specific,
apply as explicit build steps, not left implicit):** pin the datasource
UID identically in the provisioning YAML and every panel JSON (a UID
mismatch renders "datasource not found" in a fresh container);
`depends_on: condition: service_healthy` with a real `pg_isready`
healthcheck on postgres, and the `app` container needs the same
dependency or `db.py` can race Postgres at startup; widen each panel's
default time range to 24h+ and seed a handful of demo rows, or README
screenshots show blank charts; set `GF_AUTH_ANONYMOUS_ENABLED=true`
(Viewer role) so a reviewer isn't hunting for admin credentials.

**8. The real blocker, resolved via rehydrate-on-first-run, not a
54%-only build.** `data/` (including the vector index) is gitignored,
and `search()` hard-fails on a corpus-version mismatch — a reviewer's
clean-cloned container has no index at all, so the first query would die
immediately. The build must produce a real index; the open question was
where the Freedom House/Access Now (46% of the corpus) text comes from,
given `docs/licensing.md`'s gate on public-facing redistribution of their
content.

**Revised 2026-07-26, Opus-consulted directly on this question after Sam
asked to include the full corpus, not just OONI/CIPESA.** Verdict: baking
full Freedom House/Access Now text into a *publicly buildable* Docker
artifact is the exact redistribution act ADR-0013 was written to avoid —
"non-commercial educational use" doesn't change that gate (Freedom
House's policy already permits non-commercial *sharing* and still gates
*reproduction* specifically — that's precisely the case it contemplates),
and an unanswered permission request (sent 2026-07-13, followed up
2026-07-25) is not implicit consent, a point ADR-0013 already made
explicitly. The actual fix, already sitting in this codebase:
**`rehydrate.py`** re-fetches and re-chunks Freedom House/Access Now
content directly from those orgs' own servers, hash-verified — already
smoke-tested live, byte-identical results. That's the acquisition act
their policy already permits, done by whoever runs the container, not a
redistribution act done by this project.

**Adopted mechanism:**
1. The Docker build always bakes the **tiered public release**
   (`dist/corpus-release-v1.zip`, ADR-0013) — OONI+CIPESA full text,
   Freedom House/Access Now metadata+hash only — so `docker compose up`
   **always works**, unconditionally, even with no network access to the
   restricted orgs at build or run time.
2. On first container start, an app-level rehydration step calls
   `rehydrate.py --org freedomhouse` and `--org accessnow`, fetching their
   real text from their own servers onto whoever is running the
   container's own machine, verified against the shipped hash, then
   re-embeds those chunks into the running index. Graceful degradation on
   network/upstream failure — log it plainly, keep serving the 54%
   baseline, don't crash the app.
3. **Every reviewer who runs this ends up with 100% of the corpus** —
   Sam is never the one distributing Freedom House/Access Now's full text
   at scale; each runner acquires it themselves, the same way the
   original ingestion phase did.
4. README states both paths plainly (baseline vs. rehydrated) and why —
   this is a disclosure that earns rubric credit, not a gap to hide.

**Not adopted:** shipping full FH/Access Now text in the public release
artifact or baking it into the image directly. **If rehydration proves
flaky before the 2026-08-02 freeze**, fall back to a hosted, full-corpus
live demo with no public download route (serving cited excerpts in
answers is this system's actual purpose, and `licensing.md` already
treats that as low-risk) — never the public full-text artifact as a
shortcut.

**Separately, ongoing outreach relevant to this decision**: Sam has been
tagging Freedom House and Access Now directly on LinkedIn in the
learning-in-public post series and intends to keep doing so, including
when the series reaches this exact rehydrate-on-first-run milestone —
a real, visible good-faith effort alongside the two unanswered emails,
not a substitute for actual permission, but worth keeping logged
alongside the licensing record since it's part of the same story.

**9. Cost/rate exposure.** A public Streamlit page (if Tier 3 cloud
deployment happens) is an open wallet against a real API key. Add a
per-session query cap and a hard `max_chars` on the input box now, not
as a Tier 3 retrofit — cheap insurance.

**10. Feedback vs. the frozen 0.946 judge number — no real statistical
tension, but pre-empt the framing.** Offline claim-level precision and
live thumbs-up/down are different signals measuring different things,
and live feedback volume will be single digits at best. One sentence in
the README says so, so a reviewer doesn't read a handful of live
thumbs-down as contradicting the offline number.

## Build order

1. Local Postgres (docker run or local install) + `db.py` + schema +
   Streamlit app, writing real rows against real `answer()` calls.
2. Streamlit-native dashboard page (the guaranteed monitoring
   deliverable) reading the same table.
3. Dockerize `app` + `postgres`; resolve the corpus-fetch step (Decision
   8); run a clean-clone rehearsal (fresh directory, `git clone`,
   `docker compose up`, ask a real question) before moving on.
4. Grafana: additive, provisioned per Decision 7's checklist, hard
   cutoff — if it's not clean quickly, the Streamlit dashboard from step
   2 already satisfies the rubric's monitoring requirement.
5. README updated: Monitoring, Quickstart (`docker compose up`),
   Deployment (still not deployed, Tier 3), Limitations (the tiered
   corpus-content gap from Decision 8, the feedback-vs-judge framing from
   Decision 10).

## Non-goals (explicitly out of scope this phase)

Chat history / multi-turn conversation; a retrieval-method selector in
the UI; cloud deployment (Tier 3); query rewriting (Tier 3); any change
to `generate.py`'s prompt, `search.py`'s ranking, or `judge.py`'s
protocol — this phase is additive instrumentation around already-closed
phases, not a revision to them.

## What would trigger a revisit

- If Sam wants the public Docker build to answer from the full corpus
  (not just OONI/CIPESA), that's a licensing decision needing its own
  look at `docs/licensing.md`/ADR-0013, not a default to change silently
  here.
- If Grafana provisioning isn't clean by the stated cutoff, ship with
  the Streamlit-native dashboard only — don't let Grafana debugging
  consume time from the 2026-08-02 feature-freeze gate.
