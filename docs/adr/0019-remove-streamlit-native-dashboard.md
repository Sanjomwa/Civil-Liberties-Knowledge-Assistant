# ADR-0019: Remove the Streamlit-Native Monitoring Dashboard

**Status:** Accepted, 2026-07-27. Amends `docs/interface-design.md`
Decisions 2 and 5.

## Context

`docs/interface-design.md` Decision 2 deliberately built two monitoring
surfaces reading the same `interactions` table: a Streamlit-native
6-chart dashboard (`src/interface/pages/dashboard.py`), built and
verified *first*, and Grafana, built *second* as "the highest-risk,
lowest-marginal-point piece" — an explicit hedge. The stated reasoning:
"Building the ~1-hour Streamlit dashboard first banks the monitoring
points immediately; Grafana is then attempted as a pure add-on with a
hard cutoff, not a cliff the whole monitoring score depends on." At the
time that decision was written (2026-07-26), Grafana provisioning was
unproven — a real risk, not a hypothetical one, given the actual
version-drift and port-mismatch bugs Grafana went on to hit during
implementation and cloud deployment.

That risk has since resolved in Grafana's favor. As of 2026-07-27,
Grafana is fully built, deployed to Cloud Run, and verified end to end
against real production data — a real question asked through the live
app, a real row in Neon, correctly rendered in Grafana's own
"Feedback over time" panel via a direct `/api/ds/query` check, not
just eyeballed in the UI (`reports.md`, `decisionlog.md`, 2026-07-27).
The condition that justified building and keeping both dashboards — an
unproven Grafana as a project-ending risk — no longer holds.

Sam's direct observation, prompting this ADR: running two dashboards
against the same data is redundant on its face, and the Streamlit one
should go now that Grafana is confirmed working, not kept indefinitely
as a hedge against a risk that already resolved.

## Decision

**Remove `src/interface/pages/dashboard.py` entirely.** Streamlit's
`pages/` auto-discovery means deleting the file removes the second
navigation tab automatically — no change needed in `app.py` itself,
which never referenced it directly. Grafana becomes the sole
monitoring dashboard, both locally (`docker-compose`) and in the cloud
deployment.

**Not removed:** the `interactions` table schema, `db.py`'s
`insert_interaction()`/`record_feedback()`, or any of the six metrics
themselves — those are the actual monitoring substance and are
unaffected. Only the redundant second *rendering* of them goes.

**Documentation updated to match, not left describing a file that no
longer exists:** `README.md`'s Monitoring section (currently describes
both dashboards, `src/interface/pages/dashboard.py` by name) and
`docs/presentation-reference.md`'s Tier 2 section (same). `docs/
interface-design.md` itself is **not rewritten** — it's a frozen
pre-implementation design record, and Decision 2's reasoning was sound
*at the time it was made*, under real uncertainty about Grafana. It
gets a superseded-pointer note to this ADR instead, per this project's
own standing convention of not silently rewriting history when a
documented decision changes.

## Correction, found during implementation, 2026-07-28

This ADR's premise was checked against the real repo before the doc
updates below were written, and was wrong on one concrete detail:
`grafana/dashboards/interactions.json` only defines **5** panels
(feedback over time, latency, retrieval score distribution, source-org
mix, tokens/cost) — not 6. The citation data-quality panel (invalid
citation markers / unsupported-paragraph rate over time, `docs/
interface-design.md` Decision 5's "free sixth chart") was only ever
built in the now-deleted Streamlit page; Grafana never got it. Both
`README.md` and `docs/presentation-reference.md` already said "5 of 6
panels" correctly, pre-dating this ADR — so this was a real gap this
ADR's own drafting missed, not new drift introduced by removing
Streamlit.

Caught by Claude Code stopping mid-task rather than rounding "5" up to
"6" in the docs to match this ADR's stated premise — exactly the
right call per this project's own "don't silently paper over a
prompt's wrong premise" convention.

**Resolution: close the gap, don't shrink the claim.** Add the missing
6th panel to `grafana/dashboards/interactions.json` (same data the
deleted Streamlit chart used — `invalid_marker_count`/
`unsupported_paragraph_count` from `interactions`, plotted over `ts`),
so Grafana actually reaches the 6-metric parity this ADR assumed,
rather than documenting a permanent reduction from 6 monitoring
signals to 5 as a side effect of a redundancy cleanup. This was a real,
valued differentiator chart ("a sixth chart no other cohort project is
likely to have," per `docs/interface-design.md` Decision 4) — worth
preserving on purpose, not losing by accident.

## Consequences

- One fewer file to keep in sync with schema changes going forward —
  any future column added to `interactions` only needs a Grafana panel
  update, not two.
- Local `docker-compose up` and the cloud deployment both lose the
  Streamlit "Monitoring Dashboard" nav tab; anyone visiting the app now
  sees only the single-page Q&A interface, matching Decision 3's
  original single-page-app framing more cleanly than the two-page
  version did.
- No rubric risk: the monitoring requirement is satisfied by Grafana
  alone now, with real live data confirmed rendering — a stronger
  demonstration than the Streamlit fallback would have been on its own.
- If Grafana ever becomes unreliable again (e.g., a future
  `grafana/grafana:latest` version-drift bug reintroduces the
  `jsonData.database` class of breakage — a real, currently-open risk
  given the image tag is still unpinned), this hedge is gone. That
  tradeoff is accepted deliberately, not overlooked — see "what would
  trigger a revisit."

## Advisor consult

Not sought. This is a low-complexity removal once its triggering
condition (Grafana risk) resolved favorably and was independently,
concretely verified — same class as ADR-0004's correction-not-design-
decision distinction, not a case requiring Opus/Fable judgment under
real uncertainty.

## What would trigger a revisit

- If `grafana/grafana:latest`'s unpinned tag causes another real
  breaking version-drift bug (this project has already hit one) and
  pinning a specific version doesn't fully close that risk out — worth
  reconsidering whether a lightweight native fallback is cheap insurance
  again, the same reasoning Decision 2 originally used.
- If Grafana's Cloud Run service becomes unreliable in a way Streamlit
  wouldn't be (e.g., cold-start latency on a second service on top of
  the app's own) — revisit whether monitoring should live inside the
  main app process instead of a separate service.
