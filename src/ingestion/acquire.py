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

Checksum design (ADR-0005, 2026-07-20): the `sha256` field this module
reads and verifies only ever proves the local copy in data/raw/ hasn't
rotted on disk since it was saved — it does NOT prove, and never did,
that the local copy still matches whatever the live source currently
serves. Re-fetching and re-comparing against the same recorded hash on
every run was never live-source verification; it was always local-disk
integrity checking with an incidental extra property (that most sources
happen to serve byte-stable content, so the two checks were
indistinguishable in practice) which broke down the moment a CDN-injected,
per-request-randomized source (Freedom House) was added. For sources
declared `raw_bytes_stable: false` in their YAML, `sha256` is trust-on-
first-use — recorded from whatever the first real download returns, never
gated against a pre-declared value, since no correct value could ever be
pre-declared for bytes that are never the same twice. Live-source content
fidelity, where it matters, is `extract.py`'s `content_sha256` job instead
(computed over canonicalized extracted text, immune to markup-level
randomness) — see ADR-0005 for the full reasoning.

Usage:
    uv run python src/ingestion/acquire.py
"""

import csv
import hashlib
import re
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
    "Accept": "application/pdf,text/html,application/json,*/*;q=0.8",
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
    """Compute the SHA-256 hex digest of a file, reading in chunks (safe for
    large PDFs). Used both to bootstrap a new baseline and to check a local
    file against a previously-recorded one — always a local-disk integrity
    check (has this file rotted/changed since we saved it?), never a check
    against the live source (see ADR-0005; ADR-0005 note also applies
    everywhere this function's result is compared against `doc["sha256"]`)."""
    digest = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(8192), b""):
            digest.update(chunk)
    return digest.hexdigest()


_STOPWORDS = {"the", "on", "of", "and", "a", "an", "in", "to", "for", "is", "at"}


def _normalize_for_match(text: str) -> str:
    """Lowercase, strip punctuation, collapse whitespace — used on both a
    declared title and fetched content so a substring check between them
    isn't defeated by case, punctuation, or incidental whitespace
    differences."""
    text = text.lower()
    text = re.sub(r"[^a-z0-9\s]", " ", text)
    return re.sub(r"\s+", " ", text).strip()


def _title_key_words(title: str) -> list[str]:
    """Words from a declared title worth requiring in fetched content: drop
    short filler and common stopwords, keep everything else (including
    years and other short-but-meaningful tokens like country names)."""
    words = _normalize_for_match(title).split()
    return [w for w in words if len(w) > 2 and w not in _STOPWORDS]


