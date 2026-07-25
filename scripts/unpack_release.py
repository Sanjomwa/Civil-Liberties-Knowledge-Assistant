"""
unpack_release.py -- reconstructs data/chunks/ and data/metadata/ from
the tiered public release archive (dist/corpus-release-v1.zip,
ADR-0013), for the Docker build-time baseline (OONI+CIPESA, ~54% of the
corpus). Freedom House/Access Now are not unpacked here -- their
metadata-only/ entries carry no chunk text; rehydrate.py fetches their
real text separately (interface-design.md Decision 8).

full-text/{org}/{chunk_id}.json records are byte-identical in shape to
data/chunks/{doc_id}/{chunk_id}.json (confirmed directly against a real
chunk file and a real release entry, not assumed) -- each carries its
own embedded `document_metadata`, which chunk.py's write_metadata()
persists to data/metadata/{doc_id}.json as the literal same object (see
chunk.py's own docstring on write_metadata). So data/metadata/{doc_id}.json
can be reconstructed from any one of that document's chunks -- written
once per doc_id, not once per chunk.

Usage:
    python scripts/unpack_release.py dist/corpus-release-v1.zip
"""

import json
import sys
import zipfile
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
CHUNKS_DIR = PROJECT_ROOT / "data" / "chunks"
METADATA_DIR = PROJECT_ROOT / "data" / "metadata"


def unpack(zip_path: Path) -> None:
    CHUNKS_DIR.mkdir(parents=True, exist_ok=True)
    METADATA_DIR.mkdir(parents=True, exist_ok=True)

    written_chunks = 0
    written_docs = set()

    with zipfile.ZipFile(zip_path) as zf:
        for name in zf.namelist():
            if not name.startswith("full-text/") or not name.endswith(".json"):
                continue
            record = json.loads(zf.read(name))
            doc_id = record["doc_id"]
            chunk_id = record["chunk_id"]

            doc_dir = CHUNKS_DIR / doc_id
            doc_dir.mkdir(parents=True, exist_ok=True)
            with open(doc_dir / f"{chunk_id}.json", "w", encoding="utf-8") as f:
                json.dump(record, f, indent=2, ensure_ascii=False)
                f.write("\n")
            written_chunks += 1

            if doc_id not in written_docs:
                meta_path = METADATA_DIR / f"{doc_id}.json"
                with open(meta_path, "w", encoding="utf-8") as f:
                    json.dump(record["document_metadata"], f, indent=2, ensure_ascii=False)
                    f.write("\n")
                written_docs.add(doc_id)

    print(f"[ok] unpacked {written_chunks} chunk(s) across {len(written_docs)} "
          f"document(s) from {zip_path.name} (full-text/ only -- OONI+CIPESA "
          f"baseline; Freedom House/Access Now come from rehydrate.py, not this file)")


def main() -> None:
    if len(sys.argv) != 2:
        print(f"Usage: python {sys.argv[0]} <path-to-corpus-release-v1.zip>", file=sys.stderr)
        sys.exit(1)
    unpack(Path(sys.argv[1]))


if __name__ == "__main__":
    main()
