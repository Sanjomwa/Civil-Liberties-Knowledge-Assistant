# Presentation Quick Reference — Civil Liberties Knowledge Assistant

Single-page index of every real number, decision, and rationale worth having
on hand under time pressure (interview, demo, peer review, viva). Not a
replacement for `docs/adr/`, `docs/PROJECT_CONTINUITY.md`, or
`decisionlog.md` — those stay authoritative. This doc exists so nothing here
has to be re-derived or re-tested to find; if a number below and one of those
files ever disagree, the dated ADR/PROJECT_CONTINUITY entry wins, not this
page — flag the drift rather than trusting this copy.

Last built: 2026-07-26 (Tier 2 section added). Rebuild by re-reading
`decisionlog.md` in full whenever a phase closes or a headline number
changes.

---

## Project identity, one paragraph

RAG assistant answering questions about internet censorship, network
interference, and digital rights in five East African countries (Kenya,
Uganda, Tanzania, Ethiopia, Rwanda), 2022–2026. Sources: OONI, Access Now,
CIPESA, Freedom House (v1). Every answer must cite sources; thin or
contradictory evidence gets flagged explicitly, not smoothed over.
Complementary to, not a component of, the separate CLIO platform effort
(CLIO's AI layer is a different design). Non-commercial / possibly
grant-facing, never monetized. Repo:
`github.com/Sanjomwa/Civil-Liberties-Knowledge-Assistant` (public, MIT).
Architecture frozen at v1.0 (June 2026), amended to **v1.9** via
ADR-0001–0009 (v1.9's version, not the ADR count — later ADRs are
methodology, not architecture edits). **Deadline: Project Attempt 2,
2026-08-11, 02:00, Sam's local timezone** (re-verified directly from the
course-management site multiple times, not assumed).

---

## Phase status at a glance

| Phase | Status | Closed | Key doc |
|---|---|---|---|
| Ingestion | CLOSED | 2026-07-20 | ADR-0001–0008 |
| Retrieval | CLOSED | 2026-07-23 | `retrieval-design.md` |
| Generation | CLOSED | 2026-07-24 | ADR-0009 |
| LLM evaluation | Built, ONE step open (human calibration) | — | ADR-0010, 0011, 0014 |
| Rubric completion (Tier 1) | DONE | 2026-07-25 | ADR-0012 |
| Rubric completion (Tier 2) | DONE — interface, Postgres, Grafana, Docker, both rehearsal directions verified, confirmed live on GitHub | 2026-07-26 | `interface-design.md`, `reports.md` |
| Rubric completion (Tier 3) | Not started, contingent on schedule | — | ADR-0012 |

---

## Ingestion — real numbers

- **35 documents, 3,783 chunks.** Per-org: Access Now 4 (668 chunks), CIPESA
  9 (1,299), Freedom House 16 (1,595), OONI 6 (221).
- Chunking: fixed windows, 1500 chars / 750-char step (50% overlap).
- ADRs: 0001 English-only corpus disclosure · 0002 tiered validation routing
  (automated vs. human-confirmed) · 0003 provenance/lifecycle metadata +
  `corpus_version` drift stamp · 0004 editorial corrections · 0005
  content-checksum handling for CDN-served HTML (Freedom House's
  `raw_bytes_stable: false` trust-on-first-use) · 0006 corpus window extended
  2022–2025 → **2022–2026** (event-motivated static bump, not a rolling
  window — reproducibility) · 0007 pipeline consistency fixes · 0008
  page-level citation provenance (true PDF page numbers survive skipped
  blank pages).
- **Independent parallel Opus + Fable review (2026-07-20)** converged on 6
  real findings before retrieval began (all fixed): unseeded `langdetect`;
  duplicate language/word-count computation between `validate.py` and
  `metadata.py`; content-drift detected but never surfacing past a stderr
  print; a single em-dash-exact-match heading gate as an unguarded
  single-point-of-failure; fragile regex-based in-place YAML surgery; **no
  page-level citation provenance existed at all** (the most mission-relevant
  finding, for a citation-grounded project).
- Freedom House permission request sent 2026-07-13 — no response as of the
  last check; tiered corpus release (ADR-0013) built instead of waiting
  indefinitely: full-text chunks for OONI/CIPESA (1,520), metadata-only/
  hash-verified for Freedom House/Access Now (2,263) = 3,783 total.
  `dist/corpus-release-v1.zip`, 4.3MB. `rehydrate.py` deterministically
  re-fetches and re-chunks the restricted-org content, verified against
  stored hashes.

