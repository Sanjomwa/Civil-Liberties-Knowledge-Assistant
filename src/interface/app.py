"""
app.py -- single-page Streamlit interface, per docs/interface-design.md
Decision 3. Answers real questions via the existing, unchanged answer(),
records one row per real query to Postgres (db.py), and captures
thumbs up/down feedback.

Explicitly excluded, per Decision 3: chat history, multi-turn
conversation, a user-facing retrieval-method selector.

Usage:
    uv run streamlit run src/interface/app.py
"""

import sys
import time
from pathlib import Path

import streamlit as st

PROJECT_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(PROJECT_ROOT / "src"))
sys.path.insert(0, str(PROJECT_ROOT / "src" / "generation"))
sys.path.insert(0, str(PROJECT_ROOT / "src" / "interface"))

from generate import LLM_MODEL, TOP_K, answer  # noqa: E402
from retrieval.search import search  # noqa: E402

# citations.py's per-doc metadata lookup is private (_load_doc_metadata),
# but there's no public per-citation org accessor -- render_sources() and
# sourcing_footer() both use this same private function internally for
# the identical lookup. Per interface-design.md Decision 4a #3: use it
# directly rather than duplicating the metadata-file-reading logic here.
from citations import _load_doc_metadata  # noqa: E402

from db import est_cost_usd, init_db, insert_interaction, record_feedback  # noqa: E402

# Decision 9: cheap insurance against an open wallet against a real API
# key, added now rather than as a Tier 3 retrofit.
MAX_QUERIES_PER_SESSION = 20
MAX_CHARS = 500

EXAMPLE_QUESTIONS = [
    "How does OONI determine whether access to X is being blocked when "
    "analyzing web connectivity measurements?",
    "What kinds of barriers make it difficult for different internet or "
    "telecom providers to operate in Ethiopia?",
    "Which of the study countries had the highest purchasing-power-adjusted "
    "income in 2025?",
    "What outside actors were linked to a harassment effort targeting "
    "critics of the Rwandan government living abroad?",
]


@st.cache_resource
def _load_search_resources() -> bool:
    """Forces the embedding model + both indexes to load once and stay
    cached for the lifetime of this Streamlit process/session -- a plain
    lru_cache inside search.py's own module doesn't survive Streamlit's
    script-rerun model the same explicit way st.cache_resource does
    (interface-design.md Decision 3's first non-negotiable). Checked
    search.py's real load path directly (_get_embedding_model/
    _get_vector_index/_get_text_index, all module-private) rather than
    guessing what needed caching."""
    from retrieval.search import (  # noqa: E402
        _check_index_freshness,
        _get_embedding_model,
        _get_text_index,
        _get_vector_index,
    )

    _check_index_freshness()
    _get_embedding_model()
    _get_vector_index()
    _get_text_index()
    return True


def _sourcing_status(sourcing: dict) -> str:
    if sourcing["distinct_docs"] == 0:
        return "none"
    if sourcing["distinct_docs"] == 1:
        return "thin"
    if sourcing["distinct_orgs"] == 1:
        return "single_org"
    return "broad"


def _build_citations_summary(citations: list[dict], retrieved_chunks: list[dict]) -> list[dict]:
    """Joins parse_citations()'s {marker, chunk_id, doc_id, pages} against
    answer()'s new retrieved_chunks field (chunk_id -> score) for the
    score, and citations.py's own metadata lookup for org -- composition
    at the interface layer, not a change to citations.py's contract
    (interface-design.md Decision 4a #3). Never includes excerpt text."""
    score_by_chunk_id = {c["chunk_id"]: c["score"] for c in retrieved_chunks}
    summary = []
    for c in citations:
        meta = _load_doc_metadata(c["doc_id"])
        org = meta["organization"] if meta else None
        summary.append({
            "marker": c["marker"],
            "doc_id": c["doc_id"],
            "org": org,
            "score": score_by_chunk_id.get(c["chunk_id"]),
        })
    return summary


