# ADR-0016: GCP Cloud Deployment Architecture

**Status:** Accepted, 2026-07-26.

## Context

ADR-0012's Tier 3 names cloud deployment as the bonus rubric item (2
points), built only once Tier 2 (interface, monitoring, containerization)
exists to deploy — which it now does, verified live, 7 days ahead of the
2026-08-02 feature-freeze gate. Sam chose GCP as the target platform.

This is a genuinely new design surface, not a deviation from an existing
frozen decision — nothing in the architecture doc or any prior ADR
addressed where the containerized stack runs. Real facts on the table
before designing anything:

The stack is three `docker-compose` services (`postgres:16-alpine` with
a `pgdata` volume; `app`, built from a local `Dockerfile`, bound to
`127.0.0.1:8501` since the port-exposure incident; `grafana/grafana:latest`
with anonymous-viewer auth, bound to `127.0.0.1:3000`), currently running
only on Sam's own laptop.

The real, load-bearing constraint: `src/interface/entrypoint.sh` runs
corpus rehydration (`rehydrate.py --org freedomhouse`, `--org accessnow`)
and a full `embed.py` re-embed **unconditionally on every container
start**, with no caching across restarts. A real timed run on Sam's own
machine measured this at roughly 15 minutes of sustained 190-198% CPU
utilization to rebuild the 3,783-chunk index. This exists because the
Docker image only ever bakes the license-clear 54% tiered baseline
(OONI + CIPESA, per ADR-0013) at build time — Freedom House and Access
Now's 46% is deliberately never baked into a public image, and is only
ever fetched live from their own servers at container-start time, to
respect the still-open Freedom House permission request.

Expected real traffic for this deployment is low and bursty — a course
grader or a portfolio visitor clicking a link occasionally, not sustained
production load. Sam has no prior GCP experience.

**Per Sam's explicit process decision (2026-07-26, logged in this
project's own `CLAUDE.md` Section 3): this design was produced by a
single, deep Fable design consult**, a deliberate test of Fable's
technical/architectural design capability (reversing the project's
usual Opus-does-design default for this one phase) rather than the
usual Opus consult. Full transcript basis in `decisionlog.md`,
2026-07-26. Opus is reserved for implementation-time consults on this
phase instead, per that same process decision.

## Decision

### Compute: Cloud Run, not a single always-on VM

**Cloud Run**, not GCE. The traffic pattern (low, bursty, occasional
visits) is exactly Cloud Run's fit: scale-to-zero billing, a free HTTPS
URL, no OS/VM maintenance for a first-time GCP user. A single
always-on GCE VM running `docker-compose` as-is would be conceptually
simpler but costs more (an always-on `e2-medium` runs ~$15-30/month
regardless of whether anyone visits) and adds patching overhead with no
real benefit given the traffic shape.

`docker-compose`'s three services do not map 1:1 onto Cloud Run — they
become **two Cloud Run services plus one managed database**, not three
containers on one host:

1. **App** — its own Cloud Run service, `min-instances=0`, 1-2 vCPU /
   1-2 GiB RAM. Streamlit needs websockets, which Cloud Run supports;
   `--session-affinity` should be set so a client's reconnects land on
   the same instance.
2. **Grafana** — its own Cloud Run service, not merged with the app.
   This works because this project's Grafana is already effectively
   stateless: dashboards come from provisioning files (baked into a
   small custom Grafana image built from the existing
   `grafana/provisioning`/`grafana/dashboards` folders), data comes from
   Postgres, and anonymous-viewer auth (Decision 7,
   `docs/interface-design.md`) means there's no per-user state to lose
   on a cold start.
3. **Postgres** — **Cloud SQL** (smallest shared-core tier,
   `db-f1-micro`, ~10 GB), not a self-hosted container. This is the one
   component that genuinely needs durable, managed persistence — the
   interaction log *is* the monitoring story this project already
   built, and losing it on every cold start would break that story
   entirely. Both Cloud Run services attach via
   `--add-cloudsql-instances`; `DATABASE_URL` and Grafana's Postgres
   datasource host both use the Cloud SQL unix-socket path
   (`/cloudsql/PROJECT:REGION:INSTANCE`).

### Secrets: GCP Secret Manager, not a baked or plain env var

`OPENAI_API_KEY` and the Postgres password move to **Secret Manager**
(`gcloud secrets create`, service-account granted
`secretmanager.secretAccessor`, deployed via `--set-secrets`). Neither
value is ever baked into an image or committed to the repo — the
current local `.env`-sourced approach is correct for a laptop-only
`docker-compose` run and not appropriate once the image is deployed
anywhere shared.

### Resolving the rehydration/cold-start tension: bake at deploy time, not runtime

**The central design problem, resolved explicitly, not left implicit:**
scale-to-zero and a 15-minute unconditional rehydration-on-start are
incompatible — a real visitor hitting a cold instance would wait 15
minutes, which defeats the purpose of a shareable demo link. Keeping an
instance permanently warm to hide this just trades the problem for a
different, needless always-on cost.

**Decision: move rehydration from a runtime step to a deploy-time step,
via a private, second-stage image.** The public Dockerfile, the public
GitHub repo, and any public-facing image artifact are unchanged and
stay at the 54% tiered baseline — this does not touch ADR-0013's
licensing-driven tiered-release design at all. A second, private
Dockerfile (`FROM <the existing baseline image>`) adds one `RUN` step
that performs the same rehydration + re-embed the runtime entrypoint
does today (`rehydrate.py --org freedomhouse && --org accessnow &&
embed.py`), and this private image is pushed to a private **Artifact
Registry** repository in Sam's own GCP project — never published, never
part of the public repo or its release artifacts.

