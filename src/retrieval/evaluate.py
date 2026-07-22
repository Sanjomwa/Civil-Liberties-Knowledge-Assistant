"""
evaluate.py — Hit Rate / MRR per method, per category slice, RRF k-swept.

Runs every question in data/eval/ground_truth.json through search.search()
for each candidate method (text, vector, hybrid at several RRF k values —
mirroring 04-evaluation's own HW4 k-sweep, not assuming a single default)
and reports Hit Rate and MRR, both in aggregate and broken out per
category slice (multi_country / ooni_methodology / general, as assigned by
ground_truth.py).

Method-selection fix (from the 2026-07-22 Opus design review): this script
does NOT auto-crown a winner from the aggregate score alone. It writes a
report table; the actual default method for the next (generation) phase is
a human decision, informed by that table — explicitly including whether
the winning method still holds up on every slice, not just in aggregate.
project_evaluation_plan.md names citation-adjacent evidence quality as this
project's most safety-relevant concern, so a method that wins in aggregate
but does worse specifically where evidence is hardest to retrieve
correctly is a real red flag, not a footnote.

Recording the human decision: after reading data/eval/evaluation-report.md,
run this script again with --set-default to write
data/eval/default_method.json — the artifact the generation phase reads
its starting config from. This is a separate, explicit, later invocation
(not automatic) so the decision is deliberate, not defaulted.

Usage:
    uv run python src/retrieval/evaluate.py
    uv run python src/retrieval/evaluate.py --set-default hybrid --rrf-k 30
"""

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from search import search  # noqa: E402 — needs sys.path set first

PROJECT_ROOT = Path(__file__).resolve().parents[2]
EVAL_DIR = PROJECT_ROOT / "data" / "eval"
GROUND_TRUTH_PATH = EVAL_DIR / "ground_truth.json"
FILTERED_GROUND_TRUTH_PATH = EVAL_DIR / "ground_truth_filtered.json"
REPORT_PATH = EVAL_DIR / "evaluation-report.md"
DEFAULT_METHOD_PATH = EVAL_DIR / "default_method.json"

TOP_K = 10
RRF_K_SWEEP = [1, 10, 30, 60, 100]
CATEGORIES = ["multi_country", "ooni_methodology", "general"]


def load_ground_truth() -> tuple[list[dict], Path]:
    """Prefers ground_truth_filtered.json (written by
    filter_ground_truth.py) if it exists -- added 2026-07-22 after two
    rounds of prompt-only circularity fixes plateaued around ~24%
    flagged; filtering the existing 150 questions was chosen over a
    third full re-run, see decisionlog.md. Falls back to the unfiltered
    ground_truth.json if the filter step hasn't been run, so this script
    still works standalone. Returns the path too (not just the
    questions) -- write_report() uses it so the report's own text names
    whichever file was actually loaded, rather than a hardcoded string
    that silently goes stale, which is exactly what happened here until
    caught in Claude Code's own reports.md verification (2026-07-22)."""
    if FILTERED_GROUND_TRUTH_PATH.exists():
        path = FILTERED_GROUND_TRUTH_PATH
    elif GROUND_TRUTH_PATH.exists():
        path = GROUND_TRUTH_PATH
    else:
        print(f"No {GROUND_TRUTH_PATH.relative_to(PROJECT_ROOT)} found — run "
              f"src/retrieval/ground_truth.py first.", file=sys.stderr)
        sys.exit(1)
    with open(path, encoding="utf-8") as f:
        questions = json.load(f)["questions"]
    print(f"[ok] loaded {len(questions)} ground-truth question(s) from "
          f"{path.relative_to(PROJECT_ROOT)}")
    return questions, path


def hit_rate_and_mrr(questions: list[dict], method: str, rrf_k: int | None) -> dict:
    """Runs every question through search(), returns aggregate + per-category
    hit_rate/mrr for this one method (and, for hybrid, this one rrf_k)."""
    per_category_hits = {c: [] for c in CATEGORIES}
    per_category_rr = {c: [] for c in CATEGORIES}

    for q in questions:
        kwargs = {"top_k": TOP_K, "method": method}
        if method == "hybrid":
            kwargs["rrf_k"] = rrf_k
        results = search(q["question"], **kwargs)
        result_ids = [r["chunk_id"] for r in results]

        category = q.get("category", "general")
        if q["correct_chunk_id"] in result_ids:
            rank = result_ids.index(q["correct_chunk_id"]) + 1
            per_category_hits[category].append(1)
            per_category_rr[category].append(1.0 / rank)
        else:
            per_category_hits[category].append(0)
            per_category_rr[category].append(0.0)

    def avg(values: list[float]) -> float:
        return sum(values) / len(values) if values else 0.0

    all_hits = [h for cat in per_category_hits.values() for h in cat]
    all_rr = [r for cat in per_category_rr.values() for r in cat]

    return {
        "aggregate": {"hit_rate": avg(all_hits), "mrr": avg(all_rr), "n": len(all_hits)},
        "per_category": {
            cat: {
                "hit_rate": avg(per_category_hits[cat]),
                "mrr": avg(per_category_rr[cat]),
                "n": len(per_category_hits[cat]),
            }
            for cat in CATEGORIES
        },
    }


