# components/metrics.py
# Owned by: Naveen
# Job: Renders 4 stat cards at the top of the page

import streamlit as st
from data.hotspots import get_hotspots

def render_metrics():
    df = get_hotspots()
    
    # Custom Glass Card CSS for metrics
    st.markdown("""
    <style>
        .metric-container {
            display: flex;
            justify-content: space-between;
            gap: 1.5rem;
            margin-bottom: 2rem;
        }
        .metric-card {
            flex: 1;
            background: rgba(0, 29, 61, 0.6);
            backdrop-filter: blur(12px);
            border: 1px solid rgba(255, 183, 0, 0.15);
            border-radius: 12px;
            padding: 1.5rem;
            text-align: left;
            transition: transform 0.3s ease, border-color 0.3s ease;
        }
        .metric-card:hover {
            transform: translateY(-5px);
            border-color: rgba(255, 183, 0, 0.4);
        }
        .metric-label {
            color: #88aacc;
            font-size: 0.85rem;
            font-weight: 500;
            text-transform: uppercase;
            letter-spacing: 0.05em;
            margin-bottom: 0.5rem;
        }
        .metric-value {
            color: #FFB700;
            font-family: 'Montserrat', sans-serif;
            font-size: 2.2rem;
            font-weight: 800;
            line-height: 1;
        }
        .metric-unit {
            font-size: 1rem;
            color: #88aacc;
            margin-left: 0.3rem;
        }
    </style>
    """, unsafe_allow_html=True)

    zones_tracked = len(df)
    critical_zones = len(df[df["severity"] == "Critical"])
    avg_fdi = round(df["fdi_score"].mean(), 2)
    total_area = f"{df['area_km2'].sum():,}"

    st.markdown(f"""
    <div class="metric-container">
        <div class="metric-card">
            <div class="metric-label">Zones Tracked</div>
            <div class="metric-value">{zones_tracked}</div>
        </div>
        <div class="metric-card">
            <div class="metric-label">Critical Zones</div>
            <div class="metric-value" style="color: #FF5400;">{critical_zones}</div>
        </div>
        <div class="metric-card">
            <div class="metric-label">Avg FDI Score</div>
            <div class="metric-value">{avg_fdi}</div>
        </div>
        <div class="metric-card">
            <div class="metric-label">Affected Area</div>
            <div class="metric-value">{total_area}<span class="metric-unit">km²</span></div>
        </div>
    </div>
    """, unsafe_allow_html=True)
