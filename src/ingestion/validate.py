"""
validate.py — structural validation of extracted documents.

Reads corpus/manifest.csv (documents acquire.py has verified) and checks
each one against the tiered checks from ADR-0002 (docs/adr/0002-tiered-
validation-routing.md):

  Tier 1 — fully automated, auto-excludes on failure. Facts, not
  judgments, so no human review is needed to act on them:
    - extraction succeeded (data/processed/{org}/{doc_id}.txt exists and
      is non-empty)
    - file integrity (SHA-256 still matches what acquire.py recorded)
  A Tier 1 failure is logged automatically to corpus/acquisition-log.md —
  the reasoning here is deterministic, so validate.py can write that
  entry itself.

  Tier 2 — automated checks, but only ever flag for human review, never
  auto-exclude:
    - language (must detect as English)
    - minimum length (>= 500 words)
    - near-duplicate (SimHash compared against every other document that
      passed Tier 1 — with a one-document corpus this never fires, but it
      still runs, proving the branching logic actually executes rather
      than just existing on paper)
    - content drift (ADR-0007, 2026-07-20): for orgs whose raw bytes
      aren't stable (raw_bytes_stable: false), recompute content_sha256
      over the current extracted text and compare against
      corpus/derived-checksums/{org}.json. A mismatch here is the same
      signal extract.py already logs to acquisition-log.md
      (append_content_drift_flag) — surfaced *again* as a proper Tier 2
      flag so it actually reaches the human-review path ADR-0005 always
      said it should, instead of only ever being a stderr print that
      nothing downstream consumed.

Writes corpus/validation-report.md (human-readable) and
corpus/validation-results.json (ADR-0007, 2026-07-20 — machine-readable:
one entry per document, tier1/tier2 results in structured form) — the
report is for a human to read; the JSON is what metadata.py now consumes
instead of re-running language/word-count detection itself, so the two
stages can never quietly disagree about the same fact.

The actual Included/Excluded call — topic relevance, coverage
contribution — is Sam's judgment, logged by hand in
corpus/acquisition-log.md, not automated here.

Usage:
    uv run python src/ingestion/validate.py
"""

import csv
import hashlib
import json
import sys
from pathlib import Path

from langdetect import DetectorFactory, LangDetectException, detect_langs
from simhash import Simhash

# ADR-0007, finding 1: langdetect's detector is seeded from wall-clock time
# by default, making detect() non-deterministic for short/ambiguous text —
# the same document could flip language classification between runs with no
# code or content change. Seeding makes every run reproducible.
DetectorFactory.seed = 0

sys.path.insert(0, str(Path(__file__).resolve().parent))
from acquire import load_derived_checksums  # noqa: E402 — needs sys.path set first
from extract import content_sha256_of, load_content_checksum_orgs  # noqa: E402

# The simhash package's default `large_weight_cutoff` (50) routes any token
# appearing more than 50 times through a code path
# (`Simhash._bitarray_from_bytes(h) * w`) that multiplies a uint8 numpy
# array by the raw weight -- fine under old numpy (silently wrapped), but
# modern numpy (>=~1.24) raises OverflowError instead, since w easily
# exceeds 255 for a common word in a real multi-thousand-word report. Real
# bug hit 2026-07-13 on the first real multi-document validate.py run (10
# documents, some 25-30k words) -- never surfaced on the single
# walking-skeleton document. Raising the cutoff avoids that code path
# entirely; no real document will repeat a single token a billion times.
Simhash.large_weight_cutoff = 10**9

PROJECT_ROOT = Path(__file__).resolve().parents[2]
MANIFEST_PATH = PROJECT_ROOT / "corpus" / "manifest.csv"
PROCESSED_DIR = PROJECT_ROOT / "data" / "processed"
CHECKSUMS_PATH = PROJECT_ROOT / "corpus" / "checksums.sha256"
REPORT_PATH = PROJECT_ROOT / "corpus" / "validation-report.md"
RESULTS_PATH = PROJECT_ROOT / "corpus" / "validation-results.json"
ACQUISITION_LOG_PATH = PROJECT_ROOT / "corpus" / "acquisition-log.md"

