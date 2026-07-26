# Cloud Deployment (GCP) — Pre-Implementation Design

Written 2026-07-26, before any GCP resources exist — mirrors
`retrieval-design.md`/`generation-design.md`/`evaluation-design.md`/
`interface-design.md`'s shape: a synthesized design reference, not a
live status page. Covers ADR-0012 Tier 3's cloud-deployment item. Full
decision rationale and tradeoffs: `docs/adr/0016-gcp-cloud-deployment-
architecture.md`. Design produced via a single deep Fable consult, per
this project's `CLAUDE.md` Section 3 (2026-07-26 Tier 3 exception) —
transcript basis in `decisionlog.md`, same date.

## Scope boundary

Ends at: the existing Streamlit app, Postgres logging, and Grafana
dashboard all reachable at a real public URL, with the corpus's full
(rehydrated) content already indexed at deploy time rather than at
container start. Does not touch `generate.py`, `search.py`,
`app.py`, or any prompt/retrieval/judge behavior — this phase is
infrastructure only. Does not touch the public repo, the public
Dockerfile, or ADR-0013's tiered public-release policy — those stay
exactly as they are.

## Decisions

**1. Compute: Cloud Run (two services), not a single GCE VM.** The
`app` and `grafana` compose services become two independent Cloud Run
services, `min-instances=0`. `docker-compose`'s multi-container shape
does not port directly — Cloud Run runs one container per service, no
compose file support. Rationale and cost comparison: ADR-0016.

**2. Database: Cloud SQL (`db-f1-micro`), not a self-hosted Postgres
container.** Both Cloud Run services (`app`, `grafana`) connect via
`--add-cloudsql-instances` and the Cloud SQL unix-socket path
(`/cloudsql/PROJECT:REGION:INSTANCE`), not a TCP host:port. This is the
one component needing durable, managed storage — the interaction log
is the monitoring story this project already built (Tier 2); losing it
on every cold start isn't acceptable.

**3. Secrets: GCP Secret Manager for `OPENAI_API_KEY` and the Postgres
password.** Neither value is baked into any image or committed to the
repo. Deployed via `--set-secrets` on the app's Cloud Run service; the
service account needs `roles/secretmanager.secretAccessor`.

**4. The rehydration/cold-start fix: a private, second-stage image,
built once at deploy time, not the existing runtime `entrypoint.sh`
unmodified.** This is the load-bearing decision — full reasoning in
ADR-0016. Concretely:

- The existing public `Dockerfile` and `entrypoint.sh` are untouched —
  local `docker-compose up` keeps working exactly as today.
- A new, **private** `Dockerfile.cloud` (name indicative, not fixed):
  `FROM` the existing baseline image, then one `RUN` step performing
  what `entrypoint.sh` does today at container start —
  `uv run python src/ingestion/rehydrate.py --org freedomhouse && uv
  run python src/ingestion/rehydrate.py --org accessnow && uv run
  python src/retrieval/embed.py`. If any step fails, the *build* fails
  — caught before deploy, not discovered by a real visitor.
- This image is pushed to a **private Artifact Registry** repository in
  Sam's own GCP project. Never published, never part of the public
  repo, never referenced from any public release artifact.
- The cloud image's actual runtime command is just
  `exec uv run streamlit run src/interface/app.py --server.address 0.0.0.0 --server.port $PORT`
  (Cloud Run injects `$PORT`; no rehydration logic runs at container
  start at all for this image).
- Practical consequence: whenever Freedom House or Access Now publish
  something new, the private image needs a manual rebuild + repush to
  pick it up — this is the accepted cost named in ADR-0016, not an
  oversight.

**5. Grafana on Cloud Run: bake provisioning into a small custom
image.** `grafana/provisioning/` and `grafana/dashboards/` (currently
bind-mounted locally) get `COPY`'d into a small Grafana-based image
instead, since Cloud Run has no bind-mount equivalent. No dashboard
state needs to persist beyond what Postgres already stores — anonymous
Viewer auth (Decision 7, `docs/interface-design.md`) means there's no
per-user Grafana state to lose.

**6. `docker-compose.yml` and local dev are unaffected.** This design
adds a deployment target; it does not replace or modify the local
development path. Anyone cloning the repo still runs
`docker compose up --build` exactly as documented in `README.md` today.

## Open items for implementation (not decided here)

Per ADR-0016's own list — resolve these during the build, consulting
Opus if genuinely stuck, not by improvising a silent default:

- Cloud Build vs. local build-and-push for the private image.
- Whether `min-instances=1` is worth the small added cost during
  active grading review (removes even a few seconds of cold start).
- Verifying Grafana's Cloud SQL socket-path datasource config and
  Streamlit's `--session-affinity` behavior empirically on the first
  real deploy — both are stated as the expected mechanism, not yet
  confirmed against a real Cloud Run instance.
- Cloud SQL auth mode: password via Secret Manager (simplest, default
  here) vs. IAM database authentication (optional polish, not required).

## Cost shape

Cloud SQL (`db-f1-micro`) is the only always-on cost, ~$10-13/month.
Cloud Run is ~$0 at the expected traffic level (scale-to-zero,
per-request billing). Artifact Registry and Secret Manager: pennies.
Overall: a **$10-15/month shape**, covered in full by GCP's standard
free-trial credit through submission and grading.
