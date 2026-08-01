"""Tier 1 (docs/testing-design.md): search.py's RRF fusion math and the
_boost_by_country re-rank -- confirmed pure functions over in-memory
lists of dicts. Neither touches _load_index_metadata() (the
lru_cache/file-read function in this module), so no injectable-loader
fix is needed for this scope, unlike citations.py."""

import pytest

from search import _boost_by_country, _rrf_combine


# ---- _rrf_combine() ------------------------------------------------


def test_rrf_combine_computes_reciprocal_rank_fusion_score():
    list1 = [{"chunk_id": "a"}, {"chunk_id": "b"}, {"chunk_id": "c"}]
    list2 = [{"chunk_id": "c"}, {"chunk_id": "a"}]
    k = 10

    result = _rrf_combine([list1, list2], k=k, top_k=10)
    scores = {r["chunk_id"]: r["score"] for r in result}

    assert scores["a"] == pytest.approx(1 / (k + 1) + 1 / (k + 2))
    assert scores["b"] == pytest.approx(1 / (k + 2))
    assert scores["c"] == pytest.approx(1 / (k + 3) + 1 / (k + 1))

    ids_in_order = [r["chunk_id"] for r in result]
    assert ids_in_order == sorted(scores, key=lambda cid: scores[cid], reverse=True)


def test_rrf_combine_respects_top_k():
    list1 = [{"chunk_id": str(i)} for i in range(5)]
    result = _rrf_combine([list1], k=10, top_k=2)
    assert len(result) == 2


def test_rrf_combine_uses_first_seen_chunk_dict_for_duplicate_ids():
    list1 = [{"chunk_id": "x", "text": "from list1"}]
    list2 = [{"chunk_id": "x", "text": "from list2"}]
    result = _rrf_combine([list1, list2], k=10, top_k=10)
    assert result[0]["text"] == "from list1"


def test_rrf_combine_empty_lists_produces_no_results():
    assert _rrf_combine([[], []], k=10, top_k=5) == []


# ---- _boost_by_country() -------------------------------------------


def test_boost_by_country_moves_matching_chunks_to_front_preserving_relative_order():
    results = [
        {"chunk_id": "1", "countries": ["TZ"]},
        {"chunk_id": "2", "countries": ["KE"]},
        {"chunk_id": "3", "countries": ["KE", "UG"]},
        {"chunk_id": "4", "countries": ["RW"]},
    ]
    boosted = _boost_by_country(results, {"KE"})
    assert [r["chunk_id"] for r in boosted] == ["2", "3", "1", "4"]


def test_boost_by_country_is_noop_when_no_countries_detected():
    results = [{"chunk_id": "1", "countries": ["KE"]}]
    assert _boost_by_country(results, set()) is results


def test_boost_by_country_is_noop_when_no_result_matches():
    results = [{"chunk_id": "1", "countries": ["TZ"]}, {"chunk_id": "2", "countries": ["RW"]}]
    boosted = _boost_by_country(results, {"KE"})
    assert boosted == results


def test_boost_by_country_never_drops_a_result():
    results = [{"chunk_id": str(i), "countries": []} for i in range(5)]
    boosted = _boost_by_country(results, {"KE"})
    assert {r["chunk_id"] for r in boosted} == {r["chunk_id"] for r in results}
    assert len(boosted) == len(results)


def test_boost_by_country_handles_missing_countries_key():
    results = [{"chunk_id": "1"}, {"chunk_id": "2", "countries": ["KE"]}]
    boosted = _boost_by_country(results, {"KE"})
    assert [r["chunk_id"] for r in boosted] == ["2", "1"]