MIN_WORD_COUNT = 500
NEAR_DUPLICATE_MAX_DISTANCE = 3  # SimHash Hamming distance threshold

# Deliberately simple keyword hint for the human semantic review in
# docs/corpus-inclusion-rubric.md — an assist signal in the report, not a
# replacement for that review.
TOPIC_KEYWORDS = [
    "censorship", "internet shutdown", "blocked", "blocking",
    "network interference", "surveillance", "digital rights",
    "freedom of expression", "vpn", "throttl",
]


def sha256_of(path: Path) -> str:
    digest = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(8192), b""):
            digest.update(chunk)
    return digest.hexdigest()


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


def tier1_checks(row: dict) -> dict:
    """Facts, not judgments: did extraction succeed, does the file still
    match its checksum. Returns {"extraction_ok": bool, "integrity_ok": bool}."""
    doc_id = row["doc_id"]
    org = row["org"]
    processed_path = PROCESSED_DIR / org / f"{doc_id}.txt"
    extraction_ok = processed_path.exists() and processed_path.stat().st_size > 0

    raw_path = PROJECT_ROOT / row["local_path"]
    integrity_ok = raw_path.exists() and sha256_of(raw_path) == row["sha256"]

    return {"extraction_ok": extraction_ok, "integrity_ok": integrity_ok}


def content_drift_check(doc_id: str, org: str, text: str,
                         content_checksum_orgs: set[str]) -> dict | None:
    """ADR-0007, finding 3: re-surface a content_sha256 mismatch as a real
    Tier 2 flag, not just extract.py's stderr print / acquisition-log
    entry. Returns None for any org not tracked (content_checksum_orgs),
    or if there's no recorded baseline yet to compare against (first run
    — extract.py's own bootstrap step, nothing to flag)."""
    if org not in content_checksum_orgs:
        return None
    derived = load_derived_checksums(org)
    expected = derived.get(doc_id, {}).get("content_sha256")
    if expected is None:
        return None
    actual = content_sha256_of(text)
    return {"drifted": actual != expected, "expected": expected, "actual": actual}


def tier2_checks(doc_id: str, org: str, text: str, other_simhashes: dict,
                  content_checksum_orgs: set[str]) -> dict:
    """Automated, but every result here is a flag for human review, never
    an automatic exclusion."""
    word_count = len(text.split())

    try:
        top = detect_langs(text)[0]
        language = top.lang
        language_confidence = round(top.prob, 4)
    except LangDetectException:
        language = "unknown"
        language_confidence = 0.0

    this_hash = Simhash(text)
    near_duplicates = [
        other_doc_id
        for other_doc_id, other_hash in other_simhashes.items()
        if this_hash.distance(other_hash) <= NEAR_DUPLICATE_MAX_DISTANCE
    ]

    drift = content_drift_check(doc_id, org, text, content_checksum_orgs)

    return {
        "word_count": word_count,
        "language": language,
        "language_confidence": language_confidence,
        "language_ok": language == "en",
        "length_ok": word_count >= MIN_WORD_COUNT,
        "near_duplicates": near_duplicates,
        "content_drift": drift,
    }


def topic_keyword_hint(text: str) -> list[str]:
    lower = text.lower()
    return [kw for kw in TOPIC_KEYWORDS if kw in lower]


def append_acquisition_log_exclusion(doc_id: str, reason: str) -> None:
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
        f.write(f"- **{doc_id}** — Excluded (automated, Tier 1): {reason}\n")


