"""
chunk.py — split extracted text into overlapping chunks for later embedding.

Reads every data/metadata/{doc_id}.json written by metadata.py (that's the
authoritative list of what belongs in the corpus at this stage — chunk.py
doesn't re-decide inclusion, it just processes whatever metadata.py already
produced), and the corresponding extracted text at
data/processed/{org}/{doc_id}.txt.

Splits each document into fixed overlapping windows — chunk_size=1500
chars, chunk_step=750 chars, per the architecture — and writes one JSON
file per chunk to data/chunks/{doc_id}/{chunk_id}.json. Each chunk record
embeds the full document metadata record ("each chunk inherits full
document metadata", per the architecture), so a chunk is self-contained at
retrieval time without needing a join back to data/metadata/.

Also updates data/metadata/{doc_id}.json with a `chunking` block (ADR-0003)
— strategy, chunk_size, chunk_step, total_chunks, chunking_date, and a
corpus_version stamp copied from declared.corpus_version at the moment
chunking actually runs. That stamp is what makes stale chunks detectable
later (via check_drift.py, not yet built) if the corpus version moves on
without this document being re-chunked.

**Fixed 2026-07-22 — the chunking block now actually reaches chunk files
too, not just data/metadata/{doc_id}.json.** Previously
`chunk_document()` wrote every chunk file from the in-memory `metadata`
dict *before* the chunking block was ever added to it (that used to
happen in a separate step afterward), so each chunk's own embedded
`document_metadata` never carried a `"chunking"` key at all — confirmed
against the real corpus: zero of 3,783 chunk files had one. Found when
`src/retrieval/embed.py` hard-failed against the real corpus expecting
that stamp to be there (see decisionlog.md, 2026-07-22, for the full
incident). `chunk_document()` now computes `total_chunks` from the
window count first, stamps the `chunking` block into `metadata` in
place, and only then writes chunk files — so every chunk file's
embedded `document_metadata` matches `data/metadata/{doc_id}.json`
exactly, including `chunking`. No other field, chunk boundary, chunk_id,
or `pages` value changes as a result of this fix — confirmed via a
smoke test comparing before/after chunk counts and content on a
synthetic fixture before running this against the real corpus.

Idempotent: rerunning a document clears its existing data/chunks/{doc_id}/
directory first and rewrites it from scratch, so stale chunk counts or
boundaries from a previous chunk_size/chunk_step never linger alongside
new ones.

Chunking is deliberately a separate stage from extraction (per the
architecture's own "Chunking is separate from ingestion" principle) —
re-chunking with different parameters never requires re-extracting.

Page provenance (ADR-0008, 2026-07-20): for PDF-sourced documents, each
chunk record now also carries a `"pages"` field — the sorted list of true
PDF page numbers (see src/ingestion/pages.py) the chunk's
[char_start, char_end) range overlaps, resolved against the
data/processed/{org}/{doc_id}.pages.json sidecar extract.py writes. `null`
for non-PDF sources (no sidecar exists) or if the sidecar hasn't been
generated yet for this document. Pure addition to the chunk schema — no
existing field changes meaning, and chunk counts are unaffected.

Usage:
    uv run python src/ingestion/chunk.py
"""

import json
import shutil
import sys
from datetime import date
from pathlib import Path

import yaml

sys.path.insert(0, str(Path(__file__).resolve().parent))
from pages import load_pages_sidecar, pages_sidecar_path, resolve_page_range  # noqa: E402

PROJECT_ROOT = Path(__file__).resolve().parents[2]
SOURCES_DIR = PROJECT_ROOT / "corpus" / "sources"
PROCESSED_DIR = PROJECT_ROOT / "data" / "processed"
METADATA_DIR = PROJECT_ROOT / "data" / "metadata"
CHUNKS_DIR = PROJECT_ROOT / "data" / "chunks"

CHUNK_SIZE = 1500
CHUNK_STEP = 750


def load_org_lookup() -> dict:
    """doc_id -> org, read from corpus/sources/*.yaml (the same declared
    source metadata.py and acquire.py already trust) — needed here only to
    locate data/processed/{org}/{doc_id}.txt, since the metadata schema
    itself doesn't record the org folder slug."""
    lookup = {}
    for yaml_path in sorted(SOURCES_DIR.glob("*.yaml")):
        org = yaml_path.stem
        with open(yaml_path) as f:
            data = yaml.safe_load(f) or {}
        for doc in data.get("documents", []):
            lookup[doc["doc_id"]] = org
    return lookup


def make_windows(text: str, size: int = CHUNK_SIZE, step: int = CHUNK_STEP):
    """Fixed overlapping windows over `text`. Always includes a final
    window that reaches exactly the end of the text (no trailing
    near-empty remainder chunk), and a document shorter than `size`
    produces exactly one chunk covering all of it."""
    windows = []
    start = 0
    n = len(text)
    if n == 0:
        return windows
    while start < n:
        end = min(start + size, n)
        windows.append((start, end))
        if end == n:
            break
        start += step
    return windows


