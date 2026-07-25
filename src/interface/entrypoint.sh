#!/bin/sh
# entrypoint.sh -- first-run rehydration, per docs/interface-design.md
# Decision 8. Runs once per container start (not per query, not retried
# in a loop): attempts to fetch Freedom House + Access Now's real text
# directly from their own servers, verified against the shipped hash,
# then re-embeds the full corpus if both succeed. On any failure --
# no network, upstream error, hash mismatch -- logs it plainly and keeps
# serving the build-time 54% baseline (OONI + CIPESA) already indexed
# into the image. Never crashes the app over a rehydration failure.
set -e

echo "[entrypoint] first-run rehydration attempt (Freedom House + Access Now)..."

REHYDRATE_OK=1

if ! uv run python src/ingestion/rehydrate.py --org freedomhouse; then
    echo "[entrypoint] WARNING: Freedom House rehydration failed -- this is" >&2
    echo "[entrypoint] expected if there's no network access to freedomhouse.org" >&2
    echo "[entrypoint] right now. Continuing with the 54% baseline." >&2
    REHYDRATE_OK=0
fi

if ! uv run python src/ingestion/rehydrate.py --org accessnow; then
    echo "[entrypoint] WARNING: Access Now rehydration failed -- continuing" >&2
    echo "[entrypoint] with the 54% baseline." >&2
    REHYDRATE_OK=0
fi

if [ "$REHYDRATE_OK" = "1" ]; then
    echo "[entrypoint] rehydration succeeded for both orgs -- rebuilding the"
    echo "[entrypoint] index over the full, now-complete corpus..."
    uv run python src/retrieval/embed.py
    echo "[entrypoint] full-corpus index built. Serving 100% of the corpus."
else
    echo "[entrypoint] rehydration incomplete -- serving the build-time 54%" >&2
    echo "[entrypoint] baseline (OONI + CIPESA only) for this container's" >&2
    echo "[entrypoint] lifetime. Not retrying." >&2
fi

echo "[entrypoint] starting Streamlit..."
exec uv run streamlit run src/interface/app.py --server.address 0.0.0.0 --server.port 8501
