"""
build_release_artifact.py — package the tiered public corpus release
(docs/adr/0013-tiered-corpus-release.md).

Two tiers, split by actual licensing risk rather than shipped uniformly:

  - OONI and CIPESA — full chunk records exactly as data/chunks/ already
    stores them, each explicitly carrying its own org's real license
    string (CC BY-NC-SA 4.0 / CC BY 4.0) at the record level, not just a
    repo-wide note — OONI's ShareAlike term propagates to anything
    derived from it and needs to stay visible per record.
  - Freedom House and Access Now — stripped records only: doc_id, source
    URL, chunk_id, char offsets, content_sha256. No chunk text, no
    embedding vector. A user reconstructs the real text locally via
    `uv run python src/ingestion/rehydrate.py --org <org>`, then runs
    embed.py as normal, same as any other corpus build.

content_sha256 for the stripped tier (judgment call, documented here since
it's not a verbatim rule from anywhere else): computed fresh from each
document's currently-processed text via extract.py's own
content_sha256_of(), for BOTH Freedom House and Access Now. This is the
same hash function extract.py and rehydrate.py already use — no second
hashing scheme — but note Access Now itself is not one of extract.py's
"content_checksum_orgs" (ADR-0005/0007 only tracks that ongoing, during
ingestion, for raw_bytes_stable: false sources — Freedom House currently).
That scoping decision is about which org needs continuous live-content
drift monitoring during ingestion; it says nothing about whether a
one-off verification hash is useful to ship in a release artifact for a
stable-bytes org too, which it is: it's exactly what a rehydrating user
compares their locally-reconstructed text against, same field, same
purpose, for both restricted orgs.

Output: a single zip, dist/corpus-release-v1.zip by default — outside
data/ (gitignored, ephemeral) and outside corpus/ (curated declarations),
so it's easy to find and attach to a GitHub Release by hand. This script
never creates or publishes a release itself — that's a human action, same
convention as every git push/commit in this project.

Usage:
    uv run python scripts/build_release_artifact.py
    uv run python scripts/build_release_artifact.py --output dist/corpus-release-v2.zip
"""

import argparse
import json
import sys
import zipfile
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT / "src" / "ingestion"))
from extract import content_sha256_of  # noqa: E402

CHUNKS_DIR = PROJECT_ROOT / "data" / "chunks"
PROCESSED_DIR = PROJECT_ROOT / "data" / "processed"
DIST_DIR = PROJECT_ROOT / "dist"

FULL_TEXT_LICENSES = {"ooni": "CC BY-NC-SA 4.0", "cipesa": "CC BY 4.0"}
STRIPPED_ORGS = {"freedomhouse", "accessnow"}

# doc_id prefix -> org folder slug, matching corpus/sources/*.yaml naming.
# Order doesn't matter here -- none of these four prefixes is a prefix of
# another (confirmed against the real corpus's doc_id naming).
ORG_PREFIXES = {
    "ooni-": "ooni",
    "cipesa-": "cipesa",
    "freedomhouse-": "freedomhouse",
    "accessnow-": "accessnow",
}

MANIFEST_TEMPLATE = """\
# Civil Liberties Knowledge Assistant — Tiered Corpus Release

Full design and reasoning: docs/adr/0013-tiered-corpus-release.md in the
project repository. Summary:

Two of this corpus's four source organizations (Freedom House, Access Now)
have licensing terms that don't clearly permit bulk republication of their
full report text, even chunked (see docs/licensing.md). The other two
(OONI, CIPESA) are Creative-Commons licensed and republished here in full.

## full-text/ — OONI and CIPESA, complete chunk text

{full_docs} document(s), {full_chunks} chunk(s). Each record is exactly
what this project's own retrieval index was built from (chunk_id, doc_id,
char offsets, text, pages, full document metadata), plus an explicit
`license` field:
  - OONI: CC BY-NC-SA 4.0 (Attribution, NonCommercial, ShareAlike)
  - CIPESA: CC BY 4.0 (Attribution)

## metadata-only/ — Freedom House and Access Now, text stripped

{stripped_docs} document(s), {stripped_chunks} chunk(s). Each record has
only: doc_id, source_url, chunk_id, char_start, char_end, content_sha256.
No chunk text and no embedding vector are included.

To reconstruct the real chunk text locally:

    git clone <this repo>
    cd civil-liberties-knowledge-assistant
    uv sync
    uv run python src/ingestion/rehydrate.py --org freedomhouse
    uv run python src/ingestion/rehydrate.py --org accessnow
    uv run python src/retrieval/embed.py

`rehydrate.py` re-fetches each document from its original source, re-runs
the same deterministic extraction and chunking this project used, and
verifies the result against `content_sha256` above before accepting it —
a mismatch is a hard failure, not a silent warning. A successful
rehydration is independent proof the corpus matches what's indexed,
stronger than trusting a static text dump would be.
"""


