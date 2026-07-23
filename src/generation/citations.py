"""
citations.py -- turns the model's [n] markers into real, checkable
citations, and computes the sourcing footer describing what was
actually CITED (not what was retrieved).

Per ADR-0009: the LLM never writes a citation itself, only a numbered
reference to one of the excerpts it was given. Everything here is
mechanical: parse the markers, validate them against the real chunk
list, look up each cited chunk's document metadata, and render both a
Sources list and a factual sourcing footer (distinct orgs/docs/dates
among what was actually cited, never what was merely retrieved -- see
ADR-0009 for why that distinction is the whole point of this design).

Usage (as a library, not a script):
    from citations import parse_citations, render_sources, sourcing_footer
"""

import json
import re
from functools import lru_cache
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
METADATA_DIR = PROJECT_ROOT / "data" / "metadata"

MARKER_RE = re.compile(r"\[(\d+)\]")


@lru_cache(maxsize=None)
def _load_doc_metadata(doc_id: str) -> dict | None:
    """Reads data/metadata/{doc_id}.json's `declared` block -- title,
    url, organization, publication_date. Chunks themselves don't carry
    title/url (found by reading metadata.py directly during the
    2026-07-24 Fable consult, not assumed) -- this is the real lookup.
    Returns None if the metadata file is missing, so a broken lookup
    degrades one citation's rendering rather than crashing generation."""
    path = METADATA_DIR / f"{doc_id}.json"
    if not path.exists():
        return None
    with open(path, encoding="utf-8") as f:
        return json.load(f)["declared"]


def parse_citations(answer_text: str, chunks: list[dict]) -> dict:
    """Extracts every [n] marker from answer_text and validates it
    against the 1..len(chunks) range of excerpts actually given to the
    model.

    Returns:
        {
            "citations": [{"marker", "chunk_id", "doc_id", "pages"}, ...]
                -- one entry per distinct valid marker actually used,
                sorted by marker/excerpt number ascending (i.e.
                retrieval-rank order, not the order the model happened
                to write them in prose) -- deterministic and matches
                the numbering a reader sees in the excerpts themselves.
            "invalid_markers": [n, ...]
                -- markers outside the valid range; dropped from
                citations, kept here so a caller can log/investigate.
            "unsupported_paragraphs": [str, ...]
                -- non-empty paragraphs with no valid marker at all; a
                real signal a claim may be uncited, not proof of one.
        }
    """
    n_chunks = len(chunks)
    seen: dict[int, dict] = {}
    invalid: list[int] = []

    for match in MARKER_RE.finditer(answer_text):
        n = int(match.group(1))
        if not (1 <= n <= n_chunks):
            if n not in invalid:
                invalid.append(n)
            continue
        if n not in seen:
            chunk = chunks[n - 1]
            seen[n] = {
                "marker": n,
                "chunk_id": chunk["chunk_id"],
                "doc_id": chunk["doc_id"],
                "pages": chunk.get("pages"),
            }

    citations = [seen[n] for n in sorted(seen)]

    unsupported = [
        para.strip()
        for para in answer_text.split("\n\n")
        if para.strip() and not MARKER_RE.search(para)
    ]

    return {
        "citations": citations,
        "invalid_markers": invalid,
        "unsupported_paragraphs": unsupported,
    }


def render_sources(citations: list[dict]) -> str:
    """Renders a markdown Sources list from parse_citations()'s
    `citations` list, one line per citation in marker order, e.g.
    '[3] CIPESA, "State of Internet Freedom in Africa 2025"
    (2025-09-01), pp. 7-8. <url>'. A missing metadata lookup renders a
    degraded but honest line instead of crashing."""
    lines = []
    for c in citations:
        meta = _load_doc_metadata(c["doc_id"])
        if meta is None:
            lines.append(
                f"[{c['marker']}] {c['doc_id']} (metadata unavailable), "
                f"chunk {c['chunk_id']}."
            )
            continue
        pages = c.get("pages")
        page_str = ""
        if pages:
            page_str = f", p. {pages[0]}" if len(pages) == 1 else f", pp. {pages[0]}-{pages[-1]}"
        lines.append(
            f"[{c['marker']}] {meta['organization']}, \"{meta['title']}\" "
            f"({meta['publication_date']}){page_str}. {meta['url']}"
        )
    return "\n".join(lines)


def sourcing_footer(citations: list[dict]) -> dict:
    """Computes distinct orgs/docs/date-range over the CITED subset
    only -- never the retrieved-but-unused chunks (see ADR-0009 for why
    that distinction is the whole design). Returns the raw counts plus
    a rendered, factual (not binary-verdict) footer string."""
    if not citations:
        return {
            "distinct_orgs": 0,
            "distinct_docs": 0,
            "footer": "Sourcing: no citations were produced for this answer.",
        }

    docs_meta: dict[str, dict | None] = {}
    for c in citations:
        docs_meta.setdefault(c["doc_id"], _load_doc_metadata(c["doc_id"]))

    orgs = {m["organization"] for m in docs_meta.values() if m}
    dates = sorted({m["publication_date"][:4] for m in docs_meta.values() if m})
    distinct_docs = len(docs_meta)
    distinct_orgs = len(orgs)
    year_range = dates[0] if len(dates) <= 1 else f"{dates[0]}-{dates[-1]}"

    if distinct_docs == 1:
        only_org = next(iter(orgs), "an unknown organization")
        footer = (
            f"Sourcing: this answer cites a single document (from "
            f"{only_org}). No independent corroboration was found among "
            f"the retrieved evidence for this question."
        )
    elif distinct_orgs == 1:
        only_org = next(iter(orgs))
        footer = (
            f"Sourcing: all cited evidence comes from one organization "
            f"({only_org}), across {distinct_docs} reports ({year_range})."
        )
    else:
        footer = (
            f"Sourcing: this answer cites {distinct_docs} documents from "
            f"{distinct_orgs} organizations ({year_range})."
        )

    return {
        "distinct_orgs": distinct_orgs,
        "distinct_docs": distinct_docs,
        "footer": footer,
    }
