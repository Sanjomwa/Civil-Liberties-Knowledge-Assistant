# ADR-0013: Tiered Corpus Release, and Resolving a Licensing-Scope Conflict Between This Project's Own Docs

**Status:** Accepted, 2026-07-25.

## Context

ADR-0012's Tier 1 completion plan included "ship the processed corpus as
a release artifact," motivated by the Reproducibility rubric criterion
(2/2 requires "the dataset is accessible... easy to run") and OONI's real
429-on-scripted-requests friction. Before drafting a handoff prompt to
actually do this, the project's own licensing documents were checked
directly rather than assumed — and two real problems surfaced.

**First: shipping the full processed corpus publicly is a real, if
modest, licensing risk for two of the four source organizations, not
just OONI's acquisition friction.** Freedom House (46% of the corpus) is
not Creative-Commons licensed at all — their policy permits *sharing*
already-published content but gates *reproduction/republishing* behind
written permission. A permission request was sent 2026-07-13
(`press@freedomhouse.org`); as of this ADR, **twelve days later, there
has been no reply.** Access Now's report *text* specifically (as opposed
to their site's labeled "Media Material") was never confirmed
blanket-reusable either — `docs/licensing.md`'s own guidance is to "avoid
full verbatim redistribution of large excerpts beyond what the assistant
needs to answer a specific question with a citation." Chunking either
organization's reports into ~2,000-character pieces and publishing the
full set does not convert republication into citation-scale quotation —
it's the complete work in a different container. CIPESA (CC BY 4.0) and
OONI (CC BY-NC-SA 4.0, non-commercial satisfied) are not affected by this
concern.

**Second: this project's own two governance documents don't agree on how
broad the Freedom House gate is, and that was never caught until now.**
`docs/licensing.md` — the actual constraint document — states Freedom
House needs permission before the corpus is exposed "through the CLIO
API boundary **or any other public-facing redistribution**." A later
summary written into `docs/PROJECT_CONTINUITY.md` narrowed this,
restating the same constraint as just "no CLIO-facing redistribution of
Freedom House content." A public GitHub Release for this course
submission is unambiguously "public-facing redistribution" under the
first, original phrasing — the derived summary quietly narrowed a third
party's permission scope, which is a documentation defect, not a
competing decision that needed weighing.

