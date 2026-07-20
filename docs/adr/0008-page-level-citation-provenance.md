# ADR-0008: Page-Level Provenance for PDF-Sourced Chunks

**Status:** Accepted, 2026-07-20.

## Context

The architecture's core acceptance principle, stated since the frozen
v1.0 design and never contested: every answer must cite sources. A
citation that can't be checked against the real, page-numbered source
document doesn't actually satisfy that principle, no matter how
correctly the retrieval and generation layers eventually cite a chunk —
if the chunk itself carries no page reference, there's nothing more
specific to cite than "somewhere in this PDF."

`extract_pdf_text()` (`extract.py`), as built, discards this information
completely:

```python
def extract_pdf_text(path: Path) -> str:
    pages = []
    with pdfplumber.open(path) as pdf:
        for page in pdf.pages:
            text = page.extract_text()
            if text:
                pages.append(text)
    return "\n\n".join(pages).strip()
```

The joined string has no memory of which page contributed which
characters. `chunk.py` then chunks this flat text using only character
offsets (`char_start`, `char_end` within the joined string) — a chunk
can be traced back to a byte range in an internal representation, but
not to anything a human checking a citation against the real PDF could
use.

A second, subtler correctness issue compounds this: pages with no
extractable text are silently skipped (the `if text:` check — a common
outcome for a title page, a mostly-image page, or a blank separator
page). This means the Nth page of *output* is not necessarily the Nth
page of the *real PDF* — a naive fix that just counted output pages
sequentially would produce citations that are confidently wrong, not
just imprecise.

This finding was independently surfaced by both models in the
end-of-ingestion-phase review (`decisionlog.md`, 2026-07-20) as the
single most mission-relevant gap identified — the one place where the
pipeline under-delivers relative to what the project's own architecture
already claims to guarantee, not merely an internal consistency issue
(contrast ADR-0007's four findings, which are real but don't touch the
citation guarantee itself).

