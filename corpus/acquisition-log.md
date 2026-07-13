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

## accessnow-africa-2023-keepiton-shutdowns — Included

**Reviewed:** 2026-07-13. **Automated checks:** Tier 1 passed, Tier 2 clean (English, 25,491 words, no near-duplicates).

**Topic relevance:** Clean include. Continent-wide report whose core subject is documenting internet shutdowns, explicitly including country-by-country findings for all five target countries within the 2022-2025 window.

**Coverage contribution:** First Access Now document in the corpus — new organization, no existing entry to be a near-duplicate of.

**Decision: Included.**

## accessnow-africa-2024-keepiton-shutdowns — Included

**Reviewed:** 2026-07-13. **Automated checks:** Tier 1 passed, Tier 2 clean (English, 9,286 words, no near-duplicates).

**Topic relevance:** Clean include. Documents Kenya's mid-2024 protest-related shutdown and its connectivity spillover into Rwanda, plus continued Ethiopia and Uganda restrictions — squarely on-topic, within window.

**Coverage contribution:** Overlaps in period with this corpus's CIPESA 2024 entry and the Freedom House 2024 country chapters — a genuine cross-organizational account of the same general period, exactly the kind of comparison the architecture's own research questions call for, not duplication (confirmed non-near-duplicate by SimHash, distance well above threshold).

**Decision: Included.**

## cipesa-africa-2024-sifa-elections — Included

**Reviewed:** 2026-07-13. **Automated checks:** Tier 1 passed, Tier 2 clean (English, 30,247 words, no near-duplicates).

**Topic relevance:** Clean include. Examines technology's role (enabling and repressive) in Africa's 2024 elections, explicitly connecting to censorship and digital rights themes; countries-covered claim not independently verified per-country (see corpus/sources/cipesa.yaml note) but topic keyword hint and word count both support genuine on-topic content.

**Coverage contribution:** First CIPESA document in the corpus; overlapping 2024 period with the Access Now entry above — different organizational methodology and framing (elections/technology lens vs. shutdown-tracking).

**Decision: Included.**

## cipesa-africa-2025-sifa-ai — Included

**Reviewed:** 2026-07-13. **Automated checks:** Tier 1 passed, Tier 2 clean (English, 29,857 words, no near-duplicates).

**Topic relevance:** Include, slightly less direct than this corpus's other entries — core subject is AI's implications for digital democracy, not internet shutdowns directly, but CIPESA explicitly frames AI-driven content moderation, surveillance, and disinformation as censorship-adjacent risks, which keeps it inside the digital-rights scope rather than a topic drift. Confirmed via direct PDF read that Ethiopia, Kenya, Rwanda, and Uganda are covered by name (not Tanzania — see corpus/sources/cipesa.yaml, `countries` field corrected accordingly).

**Coverage contribution:** New 2025 period, not otherwise covered in the corpus except partially by the OONI Tanzania document; different topical angle (AI/disinformation) from every other entry — genuine coverage contribution, not overlap.

**Decision: Included.**

## freedomhouse-ke-2024-fotn — Included

**Reviewed:** 2026-07-13. **Automated checks:** Tier 1 passed, Tier 2 clean (English, 14,084 words, no near-duplicates).

**Topic relevance:** Clean include. Country-specific Freedom on the Net chapter — internet freedom is its entire subject.

**Coverage contribution:** Kenya is already covered by two OONI documents and the Access Now reports, but Freedom House's structural/legal-analysis lens (arrests, content law, platform regulation) is a genuinely different organizational account from OONI's technical network measurement or Access Now's shutdown-tracking — textbook cross-org coverage contribution per the rubric, not duplication.

**Rights/licensing note (rubric Section 3):** Freedom House content is permission-gated per docs/licensing.md. Permission request sent 2026-07-13, awaiting response (see docs/PROJECT_CONTINUITY.md Section 7). This document is for internal course-project use only; no CLIO-facing redistribution until permission is confirmed.

**Decision: Included.**

## freedomhouse-ug-2024-fotn — Included

**Reviewed:** 2026-07-13. **Automated checks:** Tier 1 passed, Tier 2 clean (English, 12,564 words, no near-duplicates).

**Topic relevance:** Clean include.

**Coverage contribution:** First Uganda-specific document in the corpus (every other Uganda mention so far is inside a continent-wide report) — fills a real per-country gap. Notably reports no new connectivity restrictions in this coverage window, which usefully complements rather than duplicates Access Now's separate note of Uganda's continuing Facebook block — two orgs' accounts of the same period genuinely diverging, not overlapping.

**Rights/licensing note:** Same as above — permission pending, internal use only.

**Decision: Included.**

## freedomhouse-et-2024-fotn — Included

**Reviewed:** 2026-07-13. **Automated checks:** Tier 1 passed, Tier 2 clean (English, 14,308 words, no near-duplicates).

**Topic relevance:** Clean include. Lowest-scored ("Not Free") country in this edition; conflict-related connectivity disruption and content-removal law squarely on-topic.

**Coverage contribution:** First Ethiopia-specific document in the corpus; direct topical overlap with this corpus's network-interference-during-unrest theme (OONI, Access Now) from a structural/legal angle rather than technical measurement.

**Rights/licensing note:** Same as above — permission pending, internal use only.

**Decision: Included.**

## freedomhouse-rw-2024-fotn — Included

**Reviewed:** 2026-07-13. **Automated checks:** Tier 1 passed, Tier 2 clean (English, 12,058 words, no near-duplicates).

**Topic relevance:** Clean include. Declining internet freedom, progovernment online harassment, self-censorship ahead of the July 2024 election — squarely on-topic.

**Coverage contribution:** First Rwanda-specific document in the corpus; complements Access Now's brief note of Rwanda's connectivity spillover from Kenya's 2024 protests with a full country-level account.

**Rights/licensing note:** Same as above — permission pending, internal use only.

**Decision: Included.**

## ooni-ke-2025-telegram-kcse-blocking — Included

**Reviewed:** 2026-07-13. **Automated checks:** Tier 1 passed, Tier 2 clean (English, 8,568 words, no near-duplicates).

**Topic relevance:** Clean include. Technical measurement evidence of Telegram blocking during Kenya's 2023/2024 KCSE exams — squarely within OONI's approved-source, technical-measurement scope, Kenya is a target country, within window.

**Coverage contribution:** Second OONI document in the corpus. Topically distinct from the existing Tanzania document (exam-integrity-motivated app blocking vs. platform blocking during civil unrest) and from Kenya's other corpus entries (Access Now/Freedom House cover Kenya's protest-related shutdown, not the exam-blocking incident) — genuine new ground, not a near-duplicate (confirmed by SimHash).

**Decision: Included.**
