"""
evaluate_generation.py -- runs the per-claim judge over
data/eval/generation_results.jsonl (writing data/eval/judgments.jsonl,
resumable, same discipline as run_answers.py), then aggregates verdicts
into claim-level citation precision (aggregate AND per-category), reports
invalid_markers/unsupported_paragraphs counts, reviews the refusal slice,
and writes stratified human-review sample files.

Per ADR-0011: citation precision's unit is CLAIMS, not raw citation
markers -- a claim carrying [4][7] is one claim, judged once, not two.

Licensing note (decided before the first push, see .gitignore): judgments
carry real cited chunk excerpts and are NOT committed --
data/eval/judgments.jsonl and data/eval/generation_results.jsonl are
gitignored. Only slim, excerpt-free CSVs (judgment_id/question_id/
category/verdict/reason/human_verdict) and this script's markdown report
are committed.

Usage:
    uv run python src/evaluation/evaluate_generation.py [--limit N] [--resume]
    uv run python src/evaluation/evaluate_generation.py --score-review
"""

import argparse
import csv
import json
import random
import sys
from collections import Counter
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(PROJECT_ROOT / "src" / "evaluation"))
from judge import claims_with_chunk_text, judge, get_judge_model  # noqa: E402

EVAL_DIR = PROJECT_ROOT / "data" / "eval"
RESULTS_PATH = EVAL_DIR / "generation_results.jsonl"
JUDGMENTS_PATH = EVAL_DIR / "judgments.jsonl"
CALIBRATION_SAMPLE_PATH = EVAL_DIR / "judge_calibration_sample.csv"
CALIBRATION_SAMPLE_FULL_PATH = EVAL_DIR / "judge_calibration_sample_full.csv"
DEPLOYMENT_SAMPLE_PATH = EVAL_DIR / "deployment_review_sample.csv"
DEPLOYMENT_SAMPLE_FULL_PATH = EVAL_DIR / "deployment_review_sample_full.csv"
REPORT_PATH = EVAL_DIR / "generation-evaluation-report.md"

SEED = 42
CALIBRATION_TARGET_TOTAL = 65  # within the 50-80 range per Decision 3
DEPLOYMENT_PER_CATEGORY = 15

VERDICTS = ("supported", "partial", "unsupported")

# Simple keyword heuristic for "did the system decline" -- a first pass,
# not the final word; every refusal-slice answer is also read directly
# (see reports.md) since this is a small (~9 question) slice and a
# heuristic alone risks the exact "over-claiming vs correctly declining"
# distinction this slice exists to catch.
DECLINE_PHRASES = [
    "do not contain", "does not contain", "do not provide", "does not provide",
    "no information", "not enough information", "insufficient information",
    "not covered", "does not cover", "no relevant", "not addressed",
    "cannot answer", "can't answer", "unable to answer", "not answer this question",
    "no evidence", "not available in", "outside the scope", "outside the corpus",
]


# --- Step 1: run the judge over every claim in generation_results.jsonl ---

