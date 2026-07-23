"""
search.py — one interface, three interchangeable backends.

`search(query, top_k, method)` is the single function every caller (ground
truth generation isn't a caller of this, but evaluate.py and, later, the
generation phase both are) should ever need. Per
`04-evaluation/project/project_evaluation_plan.md`'s explicit requirement,
evaluation code must be written generically against a `search_function`
parameter — swapping method="text"/"vector"/"hybrid" here must never
require touching evaluate.py, and doesn't: all three return the same shape.

Backends:
  - "text"   — TF-IDF keyword search over chunk text (minsearch.Index,
               built by embed.py).
  - "vector" — cosine similarity over BAAI/bge-small-en-v1.5 embeddings
               (minsearch.VectorSearch, built by embed.py). The query is
               embedded with the same model's `query_embed()` — using the
               dedicated query method (not `embed()`) matters even though
               this specific model's own card says prefixes aren't
               necessary, since it's the correct, forward-compatible call
               regardless of that detail.
  - "hybrid" — Reciprocal Rank Fusion (RRF) combining the text and vector
               rankings: score(chunk) = sum over rankers of 1/(k + rank).
               `k` is a real parameter, not a formality — Module 4's own
               homework (04-evaluation) found `k` moved which method won on
               a real corpus. Default here is provisional; evaluate.py's
               k-sweep is what should actually set it, not this default.

Index freshness (fix from the 2026-07-22 Opus design review): before any
search runs, the persisted `data/index/index_metadata.json` stamp is
checked against the corpus's current `corpus/CORPUS_VERSION`. A mismatch
is a hard failure — re-run `embed.py`. Without this check, a re-chunk that
isn't followed by a re-embed would silently return results scored against
stale, no-longer-current chunk content, with no error to signal it.

`lifecycle_status="active"` is the default filter on every search — closes
the "retrieval-time lifecycle.status filter not yet built" gap noted in
`docs/ingestion-design.md`. Pass `lifecycle_status=None` to disable it.

Usage (as a library, not a script):
    from search import search
    results = search("How does OONI detect Telegram blocking?", top_k=5, method="hybrid")
"""

import json
import sys
from functools import lru_cache
from pathlib import Path

from fastembed import TextEmbedding
from minsearch import Index, VectorSearch

PROJECT_ROOT = Path(__file__).resolve().parents[2]
INDEX_DIR = PROJECT_ROOT / "data" / "index"
CORPUS_VERSION_PATH = PROJECT_ROOT / "corpus" / "CORPUS_VERSION"
DEFAULT_METHOD_PATH = PROJECT_ROOT / "data" / "eval" / "default_method.json"

VECTOR_INDEX_PATH = INDEX_DIR / "vector_index.pkl"
TEXT_INDEX_PATH = INDEX_DIR / "text_index.pkl"
INDEX_METADATA_PATH = INDEX_DIR / "index_metadata.json"

# Fixed 2026-07-22 (Fable review, verified against this file directly): this
# used to be a hardcoded constant (60) that any caller not passing rrf_k
# explicitly would silently get -- while the actual measured, recorded
# decision (evaluate.py --set-default) is k=10, written to
# data/eval/default_method.json. On the multi_country slice the measured
# gap between k=10 and k=60 is ~9 points of Hit Rate -- a real, silent drift
# risk for any future generation-phase code calling search(query) plainly.
# Same class of bug as the corpus_version staleness checks elsewhere in this
# module: a derived artifact silently going stale relative to its source of
# truth. Fixed by reading the recorded decision at call time instead of
# duplicating it as a second, driftable constant. FALLBACK_RRF_K is only
# used pre-evaluation, before any default has ever been recorded.
FALLBACK_RRF_K = 60  # used only if default_method.json doesn't exist yet
HYBRID_CANDIDATE_POOL = 50  # depth pulled from each backend before RRF-combining

# Added 2026-07-22 (P2, Opus+Fable consult, 2026-07-22): both reviewing
# models independently converged on this as the fix for the multi_country
# slice's real, mechanistically-explained problem -- plain TF-IDF beats
# hybrid/vector there because entity-dense proper-noun matching (a query
# naming "Kenya" and "Uganda" together) is exactly where sparse exact-term
# matching has a real edge over dense embeddings. Every chunk already
# carries a `countries` metadata list (from corpus/sources/*.yaml via
# metadata.py) -- this was already present, just never used at query time.
# Explicitly a *boost*, not a filter, per both advisors' shared caution:
# a wrong or missed country detection must never drop a result, only
# reorder it, so the worst case of a false-positive/-negative detection is
# a no-op on ranking, not lost recall. Root country names are used as the
# keyword (not adjectival forms) because every adjectival form in this
# corpus's five countries contains its noun form as a literal substring
# ("kenyan" contains "kenya", "ugandan" contains "uganda", etc.), so one
# substring check catches both without a second keyword list to maintain.
COUNTRY_KEYWORDS = {
    "KE": "kenya",
    "UG": "uganda",
    "TZ": "tanzania",
    "ET": "ethiopia",
    "RW": "rwanda",
}


