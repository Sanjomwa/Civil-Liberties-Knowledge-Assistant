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
import random
import re
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

# Added 2026-07-22, Opus + Fable phase-boundary review of the whole
# retrieval phase (see decisionlog.md). Both advisors converged on: the
# aggregate numbers alone don't say enough. Three additions, each testing
# a specific open question rather than being metrics for their own sake:
#
# 1. Neighbor-aware "relaxed" Hit Rate/MRR -- tests whether the strict
#    single-correct-chunk-id scoring is undercounting genuine hits because
#    chunking is 50% overlapping (chunk_size=1500/chunk_step=750), so a
#    retrieved same-doc neighbor chunk often covers the same passage as
#    the labeled "correct" one but currently scores as a full miss. Opus's
#    own estimate was this explains "a third to half" of misses, not
#    most -- this measures it directly instead of arguing about it.
# 2. Hit Rate @3/@5 -- the generation phase will realistically consume
#    3-5 chunks per answer, not the top_k=10 this evaluation uses. A gold
#    chunk at rank 8 counts as a "hit" here but would be a miss in the
#    system users actually see (Fable's point).
# 3. Source-diversity@10 (avg. distinct orgs / distinct docs in the top-10,
#    independent of whether the labeled chunk was hit) -- this project's
#    own stated top safety priority is flagging thin/contradictory
#    evidence, which needs retrieval to surface corroborating chunks from
#    multiple sources, not just the one gold chunk. Single-gold Hit Rate
#    is silent on that; this is a first, purely descriptive signal.
#
# Plus 95% bootstrap confidence intervals on the aggregate Hit Rate/MRR
# (percentile method, 2000 resamples) -- per-slice n's are small enough
# (ooni_methodology=11 in the last real run) that slice deltas aren't
# statistically powered; CIs make that visible in the report itself
# instead of requiring the reader to already know it.

BOOTSTRAP_RESAMPLES = 2000
BOOTSTRAP_SEED = 42
_CHUNK_ID_RE = re.compile(r"^(?P<prefix>.+-chunk-)(?P<idx>\d+)$")


def _neighbor_chunk_ids(chunk_id: str) -> list[str]:
    """Same-document chunk_id(s) immediately before/after this one, per
    the {doc_id}-chunk-{0000} naming chunk.py writes -- computed by string
    manipulation only (no file I/O), since the ±1 chunk_index is exactly
    what 50%-overlap chunking (chunk_step=750 of chunk_size=1500) means
    covers a substantially overlapping span of the source text."""
    m = _CHUNK_ID_RE.match(chunk_id)
    if not m:
        return []
    prefix, idx_str = m.group("prefix"), m.group("idx")
    width = len(idx_str)
    idx = int(idx_str)
    neighbors = []
    if idx > 0:
        neighbors.append(f"{prefix}{idx - 1:0{width}d}")
    neighbors.append(f"{prefix}{idx + 1:0{width}d}")
    return neighbors


