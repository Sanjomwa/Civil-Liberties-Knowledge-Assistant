"""
judge.py -- judge(claim_text, cited_chunk_texts) -> {verdict, reason}, the
one place citation-faithfulness scoring lives for this project.

Per ADR-0010 (protocol) as amended by ADR-0011 (unit/signature): the judge
scores one CLAIM at a time, not one raw citation marker. A claim is a
sentence in answer_markdown carrying at least one valid [n] marker,
extracted freshly from the raw answer text -- citations.py's own
parse_citations() dedupes to one record per distinct marker *number* for
the whole answer and discards which claim each marker was attached to, so
it cannot be reused for claim extraction itself (see extract_claims()
below). It CAN be reused for marker validity/chunk-id resolution, since
that's a non-lossy mechanical fact (same MARKER_RE rule) -- only the
per-claim marker association is the actual gap ADR-0011 fixes.

If a claim carries multiple markers (e.g. "...affected.[4][7]"), the
judge receives the UNION of all cited chunks' text in ONE call and
renders ONE verdict for the claim as a whole -- never one call per
marker, which would wrongly score a well-corroborated multi-source claim
as partial. Each call sees ONLY the claim text and its cited chunk
text(s) -- never the full answer, the question, or other claims' chunks
-- which structurally removes the self-preference risk a whole-answer
judge would carry.

Judge model, per ADR-0011: try gpt-5.4 first (checked empirically against
this OpenAI account/project, same discovery method LLM_MODEL used in
src/retrieval/ground_truth.py -- never assumed). If gpt-5.4 isn't enabled,
fall back to gpt-5.4-mini (the generator's own model) -- this makes
calibration self-judging, which must be reported as a named limitation,
not silently absorbed.

Also owns the synthetic contradiction-mechanism fixture test (ADR-0010):
a hand-built pair of excerpts engineered to disagree on a checkable fact,
verifying the generation prompt's contradiction-handling mechanism
(ADR-0009: state both positions, never average) independent of whether
the real corpus happens to contain one. Structurally separate from
real-corpus scoring -- never folded into citation-precision numbers.

Usage (as a library, not a script):
    from judge import judge, extract_claims, get_judge_model
"""

import json
import re
import sys
from pathlib import Path

from dotenv import load_dotenv
from openai import OpenAI, PermissionDeniedError

PROJECT_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(PROJECT_ROOT / "src"))
sys.path.insert(0, str(PROJECT_ROOT / "src" / "generation"))

from prompts import build_user_prompt  # noqa: E402
from citations import parse_citations  # noqa: E402

load_dotenv()

PREFERRED_JUDGE_MODEL = "gpt-5.4"
FALLBACK_JUDGE_MODEL = "gpt-5.4-mini"  # same model generate.py uses -- self-judging if used

# Sentence-boundary regex: greedily consume everything up to a terminal
# punctuation mark, then swallow any [n] marker group(s) that immediately
# follow it -- this project's own generation prompt encourages exactly
# that style ("...affected.[4][7]"). Decimal numbers (e.g. "3.5 million")
# would otherwise falsely end a "sentence" at the embedded period, since
# the regex can't see across a period it must treat as a terminator
# candidate -- _protect_decimals()/_restore_decimals() sidestep this by
# temporarily masking digit-period-digit sequences before splitting, not
# by trying to special-case it inside the regex itself.
# Known limitation, explicitly accepted per ADR-0011's own "what would
# trigger a revisit": abbreviations or unusual punctuation can still
# missegment real text. Not perfect, good enough to extract real claims.
_SENTENCE_RE = re.compile(r"[^.!?]*[.!?]+(?:\s*\[\d+\])*")
_MARKER_RE = re.compile(r"\[(\d+)\]")
_DECIMAL_RE = re.compile(r"(?<=\d)\.(?=\d)")
_DECIMAL_PLACEHOLDER = "\x00"


def _protect_decimals(text: str) -> str:
    return _DECIMAL_RE.sub(_DECIMAL_PLACEHOLDER, text)


def _restore_decimals(text: str) -> str:
    return text.replace(_DECIMAL_PLACEHOLDER, ".")


