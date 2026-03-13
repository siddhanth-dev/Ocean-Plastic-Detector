# components/alerts.py
# Owned by: Naveen
# Job: Shows zones that have worsened based on FDI growth trend

import streamlit as st
from data.hotspots import get_hotspots

# Same growth rates as trend_chart.py
GROWTH_RATE = {
    "Critical": 0.07,
    "High":     0.05,
    "Medium":   0.04,
    "Low":      0.02,
}

ALERT_COLOR = {
    "Critical": "#FF5400",
    "High":     "#FF8500",
    "Medium":   "#FFB700",
    "Low":      "#FFD000",
}

def get_alerts():
    """
    Returns zones where FDI grew more than 5% in the last year.
    Based on simulated trend data using UNEP growth rates.
    """
    df     = get_hotspots()
    alerts = []

    for _, row in df.iterrows():
        rate        = GROWTH_RATE.get(row["severity"], 0.03)
        fdi_now     = row["fdi_score"]
        fdi_lastyear = round(fdi_now / (1 + rate), 3)
        growth_pct  = round(((fdi_now - fdi_lastyear) / fdi_lastyear) * 100, 1)

        if growth_pct >= 6.0:
            alerts.append({
                "name":       row["name"],
                "severity":   row["severity"],
                "fdi_now":    fdi_now,
                "fdi_prev":   fdi_lastyear,
                "growth_pct": growth_pct,
                "lat":        row["lat"],
                "lon":        row["lon"],
            })

    return sorted(alerts, key=lambda x: x["growth_pct"], reverse=True)

def render_alerts():
    alerts = get_alerts()

    if not alerts:
        st.caption("No significant changes detected.")
        return

    st.markdown(f"#### Active Alerts — {len(alerts)} Zones Worsening")
    st.caption("Zones where FDI score grew more than 6% in the past year.")
    st.markdown("---")

    for a in alerts:
        color = ALERT_COLOR.get(a["severity"], "#aaaaaa")
        st.markdown(f"""
        <div class="glass-card" style="margin-bottom: 12px; border-left: 4px solid {color} !important;">
            <div style="display:flex; justify-content:space-between; align-items: center;">
                <div style="color:{color}; font-size:0.75rem; font-weight:700; letter-spacing:1px; text-transform: uppercase;">
                    {a['severity']}
                </div>
                <div style="color:#FFB700; font-size:0.8rem; font-family:'Space Mono',monospace; font-weight:600;">
                    +{a['growth_pct']}% / YR
                </div>
            </div>
            <div style="color:#fff; font-weight:700; margin-top:8px; font-size:1.1rem; font-family:'Montserrat', sans-serif;">
                {a['name']}
            </div>
            <div style="color:#88aacc; font-size:0.8rem; margin-top:6px; font-family:'Space Mono',monospace;">
                {a['lat']}°, {a['lon']}°
            </div>
            <div style="display:flex; justify-content:space-between; margin-top:12px; padding-top:10px; border-top:1px solid rgba(255,183,0,0.1);">
                <span style="color:#88aacc; font-size:0.75rem;">FDI SCORE</span>
                <span style="color:#FFB700; font-weight:700; font-size:0.9rem;">{a['fdi_now']}</span>
            </div>
        </div>
        """, unsafe_allow_html=True)