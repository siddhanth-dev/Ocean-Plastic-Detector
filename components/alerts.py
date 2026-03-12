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
    "Critical": "#ff2222",
    "High":     "#ff8800",
    "Medium":   "#ffcc00",
    "Low":      "#44cc44",
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
        <div style="
            border-left: 4px solid {color};
            background: #080f1c;
            border-radius: 4px;
            padding: 12px 16px;
            margin-bottom: 10px;
        ">
            <div style="display:flex; justify-content:space-between;">
                <div style="color:{color}; font-size:0.7rem; letter-spacing:2px; font-family:'Space Mono',monospace;">
                    {a['severity'].upper()}
                </div>
                <div style="color:#ff4444; font-size:0.75rem; font-family:'Space Mono',monospace;">
                    +{a['growth_pct']}% THIS YEAR
                </div>
            </div>
            <div style="color:#c8d8e8; font-weight:bold; margin-top:6px; font-size:0.9rem;">
                {a['name']}
            </div>
            <div style="color:#445566; font-size:0.75rem; margin-top:4px; font-family:'Space Mono',monospace;">
                FDI: {a['fdi_prev']} &rarr; {a['fdi_now']} &nbsp;|&nbsp; {a['lat']}°, {a['lon']}°
            </div>
        </div>
        """, unsafe_allow_html=True)