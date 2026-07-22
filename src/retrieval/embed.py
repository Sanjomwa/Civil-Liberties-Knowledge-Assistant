"""
embed.py — compute one embedding vector per chunk, build the retrieval index.

Reads every chunk record from data/chunks/{doc_id}/{chunk_id}.json (written by
src/ingestion/chunk.py) and builds the two retrieval indexes search.py needs:
a vector index (cosine similarity over dense embeddings) and a text index
(TF-IDF keyword search) — both via the `minsearch` library (`minsearch.
VectorSearch` and `minsearch.Index`), which already provides fit/search/save/
load without hand-rolled persistence code.

Combining both indexes in one script, rather than a separate script per
index, is a deliberate right-sizing call: both need the same one-time read
of every chunk, and TF-IDF fitting is cheap relative to the embedding step,
so there's no benefit to reading 3,783 chunk files twice. See
docs/retrieval-design.md for the full phase design.

Embedding model: BAAI/bge-small-en-v1.5, via its ONNX port bundled with the
`fastembed` library (not a torch dependency — small, local, no API key).
Chosen over the course's own all-MiniLM-L6-v2 for two concrete reasons (see
docs/retrieval-design.md's embed.py section for the full reasoning): this
corpus's chunk_size=1500 chars (~375 tokens) exceeds MiniLM's 256-token
window, a real truncation risk; BGE is trained specifically for asymmetric
query/passage retrieval, a better fit for the actual task here than a
generic sentence-similarity model. fastembed's own bundled model card notes
prefixes are "not so necessary" for this specific model — verified via
`TextEmbedding.list_supported_models()`, not assumed — so `embed()`/
`query_embed()` are used as-is with no manual prefix string.

Corpus-version / model stamp (fix from the 2026-07-22 Opus design review):
before embedding anything, every document's `chunking.corpus_version`
stamp (ADR-0003) is checked against the single current value in
corpus/CORPUS_VERSION. Any mismatch is a hard failure, not a silent
skip — it means a document was corpus-version-bumped without being
re-chunked (the frozen architecture explicitly allows re-chunking without
re-extraction, so this drift is a real, expected-to-eventually-happen case,
not a hypothetical). The resulting index is stamped with the same corpus
version plus the embedding model name — search.py and evaluate.py check
this stamp before running anything, so a later re-chunk without a matching
re-embed fails loudly instead of silently returning stale-chunk results.

**Corrected 2026-07-22, first real run against the actual corpus:** the
`chunking.corpus_version` stamp is read from data/metadata/{doc_id}.json,
NOT from the chunk record's own embedded `document_metadata` — found via
a real hard-fail on the first WSL run against all 35 real documents (not
a synthetic fixture). Root cause, confirmed by inspecting the real chunk
files: `src/ingestion/chunk.py`'s `chunk_document()` writes each chunk
file from the in-memory `metadata` dict *before*
`update_metadata_with_chunking()` adds the `chunking` block to that same
dict — so the block only ever reaches `data/metadata/{doc_id}.json`
(written second, after the block exists), never the chunk files
themselves. Confirmed: zero of 3,783 real chunk files have a `"chunking"`
key at all. This is a real bug in already-shipped, "closed" ingestion
code — flagged to Sam separately (see decisionlog.md, 2026-07-22) as its
own decision (fix chunk.py and re-run vs. leave the workaround below in
place), not fixed here. This script's own fix does not depend on that
decision either way: it reads the stamp from data/metadata/{doc_id}.json
directly, cached per doc_id, which is unaffected by the bug (metadata.py/
chunk.py both write correctly to that file).

Also corrected 2026-07-22: corpus/CORPUS_VERSION's real content is
`"<version> <date-it-was-set>"` (e.g. `"v1.0 2026-07-13"`), not a bare
version string — this file had never actually been read
programmatically by any prior ingestion script, so its real format
hadn't been verified before this comparison was first written. Fixed to
compare only the leading whitespace-separated token.

lifecycle_status is indexed as a keyword field on both indexes (cheap,
already free from minsearch's own filter support) — this is what closes
the "retrieval-time lifecycle.status filter not yet built" gap noted in
docs/ingestion-design.md's own "what's deliberately not built yet" section.
No document has a non-"active" status yet, so this has no visible effect
today, but search.py defaults to filtering it so a future supersession
doesn't require touching this script.

Idempotent: rerunning regenerates both indexes and the metadata stamp from
scratch — never appends to a stale index.

Usage:
    uv run python src/retrieval/embed.py
"""

