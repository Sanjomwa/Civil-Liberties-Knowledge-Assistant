"""
ground_truth.py — chunk-level questions for retrieval evaluation, built to
avoid circularity.

Samples a stratified subset of chunks from data/chunks/ (not all 3,783 —
cost/time control) and generates one question per sampled chunk via an
LLM, using a researcher/journalist framing
(per 04-evaluation/project/project_evaluation_plan.md), not a generic-FAQ
framing.

Circularity fix (from the 2026-07-22 Opus design review): synthetic
questions generated straight from a chunk tend to lexically echo it, which
structurally inflates keyword search's apparent win rate in evaluation —
this may be part of why Module 4's own homework found keyword search
beating vector search on a different corpus, not purely a property of the
corpus itself. The generation prompt below explicitly instructs
paraphrase/abstraction: ask about the passage's substance without quoting
or closely mirroring its exact phrasing. This script also writes a small
`ground_truth_review_sample.json` — ~25 pairs for a human (Sam) to hand-
check for residual circularity before evaluate.py's results are trusted.
That manual check is a required step, not optional, per the design review.

Stratification: three categories, deliberately oversampling the two named
as "harder" in project_evaluation_plan.md relative to their natural share
of the corpus — "multi_country" (a chunk whose document covers more than
one country) and "ooni_methodology" (an OONI-org chunk whose text matches
a small heuristic keyword list — TOPIC-hint style, an approximation, not a
precise classifier, same spirit as validate.py's own topic_keyword_hint).
Everything else is "general". "Thin/contradictory-evidence" cases from the
evaluation plan are NOT auto-sampled here — that's a cross-document
property (whether multiple sources agree or one source is sparse), not
something a single isolated chunk's own text can reliably signal. Flagged
here rather than faked with a classifier that would overclaim precision it
doesn't have; Sam can hand-select a few such cases separately if wanted.

Costs real money per run (LLM calls) — unlike the rest of this project's
scripts, this one is NOT free to rerun casually. Re-run only when the
ground truth genuinely needs to change (corpus grew significantly, sample
size needs adjusting), not as a routine step.

Requires OPENAI_API_KEY (via .env / load_dotenv()).

Usage:
    uv run python src/retrieval/ground_truth.py
    uv run python src/retrieval/ground_truth.py --regenerate-review-sample
        # free, no LLM calls — rebuilds ground_truth_review_sample.json
        # from the existing ground_truth.json + chunk files on disk.
        # Use this if the review sample needs regenerating (e.g. the
        # 2026-07-22 chunk_text fix) without re-spending the real run.
"""

import json
import os
import random
import sys
from pathlib import Path

from dotenv import load_dotenv
from openai import OpenAI

load_dotenv()

PROJECT_ROOT = Path(__file__).resolve().parents[2]
CHUNKS_DIR = PROJECT_ROOT / "data" / "chunks"
CORPUS_VERSION_PATH = PROJECT_ROOT / "corpus" / "CORPUS_VERSION"
EVAL_DIR = PROJECT_ROOT / "data" / "eval"
GROUND_TRUTH_PATH = EVAL_DIR / "ground_truth.json"
REVIEW_SAMPLE_PATH = EVAL_DIR / "ground_truth_review_sample.json"

SEED = 42
# Fixed 2026-07-22 — was hardcoded to "gpt-4o-mini", which this OpenAI
# project doesn't have access to (403 model_not_found on every real call).
# The course's own code (rag_helper.py, evaluation_utils.py, confirmed via
# LLM-ZOOMCAMP-2026-main.zip) uses "gpt-5.4-mini" everywhere — Sam
# intentionally set that up as the low-credit-usage model for this
# project's key/project, so this now matches both the course convention
# and what Sam's account actually has enabled.
LLM_MODEL = "gpt-5.4-mini"

# Target sample counts per stratum. Capped at whatever's actually available
# in a stratum (e.g. ooni_methodology chunks are a small slice of a
# corpus where OONI itself is the smallest-chunk-count org) — see
# sample_stratified()'s min(target, available) logic.
STRATUM_TARGETS = {
    "multi_country": 30,
    "ooni_methodology": 20,
    "general": 100,
}
REVIEW_SAMPLE_SIZE = 25