## Retrieval — real numbers

- Embedding: `BAAI/bge-small-en-v1.5` (chosen over the course's
  `all-MiniLM-L6-v2` — this corpus's chunks exceed MiniLM's 256-token max).
- Ground truth: 130 → 150 (after fixing a real `classify_category()`
  case-sensitivity bug that made the OONI-methodology branch unreachable) →
  **101 questions** after circularity filtering. **101 is the real, final
  count** — 97 and 130 are both superseded intermediate counts that
  recurred as stale-number bugs more than once; double-check before citing.
- **Default method: hybrid search, RRF k=10.**
- Aggregate (n=101, hybrid k=10): **Hit Rate 0.644–0.660, MRR 0.269–0.275**
  (varies slightly by which exact run), vs. text 0.536/0.212 and vector
  0.515/0.225.
- Per-slice exception: **`multi_country` — plain text search has the best
  MRR (0.267)**, never beaten by any hybrid k or vector config. Root cause,
  verified directly: only 1 of 22 `multi_country` questions actually names
  a corpus-tracked country; the category means "gold answer spans multiple
  countries," not "names 2+ tracked countries" — P2 (country-metadata
  boost) is a real, verified, zero-regression fix but structurally cannot
  touch this slice, since it can't fire on a query naming no tracked
  country.
- `ooni_methodology` (n=11, thin — read directionally): hybrid dominates,
  **Hit Rate up to 0.909** vs. text's 0.636.
- **Relaxed (neighbor-aware) Hit Rate: 0.812 vs. strict 0.644** — a 16.8-point
  gap, confirming ~half the "miss rate" is 50%-overlap chunking's own
  same-doc-neighbor scoring artifact, not pure retrieval failure.
- **HR@3=0.366, HR@5=0.465** vs. HR@10=0.644 — a real, actionable drop-off
  if generation consumes fewer than 10 chunks per answer.
