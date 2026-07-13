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
non-empty — safe to rerun.

Connects to: reads from data/raw/ (immutable, never modified). Produces
data/processed/{org}/*.txt, consumed next by validate.py.

Usage:
    uv run python src/ingestion/extract.py
"""

import csv
import sys
from pathlib import Path

import pdfplumber

PROJECT_ROOT = Path(__file__).resolve().parents[2]
MANIFEST_PATH = PROJECT_ROOT / "corpus" / "manifest.csv"
PROCESSED_DIR = PROJECT_ROOT / "data" / "processed"


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


def extract_document(row: dict) -> bool:
    """Extract one document. Returns True on success, False on any failure
    (reported clearly, doesn't crash the run — other documents still get
    processed)."""
    doc_id = row["doc_id"]
    org = row["org"]
    raw_path = PROJECT_ROOT / row["local_path"]
    out_dir = PROCESSED_DIR / org
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / f"{doc_id}.txt"

    if out_path.exists() and out_path.stat().st_size > 0:
        print(f"[skip] {doc_id} — already extracted")
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
    return True


def main() -> None:
    rows = load_manifest()
    if not rows:
        print("Manifest is empty — nothing to extract.")
        return

    results = [extract_document(row) for row in rows]
    ok = sum(results)
    print(f"\n{ok}/{len(results)} document(s) extracted successfully.")


if __name__ == "__main__":
    main()
