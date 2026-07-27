#!/bin/bash
# deploy/gcp-deploy.sh -- GCP deployment sequence per ADR-0016 / ADR-0018
# / docs/deployment-design.md. DRAFTED, NOT RUN -- this is documentation
# of the intended command sequence, reviewed here before any real GCP
# resource is created. See reports.md for the pause point: real
# execution needs Sam's own GCP project, billing, and gcloud auth first
# (docs/deployment-runbook.md).
#
# ADR-0018 (2026-07-26): Cloud SQL is REMOVED from this script entirely --
# replaced by Neon (serverless Postgres, wire-compatible, true
# scale-to-zero, no GCP billing exposure). No Cloud SQL instance, no
# `--add-cloudsql-instances`, no sqladmin.googleapis.com anywhere below.
#
# PROJECT_ID/REGION below are now REAL, confirmed values (2026-07-27) --
# not placeholders anymore. Project created fresh (`civil-liberties-kb-
# assistant` -- the originally-proposed `civil-liberties-knowledge-
# assistant` exceeds GCP's 30-character project-ID limit), billing linked
# to Sam's existing account, all three required APIs enabled, confirmed
# via `gcloud services list --enabled`. Region (`us-central1`) confirmed
# with Sam per the runbook's own default-unless-otherwise-stated
# instruction. Still overridable via env var if either ever needs to
# change -- not hardcoded without an escape hatch.
#
# Does NOT decide Cloud Build vs. local build-and-push (deployment-design.md's
# own "open item, not decided here") -- this draft uses local build-and-push
# (simplest, no extra GCP service setup beyond what the runbook already
# lists); switching to `gcloud builds submit` instead is a straightforward
# later change if Sam prefers it, not a rewrite.
#
# Usage (once Sam has completed docs/deployment-runbook.md's remaining
# checklist item -- creating a free Neon project/database and copying its
# pooled connection string; the GCP project/billing/API setup below is
# already done):
#   OPENAI_API_KEY=<real-key> \
#   DATABASE_URL='postgresql://<user>:<password>@<host>/interactions?sslmode=require' \
#     ./deploy/gcp-deploy.sh
#
# (PROJECT_ID/REGION only need overriding if you want a different project
# or region than the confirmed defaults below.)

set -euo pipefail

# --- Real, confirmed values -- still overridable via env var ---
PROJECT_ID="${PROJECT_ID:-civil-liberties-kb-assistant}"
REGION="${REGION:-us-central1}"
AR_REPO="civil-liberties-knowledge-assistant"
APP_SERVICE="app-cloud"
GRAFANA_SERVICE="grafana-cloud"

# --- Secrets read from the calling shell's environment, never hardcoded ---
OPENAI_API_KEY="${OPENAI_API_KEY:?Set OPENAI_API_KEY in your shell before running this script}"
# DATABASE_URL: the FULL pooled Neon connection string, exactly as Neon's
# console/CLI provides it (includes user + password + host + sslmode
# already) -- <<< SAM: PASTE YOUR REAL NEON POOLED CONNECTION STRING HERE
# (or export DATABASE_URL before running this script) >>>. This one value
# is where Sam's real Neon credential goes; nothing else in this script
# needs a separate raw password for the app service.
DATABASE_URL="${DATABASE_URL:?Set DATABASE_URL to your real Neon pooled connection string before running this script}"

AR_HOST="${REGION}-docker.pkg.dev"
APP_IMAGE="${AR_HOST}/${PROJECT_ID}/${AR_REPO}/app-cloud:latest"
GRAFANA_IMAGE="${AR_HOST}/${PROJECT_ID}/${AR_REPO}/grafana-cloud:latest"

echo "=== 0. Set active project ==="
gcloud config set project "$PROJECT_ID"

echo "=== 1. Enable required APIs (idempotent -- safe to re-run) ==="
# sqladmin.googleapis.com REMOVED per ADR-0018 -- Neon needs no GCP API
# at all, it's a third-party service reached over a plain connection
# string.
gcloud services enable \
    run.googleapis.com \
    artifactregistry.googleapis.com \
    secretmanager.googleapis.com

echo "=== 2. Create Artifact Registry repo (private) ==="
gcloud artifacts repositories create "$AR_REPO" \
    --repository-format=docker \
    --location="$REGION" \
    --description="Private images for Civil Liberties Knowledge Assistant (app-cloud, grafana-cloud) -- never public" \
    || echo "[ok] repo may already exist -- continuing"

gcloud auth configure-docker "$AR_HOST" --quiet

echo "=== 3. Build + push the private app image (Dockerfile.cloud) ==="
# Requires the public baseline image to already exist locally:
#   docker compose build app
docker build -f Dockerfile.cloud -t "$APP_IMAGE" .
docker push "$APP_IMAGE"

echo "=== 4. Build + push the Grafana image (Dockerfile.grafana.cloud) ==="
docker build -f Dockerfile.grafana.cloud -t "$GRAFANA_IMAGE" .
docker push "$GRAFANA_IMAGE"

