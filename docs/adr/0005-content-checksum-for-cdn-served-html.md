# ADR-0005: Split Checksum Into Raw-Bytes and Extracted-Content, for CDN-Served HTML Sources

**Status:** Accepted, 2026-07-20.

## Context

`acquire.py`'s integrity design, as built, was intended to do one job:
guarantee an immutable raw file, verified byte-for-byte on every run, so
nobody accidentally trusts a corrupted or bot-challenge-page copy of a
source document. In practice it was only ever doing half of that. Its
`[skip]` path (a local file already present) compares the file **to its own
previously-recorded hash**, never to a fresh live fetch — so it has only ever
verified "the saved copy hasn't rotted on disk," not "the saved copy still
matches what the source currently serves." That gap was invisible until
today, because nothing had been re-fetched since the walking-skeleton and
10-document milestones (2026-07-13).

It became visible attempting to acquire 8 new Freedom House documents
(2026-07-20). All 8 failed checksum verification — not intermittently,
structurally. Diagnosis: fetching the identical URL twice in immediate
succession, same process, same headers, produces two different SHA-256
hashes every time, at identical byte length. A line diff of the two ~2000-line
response bodies shows exactly 3 differing lines, all Cloudflare-injected, none
of them page content:

- `/cdn-cgi/l/email-protection#...` — Cloudflare's email-obfuscation feature
  XOR-encodes any `mailto:`-adjacent email address with a random per-request
  key, decoded client-side via JS. The underlying email is constant; the
  encoded string differs every response.
- `window.__CF$cv$params={r:'...',t:'...'}` — a Cloudflare challenge-platform
  verification token, randomized per response, injected into an inline
  `<script>` even on a page that returns a clean 200 with no visible
  challenge.

Confirmed this isn't specific to the 2023 Kenya page or to this fetch: the
same two markers are present in the 4 Freedom House 2024 documents already
acquired and included in the corpus (2026-07-13). Their checksums have only
"held" because they've never been live-refetched — per this finding, a fresh
download of any of those 4 today would almost certainly fail the same way.

This is a known, general class of problem — checksumming a non-deterministic
serialization — with an established general answer (canonicalize before
hashing; the same idea behind XML C14N or JSON Canonicalization Scheme), not
something specific to Freedom House or requiring a bespoke solution.

**Separately, and just as important:** no version of the checksum design,
old or new, ever guarded against the actual original threat this project
cared about first — a bot-challenge page silently saved as if it were real
content. A checksum only proves consistency with whatever was saved first;
if that first save was a challenge page, any checksum scheme happily locks
in a stable hash of garbage forever. `acquire.py` already has a partial guard
for this (`looks_like_declared_format()`'s negative check — known
challenge-phrase absence, for both PDF magic bytes and HTML content) but it
has never asserted anything positive about the content being real.

**Correction, same day, before any code was written:** the decision below
originally said the raw-bytes checksum's *behavior* would stay unchanged.
That's incomplete — it overlooked that `acquire.py`'s download path gates
the *first* acquisition on matching a pre-declared hash, not just future
re-runs (`if actual_sha256 != expected_sha256: raise AcquisitionFailure`,
in `acquire_document()`). For a source with no stable raw bytes at all,
there is no correct value to pre-declare, so that gate can never pass on
day one either — not just on a later re-verify. Caught while drafting the
implementation prompt, before Claude Code touched anything. Decision #1
below is written to reflect the corrected understanding, not the original.

## Decision

**Split the single checksum into two, with two different jobs, rather than
trying to make one hash do both:**

1. **Raw-bytes checksum (`sha256`, existing field): unchanged for stable
   sources, trust-on-first-use for declared-volatile ones.** For every
   source whose raw bytes are actually stable (PDFs, OONI's manually-saved
   HTML — the overwhelming majority of documents), nothing changes: a
   pre-declared hash still gates acquisition and still verifies the local
   file on every re-run.

   For a source explicitly marked volatile (new per-org YAML field,
   `raw_bytes_stable: false` — set on `freedomhouse.yaml` only),
   `acquire.py`'s download path stops gating the *first* acquisition on a
   pre-declared hash, since no correct value could ever be pre-declared for
   bytes that are never the same twice. Instead: download once, save the
   file, and record whatever hash was actually obtained as the new
   baseline (written back into `corpus/sources/{org}.yaml`, replacing
   `REPLACE_ME` — same bootstrap shape as before, just recorded rather than
   verified on this specific first run). From the second run onward, that
   recorded value verifies the local file hasn't rotted on disk, exactly
   as the mechanism always did for stable sources — it just can no longer
   also serve as evidence the live source hasn't changed, which per the
   Context section it was never actually proving anyway.

2. **New: content checksum (`content_sha256`, new field), computed by
   `extract.py`, not `acquire.py`.** A SHA-256 of the canonicalized extracted
   text (the same text `extract.py` already produces for `chunk.py`), with
   the extractor and its version pinned in the metadata so a future extractor
   upgrade doesn't get misread as source drift. Because extraction already
   strips scripts, links, and markup, this checksum is naturally immune to
   Cloudflare's injected tokens (and to whatever similar CDN adds next — this
   is the canonicalize-then-hash fix, not a patch for these two specific
   markers). Same bootstrap pattern as the existing `sha256` field: starts
   `REPLACE_ME`/absent for a first-time document, gets filled in from the
   first real extraction, verified on every extraction after that. A
   mismatch here is a genuine, meaningful signal — the source's actual
   content changed — not corruption.

   **Scope: only required for sources known to inject non-deterministic
   content into raw bytes.** Not a blanket new field on every document.
   Access Now/CIPESA PDFs and OONI's manually browser-saved HTML don't have
   this problem — their raw bytes are already stable — so `content_sha256`
   stays optional/absent for those rather than adding ceremony where it
   solves nothing. `corpus/sources/freedomhouse.yaml` is the one file where
   it's required for every entry, going forward.

