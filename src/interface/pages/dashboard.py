"""
dashboard.py -- Streamlit-native monitoring dashboard, per
docs/interface-design.md Decisions 2 and 5. The guaranteed monitoring
deliverable (built and verified before Grafana is even attempted).

Auto-discovered by Streamlit as a second page when app.py is run
(src/interface/pages/*.py convention) -- no separate `streamlit run`
command needed.

Six charts, all reading directly from the `interactions` table:
1. Feedback over time (daily up/down counts)
2. Latency, split retrieval_ms vs llm_ms, stacked
3. Retrieval score distribution (histogram over flattened retrieval_scores)
4. Source-org mix
5. Token/cost over time
6. Citation data-quality rate over time (invalid_marker_count /
   unsupported_paragraph_count), the free sixth chart citations.py
   already computes.
"""

import sys
from pathlib import Path

import altair as alt
import pandas as pd
import streamlit as st

PROJECT_ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(PROJECT_ROOT / "src" / "interface"))

from db import get_conn  # noqa: E402

st.set_page_config(page_title="Monitoring Dashboard", page_icon="📊")
st.title("Monitoring Dashboard")


@st.cache_data(ttl=30)
def load_interactions() -> pd.DataFrame:
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT id, ts, retrieval_ms, llm_ms, total_tokens, est_cost_usd,
                       retrieval_scores, source_orgs, invalid_marker_count,
                       unsupported_paragraph_count, citation_count, feedback
                FROM interactions
                ORDER BY ts
                """
            )
            rows = cur.fetchall()
            cols = [d.name for d in cur.description]
    return pd.DataFrame(rows, columns=cols)


df = load_interactions()

if df.empty:
    st.info("No interactions recorded yet — ask a few questions on the main page first.")
    st.stop()

df["ts"] = pd.to_datetime(df["ts"])
df["date"] = df["ts"].dt.date

st.caption(f"{len(df)} real interaction(s) recorded.")

# --- 1. Feedback over time ---
st.subheader("1. Feedback over time")
fb = df[df["feedback"].notna()].copy()
if fb.empty:
    st.caption("No feedback recorded yet.")
else:
    fb["vote"] = fb["feedback"].map({1: "👍 up", -1: "👎 down"})
    daily = fb.groupby(["date", "vote"]).size().reset_index(name="count")
    chart = alt.Chart(daily).mark_bar().encode(
        x="date:T", y="count:Q", color="vote:N",
    )
    st.altair_chart(chart, width='stretch')

# --- 2. Latency, stacked retrieval vs llm ---
st.subheader("2. Latency (retrieval vs LLM, stacked)")
latency_long = df.melt(
    id_vars=["ts"], value_vars=["retrieval_ms", "llm_ms"],
    var_name="stage", value_name="ms",
)
chart = alt.Chart(latency_long).mark_bar().encode(
    x="ts:T", y="ms:Q", color="stage:N",
)
st.altair_chart(chart, width='stretch')

# --- 3. Retrieval score distribution ---
st.subheader("3. Retrieval score distribution")
all_scores = [s for scores in df["retrieval_scores"].dropna() for s in (scores or [])]
if not all_scores:
    st.caption("No retrieval scores recorded yet.")
else:
    scores_df = pd.DataFrame({"score": all_scores})
    chart = alt.Chart(scores_df).mark_bar().encode(
        x=alt.X("score:Q", bin=alt.Bin(maxbins=30)), y="count()",
    )
    st.altair_chart(chart, width='stretch')

# --- 4. Source-org mix ---
st.subheader("4. Source-org mix")
org_counts: dict[str, int] = {}
for orgs in df["source_orgs"].dropna():
    for org in orgs or []:
        org_counts[org] = org_counts.get(org, 0) + 1
if not org_counts:
    st.caption("No cited organizations recorded yet.")
else:
    org_df = pd.DataFrame(sorted(org_counts.items()), columns=["organization", "count"])
    chart = alt.Chart(org_df).mark_bar().encode(x="organization:N", y="count:Q")
    st.altair_chart(chart, width='stretch')

# --- 5. Token/cost over time ---
st.subheader("5. Token count and estimated cost over time")
col1, col2 = st.columns(2)
with col1:
    st.altair_chart(
        alt.Chart(df).mark_line(point=True).encode(x="ts:T", y="total_tokens:Q"),
        width='stretch',
    )
with col2:
    cost_df = df[df["est_cost_usd"].notna()].copy()
    cost_df["est_cost_usd"] = cost_df["est_cost_usd"].astype(float)
    st.altair_chart(
        alt.Chart(cost_df).mark_line(point=True).encode(x="ts:T", y="est_cost_usd:Q"),
        width='stretch',
    )
st.caption(f"Total estimated cost so far: ${df['est_cost_usd'].astype(float).sum():.5f}")

# --- 6. Citation data-quality rate over time (free, from citations.py) ---
st.subheader("6. Citation data-quality (invalid markers / unsupported paragraphs)")
quality_long = df.melt(
    id_vars=["ts"], value_vars=["invalid_marker_count", "unsupported_paragraph_count"],
    var_name="metric", value_name="count",
)
chart = alt.Chart(quality_long).mark_line(point=True).encode(
    x="ts:T", y="count:Q", color="metric:N",
)
st.altair_chart(chart, width='stretch')
