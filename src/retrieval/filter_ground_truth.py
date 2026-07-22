"""
filter_ground_truth.py -- drops ground-truth questions that lift a
descriptive phrase near-verbatim from their own source chunk.

Built 2026-07-22, after two rounds of prompt-only circularity fixes on
ground_truth.py plateaued around ~24% flagged in Sam's own manual
review each time (self-referential phrasing got fully eliminated on the
second pass, but a citation/survey-header-echo pattern took its place
at similar volume -- see decisionlog.md, 2026-07-22, for both review
write-ups). Rather than spend a third full LLM re-run chasing
diminishing returns on pure prompting, this mechanically applies the
same rule QUESTION_SYSTEM_PROMPT already states to the model -- "if a
phrase in your draft question shares 4+ consecutive words with the
passage, and that phrase is a description or characterization (not a
proper noun/date/place name), rewrite it" -- as a downstream filter,
instead of only trusting the model to have followed it.

Scope, stated honestly, not oversold: this catches literal
verbatim-phrase lifts (the majority of what both reviews flagged --
e.g. a Freedom on the Net indicator header like "Are there laws that
assign criminal penalties..." echoed almost directly into the
question). It will NOT catch a looser paraphrase of a citation's own
title (e.g. a footnote titled "Uganda Blocks Facebook Ahead of
Contentious Election" turned into "Which country blocked Facebook
before a disputed election?") that doesn't share a strict 4-word run --
that subtler case still needs an actual human read to catch. This
narrows the remaining manual-review burden; it does not eliminate the
need for one entirely, and evaluate.py's results should still be read
with that residual caveat in mind.

Proper nouns, dates, and numbers are exempted from the phrase-overlap
check (per the prompt's own stated exception) via a simple heuristic:
an n-gram made entirely of capitalized tokens and/or digits is allowed
to overlap.

Usage:
    uv run python src/retrieval/filter_ground_truth.py
        # reads data/eval/ground_truth.json, writes
        # data/eval/ground_truth_filtered.json (the questions kept) and
        # data/eval/filter_report.md (what was dropped and why).
        # evaluate.py prefers the filtered file automatically if present.
"""

import json
import re
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
CHUNKS_DIR = PROJECT_ROOT / "data" / "chunks"
EVAL_DIR = PROJECT_ROOT / "data" / "eval"
GROUND_TRUTH_PATH = EVAL_DIR / "ground_truth.json"
FILTERED_PATH = EVAL_DIR / "ground_truth_filtered.json"
REPORT_PATH = EVAL_DIR / "filter_report.md"

N_GRAM = 4


def load_chunk_text(doc_id: str, chunk_id: str) -> str | None:
    chunk_path = CHUNKS_DIR / doc_id / f"{chunk_id}.json"
    if not chunk_path.exists():
        return None
    with open(chunk_path, encoding="utf-8") as f:
        return json.load(f)["text"]


def tokenize(text: str) -> list[str]:
    return re.findall(r"[A-Za-z']+|\d+", text)


def is_exempt_ngram(tokens: tuple[str, ...]) -> bool:
    """A run made entirely of capitalized tokens (proper nouns) and/or
    digits (dates, counts) is allowed to overlap -- only a descriptive
    phrase shared verbatim should be flagged, per the prompt's own
    stated exception."""
    return all(t[0].isupper() or t.isdigit() for t in tokens)


def shared_descriptive_ngram(question: str, chunk_text: str, n: int = N_GRAM) -> str | None:
    """Returns the first shared n-gram (lowercased) found between the
    question and its source chunk that isn't proper-noun/date-exempt,
    or None if there's no such overlap."""
    q_tokens = tokenize(question)
    c_tokens = tokenize(chunk_text)

    c_ngrams = set()
    for i in range(len(c_tokens) - n + 1):
        window = tuple(c_tokens[i:i + n])
        if is_exempt_ngram(window):
            continue
        c_ngrams.add(tuple(t.lower() for t in window))

    for i in range(len(q_tokens) - n + 1):
        window = tuple(t.lower() for t in q_tokens[i:i + n])
        if window in c_ngrams:
            return " ".join(window)
    return None


def main() -> None:
    if not GROUND_TRUTH_PATH.exists():
        print(f"No {GROUND_TRUTH_PATH.relative_to(PROJECT_ROOT)} found -- run "
              f"src/retrieval/ground_truth.py first.", file=sys.stderr)
        sys.exit(1)
    with open(GROUND_TRUTH_PATH, encoding="utf-8") as f:
        data = json.load(f)

    kept, dropped = [], []
    unverifiable = 0
    for q in data["questions"]:
        chunk_text = load_chunk_text(q["doc_id"], q["correct_chunk_id"])
        if chunk_text is None:
            # Chunk file missing -- can't verify, keep it rather than
            # silently dropping a question we couldn't actually check.
            kept.append(q)
            unverifiable += 1
            continue
        hit = shared_descriptive_ngram(q["question"], chunk_text)
        if hit:
            dropped.append({**q, "_flagged_phrase": hit})
        else:
            kept.append(q)

    EVAL_DIR.mkdir(parents=True, exist_ok=True)
    filtered_output = {
        "sampling": data["sampling"],
        "filter": {
            "n_gram": N_GRAM,
            "total_before": len(data["questions"]),
            "dropped": len(dropped),
            "kept": len(kept),
            "unverifiable_chunk_missing": unverifiable,
        },
        "questions": kept,
    }
    with open(FILTERED_PATH, "w", encoding="utf-8") as f:
        json.dump(filtered_output, f, indent=2, ensure_ascii=False)
        f.write("\n")

    report_lines = [
        "# Ground Truth Circularity Filter Report\n",
        f"{len(dropped)}/{len(data['questions'])} question(s) dropped for sharing a "
        f"{N_GRAM}+-word descriptive phrase with their own source chunk "
        f"(proper nouns/dates exempted). {len(kept)} kept for evaluate.py "
        f"(of which {unverifiable} could not be verified -- source chunk file "
        f"missing -- and were kept rather than dropped unchecked).\n",
        "**Scope reminder:** this catches verbatim phrase lifts only. Looser "
        "paraphrases of a citation's own title won't be caught here -- see this "
        "script's own module docstring.\n",
        "## Dropped\n",
    ]
    for q in dropped:
        report_lines.append(
            f"- `{q['correct_chunk_id']}` (flagged phrase: \"{q['_flagged_phrase']}\")\n"
            f"  Q: {q['question']}\n"
        )
    with open(REPORT_PATH, "w", encoding="utf-8") as f:
        f.write("\n".join(report_lines) + "\n")

    print(f"[ok] {len(kept)} kept, {len(dropped)} dropped "
          f"({unverifiable} unverifiable, kept by default) -- see "
          f"{REPORT_PATH.relative_to(PROJECT_ROOT)} for details")
    print(f"[ok] wrote {FILTERED_PATH.relative_to(PROJECT_ROOT)}")


if __name__ == "__main__":
    main()
