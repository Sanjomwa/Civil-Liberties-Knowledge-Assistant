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
- **freedomhouse-ke-2023-fotn** — acquire.py failure (2026-07-20): checksum mismatch: expected be52eeacf46c5f784fcb730c02fd9a3560e04c2f19a42cabd775211fa00735de, got 4eb32e60b79411b004b65ae7ba0bafd4eee405d774b9f4efe0b5eeb9853c9d9b. The source file may have changed since it was selected, or the download was corrupted. Not writing to data/raw/ — investigate before re-running.
- **freedomhouse-ke-2022-fotn** — acquire.py failure (2026-07-20): checksum mismatch: expected 595b66bbf50b2da15d8349148b70b9832a3f907b1c9c7c31ad73459e16385bd6, got 83ed59c7ef30cf239507934002e1e8056a2346545eb49ed3cab17d888f617431. The source file may have changed since it was selected, or the download was corrupted. Not writing to data/raw/ — investigate before re-running.
- **freedomhouse-ug-2023-fotn** — acquire.py failure (2026-07-20): checksum mismatch: expected 3bee8696e130217f3a183574168cffcb8e364b2e8634985c74e7d7ea4295dad2, got d4a3a10410b6544afde96a7b6c9ece3dd08828ed6c7fe23878284e39d5caa199. The source file may have changed since it was selected, or the download was corrupted. Not writing to data/raw/ — investigate before re-running.
- **freedomhouse-ug-2022-fotn** — acquire.py failure (2026-07-20): checksum mismatch: expected 7a7bf49fa33531503750d36b8c02a056b70498fbf517625eb6c182b062a890a2, got fbf673013605409cdc52a7a650d24d7f6f11d55271337e3e5b441c1d978ed596. The source file may have changed since it was selected, or the download was corrupted. Not writing to data/raw/ — investigate before re-running.
- **freedomhouse-et-2023-fotn** — acquire.py failure (2026-07-20): checksum mismatch: expected 74f636956abe8930fc3329d92b6250168d68f96d5ffbe6614f73ce1887972190, got 78f87b9c7677c453ec8fb53414fddbb4957e15676a4a5c7e02505fb9ef276c38. The source file may have changed since it was selected, or the download was corrupted. Not writing to data/raw/ — investigate before re-running.
- **freedomhouse-et-2022-fotn** — acquire.py failure (2026-07-20): checksum mismatch: expected 02a882b0c1a230ce335032ffc7bca6505e2624ed6ed051541849b3481d0a7bb0, got 38f8814ed196754e4c3b42e0d8b90c02bec66fda5c9e71468ccc4e8781054928. The source file may have changed since it was selected, or the download was corrupted. Not writing to data/raw/ — investigate before re-running.
- **freedomhouse-rw-2023-fotn** — acquire.py failure (2026-07-20): checksum mismatch: expected 4c373683ae46e3fc5f64209e68e6e4ac6b9c3df71a43375a2443edcbe28feb6b, got 9dd05c77b8138c2b5142ab9248755bdec77958cf93dbdd226104045f6e876f56. The source file may have changed since it was selected, or the download was corrupted. Not writing to data/raw/ — investigate before re-running.
- **freedomhouse-rw-2022-fotn** — acquire.py failure (2026-07-20): checksum mismatch: expected ecbf62d307b792e7a459592c03de837e34b975d65ef53496ebbdcd06ecf3a3c9, got d4163f4a657803b49bf07c30bb064e83dd8937f53efff87ac34850b6ed32f723. The source file may have changed since it was selected, or the download was corrupted. Not writing to data/raw/ — investigate before re-running.

## freedomhouse-ke-2023-fotn — Included

**Reviewed:** 2026-07-20. **Automated checks:** Tier 1 passed. Tier 2 FLAGGED for human review (English, 14,312 words, near-duplicate of freedomhouse-ke-2024-fotn and freedomhouse-ke-2022-fotn).

**Topic relevance:** Clean include. Country-specific Freedom on the Net chapter, coverage period June 2022-May 2023 — internet freedom/digital rights in Kenya is its entire subject, squarely within window.

**Coverage contribution:** New country/year combination not yet in the corpus. The Tier 2 near-duplicate flag against the other Kenya-year chapters reflects shared FOTN template structure, not substantive overlap — this chapter's actual findings (Telkom's nationalization, a Netflix agreement restricting LGBT+ content, election-period disinformation on TikTok/Facebook tied to an Israeli hacking firm's forged documents, a Supreme Court ruling permitting the Device Management System telecom surveillance system, and a separate Chinese state-linked breach of 8 government ministries) don't overlap with the existing Kenya 2024 entry's findings (speech-related arrests/detentions, an abduction/killing of a commentator) — genuine coverage contribution, not the same-organization near-duplicate exclusion case the rubric describes.

**Rights/licensing note:** Freedom House content, permission-gated per docs/licensing.md — internal course-project use only, pending permission response (see docs/PROJECT_CONTINUITY.md Section 7).

**Decision: Included.**

## freedomhouse-ke-2022-fotn — Included

**Reviewed:** 2026-07-20. **Automated checks:** Tier 1 passed. Tier 2 FLAGGED for human review (English, 11,865 words, near-duplicate of freedomhouse-ke-2023-fotn).

**Topic relevance:** Clean include. Country-specific Freedom on the Net chapter, coverage period June 2021-May 2022.

**Coverage contribution:** Third Kenya year in the corpus (2022/2023/2024), the earliest baseline. Tier 2's near-duplicate flag against the 2023 chapter is template similarity, not content overlap — this chapter documents a Facebook-suspension threat ahead of the 2022 election, TikTok election misinformation, a Supreme Court ruling on judicial independence (striking down a constitutional-review push), and a SIM re-registration crackdown with fine/imprisonment threats, all distinct from both the 2023 and 2024 findings.