def load_results() -> list[dict]:
    if not RESULTS_PATH.exists():
        print(f"{RESULTS_PATH.relative_to(PROJECT_ROOT)} doesn't exist -- run "
              f"run_answers.py first.", file=sys.stderr)
        sys.exit(1)
    records = []
    with open(RESULTS_PATH, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                records.append(json.loads(line))
    return records


def load_done_judgment_ids() -> set[str]:
    if not JUDGMENTS_PATH.exists():
        return set()
    done = set()
    with open(JUDGMENTS_PATH, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                done.add(json.loads(line)["judgment_id"])
    return done


def build_pending_judgments(records: list[dict], done_ids: set[str]) -> list[dict]:
    """Extracts every claim from every result record (deterministic given
    unchanged generation_results.jsonl -- what makes judgment_id stable
    across runs) and returns the ones not yet judged."""
    pending = []
    for record in records:
        claims = claims_with_chunk_text(
            record["answer_markdown"], record["citations"], record["retrieved_chunks"]
        )
        for idx, claim in enumerate(claims):
            judgment_id = f"{record['question_id']}::claim{idx:03d}"
            if judgment_id in done_ids:
                continue
            pending.append({
                "judgment_id": judgment_id,
                "question_id": record["question_id"],
                "category": record["category"],
                "claim_text": claim["claim_text"],
                "markers": claim["markers"],
                "cited_chunk_texts": claim["cited_chunk_texts"],
            })
    return pending


def run_judging(limit: int | None, resume: bool) -> None:
    records = load_results()
    done_ids = load_done_judgment_ids() if resume else set()
    pending = build_pending_judgments(records, done_ids)
    if limit is not None:
        pending = pending[:limit]

    print(f"[ok] {len(pending)} claim-judgment(s) to run this invocation "
          f"({len(done_ids)} already done).")
    if not pending:
        return

    info = get_judge_model()
    print(f"[judge model] {info['model']} (fallback used: {info['used_fallback']})")

    total_calls = 0
    with open(JUDGMENTS_PATH, "a", encoding="utf-8") as f:
        for i, item in enumerate(pending, start=1):
            try:
                verdict = judge(item["claim_text"], item["cited_chunk_texts"])
            except Exception as e:  # noqa: BLE001 -- one bad claim shouldn't kill the whole run
                print(f"[FAIL] {item['judgment_id']} -- {e}", file=sys.stderr)
                continue
            record = {**item, **verdict}
            f.write(json.dumps(record, ensure_ascii=False) + "\n")
            f.flush()
            total_calls += 1
            if i % 10 == 0 or i == len(pending):
                print(f"[{i}/{len(pending)}] judged")

    print(f"[ok] {total_calls} judgment(s) written to {JUDGMENTS_PATH.relative_to(PROJECT_ROOT)}")


def load_judgments() -> list[dict]:
    if not JUDGMENTS_PATH.exists():
        return []
    judgments = []
    with open(JUDGMENTS_PATH, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                judgments.append(json.loads(line))
    return judgments


# --- Step 2: aggregation ---

def citation_precision(counts: Counter) -> float | None:
    denom = counts["supported"] + counts["partial"] + counts["unsupported"]
    if denom == 0:
        return None
    return counts["supported"] / denom


def aggregate_by_category(judgments: list[dict]) -> dict:
    by_category: dict[str, Counter] = {}
    overall = Counter()
    for j in judgments:
        by_category.setdefault(j["category"], Counter())[j["verdict"]] += 1
        overall[j["verdict"]] += 1
    return {"overall": overall, "by_category": by_category}


def aggregate_mechanical_counts(records: list[dict]) -> dict:
    """invalid_markers / unsupported_paragraphs -- already computed for
    free by citations.py at generation time, aggregated here (overall and
    per-category) rather than ignored."""
    overall = {"invalid_markers": 0, "unsupported_paragraphs": 0}
    by_category: dict[str, dict] = {}
    for r in records:
        cat = r["category"]
        by_category.setdefault(cat, {"invalid_markers": 0, "unsupported_paragraphs": 0})
        n_invalid = len(r["invalid_markers"])
        n_unsupported = len(r["unsupported_paragraphs"])
        overall["invalid_markers"] += n_invalid
        overall["unsupported_paragraphs"] += n_unsupported
        by_category[cat]["invalid_markers"] += n_invalid
        by_category[cat]["unsupported_paragraphs"] += n_unsupported
    return {"overall": overall, "by_category": by_category}


def review_refusal_slice(records: list[dict]) -> list[dict]:
    """For every refusal-slice question, records a heuristic decline
    check (keyword scan) plus the raw answer -- this slice is small
    enough (~9 questions) that reports.md also reads each one directly
    rather than trusting the heuristic alone."""
    results = []
    for r in records:
        if r["category"] != "refusal":
            continue
        lowered = r["answer_markdown"].lower()
        heuristic_declined = any(phrase in lowered for phrase in DECLINE_PHRASES)
        results.append({
            "question_id": r["question_id"],
            "question": r["question"],
            "rationale": r.get("rationale"),
            "n_citations": len(r["citations"]),
            "heuristic_declined": heuristic_declined,
            "answer_markdown": r["answer_markdown"],
        })
    return results


# --- Step 3: human-review sample files ---

def write_calibration_sample(judgments: list[dict]) -> None:
    """Stratified by VERDICT (per Decision 3): oversample every
    unsupported/partial verdict, fill the remainder with a random sample
    of supported verdicts, target ~50-80 total."""
    rng = random.Random(SEED)
    unsupported = [j for j in judgments if j["verdict"] == "unsupported"]
    partial = [j for j in judgments if j["verdict"] == "partial"]
    supported = [j for j in judgments if j["verdict"] == "supported"]

    sample = list(unsupported) + list(partial)
    remaining = max(0, CALIBRATION_TARGET_TOTAL - len(sample))
    sample += rng.sample(supported, min(remaining, len(supported)))
    rng.shuffle(sample)

    _write_review_csvs(sample, CALIBRATION_SAMPLE_PATH, CALIBRATION_SAMPLE_FULL_PATH)
    print(f"[ok] wrote {len(sample)}-row judge calibration sample "
          f"({len(unsupported)} unsupported, {len(partial)} partial, "
          f"{len(sample) - len(unsupported) - len(partial)} supported)")


def write_deployment_sample(judgments: list[dict]) -> None:
    """Stratified by CATEGORY (per Decision 3): a fixed count per stratum
    (~15 each), not a global percentage -- for the separate deployment
    citation-precision review."""
    rng = random.Random(SEED)
    by_category: dict[str, list[dict]] = {}
    for j in judgments:
        by_category.setdefault(j["category"], []).append(j)

    sample = []
    for category, items in by_category.items():
        n = min(DEPLOYMENT_PER_CATEGORY, len(items))
        sample.extend(rng.sample(items, n))

    _write_review_csvs(sample, DEPLOYMENT_SAMPLE_PATH, DEPLOYMENT_SAMPLE_FULL_PATH)
    counts = {cat: min(DEPLOYMENT_PER_CATEGORY, len(items)) for cat, items in by_category.items()}
    print(f"[ok] wrote {len(sample)}-row deployment review sample: {counts}")


def _write_review_csvs(sample: list[dict], slim_path: Path, full_path: Path) -> None:
    slim_fields = ["judgment_id", "question_id", "category", "verdict", "reason", "human_verdict"]
    with open(slim_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=slim_fields)
        writer.writeheader()
        for j in sample:
            writer.writerow({**{k: j.get(k, "") for k in slim_fields[:-1]}, "human_verdict": ""})

    full_fields = ["judgment_id", "question_id", "category", "claim_text",
                   "cited_chunk_texts", "verdict", "reason", "human_verdict"]
    with open(full_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=full_fields)
        writer.writeheader()
        for j in sample:
            row = {k: j.get(k, "") for k in full_fields[:-1]}
            row["cited_chunk_texts"] = json.dumps(j.get("cited_chunk_texts", []), ensure_ascii=False)
            row["human_verdict"] = ""
            writer.writerow(row)


# --- --score-review: confusion matrix, raw agreement, kappa (or ADR-0011 fallback) ---

def cohens_kappa(matrix: dict) -> float | None:
    n = sum(matrix.values())
    if n == 0:
        return None
    po = sum(matrix[(v, v)] for v in VERDICTS) / n
    row_totals = {v: sum(matrix[(v, h)] for h in VERDICTS) for v in VERDICTS}
    col_totals = {h: sum(matrix[(v, h)] for v in VERDICTS) for h in VERDICTS}
    pe = sum((row_totals[v] / n) * (col_totals[v] / n) for v in VERDICTS)
    if pe == 1:
        return None
    return (po - pe) / (1 - pe)


def score_review(slim_path: Path) -> dict:
    if not slim_path.exists():
        print(f"{slim_path.relative_to(PROJECT_ROOT)} doesn't exist -- run without "
              f"--score-review first to generate it.", file=sys.stderr)
        sys.exit(1)

    with open(slim_path, encoding="utf-8") as f:
        rows = list(csv.DictReader(f))

    matrix = {(v, h): 0 for v in VERDICTS for h in VERDICTS}
    n_scored = 0
    n_missing = 0
    for row in rows:
        human = row.get("human_verdict", "").strip().lower()
        judge_v = row["verdict"].strip().lower()
        if human not in VERDICTS:
            n_missing += 1
            continue
        matrix[(judge_v, human)] += 1
        n_scored += 1

    n_agree = sum(matrix[(v, v)] for v in VERDICTS)
    n_disagree = n_scored - n_agree
    raw_agreement = n_agree / n_scored if n_scored else None
    kappa = cohens_kappa(matrix)

    # ADR-0011 fallback: if disagreements are too few (<10) for kappa to be
    # informative, or kappa is undefined despite high raw agreement, use
    # raw-agreement-plus-error-direction instead of trusting kappa alone.
    kappa_uninformative = n_disagree < 10
    supported_but_human_unsupported = matrix[("supported", "unsupported")]
    fallback_go = (raw_agreement is not None and raw_agreement >= 0.90
                   and supported_but_human_unsupported == 0)

    return {
        "n_scored": n_scored,
        "n_missing_human_verdict": n_missing,
        "n_disagree": n_disagree,
        "raw_agreement": raw_agreement,
        "kappa": kappa,
        "kappa_uninformative": kappa_uninformative,
        "confusion_matrix": {f"judge={v}/human={h}": matrix[(v, h)] for v in VERDICTS for h in VERDICTS},
        "costliest_error_count_judge_supported_human_unsupported": supported_but_human_unsupported,
        "fallback_go_no_go": fallback_go,
    }


# --- Report ---

def write_report(judgment_agg: dict, mechanical_agg: dict, refusal_review: list[dict],
                  review_score: dict | None, judge_info: dict) -> None:
    lines = ["# Generation-Phase Evaluation Report\n"]
    lines.append(f"Judge model used: **{judge_info['model']}** "
                 f"(fallback from gpt-5.4 used: {judge_info['used_fallback']})\n")

    lines.append("## Claim-level citation precision\n")
    lines.append(
        "Unit is **claims** (a sentence carrying >=1 valid [n] marker; a "
        "multi-marker claim like `[4][7]` is judged once as one claim, not "
        "twice), not raw citation markers -- per ADR-0011.\n"
    )
    overall = judgment_agg["overall"]
    prec = citation_precision(overall)
    lines.append(f"**Aggregate**: supported={overall['supported']}, "
                 f"partial={overall['partial']}, unsupported={overall['unsupported']}, "
                 f"citation_precision={prec:.3f}" if prec is not None else "**Aggregate**: no claims judged.")
    lines.append("\n### Per category\n")
    for cat, counts in sorted(judgment_agg["by_category"].items()):
        p = citation_precision(counts)
        p_str = f"{p:.3f}" if p is not None else "n/a"
        lines.append(f"- **{cat}**: supported={counts['supported']}, partial={counts['partial']}, "
                     f"unsupported={counts['unsupported']}, citation_precision={p_str}")

    lines.append("\n## Mechanical counts (citations.py, free)\n")
    m = mechanical_agg["overall"]
    lines.append(f"invalid_markers={m['invalid_markers']}, unsupported_paragraphs={m['unsupported_paragraphs']}\n")
    for cat, counts in sorted(mechanical_agg["by_category"].items()):
        lines.append(f"- **{cat}**: invalid_markers={counts['invalid_markers']}, "
                     f"unsupported_paragraphs={counts['unsupported_paragraphs']}")

    lines.append("\n## Refusal slice review\n")
    for r in refusal_review:
        lines.append(f"- `{r['question_id']}` (heuristic_declined={r['heuristic_declined']}, "
                     f"n_citations={r['n_citations']}): {r['question']}")

    if review_score is not None:
        lines.append("\n## Human-review scoring (--score-review)\n")
        lines.append(f"n_scored={review_score['n_scored']}, "
                     f"n_missing_human_verdict={review_score['n_missing_human_verdict']}, "
                     f"n_disagree={review_score['n_disagree']}")
        ra = review_score["raw_agreement"]
        lines.append(f"raw_agreement={ra:.3f}" if ra is not None else "raw_agreement=n/a")
        if review_score["kappa_uninformative"]:
            lines.append(
                "Cohen's kappa: **uninformative under this sample's low disagreement "
                "prevalence** (fewer than ~10 disagreements) -- per ADR-0011, falling back "
                "to raw-agreement-plus-error-direction go/no-go instead: "
                f"raw_agreement>=0.90 AND zero judge=supported/human=unsupported cases -> "
                f"**{'GO' if review_score['fallback_go_no_go'] else 'NO-GO'}** "
                f"(costliest-error count: {review_score['costliest_error_count_judge_supported_human_unsupported']})"
            )
        else:
            kappa = review_score["kappa"]
            lines.append(f"Cohen's kappa={kappa:.3f}" if kappa is not None else "Cohen's kappa=undefined")
        lines.append("\nConfusion matrix (judge x human):")
        for k, v in review_score["confusion_matrix"].items():
            lines.append(f"- {k}: {v}")

    with open(REPORT_PATH, "w", encoding="utf-8") as f:
        f.write("\n".join(lines) + "\n")
    print(f"[ok] wrote {REPORT_PATH.relative_to(PROJECT_ROOT)}")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--limit", type=int, default=None)
    parser.add_argument("--resume", action="store_true")
    parser.add_argument("--score-review", action="store_true",
                        help="Join the calibration sample's human_verdict column back on "
                             "judgment_id and compute the confusion matrix/kappa/fallback.")
    args = parser.parse_args()

    if args.score_review:
        judge_info = get_judge_model()
        records = load_results()
        judgments = load_judgments()
        judgment_agg = aggregate_by_category(judgments)
        mechanical_agg = aggregate_mechanical_counts(records)
        refusal_review = review_refusal_slice(records)
        review_score = score_review(CALIBRATION_SAMPLE_PATH)
        write_report(judgment_agg, mechanical_agg, refusal_review, review_score, judge_info)
        return

    run_judging(limit=args.limit, resume=args.resume)

    records = load_results()
    judgments = load_judgments()
    if not judgments:
        print("[ok] no judgments yet -- nothing to aggregate.")
        return

    judgment_agg = aggregate_by_category(judgments)
    mechanical_agg = aggregate_mechanical_counts(records)
    refusal_review = review_refusal_slice(records)
    write_calibration_sample(judgments)
    write_deployment_sample(judgments)
    write_report(judgment_agg, mechanical_agg, refusal_review, None, get_judge_model())


if __name__ == "__main__":
    main()
