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
from search import HYBRID_CANDIDATE_POOL, _detect_countries, search  # noqa: E402 — needs sys.path set first

PROJECT_ROOT = Path(__file__).resolve().parents[2]
EVAL_DIR = PROJECT_ROOT / "data" / "eval"
CHUNKS_DIR = PROJECT_ROOT / "data" / "chunks"
GROUND_TRUTH_PATH = EVAL_DIR / "ground_truth.json"
FILTERED_GROUND_TRUTH_PATH = EVAL_DIR / "ground_truth_filtered.json"
REPORT_PATH = EVAL_DIR / "evaluation-report.md"
RERANK_REPORT_PATH = EVAL_DIR / "reranking-ablation-report.md"
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


def country_metadata_coverage() -> tuple[int, int]:
    """Fraction of indexed chunks (data/chunks/*/*.json, the same source
    embed.py builds the index from) whose `countries` field is non-empty --
    the real regression risk flagged for the P2 boost: `_boost_by_country`
    is a total reorder, not a weighted one, so a relevant chunk missing
    `countries` metadata gets demoted below every tagged chunk and could
    fall out of top_k entirely. Reported regardless of the ablation's
    outcome, per the re-ranking ablation design (2026-07-25)."""
    total = 0
    with_countries = 0
    for chunk_path in CHUNKS_DIR.glob("*/*.json"):
        with open(chunk_path, encoding="utf-8") as f:
            record = json.load(f)
        total += 1
        if record["document_metadata"]["declared"].get("countries"):
            with_countries += 1
    return with_countries, total


def run_reranking_ablation(questions: list[dict], rrf_k: int | None) -> dict:
    """Three-arm ablation of the P2 country-metadata re-rank
    (`_boost_by_country` in search.py), added 2026-07-25 to isolate the
    re-rank's own effect from the candidate-pool-depth expansion it rides
    on top of:

      (a) baseline    — pool_k=top_k (unexpanded), boost_country=False.
      (b) pool-only   — expanded (HYBRID_CANDIDATE_POOL-based) pool_k,
                         boost_country=False. Isolates pool depth alone.
      (c) current     — expanded pool_k, boost_country=True. Today's
                         actual shipped behavior, unchanged.

    (a) is obtained directly (search()'s own pool_k collapses to top_k
    whenever boost_country=False, since detected_countries is then always
    empty). (b) is obtained by calling search() with top_k=
    HYBRID_CANDIDATE_POOL and boost_country=False, then truncating to
    TOP_K ourselves -- this forces the same expanded RRF-combine depth the
    current code always uses once a country is detected, with the boost
    itself still definitionally off. (b)'s uncut pool doubles as the exact
    candidate set `_boost_by_country` would reorder for arm (c), so it's
    reused directly to define the "firing subset" below rather than
    recomputed.

    "Firing subset": questions where _detect_countries(query) is
    non-empty AND at least one chunk in the (b)-arm candidate pool has
    `countries` metadata overlapping the detected set -- i.e. neither of
    `_boost_by_country`'s two no-op branches trigger. Firing-subset
    numbers are the primary signal; full-set numbers are diluted by
    questions where the boost can't possibly do anything.
    """
    per_question = []
    for q in questions:
        query = q["question"]
        correct_id = q["correct_chunk_id"]
        detected = _detect_countries(query)

        pooled = search(
            query, top_k=HYBRID_CANDIDATE_POOL, method="hybrid",
            rrf_k=rrf_k, boost_country=False,
        )
        results_b = pooled[:TOP_K]
        results_a = search(
            query, top_k=TOP_K, method="hybrid", rrf_k=rrf_k, boost_country=False,
        )
        results_c = search(
            query, top_k=TOP_K, method="hybrid", rrf_k=rrf_k, boost_country=True,
        )

        fires = bool(detected) and any(
            detected & set(c.get("countries", [])) for c in pooled
        )

        per_question.append({
            "question": query,
            "category": q.get("category", "general"),
            "correct_id": correct_id,
            "fires": fires,
            "ids_a": [r["chunk_id"] for r in results_a],
            "ids_b": [r["chunk_id"] for r in results_b],
            "ids_c": [r["chunk_id"] for r in results_c],
        })

    # Bit-identical assertion on the non-firing subset -- if the boost is
    # definitionally a no-op there (nothing detected, or nothing in the
    # pool matches), arms (b) and (c) MUST return exactly the same list.
    # A mismatch here is a bug in the boost_country guard itself, not a
    # research finding, and must be fixed before anything else is reported.
    mismatches = [
        pq for pq in per_question if not pq["fires"] and pq["ids_b"] != pq["ids_c"]
    ]
    if mismatches:
        raise AssertionError(
            f"{len(mismatches)} non-firing question(s) have arm (b) != arm (c) "
            f"results -- this must be a bug in the boost_country guard, not a "
            f"reportable finding. First mismatch: {mismatches[0]['question']!r} "
            f"ids_b={mismatches[0]['ids_b']!r} ids_c={mismatches[0]['ids_c']!r}"
        )

    def _hit_and_rr(ids: list[str], correct_id: str) -> tuple[int, float]:
        if correct_id in ids:
            rank = ids.index(correct_id) + 1
            return 1, 1.0 / rank
        return 0, 0.0

    def _arm_metrics(subset: list[dict], key: str) -> dict:
        hits, rrs = [], []
        for pq in subset:
            hit, rr = _hit_and_rr(pq[key], pq["correct_id"])
            hits.append(hit)
            rrs.append(rr)
        n = len(subset)
        return {
            "hit_rate": sum(hits) / n if n else 0.0,
            "mrr": sum(rrs) / n if n else 0.0,
            "n": n,
        }

    full = per_question
    firing = [pq for pq in per_question if pq["fires"]]

    arms = {"a_baseline": "ids_a", "b_pool_only": "ids_b", "c_current": "ids_c"}
    metrics_full = {name: _arm_metrics(full, key) for name, key in arms.items()}
    metrics_firing = {name: _arm_metrics(firing, key) for name, key in arms.items()}

    wins = losses = ties = 0
    for pq in firing:
        _, rr_b = _hit_and_rr(pq["ids_b"], pq["correct_id"])
        _, rr_c = _hit_and_rr(pq["ids_c"], pq["correct_id"])
        if rr_c > rr_b:
            wins += 1
        elif rr_c < rr_b:
            losses += 1
        else:
            ties += 1

    return {
        "metrics_full": metrics_full,
        "metrics_firing": metrics_firing,
        "n_full": len(full),
        "n_firing": len(firing),
        "win_loss_tie_c_vs_b": {"wins": wins, "losses": losses, "ties": ties},
        "per_question_firing": firing,
    }


