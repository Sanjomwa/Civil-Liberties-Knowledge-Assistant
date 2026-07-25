"""
compare_prompts.py -- Prompt A vs Prompt B comparison harness.

Closes the real rubric gap ADR-0012 found: the LLM-evaluation phase's own
0.879 claim-level citation precision only ever judged ONE generation
approach, but the rubric's 2-point bar requires comparing multiple
approaches and picking a winner. Full design:
docs/evaluation-design.md, Decision 6.

Model held fixed (gpt-5.4-mini, generate.py's own recorded default) and
temperature held fixed (0.2) for both arms -- only the system prompt
differs, so the comparison isolates prompt design, not model or sampling
variance. Retrieval is also held fixed per question: search() is called
ONCE per question and the identical retrieved chunk set is reused for
both prompts on that question, so retrieval noise never confounds the
comparison. Judged with the existing, unmodified judge.py -- ADR-0010/
ADR-0011's protocol is not reopened here.

CRITICAL, not optional (see docs/evaluation-design.md Decision 6):
Prompt B's raw output has a "PHASE 1 -- EVIDENCE" block, with its own
[n] markers, before the "ANSWER" heading. Claim extraction must run on
the ANSWER section only -- strip_to_answer() below -- or EVIDENCE lines
get scored as claims and the whole comparison is invalid.

Question subset: a stratified sample of the same combined question set
run_answers.py already uses (general/multi_country/ooni_methodology from
the 101-question filtered ground truth, plus the synthesis_supplement
and refusal_slice categories), preserving each category's real share of
that 122-question population via a largest-remainder allocation -- not a
flat per-category split, which would badly over- or under-weight the
smallest strata (refusal: 9, ooni_methodology: 11) relative to their real
size.

Writes results incrementally (JSONL, resumable, same discipline as
run_answers.py/evaluate_generation.py) to two files:
  data/eval/prompt_comparison_results.jsonl   -- one row per (question, arm)
  data/eval/prompt_comparison_judgments.jsonl -- one row per (claim, arm)

Usage:
    uv run python src/evaluation/compare_prompts.py [--n 40] [--seed 42] [--resume]
    uv run python src/evaluation/compare_prompts.py --report-only
"""

import argparse
import json
import random
import re
import sys
from collections import Counter, defaultdict
from pathlib import Path

from dotenv import load_dotenv
from openai import OpenAI

PROJECT_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(PROJECT_ROOT / "src"))
sys.path.insert(0, str(PROJECT_ROOT / "src" / "generation"))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from retrieval.search import search  # noqa: E402
from prompts import SYSTEM_PROMPT, SYSTEM_PROMPT_B, build_user_prompt  # noqa: E402
from citations import parse_citations  # noqa: E402
from judge import claims_with_chunk_text, judge, get_judge_model  # noqa: E402
from run_answers import load_question_set  # noqa: E402
from evaluate_generation import citation_precision, DECLINE_PHRASES  # noqa: E402

load_dotenv()

EVAL_DIR = PROJECT_ROOT / "data" / "eval"
RESULTS_PATH = EVAL_DIR / "prompt_comparison_results.jsonl"
JUDGMENTS_PATH = EVAL_DIR / "prompt_comparison_judgments.jsonl"
REPORT_PATH = EVAL_DIR / "prompt-comparison-report.md"

# Matches generate.py's own recorded model/temperature exactly -- the
# comparison is only valid if the ONLY variable that differs between arms
# is the system prompt (see Decision 6's "model held fixed" framing).
LLM_MODEL = "gpt-5.4-mini"
TEMPERATURE = 0.2
TOP_K = 10

DEFAULT_N = 40
DEFAULT_SEED = 42
ARMS = ("A", "B")

# Matches Prompt B's own literal instruction ("write the answer under the
# heading ANSWER") but tolerant of markdown decoration (##, **, trailing
# colon) a model might add despite the instruction -- verified against
# real model output before being trusted (see reports.md).
ANSWER_HEADING_RE = re.compile(r"(?im)^\s*#{0,6}\s*\**\s*ANSWER\s*\**\s*:?\s*$")


