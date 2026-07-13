"""
acquire.py — download source documents, verify checksums, archive to data/raw/.

Reads corpus/sources/*.yaml (one file per organization). Each YAML lists
documents that have already been selected for the corpus, per
docs/corpus-inclusion-rubric.md — this script doesn't decide what belongs
in the corpus, it only acquires and verifies what's already been declared.

Idempotent: rerunning skips any document already present in data/raw/ with
a matching checksum — safe to run again and again.

Two acquisition modes per document (the `acquisition` field in the source
YAML, default "auto"):

  auto   — acquire.py downloads it directly. One attempt, no retry loop.
           A tight retry loop against a 429 tends to make things worse, not
           better (it looks like abuse to whatever's rate-limiting you,
           and re-arms the cooldown) — so on a 429 or any other failure,
           this just reports it and moves on rather than hammering the
           server. Re-run the whole script later to try again.
  manual — the file is fetched by hand once (browser or a single curl) and
           placed at data/raw/{org}/{doc_id}.{ext}; acquire.py's job for
           this document is then just to verify its checksum, never to
           fetch it. This is the deliberate fallback for any source whose
           server treats scripted access as abuse — decided 2026-07 after
           OONI's server (Cloudflare-fronted) sustained a 429 against
           repeated Python requests for the exact same URL that a single
           manual curl had just fetched successfully seconds earlier.

Fails loudly (raises, non-zero exit) only for genuine integrity problems —
a present file whose checksum doesn't match what's declared. Missing
"auto" downloads or not-yet-placed "manual" files are reported clearly but
don't crash the run; other documents still get processed.

Usage:
    uv run python src/ingestion/acquire.py
"""

import csv
import hashlib
import sys
from pathlib import Path

import requests
import yaml

# Identify ourselves honestly to the (mostly small, nonprofit) servers this
# downloads from, rather than sending requests' generic default UA — same
# spirit as the citation/attribution discipline the rest of the project
# holds itself to. Full browser-like header set, since a bare UA override
# doesn't do much against CDN-level bot fingerprinting anyway.
HEADERS = {
    "User-Agent": "civil-liberties-knowledge-assistant/0.1 "
                  "(course project; contact via github.com/Sanjomwa)",
    "Accept": "application/pdf,text/html,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9",
}

PROJECT_ROOT = Path(__file__).resolve().parents[2]
SOURCES_DIR = PROJECT_ROOT / "corpus" / "sources"
RAW_DIR = PROJECT_ROOT / "data" / "raw"
MANIFEST_PATH = PROJECT_ROOT / "corpus" / "manifest.csv"
CHECKSUMS_PATH = PROJECT_ROOT / "corpus" / "checksums.sha256"

MANIFEST_FIELDS = [
    "doc_id", "org", "title", "countries", "publication_date", "sha256", "local_path",
]


def sha256_of(path: Path) -> str:
    """Compute the SHA-256 hex digest of a file, reading in chunks (safe for large PDFs)."""
    digest = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(8192), b""):
            digest.update(chunk)
    return digest.hexdigest()


def looks_like_declared_format(path: Path, source_format: str) -> bool:
    """
    Cheap sanity check independent of the checksum: does the file's magic
    number actually match what it claims to be? A checksum only proves
    "these are the bytes we expected" — it says nothing about whether those
    bytes are actually a valid file of the declared format. Added after a
    real incident (2026-07-13): a bot-challenge HTML page (Vercel Security
    Checkpoint) got saved as a .pdf by curl, with a 200 status and no error,
    and its checksum then matched itself consistently across every later
    check — this is the check that would have caught it immediately
    instead of two stages later, in extract.py.
    """
    if source_format == "pdf":
        with open(path, "rb") as f:
            header = f.read(5)
        return header == b"%PDF-"

    if source_format == "html":
        # There's no magic-number equivalent for HTML — a bot-challenge page
        # and a real article are both structurally valid HTML. The only
        # signal available is content: check for known challenge phrases.
        # Not exhaustive (challenge pages vary and this list will need
        # updating as new ones are hit), but it catches the two distinct
        # challenge mechanisms this project has already run into on ooni.org
        # alone (a "Vercel Security Checkpoint" page and a separate
        # "verifying your browser" / "enable JavaScript to continue" page).
        challenge_phrases = [
            "verifying your browser",
            "enable javascript to continue",
            "checking your browser",
            "security checkpoint",
            "just a moment",
        ]
        text = path.read_text(encoding="utf-8", errors="replace").lower()
        return not any(phrase in text for phrase in challenge_phrases)

    return True


def load_sources():
    """Yield (org, document_dict) for every document declared across corpus/sources/*.yaml."""
    for yaml_path in sorted(SOURCES_DIR.glob("*.yaml")):
        org = yaml_path.stem
        with open(yaml_path) as f:
            data = yaml.safe_load(f) or {}
        for doc in data.get("documents", []):
            yield org, doc


