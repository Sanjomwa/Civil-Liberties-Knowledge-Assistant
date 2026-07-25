"""
build_calibration_review_v2.py -- regenerates the human-calibration
review artifact from source data. Replaces the Excel-based approach
(data/eval/human_calibration_review.xlsx), which hit a real wall: Excel's
409pt row-height cap truncated 41 of 47 long excerpts on-screen, making
them unreadable without a per-cell expand-the-formula-bar workaround.

Output: a static HTML page, one section per claim, full claim text and
full cited-excerpt text with no length cap and no scrolling-inside-a-cell
-- normal browser page scroll only. Three verdict sources are shown per
claim, each explicitly labeled as AI or human so no reader can mistake
one for the other:
  - AI JUDGE -- gpt-5.4-mini (v1 and v2 shown separately)
  - AI REVIEWER -- Claude, cross-model check, NOT a human validation
  - YOUR VERDICT -- the only human-validated field, currently blank
    (recorded separately -- see the companion CSV, not in this HTML)

Also writes a slim companion CSV (judgment_id + one blank human_verdict
column) as the actual place to record verdicts -- small enough to fill
in directly without re-reading excerpt text to find the right row.

Usage:
    uv run python scripts/build_calibration_review_v2.py
"""

import ast
import csv
import html
import json
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
CALIBRATION_CSV = PROJECT_ROOT / "data/eval/judge_calibration_sample_full.csv"
V2_JUDGMENTS = PROJECT_ROOT / "data/eval/judgments_v2.jsonl"
OUT_HTML = PROJECT_ROOT / "data/eval/human_calibration_review_v2.html"
OUT_VERDICTS_CSV = PROJECT_ROOT / "data/eval/human_calibration_v2_verdicts.csv"

VALID_VERDICTS = ("supported", "partial", "unsupported")


def load_calibration_rows() -> list[dict]:
    with open(CALIBRATION_CSV, encoding="utf-8") as f:
        rows = list(csv.DictReader(f))
    for i, r in enumerate(rows, start=1):
        r["row_number"] = i
    return rows


