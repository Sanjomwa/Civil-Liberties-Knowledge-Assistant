"""
acquire.py — download source documents, verify checksums, archive to data/raw/.

Reads corpus/sources/*.yaml (one file per organization). Each YAML lists
documents that have already been selected for the corpus, per
docs/corpus-inclusion-rubric.md — this script doesn't decide what belongs
in the corpus, it only acquires and verifies what's already been declared.

Idempotent: rerunning skips any document already present in data/raw/ with
a matching checksum — safe to run again and again.

Acquisition mode, resolved per document as: the document's own
`acquisition` field if present, else the YAML's top-level
`default_acquisition`, else "auto". Added the org-level default
(2026-07-13, Opus-consulted, ahead of the 10-document/4-org milestone)
because the OONI walking-skeleton document showed this is fundamentally a
*server* property, not a per-document one — every OONI document is going
to need the same answer, so forcing it onto every single document entry
was the wrong level of repetition.

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

A single document's failure (checksum mismatch, bad format, not yet
placed) is logged and does NOT stop the rest of the run — this changed
2026-07-13, ahead of the 10-document/4-org milestone: with a single
document, "stop on first failure" and "stop the whole corpus run" were the
same thing, but at multi-org scale one bad document from one org
shouldn't block every other org's documents from being processed in the
same run. Failures are still loud (printed to stderr, and logged to
corpus/acquisition-log.md with the specific reason) and the script's exit
code reflects whether anything failed — just not via crashing mid-loop.

Usage:
    uv run python src/ingestion/acquire.py
"""

import csv
import hashlib
import sys
from datetime import date
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
ACQUISITION_LOG_PATH = PROJECT_ROOT / "corpus" / "acquisition-log.md"

MANIFEST_FIELDS = [
    "doc_id", "org", "title", "countries", "publication_date", "sha256", "local_path",
]

# Known bot-challenge phrases, checked against HTML content. Not
# exhaustive — this list grows every time a new challenge mechanism is
# actually hit (two distinct ones on ooni.org alone: a Vercel-style
# checkpoint, and a separate "verifying your browser" JS challenge).
CHALLENGE_PHRASES = [
    "verifying your browser",
    "enable javascript to continue",
    "checking your browser",
    "security checkpoint",
    "just a moment",
]


def sha256_of(path: Path) -> str:
    """Compute the SHA-256 hex digest of a file, reading in chunks (safe for large PDFs)."""
    digest = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(8192), b""):
            digest.update(chunk)
    return digest.hexdigest()


def looks_like_declared_format(path: Path, source_format: str):
    """
    Cheap sanity check independent of the checksum: does the file's magic
    number actually match what it claims to be? A checksum only proves
    "these are the bytes we expected" — it says nothing about whether those
    bytes are actually a valid file of the declared format. Added after a
    real incident (2026-07-13): a bot-challenge HTML page (Vercel Security
    Checkpoint) got saved as a .pdf by curl, with a 200 status and no error,
    and its checksum then matched itself consistently across every later
    check.

    Returns (ok: bool, reason: str | None) — the reason is None when ok is
    True, and a specific human-readable explanation when it's False. Returning
    the reason (not just a bool) matters once there's more than one document:
    it's what makes corpus/acquisition-log.md a useful empirical record of
    *why* a given org's content failed this check, rather than a silent gate.
    """
    if source_format == "pdf":
        with open(path, "rb") as f:
            header = f.read(5)
        if header == b"%PDF-":
            return True, None
        return False, f"bad PDF magic number (got {header!r}, expected b'%PDF-')"

    if source_format == "html":
        # There's no magic-number equivalent for HTML — a bot-challenge page
        # and a real article are both structurally valid HTML. The only
        # signal available is content: check for known challenge phrases.
        text = path.read_text(encoding="utf-8", errors="replace").lower()
        for phrase in CHALLENGE_PHRASES:
            if phrase in text:
                return False, f"matched known bot-challenge phrase: '{phrase}'"
        return True, None

    return True, None


def resolve_acquisition_mode(org_default: str, doc: dict) -> str:
    return doc.get("acquisition", org_default)


def load_sources():
    """Yield (org, document_dict) for every document declared across
    corpus/sources/*.yaml, with each document's effective acquisition mode
    already resolved (document field, else the YAML's own
    `default_acquisition`, else "auto") and stored under `_acquisition`."""
    for yaml_path in sorted(SOURCES_DIR.glob("*.yaml")):
        org = yaml_path.stem
        with open(yaml_path) as f:
            data = yaml.safe_load(f) or {}
        org_default = data.get("default_acquisition", "auto")
        for doc in data.get("documents", []):
            doc = dict(doc)
            doc["_acquisition"] = resolve_acquisition_mode(org_default, doc)
            yield org, doc