def stratified_sample(questions: list[dict], n: int, seed: int) -> tuple[list[dict], dict]:
    """Largest-remainder stratified sample preserving each category's real
    share of `questions` (5 categories: general, multi_country,
    ooni_methodology, synthesis_supplement, refusal) -- not a flat n/5
    split, which would badly misrepresent categories ranging from 9
    (refusal) to 68 (general) questions.

    Returns (sample, allocation) -- allocation is {category: count}, for
    the report to state exactly what was drawn and why.
    """
    by_category: dict[str, list[dict]] = defaultdict(list)
    for q in questions:
        by_category[q["category"]].append(q)

    total = len(questions)
    raw = {cat: n * len(qs) / total for cat, qs in by_category.items()}
    allocation = {cat: int(v) for cat, v in raw.items()}
    remainder = n - sum(allocation.values())
    # Largest-remainder method: give the leftover slots to the categories
    # with the biggest fractional part, so the total is exactly n.
    fractional_order = sorted(raw, key=lambda c: raw[c] - allocation[c], reverse=True)
    for cat in fractional_order[:remainder]:
        allocation[cat] += 1

    rng = random.Random(seed)
    sample = []
    for cat, count in allocation.items():
        pool = by_category[cat]
        sample.extend(rng.sample(pool, min(count, len(pool))))
    rng.shuffle(sample)
    return sample, allocation


def strip_to_answer(raw_text: str) -> str:
    """Prompt B's raw output = PHASE 1 EVIDENCE block + ANSWER heading +
    the actual answer. Returns only what follows the ANSWER heading.
    Raises ValueError if no heading is found -- a silent fallback to the
    full raw text would let EVIDENCE-line markers leak into claim
    extraction, exactly the failure mode this function exists to prevent."""
    match = ANSWER_HEADING_RE.search(raw_text)
    if match is None:
        raise ValueError(
            f"No ANSWER heading found in Prompt B output -- cannot safely "
            f"strip EVIDENCE lines. Raw output:\n{raw_text}"
        )
    return raw_text[match.end():].strip()


def is_abstention(answer_text: str, citations: list[dict]) -> bool:
    """An answer counts as an abstention if and only if it produced zero
    valid citations -- this system's design means a real, substantive
    answer almost always cites something, so this is a clean, mechanical
    signal with no false positives.

    Fixed 2026-07-25, found during this run's own manual spot-check: the
    first version of this function also matched evaluate_generation.py's
    DECLINE_PHRASES list (e.g. "do not provide") anywhere in the answer
    text. That list was built, and explicitly caveated, for whole-answer
    refusal-slice review with a human reading each match alongside it
    (see review_refusal_slice()'s own docstring) -- it is NOT safe as a
    standalone per-answer detector, because a fully substantive, cited,
    multi-paragraph answer can easily contain one bounded local qualifier
    ("...but they do not provide a specific penalty in the text
    provided") about a sub-point without abstaining on the question as a
    whole. The phrase-based version inflated Prompt A's measured
    abstention rate to 0.125 (5/40) purely from this false-positive
    pattern -- all 5 flagged answers were real, complete, cited answers,
    confirmed by reading each one directly. Corrected to zero-citations
    only; see reports.md for the full before/after and the manual
    verification."""
    return not citations


def call_model(client: OpenAI, system_prompt: str, user_prompt: str) -> tuple[str, dict | None]:
    response = client.chat.completions.create(
        model=LLM_MODEL,
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
        temperature=TEMPERATURE,
    )
    raw_text = response.choices[0].message.content.strip()
    usage = None
    if response.usage is not None:
        usage = {
            "prompt_tokens": response.usage.prompt_tokens,
            "completion_tokens": response.usage.completion_tokens,
            "total_tokens": response.usage.total_tokens,
        }
    return raw_text, usage


def run_one_arm(query: str, chunks: list[dict], arm: str, client: OpenAI) -> dict:
    """Runs one arm (A or B) for one question against the SAME retrieved
    chunk set. Returns everything compare_prompts.py's own judging step
    and report need -- shaped like run_answers.py's per-question record,
    plus arm-specific fields (raw_text distinct from answer_text for B)."""
    user_prompt = build_user_prompt(query, chunks)
    system_prompt = SYSTEM_PROMPT if arm == "A" else SYSTEM_PROMPT_B
    raw_text, usage = call_model(client, system_prompt, user_prompt)

    answer_text = strip_to_answer(raw_text) if arm == "B" else raw_text

    parsed = parse_citations(answer_text, chunks)
    chunk_text_map = {c["chunk_id"]: c["text"] for c in chunks}
    claims = claims_with_chunk_text(answer_text, parsed["citations"], chunk_text_map)

    return {
        "raw_text": raw_text,
        "answer_text": answer_text,
        "citations": parsed["citations"],
        "invalid_markers": parsed["invalid_markers"],
        "unsupported_paragraphs": parsed["unsupported_paragraphs"],
        "n_claims": len(claims),
        "claims": claims,
        "abstained": is_abstention(answer_text, parsed["citations"]),
        "usage": usage,
    }