def extract_claims(answer_markdown: str, valid_markers: set[int]) -> list[dict]:
    """Extracts claims freshly from raw answer_markdown text -- a claim is
    a sentence containing at least one marker that's a member of
    `valid_markers` (the set of marker numbers citations.parse_citations()
    already confirmed fall in 1..len(chunks) for this specific answer).
    Invalid markers found in a sentence are simply not counted -- they're
    already tracked separately at the whole-answer level via
    parse_citations()'s own `invalid_markers` list.

    Returns:
        [{"claim_text": str, "markers": [int, ...]}, ...] -- markers are
        deduped and kept in first-seen order per claim (a claim citing
        [4][4][7] behaves the same as one citing [4][7]).
    """
    protected = _protect_decimals(answer_markdown)
    claims = []
    matched_spans = []

    for match in _SENTENCE_RE.finditer(protected):
        text = _restore_decimals(match.group(0)).strip()
        matched_spans.append((match.start(), match.end()))
        if not text:
            continue
        markers = []
        for m in _MARKER_RE.findall(text):
            n = int(m)
            if n in valid_markers and n not in markers:
                markers.append(n)
        if markers:
            claims.append({"claim_text": text, "markers": markers})

    # Any trailing text after the last matched terminal punctuation (e.g. a
    # final line with no closing period, or -- if _SENTENCE_RE never
    # matched at all, since it requires at least one [.!?] -- the entire
    # text) would otherwise be silently dropped. tail_start=0 when there
    # were no sentence matches at all, so the whole answer is checked.
    tail_start = matched_spans[-1][1] if matched_spans else 0
    tail = _restore_decimals(protected[tail_start:]).strip()
    if tail:
        markers = []
        for m in _MARKER_RE.findall(tail):
            n = int(m)
            if n in valid_markers and n not in markers:
                markers.append(n)
        if markers:
            claims.append({"claim_text": tail, "markers": markers})

    return claims


def claims_with_chunk_text(answer_markdown: str, citations: list[dict],
                            retrieved_chunks: dict[str, str]) -> list[dict]:
    """Combines extract_claims() with the marker -> chunk_id resolution
    citations.py already computed (parse_citations()'s `citations` list)
    and the persisted {chunk_id: text} map from run_answers.py, producing
    exactly what judge() needs: one entry per claim, with the union of its
    cited chunks' real text attached.

    Returns:
        [{"claim_text": str, "markers": [int, ...],
          "cited_chunk_texts": [str, ...]}, ...]
    """
    marker_to_chunk_id = {c["marker"]: c["chunk_id"] for c in citations}
    valid_markers = set(marker_to_chunk_id)

    claims = extract_claims(answer_markdown, valid_markers)
    for claim in claims:
        chunk_ids = []
        for n in claim["markers"]:
            cid = marker_to_chunk_id[n]
            if cid not in chunk_ids:
                chunk_ids.append(cid)
        claim["cited_chunk_texts"] = [
            retrieved_chunks[cid] for cid in chunk_ids if cid in retrieved_chunks
        ]
    return claims


# v1: original protocol prompt (ADR-0010/0011). Kept verbatim, unmodified, for
# audit/comparison -- this is the prompt the recorded 0.879 result actually used.
JUDGE_SYSTEM_PROMPT_V1 = """You are an evidence-verification judge. You will be given a single \
claim -- one sentence from a generated answer -- and one or more excerpts that were cited as \
its source. Your only job is to judge whether the excerpt(s) actually support the claim: pure \
entailment, nothing else.

Respond with ONLY a compact JSON object, no other text:
{"verdict": "supported" | "partial" | "unsupported", "reason": "<one short sentence>"}

- "supported": the excerpt(s) fully and directly support the claim's factual content.
- "partial": the excerpt(s) support part of the claim but not all of it, or only loosely or \
indirectly support it.
- "unsupported": the excerpt(s) do not support the claim at all, or contradict it.

Do not use any outside knowledge. Judge only whether the given excerpt(s) entail the claim."""

