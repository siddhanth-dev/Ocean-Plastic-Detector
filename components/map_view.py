# components/map_view.py
# Owned by: Mikhil

import streamlit as st
import folium
from streamlit_folium import st_folium
from data.hotspots import get_nearest, get_hotspots
from components.alerts import render_alerts

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
        "attr":  "NASA GIBS"
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

    # ── Session defaults ──────────────────────────────────────────────────────
    if "click_lat" not in st.session_state: st.session_state.click_lat = 20.0
    if "click_lon" not in st.session_state: st.session_state.click_lon = 0.0

    # ── Controls ──────────────────────────────────────────────────────────────
    col1, col2 = st.columns([2, 1])
    with col1:
        layer_choice = st.radio("Map Layer", options=list(MAP_LAYERS.keys()), horizontal=True)
    with col2:
        search_range = st.slider("Search Range (km)", 500, 10000, 3000, step=500)

    # Coordinate display — updates from map click
    st.caption(f"Vessel Location: {st.session_state.click_lat:.4f}, {st.session_state.click_lon:.4f} — Click map to change")

    if st.button("Find Nearby Hotspots"):
        st.session_state.results        = get_nearest(st.session_state.click_lat, st.session_state.click_lon, search_range)
        st.session_state.searched_lat   = st.session_state.click_lat
        st.session_state.searched_lon   = st.session_state.click_lon
        st.session_state.searched_range = search_range

    st.markdown("---")

    # ── Map + Alerts layout ───────────────────────────────────────────────────
    map_col, alert_col = st.columns([3, 1])

    # ── Build Map ─────────────────────────────────────────────────────────────
    layer = MAP_LAYERS[layer_choice]
    m = folium.Map(
        location=[st.session_state.searched_lat, st.session_state.searched_lon],
        zoom_start=2,
        min_zoom=2,
        zoom_control=True,
        max_bounds=True,
        tiles=layer["tiles"],
        attr=layer["attr"]
    )
    m.fit_bounds([[-75, -180], [75, 180]])
    m.options["maxBounds"] = [[-85, -180], [85, 180]]
    m.options["maxBoundsViscosity"] = 1.0

    # Vessel marker at clicked location
    folium.Marker(
        location=[st.session_state.click_lat, st.session_state.click_lon],
        tooltip="Your Vessel — click map to move",
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
        with map_col:
            st.warning("No hotspots found. Try increasing range.")

    # ── Render map + capture click ────────────────────────────────────────────
    with map_col:
        map_data = st_folium(m, width=None, height=600)

    with alert_col:
        render_alerts()

    # If user clicked on map — update vessel coordinates
    if map_data and map_data.get("last_clicked"):
        clicked = map_data["last_clicked"]
        st.session_state.click_lat = round(clicked["lat"], 4)
        st.session_state.click_lon = round(clicked["lng"], 4)
        st.rerun()

    # ── Results + Priority ────────────────────────────────────────────────────
    if results is not None and not results.empty:
        st.markdown("---")
        left, right = st.columns([1, 1])

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

    # ── Live Satellite Scan ───────────────────────────────────────────────────
    render_live_scan()

def render_live_scan():
    from sentinel import get_fdi_from_satellite

    st.markdown("---")
    st.markdown("#### Live Satellite Scan")
    st.caption("Fetch real Sentinel-2 band values for a zone and run FDI analysis.")

    df   = get_hotspots()
    zone = st.selectbox("Select zone to scan", df["name"].tolist())
    row  = df[df["name"] == zone].iloc[0]

    if st.button("Run Live Satellite Scan"):
        with st.spinner("Fetching Sentinel-2 data from Copernicus..."):
            result, error = get_fdi_from_satellite(row["lat"], row["lon"])

        if error:
            st.error(f"Scan failed: {error}")
        else:
            color = SEVERITY_COLOR.get(result["severity"], "#aaaaaa")

            c1, c2, c3, c4 = st.columns(4)
            c1.metric("Red Band",  result["red"])
            c2.metric("NIR Band",  result["nir"])
            c3.metric("SWIR Band", result["swir"])
            c4.metric("FDI Score", result["fdi_score"])

            st.markdown(f"""
            <div style="border-left:5px solid {color}; padding:14px 18px;
                        background:#111; border-radius:6px; margin-top:12px;">
                <div style="color:{color}; font-weight:bold;">{result['severity'].upper()}</div>
                <div style="color:#ccc; margin-top:4px;">
                    {result['ml_label']} — {result['confidence']}% confidence
                </div>
                <div style="color:#888; margin-top:4px; font-size:0.85rem;">{result['action']}</div>
            </div>
            """, unsafe_allow_html=True)
# def render_live_scan():
#     st.markdown("---")
#     st.markdown("#### Live Satellite Scan")
#     st.info(
#         "Sentinel-2 integration pipeline built and connected to "
#         "Copernicus Data Space API. Live band values feed directly "
#         "into the FDI classifier. Currently pending API processing "
#         "quota — available in production deployment."
#     )