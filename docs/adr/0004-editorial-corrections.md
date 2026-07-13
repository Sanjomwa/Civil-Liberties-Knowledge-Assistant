# ADR-0004: Editorial Corrections (Date Inconsistency, Dead Reference)

**Status:** Accepted, 2026-07-11.

## Context

Two small items from the architecture review, neither a design decision —
both are the doc failing to say what it already means. Bundled into one
lightweight ADR rather than two, since the architecture's own change
process technically requires any edit to be recorded, and a full
Context/Decision/Consequences record for a typo would be over-engineering
for what it is. This is closer to a changelog entry than a design record.

**Item 7 — date inconsistency.** The document header states "Frozen for
implementation, Date: June 2026." The illustrative example inside the
metadata JSON schema (`extraction_date`, `chunking_date`) and the
reproducibility section's citation example both used "2025-06-15" / "June
2025" — a full year off the doc's own stated freeze date. Likely leftover
from an earlier draft written before the freeze date was set. Since these
are illustrative placeholder values (the whole `ooni-ke-2023-election-report`
example is hypothetical, not a real acquired document), the fix is just
making the example internally consistent with the doc's own stated
timeline.

**Item 8 — dead reference.** `docker-compose.yml` appears in the repository
structure diagram but is never mentioned or justified anywhere else in the
document. A reader has no way to know whether it's meant for pipeline
orchestration (which would contradict the architecture's explicit "no
orchestration framework" principle) or something else entirely.

## Decision

**Item 7:** update the two illustrative example dates
(`extraction_date`, `chunking_date`) from `2025-06-15` to `2026-06-15`, and
the reproducibility section's citation example from "June 2025" to "June
2026" — consistent with the document's own stated freeze date.

**Item 8:** add one clarifying sentence after the repository structure
diagram: `docker-compose.yml` pins the runtime environment (Python version,
system dependencies) for reproducibility — the same concern already named
in the "Reproducibility" section's "pinned dependencies" mechanism — and is
explicitly not a pipeline orchestration framework, consistent with the
"sequential and simple" principle stated elsewhere in the document.

## Consequences

- No behavioral or design change. Purely removes two points of confusion
  for a future reader (or a returning Sam, months from now).
- Document version increments 1.3 → 1.4.

## Opus consult

Not consulted — both items are corrections, not decisions, and fall below
this project's threshold for a mandatory advisor checkpoint (that
threshold is for decisions that deviate from the frozen design, not for
fixing an internal inconsistency in the prose itself).

## What would trigger a revisit

None expected — these are corrections, not open design questions.