def write_reranking_ablation_report(
    ablation: dict, coverage: tuple[int, int], ground_truth_path: Path,
    rrf_k_used: int,
) -> None:
    with_countries, total_chunks = coverage
    coverage_pct = (with_countries / total_chunks) if total_chunks else 0.0

    def _row(label: str, m: dict) -> str:
        return f"| {label} | {m['hit_rate']:.3f} | {m['mrr']:.3f} | {m['n']} |"

    wlt = ablation["win_loss_tie_c_vs_b"]
    lines = [
        "# Document Re-Ranking Ablation Report\n",
        f"Generated by evaluate.py's `run_reranking_ablation` against "
        f"{ablation['n_full']} ground-truth question(s) "
        f"({ground_truth_path.relative_to(PROJECT_ROOT)}). method=hybrid, "
        f"rrf_k={rrf_k_used} (recorded default) for all three arms, "
        f"top_k={TOP_K}. Evaluates the existing `_boost_by_country` "
        f"country-metadata re-rank in `src/retrieval/search.py` as the "
        f"rubric's document re-ranking best-practice point.\n",
        f"**Metadata coverage check:** {with_countries}/{total_chunks} "
        f"({coverage_pct:.1%}) indexed chunks carry a non-empty `countries` "
        f"field. This is the real regression risk for a re-rank that is a "
        f"total reorder, not a weighted one — a relevant chunk missing "
        f"`countries` would be demoted below every tagged chunk and could "
        f"fall out of top_k. At this coverage level that risk is "
        + ("negligible (every chunk carries the field).\n" if with_countries == total_chunks
           else "real — not every chunk carries the field.\n"),
        "**Provenance / circularity check:** the ground-truth set "
        "(`ground_truth_filtered.json`, mechanically filtered from a full "
        "re-run of `ground_truth.py`) was generated and manually "
        "circularity-reviewed entirely on 2026-07-22, one day *before* the "
        "P2 country-metadata boost was added to `search.py` "
        "(commit `756b28e`, 2026-07-23). `ground_truth.py` also never calls "
        "`search()` itself — questions are generated straight from sampled "
        "chunk text. So this ground truth was not created with knowledge "
        "of the boost's existence; no circularity risk from this ablation "
        "against this specific ground-truth set.\n",
        "**Bit-identical assertion:** arms (b) pool-only and (c) current "
        "were asserted programmatically identical on every non-firing "
        "question (the boost is definitionally a no-op there) before this "
        "report was written — passed, no mismatches.\n",
        "## Full set (diluted — most questions never trigger the boost at all)\n",
        "| Arm | Hit Rate | MRR | n |",
        "|---|---|---|---|",
        _row("(a) baseline (unexpanded pool, no boost)", ablation["metrics_full"]["a_baseline"]),
        _row("(b) pool-only (expanded pool, no boost)", ablation["metrics_full"]["b_pool_only"]),
        _row("(c) current system (expanded pool + boost)", ablation["metrics_full"]["c_current"]),
        "\n## Firing subset (primary signal — boost demonstrably has candidates to act on)\n",
        f"n={ablation['n_firing']} of {ablation['n_full']} full-set questions.\n",
        "| Arm | Hit Rate | MRR | n |",
        "|---|---|---|---|",
        _row("(a) baseline (unexpanded pool, no boost)", ablation["metrics_firing"]["a_baseline"]),
        _row("(b) pool-only (expanded pool, no boost)", ablation["metrics_firing"]["b_pool_only"]),
        _row("(c) current system (expanded pool + boost)", ablation["metrics_firing"]["c_current"]),
        "\n### Per-question win/loss/tie, arm (c) vs arm (b), firing subset only\n",
        f"Given the firing subset's small n, this is reported alongside the "
        f"aggregate MRR/Hit Rate delta above rather than relying on it "
        f"alone: **{wlt['wins']} win(s), {wlt['losses']} loss(es), "
        f"{wlt['ties']} tie(s)** for arm (c) vs arm (b) "
        f"(reciprocal rank of the gold chunk; a win means the boost moved "
        f"the gold chunk to a strictly better rank than pool depth alone "
        f"would have).\n",
    ]

    EVAL_DIR.mkdir(parents=True, exist_ok=True)
    with open(RERANK_REPORT_PATH, "w", encoding="utf-8") as f:
        f.write("\n".join(lines) + "\n")
    print(f"\n[ok] wrote {RERANK_REPORT_PATH.relative_to(PROJECT_ROOT)}")


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