# Deliberately simple keyword hint, same spirit as validate.py's
# TOPIC_KEYWORDS — an assist signal, not a precise classifier.
OONI_METHODOLOGY_KEYWORDS = [
    "methodology", "test helper", "ooni probe", "measurement",
    "false positive", "confirmed anomaly", "false negative",
    "control measurement", "signal", "web connectivity test",
]

# Strengthened 2026-07-22 (real problem, not a hypothetical): Sam's
# manual review of the first real run found ~24% of a 25-pair sample was
# severely circular despite the original paraphrase-only instruction —
# near-verbatim phrase lifts ("suppress political dissent", a Responsible
# AI Office description copied almost word-for-word), plus 3 uses of the
# exact self-referential phrasing the prompt already forbade in spirit
# but didn't call out explicitly ("according to this passage", "described
# here"). Also found 2 chunks that are mostly footnotes/citations, where
# the generated question implied a broader claim than that specific
# passage's own prose actually supports (possibly answered from the
# model's general knowledge rather than the text). Full detail in
# decisionlog.md. This version adds concrete positive/negative examples
# and an explicit forbidden-phrase list for both known failure modes —
# examples are more reliable than an abstract instruction for this kind
# of behavior. Triggered a full re-run (not just a prompt tweak in
# isolation) since the ooni_methodology classify_category() bug (also
# fixed same day) changes which chunks even get sampled.
#
# Second pass, same day, after Sam's review of THAT re-run: the
# self-referential phrasing rule worked completely (zero violations in
# the next 25-pair sample). The verbatim-lift rule helped but didn't
# fully close the gap — total flagged rate stayed near ~24%, just with
# a new dominant pattern: the model echoing a passage's own embedded
# Freedom-on-the-Net survey question or a footnote's own citation title
# almost verbatim, since that's often the most information-dense text
# in a footnote-heavy chunk. Added the explicit rule below against that
# specific pattern. Decided NOT to spend a third full re-run chasing
# this — see filter_ground_truth.py instead, which mechanically drops
# any already-generated question sharing a 4+-word descriptive phrase
# with its source chunk, applied to the existing 150 rather than
# re-generating. This prompt version is for future runs (corpus growth,
# a from-scratch regenerate), not required for the current evaluation.
QUESTION_SYSTEM_PROMPT = """You are a researcher or journalist investigating internet freedom and digital rights in East Africa. You will be given one passage from a research report (OONI, Access Now, CIPESA, or Freedom House).

Write exactly ONE specific question that this passage is the correct source to answer.

Rules:
- The question must be answerable using only the information in this passage.
- Do NOT quote or closely paraphrase the passage's exact wording. This is the most common failure mode. Read the passage, then write the question from memory of its substance — don't lightly edit its own sentences into a question. If a phrase in your draft question shares 4+ consecutive words with the passage, and that phrase is a *description or characterization* (not a proper noun, date, or place name — those are fine), rewrite it.
  BAD (lifted): passage says "the government continues to suppress political dissent through pervasive surveillance" -> question "What methods does the government use to suppress political dissent?"
  GOOD (paraphrased): "What tactics has the government used against political opponents and critics?"
- Never refer to "the passage," "this passage," "described here," "mentioned here," or similar self-referential phrasing. Write a real, standalone question, as if you don't have the text in front of you.
  BAD: "What does this passage say about X?" / "According to this passage, what...?" / "Which country is described here as...?"
  GOOD: "What tactics has the government used against political opponents?"
- If the passage is mostly citations, footnotes, or a reference list with little substantive prose, base the question ONLY on whatever substantive sentences actually exist in it. Do not write a broader or more general question than this specific passage's own content supports, even if you know a fuller answer from general knowledge.
- Some passages end on the report's own embedded survey question (e.g. "Are there laws that assign criminal penalties or civil liability...") or contain a footnote/citation whose own title already reads like an answer (e.g. "Uganda Blocks Facebook Ahead of Contentious Election"). Do NOT reuse that header or title as your question, even reworded — write your own question from the passage's actual substantive content instead.
- Return ONLY the question. No preamble, no quotation marks, no numbering.
"""


