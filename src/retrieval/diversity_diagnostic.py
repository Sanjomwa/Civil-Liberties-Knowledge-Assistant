"""
diversity_diagnostic.py -- investigates why hybrid/vector retrieval show
lower source-diversity@10 than text search (see decisionlog.md, 2026-07-22:
text 1.59 orgs/4.28 docs vs. hybrid k=10 1.50/3.68 vs. vector 1.48/3.74).

Working hypothesis, derivable from those three numbers alone before this
script runs: vector search's narrower spread (already close to hybrid's,
both below text) suggests the *vector* backend is the one driving hybrid's
lower diversity, not an RRF-fusion artifact -- embedding similarity is
smooth, so several chunks from one topically-rich document can all score
highly for the same query, while TF-IDF's sparse exact-term matching tends
to spread hits more evenly across whichever documents happen to contain
the specific matched terms.

This script tests that hypothesis two ways:
  1. For every ground-truth question, compares hybrid's top-10 doc_id set
     against vector's and text's -- if hybrid's set overlaps more with
     vector's than text's on most questions, that's direct evidence the
     vector backend is driving the narrowing, not RRF combination itself.
  2. Prints the 5 questions with the largest text-vs-hybrid diversity gap
     (by distinct doc_id count) side-by-side -- so the actual clustering
     pattern is visible on real examples, not just inferred from aggregate
     numbers.

Diagnostic only -- does not change default_method.json or any retrieval
code, and doesn't touch the recorded default (hybrid, k=10).

Usage:
    uv run python src/retrieval/diversity_diagnostic.py
        # reads data/eval/ground_truth_filtered.json, writes
        # data/eval/diversity_diagnostic.md
"""

import json
from pathlib import Path

from search import search

PROJECT_ROOT = Path(__file__).resolve().parents[2]
EVAL_DIR = PROJECT_ROOT / "data" / "eval"
GROUND_TRUTH_PATH = EVAL_DIR / "ground_truth_filtered.json"
OUTPUT_PATH = EVAL_DIR / "diversity_diagnostic.md"

TOP_K = 10


def doc_ids_for(question: str, method: str) -> set[str]:
    return {r["doc_id"] for r in search(question, top_k=TOP_K, method=method)}


def main() -> None:
    with open(GROUND_TRUTH_PATH, encoding="utf-8") as f:
        data = json.load(f)
    questions = [q["question"] for q in data["questions"]]

    overlaps_more_with_vector = 0
    overlaps_more_with_text = 0
    tied = 0
    gaps = []  # (gap, question, text_docs, hybrid_docs, vector_docs)

    for q in questions:
        text_docs = doc_ids_for(q, "text")
        vector_docs = doc_ids_for(q, "vector")
        hybrid_docs = doc_ids_for(q, "hybrid")

        denom = max(len(hybrid_docs), 1)
        overlap_vector = len(hybrid_docs & vector_docs) / denom
        overlap_text = len(hybrid_docs & text_docs) / denom
        if overlap_vector > overlap_text:
            overlaps_more_with_vector += 1
        elif overlap_text > overlap_vector:
            overlaps_more_with_text += 1
        else:
            tied += 1

        gap = len(text_docs) - len(hybrid_docs)
        gaps.append((gap, q, text_docs, hybrid_docs, vector_docs))

    gaps.sort(key=lambda x: x[0], reverse=True)
    total = len(questions)

    lines = [
        "# Source-Diversity Diagnostic\n",
        f"n={total} questions (from `{GROUND_TRUTH_PATH.name}`).\n",
        "## Part 1 -- which backend does hybrid's doc set resemble more?\n",
        f"Hybrid's top-{TOP_K} doc_id set overlaps MORE with **vector's** "
        f"than text's in {overlaps_more_with_vector}/{total} questions "
        f"({overlaps_more_with_vector / total:.1%}); more with **text's** "
        f"in {overlaps_more_with_text}/{total} "
        f"({overlaps_more_with_text / total:.1%}); tied in {tied}.\n",
        "If the vector-leaning share is clearly the majority, that's "
        "direct evidence the vector backend -- not RRF fusion itself -- "
        "is what narrows hybrid's source diversity relative to text.\n",
        "## Part 2 -- top 5 largest text-vs-hybrid diversity gaps\n",
    ]
    for gap, q, text_docs, hybrid_docs, vector_docs in gaps[:5]:
        lines.append(f"### Gap={gap}: {q}\n")
        lines.append(f"- text top-{TOP_K} docs ({len(text_docs)} distinct): {sorted(text_docs)}\n")
        lines.append(f"- hybrid top-{TOP_K} docs ({len(hybrid_docs)} distinct): {sorted(hybrid_docs)}\n")
        lines.append(f"- vector top-{TOP_K} docs ({len(vector_docs)} distinct): {sorted(vector_docs)}\n")

    OUTPUT_PATH.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"[ok] wrote {OUTPUT_PATH.relative_to(PROJECT_ROOT)} "
          f"({overlaps_more_with_vector}/{total} vector-leaning, "
          f"{overlaps_more_with_text}/{total} text-leaning, {tied} tied)")


if __name__ == "__main__":
    main()
