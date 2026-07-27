# ADR-0018: Neon Serverless Postgres Replaces Cloud SQL for Cloud Deployment

**Status:** Accepted, 2026-07-26. Amends ADR-0016.

## Context

ADR-0016 designed Cloud SQL (`db-f1-micro`) as the managed Postgres
backing the cloud deployment. Once real GCP pricing was checked
directly (not estimated), that instance turned out to cost ~$9-11/month
— the one non-serverless, always-on component in an otherwise
near-$0-at-this-traffic-level design (Cloud Run, Artifact Registry,
Secret Manager all sit within their free tiers).

Sam compared this against a prior GCP data-engineering project of his
that costs under $2.50/month, and made an explicit, final call: for a
project that generates no revenue, an always-on billed instance is the
wrong shape — not just costlier, but a real financial risk (if the
instance is ever left running unintentionally, there is no
usage-based ceiling on the bill). He chose to redesign the persistence
layer to be genuinely serverless, accepting more implementation work
now for a dependable, risk-free operating cost long-term. This
decision is final; this ADR is about *how*, not *whether*.

Per this project's Tier 3 process exception (`CLAUDE.md` Section 3,
2026-07-26): Fable is the design consultant for this phase, with
further calls deliberately limited to specific checkpoints — this
consult is exactly one of those named checkpoints ("genuine difficulty
hit mid-build"), not a lapse of that discipline.

**Two real access patterns this redesign has to serve, not just
"storage":**

1. `insert_interaction()` (`src/interface/db.py`) — one `INSERT` per
   real query, append-only.
2. `record_feedback(interaction_id, value)` — an **UPDATE** against an
   existing row's `feedback`/`feedback_at` columns, by primary key,
   issued sometime *after* the original insert (whenever a user clicks
   thumbs up/down).

**Five real Grafana dashboard queries** (`grafana/dashboards/
interactions.json`, verbatim Postgres SQL) that any replacement store
has to support: a `date_trunc`/`GROUP BY` feedback-over-time panel; a
plain time-series latency panel; a panel unpacking a JSONB array
(`jsonb_array_elements_text`) into one row per retrieval score; a panel
unpacking a text array (`unnest`) into one row per source org; a
tokens/cost time-series panel.

## Decision

### Neon (serverless Postgres), not BigQuery or Firestore

Fable's consult evaluated all three candidates against the two real
access patterns above, not against cost alone (all three are
effectively free at this project's traffic level, so cost doesn't
discriminate between them):

- **BigQuery** handles the append cleanly, but `record_feedback`'s
  per-row UPDATE, issued seconds-to-minutes after insert, lands
  squarely in BigQuery's streaming-buffer un-updatable window (up to
  ~90 minutes) — would force restructuring feedback into a separate
  append-only events table plus a dedup view, and rewriting panel 1 as
  a join. A real, non-trivial redesign.
- **Firestore** makes the feedback update trivial (native document
  update by key) but has no `GROUP BY`, no time-bucketing, no
  server-side aggregation across a collection, and no real Grafana
  data source — all 5 dashboard panels would need to be rebuilt as
  client-side aggregation, and Grafana would effectively have to be
  dropped as a rubric item.
- **Neon** is wire-compatible Postgres: both access patterns stay
  exactly what they are today (`INSERT ... RETURNING id`,
  `UPDATE ... WHERE id = %s`), all 5 Grafana queries port **verbatim**
  (same engine, same Postgres data-source plugin, only the connection
  string changes), and Neon's free tier genuinely scales to zero
  (autosuspends after ~5 minutes idle, wakes on connect in under a
  second — negligible next to LLM response latency), requires no
  credit card, and throttles at hard limits rather than ever billing
  an overage. This is a *stronger* no-surprise-bill guarantee than
  BigQuery, since Neon's free tier isn't attached to Sam's GCP billing
  account at all.

**Supabase was considered and explicitly rejected**: its free tier
pauses after 7 idle days and needs a *manual* resume — a grader or
recruiter hitting a dead demo link is exactly the failure this project
can't afford.

### What changes, concretely