# v2, 2026-07-25: two targeted edits per the ADR-0011 addendum's Opus 5 consult
# and the empirical claim-shape cross-check that preceded this change (see
# reports.md for both). (1) "supported" now explicitly covers a direct,
# one-step paraphrase/combination of facts that are each separately and
# explicitly stated -- the v1 "partial" catch-all ("loosely or indirectly
# support it") was broad enough to absorb this and was doing so on the large
# majority of the calibration sample's disagreements, not just negation
# claims. (2) "supported" now explicitly covers an accurately-reported
# absence claim (the cited material genuinely does not contain the thing the
# claim says is absent) -- previously structurally unverifiable under
# isolated entailment even when correct. A claim asserting absence of
# something that IS actually present in the excerpt(s) remains "unsupported"
# (a contradiction), unchanged from v1's intent.
JUDGE_SYSTEM_PROMPT_V2 = """You are an evidence-verification judge. You will be given a single \
claim -- one sentence from a generated answer -- and one or more excerpts that were cited as \
its source. Your only job is to judge whether the excerpt(s) actually support the claim: pure \
entailment, nothing else.

Respond with ONLY a compact JSON object, no other text:
{"verdict": "supported" | "partial" | "unsupported", "reason": "<one short sentence>"}

- "supported": the excerpt(s) fully and directly support the claim's factual content. This \
includes a claim that directly restates, paraphrases, or combines two or more facts that are \
EACH separately and explicitly stated in the excerpt(s) -- a single, reasonable synthesis step \
over explicit facts is "supported," not "partial." This also includes a claim that asserts the \
excerpt(s) do NOT contain, state, or mention some specific thing, when that thing genuinely does \
not appear anywhere in the excerpt(s) -- an accurately-reported absence is directly checkable \
against the given text and counts as "supported," not "partial" or "unsupported."
- "partial": the excerpt(s) support part of the claim but not all of it, or the claim requires \
real speculative reasoning, an unstated assumption, or more than one genuine inferential step \
beyond directly combining explicitly stated facts.
- "unsupported": the excerpt(s) do not support the claim at all, contradict it, or the claim \
asserts an absence of something that the excerpt(s) actually DO state (a false "not mentioned" \
claim is a contradiction, not a partial match).

Do not use any outside knowledge. Judge only whether the given excerpt(s) entail the claim."""

# v3, 2026-07-25: targeted at a distinct gap found in a blind independent
# re-read of the 22 remaining v1-vs-AI-reviewer disagreement rows (see
# reports.md and decisionlog.md, 2026-07-25). v2's "supported" clause
# already read "combines two OR MORE facts" (not literally capped at two --
# confirmed against the real text, not assumed), but 17 of the 22 rows were
# three-plus-fact combinations or comparative/superlative claims ("X is the
# longest/most persistent," "Y's duration is not given") that v2 still
# scored partial/unsupported in practice. Diagnosis: (1) "combines... facts"
# doesn't naturally read as covering a COMPARISON or ranking operation across
# facts, only restating/combining them; (2) the "partial" clause's "more than
# one genuine inferential step" is ambiguous for a claim chaining 3+ facts,
# even though "supported"'s "two or more" was never meant to exclude that.
# v3 makes both points explicit: three-or-more-fact synthesis is unambiguously
# "supported" regardless of count, and comparative/superlative claims are
# "supported" when the comparison is stated outright or directly computable
# from values each explicitly stated in the excerpt(s) -- no outside
# knowledge or estimation. The negation-claim clause (the separate,
# already-disclosed rows-1/3/4 issue) is copied byte-for-byte from v2,
# untouched -- not this task's target, and changing it risks conflating two
# different fixes.
JUDGE_SYSTEM_PROMPT_V3 = """You are an evidence-verification judge. You will be given a single \
claim -- one sentence from a generated answer -- and one or more excerpts that were cited as \
its source. Your only job is to judge whether the excerpt(s) actually support the claim: pure \
entailment, nothing else.

Respond with ONLY a compact JSON object, no other text:
{"verdict": "supported" | "partial" | "unsupported", "reason": "<one short sentence>"}

- "supported": the excerpt(s) fully and directly support the claim's factual content. This \
includes a claim that directly restates, paraphrases, or combines two, three, or more facts \
that are EACH separately and explicitly stated in the excerpt(s) -- a single, reasonable \
synthesis step over any number of explicit facts is "supported," not "partial," regardless of \
how many individual facts are combined. This also includes a comparative or superlative claim \
(e.g. "X lasted the longest," "Y's duration is not given") when the comparison is either \
explicitly stated somewhere in the cited excerpt(s), or directly computable by comparing two or \
more numbers or values that are each explicitly stated within the cited excerpt(s) -- never \
requiring outside knowledge, estimation, or a value not present in the excerpt(s). This also \
includes a claim that asserts the excerpt(s) do NOT contain, state, or mention some specific \
thing, when that thing genuinely does not appear anywhere in the excerpt(s) -- an \
accurately-reported absence is directly checkable against the given text and counts as \
"supported," not "partial" or "unsupported."
- "partial": the excerpt(s) support part of the claim but not all of it, or the claim requires \
real speculative reasoning, an unstated assumption, or more than one genuine inferential step \
beyond directly combining or comparing explicitly stated facts.
- "unsupported": the excerpt(s) do not support the claim at all, contradict it, or the claim \
asserts an absence of something that the excerpt(s) actually DO state (a false "not mentioned" \
claim is a contradiction, not a partial match).

Do not use any outside knowledge. Judge only whether the given excerpt(s) entail the claim."""