def load_current_corpus_version() -> str:
    if not CORPUS_VERSION_PATH.exists():
        print(f"No {CORPUS_VERSION_PATH.relative_to(PROJECT_ROOT)} found.", file=sys.stderr)
        sys.exit(1)
    # Real format is "<version> <date-it-was-set>" (e.g. "v1.0 2026-07-13"),
    # not a bare version string -- same fix as embed.py, found 2026-07-22
    # on the first real WSL run. Only the leading token is compared.
    return CORPUS_VERSION_PATH.read_text(encoding="utf-8").strip().split()[0]


_chunking_stamp_cache: dict[str, str | None] = {}


def _document_chunking_corpus_version(doc_id: str) -> str | None:
    """Same fix as embed.py's identically-named function — the
    chunking.corpus_version stamp lives in data/metadata/{doc_id}.json,
    never in the chunk record's own document_metadata (a real bug in
    src/ingestion/chunk.py, see embed.py's docstring and decisionlog.md,
    2026-07-22, for the full root cause)."""
    if doc_id not in _chunking_stamp_cache:
        meta_path = PROJECT_ROOT / "data" / "metadata" / f"{doc_id}.json"
        if not meta_path.exists():
            _chunking_stamp_cache[doc_id] = None
        else:
            with open(meta_path, encoding="utf-8") as f:
                doc_metadata = json.load(f)
            _chunking_stamp_cache[doc_id] = doc_metadata.get("chunking", {}).get("corpus_version")
    return _chunking_stamp_cache[doc_id]


def classify_category(chunk: dict) -> str:
    if len(chunk["countries"]) > 1:
        return "multi_country"
    # Fixed 2026-07-22 -- was comparing against the lowercase literal
    # "ooni", but corpus/sources/ooni.yaml (and therefore
    # data/metadata/{doc_id}.json's declared.organization) stores it as
    # "OONI". That made this branch permanently unreachable regardless of
    # chunk content -- the real reason ooni_methodology sampled 0/20 on
    # the first run, found by Sam's manual review noticing an OONI
    # methodology-describing chunk (measurement/TCP-TLS-failure analysis,
    # literally containing the "measurement" and "ooni probe" keywords)
    # had been classified "general" instead. Previously documented as an
    # accepted corpus-content gap (decisionlog.md, 2026-07-22) -- that
    # conclusion was wrong, or at least premature; see the follow-up
    # entry same file, same date, for the correction.
    if chunk["organization"].lower() == "ooni":
        lower = chunk["text"].lower()
        if any(kw in lower for kw in OONI_METHODOLOGY_KEYWORDS):
            return "ooni_methodology"
    return "general"


def load_chunks(current_corpus_version: str) -> list[dict]:
    """Same corpus_version integrity check as embed.py — a chunk stamped
    with a stale corpus_version shouldn't be sampled into ground truth,
    since it may be re-chunked (and its chunk_id may change) before
    evaluate.py ever runs against it."""
    if not CHUNKS_DIR.exists() or not any(CHUNKS_DIR.iterdir()):
        print(f"No chunks in {CHUNKS_DIR.relative_to(PROJECT_ROOT)} — run "
              f"src/ingestion/chunk.py first.", file=sys.stderr)
        sys.exit(1)

    chunks = []
    for chunk_path in sorted(CHUNKS_DIR.glob("*/*.json")):
        with open(chunk_path, encoding="utf-8") as f:
            record = json.load(f)
        meta = record["document_metadata"]
        if _document_chunking_corpus_version(record["doc_id"]) != current_corpus_version:
            continue  # embed.py is the one that hard-fails on this; here, just skip
        declared = meta["declared"]
        chunk = {
            "chunk_id": record["chunk_id"],
            "doc_id": record["doc_id"],
            "text": record["text"],
            "organization": declared["organization"],
            "countries": declared["countries"],
        }
        chunk["category"] = classify_category(chunk)
        chunks.append(chunk)
    return chunks