class StaleIndexError(RuntimeError):
    """Raised when data/index/ was built against a corpus_version that no
    longer matches corpus/CORPUS_VERSION — re-run embed.py."""


@lru_cache(maxsize=1)
def _recorded_default_rrf_k() -> int:
    """Reads the actual measured/recorded RRF k from
    data/eval/default_method.json if it exists, so hybrid search's default
    always matches the last decision made via `evaluate.py --set-default`,
    not a hand-maintained constant that can silently drift from it (see
    module-level comment on FALLBACK_RRF_K)."""
    if not DEFAULT_METHOD_PATH.exists():
        return FALLBACK_RRF_K
    with open(DEFAULT_METHOD_PATH, encoding="utf-8") as f:
        config = json.load(f)
    if config.get("method") != "hybrid":
        return FALLBACK_RRF_K
    return config.get("rrf_k", FALLBACK_RRF_K)


@lru_cache(maxsize=1)
def _load_index_metadata() -> dict:
    if not INDEX_METADATA_PATH.exists():
        raise StaleIndexError(
            f"No {INDEX_METADATA_PATH.relative_to(PROJECT_ROOT)} found — "
            f"run src/retrieval/embed.py first."
        )
    with open(INDEX_METADATA_PATH, encoding="utf-8") as f:
        return json.load(f)


def _check_index_freshness() -> None:
    metadata = _load_index_metadata()
    if not CORPUS_VERSION_PATH.exists():
        raise StaleIndexError(
            f"No {CORPUS_VERSION_PATH.relative_to(PROJECT_ROOT)} found — "
            f"cannot verify index freshness."
        )
    # Real format is "<version> <date-it-was-set>" (e.g. "v1.0 2026-07-13"),
    # not a bare version string -- same fix as embed.py/ground_truth.py,
    # found 2026-07-22 on the first real WSL run. Only the leading token
    # is compared, matching what embed.py stamps into index_metadata.json.
    current_version = CORPUS_VERSION_PATH.read_text(encoding="utf-8").strip().split()[0]
    indexed_version = metadata["corpus_version"]
    if current_version != indexed_version:
        raise StaleIndexError(
            f"data/index/ was built against corpus_version={indexed_version!r}, "
            f"but corpus/CORPUS_VERSION is now {current_version!r}. Re-run "
            f"src/retrieval/embed.py before searching — otherwise results "
            f"would silently be scored against stale chunk content."
        )


@lru_cache(maxsize=1)
def _get_embedding_model() -> TextEmbedding:
    metadata = _load_index_metadata()
    return TextEmbedding(model_name=metadata["embedding_model"])


@lru_cache(maxsize=1)
def _get_vector_index() -> VectorSearch:
    return VectorSearch.load(VECTOR_INDEX_PATH)


@lru_cache(maxsize=1)
def _get_text_index() -> Index:
    return Index.load(TEXT_INDEX_PATH)


def _filter_dict(lifecycle_status: str | None) -> dict:
    return {"lifecycle_status": lifecycle_status} if lifecycle_status else {}


def _text_search(query: str, top_k: int, lifecycle_status: str | None) -> list[dict]:
    return _get_text_index().search(
        query, filter_dict=_filter_dict(lifecycle_status), num_results=top_k
    )


def _vector_search(query: str, top_k: int, lifecycle_status: str | None) -> list[dict]:
    model = _get_embedding_model()
    query_vec = next(iter(model.query_embed([query])))
    return _get_vector_index().search(
        query_vec, filter_dict=_filter_dict(lifecycle_status), num_results=top_k
    )


def _rrf_combine(ranked_lists: list[list[dict]], k: int, top_k: int) -> list[dict]:
    """Reciprocal Rank Fusion: score(chunk) = sum over ranked_lists of
    1 / (k + rank), rank starting at 1. Returns the top_k chunks by
    combined score, each result carrying its own chunk dict (from
    whichever ranked list first produced it)."""
    scores: dict[str, float] = {}
    chunk_by_id: dict[str, dict] = {}
    for ranked in ranked_lists:
        for rank, chunk in enumerate(ranked, start=1):
            chunk_id = chunk["chunk_id"]
            chunk_by_id.setdefault(chunk_id, chunk)
            scores[chunk_id] = scores.get(chunk_id, 0.0) + 1.0 / (k + rank)

    ranked_ids = sorted(scores, key=lambda cid: scores[cid], reverse=True)
    return [chunk_by_id[cid] for cid in ranked_ids[:top_k]]


