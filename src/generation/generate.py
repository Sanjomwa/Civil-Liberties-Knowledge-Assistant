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

import re
import sys
import time
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

# ADR-0015 round 3: two prompt-wording iterations on SYSTEM_PROMPT's rule 2
# both left real gaps (round 2's disclose-don't-refuse wording produced a
# correct disclosure on 3 of 5 out-of-scope test questions but silently
# skipped it on the other 2, both times when the model had one confident,
# well-supported citation and simply didn't volunteer the sentence) --
# third Fable consult ruled a fourth wording attempt would keep losing to
# the model's own generation confidence, and moved the guarantee here,
# where it's deterministic instead of hoped-for.
#
# Checked first: src/retrieval/search.py's COUNTRY_KEYWORDS/_detect_countries
# already solve this exact detection problem for the five IN-scope
# countries, and chunk `countries` metadata (corpus/sources/*.yaml, via
# metadata.py) is confirmed to carry ONLY the five in-scope ISO codes
# (grep across every corpus/sources/*.yaml -- no exceptions), so option (a)
# from the task (reuse chunk metadata to detect which out-of-scope country a
# cited chunk covers) isn't available -- there's nothing to reuse. This is
# option (b): a small, separate keyword list, grounded in this corpus's
# real pan-continental document text (data/processed/cipesa/*.txt,
# data/processed/accessnow/*-africa-*.txt), not a generic world-country
# list -- countries below were confirmed to appear with real, substantive
# (non-citation/non-URL) body-text mentions in those documents, not just a
# passing table row.
#
# Lives here, not in search.py: this has nothing to do with retrieval
# ranking (it never touches `chunks` or re-ranks anything) -- it's a
# generation-phase display concern, used only to decide whether to prepend
# a disclosure sentence below.
#
# Deliberately NOT plain substring matching like _detect_countries (that
# file's simple `in` check is safe there because kenya/uganda/tanzania/
# ethiopia/rwanda don't collide) -- this longer list has two real
# collisions ("niger" is a substring of "nigeria"; "mali" is a substring of
# "somalia"), confirmed by checking every pair programmatically, so this
# uses \b-bounded regex matching instead, root names only (no adjectival
# forms, same convention as COUNTRY_KEYWORDS).
OUT_OF_SCOPE_COUNTRIES = {
    "nigeria": "Nigeria", "egypt": "Egypt", "morocco": "Morocco",
    "south africa": "South Africa", "zambia": "Zambia",
    "mozambique": "Mozambique", "cameroon": "Cameroon", "senegal": "Senegal",
    "ghana": "Ghana", "sudan": "Sudan", "somalia": "Somalia",
    "sierra leone": "Sierra Leone", "congo": "the Democratic Republic of Congo",
    "drc": "the Democratic Republic of Congo", "algeria": "Algeria",
    "tunisia": "Tunisia", "libya": "Libya", "chad": "Chad", "niger": "Niger",
    "mali": "Mali", "zimbabwe": "Zimbabwe", "togo": "Togo",
    "namibia": "Namibia", "botswana": "Botswana", "gabon": "Gabon",
    "angola": "Angola", "burkina faso": "Burkina Faso", "liberia": "Liberia",
    "mauritania": "Mauritania", "lesotho": "Lesotho", "guinea": "Guinea",
}


def _detect_out_of_scope_countries(query: str) -> list[str]:
    """Returns display names of out-of-scope countries named in the query,
    in first-appearance order, de-duplicated (e.g. "congo"/"drc" both map to
    the same display name and should only appear once)."""
    q = query.lower()
    seen: list[str] = []
    for keyword, display in OUT_OF_SCOPE_COUNTRIES.items():
        if re.search(rf"\b{re.escape(keyword)}\b", q) and display not in seen:
            seen.append(display)
    return seen


def _out_of_scope_disclosure(countries: list[str]) -> str:
    """Fixed, code-authored sentence -- never LLM-generated -- per ADR-0015
    round 3: the disclosure must not depend on the model remembering to
    write it. `countries` is display names, already deduplicated."""
    if len(countries) == 1:
        subject, verb = countries[0], "is"
    else:
        subject, verb = ", ".join(countries[:-1]) + f" and {countries[-1]}", "are"
    return (
        f"Note: {subject} {verb} outside this assistant's five-country curated "
        f"scope (Kenya, Uganda, Tanzania, Ethiopia, Rwanda); any coverage here is "
        f"incidental and the answer below may be less complete than for the five "
        f"focus countries."
    )


