"""
rehydrate.py — reconstruct restricted-license chunk text locally.

Freedom House and Access Now content is not redistributed in this
project's public release artifact (docs/adr/0013-tiered-corpus-release.md)
— only metadata and a content hash are shipped for their chunks. This
module re-runs the existing acquire.py -> extract.py -> metadata.py ->
chunk.py stages for one org's documents, so anyone who clones the release
ends up with the exact same chunk text this project actually indexed,
without this project ever having published it.

Both orgs already use `acquisition: auto` for every document (no manual
acquisition step, no new acquisition logic needed) — this module is only
plumbing that calls the three existing stages per document, plus a
verification step, not a new pipeline.

Verification reuses each org's own already-established integrity
mechanism rather than inventing a second hashing scheme:

  - Freedom House (raw_bytes_stable: false, ADR-0005) — its raw HTML
    bytes are CDN-randomized per request, so acquire.py's raw-sha256 gate
    is deliberately not a fidelity check for this org (see the 2026-07-25
    fix in acquire.py's acquire_document(), same date as this module).
    The mechanism that survives that randomness is content_sha256 (a hash
    of canonicalized *extracted* text), already tracked in
    corpus/derived-checksums/freedomhouse.json by extract.py. This module
    compares against that baseline and treats a mismatch as fatal — unlike
    extract.py's own check_content_checksum(), which only warns (ADR-0005:
    a content_sha256 mismatch during normal ingestion is a Tier-2-style
    human-review signal, not an auto-reject). Rehydration's purpose is
    different: a mismatch here means the user does not have the corpus
    text this project actually indexed, which must be loud.
  - Access Now (raw_bytes_stable: true, the default) — content_sha256 is
    never tracked for this org, by design: stable raw bytes deterministically
    produce the same extracted text every time, so acquire.py's existing
    raw-sha256 gate (which a successful acquire_document() call already
    enforces) is itself the correct, sufficient verification. No separate
    check is needed or added here.

Skips validate.py's corpus-wide duplicate-detection pass deliberately —
every rehydratable document was already validated once during original
ingestion (corpus/validation-results.json still has its entry, which
metadata.py's write_metadata_record() already hard-requires), so this
reuses that recorded result rather than re-running a corpus-wide script
for one document.

Usage:
    uv run python src/ingestion/rehydrate.py --org freedomhouse
    uv run python src/ingestion/rehydrate.py --org accessnow
"""

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import acquire  # noqa: E402
import chunk as chunk_mod  # noqa: E402
import extract  # noqa: E402
import metadata as metadata_mod  # noqa: E402

PROJECT_ROOT = Path(__file__).resolve().parents[2]
VALIDATION_RESULTS_PATH = PROJECT_ROOT / "corpus" / "validation-results.json"

REHYDRATABLE_ORGS = ["freedomhouse", "accessnow"]


class RehydrationError(Exception):
    """A document failed to rehydrate correctly — acquisition failure, or
    a verified content/hash mismatch. Always fatal for that document;
    never silently continued past."""


def _org_docs(org: str) -> list[dict]:
    return [doc for src_org, doc in acquire.load_sources() if src_org == org]


def _load_validation_results() -> dict:
    if not VALIDATION_RESULTS_PATH.exists():
        raise RehydrationError(
            f"No {VALIDATION_RESULTS_PATH.relative_to(PROJECT_ROOT)} found — "
            f"rehydrate.py reuses each document's existing validation "
            f"result rather than re-running validate.py; this file should "
            f"already exist from original corpus construction."
        )
    with open(VALIDATION_RESULTS_PATH, encoding="utf-8") as f:
        return json.load(f)


def _verify_content(org: str, doc_id: str, content_checksum_orgs: set[str]) -> None:
    """Hard verification — raises on mismatch, unlike extract.py's own
    warn-only content-drift check. No-op for an org not in
    content_checksum_orgs (Access Now): acquire_document() already
    enforced the raw-sha256 gate that's the correct check for a
    raw_bytes_stable org, by the time this is called."""
    if org not in content_checksum_orgs:
        return
    derived = acquire.load_derived_checksums(org)
    expected = derived.get(doc_id, {}).get("content_sha256")
    if expected is None:
        raise RehydrationError(
            f"{doc_id}: no recorded content_sha256 baseline in "
            f"corpus/derived-checksums/{org}.json to verify against."
        )
    processed_path = extract.PROCESSED_DIR / org / f"{doc_id}.txt"
    actual = extract.content_sha256_of(processed_path.read_text(encoding="utf-8"))
    if actual != expected:
        raise RehydrationError(
            f"{doc_id}: content_sha256 mismatch — expected {expected}, got "
            f"{actual}. The rehydrated text does not match what this "
            f"project actually indexed."
        )
    print(f"[verified] {doc_id} — content_sha256 matches ({actual})")


def rehydrate_document(
    org: str, doc: dict, validation_results: dict, content_checksum_orgs: set[str]
) -> int:
    """Re-acquire, re-extract, re-metadata, re-chunk one document. Returns
    the chunk count on success. Raises RehydrationError on any integrity
    failure."""
    doc_id = doc["doc_id"]

    try:
        row = acquire.acquire_document(org, doc)
    except acquire.AcquisitionFailure as e:
        raise RehydrationError(f"{doc_id}: acquisition failed — {e}") from e
    if row is None:
        raise RehydrationError(
            f"{doc_id}: acquisition did not complete this run (download "
            f"failed, or still pending manual placement) — see acquire.py's "
            f"own output above."
        )

    if not extract.extract_document(row, content_checksum_orgs):
        raise RehydrationError(f"{doc_id}: extraction failed — see output above.")

    _verify_content(org, doc_id, content_checksum_orgs)

    result = validation_results.get(doc_id)
    if result is None or not result.get("tier1_passed"):
        raise RehydrationError(
            f"{doc_id}: no passing Tier 1 result in "
            f"corpus/validation-results.json — rehydrate.py reuses the "
            f"existing result rather than re-running validate.py; this "
            f"document should already have one from original ingestion."
        )

    meta_path = metadata_mod.write_metadata_record(doc_id, org, doc, validation_results)
    with open(meta_path, encoding="utf-8") as f:
        meta = json.load(f)

    n_chunks = chunk_mod.chunk_document(doc_id, org, meta)
    chunk_mod.write_metadata(doc_id, meta)
    return n_chunks


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--org", required=True, choices=REHYDRATABLE_ORGS)
    args = parser.parse_args()

    docs = _org_docs(args.org)
    if not docs:
        print(
            f"No documents declared for org={args.org!r} in "
            f"corpus/sources/{args.org}.yaml.",
            file=sys.stderr,
        )
        sys.exit(1)

    try:
        validation_results = _load_validation_results()
    except RehydrationError as e:
        print(f"[FAIL] {e}", file=sys.stderr)
        sys.exit(1)

    content_checksum_orgs = extract.load_content_checksum_orgs()

    failures = 0
    total_chunks = 0
    for doc in docs:
        doc_id = doc["doc_id"]
        try:
            n_chunks = rehydrate_document(args.org, doc, validation_results, content_checksum_orgs)
        except RehydrationError as e:
            print(f"[FAIL] {e}", file=sys.stderr)
            failures += 1
            continue
        print(f"[ok] {doc_id} — rehydrated, {n_chunks} chunk(s) written")
        total_chunks += n_chunks

    print(
        f"\nDone — {len(docs) - failures}/{len(docs)} document(s) "
        f"rehydrated, {total_chunks} chunk(s) total."
    )
    if failures:
        sys.exit(1)


if __name__ == "__main__":
    main()
