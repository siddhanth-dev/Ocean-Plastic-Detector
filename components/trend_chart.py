# components/trend_chart.py
# Owned by: Naveen
# Job: Shows FDI trend over 2020-2026 per hotspot zone

import streamlit as st
import pandas as pd
import plotly.express as px
from data.hotspots import get_hotspots

# Simulated annual growth rate per severity
# Based on UNEP 2021 report — plastic input increasing ~5-8% per year
GROWTH_RATE = {
    "Critical": 0.07,
    "High":     0.05,
    "Medium":   0.04,
    "Low":      0.02,
}

YEARS = [2020, 2021, 2022, 2023, 2024, 2025, 2026]

def build_trend_data():
    df = get_hotspots()
    rows = []

    for _, zone in df.iterrows():
        rate        = GROWTH_RATE.get(zone["severity"], 0.03)
        base_fdi    = zone["fdi_score"]

        # Work backwards from current FDI to get 2020 baseline
        baseline = round(base_fdi / ((1 + rate) ** 6), 3)

        for i, year in enumerate(YEARS):
            fdi = round(baseline * ((1 + rate) ** i), 3)
            rows.append({
                "Zone":     zone["name"],
                "Severity": zone["severity"],
                "Year":     year,
                "FDI":      fdi
            })

    return pd.DataFrame(rows)

def render_trend():
    st.markdown("#### Pollution Trend — FDI Growth (2020–2026)")
    st.caption("Simulated annual FDI progression based on UNEP-reported plastic growth rates.")

    df      = get_hotspots()
    zones   = df["name"].tolist()

    # Zone selector
    selected = st.multiselect(
        "Select zones to compare",
        options=zones,
        default=zones[:4]
    )

    if not selected:
        st.info("Select at least one zone to view trends.")
        return

    trend_df = build_trend_data()
    filtered = trend_df[trend_df["Zone"].isin(selected)]

    # Line chart
    fig = px.line(
        filtered,
        x="Year",
        y="FDI",
        color="Zone",
        markers=True,
        title="FDI Score Trend by Zone",
        labels={"FDI": "FDI Score", "Year": "Year"},
        template="plotly_dark"
    )
    fig.update_layout(
        legend=dict(orientation="h", yanchor="bottom", y=-0.4),
        margin=dict(t=40, b=80),
        hovermode="x unified"
    )
    fig.update_traces(line=dict(width=2), marker=dict(size=6))

    st.plotly_chart(fig, use_container_width=True)

    # Growth summary table
    st.markdown("#### Growth Summary")
    summary = []
    for zone in selected:
        zone_data = trend_df[trend_df["Zone"] == zone]
        fdi_2020  = zone_data[zone_data["Year"] == 2020]["FDI"].values[0]
        fdi_2026  = zone_data[zone_data["Year"] == 2026]["FDI"].values[0]
        growth    = round(((fdi_2026 - fdi_2020) / fdi_2020) * 100, 1)
        severity  = df[df["name"] == zone]["severity"].values[0]
        summary.append({
            "Zone":          zone,
            "Severity":      severity,
            "FDI 2020":      fdi_2020,
            "FDI 2026":      fdi_2026,
            "Growth (%)":    f"+{growth}%"
        })

    st.dataframe(
        pd.DataFrame(summary),
        use_container_width=True,
        hide_index=True
    )