def acquire_document(org: str, doc: dict):
    """
    Handle one document. Returns a manifest row (dict) on success, or None
    if it's not ready yet (auto download failed this run, or a manual file
    hasn't been placed yet) — neither of those crashes the whole run.
    Raises only on a genuine checksum mismatch against a present file.
    """
    doc_id = doc["doc_id"]
    expected_sha256 = doc["sha256"]
    url = doc["url"]
    ext = "pdf" if doc["source_format"] == "pdf" else "html"
    mode = doc.get("acquisition", "auto")

    if expected_sha256.startswith("REPLACE_ME"):
        raise ValueError(
            f"{doc_id}: corpus/sources/{org}.yaml still has a placeholder "
            f"sha256. Get the real file once by hand, compute its checksum, "
            f"and put that in the YAML before running this script."
        )

    org_dir = RAW_DIR / org
    org_dir.mkdir(parents=True, exist_ok=True)
    dest = org_dir / f"{doc_id}.{ext}"

    if dest.exists():
        actual = sha256_of(dest)
        if actual == expected_sha256:
            if not looks_like_declared_format(dest, doc["source_format"]):
                raise ValueError(
                    f"{doc_id}: checksum matches, but the file doesn't look "
                    f"like a real {doc['source_format']} (bad magic number). "
                    f"Likely a blocked-request or challenge page saved by "
                    f"mistake, with a checksum that's now just consistently "
                    f"re-verifying the wrong file — replace it with the real "
                    f"one and update sha256 in corpus/sources/{org}.yaml."
                )
            print(f"[skip] {doc_id} — already present, checksum matches")
            return {**doc, "org": org, "local_path": str(dest.relative_to(PROJECT_ROOT))}
        if mode == "manual":
            raise ValueError(
                f"Checksum mismatch for {doc_id} (manual acquisition): "
                f"expected {expected_sha256}, got {actual}. The file at "
                f"{dest} doesn't match what was declared — check it's the "
                f"right file before re-running."
            )
        print(f"[redownload] {doc_id} — present but checksum mismatch, refetching")

    if mode == "manual":
        print(
            f"[pending] {doc_id} — manual acquisition, not yet placed. "
            f"Download {url} by hand and save it to "
            f"{dest.relative_to(PROJECT_ROOT)}, then re-run this script."
        )
        return None

    print(f"[download] {doc_id} <- {url}")
    try:
        response = requests.get(url, headers=HEADERS, timeout=30)
        response.raise_for_status()
    except requests.exceptions.RequestException as e:
        print(
            f"[fail] {doc_id} — {e}. Not retrying in a loop (that tends to "
            f"make rate-limiting worse, not better) — re-run the whole "
            f"script later, or mark this document `acquisition: manual` in "
            f"corpus/sources/{org}.yaml and place the file by hand.",
            file=sys.stderr,
        )
        return None

    tmp_path = dest.with_suffix(dest.suffix + ".tmp")
    tmp_path.write_bytes(response.content)

    actual_sha256 = sha256_of(tmp_path)
    if actual_sha256 != expected_sha256:
        tmp_path.unlink()
        raise ValueError(
            f"Checksum mismatch for {doc_id}: expected {expected_sha256}, "
            f"got {actual_sha256}. The source file may have changed since "
            f"it was selected, or the download was corrupted. Not writing "
            f"to data/raw/ — investigate before re-running."
        )
    if not looks_like_declared_format(tmp_path, doc["source_format"]):
        tmp_path.unlink()
        raise ValueError(
            f"{doc_id}: downloaded content doesn't look like a real "
            f"{doc['source_format']} (bad magic number) — likely a "
            f"blocked-request or bot-challenge page served with a 200 "
            f"status instead of the real file. Not writing to data/raw/."
        )

    tmp_path.rename(dest)
    print(f"[ok] {doc_id} — downloaded and verified ({len(response.content)} bytes)")
    return {**doc, "org": org, "local_path": str(dest.relative_to(PROJECT_ROOT))}


def write_manifest(rows: list[dict]) -> None:
    """Regenerate corpus/manifest.csv from scratch. Generated, never hand-edited."""
    MANIFEST_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(MANIFEST_PATH, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=MANIFEST_FIELDS)
        writer.writeheader()
        for row in rows:
            writer.writerow({
                "doc_id": row["doc_id"],
                "org": row["org"],
                "title": row["title"],
                "countries": ",".join(row["countries"]),
                "publication_date": row["publication_date"],
                "sha256": row["sha256"],
                "local_path": row["local_path"],
            })
    print(f"[manifest] wrote {len(rows)} row(s) to {MANIFEST_PATH.relative_to(PROJECT_ROOT)}")


def write_checksums(rows: list[dict]) -> None:
    """Regenerate corpus/checksums.sha256 from scratch — SHA-256 of every file in data/raw/."""
    CHECKSUMS_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(CHECKSUMS_PATH, "w") as f:
        for row in rows:
            f.write(f"{row['sha256']}  {row['local_path']}\n")
    plural = "y" if len(rows) == 1 else "ies"
    print(f"[checksums] wrote {len(rows)} entr{plural} to {CHECKSUMS_PATH.relative_to(PROJECT_ROOT)}")


def main() -> None:
    rows = []
    pending = 0
    for org, doc in load_sources():
        try:
            row = acquire_document(org, doc)
        except Exception as e:
            print(f"[FAIL] {doc.get('doc_id', '?')}: {e}", file=sys.stderr)
            sys.exit(1)
        if row is None:
            pending += 1
        else:
            rows.append(row)

    if not rows and not pending:
        print("No documents declared in corpus/sources/*.yaml — nothing to do.")
        return

    # Always regenerate from whatever succeeded THIS run, even if that's
    # zero rows — a stale manifest from a previous run (pointing at a file
    # or format that's no longer accurate) is worse than an empty one, and
    # downstream scripts (extract.py, validate.py) should never be trusting
    # leftovers from an earlier, different state of data/raw/.
    write_manifest(rows)
    write_checksums(rows)

    print(
        f"\nDone — {len(rows)} document(s) verified and in the manifest, "
        f"{pending} still pending (not yet downloaded or not yet placed "
        f"for manual acquisition)."
    )


if __name__ == "__main__":
    main()