def load_done_result_keys() -> set[str]:
    if not RESULTS_PATH.exists():
        return set()
    done = set()
    with open(RESULTS_PATH, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                row = json.loads(line)
                done.add(f"{row['question_id']}::{row['arm']}")
    return done


def run_generation(sample: list[dict], resume: bool) -> None:
    done_keys = load_done_result_keys() if resume else set()
    client = OpenAI()

    EVAL_DIR.mkdir(parents=True, exist_ok=True)
    total = len(sample) * len(ARMS)
    done_count = 0
    with open(RESULTS_PATH, "a", encoding="utf-8") as f:
        for item in sample:
            chunks = search(item["question"], top_k=TOP_K, method="hybrid")
            for arm in ARMS:
                key = f"{item['question_id']}::{arm}"
                done_count += 1
                if key in done_keys:
                    continue
                try:
                    result = run_one_arm(item["question"], chunks, arm, client)
                except Exception as e:  # noqa: BLE001 -- one bad question/arm shouldn't kill the run
                    print(f"[FAIL] {key} -- {e}", file=sys.stderr)
                    continue
                record = {
                    "question_id": item["question_id"],
                    "arm": arm,
                    "question": item["question"],
                    "category": item["category"],
                    "expected_behavior": item["expected_behavior"],
                    "raw_text": result["raw_text"],
                    "answer_text": result["answer_text"],
                    "citations": result["citations"],
                    "invalid_markers": result["invalid_markers"],
                    "unsupported_paragraphs": result["unsupported_paragraphs"],
                    "n_claims": result["n_claims"],
                    "abstained": result["abstained"],
                    "usage": result["usage"],
                    "retrieved_chunks": {c["chunk_id"]: c["text"] for c in chunks},
                }
                f.write(json.dumps(record, ensure_ascii=False) + "\n")
                f.flush()
                print(f"[{done_count}/{total}] {key} done ({item['category']}, "
                      f"n_claims={result['n_claims']}, abstained={result['abstained']})")

    print(f"[ok] generation done -- {total} (question, arm) result(s) targeted.")


def load_results() -> list[dict]:
    if not RESULTS_PATH.exists():
        return []
    with open(RESULTS_PATH, encoding="utf-8") as f:
        return [json.loads(line) for line in f if line.strip()]


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


def run_judging(resume: bool) -> None:
    records = load_results()
    done_ids = load_done_judgment_ids() if resume else set()

    pending = []
    for record in records:
        claims = claims_with_chunk_text(
            record["answer_text"], record["citations"], record["retrieved_chunks"]
        )
        for idx, claim in enumerate(claims):
            judgment_id = f"{record['question_id']}::{record['arm']}::claim{idx:03d}"
            if judgment_id in done_ids:
                continue
            pending.append({
                "judgment_id": judgment_id,
                "question_id": record["question_id"],
                "arm": record["arm"],
                "category": record["category"],
                "claim_text": claim["claim_text"],
                "markers": claim["markers"],
                "cited_chunk_texts": claim["cited_chunk_texts"],
            })

    print(f"[ok] {len(pending)} claim-judgment(s) to run ({len(done_ids)} already done).")
    if not pending:
        return

    info = get_judge_model()
    print(f"[judge model] {info['model']} (fallback used: {info['used_fallback']})")

    with open(JUDGMENTS_PATH, "a", encoding="utf-8") as f:
        for i, item in enumerate(pending, start=1):
            try:
                verdict = judge(item["claim_text"], item["cited_chunk_texts"])
            except Exception as e:  # noqa: BLE001 -- one bad claim shouldn't kill the run
                print(f"[FAIL] {item['judgment_id']} -- {e}", file=sys.stderr)
                continue
            row = {**item, **verdict}
            f.write(json.dumps(row, ensure_ascii=False) + "\n")
            f.flush()
            if i % 20 == 0 or i == len(pending):
                print(f"[{i}/{len(pending)}] judged")


def load_judgments() -> list[dict]:
    if not JUDGMENTS_PATH.exists():
        return []
    with open(JUDGMENTS_PATH, encoding="utf-8") as f:
        return [json.loads(line) for line in f if line.strip()]


def _mean(values: list[float]) -> float:
    return sum(values) / len(values) if values else 0.0


def compute_arm_stats(arm: str, records: list[dict], judgments: list[dict]) -> dict:
    arm_records = [r for r in records if r["arm"] == arm]
    arm_judgments = [j for j in judgments if j["arm"] == arm]

    verdict_counts = Counter(j["verdict"] for j in arm_judgments)
    precision = citation_precision(verdict_counts)

    claims_per_answer = _mean([r["n_claims"] for r in arm_records])
    # Recomputed fresh from each record's own `citations` list, not the
    # persisted `abstained` field -- see is_abstention()'s docstring for
    # why the original phrase-based version was a false-positive-prone
    # measurement bug, fixed after this run's own results were already
    # written to disk. Recomputing here (rather than re-running
    # generation) costs nothing and uses the correct, already-persisted
    # ground truth (citations).
    abstention_rate = _mean([1.0 if is_abstention(r["answer_text"], r["citations"]) else 0.0
                              for r in arm_records])

    prompt_tokens = [r["usage"]["prompt_tokens"] for r in arm_records if r["usage"]]
    completion_tokens = [r["usage"]["completion_tokens"] for r in arm_records if r["usage"]]

    return {
        "n_answers": len(arm_records),
        "n_claims_judged": sum(verdict_counts.values()),
        "verdict_counts": dict(verdict_counts),
        "citation_precision": precision,
        "claims_per_answer": claims_per_answer,
        "abstention_rate": abstention_rate,
        "mean_prompt_tokens": _mean(prompt_tokens),
        "mean_completion_tokens": _mean(completion_tokens),
        "total_prompt_tokens": sum(prompt_tokens),
        "total_completion_tokens": sum(completion_tokens),
    }


def write_report(allocation: dict, stats: dict[str, dict], judge_info: dict) -> None:
    lines = ["# Prompt A/B Comparison Report\n"]
    lines.append(
        "Closes ADR-0012 Decision 2 / docs/evaluation-design.md Decision 6 -- "
        "the LLM-evaluation phase's rubric gap (only one generation approach "
        "was ever compared). Model held fixed (`gpt-5.4-mini`), "
        "`temperature=0.2` for both arms, retrieval held fixed per question "
        "(one `search()` call reused for both prompts). Judged with the "
        "existing, unmodified `judge.py`.\n"
    )
    lines.append(f"**Judge model used:** {judge_info['model']} "
                 f"(fallback from gpt-5.4 used: {judge_info['used_fallback']})\n")
    lines.append(f"**Stratified subset allocation** (largest-remainder, "
                 f"preserving each category's real share of the 122-question "
                 f"combined set): {allocation}\n")

    lines.append("## Per-arm results\n")
    lines.append("| Metric | Prompt A | Prompt B |")
    lines.append("|---|---|---|")
    a, b = stats["A"], stats["B"]
    def row(label, key, fmt="{:.3f}"):
        av = a[key]
        bv = b[key]
        av_s = fmt.format(av) if isinstance(av, float) else str(av)
        bv_s = fmt.format(bv) if isinstance(bv, float) else str(bv)
        return f"| {label} | {av_s} | {bv_s} |"
    lines.append(row("n answers", "n_answers", "{}"))
    lines.append(row("n claims judged", "n_claims_judged", "{}"))
    lines.append(f"| verdict counts | {a['verdict_counts']} | {b['verdict_counts']} |")
    lines.append(row("citation precision", "citation_precision"))
    lines.append(row("claims per answer (mean)", "claims_per_answer"))
    lines.append(row("abstention rate", "abstention_rate"))
    lines.append(row("mean prompt tokens", "mean_prompt_tokens", "{:.0f}"))
    lines.append(row("mean completion tokens", "mean_completion_tokens", "{:.0f}"))
    lines.append(row("total prompt tokens (subset)", "total_prompt_tokens", "{}"))
    lines.append(row("total completion tokens (subset)", "total_completion_tokens", "{}"))

    with open(REPORT_PATH, "w", encoding="utf-8") as f:
        f.write("\n".join(lines) + "\n")
    print(f"[ok] wrote {REPORT_PATH.relative_to(PROJECT_ROOT)}")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--n", type=int, default=DEFAULT_N)
    parser.add_argument("--seed", type=int, default=DEFAULT_SEED)
    parser.add_argument("--resume", action="store_true")
    parser.add_argument("--report-only", action="store_true",
                         help="Skip generation/judging, just recompute the "
                              "report from existing result/judgment files.")
    args = parser.parse_args()

    judge_info = get_judge_model()

    if not args.report_only:
        questions = load_question_set()
        sample, allocation = stratified_sample(questions, args.n, args.seed)
        print(f"[ok] sampled {len(sample)} question(s), allocation={allocation}")
        run_generation(sample, resume=args.resume)
        run_judging(resume=args.resume)
    else:
        records = load_results()
        categories = Counter(r["category"] for r in records if r["arm"] == "A")
        allocation = dict(categories)

    records = load_results()
    judgments = load_judgments()
    if not judgments:
        print("[ok] no judgments yet -- nothing to report.")
        return

    stats = {arm: compute_arm_stats(arm, records, judgments) for arm in ARMS}
    write_report(allocation if not args.report_only else allocation, stats, judge_info)


if __name__ == "__main__":
    main()
