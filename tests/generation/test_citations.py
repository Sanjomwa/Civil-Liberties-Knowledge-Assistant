"""Tier 1 (docs/testing-design.md): citations.py's marker extraction/
range validation and sourcing_footer()'s three branches. No real file
I/O -- metadata is injected via the `metadata_loader` parameter added
specifically to make this testable without `_load_doc_metadata`'s real
file read + lru_cache."""

from citations import parse_citations, sourcing_footer


def _chunks(n: int) -> list[dict]:
    return [
        {"chunk_id": f"doc-{i}-chunk-0000", "doc_id": f"doc-{i}", "pages": [i]}
        for i in range(1, n + 1)
    ]


# ---- parse_citations() ----------------------------------------------


def test_parse_citations_extracts_valid_markers_in_marker_order():
    chunks = _chunks(5)
    answer = "Claim A [3]. Claim B [1]. Claim C [3] again."
    parsed = parse_citations(answer, chunks)

    assert [c["marker"] for c in parsed["citations"]] == [1, 3]
    assert parsed["citations"][0]["chunk_id"] == "doc-1-chunk-0000"
    assert parsed["citations"][1]["chunk_id"] == "doc-3-chunk-0000"
    assert parsed["invalid_markers"] == []


def test_parse_citations_flags_out_of_range_marker_as_invalid():
    chunks = _chunks(5)
    answer = "Claim A [3]. Claim B [7], which doesn't exist."
    parsed = parse_citations(answer, chunks)

    assert parsed["invalid_markers"] == [7]
    assert [c["marker"] for c in parsed["citations"]] == [3]
    # an invalid marker must never appear as a resolved citation
    assert all(c["marker"] != 7 for c in parsed["citations"])


def test_parse_citations_deduplicates_invalid_markers():
    chunks = _chunks(5)
    answer = "First [9]. Second [9] again. Third [12]."
    parsed = parse_citations(answer, chunks)

    assert parsed["invalid_markers"] == [9, 12]


def test_parse_citations_flags_unsupported_paragraphs():
    chunks = _chunks(5)
    answer = "This paragraph has a citation [1].\n\nThis one has none at all."
    parsed = parse_citations(answer, chunks)

    assert parsed["unsupported_paragraphs"] == ["This one has none at all."]


def test_parse_citations_empty_chunks_makes_every_marker_invalid():
    answer = "A claim [1]."
    parsed = parse_citations(answer, [])

    assert parsed["citations"] == []
    assert parsed["invalid_markers"] == [1]


# ---- sourcing_footer() -------------------------------------------------


def _fake_loader(docs: dict[str, dict]):
    def loader(doc_id: str) -> dict | None:
        return docs.get(doc_id)
    return loader


def test_sourcing_footer_no_citations():
    footer = sourcing_footer([])
    assert footer["distinct_orgs"] == 0
    assert footer["distinct_docs"] == 0
    assert "no citations were produced" in footer["footer"]


def test_sourcing_footer_single_document_branch():
    citations = [{"marker": 1, "chunk_id": "c1", "doc_id": "doc-1", "pages": [1]}]
    loader = _fake_loader({
        "doc-1": {"organization": "OONI", "title": "T", "publication_date": "2024-01-01", "url": "u"},
    })

    footer = sourcing_footer(citations, metadata_loader=loader)

    assert footer["distinct_docs"] == 1
    assert footer["distinct_orgs"] == 1
    assert "cites a single document" in footer["footer"]
    assert "OONI" in footer["footer"]


def test_sourcing_footer_single_org_multi_doc_branch():
    citations = [
        {"marker": 1, "chunk_id": "c1", "doc_id": "doc-1", "pages": [1]},
        {"marker": 2, "chunk_id": "c2", "doc_id": "doc-2", "pages": [2]},
    ]
    loader = _fake_loader({
        "doc-1": {"organization": "CIPESA", "title": "T1", "publication_date": "2023-05-01", "url": "u1"},
        "doc-2": {"organization": "CIPESA", "title": "T2", "publication_date": "2025-09-01", "url": "u2"},
    })

    footer = sourcing_footer(citations, metadata_loader=loader)

    assert footer["distinct_docs"] == 2
    assert footer["distinct_orgs"] == 1
    assert "all cited evidence comes from one organization" in footer["footer"]
    assert "CIPESA" in footer["footer"]
    assert "2023-2025" in footer["footer"]


def test_sourcing_footer_multi_org_branch():
    citations = [
        {"marker": 1, "chunk_id": "c1", "doc_id": "doc-1", "pages": [1]},
        {"marker": 2, "chunk_id": "c2", "doc_id": "doc-2", "pages": [2]},
    ]
    loader = _fake_loader({
        "doc-1": {"organization": "OONI", "title": "T1", "publication_date": "2023-05-01", "url": "u1"},
        "doc-2": {"organization": "Access Now", "title": "T2", "publication_date": "2024-09-01", "url": "u2"},
    })

    footer = sourcing_footer(citations, metadata_loader=loader)

    assert footer["distinct_docs"] == 2
    assert footer["distinct_orgs"] == 2
    assert "cites 2 documents from 2 organizations" in footer["footer"]


def test_sourcing_footer_degrades_gracefully_when_no_cited_metadata_resolves():
    # Regression test for the real IndexError found during the prior
    # test-suite pass (reports.md, 2026-08-02): when every cited doc's
    # metadata fails to resolve, `dates` is empty, and the old
    # `dates[0] if len(dates) <= 1 else ...` line indexed into it anyway.
    citations = [
        {"marker": 1, "chunk_id": "c1", "doc_id": "doc-1", "pages": [1]},
        {"marker": 2, "chunk_id": "c2", "doc_id": "doc-2", "pages": [2]},
    ]
    loader = _fake_loader({})  # every doc_id resolves to None

    footer = sourcing_footer(citations, metadata_loader=loader)

    assert footer["distinct_docs"] == 2
    assert footer["distinct_orgs"] == 0
    # Must not crash, and must not invent a date range that doesn't exist.
    assert "2023" not in footer["footer"]
    assert footer["footer"]
