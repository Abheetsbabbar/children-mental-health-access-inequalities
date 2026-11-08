"""Interactive dashboard: children and young people's mental health access & waits, England.

Run:  streamlit run app/streamlit_app.py
Reads only the small processed files committed in data/processed/, so it starts instantly.
"""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

ROOT = Path(__file__).resolve().parents[1]
PROCESSED = ROOT / "data" / "processed"
BLUE, ORANGE, NEUTRAL, MUTED = "#2a78d6", "#eb6834", "#c3c2b7", "#898781"
SEQ_BLUE = ["#cde2fb", "#9ec5f4", "#6da7ec", "#3987e5", "#256abf", "#184f95", "#0d366b"]
SEQ_ORANGE = ["#fde0d2", "#f9b99c", "#f39268", "#eb6834", "#c4501f", "#963b14"]

METRICS = {
    "access_rate_per_100k": ("Access per 100,000 under-18s (12 months)", SEQ_BLUE, ",.0f"),
    "median_wait_still_waiting_days": ("Median days waited - children still waiting", SEQ_ORANGE, ",.0f"),
    "median_wait_first_contact_days": ("Median days to first contact - children seen", SEQ_ORANGE, ",.0f"),
    "pct_clock_stops_within_4w": ("% helped within 4 weeks (Jun-Aug 2026)", SEQ_BLUE, ".0f"),
    "still_waiting_count": ("Children still waiting for first contact", SEQ_ORANGE, ",.0f"),
    "idaci_score": ("Child income deprivation (IDACI)", SEQ_ORANGE, ".2f"),
}


@st.cache_data
def load():
    sub = pd.read_parquet(PROCESSED / "mart_sub_icb_scored.parquet")
    geo = json.loads((PROCESSED / "sub_icb_2026.geojson").read_text())
    return sub, geo


def funnel_figure(df: pd.DataFrame, target: float, phi: float) -> go.Figure:
    pop = np.linspace(df.pop_u18_est.min() * 0.9, df.pop_u18_est.max() * 1.05, 300)
    fig = go.Figure()
    for z, dash, name in [(1.96, "dash", "95% limits"), (3.09, "solid", "99.8% limits")]:
        se = np.sqrt(target * 100_000 / pop * phi)
        for sign, show in [(1, True), (-1, False)]:
            y = target + sign * z * se
            fig.add_trace(go.Scatter(x=pop, y=np.where(y > 0, y, None), mode="lines", name=name,
                                     line=dict(color=MUTED, width=1, dash=dash), showlegend=show,
                                     hoverinfo="skip"))
    colors = np.where(df.funnel_class.str.startswith("High"), BLUE,
                      np.where(df.funnel_class.str.startswith("Low"), ORANGE, NEUTRAL))
    fig.add_trace(go.Scatter(
        x=df.pop_u18_est, y=df.access_rate_per_100k, mode="markers", name="Sub-ICB",
        marker=dict(size=10, color=colors, line=dict(color="white", width=1.5)),
        customdata=df[["sub_icb_name", "funnel_class"]],
        hovertemplate="<b>%{customdata[0]}</b><br>Rate %{y:,.0f} per 100k<br>"
                      "Under-18s %{x:,.0f}<br>%{customdata[1]}<extra></extra>"))
    fig.add_hline(y=target, line=dict(color="#52514e", width=1),
                  annotation_text=f"England {target:,.0f}", annotation_position="top right")
    fig.update_layout(height=430, margin=dict(l=10, r=10, t=30, b=10), hovermode="closest",
                      xaxis_title="Estimated population aged under 18",
                      yaxis_title="Accessed per 100,000", yaxis_rangemode="tozero",
                      legend=dict(orientation="h", y=1.08))
    return fig


