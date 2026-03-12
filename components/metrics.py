# components/metrics.py
# Owned by: Naveen
# Job: Renders 4 stat cards at the top of the page

import streamlit as st
from data.hotspots import get_hotspots

def render_metrics():
    df = get_hotspots()

    c1, c2, c3, c4 = st.columns(4)

    c1.metric(
        label="Zones Tracked",
        value=len(df)
    )
    c2.metric(
        label="Critical Zones",
        value=len(df[df["severity"] == "Critical"])
    )
    c3.metric(
        label="Avg FDI Score",
        value=round(df["fdi_score"].mean(), 2)
    )
    c4.metric(
        label="Total Area Affected",
        value=f"{df['area_km2'].sum():,} km²"
    )