# JUDGE_SYSTEM_PROMPT stays bound to v1 until Step 4's cheap validation on the
# 47-row disagreement subset actually passes -- do not flip this default ahead
# of that result. judge() also accepts an explicit prompt_version="v2" for
# side-by-side comparison calls before any default changes.
JUDGE_SYSTEM_PROMPT = JUDGE_SYSTEM_PROMPT_V1
_PROMPTS_BY_VERSION = {
    "v1": JUDGE_SYSTEM_PROMPT_V1,
    "v2": JUDGE_SYSTEM_PROMPT_V2,
    "v3": JUDGE_SYSTEM_PROMPT_V3,
}


def _build_judge_user_prompt(claim_text: str, cited_chunk_texts: list[str]) -> str:
    excerpts = "\n\n---\n\n".join(cited_chunk_texts) if cited_chunk_texts else "(no cited excerpts)"
    return f"Claim:\n{claim_text}\n\nCited excerpt(s):\n\n{excerpts}"


def _parse_verdict(raw_text: str) -> dict:
    """Parses the judge model's JSON response. Falls back to a bare
    keyword scan if the model didn't return clean JSON (e.g. wrapped in
    markdown fences) -- degrades gracefully rather than crashing a real
    run over one malformed response."""
    text = raw_text.strip()
    if text.startswith("```"):
        text = text.strip("`")
        if text.lower().startswith("json"):
            text = text[4:]
        text = text.strip()
    try:
        parsed = json.loads(text)
        verdict = parsed.get("verdict", "").strip().lower()
        reason = parsed.get("reason", "").strip()
        if verdict in ("supported", "partial", "unsupported"):
            return {"verdict": verdict, "reason": reason}
    except (json.JSONDecodeError, AttributeError):
        pass

    lowered = raw_text.lower()
    for candidate in ("unsupported", "partial", "supported"):
        if candidate in lowered:
            return {"verdict": candidate, "reason": raw_text.strip()[:300]}
    return {"verdict": "unsupported", "reason": f"[unparseable judge response] {raw_text.strip()[:300]}"}


_judge_model_cache: dict | None = None


def get_judge_model(client: OpenAI | None = None) -> dict:
    """Checked, ordered judge-model preference, per ADR-0011: try gpt-5.4
    first (empirically, not assumed), fall back to gpt-5.4-mini if it's
    not enabled on this OpenAI account/project. Cached for the process
    lifetime -- this is a one-time availability check, not a per-claim one.

    Returns:
        {"model": str, "used_fallback": bool}
    """
    global _judge_model_cache
    if _judge_model_cache is not None:
        return _judge_model_cache

    client = client or OpenAI()
    try:
        client.chat.completions.create(
            model=PREFERRED_JUDGE_MODEL,
            messages=[{"role": "user", "content": "reply with the single word: ok"}],
            max_completion_tokens=5,
        )
        _judge_model_cache = {"model": PREFERRED_JUDGE_MODEL, "used_fallback": False}
    except PermissionDeniedError:
        _judge_model_cache = {"model": FALLBACK_JUDGE_MODEL, "used_fallback": True}
    return _judge_model_cache


def judge(claim_text: str, cited_chunk_texts: list[str],
          client: OpenAI | None = None, model: str | None = None,
          prompt_version: str = "v1") -> dict:
    """The one entailment-scoring call. Sees ONLY claim_text and
    cited_chunk_texts -- no answer, no question, no other claims' chunks.

    prompt_version selects JUDGE_SYSTEM_PROMPT_V1 (original, ADR-0010/0011) or
    JUDGE_SYSTEM_PROMPT_V2 (2026-07-25 partial-catch-all/negation fix) -- kept
    explicit and separate so v1 and v2 can be run side by side for
    comparison, rather than only ever calling whichever one is the module
    default at the time.

    Returns:
        {"verdict": "supported" | "partial" | "unsupported", "reason": str,
         "reasoning_tokens": int | None, "system_fingerprint": str | None}
        reasoning_tokens/system_fingerprint added 2026-07-25 for the
        reasoning-token/determinism diagnostic (reports.md) -- logged for
        every future call so the question is answerable from data already
        on disk next time, not a one-off probe. Not backfilled into
        existing judgments.jsonl/judgments_v2.jsonl rows.
    """
    client = client or OpenAI()
    if model is None:
        model = get_judge_model(client)["model"]
    system_prompt = _PROMPTS_BY_VERSION[prompt_version]

    response = client.chat.completions.create(
        model=model,
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": _build_judge_user_prompt(claim_text, cited_chunk_texts)},
        ],
        temperature=0.0,
    )
    raw_text = response.choices[0].message.content or ""
    parsed = _parse_verdict(raw_text)

    reasoning_tokens = None
    usage = response.usage
    if usage is not None and getattr(usage, "completion_tokens_details", None) is not None:
        reasoning_tokens = getattr(usage.completion_tokens_details, "reasoning_tokens", None)
    parsed["reasoning_tokens"] = reasoning_tokens
    parsed["system_fingerprint"] = getattr(response, "system_fingerprint", None)
    return parsed


