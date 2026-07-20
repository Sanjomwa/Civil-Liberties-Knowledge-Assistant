"""
pages.py — shared page-breakpoint format and resolution logic (ADR-0008).

The single place the page-breakpoint format is defined, and the only
place page-range resolution logic lives. Imported by extract.py (to
write a document's data/processed/{org}/{doc_id}.pages.json sidecar
during PDF extraction) and chunk.py (to read that sidecar and resolve
each chunk's page range). Centralizing this matters specifically because
format drift between a writer and a reader of the same sidecar file
would silently corrupt citations without either side raising an error —
exactly the class of bug ADR-0007/ADR-0008 exist to prevent.

Breakpoint format: a list of dicts, one per PDF page that actually
contributed extractable text (pages with no extractable text are never
included — see extract.py's extract_pdf_text()), each:
    {"page": N, "char_start": X, "char_end": Y}
- "page" is the page's TRUE position in the source PDF (pdfplumber's own
  1-indexed page.page_number), not a sequential count of included pages
  — this is what keeps citations accurate even when earlier pages were
  skipped for having no extractable text.
- [char_start, char_end) is a half-open interval over the page's own
  real extracted characters in the final joined text, deliberately
  excluding the "\\n\\n" joiner between pages — the joiner belongs to no
  page.

Usage:
    from pages import resolve_page_range
"""

import json
from pathlib import Path


def pages_sidecar_path(processed_dir: Path, org: str, doc_id: str) -> Path:
    return processed_dir / org / f"{doc_id}.pages.json"


def write_pages_sidecar(path: Path, breakpoints: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(breakpoints, f, indent=2)
        f.write("\n")


def load_pages_sidecar(path: Path) -> list[dict] | None:
    """Returns None (not an empty list) if no sidecar exists — the
    caller's signal that this document has no page data (non-PDF
    source, or extracted before ADR-0008 landed and not yet
    re-extracted), distinct from a PDF that genuinely produced zero
    breakpoints (which shouldn't happen for a document that passed
    extraction, but isn't this function's job to judge)."""
    if not path.exists():
        return None
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def resolve_page_range(breakpoints: list[dict] | None, char_start: int, char_end: int) -> list[int] | None:
    """Given a chunk's [char_start, char_end) range in the joined
    extracted text, return the sorted, deduplicated list of true PDF
    page numbers it overlaps — resolved against each page's own real
    character range, never the inter-page joiner gap — or None if
    breakpoints is None/empty (non-PDF source, or no page data
    available for this document)."""
    if not breakpoints:
        return None
    overlapping = sorted({
        bp["page"] for bp in breakpoints
        if bp["char_start"] < char_end and bp["char_end"] > char_start
    })
    return overlapping or None