An Opus consult was run before finalizing this decision (combined with
ADR-0007's consult — see that ADR for the shared transcript).

## Decision

### Mechanism

`extract_pdf_text()` is changed to also produce a page-breakpoint list
alongside the joined text, tracking each *included* page's **true PDF
page number** (`pdfplumber`'s own `page.page_number`, 1-indexed — this
is what defeats the skipped-page off-by-one, since it reflects the
real document regardless of which earlier pages were skipped) paired
with that page's exact character range in the joined output:

```python
def extract_pdf_text(path: Path) -> tuple[str, list[dict]]:
    pages = []
    breakpoints = []
    offset = 0
    with pdfplumber.open(path) as pdf:
        for page in pdf.pages:
            text = page.extract_text()
            if text:
                pages.append(text)
                breakpoints.append({
                    "page": page.page_number,
                    "char_start": offset,
                    "char_end": offset + len(text),
                })
                offset += len(text) + 2  # the "\n\n" joiner added below
    return "\n\n".join(pages).strip(), breakpoints
```

`char_end` for each page is computed *before* adding the 2-character
joiner offset, so each page's recorded range covers only its own real
extracted content — the joiner gap between pages belongs to no page,
by design, not a rounding error to paper over.

### Storage: a sidecar file, not an inline marker

Breakpoints are written to `data/processed/{org}/{doc_id}.pages.json` —
a plain JSON array of `{"page": N, "char_start": X, "char_end": Y}`
objects — alongside the existing `.txt` file. **Only for PDF-sourced
documents.** HTML and JSON sources have no page concept; no sidecar is
written for them, and the chunk-level `pages` field (below) stays `null`.

Rejected: encoding page boundaries as an inline delimiter token within
the extracted text itself. An inline marker would contaminate the exact
text that later gets embedded and chunked — polluting both the human-
readable extracted text and, eventually, embedding vectors, for the
sake of information that belongs in metadata, not content. A sidecar
file keeps the extracted text clean and the provenance data separately
addressable.

### Shared resolution logic: `src/ingestion/pages.py`

A new small module, `pages.py`, is the single place the breakpoint
format is defined and the only place page-range resolution logic lives
— imported by both `extract.py` (to write the sidecar) and `chunk.py`
(to read it and resolve each chunk's page range). Centralizing this
matters specifically because format drift between a writer and a reader
of the same sidecar file would silently corrupt citations without
either side raising an error — exactly the class of bug this whole
review pass exists to prevent.

```python
def resolve_page_range(breakpoints: list[dict], char_start: int, char_end: int) -> list[int] | None:
    """Given a chunk's [char_start, char_end) range in the joined text,
    return the sorted, deduplicated list of true PDF page numbers it
    overlaps -- resolved against each page's own real character range
    (never the inter-page joiner gap), or None if breakpoints is empty
    (non-PDF source, or a PDF with no page data available)."""
    if not breakpoints:
        return None
    pages = sorted({
        bp["page"] for bp in breakpoints
        if bp["char_start"] < char_end and bp["char_end"] > char_start
    })
    return pages or None
```

Standard half-open-interval overlap test (`bp.char_start < chunk.char_end
and bp.char_end > chunk.char_start`), which correctly handles a chunk
that spans a page boundary (returns multiple page numbers) without
ever crediting a match to the joiner gap between pages, since that gap
falls outside every page's own `[char_start, char_end)`.

### Chunk record change

`chunk.py`'s `chunk_document()` loads the sidecar (if present) once per
document, and for each chunk calls `resolve_page_range()`, storing the
result under a new `"pages"` key in the chunk JSON record — e.g.
`"pages": [7]` or `"pages": [7, 8]` for a chunk spanning a page break,
or `"pages": null` for a non-PDF-sourced document. This is a pure
addition to the existing chunk schema — no existing field changes
meaning, and chunk *counts* are unaffected (this ADR changes what each
chunk knows about itself, not how many chunks a document produces).

## Consequences

- New artifact: `data/processed/{org}/{doc_id}.pages.json`, one per
  PDF-sourced document.
- New module: `src/ingestion/pages.py`.
- Chunk JSON schema gains one field (`"pages"`), additive, backward-
  compatible with a `null` default for non-PDF sources.
- Every PDF-sourced document already in the corpus needs re-extraction
  (to generate the sidecar) and re-chunking (to populate the new
  field) — HTML/JSON-sourced documents are unaffected and don't need
  reprocessing. This is a full pipeline re-run for the PDF-sourced
  subset of the existing 35-document corpus, not a schema migration
  applied in place; tracked as the immediate next execution step after
  this ADR and ADR-0007 both land in code.
- Retrieval and generation (later modules, not built yet) should surface
  the `pages` field in any citation they construct — noted here as a
  forward requirement, the same way ADR-0001 noted a forward
  requirement on the eventual generation layer, not built by this ADR
  itself.
- Architecture document version increments v1.7 → v1.8 (this ADR is
  sequenced after ADR-0007 in the same work session).

## Opus consult

Consulted 2026-07-20 (combined transcript with ADR-0007 — see that
ADR). Confirmed the true-`page_number`-over-sequential-output-index
choice correctly defeats the skipped-blank-page citation-accuracy trap.
Recommended sidecar over inline delimiter, for exactly the
content-contamination reason stated above — adopted directly. Recommended
a shared resolution utility rather than duplicating breakpoint-format
knowledge in both extract.py and chunk.py — adopted directly as
`pages.py`. Specifically flagged the inter-page joiner as a correctness
trap worth naming explicitly (half-open intervals resolved against real
per-page character ranges, not the 2-character gap) — incorporated into
`resolve_page_range()`'s design and docstring above. Assessed the overall
design as proportional, not overbuilt, for a project whose stated core
acceptance principle is citation-grounded answers — "the minimum to
honor 'every answer must cite sources,'" not a larger provenance system
than the mission calls for.

## What would trigger a revisit

- If a future PDF source turns out to need sub-page provenance (e.g., a
  specific paragraph or table cell reference, not just a page number) —
  a genuinely finer-grained requirement than this ADR solves, deserving
  its own design pass.
- If HTML or JSON sources ever gain a citable structural unit of their
  own (e.g., a heading anchor or a specific API record ID) — the `null`
  `pages` field for those formats could be replaced with a
  format-appropriate provenance field at that point, following the same
  sidecar-plus-shared-resolver pattern established here rather than a
  bespoke one-off.
- If `pdfplumber`'s `page.page_number` semantics ever change across a
  dependency version bump — confirm this ADR's assumption (1-indexed,
  reflects true document position regardless of skipped pages) still
  holds before trusting existing sidecars against a newly-extracted
  document.