def _bootstrap_ci(values: list[float], n_resamples: int = BOOTSTRAP_RESAMPLES) -> tuple[float, float]:
    """95% CI on the mean of `values` via percentile bootstrap. Returns
    (0.0, 0.0) for an empty input rather than raising, since some
    per-category slices can legitimately have n=0 (e.g. ooni_methodology
    before the classify_category fix)."""
    if not values:
        return (0.0, 0.0)
    rng = random.Random(BOOTSTRAP_SEED)
    n = len(values)
    means = []
    for _ in range(n_resamples):
        sample = [values[rng.randrange(n)] for _ in range(n)]
        means.append(sum(sample) / n)
    means.sort()
    lo = means[int(0.025 * n_resamples)]
    hi = means[int(0.975 * n_resamples) - 1]
    return (lo, hi)


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
    metrics for this one method (and, for hybrid, this one rrf_k): strict
    Hit Rate/MRR (+ 95% CI), neighbor-aware relaxed Hit Rate/MRR, Hit Rate
    @3/@5, and source-diversity@10 (avg. distinct orgs/docs in top-10,
    independent of correctness). See the 2026-07-22 module-level comment
    for why each of these was added."""
    per_category = {c: {
        "hits": [], "rr": [], "relaxed_hits": [], "relaxed_rr": [],
        "hits_at_3": [], "hits_at_5": [], "distinct_orgs": [], "distinct_docs": [],
    } for c in CATEGORIES}

    for q in questions:
        kwargs = {"top_k": TOP_K, "method": method}
        if method == "hybrid":
            kwargs["rrf_k"] = rrf_k
        results = search(q["question"], **kwargs)
        result_ids = [r["chunk_id"] for r in results]
        category = q.get("category", "general")
        bucket = per_category[category]

        correct_id = q["correct_chunk_id"]
        if correct_id in result_ids:
            rank = result_ids.index(correct_id) + 1
            bucket["hits"].append(1)
            bucket["rr"].append(1.0 / rank)
        else:
            bucket["hits"].append(0)
            bucket["rr"].append(0.0)

        # Relaxed: credit the best rank among the gold chunk and its
        # same-doc ±1 neighbor(s) -- see _neighbor_chunk_ids.
        acceptable_ids = {correct_id, *_neighbor_chunk_ids(correct_id)}
        best_relaxed_rank = None
        for i, rid in enumerate(result_ids, start=1):
            if rid in acceptable_ids:
                best_relaxed_rank = i
                break
        if best_relaxed_rank is not None:
            bucket["relaxed_hits"].append(1)
            bucket["relaxed_rr"].append(1.0 / best_relaxed_rank)
        else:
            bucket["relaxed_hits"].append(0)
            bucket["relaxed_rr"].append(0.0)

        bucket["hits_at_3"].append(1 if correct_id in result_ids[:3] else 0)
        bucket["hits_at_5"].append(1 if correct_id in result_ids[:5] else 0)

        bucket["distinct_orgs"].append(len({r.get("organization") for r in results}))
        bucket["distinct_docs"].append(len({r.get("doc_id") for r in results}))

    def avg(values: list[float]) -> float:
        return sum(values) / len(values) if values else 0.0

    def summarize(bucket: dict) -> dict:
        return {
            "hit_rate": avg(bucket["hits"]),
            "hit_rate_ci95": _bootstrap_ci(bucket["hits"]),
            "mrr": avg(bucket["rr"]),
            "mrr_ci95": _bootstrap_ci(bucket["rr"]),
            "relaxed_hit_rate": avg(bucket["relaxed_hits"]),
            "relaxed_mrr": avg(bucket["relaxed_rr"]),
            "hit_rate_at_3": avg(bucket["hits_at_3"]),
            "hit_rate_at_5": avg(bucket["hits_at_5"]),
            "avg_distinct_orgs": avg(bucket["distinct_orgs"]),
            "avg_distinct_docs": avg(bucket["distinct_docs"]),
            "n": len(bucket["hits"]),
        }

    all_bucket = {
        key: [v for cat in per_category.values() for v in cat[key]]
        for key in next(iter(per_category.values()))
    }

    return {
        "aggregate": summarize(all_bucket),
        "per_category": {cat: summarize(b) for cat, b in per_category.items()},
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


def _row(label: str, m: dict) -> str:
    ci_lo, ci_hi = m["hit_rate_ci95"]
    mrr_lo, mrr_hi = m["mrr_ci95"]
    return (
        f"| {label} | {m['hit_rate']:.3f} | [{ci_lo:.3f}, {ci_hi:.3f}] "
        f"| {m['mrr']:.3f} | [{mrr_lo:.3f}, {mrr_hi:.3f}] "
        f"| {m['relaxed_hit_rate']:.3f} | {m['hit_rate_at_3']:.3f} "
        f"| {m['hit_rate_at_5']:.3f} | {m['n']} |"
    )


def _diversity_row(label: str, m: dict) -> str:
    return f"| {label} | {m['avg_distinct_orgs']:.2f} | {m['avg_distinct_docs']:.2f} | {m['n']} |"


def write_report(results: dict, n_questions: int, ground_truth_path: Path) -> None:
    lines = [
        "# Retrieval Evaluation Report\n",
        f"Generated by evaluate.py against {n_questions} ground-truth question(s) "
        f"({ground_truth_path.relative_to(PROJECT_ROOT)}). top_k={TOP_K}.\n",
        "**No method is auto-selected as a default here — per the 2026-07-22 "
        "design review, that's a human decision informed by the per-slice "
        "results below, not an aggregate-only auto-pick.**\n",
        "**Extended metrics added 2026-07-22 (Opus + Fable phase-boundary "
        "review, see decisionlog.md):** `Relaxed HR` credits a hit if the gold "
        "chunk OR its same-doc ±1 neighbor is retrieved (tests whether strict "
        "single-chunk-id scoring undercounts hits given 50%-overlap chunking). "
        "`HR@3`/`HR@5` reflect the ~3-5 chunks a generation step will realistically "
        "use, not the full top_k=10. 95% CIs are a 2000-resample bootstrap on the "
        "mean — **per-category n's are small (especially ooni_methodology); read "
        "per-slice CIs as a caution against over-reading small deltas, not as a "
        "precise estimate.**\n",
        "## Aggregate\n",
        "| Method | Hit Rate | HR 95% CI | MRR | MRR 95% CI | Relaxed HR | HR@3 | HR@5 | n |",
        "|---|---|---|---|---|---|---|---|---|",
    ]
    for method in ("text", "vector"):
        lines.append(_row(method, results[method]["aggregate"]))
    for k, r in results["hybrid"].items():
        lines.append(_row(f"hybrid (k={k})", r["aggregate"]))

    lines.append("\n### Source diversity @10 (aggregate)\n")
    lines.append(
        "Avg. distinct orgs/docs in the top-10 for EVERY query, independent of "
        "whether the labeled chunk was hit — a first, purely descriptive signal "
        "for whether retrieval can surface corroborating evidence from multiple "
        "sources, which this project's citation/thin-evidence-flagging design "
        "goal actually needs (not measured by single-gold Hit Rate at all).\n"
    )
    lines.append("| Method | Avg. Distinct Orgs | Avg. Distinct Docs | n |")
    lines.append("|---|---|---|---|")
    for method in ("text", "vector"):
        lines.append(_diversity_row(method, results[method]["aggregate"]))
    for k, r in results["hybrid"].items():
        lines.append(_diversity_row(f"hybrid (k={k})", r["aggregate"]))

    lines.append("\n## Per-category slice\n")
    lines.append(
        "Whether the aggregate winner also holds up here — especially on "
        "categories where evidence is hardest to retrieve correctly — matters "
        "more than the aggregate row alone (project_evaluation_plan.md's own "
        "citation-precision priority). **Treat these as hypothesis-generators, "
        "not conclusions** — see the CI caution above.\n"
    )
    for category in CATEGORIES:
        lines.append(f"### {category}\n")
        lines.append("| Method | Hit Rate | HR 95% CI | MRR | MRR 95% CI | Relaxed HR | HR@3 | HR@5 | n |")
        lines.append("|---|---|---|---|---|---|---|---|---|")
        for method in ("text", "vector"):
            lines.append(_row(method, results[method]["per_category"][category]))
        for k, r in results["hybrid"].items():
            lines.append(_row(f"hybrid (k={k})", r["per_category"][category]))
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