def load_v2_verdicts() -> dict[str, dict]:
    """judgment_id -> {verdict, reason} from the full 481-claim v2 re-run
    (ADR-0014's source-of-record for the v2 headline number). judgment_id
    is the confirmed real join key (checked against both files directly,
    not assumed) -- all 65 calibration judgment_ids are present in this
    file."""
    v2 = {}
    with open(V2_JUDGMENTS, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            rec = json.loads(line)
            v2[rec["judgment_id"]] = {"verdict": rec["verdict"], "reason": rec["reason"]}
    return v2


def esc(text: str) -> str:
    return html.escape(text, quote=False)


def verdict_badge_class(verdict: str) -> str:
    v = (verdict or "").strip().lower()
    if v == "supported":
        return "badge-supported"
    if v == "partial":
        return "badge-partial"
    if v == "unsupported":
        return "badge-unsupported"
    return "badge-unknown"


def render_row(row: dict, v2_verdicts: dict[str, dict]) -> str:
    rn = row["row_number"]
    jid = row["judgment_id"]
    category = row["category"]
    claim_text = row["claim_text"]
    chunks = ast.literal_eval(row["cited_chunk_texts"])
    n_chunks = len(chunks)

    v1_verdict = row["verdict"]
    v1_reason = row["reason"]
    v2_entry = v2_verdicts.get(jid)
    v2_verdict = v2_entry["verdict"] if v2_entry else "(not found in judgments_v2.jsonl)"
    v2_reason = v2_entry["reason"] if v2_entry else ""

    ai_reviewer_verdict = row.get("ai_reviewer_verdict", "").strip()
    ai_reviewer_model = row.get("ai_reviewer_model", "").strip()
    if not ai_reviewer_verdict:
        ai_reviewer_verdict = "(not reviewed)"
        ai_reviewer_model = ""

    excerpts_html = ""
    for i, chunk in enumerate(chunks, start=1):
        excerpts_html += f"""
        <div class="excerpt">
          <div class="excerpt-label">Excerpt {i} of {n_chunks}</div>
          <pre class="excerpt-text">{esc(chunk.strip())}</pre>
        </div>"""

    return f"""
<section class="claim-row" id="row-{rn}">
  <div class="row-header">
    <span class="row-number">Row {rn}</span>
    <span class="row-meta">judgment_id: <code>{esc(jid)}</code> &middot; category: <code>{esc(category)}</code></span>
  </div>

  <div class="claim-block">
    <div class="block-label">CLAIM</div>
    <div class="claim-text">{esc(claim_text)}</div>
  </div>

  <div class="excerpts-block">
    <div class="block-label">CITED EXCERPT(S) -- {n_chunks} total, full verbatim text</div>
    {excerpts_html}
  </div>

  <div class="verdicts-block">
    <div class="verdict-source ai">
      <div class="source-label">AI JUDGE &mdash; gpt-5.4-mini (v1 and v2 shown separately)</div>
      <div class="verdict-line">
        <span class="verdict-tag">v1 (original rubric, 0.879 aggregate)</span>
        <span class="badge {verdict_badge_class(v1_verdict)}">{esc(v1_verdict)}</span>
        <div class="reason">{esc(v1_reason)}</div>
      </div>
      <div class="verdict-line">
        <span class="verdict-tag">v2 (fixed rubric, 2026-07-25, 0.946 aggregate)</span>
        <span class="badge {verdict_badge_class(v2_verdict)}">{esc(v2_verdict)}</span>
        <div class="reason">{esc(v2_reason)}</div>
      </div>
    </div>

    <div class="verdict-source ai-reviewer">
      <div class="source-label">AI REVIEWER &mdash; Claude, cross-model check, <strong>NOT a human validation</strong></div>
      <div class="verdict-line">
        <span class="badge {verdict_badge_class(ai_reviewer_verdict)}">{esc(ai_reviewer_verdict)}</span>
        <span class="model-note">{esc(ai_reviewer_model)}</span>
      </div>
    </div>

    <div class="verdict-source human">
      <div class="source-label">YOUR VERDICT &mdash; the only human-validated field, currently blank</div>
      <div class="verdict-line">
        <span class="badge badge-unknown">(not yet recorded)</span>
        <div class="reason">Record this in the companion CSV
        (<code>data/eval/human_calibration_v2_verdicts.csv</code>), row with
        <code>judgment_id = {esc(jid)}</code> &mdash; not in this HTML file, which is read-only.</div>
      </div>
    </div>
  </div>
</section>
"""


PAGE_CSS = """
:root {
  color-scheme: light dark;
}
body {
  font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Helvetica, Arial, sans-serif;
  line-height: 1.5;
  max-width: 860px;
  margin: 0 auto;
  padding: 2rem 1.5rem 6rem;
  color: #1a1a1a;
  background: #ffffff;
}
@media (prefers-color-scheme: dark) {
  body { color: #e4e4e4; background: #16171a; }
  .claim-row { background: #1e2024; border-color: #33363c; }
  .claim-text { background: #24262b; }
  .excerpt-text { background: #101113; color: #cfd3d8; }
  code { background: #2a2c31; color: #dcdcdc; }
  .verdict-source.ai { background: #1a2430; border-color: #2c4a6b; }
  .verdict-source.ai-reviewer { background: #2a2018; border-color: #6b4a2c; }
  .verdict-source.human { background: #1a2b1e; border-color: #2c6b3d; }
}
h1 { font-size: 1.5rem; margin-bottom: 0.25rem; }
.intro {
  font-size: 0.95rem;
  border-left: 4px solid #888;
  padding: 0.75rem 1rem;
  margin: 1rem 0 2rem;
  background: rgba(128,128,128,0.08);
}
.toc {
  columns: 4;
  column-gap: 1rem;
  font-size: 0.85rem;
  margin-bottom: 2.5rem;
}
.toc a { text-decoration: none; }
.claim-row {
  border: 1px solid #d5d5d5;
  border-radius: 8px;
  padding: 1.25rem 1.5rem;
  margin-bottom: 2rem;
  background: #fafafa;
}
.row-header {
  display: flex;
  justify-content: space-between;
  align-items: baseline;
  flex-wrap: wrap;
  gap: 0.5rem;
  border-bottom: 1px solid #ddd;
  padding-bottom: 0.5rem;
  margin-bottom: 0.75rem;
}
.row-number { font-size: 1.15rem; font-weight: 700; }
.row-meta { font-size: 0.8rem; opacity: 0.75; }
.block-label {
  font-size: 0.72rem;
  font-weight: 700;
  letter-spacing: 0.04em;
  text-transform: uppercase;
  opacity: 0.6;
  margin-bottom: 0.35rem;
  margin-top: 1rem;
}
.claim-text {
  font-size: 1.02rem;
  padding: 0.6rem 0.8rem;
  background: #fff;
  border-radius: 6px;
  border: 1px solid #e0e0e0;
}
.excerpt { margin-bottom: 0.75rem; }
.excerpt-label { font-size: 0.75rem; font-weight: 600; opacity: 0.7; margin-bottom: 0.25rem; }
.excerpt-text {
  white-space: pre-wrap;
  word-wrap: break-word;
  font-family: Georgia, "Times New Roman", serif;
  font-size: 0.92rem;
  line-height: 1.55;
  background: #fff;
  border: 1px solid #e5e5e5;
  border-radius: 6px;
  padding: 0.75rem 1rem;
  margin: 0;
}
.verdicts-block { margin-top: 1.25rem; display: flex; flex-direction: column; gap: 0.75rem; }
.verdict-source {
  border-radius: 6px;
  padding: 0.7rem 0.9rem;
  border: 1px solid;
}
.verdict-source.ai { background: #eaf2fb; border-color: #b7d1ee; }
.verdict-source.ai-reviewer { background: #fbf1e6; border-color: #e9caa0; }
.verdict-source.human { background: #eaf6ec; border-color: #b9dcc0; }
.source-label { font-weight: 700; font-size: 0.85rem; margin-bottom: 0.4rem; }
.verdict-line { margin-bottom: 0.4rem; }
.verdict-line:last-child { margin-bottom: 0; }
.verdict-tag { font-size: 0.8rem; font-weight: 600; margin-right: 0.5rem; }
.model-note { font-size: 0.78rem; opacity: 0.7; margin-left: 0.5rem; }
.reason { font-size: 0.88rem; opacity: 0.85; margin-top: 0.15rem; }
.badge {
  display: inline-block;
  font-size: 0.78rem;
  font-weight: 700;
  padding: 0.1rem 0.55rem;
  border-radius: 999px;
  text-transform: uppercase;
  letter-spacing: 0.02em;
}
.badge-supported { background: #1e7d34; color: #fff; }
.badge-partial { background: #b5860a; color: #fff; }
.badge-unsupported { background: #b3261e; color: #fff; }
.badge-unknown { background: #777; color: #fff; }
code {
  background: #eee;
  padding: 0.05rem 0.35rem;
  border-radius: 4px;
  font-size: 0.85em;
}
"""


def build() -> None:
    rows = load_calibration_rows()
    v2_verdicts = load_v2_verdicts()

    toc_links = " &middot; ".join(f'<a href="#row-{r["row_number"]}">{r["row_number"]}</a>' for r in rows)
    rows_html = "\n".join(render_row(r, v2_verdicts) for r in rows)

    page = f"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<title>Human Calibration Review v2 -- 65 claims</title>
<style>{PAGE_CSS}</style>
</head>
<body>
<h1>Human Calibration Review v2</h1>
<p class="intro">
All 65 rows from <code>data/eval/judge_calibration_sample_full.csv</code>, full verbatim claim
and excerpt text, no length cap. Replaces the Excel-based artifact
(<code>data/eval/human_calibration_review.xlsx</code>), which truncated 41 of 47 long
excerpts on-screen due to Excel's 409pt row-height cap. Three verdict sources per claim,
explicitly labeled -- <strong>only "YOUR VERDICT" is human-validated</strong>; the other two
are both AI output (a judge model and a separate AI cross-check), neither of which substitutes
for a real human read. This page is read-only reference material -- record your actual verdicts
in the companion CSV, <code>data/eval/human_calibration_v2_verdicts.csv</code>
(<code>judgment_id</code> + one blank <code>human_verdict</code> column: Supported / Partial /
Unsupported), not in this file.
</p>
<div class="toc">Jump to row: {toc_links}</div>
{rows_html}
</body>
</html>
"""
    OUT_HTML.write_text(page, encoding="utf-8")
    print(f"[ok] wrote {OUT_HTML.relative_to(PROJECT_ROOT)} ({len(rows)} rows)")

    with open(OUT_VERDICTS_CSV, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(["judgment_id", "human_verdict"])
        for r in rows:
            writer.writerow([r["judgment_id"], ""])
    print(f"[ok] wrote {OUT_VERDICTS_CSV.relative_to(PROJECT_ROOT)} ({len(rows)} rows, "
          f"human_verdict column blank -- fill in with one of {VALID_VERDICTS})")


if __name__ == "__main__":
    build()
