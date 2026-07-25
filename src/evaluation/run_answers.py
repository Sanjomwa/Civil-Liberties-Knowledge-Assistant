"""
run_answers.py -- runs answer() from src/generation/generate.py over the
full evaluation question set: the existing 97/101-question retrieval
ground truth reuse (data/eval/ground_truth_filtered.json), a hand-authored
synthesis supplement, and a hand-authored refusal slice (both in
data/eval/eval_supplement_questions.json). Each question is tagged with a
`category`.

Per ADR-0011: answer() itself does not return retrieved chunk text (only
citations, which resolve marker -> chunk_id/doc_id/pages, not the chunk's
actual text). This script independently calls search() a second time
(same query, same recorded default hybrid k=10) to reconstruct and
persist the retrieved {chunk_id: text} map alongside each result --
search() is deterministic given the same corpus/index, so this reliably
reconstructs the same top-10 set answer() used internally, without
modifying generate.py itself.

Writes results incrementally (JSONL, one line per question) to
data/eval/generation_results.jsonl -- a full run is real time and real
money, so this must be interruptible and resumable, not one big JSON
write at the end.

Usage:
    uv run python src/evaluation/run_answers.py [--limit N] [--resume]
"""

import argparse
import json
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
# generate.py itself relies on its own directory being on sys.path for its
# bare `from citations import ...` / `from prompts import ...` imports --
# that only happens automatically when generate.py is the __main__ script.
# Since this script imports generate.py as a module, both its directory
# and the shared src/ (for retrieval.search) must be added explicitly.
sys.path.insert(0, str(PROJECT_ROOT / "src"))
sys.path.insert(0, str(PROJECT_ROOT / "src" / "generation"))

from generate import answer  # noqa: E402
from retrieval.search import search  # noqa: E402

EVAL_DIR = PROJECT_ROOT / "data" / "eval"
GROUND_TRUTH_PATH = EVAL_DIR / "ground_truth_filtered.json"
SUPPLEMENT_PATH = EVAL_DIR / "eval_supplement_questions.json"
RESULTS_PATH = EVAL_DIR / "generation_results.jsonl"

# Matches generate.py's own TOP_K / recorded hybrid default -- this is the
# same call answer() makes internally (method="hybrid", rrf_k=None so it
# resolves data/eval/default_method.json), not a second decision.
SEARCH_TOP_K = 10


def load_question_set() -> list[dict]:
    """Combines the ground-truth reuse set, the synthesis supplement, and
    the refusal slice into one ordered list, each entry tagged with a
    stable, category-scoped question_id. Order is deterministic given
    unchanged input files -- that determinism is what makes --resume safe
    (a question_id must mean the same question across runs)."""
    questions = []

    with open(GROUND_TRUTH_PATH, encoding="utf-8") as f:
        gt = json.load(f)
    for i, q in enumerate(gt["questions"]):
        questions.append({
            "question_id": f"{q['category']}-{i:04d}",
            "question": q["question"],
            "category": q["category"],
            "expected_behavior": "answer",
        })

    with open(SUPPLEMENT_PATH, encoding="utf-8") as f:
        supplement = json.load(f)
    for i, q in enumerate(supplement["synthesis_supplement"]):
        questions.append({
            "question_id": f"synthesis_supplement-{i:04d}",
            "question": q["question"],
            "category": "synthesis_supplement",
            "expected_behavior": "answer",
        })
    for i, q in enumerate(supplement["refusal_slice"]):
        questions.append({
            "question_id": f"refusal-{i:04d}",
            "question": q["question"],
            "category": "refusal",
            "expected_behavior": q["expected_behavior"],
            "rationale": q["rationale"],
        })

    return questions


def load_done_ids() -> set[str]:
    if not RESULTS_PATH.exists():
        return set()
    done = set()
    with open(RESULTS_PATH, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            done.add(json.loads(line)["question_id"])
    return done


def run_one(item: dict) -> dict:
    """Runs answer() and an independent search() call for one question,
    combining both into one persisted result record."""
    result = answer(item["question"])
    chunks = search(item["question"], top_k=SEARCH_TOP_K, method="hybrid")
    chunk_text_map = {c["chunk_id"]: c["text"] for c in chunks}

    record = {
        "question_id": item["question_id"],
        "question": item["question"],
        "category": item["category"],
        "expected_behavior": item["expected_behavior"],
        "answer_markdown": result["answer_markdown"],
        "citations": result["citations"],
        "invalid_markers": result["invalid_markers"],
        "unsupported_paragraphs": result["unsupported_paragraphs"],
        "sourcing": result["sourcing"],
        "usage": result["usage"],
        "retrieved_chunks": chunk_text_map,
        "n_retrieved": len(chunks),
    }
    if "rationale" in item:
        record["rationale"] = item["rationale"]
    return record


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--limit", type=int, default=None,
                         help="Process at most N pending questions this invocation.")
    parser.add_argument("--resume", action="store_true",
                         help="Skip questions already present in generation_results.jsonl.")
    args = parser.parse_args()

    questions = load_question_set()
    done_ids = load_done_ids() if args.resume else set()

    pending = [q for q in questions if q["question_id"] not in done_ids]
    if args.limit is not None:
        pending = pending[: args.limit]

    print(f"[ok] {len(questions)} total question(s) in the combined set "
          f"({len(done_ids)} already done, {len(pending)} to run this invocation).")

    if not pending:
        print("[ok] nothing to do.")
        return

    EVAL_DIR.mkdir(parents=True, exist_ok=True)
    total_calls = 0
    total_prompt_tokens = 0
    total_completion_tokens = 0
    total_failed = 0

    with open(RESULTS_PATH, "a", encoding="utf-8") as f:
        for i, item in enumerate(pending, start=1):
            try:
                record = run_one(item)
            except Exception as e:  # noqa: BLE001 -- one bad question shouldn't kill the whole run
                print(f"[FAIL] {item['question_id']} -- {e}", file=sys.stderr)
                total_failed += 1
                continue
            f.write(json.dumps(record, ensure_ascii=False) + "\n")
            f.flush()
            total_calls += 1
            if record["usage"]:
                total_prompt_tokens += record["usage"]["prompt_tokens"]
                total_completion_tokens += record["usage"]["completion_tokens"]
            print(f"[{i}/{len(pending)}] {item['question_id']} done ({item['category']})")

    print(f"\n[ok] wrote {total_calls} result(s) to "
          f"{RESULTS_PATH.relative_to(PROJECT_ROOT)} ({total_failed} failed)")
    print(f"[cost] this invocation: {total_calls} answer() call(s), "
          f"{total_prompt_tokens} prompt token(s), "
          f"{total_completion_tokens} completion token(s)")


if __name__ == "__main__":
    main()