# --- Synthetic contradiction-mechanism fixture (ADR-0010 / Decision 4) ---
# Hand-built, clearly synthetic -- NOT real corpus chunks. Verifies
# ADR-0009's prompt-only contradiction mechanism (state both positions,
# never average) in isolation from whether the real corpus happens to
# contain a genuine cross-source disagreement. Kept structurally separate
# from real-corpus metrics; never used to compute citation precision.

_FIXTURE_QUERY = "How long did the internet shutdown in Bandaria last, and who reported it?"
_FIXTURE_CHUNK_A = {
    "chunk_id": "synthetic-fixture-a",
    "doc_id": "synthetic-fixture-doc-a",
    "organization": "Synthetic Org A (fixture only, not a real corpus source)",
    "text": (
        "According to network measurement data collected during the incident, the "
        "nationwide internet shutdown in Bandaria lasted exactly 4 days, from January "
        "13 to January 17, 2026, affecting all major mobile network operators."
    ),
}
_FIXTURE_CHUNK_B = {
    "chunk_id": "synthetic-fixture-b",
    "doc_id": "synthetic-fixture-doc-b",
    "organization": "Synthetic Org B (fixture only, not a real corpus source)",
    "text": (
        "Interviews with telecom operator staff indicate the Bandaria shutdown "
        "actually extended for 6 days, from January 13 to January 19, 2026, longer "
        "than official statements acknowledged."
    ),
}


def run_contradiction_fixture_test(client: OpenAI | None = None) -> dict:
    """Feeds the two hand-built, deliberately-conflicting excerpts above
    through the real generation prompt (prompts.build_user_prompt), calls
    the generator model directly, and checks -- heuristically, not via the
    judge -- whether the model's answer states both positions (4 days AND
    6 days, each attached to its own citation) rather than averaging (e.g.
    blending to "5 days") or silently picking one side.

    Returns a dict with the raw answer text and a boolean assessment, so a
    human can independently read the model's actual output rather than
    trusting the heuristic alone. Explicitly excluded from real-corpus
    evaluation metrics -- reported separately, always labeled synthetic.
    """
    client = client or OpenAI()
    from generate import LLM_MODEL, SYSTEM_PROMPT  # noqa: E402 -- generator's own model/prompt, unmodified

    chunks = [_FIXTURE_CHUNK_A, _FIXTURE_CHUNK_B]
    user_prompt = build_user_prompt(_FIXTURE_QUERY, chunks)
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

    mentions_both_durations = "4" in answer_text and "6" in answer_text
    cites_both_sources = {c["marker"] for c in parsed["citations"]} == {1, 2}
    no_averaged_number = "5 days" not in answer_text.lower()
    surfaces_both_positions = mentions_both_durations and cites_both_sources and no_averaged_number

    return {
        "fixture_query": _FIXTURE_QUERY,
        "excerpt_a": _FIXTURE_CHUNK_A["text"],
        "excerpt_b": _FIXTURE_CHUNK_B["text"],
        "model_answer": answer_text,
        "citations_found": parsed["citations"],
        "surfaces_both_positions": surfaces_both_positions,
        "notes": (
            "Heuristic check: both duration figures (4, 6) present, both source "
            "markers ([1] and [2]) actually cited, and no blended/averaged figure "
            "('5 days') present. This is a SYNTHETIC fixture, not a real corpus "
            "finding -- excluded from citation-precision metrics."
        ),
    }


def main() -> None:
    """Ad-hoc manual check: prints the judge-model availability result and
    the contradiction fixture's outcome. `uv run python src/evaluation/judge.py`"""
    info = get_judge_model()
    print(f"[judge model] {info['model']} (fallback used: {info['used_fallback']})")

    fixture = run_contradiction_fixture_test()
    print(f"\n[contradiction fixture] surfaces_both_positions={fixture['surfaces_both_positions']}")
    print(f"model answer:\n{fixture['model_answer']}")


if __name__ == "__main__":
    main()
