#!/bin/sh
# entrypoint.cloud.sh -- Cloud Run's runtime entrypoint for the private,
# deploy-time-baked image (Dockerfile.cloud). Per ADR-0016 / docs/
# deployment-design.md Decision 4.
#
# No rehydration logic here at all -- Dockerfile.cloud's own RUN step
# already rehydrated both orgs and re-embedded the full corpus at BUILD
# time (and fails the build loudly if that didn't work, per its own
# comment), so cold start here is just starting Streamlit against an
# already-complete index. This is the entire fix for the scale-to-zero /
# 15-minute-rehydration conflict ADR-0016 resolves: cold start drops from
# ~15 minutes to seconds.
#
# $PORT is injected by Cloud Run at runtime -- never hardcoded to 8501
# here, unlike the local entrypoint.sh (docker-compose binds a fixed
# host port, Cloud Run does not).
set -e
exec uv run streamlit run src/interface/app.py --server.address 0.0.0.0 --server.port "$PORT"