def main() -> None:
    st.set_page_config(page_title="CYP Mental Health Access", page_icon="📊", layout="wide")
    sub, geo = load()
    results = json.loads((ROOT / "reports" / "results.json").read_text())
    eng = results["england"]

    st.title("Children and young people's mental health: access and waits in England")
    st.caption("NHS England Mental Health Services Data Set (performance data to 31 August 2026), "
               "English Indices of Deprivation 2025 and ONS geography. Aggregate open data only.")

    # ---- filters (one row, above the charts)
    c1, c2 = st.columns([1, 2])
    regions = ["All England", *sorted(sub.region_name.unique())]
    region = c1.selectbox("NHS region", regions)
    metric = c2.selectbox("Map metric", list(METRICS), format_func=lambda k: METRICS[k][0])
    view = sub if region == "All England" else sub[sub.region_name == region]

    # ---- headline tiles
    k = st.columns(4)
    k[0].metric("Children seen (12 months)", f"{eng['cyp_accessed_12m']:,.0f}")
    k[1].metric("Helped within 4 weeks", f"{eng['pct_clock_stops_within_4w']:.0f}%")
    k[2].metric("Waiting for first contact", f"{eng['open_waiting_first_contact']:,.0f}")
    k[3].metric("Median wait so far", f"{eng['median_open_wait_days']:,.0f} days")

    # ---- map + funnel
    left, right = st.columns([1.1, 1])
    label, scale, fmt = METRICS[metric]
    fig_map = px.choropleth_map(
        view, geojson=geo, locations="sub_icb_code", featureidkey="properties.sub_icb_code",
        color=metric, color_continuous_scale=scale, map_style="carto-positron",
        center={"lat": 52.8, "lon": -1.6}, zoom=5.2 if region == "All England" else 6.2, opacity=0.85,
        hover_name="sub_icb_name", hover_data={metric: f":{fmt}", "sub_icb_code": False},
        labels={metric: label})
    fig_map.update_layout(height=560, margin=dict(l=0, r=0, t=0, b=0))
    left.subheader(label)
    left.plotly_chart(fig_map, use_container_width=True)

    right.subheader("Funnel plot: which areas differ beyond expected variation?")
    right.plotly_chart(funnel_figure(view, eng["access_rate_per_100k"], results["funnel"]["phi"]),
                       use_container_width=True)
    right.caption(f"Limits widened for over-dispersion (phi = {results['funnel']['phi']:.0f}); "
                  "blue = above, orange = below the 95% limits.")

    # ---- deprivation scatter
    st.subheader("Does deprivation explain access or waits?")
    y_metric = st.radio("Outcome", ["access_rate_per_100k", "median_wait_still_waiting_days",
                                    "pct_clock_stops_within_4w"],
                        format_func=lambda k: METRICS[k][0], horizontal=True)
    fig_sc = px.scatter(view, x="idaci_score", y=y_metric, hover_name="sub_icb_name",
                        size="pop_u18_est", size_max=22, color_discrete_sequence=[BLUE],
                        labels={"idaci_score": "Child income deprivation (IDACI)", y_metric: METRICS[y_metric][0],
                                "pop_u18_est": "Under-18 population"},
                        trendline="lowess")
    fig_sc.update_layout(height=420, margin=dict(l=10, r=10, t=10, b=10))
    st.plotly_chart(fig_sc, use_container_width=True)

    # ---- table view (accessibility: every chart value is also available as text)
    st.subheader("Data table")
    cols = ["sub_icb_name", "icb_name", "region_name", "pop_u18_est", "access_rate_per_100k",
            "median_wait_first_contact_days", "median_wait_still_waiting_days", "pct_clock_stops_within_4w",
            "still_waiting_count", "idaci_score", "funnel_class"]
    st.dataframe(view[cols].sort_values("access_rate_per_100k", ascending=False), use_container_width=True,
                 hide_index=True)
    st.download_button("Download CSV", view[cols].to_csv(index=False), "cyp_mh_sub_icb.csv", "text/csv")


if __name__ == "__main__":
    main()
