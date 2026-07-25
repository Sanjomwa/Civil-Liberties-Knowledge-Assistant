"""
contradiction_search.py -- bounded, one-time empirical search for a real
cross-organization contradiction in the corpus, per docs/evaluation-design.md
Decision 4 and ADR-0010.

Per ADR-0010: before assuming no real contradiction exists, actually look
for one -- but BOUNDED, not open-ended. Names 5-8 candidate shared real
events up front, calls search() for each, forms cross-organization pairs
from each event's top-10 results, and caps the pairwise disagreement scan
at roughly 50 calls total. Declares the search complete either way once
that budget is spent -- never retried indefinitely.

If nothing real survives: per ADR-0010, does NOT edit real chunk text to
manufacture one. The absence is documented as a real, named evaluation gap
(see reports.md), and the contradiction-handling *mechanism* is verified
separately via judge.py's synthetic fixture instead.

Usage:
    uv run python src/evaluation/contradiction_search.py
"""

import json
import sys
from itertools import combinations
from pathlib import Path

from dotenv import load_dotenv
from openai import OpenAI

PROJECT_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(PROJECT_ROOT / "src"))
from retrieval.search import search  # noqa: E402

load_dotenv()

EVAL_DIR = PROJECT_ROOT / "data" / "eval"
OUTPUT_PATH = EVAL_DIR / "contradiction_search_results.json"

DISAGREEMENT_MODEL = "gpt-5.4-mini"  # cheap classification call, not the calibration judge
TOTAL_CALL_BUDGET = 50

# Named up front, per ADR-0010's bounding requirement -- known candidate
# shared real events already identified in this corpus (cross-referenced
# against corpus/sources/*.yaml document titles/scope before writing this
# list, not guessed blind).
CANDIDATE_EVENTS = [
    "Kenya June 2024 #RejectFinanceBill2024 internet shutdown",
    "Uganda January 2026 election internet shutdown",
    "Uganda 2021 election internet blackout",
    "Ethiopia 2023 social media blocking",
    "Tanzania 2024 Twitter X platform blocking",
    "Tanzania 2025 X platform blocking",
    "Kenya 2025 Telegram KCSE exam blocking",
]

DISAGREEMENT_SYSTEM_PROMPT = """You are checking two excerpts from different organizations' \
reports on the same real-world event, to see if they state conflicting values for the same \
checkable fact (an exact date, a duration, a numeric scale, or an attributed cause).

Respond with ONLY a compact JSON object, no other text:
{"disagree": true | false, "fact_compared": "<what fact you compared>", "explanation": "<one sentence>"}

Only say disagree=true if both excerpts make a specific, checkable claim about the SAME fact \
and those claims are genuinely inconsistent with each other -- not just different levels of \
detail or different facts about the same broader event."""


def form_cross_org_pairs(chunks: list[dict]) -> list[tuple[dict, dict]]:
    pairs = []
    for a, b in combinations(chunks, 2):
        if a["organization"] != b["organization"]:
            pairs.append((a, b))
    return pairs


def check_pair_disagreement(client: OpenAI, chunk_a: dict, chunk_b: dict) -> dict:
    user_content = (
        f"Excerpt 1 (from {chunk_a['organization']}):\n{chunk_a['text']}\n\n"
        f"Excerpt 2 (from {chunk_b['organization']}):\n{chunk_b['text']}"
    )
    response = client.chat.completions.create(
        model=DISAGREEMENT_MODEL,
        messages=[
            {"role": "system", "content": DISAGREEMENT_SYSTEM_PROMPT},
            {"role": "user", "content": user_content},
        ],
        temperature=0.0,
    )
    raw = (response.choices[0].message.content or "").strip()
    try:
        parsed = json.loads(raw.strip("`").removeprefix("json").strip())
    except (json.JSONDecodeError, AttributeError):
        parsed = {"disagree": False, "fact_compared": "unparseable", "explanation": raw[:200]}
    return parsed


def main() -> None:
    client = OpenAI()
    calls_used = 0
    survivors = []
    per_event_log = []

    for event in CANDIDATE_EVENTS:
        if calls_used >= TOTAL_CALL_BUDGET:
            print(f"[budget] {TOTAL_CALL_BUDGET}-call budget spent -- stopping before '{event}'.")
            break

        results = search(event, top_k=10, method="hybrid")
        pairs = form_cross_org_pairs(results)
        # Spread the remaining budget roughly evenly across remaining events.
        remaining_events = len(CANDIDATE_EVENTS) - CANDIDATE_EVENTS.index(event)
        remaining_budget = TOTAL_CALL_BUDGET - calls_used
        per_event_cap = max(1, remaining_budget // remaining_events)
        pairs = pairs[:per_event_cap]

        print(f"[event] '{event}' -- {len(results)} chunk(s) retrieved, "
              f"{len(pairs)} cross-org pair(s) checked (budget remaining: {remaining_budget})")

        event_survivors = []
        for chunk_a, chunk_b in pairs:
            if calls_used >= TOTAL_CALL_BUDGET:
                break
            verdict = check_pair_disagreement(client, chunk_a, chunk_b)
            calls_used += 1
            if verdict.get("disagree"):
                survivor = {
                    "event": event,
                    "chunk_a": {"chunk_id": chunk_a["chunk_id"], "doc_id": chunk_a["doc_id"],
                                "organization": chunk_a["organization"], "text": chunk_a["text"]},
                    "chunk_b": {"chunk_id": chunk_b["chunk_id"], "doc_id": chunk_b["doc_id"],
                                "organization": chunk_b["organization"], "text": chunk_b["text"]},
                    "fact_compared": verdict.get("fact_compared"),
                    "explanation": verdict.get("explanation"),
                }
                event_survivors.append(survivor)
                survivors.append(survivor)

        per_event_log.append({
            "event": event,
            "n_retrieved": len(results),
            "n_pairs_checked": len(pairs),
            "n_survivors": len(event_survivors),
        })

    output = {
        "candidate_events": CANDIDATE_EVENTS,
        "total_call_budget": TOTAL_CALL_BUDGET,
        "calls_used": calls_used,
        "per_event_log": per_event_log,
        "survivors": survivors,
        "conclusion": (
            f"{len(survivors)} candidate disagreement(s) flagged out of {calls_used} pair(s) "
            f"checked across {len(per_event_log)} event(s). Human verification still required "
            f"before treating any survivor as a confirmed real contradiction."
            if survivors else
            f"No candidate disagreements survived {calls_used} pairwise checks across "
            f"{len(per_event_log)} event(s), within the {TOTAL_CALL_BUDGET}-call budget. "
            f"Per ADR-0010, this absence is documented as a real evaluation gap, not "
            f"fabricated around -- see judge.py's synthetic contradiction-mechanism fixture "
            f"for the mechanism-only verification instead."
        ),
    }

    EVAL_DIR.mkdir(parents=True, exist_ok=True)
    with open(OUTPUT_PATH, "w", encoding="utf-8") as f:
        json.dump(output, f, indent=2, ensure_ascii=False)
        f.write("\n")

    print(f"\n[ok] {calls_used} pairwise call(s) used, {len(survivors)} survivor(s) found.")
    print(f"[ok] wrote {OUTPUT_PATH.relative_to(PROJECT_ROOT)}")
    print(f"\n{output['conclusion']}")


if __name__ == "__main__":
    main()
