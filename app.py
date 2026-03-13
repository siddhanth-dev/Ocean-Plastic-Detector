import streamlit as st
# import sys
# import os

# # Fix for broken venv relocation
# site_packages = "/home/naveen/Ocean-Plastic-Detector/venv/lib/python3.12/site-packages"
# if os.path.exists(site_packages) and site_packages not in sys.path:
#     sys.path.append(site_packages)

from components.map_view import render_map
from components.metrics import render_metrics
from components.trend_chart import render_trend
from components.mission_brief import render_mission_brief
from fdi import calculate_fdi, classify_fdi, ml_classify

SEVERITY_COLOR = {
    "Critical": "#ff2222",
    "High":     "#ff8800",
    "Medium":   "#ffcc00",
    "Low":      "#44cc44",
}

st.set_page_config(page_title="Global Plastic Ledger",page_icon="🌊", layout="wide")
st.title("Global Plastic Ledger")
st.caption("Real-Time Ocean Plastic Hotspot Tracker")
st.markdown("---")

# ── Session State ─────────────────────────────────────────────────────────────
if "results"        not in st.session_state: st.session_state.results        = None
if "searched_lat"   not in st.session_state: st.session_state.searched_lat   = 20.0
if "searched_lon"   not in st.session_state: st.session_state.searched_lon   = 0.0
if "searched_range" not in st.session_state: st.session_state.searched_range = 3000
if "click_lat"      not in st.session_state: st.session_state.click_lat      = 20.0
if "click_lon"      not in st.session_state: st.session_state.click_lon      = 0.0
if "selected_route"  not in st.session_state: st.session_state.selected_route  = None
if "route_target_name" not in st.session_state: st.session_state.route_target_name = ""

# ── Metrics ───────────────────────────────────────────────────────────────────
render_metrics()
st.markdown("---")

# ── Tabs ──────────────────────────────────────────────────────────────────────
tab1, tab2, tab3, tab4 = st.tabs([
    "Hotspot Map",
    "FDI Analyzer",
    "Pollution Trends",
    "Mission Brief"
])

with tab1:
    render_map()

with tab2:
    st.markdown("#### Satellite Band Input")
    st.caption("Adjust spectral band values to classify a satellite region.")

    col1, col2, col3 = st.columns(3)
    with col1: red  = st.slider("Red Band",  0.0, 1.0, 0.05, key="red")
    with col2: nir  = st.slider("NIR Band",  0.0, 1.0, 0.80, key="nir")
    with col3: swir = st.slider("SWIR Band", 0.0, 1.0, 0.10, key="swir")

    if st.button("Run FDI Analysis"):
        fdi_score        = calculate_fdi(red, nir, swir)
        severity, action = classify_fdi(fdi_score)
        ml_label, conf   = ml_classify(red, nir, swir)
        color            = SEVERITY_COLOR.get(severity, "#aaaaaa")

        c1, c2, c3 = st.columns(3)
        with c1: st.metric("FDI Score",  fdi_score)
        with c2: st.metric("ML Result",  ml_label)
        with c3: st.metric("Confidence", f"{conf}%")

        st.markdown(f"""
        <div style="border-left:5px solid {color}; padding:14px 18px;
                    background:#111; border-radius:6px; margin-top:16px;">
            <div style="color:{color}; font-weight:bold;">{severity.upper()}</div>
            <div style="color:#ccc; margin-top:6px;">{action}</div>
        </div>
        """, unsafe_allow_html=True)

        st.caption(f"FDI = NIR - (RED + SWIR) = {nir} - ({red} + {swir}) = {fdi_score}")

with tab3:
    render_trend()

with tab4:
    render_mission_brief()