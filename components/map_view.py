# components/map_view.py
# Owned by: Mikhil
# Job: Map + hotspot results + cleanup priority ranking in one tab

import streamlit as st
import folium
from streamlit_folium import st_folium
from data.hotspots import get_nearest

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

MAP_LAYERS = {
    "Satellite (ESRI)": {
        "tiles": "https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}",
        "attr":  "ESRI World Imagery"
    },
    "NASA Blue Marble": {
        "tiles": "https://gibs.earthdata.nasa.gov/wmts/epsg3857/best/BlueMarble_NextGeneration/default/GoogleMapsCompatible_Level8/{z}/{y}/{x}.jpg",
        "attr":  "NASA GIBS — Blue Marble"
    },
    "Dark": {
        "tiles": "CartoDB dark_matter",
        "attr":  "CartoDB"
    },
}

def priority_score(row, max_range):
    w = SEVERITY_WEIGHT.get(row["severity"], 1.0)
    return round((w * row["fdi_score"]) + (row["density"] / 100) - (row["distance_km"] / max_range), 3)

def estimated_tonnes(row):
    return round((row["density"] * row["area_km2"]) / 1_000_000, 1)

def render_map():

    # ── Inputs ────────────────────────────────────────────────────────────────
    col1, col2, col3 = st.columns(3)
    with col1:
        lat          = st.number_input("Vessel Latitude",  value=20.0, step=0.1)
    with col2:
        lon          = st.number_input("Vessel Longitude", value=0.0,  step=0.1)
    with col3:
        search_range = st.slider("Search Range (km)", 500, 10000, 3000, step=500)

    layer_choice = st.radio("Map Layer", options=list(MAP_LAYERS.keys()), horizontal=True)

    if st.button("Find Nearby Hotspots"):
        st.session_state.results        = get_nearest(lat, lon, search_range)
        st.session_state.searched_lat   = lat
        st.session_state.searched_lon   = lon
        st.session_state.searched_range = search_range

    st.markdown("---")

    # ── Build Map ─────────────────────────────────────────────────────────────
    layer = MAP_LAYERS[layer_choice]
    m = folium.Map(
        location=[st.session_state.searched_lat, st.session_state.searched_lon],
        zoom_start=2,
        tiles=layer["tiles"],
        attr=layer["attr"]
    )

    folium.Marker(
        location=[st.session_state.searched_lat, st.session_state.searched_lon],
        tooltip="Your Vessel",
        icon=folium.Icon(color="blue", icon="ship", prefix="fa")
    ).add_to(m)

    results = st.session_state.results

    if results is not None and not results.empty:
        folium.Circle(
            location=[st.session_state.searched_lat, st.session_state.searched_lon],
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
                popup=folium.Popup(
                    f"<b>{row['name']}</b><br>"
                    f"Severity: {row['severity']}<br>"
                    f"FDI Score: {row['fdi_score']}<br>"
                    f"Source: {row['source']}<br>"
                    f"Distance: {row['distance_km']} km",
                    max_width=240
                )
            ).add_to(m)

    elif results is not None and results.empty:
        st.warning("No hotspots found. Try increasing the search range.")

    st_folium(m, width=None, height=500)

    # ── Results + Priority Ranking ────────────────────────────────────────────
    if results is not None and not results.empty:

        st.markdown("---")
        left, right = st.columns([1, 1])

        # Left — full results table
        with left:
            st.markdown(f"#### {len(results)} Hotspot(s) Found")
            st.dataframe(
                results[["name", "severity", "distance_km", "fdi_score", "density"]]
                .rename(columns={
                    "name":        "Zone",
                    "severity":    "Severity",
                    "distance_km": "Distance (km)",
                    "fdi_score":   "FDI Score",
                    "density":     "Density (kg/km²)"
                }),
                use_container_width=True,
                hide_index=True
            )

        # Right — top 3 priority targets
        with right:
            st.markdown("#### Top Cleanup Targets")

            ranked = results.copy()
            ranked["priority_score"] = ranked.apply(
                lambda r: priority_score(r, st.session_state.searched_range), axis=1
            )
            ranked["est_tonnes"] = ranked.apply(estimated_tonnes, axis=1)
            ranked = ranked.sort_values("priority_score", ascending=False).head(3).reset_index(drop=True)

            for i, row in ranked.iterrows():
                color = SEVERITY_COLOR.get(row["severity"], "#aaaaaa")
                st.markdown(f"""
                <div style="border-left:5px solid {color}; background:#0d0d0d;
                            border-radius:8px; padding:14px 16px; margin-bottom:12px;">
                    <div style="color:#888; font-size:0.75rem; letter-spacing:2px;">
                        PRIORITY {["1ST","2ND","3RD"][i]}
                    </div>
                    <div style="color:#eee; font-weight:bold; margin-top:4px;">
                        {row['name']}
                    </div>
                    <div style="color:#aaa; font-size:0.85rem; margin-top:6px;">
                        <span style="color:{color};">{row['severity']}</span> &nbsp;|&nbsp;
                        {row['distance_km']} km &nbsp;|&nbsp;
                        {row['est_tonnes']:,} t &nbsp;|&nbsp;
                        FDI {row['fdi_score']}
                    </div>
                </div>
                """, unsafe_allow_html=True)