def stamp_chunking_block(metadata: dict, total_chunks: int) -> None:
    """Mutates `metadata` in place, adding the ADR-0003 `chunking` block.
    Must run BEFORE any chunk file is written (see chunk_document) so that
    every chunk's own embedded document_metadata carries this block too,
    not just data/metadata/{doc_id}.json — see this module's docstring,
    "Fixed 2026-07-22", for why that distinction matters."""
    metadata["chunking"] = {
        "strategy": "fixed_overlap",
        "chunk_size": CHUNK_SIZE,
        "chunk_step": CHUNK_STEP,
        "total_chunks": total_chunks,
        "chunking_date": date.today().isoformat(),
        # Stamped from declared.corpus_version at the moment chunking runs
        # (ADR-0003) — a later mismatch against declared.corpus_version is
        # what makes this document's chunks detectably stale.
        "corpus_version": metadata["declared"]["corpus_version"],
    }


def chunk_document(doc_id: str, org: str, metadata: dict) -> int:
    processed_path = PROCESSED_DIR / org / f"{doc_id}.txt"
    if not processed_path.exists():
        raise FileNotFoundError(
            f"{doc_id}: expected extracted text at "
            f"{processed_path.relative_to(PROJECT_ROOT)}, not found. Run "
            f"extract.py first."
        )
    text = processed_path.read_text(encoding="utf-8")
    windows = make_windows(text)

    # Stamp the chunking block into `metadata` (mutated in place) BEFORE
    # writing any chunk file below, so every chunk's own embedded
    # document_metadata includes it — this ordering is the fix (see
    # module docstring, "Fixed 2026-07-22"). Previously this ran after
    # every chunk file was already written, so the block never reached
    # them.
    stamp_chunking_block(metadata, total_chunks=len(windows))

    # ADR-0008: load once per document, not once per chunk. None for
    # non-PDF sources or a PDF not yet re-extracted since ADR-0008 landed
    # (extract.py's own self-migrating skip logic handles that latter case
    # on its next run — chunk.py just reflects whatever sidecar state
    # currently exists).
    breakpoints = load_pages_sidecar(pages_sidecar_path(PROCESSED_DIR, org, doc_id))

    doc_chunk_dir = CHUNKS_DIR / doc_id
    if doc_chunk_dir.exists():
        shutil.rmtree(doc_chunk_dir)
    doc_chunk_dir.mkdir(parents=True)

    for index, (char_start, char_end) in enumerate(windows):
        chunk_id = f"{doc_id}-chunk-{index:04d}"
        record = {
            "chunk_id": chunk_id,
            "doc_id": doc_id,
            "chunk_index": index,
            "char_start": char_start,
            "char_end": char_end,
            "text": text[char_start:char_end],
            "pages": resolve_page_range(breakpoints, char_start, char_end),
            "document_metadata": metadata,
        }
        out_path = doc_chunk_dir / f"{chunk_id}.json"
        with open(out_path, "w", encoding="utf-8") as f:
            json.dump(record, f, indent=2, ensure_ascii=False)
            f.write("\n")

    return len(windows)


def write_metadata(doc_id: str, metadata: dict) -> None:
    """Persists `metadata` (already stamped with `chunking` by
    stamp_chunking_block, called from within chunk_document) to
    data/metadata/{doc_id}.json. Renamed from update_metadata_with_chunking
    2026-07-22 — it no longer computes the chunking block itself, just
    writes what chunk_document already stamped, so the two can never
    drift out of sync with each other again."""
    meta_path = METADATA_DIR / f"{doc_id}.json"
    with open(meta_path, "w", encoding="utf-8") as f:
        json.dump(metadata, f, indent=2, ensure_ascii=False)
        f.write("\n")


def main() -> None:
    if not METADATA_DIR.exists() or not any(METADATA_DIR.glob("*.json")):
        print(
            f"No metadata records in "
            f"{METADATA_DIR.relative_to(PROJECT_ROOT)} — run metadata.py "
            f"first.",
            file=sys.stderr,
        )
        return

    org_lookup = load_org_lookup()
    total_docs = 0
    total_chunks_written = 0

    for meta_path in sorted(METADATA_DIR.glob("*.json")):
        doc_id = meta_path.stem
        with open(meta_path, encoding="utf-8") as f:
            metadata = json.load(f)

        org = org_lookup.get(doc_id)
        if org is None:
            print(
                f"[FAIL] {doc_id} — has a metadata record but isn't "
                f"declared in any corpus/sources/*.yaml. Check for a stale "
                f"metadata.json left over from a removed source entry.",
                file=sys.stderr,
            )
            sys.exit(1)

        try:
            n_chunks = chunk_document(doc_id, org, metadata)
        except FileNotFoundError as e:
            print(f"[FAIL] {e}", file=sys.stderr)
            sys.exit(1)

        write_metadata(doc_id, metadata)
        print(f"[ok] {doc_id} — {n_chunks} chunk(s) written")
        total_docs += 1
        total_chunks_written += n_chunks

    print(
        f"\nDone — {total_chunks_written} chunk(s) across {total_docs} "
        f"document(s) written to {CHUNKS_DIR.relative_to(PROJECT_ROOT)}."
    )


if __name__ == "__main__":
    main()
