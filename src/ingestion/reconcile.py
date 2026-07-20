"""
reconcile.py — cross-check that every surface tracking corpus state agrees
with every other one (ADR-0007, Finding 3).

Five different artifacts each drive a different pipeline stage:
corpus/sources/*.yaml (declared), corpus/manifest.csv (acquired),
corpus/acquisition-log.md's `## doc_id — Included` headings (human
decision), data/metadata/*.json (what chunk.py actually processes), and
data/chunks/{doc_id}/ (chunk.py's own output). Nothing else in the
pipeline checks these agree with each other — a hand-edit typo, a
transient rerun failure, or a removed log entry can silently desync one
from another with no error anywhere. This script is the check.

Not wired into pipeline.py's automatic stages. Like the not-yet-built
check_drift.py (ADR-0003), this is a diagnostic a human runs deliberately
— on demand, after a batch of changes, before treating the corpus as
settled — not a gate that blocks normal acquire/extract/validate/
metadata/chunk operation.

Checks, each independent, all run every time (a failure in one doesn't
skip the rest — a full report of every disagreement is more useful than
stopping at the first):

  1. Declared <-> acquired: every doc_id in corpus/sources/*.yaml with a
     real (non-REPLACE_ME) sha256 appears in corpus/manifest.csv, and
     vice versa.
  2. Included <-> metadata: every doc_id marked "## doc_id — Included" in
     acquisition-log.md has a matching data/metadata/{doc_id}.json, and
     vice versa.
  3. Derived checksums <-> declared: every doc_id with an entry in
     corpus/derived-checksums/{org}.json has a matching doc_id in that
     org's corpus/sources/{org}.yaml.
  4. Metadata <-> chunks: every doc_id with chunks in
     data/chunks/{doc_id}/ has a data/metadata/{doc_id}.json whose
     chunking.total_chunks matches the actual chunk file count, and vice
     versa.

Exit code non-zero if anything disagrees, printing exactly which doc_id
and which two sources disagreed — not just a pass/fail summary.

Usage:
    uv run python src/ingestion/reconcile.py
"""

import csv
import json
import re
import sys
from pathlib import Path

import yaml

sys.path.insert(0, str(Path(__file__).resolve().parent))
from acquire import load_derived_checksums  # noqa: E402 — needs sys.path set first

PROJECT_ROOT = Path(__file__).resolve().parents[2]
SOURCES_DIR = PROJECT_ROOT / "corpus" / "sources"
MANIFEST_PATH = PROJECT_ROOT / "corpus" / "manifest.csv"
ACQUISITION_LOG_PATH = PROJECT_ROOT / "corpus" / "acquisition-log.md"
DERIVED_CHECKSUMS_DIR = PROJECT_ROOT / "corpus" / "derived-checksums"
METADATA_DIR = PROJECT_ROOT / "data" / "metadata"
CHUNKS_DIR = PROJECT_ROOT / "data" / "chunks"

INCLUDED_HEADING_RE = re.compile(r"^## (\S+) — Included\s*$", re.MULTILINE)


def load_declared_real_sha256() -> dict[str, str]:
    """doc_id -> org, for every document declared in corpus/sources/*.yaml
    with a real (non-REPLACE_ME, non-empty) sha256 — a REPLACE_ME entry
    hasn't been acquired yet, so its absence from manifest.csv is expected,
    not drift."""
    docs = {}
    for yaml_path in sorted(SOURCES_DIR.glob("*.yaml")):
        org = yaml_path.stem
        with open(yaml_path) as f:
            data = yaml.safe_load(f) or {}
        for doc in data.get("documents", []):
            sha = doc.get("sha256", "")
            if sha and not sha.startswith("REPLACE_ME"):
                docs[doc["doc_id"]] = org
    return docs


def load_all_declared_doc_ids() -> set[str]:
    """Every doc_id declared in corpus/sources/*.yaml, regardless of
    acquisition status — used for the derived-checksums <-> declared
    check, which cares about "does this doc_id exist at all", not
    whether it has a real sha256 yet."""
    doc_ids = set()
    for yaml_path in sorted(SOURCES_DIR.glob("*.yaml")):
        with open(yaml_path) as f:
            data = yaml.safe_load(f) or {}
        for doc in data.get("documents", []):
            doc_ids.add(doc["doc_id"])
    return doc_ids


def load_manifest_doc_ids() -> set[str]:
    if not MANIFEST_PATH.exists():
        return set()
    with open(MANIFEST_PATH, newline="") as f:
        return {row["doc_id"] for row in csv.DictReader(f)}


def load_included_doc_ids() -> set[str]:
    if not ACQUISITION_LOG_PATH.exists():
        return set()
    text = ACQUISITION_LOG_PATH.read_text(encoding="utf-8")
    return set(INCLUDED_HEADING_RE.findall(text))


def load_metadata_doc_ids() -> set[str]:
    if not METADATA_DIR.exists():
        return set()
    return {p.stem for p in METADATA_DIR.glob("*.json")}