def run_all_methods(questions: list[dict]) -> dict:
    results = {}
    for method in ("text", "vector"):
        print(f"[eval] method={method}...")
        results[method] = hit_rate_and_mrr(questions, method, rrf_k=None)

    results["hybrid"] = {}
    for k in RRF_K_SWEEP:
        print(f"[eval] method=hybrid, rrf_k={k}...")
        results["hybrid"][k] = hit_rate_and_mrr(questions, "hybrid", rrf_k=k)

    return results


def write_report(results: dict, n_questions: int, ground_truth_path: Path) -> None:
    lines = [
        "# Retrieval Evaluation Report\n",
        f"Generated by evaluate.py against {n_questions} ground-truth question(s) "
        f"({ground_truth_path.relative_to(PROJECT_ROOT)}). top_k={TOP_K}.\n",
        "**No method is auto-selected as a default here — per the 2026-07-22 "
        "design review, that's a human decision informed by the per-slice "
        "results below, not an aggregate-only auto-pick.**\n",
        "## Aggregate\n",
        "| Method | Hit Rate | MRR | n |",
        "|---|---|---|---|",
    ]
    for method in ("text", "vector"):
        agg = results[method]["aggregate"]
        lines.append(f"| {method} | {agg['hit_rate']:.3f} | {agg['mrr']:.3f} | {agg['n']} |")
    for k, r in results["hybrid"].items():
        agg = r["aggregate"]
        lines.append(f"| hybrid (k={k}) | {agg['hit_rate']:.3f} | {agg['mrr']:.3f} | {agg['n']} |")

    lines.append("\n## Per-category slice\n")
    lines.append(
        "Whether the aggregate winner also holds up here — especially on "
        "categories where evidence is hardest to retrieve correctly — matters "
        "more than the aggregate row alone (project_evaluation_plan.md's own "
        "citation-precision priority).\n"
    )
    for category in CATEGORIES:
        lines.append(f"### {category}\n")
        lines.append("| Method | Hit Rate | MRR | n |")
        lines.append("|---|---|---|---|")
        for method in ("text", "vector"):
            pc = results[method]["per_category"][category]
            lines.append(f"| {method} | {pc['hit_rate']:.3f} | {pc['mrr']:.3f} | {pc['n']} |")
        for k, r in results["hybrid"].items():
            pc = r["per_category"][category]
            lines.append(f"| hybrid (k={k}) | {pc['hit_rate']:.3f} | {pc['mrr']:.3f} | {pc['n']} |")
        lines.append("")

    lines.append(
        "\nOnce reviewed, record the chosen default method by running:\n"
        "`uv run python src/retrieval/evaluate.py --set-default <text|vector|hybrid> "
        "[--rrf-k <k>]`\n"
    )

    EVAL_DIR.mkdir(parents=True, exist_ok=True)
    with open(REPORT_PATH, "w", encoding="utf-8") as f:
        f.write("\n".join(lines) + "\n")
    print(f"\n[ok] wrote {REPORT_PATH.relative_to(PROJECT_ROOT)}")


def set_default_method(method: str, rrf_k: int | None) -> None:
    if not REPORT_PATH.exists():
        print(f"No {REPORT_PATH.relative_to(PROJECT_ROOT)} found — run evaluate.py "
              f"once without --set-default first, and review it, before recording "
              f"a default.", file=sys.stderr)
        sys.exit(1)
    config = {"method": method}
    if method == "hybrid":
        if rrf_k is None:
            print("Method 'hybrid' requires --rrf-k.", file=sys.stderr)
            sys.exit(1)
        config["rrf_k"] = rrf_k

    EVAL_DIR.mkdir(parents=True, exist_ok=True)
    with open(DEFAULT_METHOD_PATH, "w", encoding="utf-8") as f:
        json.dump(config, f, indent=2)
        f.write("\n")
    print(f"[ok] wrote {DEFAULT_METHOD_PATH.relative_to(PROJECT_ROOT)} — {config}")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--set-default", choices=["text", "vector", "hybrid"])
    parser.add_argument("--rrf-k", type=int)
    args = parser.parse_args()

    if args.set_default:
        set_default_method(args.set_default, args.rrf_k)
        return

    questions, ground_truth_path = load_ground_truth()
    results = run_all_methods(questions)
    write_report(results, len(questions), ground_truth_path)


if __name__ == "__main__":
    main()
