"""
metadata.py — build data/metadata/{doc_id}.json for every Included document.

Reads corpus/sources/*.yaml for declared fields (the same single source of
truth acquire.py reads from), and corpus/acquisition-log.md for which
documents a human has actually marked "Included" per
docs/corpus-inclusion-rubric.md — metadata.py never makes an inclusion
judgment itself, it only acts on a decision already recorded there.

For each included document, computes derived fields from the extracted
text (data/processed/{org}/{doc_id}.txt) and the raw file
(data/raw/{org}/{doc_id}.{ext}), and writes the merged record to
data/metadata/{doc_id}.json — schema_version 1.1 per ADR-0003 (declared +
derived + lifecycle blocks). The chunking block is intentionally not
written here — it doesn't exist yet at this point in the pipeline, and
gets added later by chunk.py, once chunking has actually happened.

Language/word-count source (ADR-0007, 2026-07-20): these used to be
computed here a second time, independently of validate.py's own Tier 2
langdetect call — two separate detectors, on the same text, that could
in principle disagree with no error raised (a bug found in the
end-of-ingestion-phase Opus+Fable review — see decisionlog.md). This
module now reads corpus/validation-results.json (written by validate.py)
instead of calling langdetect itself, so the two stages can never
quietly diverge on the same fact. A document marked Included in
acquisition-log.md that has no matching validation-results.json entry
(or whose Tier 1 failed) is a hard failure here, not a silent skip —
that combination means validate.py hasn't actually been run (or rerun)
against the current corpus state, which the pipeline should never paper
over.

Idempotent: rerunning regenerates every included document's metadata file
from scratch — a metadata file with a since-changed source YAML or
re-extracted text should never carry stale derived facts forward.

Usage:
    uv run python src/ingestion/metadata.py
"""

import json
import re
import sys
from datetime import date
from pathlib import Path

import yaml

PROJECT_ROOT = Path(__file__).resolve().parents[2]
SOURCES_DIR = PROJECT_ROOT / "corpus" / "sources"
RAW_DIR = PROJECT_ROOT / "data" / "raw"
PROCESSED_DIR = PROJECT_ROOT / "data" / "processed"
METADATA_DIR = PROJECT_ROOT / "data" / "metadata"
ACQUISITION_LOG_PATH = PROJECT_ROOT / "corpus" / "acquisition-log.md"
VALIDATION_RESULTS_PATH = PROJECT_ROOT / "corpus" / "validation-results.json"

SCHEMA_VERSION = "1.1"

# Matches this project's own acquisition-log.md heading convention, e.g.
# "## ooni-tz-2025-x-platform-blocking — Included". Deliberately anchored
# to "Included" only — an "Excluded" heading (Tier 1 automatic, or human
# semantic review) must never produce a metadata record.
INCLUDED_HEADING_RE = re.compile(r"^## (\S+) — Included\s*$", re.MULTILINE)


def load_sources() -> dict:
    """doc_id -> (org, declared_dict) for every document declared across corpus/sources/*.yaml."""
    docs = {}
    for yaml_path in sorted(SOURCES_DIR.glob("*.yaml")):
        org = yaml_path.stem
        with open(yaml_path) as f:
            data = yaml.safe_load(f) or {}
        for doc in data.get("documents", []):
            docs[doc["doc_id"]] = (org, doc)
    return docs


def included_doc_ids() -> set:
    """
    Which doc_ids a human has actually marked Included in
    corpus/acquisition-log.md. metadata.py doesn't judge topic relevance or
    coverage contribution itself — docs/corpus-inclusion-rubric.md is
    explicit that's a human call, logged by hand. This just reads that
    record rather than re-deciding anything.
    """
    if not ACQUISITION_LOG_PATH.exists():
        print(
            f"No {ACQUISITION_LOG_PATH.relative_to(PROJECT_ROOT)} yet — "
            f"nothing has been marked Included. Run validate.py, do the "
            f"semantic review per docs/corpus-inclusion-rubric.md, and log "
            f"the decision there before running this script.",
            file=sys.stderr,
        )
        return set()
    text = ACQUISITION_LOG_PATH.read_text(encoding="utf-8")
    return set(INCLUDED_HEADING_RE.findall(text))


def load_validation_results() -> dict:
    """ADR-0007: the single source of truth for language/word-count facts,
    written by validate.py. Missing entirely means validate.py hasn't been
    run yet against the current manifest."""
    if not VALIDATION_RESULTS_PATH.exists():
        print(
            f"No {VALIDATION_RESULTS_PATH.relative_to(PROJECT_ROOT)} yet — "
            f"run validate.py before metadata.py (ADR-0007: metadata.py no "
            f"longer computes language/word-count itself).",
            file=sys.stderr,
        )
        sys.exit(1)
    with open(VALIDATION_RESULTS_PATH, encoding="utf-8") as f:
        return json.load(f)


def build_declared(doc: dict) -> dict:
    # Only the fields the architecture's metadata schema actually specifies
    # under "declared". corpus/sources/*.yaml also carries a couple of
    # pipeline-only fields (like `acquisition`) that steer acquire.py but
    # aren't part of the metadata record itself.
    return {
        "title": doc["title"],
        "organization": doc["organization"],
        "countries": doc["countries"],
        "publication_date": doc["publication_date"],
        "url": doc["url"],
        "doc_type": doc["doc_type"],
        "source_format": doc["source_format"],
        "topics": doc["topics"],
        "language": doc["language"],
        "selection_rationale": " ".join(doc["selection_rationale"].split()),
        "corpus_version": doc["corpus_version"],
    }


