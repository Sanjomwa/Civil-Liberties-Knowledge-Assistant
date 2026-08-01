"""Priority 0 (docs/testing-design.md): the highest-value test in this
suite. ADR-0009's entire citation-integrity claim rests on
`prompts.build_user_prompt()`'s excerpt numbering and
`citations.parse_citations()`'s marker-to-chunk resolution agreeing on
the same scheme. A silent drift between the two (e.g. one goes 0-indexed,
or reorders chunks) would make answers look correctly cited while
actually pointing at the wrong document -- and nothing else in this
pipeline would catch it, since the citation-precision judge is only ever
handed whichever chunk the (possibly wrong) marker resolves to.

This test does NOT assume `prompts.py`'s numbering is `chunks[i-1]` --
it *extracts* the marker each chunk was actually rendered under from
`build_user_prompt()`'s real output, then confirms `parse_citations()`
resolves that same marker back to that same chunk. A change to either
function's numbering scheme, in isolation, fails this test.
"""

import re

from citations import parse_citations
from prompts import build_user_prompt

EXCERPT_BLOCK_RE = re.compile(
    r"\[(\d+)\] \(organization: [^)]*\)\n(.*?)(?=\n\n\[\d+\]|\Z)", re.DOTALL
)


def _fake_chunks(n: int) -> list[dict]:
    return [
        {
            "chunk_id": f"doc-{i}-chunk-0000",
            "doc_id": f"doc-{i}",
            "organization": "CIPESA",
            "text": f"UNIQUE_EXCERPT_TEXT_{i}",
            "pages": [i],
        }
        for i in range(1, n + 1)
    ]


def _marker_to_chunk_from_rendered_prompt(prompt_text: str, chunks: list[dict]) -> dict[int, dict]:
    """Independently derives {marker: chunk} from build_user_prompt()'s
    actual rendered output, matching each rendered excerpt's unique text
    back to the original chunk dict it came from -- not by assuming any
    particular indexing scheme."""
    text_to_chunk = {c["text"]: c for c in chunks}
    marker_to_chunk = {}
    for match in EXCERPT_BLOCK_RE.finditer(prompt_text):
        marker = int(match.group(1))
        rendered_text = match.group(2).strip()
        assert rendered_text in text_to_chunk, (
            f"prompt excerpt under marker [{marker}] doesn't match any "
            f"known fake chunk's text -- regex or fixture mismatch"
        )
        marker_to_chunk[marker] = text_to_chunk[rendered_text]
    return marker_to_chunk


def test_prompt_numbering_and_citation_parsing_agree_on_same_chunk():
    chunks = _fake_chunks(5)
    prompt = build_user_prompt("What tactics are used against dissent?", chunks)

    marker_to_chunk = _marker_to_chunk_from_rendered_prompt(prompt, chunks)
    assert set(marker_to_chunk) == {1, 2, 3, 4, 5}, (
        "expected exactly markers 1..5 rendered in the prompt"
    )

    # A synthetic model answer citing a subset of markers, deliberately
    # out of numeric order and with a repeated marker, the way a real
    # model answer would.
    answer_text = (
        f"First claim, supported by excerpt three [3].\n\n"
        f"Second claim, supported by excerpts one and five [1][5].\n\n"
        f"Third claim, also citing excerpt three again [3]."
    )

    parsed = parse_citations(answer_text, chunks)
    assert parsed["invalid_markers"] == []

    cited_by_marker = {c["marker"]: c for c in parsed["citations"]}
    assert set(cited_by_marker) == {1, 3, 5}

    for marker, citation in cited_by_marker.items():
        expected_chunk = marker_to_chunk[marker]
        assert citation["chunk_id"] == expected_chunk["chunk_id"], (
            f"marker [{marker}] was rendered in the prompt under chunk "
            f"{expected_chunk['chunk_id']!r}, but parse_citations() "
            f"resolved it to {citation['chunk_id']!r} instead -- the "
            f"numbering schemes have drifted apart"
        )
        assert citation["doc_id"] == expected_chunk["doc_id"]
        assert citation["pages"] == expected_chunk["pages"]