- `src/interface/db.py`: **no logic change** to `insert_interaction()`
  or `record_feedback()` — both keep their existing SQL exactly as
  written. `init_db()` runs the same idempotent `CREATE TABLE IF NOT
  EXISTS` DDL against Neon instead of Cloud SQL. The only real code
  change: connection handling — use Neon's pooled connection string
  (its built-in `pgbouncer` endpoint) via `DATABASE_URL`, and add a
  one-retry-on-connect wrapper around `get_conn()`, since the first
  connection after an autosuspend wake can occasionally drop mid-wake.
  That retry wrapper is the entire new code this migration requires.
- `grafana/provisioning-cloud/datasources/postgres.yml` (built in the
  prior Tier 3 session for Cloud SQL's Unix-socket path): rewritten to
  Neon's `host:port` + `sslmode=require` connection format instead. The
  already-fixed `jsonData.database` provisioning setting (from the
  earlier Grafana version-drift bug) still applies unchanged.
- `deploy/gcp-deploy.sh` and `docs/deployment-runbook.md`: the Cloud
  SQL instance-creation steps are removed entirely. Neon project/
  database creation happens via Neon's own console or CLI — a real but
  lightweight manual step for Sam (comparable in effort to the GCP
  project/billing setup, not a new engineering burden), producing a
  connection string that goes into Secret Manager as `DATABASE_URL`,
  same as today.
- The GCP API-enablement list drops `sqladmin.googleapis.com` — Cloud
  SQL Admin is no longer needed anywhere in this design.
- **Local development is unaffected**: `docker-compose`'s Postgres
  service stays exactly as-is. One *engine* (Postgres) everywhere, two
  *instances* (local Docker Postgres, cloud Neon) — `db.py` doesn't
  need to know or care which one it's talking to; the difference is
  entirely in the connection string.

## Consequences

- ADR-0016's Cloud Run / Artifact Registry / Secret Manager decisions
  are all unaffected and stand as designed — only the database
  component changes.
- The real cost shape for the cloud deployment drops from ~$9-11/month
  to **effectively $0/month** at this project's traffic level,
  matching the shape of Sam's other low-cost GCP project.
- A new, explicit, named risk this ADR takes on deliberately: this
  trades a GCP-native managed service for a third-party (Neon) free
  tier whose terms could change. Mitigation is structural, not
  hopeful — the schema is plain Postgres, so the exit path is a
  `pg_dump` to anywhere, including back to Cloud SQL if this project
  ever has a reason to pay for guaranteed availability. See "what would
  trigger a revisit" below.
- Everything already built in the prior Tier 3 session for Cloud SQL
  (the Cloud-SQL-specific Grafana datasource file, the Cloud SQL steps
  in `deploy/gcp-deploy.sh` and the runbook) needs updating, not
  scrapped wholesale — the surrounding Cloud Run/Secret Manager/
  Artifact Registry scaffolding is unaffected and stays.

## Fable design consult

Consulted 2026-07-26, as a named "genuine difficulty" checkpoint per
this project's Tier 3 process exception, not a lapse of the
deliberate call-limiting discipline. Grounded in the real, verbatim
schema and all 5 real Grafana queries (pasted directly into the
consult, not summarized) — full transcript in `decisionlog.md`,
2026-07-26. Gave a decisive single recommendation (Neon) with the
specific reasoning against the two real access patterns, not a menu of
options, and explicitly named and rejected a fourth candidate
(Supabase) for a concrete, real failure mode (manual-resume-required
after 7 idle days).

## What would trigger a revisit

- **If Neon's free tier terms change materially** (pricing, autosuspend
  behavior, or a policy shift making it unsuitable for even light
  production use) — the documented exit path (`pg_dump` to Cloud SQL
  or elsewhere) should be exercised, not a reason to panic-migrate
  without a plan.
- **If real traffic ever grows enough that autosuspend/cold-start
  latency becomes a genuine user-facing problem** (not just a
  theoretical one) — worth revisiting whether a paid Neon tier or a
  return to Cloud SQL is justified by then having real usage to
  justify the cost, the opposite condition from today's zero-revenue
  status quo.
- **If the one-retry-on-connect wrapper turns out insufficient** (i.e.
  cold-start connection drops happen more than rarely) — that's a
  signal to add a longer backoff/retry policy, not silently ignore
  intermittent failures.