This is not a new redistribution act beyond what already happens today:
the mechanism (fetch each org's own real content from their own
servers, verify against the shipped hash) is identical to what
`entrypoint.sh` already does at runtime; this only changes *when* that
fetch happens and *where* the result is cached. If the fetch fails
during this deploy-time build, the build itself fails loudly and Sam
retries — a strictly better failure mode than the current runtime
behavior's silent fall-back to the 54% baseline, since a deploy-time
failure is caught before anything goes live, not discovered by a real
visitor getting a degraded answer.

Cloud Run's own `entrypoint.sh` for this private image becomes just the
final `exec uv run streamlit run ...` line — no rehydration logic at
runtime at all. Cold start drops from ~15 minutes to seconds, since
loading an already-built embedding index (a few MB of vectors) is
trivial compared to computing it.

### Cost shape

**Corrected 2026-07-26 against real, official GCP pricing (not
estimated) — Sam's billing account is a real, already-billed monthly
account, not a free trial, so this needed verifying properly rather
than assumed.** Source: `cloud.google.com/sql/pricing` and
`cloud.google.com/run/pricing`, fetched directly.

- **Cloud SQL `db-f1-micro`** (Iowa/`us-central1`): $0.0105/hour
  instance cost × ~730 hours/month ≈ **$7.67/month**, plus SSD storage
  at $0.000232877/GiB-hour — a 10 GB instance ≈ **$1.70/month**. **Real
  total: ~$9.40-11/month**, the one always-on, non-negotiable cost.
- **A real, avoidable cost gotcha, not previously flagged:** Cloud SQL
  charges **$0.01/hour (~$7.30/month) for an idle public IPv4
  address**. Since this design already connects via the Cloud SQL
  Unix-socket path (`--add-cloudsql-instances`), the instance should be
  created **with no public IP at all** (private-only) — this avoids
  the charge entirely and is also better security practice. Must be
  set explicitly at instance creation; confirm this in the deploy
  script rather than assuming the default.
- **Cloud Run**: free tier is 2 million requests, 360,000 GiB-seconds,
  180,000 vCPU-seconds, and 1 GiB egress per month — at the traffic
  level described (occasional demo visits), both services combined
  should stay within this free tier, i.e. **effectively $0/month**.
- **Artifact Registry, Secret Manager**: both have their own free
  tiers (storage/version-count) large enough for this project's two
  small images and two secrets — effectively **$0/month or pennies**.

**Real overall shape: roughly $9-12/month, driven entirely by Cloud
SQL** — assuming the no-public-IP setting is applied. **This is not
covered by any free trial** — Sam's account is billed monthly already,
so this is real recurring spend from day one, not a one-time credit
being drawn down. A practical cost lever Sam has, if he wants finer
control: Cloud SQL can be **manually stopped** between periods when no
demo visits are expected (compute charges stop while stopped; storage
charges continue) and restarted in roughly a minute when the link is
being shared again — unlike the app's own corpus rehydration, this is
unrelated to the 15-minute cold-start problem this ADR already solved,
so stopping/restarting Cloud SQL is safe and doesn't reintroduce it.

## Consequences

- A new, private deploy-time Dockerfile and a private Artifact Registry
  repository are added to the project's real infrastructure — not
  committed to the public repo (secrets and the bake mechanism are
  deploy-time concerns, not source).
- `docker-compose.yml` and the local `entrypoint.sh` are unaffected —
  local development continues to work exactly as it does today. Cloud
  deployment is an additional target, not a replacement for local dev.
- `docs/licensing.md`/ADR-0013's tiered-release policy is unaffected —
  the private deploy-time image is never published or distributed, so
  it doesn't change what's public.
- This ADR does not cover implementation specifics (exact `gcloud`
  commands, Cloud Build vs. local build-and-push, Grafana's socket-path
  datasource config verified empirically) — those are implementation-time
  decisions for the Claude Code handoff and, where genuinely stuck, an
  Opus consult, per Sam's process decision for this phase.

## Fable design consult

Consulted 2026-07-26 (a single deep design pass, not iterative — see
Context above for the process rationale). Gave a decisive, opinionated
recommendation rather than a menu: Cloud Run + Cloud SQL + Secret
Manager, with the deploy-time-bake resolution to the cold-start
tension stated as the central design call, defended on its own terms
(what it costs — needing to rebuild and repush the private image
whenever upstream content changes — versus what it buys — a genuinely
fast cold start on a scale-to-zero service). Full transcript in
`decisionlog.md`, 2026-07-26.

## What would trigger a revisit

- **If real traffic turns out to be higher/steadier than expected**
  (e.g., this becomes a genuinely used tool, not just an occasional
  demo visit) — revisit whether `min-instances=0` still makes sense, or
  whether a small `min-instances=1` (removing even the seconds-scale
  cold start) is worth the modest added cost.
- **If Freedom House replies with permission** before or after this
  deployment exists — no change needed to this ADR's mechanism (the
  private image still just fetches from their real servers), but worth
  noting alongside ADR-0013's own revisit condition, since both track
  the same underlying event.
- **If the private image's deploy-time rehydration fetch starts failing
  regularly** (e.g., Freedom House/Access Now change their site
  structure) — that's a real reproducibility gap to disclose in
  deployment notes, not silently retried indefinitely, same discipline
  as ADR-0013's `rehydrate.py` revisit condition.