def _run_query(query: str) -> None:
    """Runs answer() once, persists one interactions row, and stashes
    everything the render step needs in session_state -- a thumbs click
    later must never re-trigger this function."""
    result = answer(query)

    # Independent second search() call, same pattern run_answers.py
    # already uses, purely for the on-screen "retrieved excerpts +
    # scores" expander -- the interactions table itself never stores
    # excerpt text (Decision 4), only this UI-only display does. Uses
    # result["rewritten_query"] (ADR-0017), not the raw `query` --
    # answer() itself now searches with the rewritten query internally,
    # so reconstructing with the raw query here would risk a different
    # top-10 set than the one the citations in the answer actually came
    # from, silently mismatching the displayed excerpts.
    display_chunks = search(result["rewritten_query"], top_k=TOP_K)

    total_tokens = result["usage"]["total_tokens"] if result["usage"] else None
    prompt_tokens = result["usage"]["prompt_tokens"] if result["usage"] else None
    completion_tokens = result["usage"]["completion_tokens"] if result["usage"] else None
    cost = None
    if result["usage"] is not None:
        cost = est_cost_usd(LLM_MODEL, prompt_tokens, completion_tokens)

    retrieval_scores = [c["score"] for c in result["retrieved_chunks"] if c["score"] is not None]
    citations_summary = _build_citations_summary(result["citations"], result["retrieved_chunks"])
    sourcing_status = _sourcing_status(result["sourcing"])
    source_orgs = sorted({c["org"] for c in citations_summary if c["org"]})

    latency_ms = result["timings"]["retrieval_ms"] + result["timings"]["llm_ms"]

    interaction_id = insert_interaction(
        query=query,
        rewritten_query=result["rewritten_query"],
        answer_markdown=result["answer_markdown"],
        latency_ms=latency_ms,
        retrieval_ms=result["timings"]["retrieval_ms"],
        llm_ms=result["timings"]["llm_ms"],
        prompt_tokens=prompt_tokens,
        completion_tokens=completion_tokens,
        total_tokens=total_tokens,
        model=LLM_MODEL,
        est_cost_usd=cost,
        retrieval_method="hybrid",
        top_k=TOP_K,
        n_chunks=len(result["retrieved_chunks"]),
        retrieval_scores=retrieval_scores,
        citations_summary=citations_summary,
        source_orgs=source_orgs,
        citation_count=len(result["citations"]),
        sourcing_status=sourcing_status,
        distinct_org_count=result["sourcing"]["distinct_orgs"],
        distinct_doc_count=result["sourcing"]["distinct_docs"],
        invalid_marker_count=len(result["invalid_markers"]),
        unsupported_paragraph_count=len(result["unsupported_paragraphs"]),
    )

    st.session_state.last_result = result
    st.session_state.last_display_chunks = display_chunks
    st.session_state.last_interaction_id = interaction_id
    st.session_state.last_cost = cost
    st.session_state.last_sourcing_status = sourcing_status
    st.session_state.voted = False
    st.session_state.query_count += 1


def _render_result() -> None:
    result = st.session_state.last_result
    sourcing_status = st.session_state.last_sourcing_status

    st.markdown(result["answer_markdown"])

    footer_text = result["sourcing"]["footer"]
    if sourcing_status in ("thin", "none"):
        st.warning(footer_text)
    else:
        st.info(footer_text)

    if result["sources"]:
        st.markdown("**Sources**")
        st.text(result["sources"])

    with st.expander("Retrieved excerpts + scores"):
        for i, chunk in enumerate(st.session_state.last_display_chunks, start=1):
            st.markdown(f"**[{i}] {chunk.get('organization', 'unknown org')}** "
                        f"(score: {chunk.get('score', 0):.4f})")
            st.text(chunk["text"][:1000])

    col1, col2, _ = st.columns([1, 1, 6])
    with col1:
        if st.button("👍", key=f"up-{st.session_state.last_interaction_id}",
                      disabled=st.session_state.voted):
            record_feedback(st.session_state.last_interaction_id, 1)
            st.session_state.voted = True
            st.rerun()
    with col2:
        if st.button("👎", key=f"down-{st.session_state.last_interaction_id}",
                      disabled=st.session_state.voted):
            record_feedback(st.session_state.last_interaction_id, -1)
            st.session_state.voted = True
            st.rerun()
    if st.session_state.voted:
        st.caption("Thanks for the feedback.")

    timings = result["timings"]
    usage_str = ""
    if result["usage"]:
        usage_str = f", {result['usage']['total_tokens']} tokens"
        if st.session_state.last_cost is not None:
            usage_str += f", est. ${st.session_state.last_cost:.5f}"
    st.caption(
        f"Model: {LLM_MODEL} · Retrieval: {timings['retrieval_ms']}ms · "
        f"LLM: {timings['llm_ms']}ms{usage_str}"
    )


def main() -> None:
    st.set_page_config(page_title="Civil Liberties Knowledge Assistant", page_icon="🌍")
    init_db()
    _load_search_resources()

    if "query_count" not in st.session_state:
        st.session_state.query_count = 0
    if "last_result" not in st.session_state:
        st.session_state.last_result = None
    if "voted" not in st.session_state:
        st.session_state.voted = False

    st.title("Civil Liberties Knowledge Assistant")
    st.caption(
        "Scope: OONI, Access Now, CIPESA, and Freedom House reports on internet "
        "censorship and digital rights in Kenya, Uganda, Tanzania, Ethiopia, and "
        "Rwanda, 2022–2026. Every answer cites the specific excerpt it draws from."
    )

    st.markdown("**Try an example question:**")
    cols = st.columns(len(EXAMPLE_QUESTIONS))
    example_clicked = None
    for i, (col, q) in enumerate(zip(cols, EXAMPLE_QUESTIONS)):
        with col:
            if st.button(q[:60] + ("…" if len(q) > 60 else ""), key=f"example-{i}"):
                example_clicked = q

    query = st.text_input(
        "Ask a question:",
        value=example_clicked or "",
        max_chars=MAX_CHARS,
        key="query_input",
    )

    at_limit = st.session_state.query_count >= MAX_QUERIES_PER_SESSION
    if at_limit:
        st.error(
            f"This session has reached its limit of {MAX_QUERIES_PER_SESSION} "
            f"questions. Refresh the page to start a new session."
        )

    submit = st.button("Ask", disabled=at_limit)

    if (submit or example_clicked) and query and not at_limit:
        with st.spinner("Searching the corpus and generating an answer…"):
            _run_query(query)

    if st.session_state.last_result is not None:
        _render_result()

    st.caption(f"Queries this session: {st.session_state.query_count}/{MAX_QUERIES_PER_SESSION}")


if __name__ == "__main__":
    main()
