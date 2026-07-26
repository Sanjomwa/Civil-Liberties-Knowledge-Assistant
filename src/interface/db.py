"""
db.py -- Postgres persistence for one interaction per real query, plus
feedback recording. Plain SQL via psycopg (v3), no ORM -- matches this
project's one-file-one-responsibility, no-unnecessary-abstraction style
(same discipline as citations.py/judge.py's plain-function design).

Schema is copied verbatim from docs/interface-design.md Decision 4 -- not
redesigned. `CREATE TABLE IF NOT EXISTS` only, run once at app startup;
never DROP/--force (this project's own 05-monitoring/notes/
03_common_pitfalls.md #5 names an unguarded `init_db(drop=True)` as
exactly the mistake to avoid).

Usage (as a library, not a script):
    from db import get_conn, init_db, insert_interaction, record_feedback
"""

import os
from contextlib import contextmanager

import psycopg
from dotenv import load_dotenv

load_dotenv()

DATABASE_URL = os.environ.get(
    "DATABASE_URL", "postgresql://postgres:postgres@localhost:5432/interactions"
)

# Schema verbatim from docs/interface-design.md Decision 4 -- do not
# redesign; any real change to this table needs its own ADR, same
# discipline as every other closed-phase schema change in this project.
SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS interactions (
    id                        BIGSERIAL PRIMARY KEY,
    ts                        TIMESTAMPTZ NOT NULL DEFAULT now(),
    query                     TEXT NOT NULL,
    answer_markdown           TEXT NOT NULL,
    latency_ms                INTEGER,
    retrieval_ms              INTEGER,
    llm_ms                    INTEGER,
    prompt_tokens             INTEGER,
    completion_tokens         INTEGER,
    total_tokens              INTEGER,
    model                     TEXT,
    est_cost_usd              NUMERIC(10, 6),
    retrieval_method          TEXT,
    top_k                     INTEGER,
    n_chunks                  INTEGER,
    retrieval_scores          JSONB,
    citations_summary         JSONB,
    source_orgs               TEXT[],
    citation_count            INTEGER,
    sourcing_status           TEXT,
    distinct_org_count        INTEGER,
    distinct_doc_count        INTEGER,
    invalid_marker_count      INTEGER,
    unsupported_paragraph_count INTEGER,
    feedback                  SMALLINT,
    feedback_at               TIMESTAMPTZ
);
"""

# Explicit per-model $-per-1k-token rate table. Raises on an unknown
# model rather than silently writing 0/None -- this project's own
# 05-monitoring/notes/03_common_pitfalls.md #2 names silent zero-cost for
# an unrecognized model as exactly the failure mode to not repeat.
# Rates below are this project's own recorded placeholder estimate (not
# pulled from a live pricing API) -- update here if real billing rates
# for this account ever differ; the point of raising on an unknown model
# is to force that update to happen deliberately, not silently drift.
MODEL_RATES_PER_1K = {
    "gpt-5.4-mini": {"prompt": 0.00025, "completion": 0.00100},
    "gpt-5.4": {"prompt": 0.00250, "completion": 0.01000},
}


class UnknownModelError(ValueError):
    """Raised by est_cost_usd() when a model has no entry in
    MODEL_RATES_PER_1K -- deliberately fatal, not a silent $0 estimate."""


def est_cost_usd(model: str, prompt_tokens: int, completion_tokens: int) -> float:
    if model not in MODEL_RATES_PER_1K:
        raise UnknownModelError(
            f"No rate entry for model {model!r} in MODEL_RATES_PER_1K -- "
            f"add one explicitly before recording cost for this model. "
            f"Known models: {sorted(MODEL_RATES_PER_1K)}"
        )
    rates = MODEL_RATES_PER_1K[model]
    return (prompt_tokens / 1000) * rates["prompt"] + (completion_tokens / 1000) * rates["completion"]


@contextmanager
def get_conn():
    conn = psycopg.connect(DATABASE_URL)
    try:
        yield conn
    finally:
        conn.close()


def init_db() -> None:
    """Idempotent schema creation -- safe to call on every app startup.
    Never drops or truncates anything."""
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(SCHEMA_SQL)
        conn.commit()


def insert_interaction(
    *,
    query: str,
    answer_markdown: str,
    latency_ms: int | None = None,
    retrieval_ms: int | None = None,
    llm_ms: int | None = None,
    prompt_tokens: int | None = None,
    completion_tokens: int | None = None,
    total_tokens: int | None = None,
    model: str | None = None,
    est_cost_usd: float | None = None,
    retrieval_method: str | None = None,
    top_k: int | None = None,
    n_chunks: int | None = None,
    retrieval_scores: list[float] | None = None,
    citations_summary: list[dict] | None = None,
    source_orgs: list[str] | None = None,
    citation_count: int | None = None,
    sourcing_status: str | None = None,
    distinct_org_count: int | None = None,
    distinct_doc_count: int | None = None,
    invalid_marker_count: int | None = None,
    unsupported_paragraph_count: int | None = None,
) -> int:
    """Inserts one row for one real query. Returns the new row's id so
    the caller (the Streamlit app) can attach a later feedback vote to
    this exact interaction via record_feedback()."""
    import json

    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO interactions (
                    query, answer_markdown, latency_ms, retrieval_ms, llm_ms,
                    prompt_tokens, completion_tokens, total_tokens, model, est_cost_usd,
                    retrieval_method, top_k, n_chunks, retrieval_scores, citations_summary,
                    source_orgs, citation_count, sourcing_status, distinct_org_count,
                    distinct_doc_count, invalid_marker_count, unsupported_paragraph_count
                ) VALUES (
                    %s, %s, %s, %s, %s,
                    %s, %s, %s, %s, %s,
                    %s, %s, %s, %s, %s,
                    %s, %s, %s, %s,
                    %s, %s, %s
                )
                RETURNING id
                """,
                (
                    query, answer_markdown, latency_ms, retrieval_ms, llm_ms,
                    prompt_tokens, completion_tokens, total_tokens, model, est_cost_usd,
                    retrieval_method, top_k, n_chunks,
                    json.dumps(retrieval_scores) if retrieval_scores is not None else None,
                    json.dumps(citations_summary) if citations_summary is not None else None,
                    source_orgs, citation_count, sourcing_status, distinct_org_count,
                    distinct_doc_count, invalid_marker_count, unsupported_paragraph_count,
                ),
            )
            new_id = cur.fetchone()[0]
        conn.commit()
    return new_id


def record_feedback(interaction_id: int, value: int) -> None:
    """UPDATE, not an insert -- exactly one feedback verdict per answer,
    per docs/interface-design.md Decision 4. value is +1 (thumbs up) or
    -1 (thumbs down)."""
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "UPDATE interactions SET feedback = %s, feedback_at = now() WHERE id = %s",
                (value, interaction_id),
            )
        conn.commit()