def sample_stratified(chunks: list[dict], rng: random.Random) -> tuple[list[dict], dict]:
    by_category: dict[str, list[dict]] = {}
    for chunk in chunks:
        by_category.setdefault(chunk["category"], []).append(chunk)

    sampled = []
    actual_counts = {}
    for category, target in STRATUM_TARGETS.items():
        pool = by_category.get(category, [])
        n = min(target, len(pool))
        sampled.extend(rng.sample(pool, n))
        actual_counts[category] = n

    return sampled, actual_counts


def load_chunk_text(doc_id: str, chunk_id: str) -> str | None:
    """Looks up one chunk's raw text by id, for attaching to the review
    sample (see write_review_sample). Returns None if the chunk file is
    missing (shouldn't happen right after load_chunks() ran successfully,
    but this is defensive, not load-bearing)."""
    chunk_path = CHUNKS_DIR / doc_id / f"{chunk_id}.json"
    if not chunk_path.exists():
        return None
    with open(chunk_path, encoding="utf-8") as f:
        return json.load(f)["text"]


def write_review_sample(questions: list[dict], rng: random.Random) -> list[dict]:
    """Fixed 2026-07-22 — the review sample previously wrote out only
    {question, correct_chunk_id, doc_id, organization, category}, with no
    chunk text. That made the sample unusable for its actual stated
    purpose: judging whether a question echoes the passage's own wording
    requires having the passage in front of you. Found when Sam pasted
    the sample back for review and there was nothing to compare each
    question against except re-opening 25 individual chunk files by
    hand. Now attaches each pair's chunk_text directly."""
    sample = rng.sample(questions, min(REVIEW_SAMPLE_SIZE, len(questions)))
    for pair in sample:
        pair["chunk_text"] = load_chunk_text(pair["doc_id"], pair["correct_chunk_id"])
    return sample


def generate_question(client: OpenAI, chunk: dict) -> str | None:
    try:
        response = client.chat.completions.create(
            model=LLM_MODEL,
            messages=[
                {"role": "system", "content": QUESTION_SYSTEM_PROMPT},
                {"role": "user", "content": chunk["text"]},
            ],
            temperature=0.7,
        )
        return response.choices[0].message.content.strip()
    except Exception as e:  # noqa: BLE001 — a skipped question is fine, a crashed run isn't
        print(f"[FAIL] {chunk['chunk_id']} — LLM call failed: {e}", file=sys.stderr)
        return None