- Two independent advisor reviews (Opus, then Fable building on it) found
  two real bugs: `search.py`'s `DEFAULT_RRF_K=60` constant silently
  diverging from the actually-recorded k=10 decision (config-drift
  footgun, fixed to read the recorded default at call time); the ground
  truth filter's proper-noun exemption requiring every token in a phrase
  capitalized (fixed, though empirically this specific bug wasn't actually
  ooni_methodology's loss driver — tested and falsified against real data).
- Source-diversity@10: text search retrieves from a meaningfully *wider*
  set of sources than hybrid or vector (1.59 vs. 1.50 vs. 1.48 avg. distinct
  orgs) — a real, disclosed tension with the hybrid default, deliberately
  not retrieval-fixed; handed to generation's own thin/contradictory-
  evidence flagging by design.
- Re-ranking ablation (country boost, P2, ADR-0012 Tier 1 item): firing
  subset (n=65) Hit Rate 0.646/MRR 0.269 with boost vs. 0.631/0.266
  without — 3 wins, 0 losses, 62 ties. Small, real, clean, zero regressions.

## Generation — real numbers

- ADR-0009: index-only citation-marker protocol (`[1]`–`[10]`, deterministic
  parse/render — the LLM never generates a page number, so a fabricated
  citation is structurally impossible) + evidence flagging.
- Sourcing footer computed on the **cited** subset, not the retrieved set
  (a deliberate correction to the original design idea, which would have
  measured availability, not reliance).
- Real smoke test (4 queries, real corpus, real API key): **zero
  fabrications, zero misattributions** across every citation spot-checked
  against real source text. All three sourcing-footer cases (multi-org,
  single-org-multi-doc, single-document-strongest-caveat) confirmed firing
  correctly on live data.

## LLM evaluation — real numbers (the load-bearing section)

- ADR-0010: per-citation isolated-entailment judge protocol + judge-model
  choice + contradiction-test-gap handling. ADR-0011: claim-level precision
  (joint multi-marker judging, not per-marker isolation), a statistical
  fallback for degenerate Cohen's κ, one ordered judge-model fallback
  policy. ADR-0014: judge rubric v1→v2 fix, headline number decision.
- **Claim-level citation precision, v1: 0.879 aggregate** (423 supported /
  37 partial / 21 unsupported of 481 claims). Per-category: general 0.912,
  multi_country 0.886, ooni_methodology 0.930, synthesis_supplement 0.806,
  refusal 0.565 (expected — refusal claims are structurally harder to get
  "supported," not a red flag).
- Judge model: `gpt-5.4` returned a real, confirmed 403 on this OpenAI
  project; fell back to `gpt-5.4-mini` (same model the generator uses) —
  **self-judging risk, disclosed as a named limitation**, not buried.
- No real cross-source contradiction found in the corpus after a real
  bounded search (37 of a 50-call budget, 9 candidate pairs, all false
  positives on inspection) — **documented as a genuine evaluation gap**,
  not fabricated. The synthetic contradiction-mechanism fixture passed
  cleanly; the mechanism works, this corpus doesn't happen to trigger it.
- **Judge rubric v2 fix (2026-07-25): citation precision moved 0.879 →
  0.946**, every category improved, 33 claims moved to "supported," 1
  moved the other way (a defensible edge case on inspection). **Sam chose
  0.946 as the headline number**, 0.879 disclosed as superseded original
  methodology, per ADR-0014.
- **Prompt A/B comparison (rubric Tier 2 "compare multiple approaches"
  fix): real null result — Prompt A (original) wins 0.893 vs. Prompt B
  (evidence-first) 0.869.** Real, understood mechanism, not a denominator
  artifact: Prompt B's EVIDENCE-list format misattributed multiple facts to
  a single citation marker in spot-checked cases. `generate.py` stays on
  Prompt A. This is the fix that moved LLM evaluation from the rubric's
  1/2 (single approach only) toward 2/2 (multiple approaches genuinely
  compared).
- **Judge-validity against real human judgment remains OPEN as of
  2026-07-25.** What's been checked so far, and what hasn't:
  - AI-reviewer (Claude) cross-check vs. judge v1: **28.6% raw agreement
    (45 of 63 scored rows disagreed), 100% one-directional** (AI reviewer
    never once stricter than the judge). Explicitly disclosed as AI-vs-AI,
    **not human validation** — both raters likely share reading-
    comprehension failure modes.
  - Root-caused (Opus 5 consult): the judge's "partial" verdict had a broad
    catch-all clause, plus a structural gap on negation/absence claims
    (a chunk's silence can't textually entail a claim about that silence).
    Both targeted by the v2 fix above.
  - Blind re-read of the 22 residual v2 disagreements against verbatim
    (not paraphrased) text: only 2/22 flipped. Real, bounded ~4% gap
    remains in 3+-fact/comparative claims — a v3 prompt attempt at this
    was run and came back **negative/inconclusive, not promoted** to a full
    re-run (a genuinely reported null result, not smoothed over).
  - **Judge instability, independently confirmed twice**: ~27–40% of
    repeated identical judge calls (same claim, same excerpt,
    `temperature=0.0`) flip verdict. The reasoning-token hypothesis (Opus
    5 / Fable joint discussion) was tested directly and **not confirmed**
    — `reasoning_tokens` was exactly 0 on all 100 test calls, including on
    flipped rows. Likeliest honest explanation: ordinary provider-side
    inference non-determinism at temperature=0, not a reasoning-model
    artifact.
  - Parse-fallback bias (a flagged risk that the judge's "unsupported"
    default on malformed replies might be directionally harsh): checked
    against both real 481-claim runs, **0 occurrences of the hard-failure
    marker across 962 real judge calls** — not found.
  - **Remaining step: Sam's own human calibration read**, via the
    redesigned `data/eval/human_calibration_review_v2.html` (65 rows, full
    verbatim text, three plainly labeled verdict sources — AI Judge v1+v2,
    AI Reviewer/Claude explicitly marked not-human, and a blank human
    field) + companion `human_calibration_v2_verdicts.csv`. Nothing left to
    check from the Cowork/Claude Code side without this.
  - **Pre-registered convention, locked in before any human label exists**:
    if a binary supported/not-supported framing is ever used, "partial"
    collapses to **not-supported** (the conservative direction — a false
    "supported" is the costliest error, per ADR-0011).
- Cost of the real evaluation run: ~648 API calls, ~1,028,000 input tokens,
  ~51,150 output tokens, low single-digit dollars on `gpt-5.4-mini`
  pricing. Token volume, not call count, is the real cost driver.

## Tier 2 — interface, monitoring, containerization — real numbers

- **Streamlit interface** (`src/interface/app.py`): single page, wraps the
  existing `answer()` unchanged. 4 real example questions (pulled from the
  filtered ground truth, not invented), sourcing-status split
  (`st.warning` for thin/none, `st.info` for broad/single-org), a
  retrieved-excerpts+scores expander, thumbs up/down feedback, 20-query
  session cap, 500-char input cap.
- **Postgres logging** (`src/interface/db.py`): one `interactions` table,
  reduced projection (never raw citation excerpt text). `est_cost_usd()`
  raises `UnknownModelError` on an unrecognized model rather than silently
  logging 0 — confirmed to actually raise, not just documented to.
- **Docker + rehydrate-on-first-run** (ADR-0013's tiered release,
  `docs/interface-design.md` Decision 8): build time always bakes the
  54%-public-text release (1,520 chunks, OONI+CIPESA) so `docker compose
  up` unconditionally works; first container start attempts
  `rehydrate.py` against Freedom House + Access Now's own servers to
  reach the full 3,783-chunk corpus, re-embeds only on full success,
  degrades gracefully to the 54% baseline on any failure (logged
  plainly, never a crash). **Both directions verified for real**, not
  assumed: network-reachable rehearsal reached 100% coverage and a real
  generation call cited real rehydrated Freedom House text; network-
  blocked rehearsal failed cleanly (`0/16`, `0/4`), no re-embed
  attempted, confirmed via a live `search()` call that the container
  correctly held at the 1,520-chunk baseline with zero drift.
- **Grafana, sole monitoring dashboard** (ADR-0019): third compose
  service locally, the `grafana-cloud` Cloud Run service in production,
  `GF_AUTH_ANONYMOUS_ENABLED=true` (Viewer role), provisioned Postgres
  datasource + 6-panel dashboard — feedback over time, latency (retrieval
  vs LLM), retrieval-score distribution, source-org mix, token/cost over
  time, citation data-quality rate (datasource UID pinned identically
  everywhere it's referenced). Verified against real production data
  through Grafana's own `/api/ds/query` endpoint — every panel, including
  citation data-quality, executes and returns real rows.
- **Real incident, disclosed not smoothed over**: during testing,
  `docker-compose.yml` published the app port on all host interfaces
  (`8501:8501`), and Streamlit's dev server logged an external URL on
  the host's public IP. Three real queries appeared in Postgres that the
  tester didn't ask, ~$0.006 in real OpenAI cost — caught by noticing
  unexplained rows, not an alert. **Severity genuinely unresolved**: Sam
  suspects it may have been his own testing rather than an outside
  party; not confirmed either way. Fix applied regardless of cause:
  `"8501:8501"` → `"127.0.0.1:8501:8501"`.
- **Git-attribution incident, found and fully resolved same day**: a
  local rehearsal commit carried Claude Code's identity/AI-attribution
  trailer and was pushed to public GitHub history — caught, diagnosed
  (two commits affected), fixed via `git commit-tree` rebuild + tagged
  backup + `git push --force-with-lease`, confirmed clean. A strict
  standing rule (real git identity, no AI trailer, verify before
  reporting done) was added to `claude-code-wsl-CLAUDE.md` v5 to prevent
  recurrence.
- **Confirmed live on GitHub, 2026-07-26**: `main`'s homepage view
  initially looked stale (2 commits, old file tree) — traced to GitHub's
  anonymous-viewer edge cache, not a real problem. Direct fetch of
  `raw.githubusercontent.com/.../main/src/interface/app.py` returned the
  real, current file byte-for-byte — independent proof the push is
  genuinely live, not just locally believed to be.
- **Confirmed on a second, independent machine, same day**: after a
  Docker Desktop reinstall (unrelated Windows registry corruption), the
  full stack was built and verified end to end from a genuine clean
  state — 100% corpus rehydration on a real first run (both orgs
  hash-verified), a real question driven through an actual headless
  browser against the running app with a correctly-cited answer
  confirmed logged in Postgres afterward via direct query. **Two real
  bugs found, root-caused, not yet fixed**: Grafana panels fail at query
  time because the unpinned `grafana/grafana:latest` tag resolved to a
  version needing `jsonData.database` instead of the provisioning YAML's
  legacy top-level `database:` field; the README's mermaid architecture
  diagram fails to render at all because one node label has an unescaped
  `[n]` nested inside its own `[...]` brackets, breaking the whole
  diagram's parse. Both fixes are known, scoped, and handed to Claude
  Code as a follow-up.

## Rubric audit — what's actually earned vs. still open

Checked directly against `DataTalksClub/llm-zoomcamp`'s real `project.md`
Evaluation Criteria (fetched verbatim, not assumed), against real code:

- **2/2 earned**: Retrieval flow, Retrieval evaluation, Ingestion pipeline,
  document re-ranking best practice (P2 ablation, measured not asserted).
- **LLM evaluation: was 1/2, now fixed toward 2/2** via the real Prompt A/B
  comparison above (a genuine second approach, judged, compared, a winner
  picked) — this was the single most important rubric gap found.
- **Problem description / Reproducibility**: were under-scoring on
  documentation alone (a 306-byte one-sentence README) — fixed via the
  Tier 1 README rewrite + shipping the processed corpus + disclosing
  OONI's manual-acquisition/429 constraint explicitly.
- **Interface and Containerization: now built — 2/2 achievable**, built
  and verified 2026-07-26, well ahead of the 2026-08-02 feature-freeze
  gate. Streamlit UI + feedback, Postgres-backed 6-panel Grafana
  dashboard, Docker with a real rehydrate-on-first-run mechanism
  verified both directions. See the Tier 2 section above for detail.
- Completion plan (ADR-0012, Opus 5 consult): Tier 1 (by 7/27, done) —
  README, corpus release, re-rank evaluation. **Tier 2 (target 8/2, done
  early 7/26)** — Prompt A/B (done), Streamlit + thumbs up/down feedback,
  monitoring dashboard, docker-compose, all done. Tier 3 (8/3–05, only if
  on schedule) — cloud deployment (highest-value portfolio item, the link
  recruiters actually click), query rewriting if time remains. 8/6–07 is
  buffer, not build. **Ahead of schedule as of 2026-07-26** — Tier 2
  closed 7 days before its own gate.

## Build-in-public (LinkedIn series)

14-post plan, effectively 13 after a merge. Fixed posting order (never
reordered to chase whichever milestone is freshest). Posts 1–6 published
as of 2026-07-25 (post 6: retrieval evaluation / Hit Rate-MRR findings,
required Opus overclaim check caught 4 real issues before publishing).
Posts 7 (generation) and 8 (LLM evaluation) merged into one, freeing a
slot for a new cloud-deployment post (sequenced after containerization,
not immediately — can't honestly post about deployment before something
exists to deploy).

## Recurring engineering lessons (the "why," not just the "what")

- **"Verify, don't trust prose" is the single most load-bearing discipline
  in this project** — recurs dozens of times: stale question counts (97 →
  101, 130 → 101) carried forward into new prompts more than once;
  `reports.md`/PROJECT_CONTINUITY.md snapshots freezing while dated
  entries kept moving; docx version-bump drift recurring at least three
  times; a `sync.sh pull` silently reverting same-day Cowork-side edits at
  least twice.
- **Three separate, independent, plausible hypotheses about eval-slice
  behavior were tested directly against real data and found wrong**: the
  `ooni_methodology` filter-exemption theory, the vector-backend-narrows-
  diversity theory, and the `multi_country`/P2 theory. Named explicitly as
  validation of the empirical-verification discipline itself, not a
  criticism of the advisors who proposed them.
- **The judge-rubric tuning loop (v1→v2→v3) risked Goodharting** — each
  round's target was defined by disagreement with an unvalidated AI
  reviewer (Claude), not real human judgment. Both Opus 5 and Fable
  converged on this independently when asked to discuss the judge's
  instability directly with each other. The only real fix is scoring
  both v1 and v2 against genuine human labels, which is why human
  calibration was reinstated after initially being declined as
  unsustainable.
- **Advisor allocation discipline**: Opus 5 is the primary technical
  advisor (consult before any non-trivial change, especially to a
  previously-closed phase); Fable is budget-conscious (~3–4 total spends
  across the whole project) and used for milestone-completion narrative
  review, occasionally for deep technical second opinions when Sam
  explicitly asks for it (e.g. the judge-instability discussion).
- **sync.sh data-loss incidents recurred at least four times** across the
  project (corpus/acquisition-log.md clobber, ADR-0005 code revert,
  Freedom House hash revert, a same-day doc-edit revert) — root cause each
  time was a curated allow-list failing to anticipate a new file category;
  fixed permanently by moving both pull and push to full, symmetric,
  exclude-based mirrors instead of allow-lists.
- **A genuinely surprising, disclosed negative result**: editing prompt
  text in the v3 judge-rubric attempt shifted verdict behavior on an
  unrelated, byte-identical clause elsewhere in the same prompt — reported
  plainly as a real finding, not smoothed over, consistent with this
  project's standing rule that a disclosed null/negative result still
  earns credit.
