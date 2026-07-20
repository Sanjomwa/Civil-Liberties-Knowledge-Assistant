"""
extract.py — turn acquired raw files into plain text.

Reads corpus/manifest.csv (the unified view of documents acquire.py has
successfully acquired) and, for each row, extracts plain text from the
raw file: PDF via pdfplumber, HTML via trafilatura. Writes the result to
data/processed/{org}/{doc_id}.txt.

Does not clean the text — that's a later stage's job. Does not attempt
OCR — a PDF with no extractable text layer (scanned pages, images only)
is reported as an extraction failure, not silently skipped and not OCR'd
(out of scope for v1, per the architecture).

Idempotent: skips any document whose output .txt already exists and is
non-empty — safe to rerun. The `content_sha256` bootstrap/compare step
below (ADR-0005) still runs on the skip path, though — it isn't the
extraction itself, and the 4 already-extracted 2024 Freedom House
documents need it backfilled from their existing .txt, not re-extracted.

Connects to: reads from data/raw/ (immutable, never modified). Produces
data/processed/{org}/*.txt, consumed next by validate.py.

Content checksum (ADR-0005, 2026-07-20): for sources whose raw bytes
aren't stable (Freedom House, currently — CDN-injected per-request
randomness in the markup, see acquire.py's module docstring), a raw-byte
checksum can never verify live-source fidelity. `content_sha256` is the
mechanism that actually can: a SHA-256 of this module's own canonicalized
extracted text, which strips scripts/markup/links and is therefore immune
to the markup-level randomness that defeats a raw-byte hash. Tracked for
every document belonging to an org whose YAML declares
`raw_bytes_stable: false` at the top level (ADR-0007, 2026-07-20 —
previously gated by a per-document `content_sha256` field in the YAML
itself; simplified to an org-level check since ADR-0005 always intended
this "required for every entry" in a volatile org, never a genuine
per-document opt-in). Same bootstrap pattern as acquire.py's `sha256`:
absent records a new baseline, a real recorded value gets compared, and a
mismatch is a real content-drift signal — logged to
corpus/acquisition-log.md (ADR-0007; previously only printed to stderr,
which meant the signal never actually reached the Tier-2-style human
review ADR-0005 itself said it should) as well as printed as an
immediate warning. It never fails the run.

Page-level provenance (ADR-0008, 2026-07-20): for PDF sources,
extract_pdf_text() now also returns a page-breakpoint list (see
pages.py) — the true PDF page number and character range each page of
extracted text occupies in the final joined string. Written to a
sidecar file, data/processed/{org}/{doc_id}.pages.json, so chunk.py can
later resolve which page(s) a given chunk came from. HTML/JSON sources
have no page concept; no sidecar is written for them.

Usage:
    uv run python src/ingestion/extract.py
"""

import csv
import hashlib
import sys
from datetime import date
from pathlib import Path

import pdfplumber
import yaml

sys.path.insert(0, str(Path(__file__).resolve().parent))
from acquire import (  # noqa: E402 — needs sys.path set first
    load_derived_checksums,
    resolve_legacy_content_sha256,
    write_derived_checksum,
)
from pages import pages_sidecar_path, write_pages_sidecar  # noqa: E402

PROJECT_ROOT = Path(__file__).resolve().parents[2]
MANIFEST_PATH = PROJECT_ROOT / "corpus" / "manifest.csv"
PROCESSED_DIR = PROJECT_ROOT / "data" / "processed"
SOURCES_DIR = PROJECT_ROOT / "corpus" / "sources"
ACQUISITION_LOG_PATH = PROJECT_ROOT / "corpus" / "acquisition-log.md"


def load_manifest() -> list[dict]:
    if not MANIFEST_PATH.exists():
        print(
            f"No manifest at {MANIFEST_PATH.relative_to(PROJECT_ROOT)} — "
            f"run acquire.py first.",
            file=sys.stderr,
        )
        sys.exit(1)
    with open(MANIFEST_PATH, newline="") as f:
        return list(csv.DictReader(f))


def load_content_checksum_orgs() -> set[str]:
    """Which orgs declare raw_bytes_stable: false at the YAML top level
    (ADR-0007) — every document belonging to one of these orgs gets
    content_sha256 tracked; every other org gets none. Simpler and more
    accurate than the old per-document field check, since ADR-0005
    always intended this org-wide, never a genuine per-document opt-in."""
    orgs = set()
    for yaml_path in sorted(SOURCES_DIR.glob("*.yaml")):
        with open(yaml_path) as f:
            data = yaml.safe_load(f) or {}
        if data.get("raw_bytes_stable", True) is False:
            orgs.add(yaml_path.stem)
    return orgs