def _hybrid_search(
    query: str, top_k: int, lifecycle_status: str | None, rrf_k: int
) -> list[dict]:
    text_results = _text_search(query, HYBRID_CANDIDATE_POOL, lifecycle_status)
    vector_results = _vector_search(query, HYBRID_CANDIDATE_POOL, lifecycle_status)
    return _rrf_combine([text_results, vector_results], k=rrf_k, top_k=top_k)


def _detect_countries(query: str) -> set[str]:
    """Returns the set of ISO-2 codes (matching the `countries` metadata
    format) whose root country name appears anywhere in the query,
    case-insensitive. Deliberately simple substring matching -- see the
    module-level comment on COUNTRY_KEYWORDS for why adjectival forms
    don't need a second keyword list."""
    q = query.lower()
    return {code for code, keyword in COUNTRY_KEYWORDS.items() if keyword in q}


def _boost_by_country(results: list[dict], countries: set[str]) -> list[dict]:
    """Stable re-rank, never a filter: chunks whose own `countries`
    metadata overlaps the query's detected countries move to the front,
    keeping their relative order; every other chunk follows, also in its
    original relative order. If `countries` is empty (nothing detected)
    or no chunk in `results` matches, this is a no-op -- the boost can
    only ever help ranking, never drop a result."""
    if not countries:
        return results
    matching_ids = {
        r["chunk_id"] for r in results if countries & set(r.get("countries", []))
    }
    if not matching_ids:
        return results
    matching = [r for r in results if r["chunk_id"] in matching_ids]
    rest = [r for r in results if r["chunk_id"] not in matching_ids]
    return matching + rest


def search(
    query: str,
    top_k: int = 10,
    method: str = "hybrid",
    lifecycle_status: str | None = "active",
    rrf_k: int | None = None,
) -> list[dict]:
    """
    Args:
        query: the search query text.
        top_k: number of results to return.
        method: "text", "vector", or "hybrid".
        lifecycle_status: filter results to this lifecycle status
            (default "active"). Pass None to disable filtering.
        rrf_k: RRF k parameter, only used when method="hybrid". Defaults to
            None, which resolves to the actual recorded decision in
            data/eval/default_method.json (see _recorded_default_rrf_k) --
            explicitly pass a value to override it for one call, e.g. during
            evaluate.py's own k-sweep.

    Returns:
        list of chunk dicts (chunk_id, doc_id, text, pages, organization,
        countries, publication_date, lifecycle_status), ranked best-first.
        If the query names one of the five corpus countries (P2, see
        COUNTRY_KEYWORDS), chunks tagged with that country are boosted
        toward the front of the returned list -- a re-rank, not a filter,
        so results are never dropped by this step.
    """
    _check_index_freshness()

    detected_countries = _detect_countries(query)
    # Pull a deeper candidate pool than top_k whenever a boost might apply,
    # so there's actually something lower-ranked-but-country-matching for
    # _boost_by_country to promote -- boosting within an already-truncated
    # top_k would have nothing to work with. No-op (same as before P2)
    # when no country is detected.
    pool_k = max(top_k, HYBRID_CANDIDATE_POOL) if detected_countries else top_k

    if method == "text":
        results = _text_search(query, pool_k, lifecycle_status)
    elif method == "vector":
        results = _vector_search(query, pool_k, lifecycle_status)
    elif method == "hybrid":
        resolved_rrf_k = rrf_k if rrf_k is not None else _recorded_default_rrf_k()
        results = _hybrid_search(query, pool_k, lifecycle_status, resolved_rrf_k)
    else:
        raise ValueError(f"Unknown method {method!r} — expected 'text', 'vector', or 'hybrid'.")

    results = _boost_by_country(results, detected_countries)
    return results[:top_k]


def main() -> None:
    """Ad-hoc manual check: `uv run python src/retrieval/search.py <query>`."""
    if len(sys.argv) < 2:
        print("Usage: uv run python src/retrieval/search.py <query>", file=sys.stderr)
        sys.exit(1)
    query = " ".join(sys.argv[1:])
    for method in ("text", "vector", "hybrid"):
        print(f"\n=== {method} ===")
        for chunk in search(query, top_k=5, method=method):
            print(f"  {chunk['chunk_id']} — {chunk['text'][:100]!r}")


if __name__ == "__main__":
    main()
