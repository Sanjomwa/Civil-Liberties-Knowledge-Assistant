# ADR-0002: Tiered Routing for Structural Validation Failures

**Status:** Accepted, 2026-07-11.

## Context

The frozen v1.0 architecture states, in the `validate.py` module
description: "Documents do not advance to metadata until a human has
reviewed the semantic report. No document is silently excluded." That
sentence is only true of the semantic-review stage. The structural stage
(five automated checks, detailed in the "Validation Detail" table) excludes
documents on its own, before any human sees them — the two stages were
being described as if governed by the same rule, and they aren't.

The five structural checks, per the architecture's own detail table
("Check | Method | Fail Condition"):

| Check | Method | Fail Condition |
|---|---|---|
| Extraction success | File exists in `processed/` and is non-empty | Empty or missing output file |
| File integrity | SHA-256 of raw file matches manifest | Hash mismatch |
| Language | `langdetect` on extracted text | Primary language is not English |
| Minimum length | Word count of extracted text | Under 500 words |
| Deterministic duplicates | Document fingerprint (SimHash) against existing corpus | Near-identical to an already-included document |

The initial proposed fix (from the broader architecture review) was binary:
route all structural failures to human review, or scope the "no silent
exclusion" claim to semantic exclusion only. Both are wrong. Routing a
checksum mismatch to a human is pure noise — it's an unambiguous fact.
Auto-excluding a real but short or unusually-flagged document without a
human ever seeing it is a real evidentiary loss for a project whose whole
premise is not smoothing over evidence.

**Correction made during this review, worth recording:** the initial
three-tier proposal (drafted with an Opus consult) classified "Deterministic
duplicates" as an unambiguous, fully-automated check, reasoning from the
architecture's own prose label ("deterministic... fingerprint comparison").
Reading the actual "Validation Detail" table — which hadn't been checked
directly in the first pass, since it's a table, not a paragraph, and was
missed by an earlier paragraph-only text extraction — showed the specified
method is **SimHash**, a similarity/near-duplicate hash, and the fail
condition is explicitly "near-identical," not "identical." That's a
threshold/similarity judgment wearing a name ("deterministic") that implies
more certainty than the method actually provides. The tiering below
reflects this correction, not the original assumption. Lesson: verify
against the primary-source table/detail, not the descriptive prose label,
before finalizing a technical classification — the same discipline this
project asks of its own evidence handling, applied to its own architecture
review.

## Decision

Apply one governing test: **surface to a human any exclusion driven by a
threshold or heuristic that could plausibly be wrong about a valuable
document; keep fully automated any exclusion driven by an unambiguous
fact.**

**Tier 1 — fully automated, excluded and logged, no human review:**
- Extraction success (file exists / is non-empty is a fact, not a judgment)
- File integrity (SHA-256 match/mismatch is a fact)

**Tier 2 — logged AND surfaced into the human-reviewed report, human
confirms before exclusion is final:**
- Language detection (`langdetect` is probabilistic and known to misfire on
  short or code-switched text — English/Swahili mixing is close to the norm
  for Kenyan and Tanzanian source documents, not an edge case, given this
  corpus's actual geographic scope)
- Minimum length (a 480-word official notice about a shutdown could be
  exactly the kind of document worth keeping despite being short)
- Deterministic duplicates (despite the name, the specified method is
  SimHash near-duplicate matching against the existing corpus — a
  similarity threshold, not an exact match; two legitimately different
  reports about related events could plausibly trigger it)

**Not a separate tier, but worth stating:** "extraction success" as
currently specified (file exists and is non-empty) would pass a document
with only 30 words of garbled text extracted from a scanned PDF. This isn't
a gap requiring new handling — that document gets caught by the Tier 2
minimum-length check regardless. No change needed here beyond noting it, so
a future maintainer doesn't mistake "extraction succeeded" for "extraction
was any good."

**The imprecise sentence is rewritten.** The `validate.py` module
description no longer claims uniform automation or a blanket "no document
is silently excluded." It states the tiering directly: automated exclusion
for unambiguous facts, human-confirmed exclusion for anything
threshold-based or judgment-based, semantic or structural.

No change to `corpus/acquisition-log.md`'s schema is needed — its existing
`status` (Found/Included/Excluded) and `exclusion_reason` fields already
accommodate logging a Tier 1 automatic exclusion the same way they'd log a
semantic one; this ADR is about routing (who decides), not about adding new
fields.

## Consequences

- No corpus contents change yet — no ingestion code exists. This changes
  what gets built when `validate.py` is written, not anything currently
  running.
- Slightly more manual review volume than the original design implied
  (language and length failures now reach a human), but only for the two
  checks most likely to wrongly exclude a legitimate document, not all
  five.
- The corrected duplicate-detection tiering means near-duplicate calls are
  now a human decision, which is directly useful input for
  `docs/corpus-inclusion-rubric.md` Section 2 (coverage contribution) — a document
  a human confirms as *not* a true duplicate is, by definition, adding
  coverage, and that reasoning should be logged the same way any other
  inclusion decision is.
- Document version increments 1.1 → 1.2 (this project's second ADR,
  following 0001).

## Opus consult

Consulted twice in this review's course. First pass validated that a
three-tier split (vs. the original binary framing) is the right shape, not
over-engineering, and specifically promoted language detection from
"arguably tier 2" to firmly tier 2, given the corpus's real bilingual risk.
That same first-pass consult assumed duplicate detection was exact-hash
based, reasoning from the architecture's prose alone — this was corrected
independently afterward by reading the actual "Validation Detail" table,
which specifies SimHash. The correction is Claude's, made after the Opus
consult, based on primary-source evidence (the table) the consult hadn't
been shown. Recorded per the project's own advisor-treatment rule: when
evidence and prior advice diverge, adapt and surface it, don't silently
pick a side — this entry is that surfacing.

## What would trigger a revisit

If `validate.py` is ever implemented with different concrete
methods than the table currently specifies (e.g., an exact-hash duplicate
check replacing SimHash, or a more robust language-ID model), the tiering
above should be re-evaluated against the same governing test, not assumed
to carry over unchanged.