3. **Strengthen the existing acquire-time content check
   (`looks_like_declared_format()` for HTML) with a positive assertion, not
   just the existing negative one.** In addition to the current
   challenge-phrase absence check, also confirm the document's own declared
   `title` (already present in every `corpus/sources/*.yaml` entry) actually
   appears, in some recognizable form, in the fetched content. This is the
   actual guard against the original threat (a challenge page silently
   trusted) — independent of either checksum, and it stays exactly where
   `looks_like_declared_format()` already lives, rather than introducing a
   parallel mechanism.

4. **One-time confirmation pass on the 4 already-included Freedom House 2024
   documents**, using the strengthened check above against their existing
   saved raw files (already on disk — this is a confirmatory read, not a
   re-acquisition, no re-download, no `corpus_version` change). Purpose:
   confirm they're real content, not to cast active doubt on them — nothing
   in `corpus/acquisition-log.md`'s existing review of those 4 suggests a
   problem, this just closes the loop now that a stronger check exists.

**Rejected: regex-stripping the two specific known markers before hashing.**
Correctly identified by the Opus consult as whack-a-mole — an unbounded,
ever-growing blocklist as Cloudflare (or any other CDN) adds new injection
points over time. The canonicalize-via-extraction approach in decision #2
is immune to markers that don't exist yet, not just the two found today.

**Rejected (for now): OONI-style, no live-reverify, one-time manual save
only.** Considered as a fallback if the two-checksum approach were too much
implementation work, but it wasn't — `extract.py` already produces the text
that decision #2's hash is computed over, so this is a smaller addition than
it first looked. Dropping live re-verification entirely would also lose
future drift-detection value for a source (Freedom House) this corpus
expects to keep growing.

## Consequences

- `src/ingestion/acquire.py`: no behavior change to its existing checksum
  logic, only a documentation correction (module docstring and the
  `sha256_of()`/checksum-comparison code comments now state plainly that
  this check verifies local-disk integrity, not live-source fidelity).
  `looks_like_declared_format()` gains the positive title-presence check
  for HTML, alongside its existing negative challenge-phrase check.
- `src/ingestion/extract.py`: gains a new responsibility — compute
  `content_sha256` over canonicalized extracted text, compare against a
  declared value if present, bootstrap (record, don't compare) if absent/
  `REPLACE_ME`. This is new code, not written yet.
- `corpus/sources/freedomhouse.yaml`: every entry gains a `content_sha256`
  field (starts `REPLACE_ME` for the 8 pending documents; the 4 existing
  2024 documents get it backfilled during the confirmation pass in decision
  #4). Other orgs' YAML files are unaffected — the field is source-specific,
  not corpus-wide.
- `docs/ingestion-design.md`'s pipeline diagram/reference needs updating to
  show the content-checksum step living in `extract.py`, not `acquire.py`.
  Not yet done — follow-up task, tracked in
  `docs/PROJECT_CONTINUITY.md` Section 7.
- Architecture document version increments v1.4 → v1.5 (this project's
  fifth ADR).
- The 8-document Freedom House batch this ADR was prompted by stays blocked
  on implementation, not un-blocked by this decision alone — `extract.py`'s
  new logic has to actually be written and run before those 8 can be
  acquired for real.

## Opus consult

Consulted 2026-07-20, briefed with the actual diff evidence (the two
Cloudflare markers, the confirmed reproducibility of the mismatch, the
retroactive finding about the 4 existing documents) and four candidate
options. Recommendation: split the checksum (this ADR's decision #1+#2,
ranked first), OONI-style no-reverify as an acceptable fallback only if the
split approach were too costly (ranked second, not chosen — see
Consequences), regex-stripping specific markers rejected as whack-a-mole
(ranked third, rejected as stated above). Independently flagged the
positive-content-assertion gap (decision #3) as the real guard against the
original bot-challenge threat, which neither the original design nor the
split-checksum fix addresses on its own — this project's design adopts that
addition as stated. No divergence between the consult's recommendation and
what's adopted here; nothing to surface as a conflict.

## What would trigger a revisit

- If a future source (beyond Freedom House) turns out to serve
  non-deterministic raw bytes for a reason canonicalized-text hashing
  *doesn't* neutralize (e.g., the actual visible article content itself
  varies per-request, not just markup/script injection around it) — that's
  a genuinely different problem than this ADR solves, and would need its
  own design pass, not an assumption that decision #2 generalizes
  automatically.
- If `content_sha256` mismatches start appearing routinely for Freedom
  House documents on later re-runs (as opposed to the one-time bootstrap
  fill) — that's a real content-drift signal and should route to a human
  via the existing Tier 2 pattern (ADR-0002), not be silently
  auto-accepted or auto-rejected.
- If the positive title-presence check (decision #3) produces false
  negatives in practice (e.g., a title with special characters that don't
  survive HTML entity decoding cleanly) — loosen the match method (fuzzy/
  substring rather than exact) before loosening the check's intent.