# ADR-0015 round 4, Part B fallback: the prompt restructure (labeled
# fact-block scope card, see SYSTEM_PROMPT) fixed the two canonical
# regression questions (org list, time window) on their exact wording, but
# testing phrasing variance beyond the canonical four found it doesn't fully
# generalize -- e.g. "What are your data sources?" and "What is the date
# range of the evidence in this corpus?" both still inferred a narrower/
# wrong answer from retrieved excerpts instead of reciting the fact block.
# Fable pre-approved this exact fallback in advance for that case: a
# post-answer, append-only supplement (never replace or intercept, same
# pattern as the out-of-scope-country fix), gated on a deliberately narrow,
# bounded keyword set -- some false negatives are an accepted tradeoff here
# over risking a false positive that appends boilerplate onto a genuine
# in-scope answer that merely happens to share vocabulary.
ORG_META_KEYWORDS = ("which organizations", "what organizations", "which sources", "what sources")
TIME_META_KEYWORDS = ("what time period", "what date range", "what years")
FOUR_ORGS = ("OONI", "Access Now", "CIPESA", "Freedom House")
ORG_FACT_CLAUSE = (
    "Note: this assistant's full source list is always OONI, Access Now, "
    "CIPESA, and Freedom House."
)
TIME_FACT_CLAUSE = "Note: this assistant's full curated time window is always 2022-2026."


def _needs_org_fact_append(query: str, answer_text: str) -> bool:
    q = query.lower()
    if not any(k in q for k in ORG_META_KEYWORDS):
        return False
    text_lower = answer_text.lower()
    return any(org.lower() not in text_lower for org in FOUR_ORGS)


def _needs_time_fact_append(query: str, answer_text: str) -> bool:
    q = query.lower()
    if not any(k in q for k in TIME_META_KEYWORDS):
        return False
    return not ("2022" in answer_text and "2026" in answer_text)


# ADR-0017 / docs/query-rewriting-design.md: normalizes a raw, possibly
# colloquial user query into the corpus's own report-style vocabulary
# before retrieval -- expanding abbreviations, making an implied country
# explicit, stripping conversational filler. This is the one Tier-3
# best-practice item (ADR-0012) not yet attempted; hybrid search and the
# P2 country-boost re-rank are both already shipped.
#
# Model choice: gpt-5.4-mini, not a smaller/cheaper model invented for
# this -- this account has only ever confirmed gpt-5.4 and gpt-5.4-mini
# enabled (gpt-4o-mini returns 403 model_not_found, per generate.py's own
# LLM_MODEL comment and ground_truth.py); gpt-5.4-mini is already this
# project's established cheap-classification-call model
# (contradiction_search.py's DISAGREEMENT_MODEL), so reusing it here
# rather than guessing at an unconfirmed model name.
REWRITE_MODEL = LLM_MODEL
REWRITE_MAX_COMPLETION_TOKENS = 150  # strict low budget, not the main answer's budget
REWRITE_TIMEOUT_SECONDS = 2.0

REWRITE_SYSTEM_PROMPT = """Rewrite the user's question into a single, clear search \
query for a corpus of internet-censorship and digital-rights reports about Kenya, \
Uganda, Tanzania, Ethiopia, and Rwanda.

- Expand abbreviations (e.g. "gov" -> "government", "reg" -> "registration").
- If a country is clearly implied but not named, make it explicit.
- Strip conversational filler ("hey", "can you tell me", "I was wondering", \
"so basically").
- Keep every specific fact, name, date, and detail from the original question. \
Do not add information that wasn't there, and do not answer the question.

Output ONLY the rewritten query on a single line -- no preamble, no quotation \
marks, no explanation."""


def rewrite_query(query: str, client: OpenAI | None = None) -> str:
    """One small-model LLM call that normalizes `query` into corpus
    report-vocabulary before retrieval. Fails open to the original,
    unmodified `query` on ANY error -- timeout, API error, or an empty/
    malformed response -- per ADR-0017's fail-safe requirement: this step
    must never be able to block or degrade an answer, only help retrieval
    or be a no-op. Same discipline as the out-of-scope disclosure and
    org/time fallback above (additive, never a point of failure for the
    base path)."""
    client = client or OpenAI()
    try:
        response = client.chat.completions.create(
            model=REWRITE_MODEL,
            messages=[
                {"role": "system", "content": REWRITE_SYSTEM_PROMPT},
                {"role": "user", "content": query},
            ],
            max_completion_tokens=REWRITE_MAX_COMPLETION_TOKENS,
            temperature=0,
            timeout=REWRITE_TIMEOUT_SECONDS,
        )
        rewritten = response.choices[0].message.content
        if not rewritten or not rewritten.strip():
            return query
        return rewritten.strip()
    except Exception:  # noqa: BLE001 -- fail-open by design, any error whatsoever
        return query


