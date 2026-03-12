import streamlit as st
import folium
from streamlit_folium import st_folium
from data.hotspots import get_nearest, get_hotspots
from fdi import calculate_fdi, classify_fdi, ml_classify

SEVERITY_COLOR = {
    "Critical": "#ff2222",
    "High":     "#ff8800",
    "Medium":   "#ffcc00",
    "Low":      "#44cc44",
}

SEVERITY_WEIGHT = {
    "Critical": 2.0,
    "High":     1.5,
    "Medium":   1.0,
    "Low":      0.5,
}

def priority_score(row, max_range):
    sweight  = SEVERITY_WEIGHT.get(row["severity"], 1.0)
    score    = (sweight * row["fdi_score"]) + (row["density"] / 100) - (row["distance_km"] / max_range)
    return round(score, 3)

def estimated_tonnes(row):
    return round((row["density"] * row["area_km2"]) / 1_000_000, 1)

st.set_page_config(page_title="Global Plastic Ledger", layout="wide")
st.title("Global Plastic Ledger")
st.caption("Real-Time Ocean Plastic Hotspot Tracker")
st.markdown("---")

# ── Session State ─────────────────────────────────────────────────────────────
if "results"        not in st.session_state: st.session_state.results        = None
if "searched_lat"   not in st.session_state: st.session_state.searched_lat   = 20.0
if "searched_lon"   not in st.session_state: st.session_state.searched_lon   = 0.0
if "searched_range" not in st.session_state: st.session_state.searched_range = 3000

# ── Tabs ──────────────────────────────────────────────────────────────────────
tab1, tab2, tab3 = st.tabs(["Hotspot Map", "FDI Analyzer", "Cleanup Priority"])

# ═══════════════════════════════════════════════════════════════════════════════
# TAB 1 — MAP
# ═══════════════════════════════════════════════════════════════════════════════
with tab1:
    col1, col2, col3 = st.columns(3)
    with col1:
        vessel_lat = st.number_input("Vessel Latitude",  value=20.0, step=0.1)
    with col2:
        vessel_lon = st.number_input("Vessel Longitude", value=0.0,  step=0.1)
    with col3:
        max_range  = st.slider("Search Range (km)", 500, 10000, 3000, step=500)

    if st.button("Find Nearby Hotspots"):
        st.session_state.results        = get_nearest(vessel_lat, vessel_lon, max_range)
        st.session_state.searched_lat   = vessel_lat
        st.session_state.searched_lon   = vessel_lon
        st.session_state.searched_range = max_range

    st.markdown("---")

    center_lat = st.session_state.searched_lat
    center_lon = st.session_state.searched_lon

    m = folium.Map(location=[center_lat, center_lon],
                   zoom_start=2, tiles="CartoDB dark_matter")

    folium.Marker(
        location=[center_lat, center_lon],
        tooltip="Your Vessel",
        icon=folium.Icon(color="blue", icon="ship", prefix="fa")
    ).add_to(m)

    results = st.session_state.results
    if results is not None:
        if results.empty:
            st.warning("No hotspots found. Try increasing the search range.")
        else:
            folium.Circle(
                location=[center_lat, center_lon],
                radius=st.session_state.searched_range * 1000,
                color="#ffffff", fill=False, weight=1, dash_array="6"
            ).add_to(m)

            for _, row in results.iterrows():
                color = SEVERITY_COLOR.get(row["severity"], "#aaaaaa")
                folium.CircleMarker(
                    location=[row["lat"], row["lon"]],
                    radius=14,
                    color=color, fill=True, fill_color=color, fill_opacity=0.5,
                    tooltip=f"{row['name']} — {row['distance_km']} km away",
                    popup=folium.Popup(f"""
                        <b>{row['name']}</b><br>
                        Severity: {row['severity']}<br>
                        FDI Score: {row['fdi_score']}<br>
                        Density: {row['density']} kg/km²<br>
                        Distance: {row['distance_km']} km
                    """, max_width=220)
                ).add_to(m)

            st.markdown(f"#### {len(results)} Hotspot(s) Found Within {st.session_state.searched_range} km")
            st.dataframe(
                results[["name", "severity", "distance_km", "fdi_score", "density"]]
                .rename(columns={
                    "name":        "Zone",
                    "severity":    "Severity",
                    "distance_km": "Distance (km)",
                    "fdi_score":   "FDI Score",
                    "density":     "Density (kg/km²)"
                }),
                use_container_width=True, hide_index=True
            )

    st_folium(m, width=None, height=520)

