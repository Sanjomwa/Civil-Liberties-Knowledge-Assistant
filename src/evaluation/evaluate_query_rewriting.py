"""
evaluate_query_rewriting.py -- ADR-0017's two evaluation runs, both
reusing src/retrieval/evaluate.py's own hit_rate_and_mrr() unchanged (not
reimplementing Hit Rate/MRR scoring here): raw query text vs.
generate.rewrite_query()'s output, same ground-truth chunk labels, same
method (hybrid, recorded default rrf_k=10 via search()'s own resolution).

Two question sets, selected via --set:
    regression  -- full data/eval/ground_truth_filtered.json (101
                   questions). Safety check: deltas should be within noise.
    adversarial -- data/eval/adversarial_query_set.json (40 degraded
                   questions, built by build_adversarial_query_set.py).
                   This is where a real gain, if any, should show up.

Rewritten queries are computed once and cached to
data/eval/query_rewrites_cache.json (keyed by the exact raw query text)
so re-running this script (e.g. after a report-formatting fix) doesn't
re-spend real API calls recomputing the same rewrites.

Usage:
    uv run python src/evaluation/evaluate_query_rewriting.py --set regression
    uv run python src/evaluation/evaluate_query_rewriting.py --set adversarial
"""

import argparse
import json
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(PROJECT_ROOT / "src"))
sys.path.insert(0, str(PROJECT_ROOT / "src" / "retrieval"))
sys.path.insert(0, str(PROJECT_ROOT / "src" / "generation"))

from evaluate import hit_rate_and_mrr, CATEGORIES  # noqa: E402
from generate import rewrite_query  # noqa: E402
from openai import OpenAI  # noqa: E402
from dotenv import load_dotenv  # noqa: E402

load_dotenv()

EVAL_DIR = PROJECT_ROOT / "data" / "eval"
GROUND_TRUTH_PATH = EVAL_DIR / "ground_truth_filtered.json"
ADVERSARIAL_PATH = EVAL_DIR / "adversarial_query_set.json"
CACHE_PATH = EVAL_DIR / "query_rewrites_cache.json"


def load_questions(which: str) -> list[dict]:
    path = GROUND_TRUTH_PATH if which == "regression" else ADVERSARIAL_PATH
    with open(path, encoding="utf-8") as f:
        return json.load(f)["questions"]


def load_cache() -> dict:
    if CACHE_PATH.exists():
        with open(CACHE_PATH, encoding="utf-8") as f:
            return json.load(f)
    return {}


def save_cache(cache: dict) -> None:
    with open(CACHE_PATH, "w", encoding="utf-8") as f:
        json.dump(cache, f, ensure_ascii=False, indent=2)


def build_rewritten_questions(questions: list[dict]) -> list[dict]:
    cache = load_cache()
    client = OpenAI()
    rewritten = []
    n_cache_hits = 0
    for i, q in enumerate(questions, start=1):
        raw = q["question"]
        if raw in cache:
            rw = cache[raw]
            n_cache_hits += 1
        else:
            rw = rewrite_query(raw, client=client)
            cache[raw] = rw
        rewritten.append({**q, "question": rw})
        if i % 10 == 0 or i == len(questions):
            print(f"[{i}/{len(questions)}] rewritten ({n_cache_hits} cache hit(s) so far)")
    save_cache(cache)
    return rewritten


def fmt_delta(raw_v: float, rw_v: float) -> str:
    delta = rw_v - raw_v
    sign = "+" if delta >= 0 else ""
    return f"{sign}{delta:.4f}"


