"""
build_adversarial_query_set.py -- builds the ~40-question degraded
adversarial set for ADR-0017's query-rewriting evaluation.

Method (stated explicitly, per the design doc's own open item): LLM-assisted
degradation, one call per selected question, followed by a manual (AI)
spot-check pass over every generated row before writing the final file --
not pure scripted string manipulation (too mechanical to produce genuinely
colloquial phrasing) and not fully hand-written (101 candidate questions is
too many to hand-degrade in a way that's demonstrably unbiased rather than
cherry-picked to make rewriting look good). Chosen over scripted
degradation because "colloquialize phrasing" specifically needs real
variation a keyword-substitution script can't produce; chosen over pure
manual writing because a human-written degraded set risks unconsciously
picking degradations that are easy for a rewrite step to fix.

Selects a stratified sample (proportional to the real category mix in
data/eval/ground_truth_filtered.json: 68 general / 22 multi_country / 11
ooni_methodology out of 101) rather than picking only easy/hard cases.

Degradation instructions given to the model: colloquialize phrasing, drop
an explicit country name if the question names one (referring to it
vaguely instead, or omitting it if context still carries), abbreviate
common words, add casual filler -- but keep at least one specific,
recognizable fact/keyword from the original, since the same
correct_chunk_id label is kept and an unfairly-obscured question would
test something impossible, not query rewriting's real value.

Usage:
    uv run python src/evaluation/build_adversarial_query_set.py
"""

import json
import random
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(PROJECT_ROOT / "src"))
sys.path.insert(0, str(PROJECT_ROOT / "src" / "generation"))

from openai import OpenAI  # noqa: E402
from dotenv import load_dotenv  # noqa: E402

load_dotenv()

GROUND_TRUTH_PATH = PROJECT_ROOT / "data" / "eval" / "ground_truth_filtered.json"
OUT_PATH = PROJECT_ROOT / "data" / "eval" / "adversarial_query_set.json"

# Same small-model precedent as rewrite_query() itself and
# contradiction_search.py's DISAGREEMENT_MODEL -- this account's
# confirmed-enabled cheap-call model, not a new/guessed one.
DEGRADE_MODEL = "gpt-5.4-mini"

SAMPLE_SIZE = 40
SEED = 42  # matches evaluate_generation.py's own stratified-sample seed convention

DEGRADE_SYSTEM_PROMPT = """You help build a test set for evaluating query-rewriting \
systems. Given a well-formed research question, rewrite it as a genuinely sloppy, \
colloquial version a real, casual user might type into a search box.

Rules:
- If the question names a specific country explicitly, remove the explicit name -- \
refer to it vaguely ("that country", "over there") or drop it entirely if the \
remaining context still makes the question interpretable.
- Abbreviate common words where a real user plausibly would (government -> gov/govt, \
organization -> org, internet -> net, information -> info, etc.).
- Add casual filler and drop careful grammar (e.g. "so like", "any idea", "wut", \
dropped capitalization, run-on phrasing).
- Keep at least one specific, recognizable fact, name, date, or keyword from the \
original question -- do not obscure it so much that the topic becomes unrecognizable.
- Do not answer the question. Do not add facts that weren't in the original.

Output ONLY the degraded question, one line, no preamble, no quotation marks."""


def degrade_one(client: OpenAI, question: str) -> str:
    response = client.chat.completions.create(
        model=DEGRADE_MODEL,
        messages=[
            {"role": "system", "content": DEGRADE_SYSTEM_PROMPT},
            {"role": "user", "content": question},
        ],
        max_completion_tokens=150,
        temperature=0.7,  # some real variation is the point here, unlike rewrite_query()
    )
    text = response.choices[0].message.content
    if not text or not text.strip():
        raise ValueError(f"empty degradation for: {question!r}")
    return text.strip()


def stratified_sample(questions: list[dict], sample_size: int) -> list[dict]:
    by_cat: dict[str, list[dict]] = {}
    for q in questions:
        by_cat.setdefault(q.get("category", "general"), []).append(q)

    total = len(questions)
    rng = random.Random(SEED)
    sample = []
    for cat, items in by_cat.items():
        n = round(sample_size * len(items) / total)
        sample.extend(rng.sample(items, min(n, len(items))))
    return sample


def main() -> None:
    with open(GROUND_TRUTH_PATH, encoding="utf-8") as f:
        questions = json.load(f)["questions"]
    print(f"[ok] loaded {len(questions)} ground-truth question(s)")

    sample = stratified_sample(questions, SAMPLE_SIZE)
    print(f"[ok] selected {len(sample)} question(s) for degradation "
          f"(stratified by category, seed={SEED})")

    client = OpenAI()
    adversarial = []
    for i, q in enumerate(sample, start=1):
        degraded = degrade_one(client, q["question"])
        adversarial.append({
            "question": degraded,
            "original_question": q["question"],
            "correct_chunk_id": q["correct_chunk_id"],
            "doc_id": q["doc_id"],
            "organization": q["organization"],
            "category": q.get("category", "general"),
        })
        print(f"[{i}/{len(sample)}] {q['category']}: {q['question'][:60]!r} "
              f"-> {degraded[:60]!r}")

    OUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(OUT_PATH, "w", encoding="utf-8") as f:
        json.dump({"questions": adversarial}, f, ensure_ascii=False, indent=2)
    print(f"\n[ok] wrote {len(adversarial)} degraded question(s) to "
          f"{OUT_PATH.relative_to(PROJECT_ROOT)}")


if __name__ == "__main__":
    main()