def build_derived(org: str, doc: dict, doc_id: str, validation_results: dict) -> dict:
    # Mirrors acquire.py's own extension-resolution dict exactly (2026-07-20:
    # added "json" for OONI's Findings-platform documents — see acquire.py's
    # acquire_document() and extract.py's extract_json_text() for the other
    # two places this same mapping needed to exist. Missed here on first
    # pass, causing metadata.py to look for a nonexistent .html file for
    # ooni-ug-2026-election-shutdown-and-blocking — see decisionlog.md,
    # 2026-07-20, for the incident this comment is here to prevent repeating).
    ext = {"pdf": "pdf", "json": "json"}.get(doc["source_format"], "html")
    raw_path = RAW_DIR / org / f"{doc_id}.{ext}"
    processed_path = PROCESSED_DIR / org / f"{doc_id}.txt"

    if not raw_path.exists():
        raise FileNotFoundError(
            f"{doc_id}: expected raw file at "
            f"{raw_path.relative_to(PROJECT_ROOT)}, not found. Run "
            f"acquire.py first."
        )
    if not processed_path.exists():
        raise FileNotFoundError(
            f"{doc_id}: expected extracted text at "
            f"{processed_path.relative_to(PROJECT_ROOT)}, not found. Run "
            f"extract.py first."
        )

    # ADR-0007: language/word-count come from validate.py's own recorded
    # result, not a second independent langdetect call here. An Included
    # document with no result, or one whose Tier 1 didn't pass, means
    # validate.py hasn't actually been (re)run against the current corpus
    # state — a real gap, not something to paper over with a fallback.
    result = validation_results.get(doc_id)
    if result is None:
        raise FileNotFoundError(
            f"{doc_id}: marked Included but has no entry in "
            f"{VALIDATION_RESULTS_PATH.relative_to(PROJECT_ROOT)}. Run "
            f"validate.py first (or rerun it — the manifest/corpus may "
            f"have changed since it last ran)."
        )
    if not result.get("tier1_passed"):
        raise FileNotFoundError(
            f"{doc_id}: marked Included, but validate.py recorded a Tier 1 "
            f"failure for it ({result.get('tier1')}). That's a "
            f"contradiction — either the Included decision or the Tier 1 "
            f"result is stale. Resolve before generating metadata."
        )
    tier2 = result["tier2"]
    word_count = tier2["word_count"]
    detected_language = tier2["language"]
    detected_language_confidence = tier2.get("language_confidence", 0.0)

    extraction_method = {
        "pdf": "pdfplumber",
        "json": "json-field-extraction",
    }.get(doc["source_format"], "trafilatura")
    # The processed file's own mtime reflects when extract.py actually ran,
    # which is more accurate than "whenever metadata.py happens to run".
    extraction_date = date.fromtimestamp(processed_path.stat().st_mtime).isoformat()

    warnings = list(result.get("tier2_flags", []))

    return {
        "sha256": doc["sha256"],
        "file_size_bytes": raw_path.stat().st_size,
        "extracted_word_count": word_count,
        "extraction_method": extraction_method,
        "extraction_date": extraction_date,
        "detected_language": detected_language,
        "detected_language_confidence": detected_language_confidence,
        "validation_status": "valid" if not warnings else "valid_with_warnings",
        "validation_warnings": warnings,
    }


def build_lifecycle() -> dict:
    # Default per ADR-0003 — every document starts "active"; no backfill
    # needed since nothing predates this schema version in this corpus.
    return {
        "status": "active",
        "superseded_by": None,
        "supersedes": None,
        "reason": None,
        "effective_date": None,
    }


def write_metadata_record(doc_id: str, org: str, doc: dict, validation_results: dict) -> Path:
    record = {
        "doc_id": doc_id,
        "schema_version": SCHEMA_VERSION,
        "declared": build_declared(doc),
        "derived": build_derived(org, doc, doc_id, validation_results),
        "lifecycle": build_lifecycle(),
    }
    METADATA_DIR.mkdir(parents=True, exist_ok=True)
    out_path = METADATA_DIR / f"{doc_id}.json"
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(record, f, indent=2, ensure_ascii=False)
        f.write("\n")
    return out_path


def main() -> None:
    declared_docs = load_sources()
    included = included_doc_ids()

    if not included:
        print("No documents marked Included yet — nothing to do.")
        return

    validation_results = load_validation_results()

    written = 0
    for doc_id in sorted(included):
        if doc_id not in declared_docs:
            print(
                f"[FAIL] {doc_id} — marked Included in "
                f"{ACQUISITION_LOG_PATH.relative_to(PROJECT_ROOT)} but not "
                f"declared in any corpus/sources/*.yaml. Check for a typo "
                f"in either file.",
                file=sys.stderr,
            )
            sys.exit(1)
        org, doc = declared_docs[doc_id]
        try:
            out_path = write_metadata_record(doc_id, org, doc, validation_results)
        except FileNotFoundError as e:
            print(f"[FAIL] {e}", file=sys.stderr)
            sys.exit(1)
        print(f"[ok] {doc_id} — wrote {out_path.relative_to(PROJECT_ROOT)}")
        written += 1

    print(
        f"\nDone — {written} document(s) written to "
        f"{METADATA_DIR.relative_to(PROJECT_ROOT)}."
    )


if __name__ == "__main__":
    main()
