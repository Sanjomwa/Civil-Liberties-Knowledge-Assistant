# Dockerfile -- app image, per docs/interface-design.md Decisions 6/8.
#
# Build-time always bakes the tiered public release (dist/corpus-release-v1.zip,
# ADR-0013: OONI+CIPESA full text, Freedom House/Access Now metadata+hash
# only) so `docker compose up` works unconditionally, even with no network
# access to the restricted orgs at build or run time. First-run
# rehydration (entrypoint.sh) upgrades a running container to 100% of the
# corpus by fetching Freedom House/Access Now's real text directly from
# their own servers -- never baked into this image or the public release
# artifact (see Decision 8's full reasoning).

FROM python:3.12-slim

WORKDIR /app

# curl: fetches the release archive. ca-certificates: TLS for that fetch
# and for rehydrate.py's own live requests to freedomhouse.org/accessnow.org.
# libgomp1: onnxruntime (fastembed's backend) needs OpenMP at runtime.
RUN apt-get update && apt-get install -y --no-install-recommends \
        curl ca-certificates libgomp1 \
    && rm -rf /var/lib/apt/lists/*

COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /usr/local/bin/

COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-dev

COPY . .

# Warm up fastembed's ONNX model download at build time, not on first
# query -- same model embed.py uses (BAAI/bge-small-en-v1.5).
RUN uv run python -c "from fastembed import TextEmbedding; TextEmbedding(model_name='BAAI/bge-small-en-v1.5')"

# Fetch + verify + unpack the tiered public release. Fails the build
# loudly on a checksum mismatch -- this is public corpus data feeding a
# RAG pipeline; a silent mismatch would be a correctness bug, not just
# an availability one.
ARG CORPUS_RELEASE_URL=https://github.com/Sanjomwa/Civil-Liberties-Knowledge-Assistant/releases/download/corpus-v1/corpus-release-v1.zip
ARG CORPUS_RELEASE_SHA256=7f658d70c8036394173c11d89dd6015e64365b2bd873ed475df77ecdb1641ed5
RUN curl -fsSL -o /tmp/corpus-release-v1.zip "$CORPUS_RELEASE_URL" \
    && echo "$CORPUS_RELEASE_SHA256  /tmp/corpus-release-v1.zip" | sha256sum -c - \
    && uv run python scripts/unpack_release.py /tmp/corpus-release-v1.zip \
    && rm /tmp/corpus-release-v1.zip

# Build the retrieval index over the baseline (OONI+CIPESA, ~54% of the
# corpus). entrypoint.sh rebuilds this at first-run if rehydration
# reaches Freedom House/Access Now too.
RUN uv run python src/retrieval/embed.py

RUN chmod +x src/interface/entrypoint.sh

EXPOSE 8501

ENTRYPOINT ["src/interface/entrypoint.sh"]