# ═══════════════════════════════════════════════════════════════════════════════
# TAB 2 — FDI ANALYZER
# ═══════════════════════════════════════════════════════════════════════════════
with tab2:
    st.markdown("#### Satellite Band Input")
    st.caption("Adjust the spectral band values from satellite imagery to classify a zone.")

    col1, col2, col3 = st.columns(3)
    with col1:
        red  = st.slider("Red Band",  0.0, 1.0, 0.05, key="red")
    with col2:
        nir  = st.slider("NIR Band",  0.0, 1.0, 0.80, key="nir")
    with col3:
        swir = st.slider("SWIR Band", 0.0, 1.0, 0.10, key="swir")

    st.markdown("---")

    if st.button("Run FDI Analysis"):
        fdi_score        = calculate_fdi(red, nir, swir)
        severity, action = classify_fdi(fdi_score)
        ml_label, conf   = ml_classify(red, nir, swir)
        color            = SEVERITY_COLOR.get(severity, "#aaaaaa")

        c1, c2, c3 = st.columns(3)
        with c1:
            st.metric("FDI Score", fdi_score)
        with c2:
            st.metric("ML Result", ml_label)
        with c3:
            st.metric("Confidence", f"{conf}%")

        st.markdown(f"""
        <div style="
            border-left: 5px solid {color};
            padding: 14px 18px;
            background: #111;
            border-radius: 6px;
            margin-top: 16px;
        ">
            <div style="color:{color}; font-weight:bold; font-size:1.1rem;">
                {severity.upper()}
            </div>
            <div style="color:#ccc; margin-top:6px; font-size:0.95rem;">{action}</div>
        </div>
        """, unsafe_allow_html=True)

        st.markdown("---")
        st.markdown("#### How this works")
        st.markdown(f"""
        The **Floating Debris Index** is calculated as:

        `FDI = NIR - (RED + SWIR)`

        With your inputs:
        `FDI = {nir} - ({red} + {swir}) = {fdi_score}`

        Plastic has a characteristically **high NIR reflectance** and **low RED/SWIR**,
        giving it a high FDI score. Water, algae, and sea foam score near zero or negative.
        The ML classifier confirms this using a Random Forest model
        trained on labeled spectral signatures.
        """)

# ═══════════════════════════════════════════════════════════════════════════════
# TAB 3 — CLEANUP PRIORITY RANKER
# ═══════════════════════════════════════════════════════════════════════════════
with tab3:
    st.markdown("#### Cleanup Priority Ranker")
    st.caption("Enter your vessel location and range to get a ranked list of cleanup targets.")

    col1, col2, col3 = st.columns(3)
    with col1:
        p_lat   = st.number_input("Vessel Latitude",  value=20.0, step=0.1, key="p_lat")
    with col2:
        p_lon   = st.number_input("Vessel Longitude", value=0.0,  step=0.1, key="p_lon")
    with col3:
        p_range = st.slider("Search Range (km)", 500, 10000, 5000, step=500, key="p_range")

    if st.button("Generate Priority List"):
        candidates = get_nearest(p_lat, p_lon, p_range)

        if candidates.empty:
            st.warning("No hotspots found within range. Try increasing the search range.")
        else:
            candidates["priority_score"] = candidates.apply(
                lambda row: priority_score(row, p_range), axis=1
            )
            candidates["est_tonnes"] = candidates.apply(estimated_tonnes, axis=1)
            ranked = candidates.sort_values("priority_score", ascending=False).head(3).reset_index(drop=True)

            st.markdown("---")
            st.markdown("#### Top Cleanup Targets")

            for i, row in ranked.iterrows():
                color  = SEVERITY_COLOR.get(row["severity"], "#aaaaaa")
                rank   = i + 1
                medals = ["1ST", "2ND", "3RD"]

                st.markdown(f"""
                <div style="
                    border-left: 6px solid {color};
                    background: #0d0d0d;
                    border-radius: 8px;
                    padding: 16px 20px;
                    margin-bottom: 14px;
                ">
                    <div style="display:flex; justify-content:space-between; align-items:center;">
                        <div style="font-size:0.8rem; color:#888; font-weight:bold; letter-spacing:2px;">
                            PRIORITY {medals[i]}
                        </div>
                        <div style="font-size:0.85rem; color:#555;">
                            Score: {row['priority_score']}
                        </div>
                    </div>
                    <div style="font-size:1.15rem; font-weight:bold; color:#eee; margin-top:6px;">
                        {row['name']}
                    </div>
                    <div style="display:flex; gap:32px; margin-top:10px; font-size:0.88rem; color:#aaa;">
                        <div><span style="color:{color}; font-weight:bold;">{row['severity']}</span></div>
                        <div>FDI: <b style="color:#eee;">{row['fdi_score']}</b></div>
                        <div>Distance: <b style="color:#eee;">{row['distance_km']} km</b></div>
                        <div>Est. Plastic: <b style="color:#eee;">{row['est_tonnes']:,} tonnes</b></div>
                    </div>
                    <div style="margin-top:10px; font-size:0.85rem; color:#888;">
                        Coords: {row['lat']}°, {row['lon']}°
                    </div>
                </div>
                """, unsafe_allow_html=True)

            st.markdown("---")
            st.markdown("#### Scoring Formula")
            st.markdown("""
            Each zone is scored using:

            `Priority Score = (Severity Weight × FDI Score) + (Density / 100) - (Distance / Max Range)`

            Severity weights: Critical = 2.0, High = 1.5, Medium = 1.0, Low = 0.5

            Higher score = clean this first.
            """)
