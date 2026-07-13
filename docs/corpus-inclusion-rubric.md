# Corpus Inclusion Rubric

Resolves architecture-review item #2: the frozen architecture's semantic
review stage (`validate.py`) asks a human to judge "topic relevance" and
"coverage contribution" before a document advances to `metadata.py`, but
never defines what either term means. With a bus factor of one, that
judgment currently exists only as tacit knowledge in the moment of
reviewing — this document makes it explicit, reusable, and auditable.

This is a living document, not a one-time spec. Every real inclusion or
exclusion decision made during actual corpus building should get logged in
`corpus/acquisition-log.md` against the categories below, and genuinely
ambiguous cases that come up should get added back here as new precedent
examples — see Section 4.

Last updated: 2026-07-11 (written pre-implementation, before corpus
building has started — the examples below are illustrative, not yet drawn
from real review decisions).

---

## 1. Topic relevance

**Definition:** a document is topically relevant if it primarily concerns
internet censorship, network interference, internet shutdowns, or digital
rights in at least one of the five target countries (Kenya, Uganda,
Tanzania, Ethiopia, Rwanda), within the 2022–2025 window.

"Primarily concerns" means the document's core subject is one of those
topics — not that every paragraph is on-topic. A 40-page country report on
digital rights broadly, with a 3-page section specifically on network
shutdowns, still counts: the shutdown coverage is why it's in the corpus,
and the rest is context a citation-grounded answer may legitimately need.

**Include if:**
- The document's title, abstract, or primary framing is about censorship,
  shutdowns, network interference, or digital rights in a target country
  within the date window.
- It's a methodology or explainer document (e.g., an OONI test
  specification) that a citation-grounded answer would need to explain
  *how* an included finding was measured or classified — these support
  in-scope documents even if the methodology page itself isn't
  country-specific.

**Exclude if:**
- The document is about digital rights in a country or region outside
  scope, even if it's from an in-scope organization (e.g., a CIPESA report
  focused on West Africa).
- The document's connection to the topic is incidental — e.g., a general
  press-freedom report that mentions internet access in one sentence.
- The document falls outside 2022–2025, even if otherwise perfectly on
  topic (older reports may still be useful background reading while
  designing the corpus, but they don't get ingested).

**Borderline example (include):** a Freedom House "Freedom on the Net"
Kenya chapter that spends most of its length on broader internet freedom
(surveillance law, platform regulation) with one substantial section on a
2023 shutdown during unrest. Include — the shutdown section is exactly the
kind of evidence this corpus exists to hold, and the surrounding context is
legitimate background, not padding.

**Borderline example (exclude):** an Access Now press release announcing a
partnership or a funding award, published during the window, that happens
to mention #KeepItOn in passing. Exclude — this is organizational news, not
evidentiary documentation of an actual incident, and the architecture
already explicitly excludes press releases for this org.

**Genuinely ambiguous, resolve case-by-case:** a CIPESA report primarily
about AI governance in Africa with a subsection connecting AI-driven content
moderation to shutdown-adjacent censorship risk. This is the kind of case
that doesn't have a clean rule — log the actual reasoning when it comes up
for real, and add it here as precedent (see Section 4).

---

## 2. Coverage contribution

**Definition:** a document contributes to corpus coverage if it adds
evidence the corpus doesn't already have — a new country/year/organization
combination, a materially different account of an event already covered
(valuable specifically because this project's own research questions
include comparing how organizations document the same events), or new
methodological grounding a citation-based answer would need.

**Include if:**
- It covers a country/year combination not yet represented for that
  organization.
- It documents the same event as an already-included document, but from a
  different organization — this is coverage contribution, not duplication,
  because cross-organization comparison is one of the architecture's stated
  research questions ("How were disruptions documented, justified, or
  disputed across organizations?").
- It's the primary methodology reference for a test/classification method
  already relied on by an included report (e.g., the OONI page explaining
  DNS-blocking classification, once a DNS-blocking finding is in the
  corpus).

**Exclude if:**
- It's a near-duplicate of an already-included document from the *same*
  organization — e.g., a mid-year update that's superseded by (or nearly
  identical to) the annual report already included. Prefer the more
  comprehensive/authoritative version.
- It adds no new country, year, organizational perspective, or
  methodological grounding beyond what's already in the corpus.

**Borderline example (include):** Access Now's KeepItOn annual report and
CIPESA's State of Internet Freedom in Africa report both cover the same
2023 Uganda shutdown. Include both — same event, different organizational
account, which is coverage contribution by definition here, not
duplication.

**Borderline example (exclude):** OONI publishes a short mid-year data note
on Ethiopia, then a fuller year-end country report covering the same
period with more detail. If the mid-year note doesn't cover a shutdown or
finding the year-end report omits, exclude the mid-year note — it doesn't
contribute coverage beyond what the fuller document already provides.
(Corrected 2026-07-11, per ADR-0002: a data note under 500 words is *not*
automatically excluded before reaching this stage — minimum length is a
Tier 2 check, flagged and routed into this same human-reviewed report for
confirmation, not silently dropped. So a genuinely short-but-thin data note
may well reach semantic review anyway; this example's exclusion reasoning
is about coverage contribution, independent of whatever the length flag
already said.)

**Note on "superseded" — two different mechanisms, don't conflate them.**
The word above describes an *acquisition-time* judgment: choosing not to
include a document because a better one already covers the same ground.
That's different from `docs/adr/0003-provenance-lifecycle-metadata.md`'s
`lifecycle.status: "superseded"`, which is for a document *already in the
corpus* being formally replaced later (e.g., an org reissues a corrected
report). If a document under review is a correction/reissue of something
already included, that's ADR-0003's mechanism (a new doc_id + lifecycle
pointer), not a simple Include/Exclude call under this rubric.

---

## 3. Rights/licensing check (tie-in, not a separate gate)

Per `docs/licensing.md`, Freedom House content specifically is
permission-gated, not Creative Commons. When a document under semantic
review is from Freedom House, the reviewer should note in the acquisition
log whether it's being included for internal, non-commercial course-project
use (fine now) versus anything that would touch the CLIO-facing
redistribution phase (needs the permission request first — see
`PROJECT_CONTINUITY.md` Section 7). This isn't a third relevance/coverage
criterion — it's a reminder to connect the inclusion decision to the
licensing status already on file, so the two documents don't drift apart.

---

## 4. How to use this during real review

1. Read the document (or enough of it to judge).
2. Check topic relevance (Section 1) — record which case it matches, or write the
   actual reasoning if it's genuinely ambiguous.
3. Check coverage contribution (Section 2) — same.
4. If the source is Freedom House, note the rights-check reminder (Section 3).
5. Log the decision — Included or Excluded, with the reason — in
   `corpus/acquisition-log.md`, per the architecture's own requirement that
   "someone reading it should be able to understand every inclusion and
   exclusion decision without reference to any other document."
6. If the case didn't cleanly fit an existing example in Section 1 or Section 2, add it
   here as a new borderline example once resolved, so the rubric actually
   grows from real decisions instead of staying a one-time draft.