def append_content_drift_flag(doc_id: str, expected: str, actual: str) -> None:
    """ADR-0007: a content_sha256 mismatch is a real Tier-2-style signal
    (ADR-0005's own stated design) and needs a durable, greppable record
    — not just a stderr print that vanishes with the terminal scrollback.
    Prefixed distinctly from Tier 1 exclusions and acquire.py failures so
    it's easy to find on its own."""
    ACQUISITION_LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
    is_new = not ACQUISITION_LOG_PATH.exists()
    with open(ACQUISITION_LOG_PATH, "a", encoding="utf-8") as f:
        if is_new:
            f.write("# Acquisition Log\n\n")
            f.write(
                "Every document encountered during corpus construction, "
                "included or not, with the reason. Tier 1 exclusions below "
                "are written automatically by validate.py — they're facts, "
                "not judgments. Inclusion/exclusion after a Tier 2 flag or "
                "the semantic review is a human call, added by hand per "
                "docs/corpus-inclusion-rubric.md.\n\n"
            )
        f.write(
            f"- **{doc_id}** — content-drift flagged "
            f"({date.today().isoformat()}): content_sha256 mismatch, "
            f"expected {expected}, got {actual}. Needs human review "
            f"(ADR-0005/ADR-0007) — also surfaced as a Tier 2 flag by "
            f"validate.py.\n"
        )


def canonicalize_for_hash(text: str) -> str:
    """Canonicalization applied before hashing extracted text (ADR-0005
    decision #2): normalize line endings only. Deliberately does NOT
    lowercase, strip whitespace runs, or otherwise touch real content —
    the goal is removing incidental encoding/line-ending variance, not
    destroying a genuine content-drift signal."""
    return text.replace("\r\n", "\n").replace("\r", "\n")


def content_sha256_of(text: str) -> str:
    return hashlib.sha256(canonicalize_for_hash(text).encode("utf-8")).hexdigest()


def check_content_checksum(doc_id: str, org: str, text: str,
                            content_checksum_orgs: set[str]) -> None:
    """ADR-0005 + ADR-0007: if this document's org declares
    raw_bytes_stable: false, bootstrap (no prior value -> record) or
    verify (prior value -> compare, warn on mismatch — never fail the
    run) against the canonicalized extracted text. No-op for every org
    not in content_checksum_orgs, which is the normal case for every org
    except Freedom House. Bootstrap/compare value now lives in
    corpus/derived-checksums/{org}.json (ADR-0007), not the source YAML
    — it's derived data, never a human declaration."""
    if org not in content_checksum_orgs:
        return
    actual = content_sha256_of(text)
    derived = load_derived_checksums(org)
    expected = derived.get(doc_id, {}).get("content_sha256")
    if expected is None:
        # ADR-0007 migration: a real baseline may already exist in the
        # source YAML from before this fix (extract.py's original
        # ADR-0005 implementation wrote it there). Check before treating
        # this as a genuinely new document.
        expected = resolve_legacy_content_sha256(org, doc_id)

    if expected is None:
        write_derived_checksum(org, doc_id, "content_sha256", actual)
        print(f"[content-checksum] {doc_id} — bootstrapped content_sha256 {actual}")
        return

    if actual != expected:
        print(
            f"[content-drift] {doc_id} — content_sha256 mismatch: expected "
            f"{expected}, got {actual}. The source's actual content may "
            f"have changed since this was recorded — not failing the run, "
            f"but this needs a human look (ADR-0005).",
            file=sys.stderr,
        )
        append_content_drift_flag(doc_id, expected, actual)


def extract_pdf_text(path: Path) -> tuple[str, list[dict]]:
    """ADR-0008: also returns a page-breakpoint list — each included
    page's true PDF page number (pdfplumber's own page.page_number,
    1-indexed, immune to the skipped-blank-page off-by-one) paired with
    its exact character range in the joined output. char_end is computed
    before the "\\n\\n" joiner is added, so a page's range covers only
    its own real extracted content."""
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


def extract_html_text(path: Path) -> str:
    import trafilatura

    html = path.read_text(encoding="utf-8", errors="replace")
    text = trafilatura.extract(html) or ""
    return text.strip()


