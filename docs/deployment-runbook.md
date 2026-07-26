# Cloud Deployment Runbook — Manual Prerequisites

Adjacent to `docs/deployment-design.md` (the frozen pre-implementation
design reference) — this is the actionable checklist, not a design
document, and it's expected to go stale/get checked off as Sam completes
each step, unlike the design doc it sits next to.

`deploy/gcp-deploy.sh` is drafted and reviewed but **not run**. Real GCP
account setup below only Sam can do — this is exactly the pause point
recorded in `reports.md`.

## Before `deploy/gcp-deploy.sh` can run for real

1. **Create (or confirm) a GCP project, with billing enabled.** GCP's
   standard free-trial credit covers this deployment's full $10-15/month
   shape through submission and grading (per ADR-0016's cost estimate).

2. **Install and authenticate the `gcloud` CLI locally:**
   ```
   gcloud auth login
   gcloud config set project <PROJECT_ID>
   ```

3. **Enable the required APIs** (also run idempotently by
   `deploy/gcp-deploy.sh` itself, listed here so it can be confirmed
   before running the full script):
   ```
   gcloud services enable run.googleapis.com
   gcloud services enable sqladmin.googleapis.com
   gcloud services enable artifactregistry.googleapis.com
   gcloud services enable secretmanager.googleapis.com
   ```

4. **Confirm back to Claude Code (or to Cowork, to relay):**
   - The real GCP project ID.
   - The preferred region (`deploy/gcp-deploy.sh` currently defaults the
     placeholder to `us-central1` — confirm or override).

5. **Have ready in your shell environment before running the script**
   (never committed, never baked into any image):
   - `OPENAI_API_KEY` — the real key.
   - `POSTGRES_PASSWORD` — a real password to set for the new Cloud SQL
     `postgres` user (the script sets it, doesn't generate it).

## What the script does once run for real

Numbered to match `deploy/gcp-deploy.sh`'s own section comments:

0. Sets the active `gcloud` project.
1. Enables the four APIs above (idempotent).
2. Creates a private Artifact Registry Docker repo.
3. Builds and pushes the private app image (`Dockerfile.cloud` —
   requires `docker compose build app` to have produced the public
   baseline image locally first).
4. Builds and pushes the Grafana image (`Dockerfile.grafana.cloud`).
5. Creates the Cloud SQL instance (`db-f1-micro`), the `interactions`
   database, and sets the `postgres` user's password.
6. Creates the two Secret Manager secrets (`openai-api-key`,
   `postgres-password`) and grants the Cloud Run runtime service account
   `secretmanager.secretAccessor`.
7. Deploys the app Cloud Run service.
8. Deploys the Grafana Cloud Run service.

## Verify after a real deploy (explicitly unconfirmed until then)

Both flagged in `docs/deployment-design.md`'s own "Open items" list as
stated-but-unverified mechanisms — confirm empirically, don't assume:

- **Grafana's Cloud SQL datasource** (`grafana/provisioning-cloud/
  datasources/postgres.yml`, using the Unix-socket path and Grafana's
  `${VAR}` provisioning env-var expansion) actually connects and renders
  the dashboard.
- **The app's `DATABASE_URL`/`PGPASSWORD` split** (see
  `deploy/gcp-deploy.sh` step 7's comment — relies on standard libpq
  behavior to resolve a DSN with no embedded password from the
  `PGPASSWORD` env var, so `db.py` needs zero code changes) actually
  connects.
- Streamlit's `--session-affinity` behavior on a real Cloud Run instance
  (client reconnects landing on the same instance).

If any of these don't work as drafted, fix the drafted mechanism (this
runbook / the Dockerfile / the datasource YAML) — don't silently
work around it in `db.py` or `app.py`, which this phase's own scope
boundary keeps untouched.