def main() -> None:
    rows = load_manifest()
    if not rows:
        print("Manifest is empty — nothing to validate.")
        return

    # Pass 1: Tier 1. Anything that fails is excluded and logged right away;
    # anything that passes gets its text loaded so Tier 2's near-duplicate
    # check has the full set to compare against.
    survivors = []
    texts = {}
    report_sections = []
    results = {}
    content_checksum_orgs = load_content_checksum_orgs()

    for row in rows:
        doc_id = row["doc_id"]
        t1 = tier1_checks(row)

        if not (t1["extraction_ok"] and t1["integrity_ok"]):
            reasons = []
            if not t1["extraction_ok"]:
                reasons.append("extraction failed or produced an empty file")
            if not t1["integrity_ok"]:
                reasons.append("SHA-256 no longer matches data/raw/")
            reason_str = "; ".join(reasons)
            print(f"[excluded] {doc_id} — Tier 1 failure: {reason_str}")
            append_acquisition_log_exclusion(doc_id, reason_str)
            report_sections.append(
                f"## {doc_id}\n\n**Tier 1: FAILED** — {reason_str}. "
                f"Excluded automatically.\n"
            )
            results[doc_id] = {
                "org": row["org"],
                "tier1": t1,
                "tier1_passed": False,
                "tier2": None,
            }
            continue

        processed_path = PROCESSED_DIR / row["org"] / f"{doc_id}.txt"
        texts[doc_id] = processed_path.read_text(encoding="utf-8")
        survivors.append(row)

    # Pass 2: Tier 2, comparing each survivor's SimHash against every other
    # survivor's — near-duplicate detection needs the whole set at once.
    simhashes = {doc_id: Simhash(text) for doc_id, text in texts.items()}

    for row in survivors:
        doc_id = row["doc_id"]
        org = row["org"]
        text = texts[doc_id]
        others = {k: v for k, v in simhashes.items() if k != doc_id}
        t2 = tier2_checks(doc_id, org, text, others, content_checksum_orgs)
        hint = topic_keyword_hint(text)

        flags = []
        if not t2["language_ok"]:
            flags.append(f"language detected as '{t2['language']}', not English")
        if not t2["length_ok"]:
            flags.append(f"only {t2['word_count']} words (below the {MIN_WORD_COUNT} minimum)")
        if t2["near_duplicates"]:
            flags.append(f"near-duplicate of: {', '.join(t2['near_duplicates'])}")
        if t2["content_drift"] and t2["content_drift"]["drifted"]:
            flags.append(
                f"content_sha256 drifted from recorded baseline "
                f"(expected {t2['content_drift']['expected']}, got "
                f"{t2['content_drift']['actual']}) — source content may "
                f"have changed since acquisition (ADR-0005/ADR-0007)"
            )

        status = "FLAGGED for human review" if flags else "clean"
        print(f"[{'flagged' if flags else 'ok'}] {doc_id} — Tier 1 passed, Tier 2: {status}")

        section = [f"## {doc_id}\n", "**Tier 1:** passed.\n", f"**Tier 2:** {status}"]
        if flags:
            section.append(" — " + "; ".join(flags))
        section.append(".\n")
        section.append(
            f"- Word count: {t2['word_count']}\n"
            f"- Language: {t2['language']}\n"
            f"- Near-duplicates found: {len(t2['near_duplicates'])}\n"
            f"- Topic keyword hint ({len(hint)} matched): "
            f"{', '.join(hint) if hint else 'none'}\n"
        )
        section.append(
            "\n_Semantic review (topic relevance, coverage contribution) is "
            "a human judgment call per docs/corpus-inclusion-rubric.md — not "
            "automated here. Record the Included/Excluded decision by hand "
            "in corpus/acquisition-log.md._\n"
        )
        report_sections.append("\n".join(section))

        results[doc_id] = {
            "org": org,
            "tier1": {"extraction_ok": True, "integrity_ok": True},
            "tier1_passed": True,
            "tier2": t2,
            "tier2_flags": flags,
        }

    REPORT_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(REPORT_PATH, "w", encoding="utf-8") as f:
        f.write("# Validation Report\n\n")
        f.write(
            "Generated by validate.py. Tier 1 failures are excluded "
            "automatically (see corpus/acquisition-log.md). Tier 2 flags "
            "and the semantic review below need a human decision, not an "
            "automatic exclusion.\n\n"
        )
        f.write("\n\n".join(report_sections))
        f.write("\n")

    print(f"\n[report] wrote {REPORT_PATH.relative_to(PROJECT_ROOT)}")

    RESULTS_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(RESULTS_PATH, "w", encoding="utf-8") as f:
        json.dump(results, f, indent=2, sort_keys=True)
        f.write("\n")
    print(f"[results] wrote {RESULTS_PATH.relative_to(PROJECT_ROOT)}")


if __name__ == "__main__":
    main()