def _recorded_default_rrf_k_for_report() -> int:
    """Reads data/eval/default_method.json directly (rather than importing
    search.py's private cached resolver) purely so the ablation report can
    print the actual k value used -- search() itself still resolves rrf_k
    internally when passed None, this is only for the report's own text."""
    with open(DEFAULT_METHOD_PATH, encoding="utf-8") as f:
        config = json.load(f)
    return config["rrf_k"]


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--set-default", choices=["text", "vector", "hybrid"])
    parser.add_argument("--rrf-k", type=int)
    parser.add_argument(
        "--rerank-ablation", action="store_true",
        help="Run the three-arm (baseline/pool-only/current) ablation of "
             "search.py's country-metadata re-rank instead of the method "
             "comparison.",
    )
    args = parser.parse_args()

    if args.set_default:
        set_default_method(args.set_default, args.rrf_k)
        return

    questions, ground_truth_path = load_ground_truth()

    if args.rerank_ablation:
        rrf_k_used = _recorded_default_rrf_k_for_report()
        coverage = country_metadata_coverage()
        ablation = run_reranking_ablation(questions, rrf_k=None)
        write_reranking_ablation_report(ablation, coverage, ground_truth_path, rrf_k_used)
        return

    results = run_all_methods(questions)
    write_report(results, len(questions), ground_truth_path)


if __name__ == "__main__":
    main()