def load_metadata_chunk_counts() -> dict[str, int]:
    """doc_id -> chunking.total_chunks as recorded in metadata, only for
    documents that actually have a chunking block yet (chunk.py may not
    have run for every metadata record)."""
    counts = {}
    if not METADATA_DIR.exists():
        return counts
    for p in METADATA_DIR.glob("*.json"):
        with open(p, encoding="utf-8") as f:
            record = json.load(f)
        chunking = record.get("chunking")
        if chunking is not None:
            counts[p.stem] = chunking["total_chunks"]
    return counts


def load_actual_chunk_counts() -> dict[str, int]:
    if not CHUNKS_DIR.exists():
        return {}
    counts = {}
    for doc_dir in CHUNKS_DIR.iterdir():
        if doc_dir.is_dir():
            counts[doc_dir.name] = len(list(doc_dir.glob("*.json")))
    return counts


def load_derived_checksum_doc_ids() -> dict[str, str]:
    """doc_id -> org, for every doc_id with an entry in any
    corpus/derived-checksums/{org}.json."""
    doc_ids = {}
    if not DERIVED_CHECKSUMS_DIR.exists():
        return doc_ids
    for json_path in sorted(DERIVED_CHECKSUMS_DIR.glob("*.json")):
        org = json_path.stem
        data = load_derived_checksums(org)
        for doc_id in data:
            doc_ids[doc_id] = org
    return doc_ids


def check_declared_vs_acquired(problems: list[str]) -> None:
    declared = load_declared_real_sha256()
    acquired = load_manifest_doc_ids()

    for doc_id in sorted(set(declared) - acquired):
        problems.append(
            f"[declared-vs-acquired] {doc_id} — has a real sha256 in "
            f"corpus/sources/{declared[doc_id]}.yaml but is missing from "
            f"corpus/manifest.csv (a rerun may have failed to re-acquire "
            f"it, silently dropping it from the manifest — ADR-0007 "
            f"Finding 3b)."
        )
    for doc_id in sorted(acquired - set(declared)):
        problems.append(
            f"[declared-vs-acquired] {doc_id} — appears in "
            f"corpus/manifest.csv but has no matching real-sha256 entry "
            f"in corpus/sources/*.yaml (removed or reverted to "
            f"REPLACE_ME after acquisition?)."
        )


def check_included_vs_metadata(problems: list[str]) -> None:
    included = load_included_doc_ids()
    metadata = load_metadata_doc_ids()

    for doc_id in sorted(included - metadata):
        problems.append(
            f"[included-vs-metadata] {doc_id} — marked '## {doc_id} — "
            f"Included' in acquisition-log.md but has no "
            f"data/metadata/{doc_id}.json (run metadata.py, or check for "
            f"a heading-format typo that INCLUDED_HEADING_RE won't match "
            f"— ADR-0007 Finding 3a)."
        )
    for doc_id in sorted(metadata - included):
        problems.append(
            f"[included-vs-metadata] {doc_id} — has a "
            f"data/metadata/{doc_id}.json but no matching '## {doc_id} — "
            f"Included' heading in acquisition-log.md (removed from the "
            f"log after metadata was generated?)."
        )


def check_derived_checksums_vs_declared(problems: list[str]) -> None:
    derived = load_derived_checksum_doc_ids()
    declared = load_all_declared_doc_ids()

    for doc_id, org in sorted(derived.items()):
        if doc_id not in declared:
            problems.append(
                f"[derived-vs-declared] {doc_id} — has an entry in "
                f"corpus/derived-checksums/{org}.json but no matching "
                f"doc_id in corpus/sources/{org}.yaml (stale entry left "
                f"over from a removed or renamed document?)."
            )


def check_metadata_vs_chunks(problems: list[str]) -> None:
    metadata_counts = load_metadata_chunk_counts()
    actual_counts = load_actual_chunk_counts()

    for doc_id in sorted(set(metadata_counts) - set(actual_counts)):
        problems.append(
            f"[metadata-vs-chunks] {doc_id} — metadata.json records "
            f"chunking.total_chunks={metadata_counts[doc_id]} but "
            f"data/chunks/{doc_id}/ doesn't exist."
        )
    for doc_id in sorted(set(actual_counts) - set(metadata_counts)):
        problems.append(
            f"[metadata-vs-chunks] {doc_id} — has "
            f"{actual_counts[doc_id]} chunk file(s) in "
            f"data/chunks/{doc_id}/ but its metadata.json has no "
            f"chunking block yet (or no metadata.json at all)."
        )
    for doc_id in sorted(set(metadata_counts) & set(actual_counts)):
        if metadata_counts[doc_id] != actual_counts[doc_id]:
            problems.append(
                f"[metadata-vs-chunks] {doc_id} — metadata.json says "
                f"chunking.total_chunks={metadata_counts[doc_id]} but "
                f"data/chunks/{doc_id}/ actually has "
                f"{actual_counts[doc_id]} chunk file(s)."
            )


def main() -> None:
    problems: list[str] = []

    check_declared_vs_acquired(problems)
    check_included_vs_metadata(problems)
    check_derived_checksums_vs_declared(problems)
    check_metadata_vs_chunks(problems)

    if not problems:
        print("[ok] All corpus-state surfaces agree — no drift found.")
        return

    print(f"[drift] {len(problems)} disagreement(s) found:\n")
    for p in problems:
        print(f"  - {p}")
    print()
    sys.exit(1)


if __name__ == "__main__":
    main()
