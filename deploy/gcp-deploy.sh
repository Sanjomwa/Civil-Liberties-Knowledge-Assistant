#!/bin/bash
# deploy/gcp-deploy.sh -- GCP deployment sequence per ADR-0016 / docs/
# deployment-design.md. DRAFTED, NOT RUN -- this is documentation of the
# intended command sequence, reviewed here before any real GCP resource
# is created. See reports.md for the pause point: real execution needs
# Sam's own GCP project, billing, and gcloud auth first (B2 checklist).
#
# Placeholders below (PROJECT_ID, REGION) are NOT real resource names --
# per this task's own instruction, don't invent them. Set them as real
# environment variables before running, or edit the defaults directly
# once Sam confirms them.
#
# Does NOT decide Cloud Build vs. local build-and-push (deployment-design.md's
# own "open item, not decided here") -- this draft uses local build-and-push
# (simplest, no extra GCP service setup beyond what B2's checklist already
# lists); switching to `gcloud builds submit` instead is a straightforward
# later change if Sam prefers it, not a rewrite.
#
# Usage (once Sam has completed the B2 checklist in reports.md):
#   PROJECT_ID=<real-project-id> REGION=<real-region> \
#   OPENAI_API_KEY=<real-key> POSTGRES_PASSWORD=<real-password> \
#     ./deploy/gcp-deploy.sh

set -euo pipefail

# --- Placeholders -- confirm with Sam before using real values ---
PROJECT_ID="${PROJECT_ID:?Set PROJECT_ID -- e.g. PROJECT_ID=my-real-project-id}"
REGION="${REGION:-us-central1}"  # placeholder default; confirm Sam's preferred region
AR_REPO="civil-liberties-knowledge-assistant"
SQL_INSTANCE="civil-liberties-interactions"
APP_SERVICE="app-cloud"
GRAFANA_SERVICE="grafana-cloud"

# --- Secrets read from the calling shell's environment, never hardcoded ---
OPENAI_API_KEY="${OPENAI_API_KEY:?Set OPENAI_API_KEY in your shell before running this script}"
POSTGRES_PASSWORD="${POSTGRES_PASSWORD:?Set POSTGRES_PASSWORD in your shell before running this script}"

AR_HOST="${REGION}-docker.pkg.dev"
APP_IMAGE="${AR_HOST}/${PROJECT_ID}/${AR_REPO}/app-cloud:latest"
GRAFANA_IMAGE="${AR_HOST}/${PROJECT_ID}/${AR_REPO}/grafana-cloud:latest"

echo "=== 0. Set active project ==="
gcloud config set project "$PROJECT_ID"

echo "=== 1. Enable required APIs (idempotent -- safe to re-run) ==="
# Same commands as reports.md's B2 checklist item 3, included here too so
# this script is self-sufficient even if Sam runs it before that manual
# checklist for some reason.
gcloud services enable \
    run.googleapis.com \
    sqladmin.googleapis.com \
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

echo "=== 5. Create Cloud SQL instance (db-f1-micro) ==="
gcloud sql instances create "$SQL_INSTANCE" \
    --database-version=POSTGRES_16 \
    --tier=db-f1-micro \
    --region="$REGION" \
    --storage-size=10 \
    --storage-type=HDD \
    || echo "[ok] instance may already exist -- continuing"

gcloud sql databases create interactions --instance="$SQL_INSTANCE" \
    || echo "[ok] database may already exist -- continuing"

gcloud sql users set-password postgres \
    --instance="$SQL_INSTANCE" \
    --password="$POSTGRES_PASSWORD"

CLOUDSQL_CONNECTION_NAME="$(gcloud sql instances describe "$SQL_INSTANCE" --format='value(connectionName)')"
echo "[ok] Cloud SQL connection name: $CLOUDSQL_CONNECTION_NAME"