def write_comparison_report(which: str, raw_metrics: dict, rw_metrics: dict, n: int) -> Path:
    out_path = EVAL_DIR / f"query-rewriting-{which}-report.md"
    lines = [
        f"# Query rewriting evaluation -- {which} set ({n} questions)",
        "",
        "Both runs use `src/retrieval/evaluate.py`'s own `hit_rate_and_mrr()` "
        "unchanged, method=hybrid, rrf_k=recorded default (10). Only the "
        "query text fed to `search()` differs: raw vs. "
        "`generate.rewrite_query()`'s output.",
        "",
        "## Aggregate",
        "",
        "| Metric | Raw | Rewritten | Delta |",
        "|---|---|---|---|",
    ]
    ra, rw = raw_metrics["aggregate"], rw_metrics["aggregate"]
    for key, label in [
        ("hit_rate", "Hit Rate"), ("mrr", "MRR"),
        ("relaxed_hit_rate", "Relaxed Hit Rate"), ("relaxed_mrr", "Relaxed MRR"),
        ("hit_rate_at_3", "Hit Rate@3"), ("hit_rate_at_5", "Hit Rate@5"),
    ]:
        lines.append(f"| {label} | {ra[key]:.4f} | {rw[key]:.4f} | {fmt_delta(ra[key], rw[key])} |")
    lines.append(f"| n | {ra['n']} | {rw['n']} | |")

    lines.append("")
    lines.append("### 95% bootstrap CI (strict Hit Rate / MRR only, 2000 resamples)")
    lines.append("")
    lines.append("| Metric | Raw CI | Rewritten CI | CIs overlap? |")
    lines.append("|---|---|---|---|")
    for key, label in [("hit_rate_ci95", "Hit Rate"), ("mrr_ci95", "MRR")]:
        ra_lo, ra_hi = ra[key]
        rw_lo, rw_hi = rw[key]
        overlap = "yes (not distinguishable at 95%)" if ra_lo <= rw_hi and rw_lo <= ra_hi else "no"
        lines.append(f"| {label} | [{ra_lo:.4f}, {ra_hi:.4f}] | [{rw_lo:.4f}, {rw_hi:.4f}] | {overlap} |")

    lines.append("")
    lines.append("## Per category")
    lines.append("")
    for cat in CATEGORIES:
        ra_c = raw_metrics["per_category"][cat]
        rw_c = rw_metrics["per_category"][cat]
        lines.append(f"### {cat} (n={ra_c['n']})")
        lines.append("")
        lines.append("| Metric | Raw | Rewritten | Delta |")
        lines.append("|---|---|---|---|")
        for key, label in [("hit_rate", "Hit Rate"), ("mrr", "MRR")]:
            lines.append(f"| {label} | {ra_c[key]:.4f} | {rw_c[key]:.4f} | "
                          f"{fmt_delta(ra_c[key], rw_c[key])} |")
        lines.append("")

    out_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return out_path


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--set", choices=["regression", "adversarial"], required=True)
    args = parser.parse_args()

    questions = load_questions(args.set)
    print(f"[ok] loaded {len(questions)} question(s) for the {args.set} set")

    print("[ok] computing rewritten queries...")
    rewritten_questions = build_rewritten_questions(questions)

    print("[ok] running raw queries through hit_rate_and_mrr()...")
    raw_metrics = hit_rate_and_mrr(questions, method="hybrid", rrf_k=None)

    print("[ok] running rewritten queries through hit_rate_and_mrr()...")
    rw_metrics = hit_rate_and_mrr(rewritten_questions, method="hybrid", rrf_k=None)

    out_path = write_comparison_report(args.set, raw_metrics, rw_metrics, len(questions))
    print(f"\n[ok] wrote {out_path.relative_to(PROJECT_ROOT)}")

    ra, rw = raw_metrics["aggregate"], rw_metrics["aggregate"]
    print(f"\nAggregate Hit Rate: raw={ra['hit_rate']:.4f} rewritten={rw['hit_rate']:.4f} "
          f"delta={fmt_delta(ra['hit_rate'], rw['hit_rate'])}")
    print(f"Aggregate MRR:      raw={ra['mrr']:.4f} rewritten={rw['mrr']:.4f} "
          f"delta={fmt_delta(ra['mrr'], rw['mrr'])}")


if __name__ == "__main__":
    main()
