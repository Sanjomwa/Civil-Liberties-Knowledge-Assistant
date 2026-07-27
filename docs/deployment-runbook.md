# Cloud Deployment Runbook — Manual Prerequisites

Adjacent to `docs/deployment-design.md` (the frozen pre-implementation
design reference) — this is the actionable checklist, not a design
document, and it's expected to go stale/get checked off as Sam completes
each step, unlike the design doc it sits next to.

`deploy/gcp-deploy.sh` is drafted and reviewed but **not run**. Real GCP
(and now Neon) account setup below only Sam can do — this is exactly the
pause point recorded in `reports.md`.

**Updated 2026-07-26, ADR-0018:** Cloud SQL is replaced by Neon
(serverless Postgres) — real GCP pricing showed Cloud SQL costing
$9-11/month always-on with no usage ceiling, rejected for a zero-revenue
project. Neon is wire-compatible Postgres with a true scale-to-zero free
tier (no credit card, no overage billing).

## Before `deploy/gcp-deploy.sh` can run for real

1. **Create (or confirm) a GCP project, with billing enabled.** GCP's
   standard free-trial credit covers the Cloud Run/Artifact Registry/
   Secret Manager cost shape (now effectively $0/month at this project's
   traffic level, per ADR-0018 — Cloud SQL was the only non-free
   component, and it's gone).

2. **Install and authenticate the `gcloud` CLI locally:**
   ```
   gcloud auth login
   gcloud config set project <PROJECT_ID>
   ```

3. **Enable the required APIs** (also run idempotently by
   `deploy/gcp-deploy.sh` itself, listed here so it can be confirmed
   before running the full script). **`sqladmin.googleapis.com` is no
   longer needed** — Cloud SQL Admin, removed per ADR-0018:
   ```
   gcloud services enable run.googleapis.com
   gcloud services enable artifactregistry.googleapis.com
   gcloud services enable secretmanager.googleapis.com
   ```

4. **Create a free Neon project and database**, replacing the old
   "create a Cloud SQL instance" step entirely:
   - Sign up / log in at `console.neon.tech` (or use Neon's own CLI),
     create a new project, and create a database named `interactions`
     inside it (matching this project's existing schema/database name).
   - Copy the **pooled connection string** Neon provides (its
     `pgbouncer` endpoint — this is what makes true scale-to-zero work;
     the direct/unpooled endpoint is not what this deployment wants).
     It looks like:
     `postgresql://<user>:<password>@<host>-pooler.<region>.aws.neon.tech/interactions?sslmode=require`

5. **Confirm back to Claude Code (or to Cowork, to relay):**
   - The real GCP project ID.
   - The preferred region (`deploy/gcp-deploy.sh` currently defaults the
     placeholder to `us-central1` — confirm or override).

6. **Have ready in your shell environment before running the script**
   (never committed, never baked into any image):
   - `OPENAI_API_KEY` — the real key.
   - `DATABASE_URL` — the real Neon pooled connection string from step 4,
     exactly as Neon provides it (already includes user + password + host
     + `sslmode=require`). This one value is where your real Neon
     credential goes; the script itself derives everything Grafana
     separately needs (host/user/password) from this same string — you
     don't need to provide those a second time.

## What the script does once run for real

Numbered to match `deploy/gcp-deploy.sh`'s own section comments:

0. Sets the active `gcloud` project.
1. Enables the three APIs above (idempotent). No Cloud SQL Admin.
2. Creates a private Artifact Registry Docker repo.
3. Builds and pushes the private app image (`Dockerfile.cloud` —
   requires `docker compose build app` to have produced the public
   baseline image locally first).
4. Builds and pushes the Grafana image (`Dockerfile.grafana.cloud`).
5. Creates three Secret Manager secrets: `openai-api-key` (from
   `OPENAI_API_KEY`), `database-url` (the full Neon connection string,
   from `DATABASE_URL`, mounted directly as the app service's
   `DATABASE_URL` env var), and `neon-password` (the password component,
   parsed out of the same `DATABASE_URL` by the script itself, for
   Grafana's separate host/user/password datasource fields). Grants the
   Cloud Run runtime service account `secretmanager.secretAccessor` on
   all three. No Cloud SQL instance is created anywhere.
6. Deploys the app Cloud Run service.
7. Deploys the Grafana Cloud Run service.

## Verify after a real deploy (explicitly unconfirmed until then)

Flagged in `docs/deployment-design.md`'s own "Open items" list as
stated-but-unverified mechanisms — confirm empirically, don't assume:

- **Grafana's Neon datasource** (`grafana/provisioning-cloud/
  datasources/postgres.yml`, a standard `host:port` + `sslmode=require`
  connection via Grafana's `${VAR}` provisioning env-var expansion)
  actually connects and renders the dashboard.
- **The app's `DATABASE_URL`** (mounted directly from the `database-url`
  secret, Neon's own self-contained pooled connection string) actually
  connects — this should be more straightforward to verify than the old
  Cloud SQL socket-path mechanism, since it's just a standard Postgres
  DSN, but hasn't been tried against a real Neon instance yet.
- **Neon's autosuspend/wake behavior in practice** — confirm the
  one-retry-on-connect wrapper in `db.py`'s `get_conn()` (ADR-0018) is
  actually sufficient for a real cold wake, not just a plausible-sounding
  mitigation. If cold-start connection drops happen more than rarely,
  that's ADR-0018's own named signal to add a longer backoff, not to
  silently ignore intermittent failures.
- Streamlit's `--session-affinity` behavior on a real Cloud Run instance
  (client reconnects landing on the same instance) — unaffected by the
  Neon migration, still unverified from the original Cloud SQL design.

If any of these don't work as drafted, fix the drafted mechanism (this
runbook / the Dockerfile / the datasource YAML / the deploy script) —
don't silently work around it in `db.py` or `app.py` beyond the one
retry wrapper ADR-0018 already specifies, which this phase's own scope
boundary keeps untouched otherwise.