echo "=== 6. Create the two Secret Manager secrets ==="
# NOTE: `gcloud secrets create` fails if the secret already exists -- on a
# genuine re-run (e.g. rotating a key), use
# `gcloud secrets versions add <name> --data-file=-` instead of `create`.
printf '%s' "$OPENAI_API_KEY" | gcloud secrets create openai-api-key --data-file=- \
    || echo "[ok] secret may already exist -- use 'versions add' to rotate it instead"
printf '%s' "$POSTGRES_PASSWORD" | gcloud secrets create postgres-password --data-file=- \
    || echo "[ok] secret may already exist -- use 'versions add' to rotate it instead"

PROJECT_NUMBER="$(gcloud projects describe "$PROJECT_ID" --format='value(projectNumber)')"
RUNTIME_SA="${PROJECT_NUMBER}-compute@developer.gserviceaccount.com"

gcloud secrets add-iam-policy-binding openai-api-key \
    --member="serviceAccount:${RUNTIME_SA}" \
    --role="roles/secretmanager.secretAccessor"
gcloud secrets add-iam-policy-binding postgres-password \
    --member="serviceAccount:${RUNTIME_SA}" \
    --role="roles/secretmanager.secretAccessor"

echo "=== 7. Deploy the app Cloud Run service ==="
# DATABASE_URL deliberately does NOT embed the password -- psycopg/libpq
# resolves a missing password in the DSN from the standard PGPASSWORD
# environment variable automatically, so the real secret value never
# needs to be string-interpolated into DATABASE_URL (which --set-secrets
# alone can't do -- Cloud Run doesn't expand one env var's value inside
# another's). This is standard libpq behavior, not a new mechanism this
# project invented, but UNVERIFIED against this project's actual db.py
# (a plain `psycopg.connect(DATABASE_URL)` call) until the first real
# deploy -- confirm this connects before trusting it silently.
#
# --session-affinity: Streamlit needs a client's reconnects to land on
# the same instance (ADR-0016).
gcloud run deploy "$APP_SERVICE" \
    --image="$APP_IMAGE" \
    --region="$REGION" \
    --platform=managed \
    --allow-unauthenticated \
    --session-affinity \
    --min-instances=0 \
    --cpu=1 \
    --memory=2Gi \
    --add-cloudsql-instances="$CLOUDSQL_CONNECTION_NAME" \
    --set-secrets="OPENAI_API_KEY=openai-api-key:latest,PGPASSWORD=postgres-password:latest" \
    --set-env-vars="DATABASE_URL=postgresql://postgres@/interactions?host=/cloudsql/${CLOUDSQL_CONNECTION_NAME}"

echo "=== 8. Deploy the Grafana Cloud Run service ==="
# Grafana's own provisioning env-var expansion (grafana/provisioning-cloud/
# datasources/postgres.yml) reads POSTGRES_PASSWORD and
# CLOUDSQL_CONNECTION_NAME by exactly these names -- keep these two
# env-var names in sync with that file if either changes.
gcloud run deploy "$GRAFANA_SERVICE" \
    --image="$GRAFANA_IMAGE" \
    --region="$REGION" \
    --platform=managed \
    --allow-unauthenticated \
    --min-instances=0 \
    --cpu=1 \
    --memory=1Gi \
    --add-cloudsql-instances="$CLOUDSQL_CONNECTION_NAME" \
    --set-secrets="POSTGRES_PASSWORD=postgres-password:latest" \
    --set-env-vars="CLOUDSQL_CONNECTION_NAME=${CLOUDSQL_CONNECTION_NAME},GF_AUTH_ANONYMOUS_ENABLED=true,GF_AUTH_ANONYMOUS_ORG_ROLE=Viewer"

echo "=== Done (drafted commands only -- this line only prints if actually run) ==="
echo "App URL:     $(gcloud run services describe "$APP_SERVICE" --region "$REGION" --format='value(status.url)')"
echo "Grafana URL: $(gcloud run services describe "$GRAFANA_SERVICE" --region "$REGION" --format='value(status.url)')"
