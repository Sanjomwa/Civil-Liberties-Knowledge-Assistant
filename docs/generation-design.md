# Generation Phase Design (Pre-Implementation Reference)

Synthesizes the frozen architecture's core acceptance principle ("every
answer must cite its sources"; "when evidence is thin or contradictory,
the system must say so explicitly"), `04-evaluation/project/
project_evaluation_plan.md`'s pre-existing Tier 2 evaluation design
(citation precision, human-reviewed sample, a dedicated thin/
contradictory-evidence ground-truth slice), and a 2026-07-24 Fable
design consult into one coherent picture of what `src/generation/` will
do when it's built. Design reference, not a status report — no code
exists yet at time of writing. Mirrors the shape of `docs/
retrieval-design.md` and `docs/ingestion-design.md`, written the same
way before code existed in each of those phases.

**Frozen principles this phase inherits, unchanged:** the pipeline stays
sequential and simple — no orchestration framework, no abstract
interfaces for hypothetical future needs. Any deviation from an
already-decided architecture element gets an ADR. Retrieval's `search()`
is read-only input here, never modified — this phase consumes it exactly
as closed.

---

## What retrieval already provides

`search(query, top_k=10, method="hybrid", lifecycle_status="active",
rrf_k=None) -> list[dict]`, recorded default hybrid/k=10, returns chunk
dicts: `chunk_id`, `doc_id`, `text`, `organization`, `countries`,
`publication_date`, `doc_type`, `lifecycle_status`, `pages` (true PDF
page numbers, or `null` for non-PDF sources — ADR-0008).

**Chunks do NOT carry `title` or `url`.** Those live in `data/metadata/
{doc_id}.json`'s `declared` block (`title`, `organization`, `countries`,
`publication_date`, `url`, `doc_type`, `source_format`, `topics`,
`language`, `selection_rationale`, `corpus_version`) — found by reading
`metadata.py` directly during the Fable consult, not assumed. Citation
rendering needs a `doc_id -> data/metadata/{doc_id}.json` lookup; this
is real, not optional plumbing.

Known, already-measured properties of what `search()` returns, relevant
to this phase's decisions below: a neighbor-aware Relaxed Hit Rate
~17-23 points above strict Hit Rate (a real chunk-overlap scoring
artifact, not necessarily genuine irrelevance); HR@3/HR@5 notably below
HR@10 (recall costs real ground the fewer chunks are used); hybrid's
source-diversity@10 is narrower than plain text search's (a retrieval
property, deliberately not retrieval-fixed — this phase is where that
finding cashes out, see below).

---

## Pipeline shape

**Single LLM call, plus a deterministic (non-LLM) parse/validate step —
not a second LLM call.**

The LLM is given the full 10 retrieved chunks, numbered `[1]`..`[10]`
in the prompt, and instructed to attach `[n]` markers to claims,
referring only to the numbered excerpts — **it never writes a citation
itself, only picks an index.** A fabricated page number or title becomes
structurally impossible, since the model never generates one; the
citation text is assembled mechanically afterward from `[n] -> chunk ->
doc_id -> data/metadata/{doc_id}.json`.

Post-generation, `citations.py` parses every `[n]` marker out of the
answer text, drops any outside the valid 1-10 range, and flags any
claim-bearing paragraph with zero markers (a real signal of an
unsupported claim slipping through, worth surfacing even without a full
second LLM pass).

**A second LLM grounding/verification pass was considered and rejected
for now** — it would catch a different failure mode (a real citation
that doesn't actually support the claim made), but doubles latency/cost,
adds a new failure surface, and duplicates the evaluation plan's own
human-reviewed citation-precision check, which is the more trustworthy
mechanism for exactly this failure mode per that plan's own stated
preference for human review over LLM-judge review here. Documented
fallback if that review finds real semantic-support problems at scale.

---

## Context size: all 10 retrieved chunks

Not truncated to fewer. The HR@5 -> HR@10 recall gain (roughly 18
points at the recorded default) is large relative to the token cost of
~5 extra 1500-character chunks — and the Relaxed Hit Rate finding means
a real share of what a naive "top-5 only" cut would drop is harmless
same-document redundancy, not noise. Dilution risk (irrelevant excerpts
crowding the prompt) is handled via explicit prompt instruction ("not
every excerpt below is relevant to the question — cite only the ones
you actually use"), not by truncating the input.

---

## Thin and contradictory evidence: two different problems, handled two different ways

**These are split deliberately, not lumped into one "confidence" flag.**

### Thin evidence — mechanical, computed on the CITED subset, not the retrieved one

The originally-considered approach (reuse `search()`'s own
source-diversity@10 machinery as a pre-LLM check on the *retrieved* set)
was directly challenged during the Fable consult and dropped: it
measures availability, not what the answer actually relies on.
Retrieval always returns 10 chunks regardless of how many the model
actually uses — a pre-check would misfire in both directions (falsely
flagging "thin" when broad retrieval existed but only 2 strong sources
were actually needed; failing to flag when 8 of 10 retrieved chunks go
unused and the real citation set is genuinely narrow).

**Adopted instead:** after `citations.py` parses which chunks were
actually cited, compute distinct orgs / distinct docs / publication-date
spread over that cited subset only — free, since the parse step already
has it. Render a factual sourcing footer, not a binary verdict, e.g.
*"Sourcing: all cited evidence comes from one organization (OONI),
across 3 reports (2023-2025)."* A factual footer handles a case a
boolean can't — a single genuinely strong source and three same-org
reports across years both count as "one org," but they aren't the same
situation to a researcher reading the answer, and stating the fact lets
them judge it rather than being told a verdict. A stronger, explicit
caveat sentence is added specifically when cited-doc count == 1 (a
single document, not just a single organization).

### Contradictory evidence — prompted LLM behavior, verified by evaluation, not mechanically detected

No feasible mechanical check exists for "do these two excerpts disagree"
short of real NLI machinery, which is out of scope for this phase's
timeline. Handled via explicit prompt instruction: when cited excerpts
disagree, state both positions with their own citations, and never
average or silently pick one. The evaluation plan's own dedicated
contradictory-evidence ground-truth slice is the actual verification
mechanism for whether this behavior holds in practice — not something
this phase's code can self-certify.

---

## Citation format

Inline `[n]` markers in the answer text, 1:1 with the numbered prompt
excerpts (deliberately no merging of same-document chunks — the
evaluation plan's citation-precision metric is defined at chunk level,
so `marker -> chunk_id` needs to resolve exactly). A rendered Sources
list follows the answer: `[3] CIPESA, "State of Internet Freedom in
Africa 2025" (2025-09-01), pp. 7-8. <url>`.

