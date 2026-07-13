# ADR-0001: Disclose English-Only Filtering as a Non-Neutral Scope Limitation

**Status:** Accepted, 2026-07-11.

## Context

The frozen v1.0 architecture's structural validation stage (`validate.py`)
automatically rejects any acquired document that isn't detected as English.
This appears in the document's "What Is Explicitly Out of Scope" list
alongside "Multi-language support," presented with the same weight as
purely mechanical checks like minimum word count or duplicate detection.

That framing is misleading. Word-count and duplicate checks clean up
low-value files without changing what the corpus is *about*. The
English-only filter does change what the corpus is about: it determines
whose documentation gets included before a human ever reviews anything. The
five target countries (Kenya, Uganda, Tanzania, Ethiopia, Rwanda) have real
digital-rights and shutdown documentation produced in Swahili, Amharic, and
other local languages — often from grassroots or locally-based sources
closest to an actual incident. The four v1 source organizations (OONI,
Access Now, CIPESA, Freedom House) are all internationally-facing and
publish primarily in English. An English-only filter therefore doesn't just
lose "some documents" at random — it systematically favors the
internationally-facing account of events over the locally-sourced one,
every time, across the whole corpus.

This was identified during an architecture review on 2026-07-11 (Claude,
with Sam) and independently confirmed via an Opus advisor consult, which
ranked it "nearly as important as" the license/ToS gap (ADR-worthy, not a
cosmetic fix) and specifically recommended it be stated as "an
acknowledged, versioned limitation," not left as an unremarked technical
non-goal.

## Decision

1. Multi-language support remains out of scope for v1 — this ADR does not
   change that. Building multi-language ingestion is a real scope
   expansion with its own cost, and nothing here argues it should happen
   now.
2. The architecture document is amended to explicitly disclose that
   English-only filtering is an intentional but non-neutral limitation,
   likely under-representing grassroots and local-language documentation
   relative to internationally-facing English reporting from the same four
   organizations. This disclosure is added to the "What Is Explicitly Out
   of Scope" section, immediately following the existing scope items, with
   a reference to this ADR.
3. This is flagged as a requirement for later modules (not built now, since
   the generation layer doesn't exist yet): when the assistant answers a
   question where local-language sources plausibly exist but aren't in the
   corpus, it should be able to say so, the same way it's already required
   to flag thin or contradictory evidence. Tracked in
   `PROJECT_CONTINUITY.md` so it isn't lost between now and whenever the
   generation layer is built.
4. Per the architecture's own change-management rule, the document version
   is incremented (1.0 → 1.1) and both the header and footer version lines
   are updated with a reference to this ADR.

## Consequences

- No corpus contents change. This ADR is a disclosure/documentation fix,
  not a pipeline change — `validate.py`'s behavior is unchanged.
- Anyone reading the architecture doc going forward sees the limitation
  stated plainly instead of buried in a bullet list that implies it's
  inconsequential.
- Creates a forward obligation on the future generation layer (a
  disclaimer capability) that doesn't exist yet and isn't being built by
  this ADR — it's a noted requirement, tracked in continuity docs, not a
  new deliverable.
- Sets the template for how this project's first real ADR looks and reads
  — subsequent ADRs (e.g., the pending Freedom House licensing decision,
  see `docs/licensing.md`) should follow the same Context/Decision/
  Consequences/Opus-consult shape.

## Opus consult

Consulted 2026-07-11 as part of the broader architecture review (not a
second, ADR-specific round — the original consult already evaluated this
exact issue on its merits and ranked it ADR-worthy). Opus's framing,
adopted directly into the Decision section above: state it as "an
acknowledged, versioned limitation," not a silent non-goal. No conflict
between Opus's recommendation and the primary reviewer's (Claude's)
analysis — both converged on disclosure-not-scope-change as the right fix.

## What would trigger a revisit

If multi-language ingestion is ever seriously considered for a future
version, this ADR (and the disclosure language it introduces) should be
revisited — the limitation it documents would no longer be true, and the
architecture's own out-of-scope list would need a real update, not just a
disclosure note.