An Opus 5 consult was run given the compliance stakes (per Sam's standing
instruction to consult before decisions like this, and this project's own
practice of treating governance-document conflicts seriously — see
`CLAUDE.md`'s repeated documentation-drift warnings). Full transcript in
`decisionlog.md`, 2026-07-25.

## Decision

### The conflict resolves to the stricter, original reading

`docs/licensing.md` is the constraint document; `docs/PROJECT_CONTINUITY.md`
is a derived summary. Where the two disagree about the scope of a third
party's own permission, **the stricter reading governs until the third
party says otherwise** — not the more convenient one. `PROJECT_CONTINUITY.md`'s
narrowed language is corrected to match `licensing.md`'s original scope.
This is now a standing rule for this project, not a one-off fix: any
future summary of a licensing/governance constraint must not narrow the
original document's scope without an explicit ADR justifying why.

### Tiered corpus release

The processed corpus ships as a public GitHub Release artifact, split by
actual licensing risk rather than shipped uniformly:

- **Full chunk text, published directly:** OONI and CIPESA. Each record
  carries its actual per-organization license
  (`CC BY-NC-SA 4.0`/`CC BY 4.0`) explicitly — not one blanket repo-level
  license note, since OONI's ShareAlike term propagates to anything
  derived from it and needs to stay visible at the record level.
- **Metadata and hash only, text stripped, for Freedom House and Access
  Now:** `doc_id`, source URL, chunk character offsets, a content hash,
  and the embedding vector — everything needed to verify a re-acquired
  chunk matches what this project actually indexed, without redistributing
  the underlying report text itself.
- **A new `src/ingestion/rehydrate.py`**, callable by anyone who clones
  this release: re-fetches the two restricted organizations' source
  documents (using the existing `acquisition: auto` paths already built
  for both — this doesn't require new acquisition logic, just applying
  the existing pipeline stages to reconstruct chunk text locally), re-runs
  the same deterministic chunking, and verifies the result against the
  stored hashes. A reviewer or future user ends up with the exact same
  corpus text locally, without this project ever having published it.

This is a stronger reproducibility story than a raw text dump, not a
weaker one: a reviewer who successfully rehydrates gets independent
proof the corpus matches what's indexed, rather than just trusting a
static file.

A handful of short, individually-cited excerpts already appearing in
this project's own evaluation fixtures and generated answers (i.e.,
normal citation use, the system's actual purpose) are unaffected by this
ADR — this decision is about bulk redistribution of the full processed
corpus, not about the system continuing to cite short excerpts from
Freedom House or Access Now documents in individual generated answers,
which is exactly the kind of use `docs/licensing.md` already treats as
low-risk.

### Follow-up to Freedom House

A short follow-up email was sent (Sam's own action, same as the original
request — no send capability exists on the Cowork/Claude side) referencing
the 2026-07-13 request, restating the ask briefly, and noting the
approaching course deadline without pressuring for a specific answer.
Documents that twelve days of silence isn't being treated as implicit
consent.

## Consequences

- `docs/licensing.md` is now explicitly the authoritative document for
  any future summary of per-org licensing constraints — restated in this
  ADR so it doesn't need re-discovering.
- `docs/PROJECT_CONTINUITY.md`'s Section 7 Freedom House entry is
  corrected to match `licensing.md`'s original broader scope.
- `src/ingestion/rehydrate.py` is a new module, not yet built — a real
  addition to the ingestion phase's scope, even though that phase is
  otherwise closed. Same "closed phase gets a documented real change, not
  a silent edit" discipline as every other post-closure addition this
  project has made.
- The release artifact itself doesn't exist yet — this ADR is the design;
  a Claude Code handoff prompt implementing it was drafted the same day.
- If Freedom House replies with permission before the corpus release is
  actually built, the tiered split can be revisited — see "what would
  trigger a revisit" below.

## Opus 5 consult

Consulted 2026-07-25, given the verbatim per-org licensing facts and the
real ambiguity between this project's own two documents. Confirmed the
risk is real but modest ("realistic worst case: a takedown notice"), and
that the larger cost isn't legal exposure but credibility — this
project's whole premise is provenance discipline and it's grant-facing,
so overriding its own written governance constraint for two rubric points
is a worse trade than the legal one. Identified the practical asymmetry
this ADR's tiered design is built on: the organization causing the real
reproducibility friction (OONI) is the cleanly-licensed one, and the
organizations needing protection (Freedom House, Access Now) already have
working scripted acquisition, making a hash-verified rehydration path
straightforward rather than a new acquisition problem. Recommended
resolving the doc conflict toward the stricter reading via a new ADR
(this one) and sending a documented follow-up to Freedom House. Full
transcript in `decisionlog.md`, 2026-07-25.

## What would trigger a revisit

- **If Freedom House replies with permission** — the tiered split for
  their content specifically can be lifted; re-run the release build with
  their chunks moved to the full-text tier. Access Now's status is
  independent and wouldn't change with a Freedom House reply.
- **If a similar scope-narrowing is found in any other derived summary of
  a licensing/governance document** — fix it the same way (stricter
  reading governs), and consider whether `PROJECT_CONTINUITY.md`'s own
  drafting process needs a stated rule against paraphrasing governance
  constraints instead of quoting them.
- **If `rehydrate.py` turns out not to reliably reproduce identical chunk
  hashes** (e.g., if a source document has been edited or removed
  upstream since acquisition) — that's a real reproducibility gap to
  disclose explicitly in the release notes, not silently work around.