# Step "5. Create Cloud SQL instance" REMOVED entirely per ADR-0018 --
# Sam creates the Neon project/database himself (docs/deployment-runbook.md),
# outside gcloud entirely, and provides the resulting connection string
# via DATABASE_URL above.

echo "=== 5. Create the Secret Manager secrets ==="
# NOTE: `gcloud secrets create` fails if the secret already exists -- on a
# genuine re-run (e.g. rotating a key), use
# `gcloud secrets versions add <name> --data-file=-` instead of `create`.
printf '%s' "$OPENAI_API_KEY" | gcloud secrets create openai-api-key --data-file=- \
    || echo "[ok] secret may already exist -- use 'versions add' to rotate it instead"

# The app service needs the FULL connection string (one secret, mounted
# directly as DATABASE_URL) -- Neon's URL is self-contained
# (user+password+host+sslmode all in one string), unlike Cloud SQL's
# socket path, so there's no more need for the PGPASSWORD-split workaround
# the Cloud SQL version of this script used.
printf '%s' "$DATABASE_URL" | gcloud secrets create database-url --data-file=- \
    || echo "[ok] secret may already exist -- use 'versions add' to rotate it instead"

# Grafana's datasource needs discrete host/user/password fields, not one
# URL (grafana/provisioning-cloud/datasources/postgres.yml can't parse a
# connection string) -- derive them from the same DATABASE_URL Sam
# already provided, rather than asking Sam to type the same credential in
# twice. NEON_HOST/NEON_USER are not secret on their own (just an
# endpoint hostname and username); only the derived password gets its own
# Secret Manager entry.
NEON_HOST="$(python3 -c "import sys, urllib.parse as u; print(u.urlparse(sys.argv[1]).hostname)" "$DATABASE_URL")"
NEON_USER="$(python3 -c "import sys, urllib.parse as u; print(u.urlparse(sys.argv[1]).username)" "$DATABASE_URL")"
NEON_PASSWORD="$(python3 -c "import sys, urllib.parse as u; print(u.urlparse(sys.argv[1]).password)" "$DATABASE_URL")"
NEON_DATABASE="$(python3 -c "import sys, urllib.parse as u; print(u.urlparse(sys.argv[1]).path.lstrip('/'))" "$DATABASE_URL")"
echo "[ok] parsed Neon host from DATABASE_URL: $NEON_HOST"

printf '%s' "$NEON_PASSWORD" | gcloud secrets create neon-password --data-file=- \
    || echo "[ok] secret may already exist -- use 'versions add' to rotate it instead"

PROJECT_NUMBER="$(gcloud projects describe "$PROJECT_ID" --format='value(projectNumber)')"
RUNTIME_SA="${PROJECT_NUMBER}-compute@developer.gserviceaccount.com"

for secret in openai-api-key database-url neon-password; do
    gcloud secrets add-iam-policy-binding "$secret" \
        --member="serviceAccount:${RUNTIME_SA}" \
        --role="roles/secretmanager.secretAccessor"
done

echo "=== 6. Deploy the app Cloud Run service ==="
# --add-cloudsql-instances REMOVED per ADR-0018 -- Neon needs no Cloud
# Run <-> Cloud SQL wiring at all, it's reached like any normal Postgres
# host over the network.
#
# --session-affinity: Streamlit needs a client's reconnects to land on
# the same instance (ADR-0016, unaffected by the Neon migration).
gcloud run deploy "$APP_SERVICE" \
    --image="$APP_IMAGE" \
    --region="$REGION" \
    --platform=managed \
    --allow-unauthenticated \
    --session-affinity \
    --min-instances=0 \
    --cpu=1 \
    --memory=2Gi \
    --set-secrets="OPENAI_API_KEY=openai-api-key:latest,DATABASE_URL=database-url:latest"

echo "=== 7. Deploy the Grafana Cloud Run service ==="
# Grafana's own provisioning env-var expansion (grafana/provisioning-cloud/
# datasources/postgres.yml) reads NEON_HOST/NEON_USER/NEON_PASSWORD/
# NEON_DATABASE by exactly these names -- keep these four env-var names in
# sync with that file if any changes.
gcloud run deploy "$GRAFANA_SERVICE" \
    --image="$GRAFANA_IMAGE" \
    --region="$REGION" \
    --platform=managed \
    --allow-unauthenticated \
    --port=3000 \
    --min-instances=0 \
    --cpu=1 \
    --memory=1Gi \
    --set-secrets="NEON_PASSWORD=neon-password:latest" \
    --set-env-vars="NEON_HOST=${NEON_HOST},NEON_USER=${NEON_USER},NEON_DATABASE=${NEON_DATABASE},GF_AUTH_ANONYMOUS_ENABLED=true,GF_AUTH_ANONYMOUS_ORG_ROLE=Viewer"

echo "=== Done (drafted commands only -- this line only prints if actually run) ==="
echo "App URL:     $(gcloud run services describe "$APP_SERVICE" --region "$REGION" --format='value(status.url)')"
echo "Grafana URL: $(gcloud run services describe "$GRAFANA_SERVICE" --region "$REGION" --format='value(status.url)')"
