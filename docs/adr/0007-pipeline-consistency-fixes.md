# ADR-0007: Pipeline Consistency Fixes (Validation Data Flow, Content-Drift Routing, Reconciliation, Derived-Checksum Storage)

**Status:** Accepted, 2026-07-20.

## Context

An end-of-ingestion-phase independent review (two models, Opus and Fable,
briefed identically and run in parallel with no cross-contamination —
full method in `decisionlog.md`, 2026-07-20) converged on four related
findings, all the same class of problem: a place where the pipeline's
actual data flow has quietly drifted from what its own prior ADRs already
say it should do, or where two parts of the pipeline independently
compute or store the same fact instead of one part being the single
source of truth for it.

**Finding 1 — `metadata.py` re-implements validation instead of consuming
it.** `validate.py`'s `tier2_checks()` already computes language
detection and word count as part of its Tier 2 routing (ADR-0002).
`metadata.py`'s `build_derived()` independently re-runs `detect_langs()`
and re-applies the 500-word threshold to set its own
`validation_status`/`validation_warnings` fields. These are two separate
computations of the same fact, with no guarantee they agree — and
`metadata.py`'s version is the one written into the corpus's permanent
metadata record, not `validate.py`'s.

**Finding 2 — content-drift detection doesn't do what ADR-0005 already
said it would.** ADR-0005's own text states a `content_sha256` mismatch
"should route to a human via the existing Tier 2 pattern (ADR-0002), not
be silently auto-accepted or auto-rejected." The actual code
(`extract.py`'s `check_content_checksum()`) prints a `[content-drift]`
warning to stderr and continues — it never reaches
`corpus/acquisition-log.md`, and `validate.py` never looks at
`content_sha256` at all. This isn't a new decision; it's finishing one
already made and only partially built.

**Finding 3 — no reconciliation check across where corpus state lives.**
Four (now five, see Finding 4) different artifacts each drive a
different pipeline stage: `corpus/sources/*.yaml` (declared),
`corpus/manifest.csv` (acquired), `corpus/acquisition-log.md`'s
`## doc_id — Included` headings (human decision, parsed by
`INCLUDED_HEADING_RE`), and `data/metadata/*.json` (what `chunk.py`
actually processes). Nothing checks these agree. Two concrete failure
modes were identified independently by the two reviewing models: (a) a
hand-edit typo in the log's required em-dash — `## doc_id — Included`
— silently drops a document from metadata generation with no error,
since `INCLUDED_HEADING_RE`'s regex just won't match it; (b)
`acquire.py`'s `main()` regenerates `corpus/manifest.csv` from only the
current run's successful rows, so a document that acquired successfully
in an earlier run but hits a transient failure on a later rerun (e.g., a
network blip on a re-verification) silently disappears from the
manifest while its `data/metadata/{doc_id}.json` and
`data/chunks/{doc_id}/` persist untouched from the earlier run — `chunk.py`
would keep processing a document `acquire.py` no longer considers
acquired.

**Finding 4 — derived checksums are written into the declared-only
source YAML.** `write_yaml_field()` (in `acquire.py`) is a regex-based
in-place editor that surgically replaces one field's value inside a
hand-authored `corpus/sources/{org}.yaml` document block, built
specifically to preserve every comment and the file's hand-formatting
(a full `yaml.safe_load`/`yaml.dump` round-trip would discard both).
Both reviewing models flagged this as the single most fragile code in
the pipeline. But on closer inspection (see Decision below), not
everything it writes is actually the same *kind* of data — some of it
is legitimately declared, some is purely derived, and the fix needs to
distinguish the two rather than relocate everything uniformly.

An Opus consult (2026-07-20, briefed with the precise before/after
mechanics of both this fix and ADR-0008's, see that ADR for the shared
consult transcript) was run before finalizing this ADR's decision, since
Finding 4 amends a mechanism ADR-0005 itself specified.

## Decision

### Finding 1 fix: validate.py becomes the single source, metadata.py reads it

`validate.py` gains a new output artifact, `corpus/validation-results.json`
— a machine-readable, per-`doc_id` record of exactly what Tier 2 computed
(`word_count`, `language`, `language_ok`, `length_ok`, `near_duplicates`),
written alongside the existing human-readable
`corpus/validation-report.md` (which stays — it's still the actual
review artifact a human reads). `metadata.py`'s `build_derived()` reads
this file and copies the relevant fields into `validation_status`/
`validation_warnings` instead of independently re-running `detect_langs()`
and re-checking word count. If a `doc_id` marked Included in
`acquisition-log.md` has no corresponding entry in
`validation-results.json`, `metadata.py` fails loudly (same failure
posture as its existing "declared but not marked Included" check) rather
than silently falling back to recomputing — a missing entry means
`validate.py` was never run against this document post-acquisition,
which is itself worth surfacing, not smoothing over.

### Finding 2 fix: content-drift actually routes to Tier 2

`check_content_checksum()` in `extract.py`, on a mismatch, now also
appends an entry to `corpus/acquisition-log.md` (same append-only
pattern as `append_acquisition_log_failure`, a new
`append_content_drift_flag()` doing the equivalent for this case,
prefixed distinctly, e.g. `- **{doc_id}** — content-drift flagged
({date}): ...` so it's greppable separately from Tier 1 exclusions and
acquire failures) and, separately, `validate.py` now reads
`corpus/derived-checksums/{org}.json` (see Finding 4's fix) for any
declared `content_sha256` and includes a `content_drift` boolean in its
own Tier 2 output, surfaced in `validation-report.md` the same way a
near-duplicate flag is. This does not auto-exclude anything — per
ADR-0005's own stated design, it's a flag for human attention, exactly
like every other Tier 2 signal.

### Finding 3 fix: `reconcile.py`, a new standalone script

A new `src/ingestion/reconcile.py`, run on demand (not wired into
`pipeline.py`'s automatic stages — like `check_drift.py`, this is a
diagnostic check a human runs deliberately, not a gate that blocks
normal operation). Checks, and reports any disagreement rather than
silently trusting any one source:
- Every `doc_id` in `corpus/sources/*.yaml` with a real (non-`REPLACE_ME`)
  `sha256` appears in `corpus/manifest.csv`, and vice versa.
- Every `doc_id` marked `## doc_id — Included` in `acquisition-log.md`
  has a corresponding `data/metadata/{doc_id}.json`, and vice versa (a
  metadata file with no matching Included heading means something was
  removed from the log after metadata was generated — a real drift
  case, not just a formatting slip).
- Every `doc_id` with a `content_sha256` or Freedom-House-style
  trust-on-first-use `sha256` declared in
  `corpus/derived-checksums/{org}.json` (Finding 4) has a matching
  `doc_id` in the corresponding `corpus/sources/{org}.yaml` — the split
  introduced by Finding 4's fix creates exactly this same class of
  two-file-agreement problem, one level down, and this check covers it
  in the same pass rather than needing its own separate tool (per the
  Opus consult's specific point on this).
- Every `doc_id` with chunks in `data/chunks/{doc_id}/` has a
  `data/metadata/{doc_id}.json` with a matching `chunking.total_chunks`
  count, and vice versa.

Exit code non-zero if anything disagrees, with a specific human-readable
report of exactly which `doc_id` and which two sources disagreed —
matching this project's own standing preference (see `sync.sh`'s own
retrospective, `decisionlog.md` 2026-07-20) for surfacing an
unanticipated category of drift rather than only patching the specific
instance already found.

### Finding 4 fix: split by *kind* of data, not blanket relocation

Adopting the Opus consult's core framing directly: the real
discriminator isn't "computed vs. hand-typed," it's **whether a human
ever verifies the value and whether it gates anything security-relevant.**

- **Stable-org `sha256` (Access Now, CIPESA, OONI) stays exactly where
  it is, in `corpus/sources/{org}.yaml`, written via
  `write_yaml_field()` exactly as today.** This value is genuinely
  declared data — discovered once, empirically, then serves as a
  security-relevant pre-declared gate for every subsequent download
  (`acquire_document()`'s `if actual_sha256 != expected_sha256: raise
  AcquisitionFailure`). Moving it to a second file would mean the gate
  check has to look somewhere other than the document's own declaration
  for what it's gating against, which doesn't improve anything and adds
  an extra file to keep in sync for no benefit.

- **Freedom House's trust-on-first-use `sha256`, and `content_sha256`
  for every document that has one, move to a new generated file,
  `corpus/derived-checksums/{org}.json`** (one file per org, mirroring
  the existing per-org YAML structure — adopted from the consult's
  specific recommendation over a single corpus-wide file, since it
  keeps reconciliation per-org and matches the symmetry a reader of this
  repo already expects from the YAML layout). Plain JSON writes, no
  regex surgery, since this file is machine-owned end to end and has no
  comments to preserve. `acquire.py`'s trust-on-first-use bootstrap path
  and `extract.py`'s `check_content_checksum()` both write here instead
  of calling `write_yaml_field()`.

**Deviation from the consult's suggestion, made deliberately and
recorded rather than silently adopted:** the consult additionally
suggested trying to eliminate `write_yaml_field()` entirely, by having
even the stable-org *first* hash discovery be script-printed and
human-pasted rather than script-written. Considered and **not adopted**:
this project's actual established operational workflow (documented
extensively across this session's `decisionlog.md` entries, e.g. the
CIPESA and OONI batch acquisitions) depends on `acquire.py` auto-filling
multiple `REPLACE_ME` placeholders in a single run when Claude Code
acquires a batch of newly-declared documents — converting that to a
manual copy-paste step per document would be real, recurring workflow
friction for a course project with a bus factor of one, in exchange for
a security property the design doesn't actually gain: the model is
already effectively trust-on-first-use for the *first* download of any
document regardless of who types the hash in afterward (nothing
verifies that first download against an independent source either way).
`write_yaml_field()` therefore survives, scoped to exactly one
remaining caller (the stable-org first-hash write) instead of three —
a real reduction in its blast radius, just not full elimination.

## Consequences

- New artifacts: `corpus/validation-results.json`,
  `corpus/derived-checksums/{org}.json` (one per org that has any
  derived checksums — currently Freedom House only, though the
  mechanism is general), `src/ingestion/reconcile.py`.
- `metadata.py`'s `build_derived()` no longer imports or calls
  `langdetect` directly — it reads `validate.py`'s output instead. Its
  dependency on `langdetect` is removed; `validate.py` remains the only
  module that imports it.
- `write_yaml_field()`'s surface area shrinks from three call sites
  (stable-org first hash, Freedom-House trust-on-first-use hash,
  `content_sha256` bootstrap) to one.
- `docs/ingestion-design.md`'s pipeline diagram and per-stage
  descriptions need updating to show the new artifacts and the
  corrected data-flow direction (metadata.py reads from validate.py's
  output, not from raw text a second time). Tracked as a follow-up in
  this same work session, not a separate deferred item.
- No change to any already-Included document's inclusion status, and no
  change to chunk *counts* — this ADR fixes data-flow and storage
  bookkeeping, not chunking behavior. (Contrast with ADR-0008, which
  does add new fields to chunk records, though also without changing
  chunk counts.)
- Architecture document version increments v1.6 → v1.7.

## Opus consult

Consulted 2026-07-20, briefed with the precise proposed mechanics for
both this ADR and ADR-0008 in one combined consult (both are pipeline
fixes prompted by the same review event, briefed together for
efficiency — see `decisionlog.md` for the full transcript). On Finding
4 specifically: confirmed the declared-vs-derived discriminator is the
right cut; recommended additionally trying to eliminate
`write_yaml_field()` entirely (not adopted, see the deviation note
above — surfaced rather than silently declined, per this project's
standing advisor-treatment rule); flagged that splitting checksum
storage across two files creates its own two-file-agreement problem,
which is folded into `reconcile.py` (Finding 3's fix) rather than
needing a separate tool; recommended per-org derived-checksum files
over one corpus-wide file, adopted directly.

## What would trigger a revisit

- If a fifth or sixth org is ever added (v1.1 scope opening, Netblocks/
  Citizen Lab) and turns out to also need trust-on-first-use or
  content-checksum treatment, confirm the per-org
  `derived-checksums/{org}.json` pattern still holds rather than
  assuming it generalizes automatically.
- If `reconcile.py` ever needs to run as a blocking gate rather than an
  on-demand diagnostic (e.g., if drift starts happening often enough
  that catching it after the fact is no longer good enough) — that's a
  bigger process change than this ADR makes, deserving its own decision
  at that point.
- If `validation-results.json` and `validation-report.md` ever need to
  carry different information (right now they're two representations
  of the same underlying computation) — if they start to diverge in
  purpose, revisit whether one machine-readable file is still the right
  shape.