def looks_like_declared_format(path: Path, source_format: str, title: str = ""):
    """
    Sanity checks independent of the checksum — a checksum only proves
    "these are the bytes we expected," never that those bytes are actually a
    valid, real document of the declared format and content. Two checks,
    added at different times for different threats:

    - Negative (PDF magic bytes; HTML known challenge phrases): added after
      a real incident (2026-07-13) where a bot-challenge HTML page (Vercel
      Security Checkpoint) got saved as a .pdf by curl, 200 status, no
      error, and its checksum then matched itself consistently forever
      after.
    - Positive (HTML only, `title` presence): added per ADR-0005
      (2026-07-20) — the negative check alone only rules out *known*
      challenge phrasings; it asserts nothing positive about the content
      being the real, declared document. Checks that the declared title's
      key words (normalized, punctuation-stripped, fuzzy/substring — not an
      exact match, since HTML entity decoding or minor formatting shouldn't
      cause a false failure) actually appear in the fetched content.

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
        # signal available is content: check for known challenge phrases
        # (negative), then that the declared title's key words actually
        # showed up (positive).
        text = path.read_text(encoding="utf-8", errors="replace")
        lower_text = text.lower()
        for phrase in CHALLENGE_PHRASES:
            if phrase in lower_text:
                return False, f"matched known bot-challenge phrase: '{phrase}'"

        key_words = _title_key_words(title) if title else []
        if key_words:
            normalized_content = _normalize_for_match(text)
            missing = [w for w in key_words if w not in normalized_content]
            if missing:
                return False, (
                    f"declared title {title!r} not found in fetched content "
                    f"(missing key word(s): {', '.join(missing)}) — likely a "
                    f"blocked-request or bot-challenge page, not the real "
                    f"document"
                )
        return True, None

    if source_format == "json":
        # Added 2026-07-20 for OONI's newer "Findings" platform: the
        # public-facing page (explorer.ooni.org/findings/<id>) is a
        # JS-rendered SPA with no real content in its raw HTML, but the
        # same content is served as JSON by a documented API endpoint
        # (api.ooni.org/api/v1/incidents/show/<id>) with a "text" field
        # holding the full markdown-ish report body. No magic-number
        # equivalent exists for JSON, so this checks structural validity
        # (parses, has a non-empty "text" field) plus the same positive
        # title-key-word check HTML uses — a JSON error page or an empty
        # incident record wouldn't pass either check.
        import json

        text = path.read_text(encoding="utf-8", errors="replace")
        try:
            data = json.loads(text)
        except json.JSONDecodeError as e:
            return False, f"not valid JSON ({e})"

        body = data.get("incident", {}).get("text", "")
        if not body:
            return False, "parsed JSON but found no non-empty 'incident.text' field"

        key_words = _title_key_words(title) if title else []
        if key_words:
            normalized_content = _normalize_for_match(body)
            missing = [w for w in key_words if w not in normalized_content]
            if missing:
                return False, (
                    f"declared title {title!r} not found in the JSON's "
                    f"'incident.text' field (missing key word(s): "
                    f"{', '.join(missing)}) — likely the wrong incident id "
                    f"or an unexpected API response shape, not the real "
                    f"document"
                )
        return True, None

    return True, None


def resolve_acquisition_mode(org_default: str, doc: dict) -> str:
    return doc.get("acquisition", org_default)


def load_sources():
    """Yield (org, document_dict) for every document declared across
    corpus/sources/*.yaml, with each document's effective acquisition mode
    already resolved (document field, else the YAML's own
    `default_acquisition`, else "auto") and stored under `_acquisition`, and
    its raw-bytes stability (the YAML's top-level `raw_bytes_stable`, else
    `True` — every org except Freedom House has no such field at all, and
    `True` is the correct default for all of them) stored under
    `_raw_bytes_stable` (ADR-0005). No per-document override for
    `raw_bytes_stable` exists — per the ADR this is a server-wide property
    of a source, same reasoning as `default_acquisition`."""
    for yaml_path in sorted(SOURCES_DIR.glob("*.yaml")):
        org = yaml_path.stem
        with open(yaml_path) as f:
            data = yaml.safe_load(f) or {}
        org_default = data.get("default_acquisition", "auto")
        org_raw_bytes_stable = data.get("raw_bytes_stable", True)
        for doc in data.get("documents", []):
            doc = dict(doc)
            doc["_acquisition"] = resolve_acquisition_mode(org_default, doc)
            doc["_raw_bytes_stable"] = org_raw_bytes_stable
            yield org, doc


def write_yaml_field(org: str, doc_id: str, field: str, value: str) -> None:
    """Surgically replace one field's value for one document's block in
    corpus/sources/{org}.yaml, in place, preserving every comment and the
    rest of the file's formatting exactly. These files are hand-maintained
    prose-plus-YAML (long dated comments, `selection_rationale` blocks) —
    a full yaml.safe_load/yaml.dump round-trip would silently discard all
    of that, so this edits the text directly instead of going back through
    PyYAML.

    Assumes `field` appears as `{field}: <value>` on its own line somewhere
    inside the named document's block (from its own `- doc_id:` line up to
    the next one, or end of file) — true for every field this project
    writes back (`sha256`, `content_sha256`). Any trailing same-line
    comment on that field's line is preserved unchanged.
    """
    path = SOURCES_DIR / f"{org}.yaml"
    text = path.read_text(encoding="utf-8")

    block_re = re.compile(
        rf"(?ms)^  - doc_id: {re.escape(doc_id)}\n.*?(?=^  - doc_id:|\Z)"
    )
    match = block_re.search(text)
    if match is None:
        raise ValueError(f"doc_id {doc_id!r} not found in {path}")
    block = match.group(0)

    field_re = re.compile(rf'(?m)^(\s*{re.escape(field)}:\s*)(?:"[^"]*"|\S+)(.*)$')
    new_block, count = field_re.subn(rf'\g<1>"{value}"\g<2>', block, count=1)
    if count == 0:
        raise ValueError(f"field {field!r} not found in {doc_id!r}'s block in {path}")

    text = text[: match.start()] + new_block + text[match.end() :]
    path.write_text(text, encoding="utf-8")


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


def _fetch_once(doc_id: str, url: str) -> bytes | None:
    """Single GET, no retry loop (a tight retry against a 429 tends to make
    things worse, not better — see module docstring). Returns the response
    body on success, or None if the request itself failed (logged to
    stderr; caller decides whether that's fatal for this run)."""
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
    return response.content


def acquire_document(org: str, doc: dict):
    """
    Handle one document. Returns a manifest row (dict) on success, or None
    if it's not ready yet (auto download failed this run, or a manual file
    hasn't been placed yet) — neither of those is an AcquisitionFailure.
    Raises AcquisitionFailure only for a genuine integrity problem: a
    present file whose checksum or format doesn't match what's declared.

    Checksum handling branches on `_raw_bytes_stable` (ADR-0005): for the
    overwhelming majority of sources (stable raw bytes), a placeholder
    `sha256` is refused outright and a real download is gated on matching
    the pre-declared value — that's the `else` branch below, unchanged.
    For a source declared `raw_bytes_stable: false` (Freedom House only,
    currently) with no baseline recorded yet, there is no correct value
    that could have been pre-declared, so the first acquisition can't be
    gated on one — it downloads once and *records* whatever hash it
    actually got as the new baseline, trust-on-first-use. Once that
    baseline exists, later runs verify against it exactly like any other
    source (local-disk rot check only, never live-source fidelity — see
    module docstring and ADR-0005).
    """
    doc_id = doc["doc_id"]
    expected_sha256 = doc["sha256"]
    url = doc["url"]
    ext = {"pdf": "pdf", "json": "json"}.get(doc["source_format"], "html")
    mode = doc["_acquisition"]
    raw_bytes_stable = doc["_raw_bytes_stable"]
    title = doc.get("title", "")
    is_placeholder = expected_sha256.startswith("REPLACE_ME")

    org_dir = RAW_DIR / org
    org_dir.mkdir(parents=True, exist_ok=True)
    dest = org_dir / f"{doc_id}.{ext}"

    if raw_bytes_stable:
        if is_placeholder:
            raise AcquisitionFailure(
                f"corpus/sources/{org}.yaml still has a placeholder sha256. "
                f"Get the real file once by hand, compute its checksum, and "
                f"put that in the YAML before running this script."
            )
    elif is_placeholder or not dest.exists():
        # Trust-on-first-use bootstrap (ADR-0005 decision #1, corrected):
        # raw bytes are declared volatile, so there's no baseline to gate
        # against yet. Get a real file onto disk one way or another, then
        # record its hash as the new baseline instead of verifying it
        # against anything.
        if dest.exists():
            # A file is already present (e.g. placed by hand) but no
            # baseline is recorded yet — bootstrap from it directly, don't
            # re-download.
            ok, reason = looks_like_declared_format(dest, doc["source_format"], title)
            if not ok:
                raise AcquisitionFailure(
                    f"existing file doesn't look like a real "
                    f"{doc['source_format']} ({reason}) — can't bootstrap a "
                    f"baseline checksum from it. Replace it with the real "
                    f"file before re-running."
                )
            actual_sha256 = sha256_of(dest)
            write_yaml_field(org, doc_id, "sha256", actual_sha256)
            print(
                f"[bootstrap] {doc_id} — raw_bytes_stable: false; recorded "
                f"baseline checksum {actual_sha256} from the existing local "
                f"file (not verified against a live fetch — see ADR-0005)"
            )
            return {
                **doc,
                "org": org,
                "sha256": actual_sha256,
                "local_path": str(dest.relative_to(PROJECT_ROOT)),
            }

        if mode == "manual":
            print(
                f"[pending] {doc_id} — manual acquisition, not yet placed. "
                f"Download {url} by hand and save it to "
                f"{dest.relative_to(PROJECT_ROOT)}, then re-run this script."
            )
            return None

        content = _fetch_once(doc_id, url)
        if content is None:
            return None

        tmp_path = dest.with_suffix(dest.suffix + ".tmp")
        tmp_path.write_bytes(content)

        ok, reason = looks_like_declared_format(tmp_path, doc["source_format"], title)
        if not ok:
            tmp_path.unlink()
            raise AcquisitionFailure(
                f"downloaded content doesn't look like a real "
                f"{doc['source_format']} ({reason}) — likely a blocked-"
                f"request or bot-challenge page served with a 200 status "
                f"instead of the real file. Not writing to data/raw/."
            )

        actual_sha256 = sha256_of(tmp_path)
        tmp_path.rename(dest)
        write_yaml_field(org, doc_id, "sha256", actual_sha256)
        print(
            f"[ok] {doc_id} — downloaded and verified ({len(content)} bytes); "
            f"raw_bytes_stable: false, so {actual_sha256} is recorded as a "
            f"new local-rot baseline, not verified against a pre-declared "
            f"value (see ADR-0005)"
        )
        return {
            **doc,
            "org": org,
            "sha256": actual_sha256,
            "local_path": str(dest.relative_to(PROJECT_ROOT)),
        }

    # Existing behavior, unchanged: stable-bytes sources always take this
    # path; volatile-bytes sources (raw_bytes_stable: false) take it too
    # once a baseline has already been recorded above. Either way this only
    # ever checks the local file against its own previously-recorded hash —
    # local-disk integrity, never live-source fidelity (see module
    # docstring, ADR-0005).
    if dest.exists():
        actual = sha256_of(dest)
        if actual == expected_sha256:
            ok, reason = looks_like_declared_format(dest, doc["source_format"], title)
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

    content = _fetch_once(doc_id, url)
    if content is None:
        return None

    tmp_path = dest.with_suffix(dest.suffix + ".tmp")
    tmp_path.write_bytes(content)

    actual_sha256 = sha256_of(tmp_path)
    if actual_sha256 != expected_sha256:
        tmp_path.unlink()
        raise AcquisitionFailure(
            f"checksum mismatch: expected {expected_sha256}, got "
            f"{actual_sha256}. The source file may have changed since it "
            f"was selected, or the download was corrupted. Not writing to "
            f"data/raw/ — investigate before re-running."
        )
    ok, reason = looks_like_declared_format(tmp_path, doc["source_format"], title)
    if not ok:
        tmp_path.unlink()
        raise AcquisitionFailure(
            f"downloaded content doesn't look like a real "
            f"{doc['source_format']} ({reason}) — likely a blocked-request "
            f"or bot-challenge page served with a 200 status instead of "
            f"the real file. Not writing to data/raw/."
        )

    tmp_path.rename(dest)
    print(f"[ok] {doc_id} — downloaded and verified ({len(content)} bytes)")
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
