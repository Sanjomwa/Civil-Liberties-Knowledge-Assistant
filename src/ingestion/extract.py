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
to the markup-level randomness that defeats a raw-byte hash. Declared per
document in corpus/sources/{org}.yaml — most orgs won't have the field at
all, which just means there's nothing to bootstrap or verify for them.
Same bootstrap pattern as acquire.py's `sha256`: `REPLACE_ME` records a
new baseline, a real declared value gets compared, and a mismatch is a
real content-drift signal that's printed as a warning, not something that
fails the run.

Usage:
    uv run python src/ingestion/extract.py
"""

import csv
import hashlib
import sys
from pathlib import Path

import pdfplumber
import yaml

sys.path.insert(0, str(Path(__file__).resolve().parent))
from acquire import write_yaml_field  # noqa: E402 — needs sys.path set first

PROJECT_ROOT = Path(__file__).resolve().parents[2]
MANIFEST_PATH = PROJECT_ROOT / "corpus" / "manifest.csv"
PROCESSED_DIR = PROJECT_ROOT / "data" / "processed"
SOURCES_DIR = PROJECT_ROOT / "corpus" / "sources"


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


def load_content_sha256_declarations() -> dict[str, tuple[str, str]]:
    """Map doc_id -> (org, declared content_sha256) for every document that
    declares the field in corpus/sources/*.yaml (ADR-0005). Most orgs won't
    have it at all — absence means nothing to bootstrap or verify for that
    document, not an error. Loaded the same way acquire.py's own
    load_sources() reads these files."""
    declarations = {}
    for yaml_path in sorted(SOURCES_DIR.glob("*.yaml")):
        org = yaml_path.stem
        with open(yaml_path) as f:
            data = yaml.safe_load(f) or {}
        for doc in data.get("documents", []):
            if "content_sha256" in doc:
                declarations[doc["doc_id"]] = (org, doc["content_sha256"])
    return declarations


def canonicalize_for_hash(text: str) -> str:
    """Canonicalization applied before hashing extracted text (ADR-0005
    decision #2): normalize line endings only. Deliberately does NOT
    lowercase, strip whitespace runs, or otherwise touch real content —
    the goal is removing incidental encoding/line-ending variance, not
    destroying a genuine content-drift signal."""
    return text.replace("\r\n", "\n").replace("\r", "\n")


def content_sha256_of(text: str) -> str:
    return hashlib.sha256(canonicalize_for_hash(text).encode("utf-8")).hexdigest()


def check_content_checksum(doc_id: str, text: str,
                            declarations: dict[str, tuple[str, str]]) -> None:
    """ADR-0005: if this doc_id declares a content_sha256 in its org's
    YAML, bootstrap (REPLACE_ME -> record) or verify (real value ->
    compare, warn on mismatch — never fail the run) against the
    canonicalized extracted text. No-op if the doc_id declares nothing,
    which is the normal case for every org except Freedom House."""
    declared = declarations.get(doc_id)
    if declared is None:
        return
    org, expected = declared
    actual = content_sha256_of(text)

    if expected == "REPLACE_ME":
        write_yaml_field(org, doc_id, "content_sha256", actual)
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


def extract_pdf_text(path: Path) -> str:
    pages = []
    with pdfplumber.open(path) as pdf:
        for page in pdf.pages:
            text = page.extract_text()
            if text:
                pages.append(text)
    return "\n\n".join(pages).strip()


def extract_html_text(path: Path) -> str:
    import trafilatura

    html = path.read_text(encoding="utf-8", errors="replace")
    text = trafilatura.extract(html) or ""
    return text.strip()


def extract_document(row: dict, declarations: dict[str, tuple[str, str]]) -> bool:
    """Extract one document. Returns True on success, False on any failure
    (reported clearly, doesn't crash the run — other documents still get
    processed). Runs the ADR-0005 content_sha256 bootstrap/compare step
    (`check_content_checksum`) on every success path, including the skip
    path — a document whose .txt already exists still needs that step,
    not just fresh extractions, so the 4 already-extracted 2024 Freedom
    House documents get backfilled rather than silently skipped."""
    doc_id = row["doc_id"]
    org = row["org"]
    raw_path = PROJECT_ROOT / row["local_path"]
    out_dir = PROCESSED_DIR / org
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / f"{doc_id}.txt"

    if out_path.exists() and out_path.stat().st_size > 0:
        print(f"[skip] {doc_id} — already extracted")
        check_content_checksum(doc_id, out_path.read_text(encoding="utf-8"), declarations)
        return True

    if not raw_path.exists():
        print(
            f"[fail] {doc_id} — raw file missing at {raw_path}, "
            f"run acquire.py first",
            file=sys.stderr,
        )
        return False

    suffix = raw_path.suffix.lower()
    try:
        if suffix == ".pdf":
            text = extract_pdf_text(raw_path)
        elif suffix in (".html", ".htm"):
            text = extract_html_text(raw_path)
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
    check_content_checksum(doc_id, text, declarations)
    return True


def main() -> None:
    rows = load_manifest()
    if not rows:
        print("Manifest is empty — nothing to extract.")
        return

    declarations = load_content_sha256_declarations()
    results = [extract_document(row, declarations) for row in rows]
    ok = sum(results)
    print(f"\n{ok}/{len(results)} document(s) extracted successfully.")


if __name__ == "__main__":
    main()