def answer(query: str, client: OpenAI | None = None) -> dict:
    """Runs the full generation pipeline for one query.

    Returns:
        {
            "query": str,
            "rewritten_query": str,        -- ADR-0017: rewrite_query()'s output,
                fed to search() instead of `query`; equals `query` unchanged
                whenever the rewrite call fails or times out (fail-open).
            "answer_markdown": str,        -- the model's raw answer, [n] markers intact
                -- may have a fixed, code-authored out-of-scope disclosure
                sentence prepended (ADR-0015 round 3, see
                _out_of_scope_disclosure) when the query names a detected
                out-of-scope country AND the model actually cited real
                evidence; never affects citations/invalid_markers/
                unsupported_paragraphs below, which are all computed from
                the model's original, unmodified text first. May also have
                a fixed org-list or time-window fact clause APPENDED
                (ADR-0015 round 4 Part B fallback) when the query matches a
                narrow org/time meta-question keyword set and the model's
                own answer is missing an org name or the full 2022-2026
                window -- same non-interference guarantee, added after
                citation parsing.
            "citations": [...],            -- from citations.parse_citations()
            "invalid_markers": [...],
            "unsupported_paragraphs": [...],
            "sources": str,                 -- rendered Sources list
            "sourcing": {...},              -- footer + distinct org/doc counts
            "usage": {...} | None,          -- token usage, for the monitoring phase
            "timings": {"retrieval_ms": int, "llm_ms": int},
                -- added 2026-07-26 (interface-design.md Decision 4/4a),
                measured around the existing search() and LLM calls --
                additive, every existing caller accesses specific keys by
                name (confirmed against run_answers.py) so this can't break
                anything already reading this dict.
            "retrieved_chunks": [{"chunk_id": str, "score": float | None}, ...]
                -- added 2026-07-26 (Decision 4a): chunk_id + score only,
                deliberately no excerpt text, same restraint `citations`
                already applies. Lets the interface layer build
                citations_summary/retrieval_scores by joining against
                `citations`, without answer() exposing raw chunk text.
        }
    """
    client = client or OpenAI()

    # ADR-0017: rewrite feeds search() only -- everything downstream that
    # reflects the user's actual intent (the prompt shown to the model,
    # out-of-scope-country detection, the org/time meta-question fallback,
    # and the returned "query" field) keeps using the original `query`
    # unchanged. search() itself takes one query string for both hybrid
    # legs (no separate BM25-only parameter exists, and search() is not
    # modified per ADR-0017/the design doc), so the rewritten query feeds
    # both legs of hybrid search, not just BM25 -- the only option that
    # doesn't require reimplementing search()'s own RRF merge outside it.
    rewritten_query = rewrite_query(query, client=client)

    retrieval_start = time.monotonic()
    chunks = search(rewritten_query, top_k=TOP_K)
    retrieval_ms = int((time.monotonic() - retrieval_start) * 1000)

    if not chunks:
        return {
            "query": query,
            "rewritten_query": rewritten_query,
            "answer_markdown": "No relevant evidence was found in the corpus for this question.",
            "citations": [],
            "invalid_markers": [],
            "unsupported_paragraphs": [],
            "sources": "",
            "sourcing": sourcing_footer([]),
            "usage": None,
            "timings": {"retrieval_ms": retrieval_ms, "llm_ms": 0},
            "retrieved_chunks": [],
        }

    user_prompt = build_user_prompt(query, chunks)
    llm_start = time.monotonic()
    response = client.chat.completions.create(
        model=LLM_MODEL,
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": user_prompt},
        ],
        temperature=0.2,
    )
    llm_ms = int((time.monotonic() - llm_start) * 1000)
    answer_text = response.choices[0].message.content.strip()

    parsed = parse_citations(answer_text, chunks)
    sources_list = render_sources(parsed["citations"])
    footer = sourcing_footer(parsed["citations"])

    # Prepended to the DISPLAYED text only, after parse_citations() already
    # ran on the model's real, unmodified output -- citations/invalid_markers/
    # unsupported_paragraphs must stay accurate to what the model actually
    # wrote. This sentence carries no [n] marker and is never a "claim," so
    # it must never be counted as an unsupported paragraph either.
    out_of_scope = _detect_out_of_scope_countries(query)
    if out_of_scope and parsed["citations"]:
        answer_text = f"{_out_of_scope_disclosure(out_of_scope)}\n\n{answer_text}"

    # Round 4 Part B fallback -- appended, never prepended/replacing: this
    # is a supplement to an answer that's otherwise already given, not a
    # framing note that belongs before it (unlike the out-of-scope-country
    # disclosure above, which readers need before the rest of the answer).
    if _needs_org_fact_append(query, answer_text):
        answer_text = f"{answer_text}\n\n{ORG_FACT_CLAUSE}"
    if _needs_time_fact_append(query, answer_text):
        answer_text = f"{answer_text}\n\n{TIME_FACT_CLAUSE}"

    usage = None
    if response.usage is not None:
        usage = {
            "prompt_tokens": response.usage.prompt_tokens,
            "completion_tokens": response.usage.completion_tokens,
            "total_tokens": response.usage.total_tokens,
        }

    return {
        "query": query,
        "rewritten_query": rewritten_query,
        "answer_markdown": answer_text,
        "citations": parsed["citations"],
        "invalid_markers": parsed["invalid_markers"],
        "unsupported_paragraphs": parsed["unsupported_paragraphs"],
        "sources": sources_list,
        "sourcing": footer,
        "usage": usage,
        "timings": {"retrieval_ms": retrieval_ms, "llm_ms": llm_ms},
        "retrieved_chunks": [{"chunk_id": c["chunk_id"], "score": c.get("score")} for c in chunks],
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