def append_acquisition_log_failure(doc_id: str, reason: str) -> None:
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
            f"- **{doc_id}** — acquire.py failure ({date.today().isoformat()}): "
            f"{reason}\n"
        )


class AcquisitionFailure(Exception):
    """A single document's acquisition failed. Caught per-document in
    main() so one bad document doesn't stop the rest of the run."""


def acquire_document(org: str, doc: dict):
    """
    Handle one document. Returns a manifest row (dict) on success, or None
    if it's not ready yet (auto download failed this run, or a manual file
    hasn't been placed yet) — neither of those is an AcquisitionFailure.
    Raises AcquisitionFailure only for a genuine integrity problem: a
    present file whose checksum or format doesn't match what's declared.
    """
    doc_id = doc["doc_id"]
    expected_sha256 = doc["sha256"]
    url = doc["url"]
    ext = "pdf" if doc["source_format"] == "pdf" else "html"
    mode = doc["_acquisition"]

    if expected_sha256.startswith("REPLACE_ME"):
        raise AcquisitionFailure(
            f"corpus/sources/{org}.yaml still has a placeholder sha256. "
            f"Get the real file once by hand, compute its checksum, and "
            f"put that in the YAML before running this script."
        )

    org_dir = RAW_DIR / org
    org_dir.mkdir(parents=True, exist_ok=True)
    dest = org_dir / f"{doc_id}.{ext}"

    if dest.exists():
        actual = sha256_of(dest)
        if actual == expected_sha256:
            ok, reason = looks_like_declared_format(dest, doc["source_format"])
            if not ok:
                raise AcquisitionFailure(
                    f"checksum matches, but the file doesn't look like a "
                    f"real {doc['source_format']} ({reason}). Likely a "
                    f"blocked-request or challenge page saved by mistake, "
                    f"with a checksum that's now just consistently "
                    f"re-verifying the wrong file — replace it with the "
                    f"real one and update sha256 in corpus/sources/{org}.yaml."
                )
            print(f"[skip] {doc_id} — already present, checksum matches")
            return {**doc, "org": org, "local_path": str(dest.relative_to(PROJECT_ROOT))}
        if mode == "manual":
            raise AcquisitionFailure(
                f"checksum mismatch (manual acquisition): expected "
                f"{expected_sha256}, got {actual}. The file at {dest} "
                f"doesn't match what was declared — check it's the right "
                f"file before re-running."
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
            f"script later, or mark this document (or its whole org, via "
            f"`default_acquisition`) as `manual` and place the file by hand.",
            file=sys.stderr,
        )
        return None

    tmp_path = dest.with_suffix(dest.suffix + ".tmp")
    tmp_path.write_bytes(response.content)

    actual_sha256 = sha256_of(tmp_path)
    if actual_sha256 != expected_sha256:
        tmp_path.unlink()
        raise AcquisitionFailure(
            f"checksum mismatch: expected {expected_sha256}, got "
            f"{actual_sha256}. The source file may have changed since it "
            f"was selected, or the download was corrupted. Not writing to "
            f"data/raw/ — investigate before re-running."
        )
    ok, reason = looks_like_declared_format(tmp_path, doc["source_format"])
    if not ok:
        tmp_path.unlink()
        raise AcquisitionFailure(
            f"downloaded content doesn't look like a real "
            f"{doc['source_format']} ({reason}) — likely a blocked-request "
            f"or bot-challenge page served with a 200 status instead of "
            f"the real file. Not writing to data/raw/."
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
    failures = 0

    for org, doc in load_sources():
        doc_id = doc.get("doc_id", "?")
        try:
            row = acquire_document(org, doc)
        except AcquisitionFailure as e:
            print(f"[FAIL] {doc_id}: {e}", file=sys.stderr)
            append_acquisition_log_failure(doc_id, str(e))
            failures += 1
            continue
        if row is None:
            pending += 1
        else:
            rows.append(row)

    if not rows and not pending and not failures:
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
        f"for manual acquisition), {failures} failed (see stderr above and "
        f"corpus/acquisition-log.md)."
    )
    if failures:
        sys.exit(1)


if __name__ == "__main__":
    main()
