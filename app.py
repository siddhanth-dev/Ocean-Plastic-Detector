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
    "Critical": "#FF5400",
    "High":     "#FF8500",
    "Medium":   "#FFB700",
    "Low":      "#FFD000",
}

st.set_page_config(page_title="Global Plastic Ledger", page_icon="🌊", layout="wide")

# ── Global CSS Overhaul ───────────────────────────────────────────────────────
st.markdown("""
<style>
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600&family=Montserrat:wght@700;800&family=Space+Mono&display=swap');

    :root {
        --deep-navy: #000814;
        --secondary-navy: #001D3D;
        --amber: #FFB700;
        --text-bright: #E0E0E0;
        --text-dim: #88aacc;
    }

    /* Global Typography */
    html, body, [class*="st-"] {
        font-family: 'Inter', sans-serif !important;
    }
    
    h1, h2, h3, h4, h5, h6 {
        font-family: 'Montserrat', sans-serif !important;
        font-weight: 700 !important;
        letter-spacing: -0.02em !important;
    }

    /* Glassmorphism utility */
    .glass-card {
        background: rgba(0, 29, 61, 0.6) !important;
        backdrop-filter: blur(12px) !important;
        -webkit-backdrop-filter: blur(12px) !important;
        border: 1px solid rgba(255, 183, 0, 0.1) !important;
        border-radius: 12px !important;
        padding: 20px !important;
        box-shadow: 0 8px 32px 0 rgba(0, 0, 0, 0.3) !important;
    }

    /* Tab overhaul */
    .stTabs [data-baseweb="tab-list"] {
        gap: 24px;
        background-color: transparent !important;
    }
    .stTabs [data-baseweb="tab"] {
        height: 50px;
        background-color: transparent !important;
        border: none !important;
        color: var(--text-dim) !important;
        font-weight: 600 !important;
        font-size: 1rem !important;
    }
    .stTabs [aria-selected="true"] {
        color: var(--amber) !important;
        border-bottom: 2px solid var(--amber) !important;
    }

    /* Header styling */
    .main-title {
        font-size: 3.5rem !important;
        background: linear-gradient(135deg, #fff 0%, var(--amber) 100%);
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
        margin-bottom: 0px !important;
    }
    .sub-caption {
        font-size: 1.1rem !important;
        color: var(--text-dim) !important;
        letter-spacing: 0.1em !important;
        text-transform: uppercase !important;
        font-weight: 500 !important;
    }
</style>
""", unsafe_allow_html=True)

st.markdown('<h1 class="main-title">Global Plastic Ledger</h1>', unsafe_allow_html=True)
st.markdown('<p class="sub-caption">Real-Time Ocean Plastic Hotspot Tracker</p>', unsafe_allow_html=True)
st.markdown("<br>", unsafe_allow_html=True)

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
                    background:#001D3D; border-radius:6px; margin-top:16px;">
            <div style="color:{color}; font-weight:bold;">{severity.upper()}</div>
            <div style="color:#eee; margin-top:6px;">{action}</div>
        </div>
        """, unsafe_allow_html=True)

        st.caption(f"FDI = NIR - (RED + SWIR) = {nir} - ({red} + {swir}) = {fdi_score}")

with tab3:
    render_trend()

with tab4:
    render_mission_brief()