**Rights/licensing note:** Same as above — permission pending, internal use only.

**Decision: Included.**

## freedomhouse-ug-2023-fotn — Included

**Reviewed:** 2026-07-20. **Automated checks:** Tier 1 passed. Tier 2 FLAGGED for human review (English, 13,232 words, near-duplicate of freedomhouse-ug-2024-fotn and freedomhouse-ug-2022-fotn).

**Topic relevance:** Clean include. Country-specific Freedom on the Net chapter, coverage period June 2022-May 2023.

**Coverage contribution:** New Uganda year not yet in the corpus. Near-duplicate flag against the other Uganda-year chapters is structural (shared template), not substantive — this chapter documents the Anti-Homosexuality Act's online-content penalties (signed May 2023), a Constitutional Court ruling striking the "offensive communication" provision, a new Computer Misuse Amendment Act (up to 7 years for vaguely-defined "unsolicited"/"malicious" information sharing, 10 for unauthorized data access), a dismissed cyberstalking case against journalists, and a reported police purchase of Cellebrite's UFED phone-hacking tool — legislative/surveillance content distinct from the existing 2024 entry.

**Rights/licensing note:** Same as above — permission pending, internal use only.

**Decision: Included.**

## freedomhouse-ug-2022-fotn — Included

**Reviewed:** 2026-07-20. **Automated checks:** Tier 1 passed. Tier 2 FLAGGED for human review (English, 11,589 words, near-duplicate of freedomhouse-ug-2024-fotn and freedomhouse-ug-2023-fotn).

**Topic relevance:** Clean include. Country-specific Freedom on the Net chapter, coverage period June 2021-May 2022.

**Coverage contribution:** Third Uganda year in the corpus, the earliest baseline. Near-duplicate flag reflects template similarity with the other two Uganda-year chapters, not overlap — this chapter documents a new internet-data tax replacing the prior OTT tax, the continued Facebook block (a persistent baseline fact worth having across editions), ongoing arrests/violence against critical journalists, and Pegasus spyware (NSO Group) used against journalists and an opposition leader — distinct from both 2023 and 2024.

**Rights/licensing note:** Same as above — permission pending, internal use only.

**Decision: Included.**

## freedomhouse-et-2023-fotn — Included

**Reviewed:** 2026-07-20. **Automated checks:** Tier 1 passed. Tier 2 FLAGGED for human review (English, 12,762 words, near-duplicate of freedomhouse-et-2022-fotn).

**Topic relevance:** Clean include. Country-specific Freedom on the Net chapter, coverage period June 2022-May 2023 — this corpus's most active live-conflict censorship story.

**Coverage contribution:** New Ethiopia year not yet in the corpus. Near-duplicate flag against the 2022 chapter is structural, not substantive — this chapter documents the Tigray internet shutdown beginning to lift after the November 2022 peace agreement, new communications blackouts opening in Oromia (Kellem Wollega, July 2022) and Amhara (mobile data cut, April 2023), and a nationwide block of TikTok/Facebook/Telegram/YouTube (Feb-May 2023) tied to Ethiopian Orthodox Church-organized protests — a genuinely new platform-wide block not present in the 2022 chapter.

**Rights/licensing note:** Same as above — permission pending, internal use only.

**Decision: Included.**

## freedomhouse-et-2022-fotn — Included

**Reviewed:** 2026-07-20. **Automated checks:** Tier 1 passed. Tier 2 FLAGGED for human review (English, 11,673 words, near-duplicate of freedomhouse-et-2023-fotn).

**Topic relevance:** Clean include. Country-specific Freedom on the Net chapter, coverage period June 2021-May 2022.

**Coverage contribution:** Third Ethiopia year in the corpus, the earliest baseline. Near-duplicate flag against the 2023 chapter is template similarity, not overlap — this chapter documents the Tigray shutdown still fully in effect pre-peace-deal (the "before" state that the 2023 chapter shows lifting), international outlets' press licenses threatened/revoked, and a journalist forcibly disappeared — distinct from both 2023 and 2024.

**Rights/licensing note:** Same as above — permission pending, internal use only.

**Decision: Included.**

## freedomhouse-rw-2023-fotn — Included

**Reviewed:** 2026-07-20. **Automated checks:** Tier 1 passed, Tier 2 clean (English, 10,128 words, no near-duplicates).

**Topic relevance:** Clean include. Country-specific Freedom on the Net chapter, coverage period June 2022-May 2023.

**Coverage contribution:** New Rwanda year not yet in the corpus. Documents a RURA telecom licensing change, 3 imprisoned YouTube journalists acquitted and released (Oct 2022), a Citizen Lab report confirming Pegasus targeting of a government critic's relative, and the death of prominent investigative journalist John Ntwali in a suspicious car accident (Jan 2023) — distinct from both the 2022 and 2024 findings.

**Rights/licensing note:** Same as above — permission pending, internal use only.

**Decision: Included.**

## freedomhouse-rw-2022-fotn — Included

**Reviewed:** 2026-07-20. **Automated checks:** Tier 1 passed, Tier 2 clean (English, 9,220 words, no near-duplicates).

**Topic relevance:** Clean include. Country-specific Freedom on the Net chapter, coverage period June 2021-May 2022.

**Coverage contribution:** Third Rwanda year in the corpus, the earliest baseline. Documents the blocking of 15 exile-run outlets, prison sentences of 15 and 7 years for YouTube critics, Pegasus targeting of non-Rwandan journalists, and a new data-privacy law with in-country data-storage requirements — distinct from both 2023 and 2024.

**Rights/licensing note:** Same as above — permission pending, internal use only.

**Decision: Included.**