import json
import sys
from datetime import datetime
from pathlib import Path

import numpy as np
from fastembed import TextEmbedding
from minsearch import Index, VectorSearch

PROJECT_ROOT = Path(__file__).resolve().parents[2]
CHUNKS_DIR = PROJECT_ROOT / "data" / "chunks"
METADATA_DIR = PROJECT_ROOT / "data" / "metadata"
INDEX_DIR = PROJECT_ROOT / "data" / "index"
CORPUS_VERSION_PATH = PROJECT_ROOT / "corpus" / "CORPUS_VERSION"

EMBEDDING_MODEL = "BAAI/bge-small-en-v1.5"
VECTOR_INDEX_PATH = INDEX_DIR / "vector_index.pkl"
TEXT_INDEX_PATH = INDEX_DIR / "text_index.pkl"
INDEX_METADATA_PATH = INDEX_DIR / "index_metadata.json"


def load_current_corpus_version() -> str:
    if not CORPUS_VERSION_PATH.exists():
        print(
            f"No {CORPUS_VERSION_PATH.relative_to(PROJECT_ROOT)} found — "
            f"this should have been created during ingestion setup.",
            file=sys.stderr,
        )
        sys.exit(1)
    raw = CORPUS_VERSION_PATH.read_text(encoding="utf-8").strip()
    # Real format is "<version> <date-it-was-set>" (e.g. "v1.0 2026-07-13"),
    # not a bare version string -- confirmed 2026-07-22 against the actual
    # file content on the first real WSL run. Only the leading token is
    # ever compared against a document's own corpus_version field.
    return raw.split()[0]


_chunking_stamp_cache: dict[str, str | None] = {}


def _document_chunking_corpus_version(doc_id: str) -> str | None:
    """The `chunking.corpus_version` stamp (ADR-0003) lives in
    data/metadata/{doc_id}.json, not in the chunk record's own embedded
    document_metadata. Confirmed 2026-07-22 against the real corpus: zero
    of 3,783 chunk files have a "chunking" key at all — src/ingestion/
    chunk.py's chunk_document() writes each chunk file from the in-memory
    metadata dict BEFORE update_metadata_with_chunking() adds the
    chunking block to that same dict, so the block only ever reaches
    data/metadata/{doc_id}.json (written second), never the chunk files.
    Real bug in already-shipped ingestion code, flagged to Sam separately
    (decisionlog.md, 2026-07-22) — not fixed here; this workaround reads
    the one place the stamp is actually, correctly written."""
    if doc_id not in _chunking_stamp_cache:
        meta_path = METADATA_DIR / f"{doc_id}.json"
        if not meta_path.exists():
            _chunking_stamp_cache[doc_id] = None
        else:
            with open(meta_path, encoding="utf-8") as f:
                doc_metadata = json.load(f)
            _chunking_stamp_cache[doc_id] = doc_metadata.get("chunking", {}).get("corpus_version")
    return _chunking_stamp_cache[doc_id]


def load_chunks(current_corpus_version: str) -> list[dict]:
    """Reads every chunk JSON, verifying its parent document's stamped
    chunking.corpus_version (from data/metadata/{doc_id}.json — see
    _document_chunking_corpus_version's docstring for why not the chunk
    file itself) matches the corpus's current version before it's allowed
    into the index. A document whose chunks predate the current corpus
    version needs re-chunking (src/ingestion/chunk.py), not silent
    inclusion of stale content — see this module's own docstring for why."""
    if not CHUNKS_DIR.exists() or not any(CHUNKS_DIR.iterdir()):
        print(
            f"No chunks in {CHUNKS_DIR.relative_to(PROJECT_ROOT)} — run "
            f"src/ingestion/chunk.py first.",
            file=sys.stderr,
        )
        sys.exit(1)

    chunks = []
    stale_docs = set()
    for chunk_path in sorted(CHUNKS_DIR.glob("*/*.json")):
        with open(chunk_path, encoding="utf-8") as f:
            record = json.load(f)

        doc_id = record["doc_id"]
        chunk_corpus_version = _document_chunking_corpus_version(doc_id)
        if chunk_corpus_version != current_corpus_version:
            stale_docs.add(doc_id)
            continue

        meta = record["document_metadata"]
        declared = meta["declared"]
        lifecycle = meta["lifecycle"]
        chunks.append(
            {
                "chunk_id": record["chunk_id"],
                "doc_id": doc_id,
                "text": record["text"],
                "pages": record.get("pages"),
                "organization": declared["organization"],
                "countries": declared["countries"],
                "publication_date": declared["publication_date"],
                "lifecycle_status": lifecycle["status"],
            }
        )

    if stale_docs:
        print(
            f"[FAIL] {len(stale_docs)} document(s) have chunks stamped with "
            f"a corpus_version other than the current {current_corpus_version!r}: "
            f"{sorted(stale_docs)}. Re-run src/ingestion/chunk.py for these "
            f"documents before embedding — embedding stale chunks would "
            f"silently poison the index.",
            file=sys.stderr,
        )
        sys.exit(1)

    return chunks