def _org_for_doc_id(doc_id: str) -> str:
    for prefix, org in ORG_PREFIXES.items():
        if doc_id.startswith(prefix):
            return org
    raise ValueError(
        f"{doc_id}: no known org prefix (expected one of {sorted(ORG_PREFIXES)})"
    )


def _full_record(chunk: dict, org: str) -> dict:
    record = dict(chunk)
    record["license"] = FULL_TEXT_LICENSES[org]
    return record


def _stripped_record(chunk: dict, org: str, content_hash_cache: dict[str, str]) -> dict:
    doc_id = chunk["doc_id"]
    if doc_id not in content_hash_cache:
        processed_path = PROCESSED_DIR / org / f"{doc_id}.txt"
        content_hash_cache[doc_id] = content_sha256_of(
            processed_path.read_text(encoding="utf-8")
        )
    declared = chunk["document_metadata"]["declared"]
    return {
        "doc_id": doc_id,
        "source_url": declared["url"],
        "chunk_id": chunk["chunk_id"],
        "char_start": chunk["char_start"],
        "char_end": chunk["char_end"],
        "content_sha256": content_hash_cache[doc_id],
    }


def build(output_path: Path) -> dict:
    full_count = 0
    stripped_count = 0
    content_hash_cache: dict[str, str] = {}
    full_docs: set[str] = set()
    stripped_docs: set[str] = set()

    output_path.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(output_path, "w", zipfile.ZIP_DEFLATED) as zf:
        for doc_dir in sorted(CHUNKS_DIR.iterdir()):
            if not doc_dir.is_dir():
                continue
            doc_id = doc_dir.name
            org = _org_for_doc_id(doc_id)

            for chunk_path in sorted(doc_dir.glob("*.json")):
                with open(chunk_path, encoding="utf-8") as f:
                    chunk = json.load(f)

                if org in FULL_TEXT_LICENSES:
                    record = _full_record(chunk, org)
                    arc_name = f"full-text/{org}/{chunk['chunk_id']}.json"
                    full_docs.add(doc_id)
                    full_count += 1
                elif org in STRIPPED_ORGS:
                    record = _stripped_record(chunk, org, content_hash_cache)
                    arc_name = f"metadata-only/{org}/{chunk['chunk_id']}.json"
                    stripped_docs.add(doc_id)
                    stripped_count += 1
                else:
                    raise ValueError(f"{doc_id}: org {org!r} not in any known release tier")

                zf.writestr(arc_name, json.dumps(record, indent=2, ensure_ascii=False))

        zf.writestr(
            "MANIFEST.md",
            MANIFEST_TEMPLATE.format(
                full_docs=len(full_docs), full_chunks=full_count,
                stripped_docs=len(stripped_docs), stripped_chunks=stripped_count,
            ),
        )

    return {
        "full_text_documents": len(full_docs),
        "full_text_chunks": full_count,
        "metadata_only_documents": len(stripped_docs),
        "metadata_only_chunks": stripped_count,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", default=str(DIST_DIR / "corpus-release-v1.zip"))
    args = parser.parse_args()

    output_path = Path(args.output)
    if not CHUNKS_DIR.exists() or not any(CHUNKS_DIR.iterdir()):
        print(
            f"No chunks in {CHUNKS_DIR.relative_to(PROJECT_ROOT)} — run the "
            f"ingestion pipeline first.",
            file=sys.stderr,
        )
        sys.exit(1)

    stats = build(output_path)
    print(f"[ok] wrote {output_path.relative_to(PROJECT_ROOT)}")
    print(
        f"  full-text (OONI+CIPESA): {stats['full_text_documents']} document(s), "
        f"{stats['full_text_chunks']} chunk(s)"
    )
    print(
        f"  metadata-only (Freedom House+Access Now): "
        f"{stats['metadata_only_documents']} document(s), "
        f"{stats['metadata_only_chunks']} chunk(s)"
    )
    print(
        "\nThis archive is not published anywhere — attach it to a GitHub "
        "Release by hand (Sam's own action)."
    )


if __name__ == "__main__":
    main()