Return shape is a structured dict, not just prose — `{answer_markdown,
citations: [{marker, chunk_id, doc_id, pages}], sourcing: {...}, usage:
{...}}` — since the interface, monitoring, and LLM-evaluation phases all
need to consume this, not just display the markdown.

---

## File structure

Three files, matching `src/retrieval/`'s own one-responsibility-per-file
pattern — deliberately not more, per the project's standing
modular/non-bloated preference:

- **`prompts.py`** — the one default system/user prompt template
  (citation-marker protocol + the thin/contradictory instructions
  above). No comparison harness — prompt/model comparison is the LLM
  evaluation phase's job, not this one's.
- **`generate.py`** — `answer(query: str) -> dict`. Calls `search()`
  unchanged (recorded default), builds the prompt from the 10 results,
  makes one LLM call (`gpt-5.4-mini`, matching `ground_truth.py`'s
  already-established model choice for this OpenAI project/key — not a
  new model decision), and assembles the final result dict.
- **`citations.py`** — marker parsing/validation, the
  `doc_id -> data/metadata/{doc_id}.json` lookup, Sources-list
  rendering, and the sourcing-footer logic described above.

---

## Explicitly not building this phase

Mirrors the retrieval review's own "not now" calls, same reasoning
(deadline proportionality, not that these ideas are wrong in the
abstract): a second LLM verification/grounding pass; NLI-based
contradiction detection; merging overlapping adjacent chunks to save
prompt tokens (would break clean chunk-level citations and page
ranges — the same naive-page-number mistake ADR-0008 exists to prevent,
in new clothing); JSON-mode/structured-output enforcement (a regex over
`[n]` markers is sufficient for this scope); streaming, response
caching, conversation memory; any model or prompt comparison.

## What would trigger a revisit

- If the evaluation phase's human-reviewed citation-precision check
  finds a real, non-trivial rate of "real citation, unsupported claim"
  errors — that's the trigger for the second LLM verification pass
  explicitly deferred above, not a hypothetical to build preemptively.
- If NLI-quality contradiction detection becomes cheap/available enough
  to add without a real time cost — revisit the prompted-only approach
  to contradictory evidence.
- If the sourcing footer's single-org/single-doc thresholds turn out to
  fire too often or too rarely against real generated answers — tune the
  threshold, not the mechanism.
