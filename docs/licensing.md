# Source Licensing — Per-Organization Findings

Resolves architecture-review item #1 (no license/ToS review existed before
acquisition). One-time review per organization, not per document, since
each org applies one blanket policy across its publications. Checked
2026-07-11 via each org's own published terms.

This file is the detail; `data_governance.md` Section 1 points here. Once
`metadata.py` exists, every document's declared metadata should include a
`license` field populated from this table.

---

## Summary table

| Org | License model | Commercial use | Redistribution of full reports | Action needed |
|---|---|---|---|---|
| OONI | CC BY-NC-SA 4.0 (data); general CC noted for content | Not permitted (NC clause) | Permitted, non-commercial, attributed, share-alike | None — this project is non-commercial. Re-check if reuse ever turns commercial. |
| Access Now | CC BY 4.0 for original "Media Material"; third-party material may need separate permission | Not addressed for reports specifically | Likely fine with attribution, but reports aren't explicitly named the way logos/images are | Attribute; treat report *text* conservatively until confirmed CC-covered like site media. |
| CIPESA | CC BY 4.0 site-wide ("unless otherwise noted") | Permitted with attribution | Permitted with attribution | Attribute. Low risk. |
| Freedom House | Not CC-licensed. Permission-gated for reproduction/republishing beyond sharing published content. Noncommercial + citation is fine for "sharing"; commercial or republishing needs written permission. | Explicitly requires prior approval | **Not confirmed** — their FAQ is written for "email a report to a colleague," not permanent archival + eventual API-served redistribution | **Needs explicit written permission before any CLIO-facing redistribution phase.** Fine for internal, non-commercial course-project use now. |

---

## Detail per organization

### OONI

Source: `ooni.org/about/data-policy`, `github.com/ooni/license`.

OONI separates licensing into three categories in their license repo —
`content`, `data`, `software`. Their published network measurement **data**
is explicitly CC BY-NC-SA 4.0 (Attribution, NonCommercial, ShareAlike). The
site footer states more generally that "content is available under a
Creative Commons license," which almost certainly covers their reports too,
but the exact variant for `content` specifically (as opposed to `data`)
wasn't independently confirmed in this pass — worth a two-minute check of
the `content` folder in `github.com/ooni/license` directly before corpus
freeze, since NC + ShareAlike are real constraints on anything downstream
(including CLIO, if CLIO is ever commercial).

**For this project:** fine as-is. Both this project and CLIO are
non-commercial civil-society/research work, which satisfies the NC clause.
Attribution and share-alike terms should be carried into however this
corpus or its derivatives are eventually distributed.

### Access Now

Source: `accessnow.org/trademarks-copyright-and-media-usage`.

This page is Access Now's general Trademarks, Copyright, and Media Usage
policy. It states original "Media Material" on their site is CC BY 4.0
unless otherwise noted, but "Media Material" as defined there leans toward
images/graphics/logos, and the page doesn't explicitly address long-form
report PDFs (like KeepItOn annual reports) the same way. It also flags that
some third-party material on their site may need separate permission.

**For this project:** treat KeepItOn report *text* as attribution-required
but not confirmed blanket-reusable the way a labeled CC BY image is. Check
each acquired report's own front-matter/footer for a report-specific
license notice when `acquire.py` runs — some orgs put it directly on the
document. If a report is silent on this, attribute clearly and avoid full
verbatim redistribution of large excerpts beyond what the assistant needs
to answer a specific question with a citation.

### CIPESA

Source: `cipesa.org` site footer.

Clean and simple: "Copyright © 2026, CIPESA. All rights reserved. Unless
otherwise noted, content on this site is licensed under Creative Commons
Attribution 4.0." CC BY 4.0, no NonCommercial or ShareAlike restriction —
the least restrictive of the four.

**For this project:** attribute, no other constraint identified.

### Freedom House

Source: `freedomhouse.org/about-us/content-permissions`.

This is the one that actually matters. Freedom House explicitly lists
"Reports" as covered content, and their policy is **not** a Creative
Commons license — it's permission-based:

- Noncommercial use is permitted, but requires citation.
- You do **not** need permission to *share* already-published content (e.g.
  email a report, post on social media).
- Any **commercial** use, or (implicitly) any reproduction/republishing
  beyond simple sharing, requires written permission from Freedom House.

Downloading full report PDFs and permanently archiving them in `data/raw/`,
then later potentially serving chunks of that text through a queryable
system exposed via an API to CLIO, is a meaningfully different act than
"sharing a link" or "emailing a report to a colleague" — the scenario their
FAQ is clearly written for. It's not clearly covered by the "noncommercial
sharing" exception, and it's not clearly a commercial use either. This is
a genuine gray area, not a confirmed problem, but also not confirmed safe.

**For this project:** using Freedom House reports for a non-commercial
course project, with citation, is reasonably low risk on its own. But
**before this corpus is ever exposed through the CLIO API boundary or any
other public-facing redistribution**, Freedom House specifically needs an
actual permission email — subject line per their own instructions:
`Permission Request: [org/project name], [Project]` — describing the
intended use (RAG assistant indexing and citing excerpts of their Freedom
on the Net country chapters). This is flagged as a real pre-CLIO-integration
action item, not a hypothetical.

---

## Action items

1. Add a `license` field to declared metadata once `metadata.py` exists,
   populated from the summary table above per document's source org.
2. Before corpus freeze: verify OONI's `content`-specific license variant
   (two-minute check of `github.com/ooni/license/tree/master/content`).
3. **Before any CLIO-facing redistribution phase:** send Freedom House an
   explicit permission request. **Sent 2026-07-13** (drafted 2026-07-11) to
   `press@freedomhouse.org` (decoded from Freedom House's Cloudflare-
   obfuscated contact links, consistent across two independent pages on
   their site). Awaiting response — no reply yet. Redistribution via CLIO
   stays gated until permission is actually confirmed, not just requested.
   Track status in `PROJECT_CONTINUITY.md` Section 7.
4. When acquiring Access Now reports, check each PDF's own front matter for
   a report-specific license notice before assuming the site-wide CC BY 4.0
   applies to report text.