def main() -> None:
    # --regenerate-review-sample (added 2026-07-22, alongside the
    # write_review_sample fix): re-derives ground_truth_review_sample.json
    # from the already-written ground_truth.json plus the chunk files
    # still on disk. No OpenAI calls, no cost — for exactly the situation
    # that prompted this fix, where 130 good questions already exist and
    # only the review sample itself needs to be rebuilt with chunk text
    # attached. Same SEED as the original run, so it's the identical 25
    # pairs already sampled, just enriched.
    if "--regenerate-review-sample" in sys.argv:
        if not GROUND_TRUTH_PATH.exists():
            print(f"{GROUND_TRUTH_PATH.relative_to(PROJECT_ROOT)} doesn't exist yet — "
                  f"run ground_truth.py normally first.", file=sys.stderr)
            sys.exit(1)
        with open(GROUND_TRUTH_PATH, encoding="utf-8") as f:
            existing = json.load(f)
        review_rng = random.Random(SEED)
        review_sample = write_review_sample(existing["questions"], review_rng)
        EVAL_DIR.mkdir(parents=True, exist_ok=True)
        with open(REVIEW_SAMPLE_PATH, "w", encoding="utf-8") as f:
            json.dump(review_sample, f, indent=2, ensure_ascii=False)
            f.write("\n")
        print(f"[ok] regenerated {REVIEW_SAMPLE_PATH.relative_to(PROJECT_ROOT)} "
              f"({len(review_sample)} pair(s), with chunk_text attached) — "
              f"no OpenAI calls made.")
        return

    if not os.environ.get("OPENAI_API_KEY"):
        print("OPENAI_API_KEY not set (check .env) — required for question generation.",
              file=sys.stderr)
        sys.exit(1)

    corpus_version = load_current_corpus_version()
    chunks = load_chunks(corpus_version)
    print(f"[ok] loaded {len(chunks)} chunk(s) eligible for sampling")

    rng = random.Random(SEED)
    sampled, actual_counts = sample_stratified(chunks, rng)
    print(f"[ok] sampled {len(sampled)} chunk(s): {actual_counts}")

    client = OpenAI()
    questions = []
    consecutive_failures = 0
    FAIL_FAST_THRESHOLD = 3  # see 2026-07-22 note below

    for i, chunk in enumerate(sampled, start=1):
        question = generate_question(client, chunk)
        if question is None:
            consecutive_failures += 1
            # Fail-fast (added 2026-07-22, after a real run): a single bad
            # chunk failing is fine and worth skipping, but the same error
            # on the first few calls in a row means something systemic is
            # broken (bad API key, no billing, model not enabled for this
            # OpenAI project, etc.) — every remaining call will fail
            # identically too. Continuing through all ~130 samples in that
            # case wastes the whole run instead of surfacing the real
            # problem immediately. This does NOT trigger on scattered
            # failures later in a run (consecutive_failures resets below),
            # only on a systemic failure right at the start.
            if consecutive_failures >= FAIL_FAST_THRESHOLD:
                print(
                    f"\n[abort] {consecutive_failures} consecutive LLM "
                    f"calls failed — this looks systemic (bad API key, no "
                    f"billing, or the model isn't enabled for this OpenAI "
                    f"project), not a per-chunk fluke. Stopping instead of "
                    f"burning through the rest of {len(sampled)} samples. "
                    f"Check the [FAIL] messages above, fix the underlying "
                    f"OpenAI account/model-access issue, then re-run.",
                    file=sys.stderr,
                )
                sys.exit(1)
            continue
        consecutive_failures = 0
        questions.append(
            {
                "question": question,
                "correct_chunk_id": chunk["chunk_id"],
                "doc_id": chunk["doc_id"],
                "organization": chunk["organization"],
                "category": chunk["category"],
            }
        )
        if i % 25 == 0 or i == len(sampled):
            print(f"[progress] {i}/{len(sampled)} question(s) generated")

    EVAL_DIR.mkdir(parents=True, exist_ok=True)
    output = {
        "sampling": {
            "seed": SEED,
            "stratum_targets": STRATUM_TARGETS,
            "stratum_actual_counts": actual_counts,
            "total_sampled": len(sampled),
            "total_generated": len(questions),
        },
        "questions": questions,
    }
    with open(GROUND_TRUTH_PATH, "w", encoding="utf-8") as f:
        json.dump(output, f, indent=2, ensure_ascii=False)
        f.write("\n")
    print(f"\n[ok] wrote {GROUND_TRUTH_PATH.relative_to(PROJECT_ROOT)} "
          f"({len(questions)} question(s))")

    review_rng = random.Random(SEED)
    review_sample = write_review_sample(questions, review_rng)
    with open(REVIEW_SAMPLE_PATH, "w", encoding="utf-8") as f:
        json.dump(review_sample, f, indent=2, ensure_ascii=False)
        f.write("\n")
    print(f"[ok] wrote {REVIEW_SAMPLE_PATH.relative_to(PROJECT_ROOT)} "
          f"({len(review_sample)} pair(s))")

    print(
        "\nREQUIRED NEXT STEP (per the 2026-07-22 design review, not optional): "
        "hand-review the pairs in "
        f"{REVIEW_SAMPLE_PATH.relative_to(PROJECT_ROOT)} for circularity — does "
        "each question actually require understanding the passage, or does it "
        "just echo the passage's own wording back? Do this before trusting "
        "evaluate.py's results."
    )


if __name__ == "__main__":
    main()
