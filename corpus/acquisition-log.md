# Acquisition Log

Every document encountered during corpus construction, included or not,
with the reason. Tier 1 exclusions below are written automatically by
validate.py — they're facts, not judgments. Inclusion/exclusion after a
Tier 2 flag or the semantic review is a human call, added by hand per
docs/corpus-inclusion-rubric.md.

---

## ooni-tz-2025-x-platform-blocking — Included

**Organization:** OONI
**Reviewed:** 2026-07-13
**Automated checks:** Tier 1 passed (extraction succeeded, checksum verified).
Tier 2 clean (English, 4445 words, no near-duplicates — first document in
the corpus, nothing yet to duplicate against).

**Topic relevance (rubric Section 1):** Clean include, not borderline. Title
and full content are squarely about a single dated network-interference
event — the blocking of the X platform in Tanzania — in a target country
(Tanzania) within the 2022–2025 window. This is exactly the "title/primary
framing is about censorship/network interference in a target country"
include case, not a background-mention exclusion.

**Coverage contribution (rubric Section 2):** Clean include. First document
in the corpus, so it trivially covers a country/year/organization
combination ("TZ", 2025, OONI) not yet represented by anything else — there
is nothing yet to be a near-duplicate of.

**Rights/licensing check (rubric Section 3):** N/A — source is OONI, not
Freedom House.

**Acquisition note:** worth recording here since it shaped which URL ended
up in corpus/sources/ooni.yaml — this document went through two false
starts before landing on a verified real copy. The original target
(ooni.org/documents/.../*.pdf) sat behind a JS bot challenge; the HTML
companion post at ooni.org/post/2025-tanzania-blocked-twitter/ turned out,
under repeated automated requests, to sit behind a *different* challenge
page. The version actually in data/raw/ was obtained by Sam via a real
browser (Save As → Webpage, HTML Only) and verified by content — 7024 raw
words, no known challenge phrases, 4445 words after extraction, opening
paragraph matching the original PDF's — not just by checksum match, since a
checksum matching a wrong (challenge-page) file was exactly what happened
twice before this. See decisionlog.md (2026-07-13) for the full sequence,
including the Opus and Fable consults that shaped the manual-acquisition
design.

**Decision: Included.**