EMBED_BATCH_SIZE = 32  # conservative on purpose -- see 2026-07-22 note below
EMBED_PROGRESS_EVERY = 320  # ~10 batches


def compute_embeddings(chunks: list[dict]) -> np.ndarray:
    """Deliberately conservative batch_size + visible progress printing
    (added 2026-07-22, after two real WSL disconnects during this exact
    step — see decisionlog.md). fastembed's own default batch_size is 256;
    lowering it caps peak per-batch memory during CPU-only onnxruntime
    inference, and printing progress lets Claude Code (and Sam watching)
    tell "still working" apart from "hung/crashed" instead of staring at
    a silent terminal for however long 3,783 chunks takes. This doesn't
    change the output vectors at all, only how they're computed and
    reported."""
    model = TextEmbedding(model_name=EMBEDDING_MODEL)
    texts = [c["text"] for c in chunks]
    vectors = []
    for i, vec in enumerate(model.embed(texts, batch_size=EMBED_BATCH_SIZE), start=1):
        vectors.append(vec)
        if i % EMBED_PROGRESS_EVERY == 0 or i == len(texts):
            print(f"  [embed] {i}/{len(texts)} chunk(s) embedded")
    return np.array(vectors, dtype=np.float32)


def build_and_save_indexes(chunks: list[dict], vectors: np.ndarray) -> None:
    INDEX_DIR.mkdir(parents=True, exist_ok=True)

    vector_index = VectorSearch(keyword_fields=["lifecycle_status"])
    vector_index.fit(vectors, chunks)
    vector_index.save(VECTOR_INDEX_PATH)

    text_index = Index(text_fields=["text"], keyword_fields=["lifecycle_status"])
    text_index.fit(chunks)
    text_index.save(TEXT_INDEX_PATH)


def write_index_metadata(chunks: list[dict], vectors: np.ndarray, corpus_version: str) -> None:
    metadata = {
        "embedding_model": EMBEDDING_MODEL,
        "embedding_dim": int(vectors.shape[1]),
        "corpus_version": corpus_version,
        "chunk_count": len(chunks),
        "created_at": datetime.now().isoformat(timespec="seconds"),
    }
    with open(INDEX_METADATA_PATH, "w", encoding="utf-8") as f:
        json.dump(metadata, f, indent=2)
        f.write("\n")


def main() -> None:
    corpus_version = load_current_corpus_version()
    chunks = load_chunks(corpus_version)
    print(f"[ok] loaded {len(chunks)} chunk(s), corpus_version={corpus_version}")

    print(f"[embed] computing {EMBEDDING_MODEL} vectors for {len(chunks)} chunk(s)...")
    vectors = compute_embeddings(chunks)
    print(f"[ok] embedded — shape {vectors.shape}")

    build_and_save_indexes(chunks, vectors)
    write_index_metadata(chunks, vectors, corpus_version)

    print(
        f"\nDone — wrote {VECTOR_INDEX_PATH.relative_to(PROJECT_ROOT)}, "
        f"{TEXT_INDEX_PATH.relative_to(PROJECT_ROOT)}, "
        f"{INDEX_METADATA_PATH.relative_to(PROJECT_ROOT)}."
    )


if __name__ == "__main__":
    main()