def extract_json_text(path: Path) -> str:
    """Added 2026-07-20 for OONI's "Findings" platform documents (see
    acquire.py's looks_like_declared_format, source_format == "json"
    branch, for the matching acquisition-side check). The public page is a
    JS-rendered SPA with nothing extractable in its raw HTML; the same
    content is available as JSON from a documented API endpoint, with a
    "text" field holding the full report body as markdown (headings,
    links, and a few custom <MAT .../> chart-embed tags mixed in). No
    markdown-to-plaintext conversion here — chunk.py works on raw text for
    every other format too, and stripping markdown risks losing structure
    (headings, list items) that's meaningful in the source itself."""
    import json

    data = json.loads(path.read_text(encoding="utf-8", errors="replace"))
    return data.get("incident", {}).get("text", "").strip()


def extract_document(row: dict, content_checksum_orgs: set[str]) -> bool:
    """Extract one document. Returns True on success, False on any failure
    (reported clearly, doesn't crash the run — other documents still get
    processed). Runs the ADR-0005/ADR-0007 content_sha256 bootstrap/compare
    step (`check_content_checksum`) on every success path, including the
    skip path — a document whose .txt already exists still needs that
    step, not just fresh extractions.

    ADR-0008: a PDF-sourced document only counts as "already extracted"
    (skippable) if its .pages.json sidecar also exists — a .txt written
    before ADR-0008 landed has no page data yet, so it's forced through
    re-extraction once, self-migrating the corpus rather than needing a
    one-off backfill script. Non-PDF sources are unaffected."""
    doc_id = row["doc_id"]
    org = row["org"]
    raw_path = PROJECT_ROOT / row["local_path"]
    out_dir = PROCESSED_DIR / org
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / f"{doc_id}.txt"
    is_pdf = raw_path.suffix.lower() == ".pdf"
    sidecar_path = pages_sidecar_path(PROCESSED_DIR, org, doc_id)

    already_extracted = out_path.exists() and out_path.stat().st_size > 0
    needs_pages_backfill = is_pdf and not sidecar_path.exists()

    if already_extracted and not needs_pages_backfill:
        print(f"[skip] {doc_id} — already extracted")
        check_content_checksum(doc_id, org, out_path.read_text(encoding="utf-8"), content_checksum_orgs)
        return True

    if already_extracted and needs_pages_backfill:
        print(f"[re-extract] {doc_id} — pre-ADR-0008 .txt has no page sidecar, re-extracting")

    if not raw_path.exists():
        print(
            f"[fail] {doc_id} — raw file missing at {raw_path}, "
            f"run acquire.py first",
            file=sys.stderr,
        )
        return False

    suffix = raw_path.suffix.lower()
    breakpoints = None
    try:
        if suffix == ".pdf":
            text, breakpoints = extract_pdf_text(raw_path)
        elif suffix in (".html", ".htm"):
            text = extract_html_text(raw_path)
        elif suffix == ".json":
            text = extract_json_text(raw_path)
        else:
            print(f"[fail] {doc_id} — unsupported format {suffix}", file=sys.stderr)
            return False
    except Exception as e:
        print(f"[fail] {doc_id} — extraction error: {e}", file=sys.stderr)
        return False

    if not text:
        print(
            f"[fail] {doc_id} — no extractable text (scanned/image-only "
            f"PDF? OCR is out of scope for v1). Not writing an empty file.",
            file=sys.stderr,
        )
        return False

    out_path.write_text(text, encoding="utf-8")
    word_count = len(text.split())
    print(f"[ok] {doc_id} — extracted {word_count} words to {out_path.relative_to(PROJECT_ROOT)}")

    if breakpoints is not None:
        write_pages_sidecar(sidecar_path, breakpoints)
        print(f"[ok] {doc_id} — wrote {len(breakpoints)} page breakpoint(s) to {sidecar_path.relative_to(PROJECT_ROOT)}")

    check_content_checksum(doc_id, org, text, content_checksum_orgs)
    return True


def main() -> None:
    rows = load_manifest()
    if not rows:
        print("Manifest is empty — nothing to extract.")
        return

    content_checksum_orgs = load_content_checksum_orgs()
    results = [extract_document(row, content_checksum_orgs) for row in rows]
    ok = sum(results)
    print(f"\n{ok}/{len(results)} document(s) extracted successfully.")


if __name__ == "__main__":
    main()
