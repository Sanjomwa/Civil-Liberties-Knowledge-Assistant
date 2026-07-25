"""
generate.py -- answer(query) -> dict, the one generation entry point.

Calls retrieval's search() unchanged (recorded default: hybrid, k=10),
builds the prompt (prompts.py), makes one LLM call, and assembles the
final structured result using citations.py's mechanical parsing -- per
ADR-0009, no second LLM call, no model/prompt comparison (that's the
LLM evaluation phase's job, not this one's).

Requires OPENAI_API_KEY (via .env / load_dotenv()) -- same pattern as
src/retrieval/ground_truth.py.

Usage (as a library, not a script):
    from generate import answer
    result = answer("How does OONI detect Telegram blocking?")
"""

import sys
from pathlib import Path

from dotenv import load_dotenv
from openai import OpenAI

PROJECT_ROOT = Path(__file__).resolve().parents[2]

# search() lives in the sibling src/retrieval/ package -- no __init__.py
# anywhere in this project (every phase so far has been standalone
# scripts, not a formal package), so this relies on Python 3's implicit
# namespace packages rather than adding packaging scaffolding just for
# one cross-directory import.
sys.path.insert(0, str(PROJECT_ROOT / "src"))
from retrieval.search import search  # noqa: E402

from citations import parse_citations, render_sources, sourcing_footer  # noqa: E402
from prompts import SYSTEM_PROMPT, build_user_prompt  # noqa: E402

# Prompt A/B comparison run 2026-07-25 (ADR-0012 Decision 2 / docs/
# evaluation-design.md Decision 6, src/evaluation/compare_prompts.py) --
# SYSTEM_PROMPT ("Prompt A") confirmed and KEPT as the default, not
# replaced. Prompt B (prompts.SYSTEM_PROMPT_B, an evidence-first two-phase
# design meant to fix two real Prompt A precision failures found by an
# earlier spot-check) was real-run against a stratified 40-question subset
# with retrieval held fixed and judged by the same unmodified judge.py.
# Result: Prompt A won on citation precision (0.893 vs 0.869) with MORE
# claims per answer (4.425 vs 4.000, so this isn't a hedging/denominator
# artifact), similar abstention behavior, and lower token cost. Manual
# spot-check found why: Prompt B's compact one-line-per-fact EVIDENCE list
# repeatedly attributed several distinct facts -- which actually span two
# adjacent, half-overlapping real chunks (this project's chunk_size=1500/
# chunk_step=750 design) -- to a single marker number, a real citation-
# fidelity regression, not a measurement artifact. Full numbers, the
# specific misattribution cases, and the spot-check: reports.md (2026-07-25)
# and data/eval/prompt-comparison-report.md.

load_dotenv()

# Matches ground_truth.py's already-established model choice for this
# OpenAI project/key -- gpt-4o-mini isn't enabled on this account
# (403 model_not_found, confirmed 2026-07-22). Not a new model decision;
# model/prompt comparison is the LLM evaluation phase's job, not this one's.
LLM_MODEL = "gpt-5.4-mini"
TOP_K = 10


def answer(query: str, client: OpenAI | None = None) -> dict:
    """Runs the full generation pipeline for one query.

    Returns:
        {
            "query": str,
            "answer_markdown": str,        -- the model's raw answer, [n] markers intact
            "citations": [...],            -- from citations.parse_citations()
            "invalid_markers": [...],
            "unsupported_paragraphs": [...],
            "sources": str,                 -- rendered Sources list
            "sourcing": {...},              -- footer + distinct org/doc counts
            "usage": {...} | None,          -- token usage, for the monitoring phase
        }
    """
    client = client or OpenAI()

    chunks = search(query, top_k=TOP_K)
    if not chunks:
        return {
            "query": query,
            "answer_markdown": "No relevant evidence was found in the corpus for this question.",
            "citations": [],
            "invalid_markers": [],
            "unsupported_paragraphs": [],
            "sources": "",
            "sourcing": sourcing_footer([]),
            "usage": None,
        }

    user_prompt = build_user_prompt(query, chunks)
    response = client.chat.completions.create(
        model=LLM_MODEL,
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": user_prompt},
        ],
        temperature=0.2,
    )
    answer_text = response.choices[0].message.content.strip()

    parsed = parse_citations(answer_text, chunks)
    sources_list = render_sources(parsed["citations"])
    footer = sourcing_footer(parsed["citations"])

    usage = None
    if response.usage is not None:
        usage = {
            "prompt_tokens": response.usage.prompt_tokens,
            "completion_tokens": response.usage.completion_tokens,
            "total_tokens": response.usage.total_tokens,
        }

    return {
        "query": query,
        "answer_markdown": answer_text,
        "citations": parsed["citations"],
        "invalid_markers": parsed["invalid_markers"],
        "unsupported_paragraphs": parsed["unsupported_paragraphs"],
        "sources": sources_list,
        "sourcing": footer,
        "usage": usage,
    }


def main() -> None:
    """Ad-hoc manual check: `uv run python src/generation/generate.py <query>`."""
    if len(sys.argv) < 2:
        print("Usage: uv run python src/generation/generate.py <query>", file=sys.stderr)
        sys.exit(1)
    query = " ".join(sys.argv[1:])
    result = answer(query)
    print(result["answer_markdown"])
    print("\n--- Sources ---")
    print(result["sources"])
    print("\n--- Sourcing ---")
    print(result["sourcing"]["footer"])
    if result["invalid_markers"]:
        print(f"\n[warn] invalid markers used by the model: {result['invalid_markers']}", file=sys.stderr)
    if result["unsupported_paragraphs"]:
        print(f"[warn] {len(result['unsupported_paragraphs'])} paragraph(s) with no citation marker", file=sys.stderr)


if __name__ == "__main__":
    main()
