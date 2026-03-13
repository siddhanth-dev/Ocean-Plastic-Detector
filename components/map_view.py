# components/map_view.py
# Owned by: Mikhil

import streamlit as st
import folium
import plotly.graph_objects as go
from streamlit_folium import st_folium

from data.hotspots import get_nearest, get_hotspots
from components.alerts import render_alerts

from components.services.constants import SEVERITY_COLOR, MAP_LAYERS
from components.services.geo_service import is_land
from components.services.scoring_service import priority_score, estimated_tonnes
from components.services.route_service import calculate_maritime_route


# ── Sidebar PML Scan ──────────────────────────────────────────────────────────
def _render_pml_sidebar():
    """
    Sidebar panel that appears after a map click.
    Shows: sensor badge, band metrics, area/mass/severity cards,
    spectral signature chart, and FDI formula caption.
    """
    from gee_service import fetch_s2_fdi, fetch_s3_fdi
    from sentinel import distance_to_shore
    from fdi import classify_fdi, ml_classify

    lat = st.session_state.get("pml_lat")
    lon = st.session_state.get("pml_lon")

    if lat is None or lon is None:
        st.sidebar.markdown(
            "<div style='color:#555;font-size:0.85rem;margin-top:40px;"
            "text-align:center;'>Click any ocean point on the map<br>"
            "to analyse it with GEE.</div>",
            unsafe_allow_html=True,
        )
        return

    st.sidebar.markdown("#### 🛰 PML Satellite Scan")
    st.sidebar.markdown(
        f"<div style='background:#111;border-radius:8px;padding:8px 12px;"
        f"font-size:0.82rem;color:#aaa;margin-bottom:10px;'>"
        f"📍 <b style='color:#eee;'>{lat:.5f}, {lon:.5f}</b></div>",
        unsafe_allow_html=True,
    )

    if st.sidebar.button("▶ Run PML Scan", use_container_width=True):
        with st.sidebar:
            with st.spinner("Routing sensor…"):
                dist_km = distance_to_shore(lat, lon)
            is_coastal = dist_km <= 20.0

            with st.spinner(
                "Fetching S2 SR…" if is_coastal else "Fetching S3 OLCI…"
            ):
                if is_coastal:
                    raw, error = fetch_s2_fdi(lat, lon, radius_m=2000)
                else:
                    raw, error = fetch_s3_fdi(lat, lon, radius_m=2000)

        if error:
            st.sidebar.error(f"Scan failed: {error}")
            return

        # Enrich with classification
        severity, action = classify_fdi(raw["fdi_score"])
        b1 = raw.get("red",  raw.get("oa10", 0))
        b2 = raw.get("nir",  raw.get("oa17", 0))
        b3 = raw.get("swir", raw.get("oa21", 0))
        ml_label, conf = ml_classify(b1, b2, b3)

        st.session_state.pml_result = {
            **raw,
            "severity":   severity,
            "action":     action,
            "ml_label":   ml_label,
            "confidence": conf,
            "is_coastal": is_coastal,
            "dist_km":    dist_km,
        }

    res = st.session_state.get("pml_result")
    if not res:
        return

    # ── Sensor badge ──────────────────────────────────────────────────────────
    is_coastal  = res["is_coastal"]
    sensor_col  = "#00bfff" if is_coastal else "#00e5cc"
    color       = SEVERITY_COLOR.get(res["severity"], "#aaaaaa")

    st.sidebar.markdown(
        f"<div style='display:inline-block;border:1px solid {sensor_col};"
        f"border-radius:14px;padding:3px 12px;color:{sensor_col};"
        f"font-size:0.78rem;font-weight:600;margin-bottom:10px;'>"
        f"{res['sensor']} · {res.get('dist_km', 0):.1f} km from shore</div>",
        unsafe_allow_html=True,
    )

    # ── Band metric row ───────────────────────────────────────────────────────
    with st.sidebar.container():
        if is_coastal:
            labels = ("B04 Red", "B08 NIR", "B11 SWIR")
            vals   = (res.get("red", 0), res.get("nir", 0), res.get("swir", 0))
        else:
            labels = ("Oa10", "Oa17", "Oa21")
            vals   = (res.get("oa10", 0), res.get("oa17", 0), res.get("oa21", 0))

        c1, c2, c3 = st.sidebar.columns(3)
        c1.metric(labels[0], vals[0])
        c2.metric(labels[1], vals[1])
        c3.metric(labels[2], vals[2])

    # ── Detection metrics row ─────────────────────────────────────────────────
    st.sidebar.markdown("**Detection — 2 km ROI**")
    d1, d2 = st.sidebar.columns(2)
    area = res.get("detected_area_m2")
    mass = res.get("mass_kg")
    d1.metric("Area",  f"{area:,} m²" if area is not None else "N/A")
    d2.metric("Mass",  f"{mass:,} kg" if mass is not None else "N/A")

    fdi_col = "#ff2222" if res["fdi_score"] > 0.4 else (
              "#ffcc00" if res["fdi_score"] > 0.1 else "#44cc44")
    st.sidebar.metric("FDI Score", res["fdi_score"],
                      delta=f"{res['fdi_score']:+.4f}",
                      delta_color="normal")

    # ── Severity card ─────────────────────────────────────────────────────────
    st.sidebar.markdown(
        f"<div style='border-left:4px solid {color};padding:10px 14px;"
        f"background:#111;border-radius:6px;margin:6px 0;'>"
        f"<div style='color:{color};font-weight:bold;font-size:1rem;'>"
        f"{res['severity'].upper()}</div>"
        f"<div style='color:#ccc;font-size:0.82rem;margin-top:4px;'>{res['action']}</div>"
        f"<div style='color:#888;font-size:0.78rem;margin-top:2px;'>"
        f"{res['ml_label']} — {res['confidence']}% conf.</div></div>",
        unsafe_allow_html=True,
    )

    # ── Spectral Signature chart ──────────────────────────────────────────────
    st.sidebar.markdown("**Spectral Signature**")

    band_names = list(labels)
    band_vals  = list(vals)

    # Reference open-ocean baseline values for the same bands
    if is_coastal:
        baseline = [0.020, 0.012, 0.005]   # clean ocean: low Red, very low NIR/SWIR
        plastic_ref = [0.050, 0.180, 0.030] # typical plastic: NIR spike
    else:
        baseline = [0.010, 0.008, 0.004]
        plastic_ref = [0.025, 0.090, 0.015]

    fig = go.Figure()

    fig.add_trace(go.Bar(
        name="Measured",
        x=band_names,
        y=band_vals,
        marker_color=[sensor_col] * 3,
        opacity=0.9,
    ))
    fig.add_trace(go.Scatter(
        name="Clean Ocean",
        x=band_names,
        y=baseline,
        mode="lines+markers",
        line=dict(color="#4488ff", dash="dot", width=1.5),
        marker=dict(size=6),
    ))
    fig.add_trace(go.Scatter(
        name="Plastic Reference",
        x=band_names,
        y=plastic_ref,
        mode="lines+markers",
        line=dict(color="#ff6600", dash="dash", width=1.5),
        marker=dict(size=6),
    ))

    fig.update_layout(
        paper_bgcolor="#0d0d0d",
        plot_bgcolor="#111",
        font=dict(color="#aaa", size=10),
        legend=dict(
            font=dict(size=9),
            bgcolor="#111",
            bordercolor="#333",
            borderwidth=1,
            orientation="h",
            y=-0.25,
        ),
        margin=dict(l=0, r=0, t=10, b=40),
        height=200,
        yaxis=dict(
            title="Reflectance",
            gridcolor="#222",
            title_font=dict(size=9),
        ),
        xaxis=dict(gridcolor="#222"),
        bargap=0.35,
    )

    st.sidebar.plotly_chart(fig, use_container_width=True, config={"displayModeBar": False})

    # Formula caption
    if is_coastal:
        b4, b8, b11 = vals
        bl = round(b4 + (b11 - b4) * 0.12, 5)
        st.sidebar.caption(
            f"FDI = B8 − [B4 + (B11 − B4)×0.12] = {b8} − {bl} = **{res['fdi_score']}**"
        )
    else:
        o10, o17, o21 = vals
        bl = round(o10 + (o21 - o10) * 0.12, 5)
        st.sidebar.caption(
            f"FDI = Oa17 − [Oa10 + (Oa21 − Oa10)×0.12] = {o17} − {bl} = **{res['fdi_score']}**"
        )


# ── Main Map ──────────────────────────────────────────────────────────────────
def render_map():

    # ── Session defaults ─────────────────────────────
    if "map_center"    not in st.session_state: st.session_state.map_center    = [20.0, 0.0]
    if "map_zoom"      not in st.session_state: st.session_state.map_zoom      = 2
    if "click_lat"     not in st.session_state: st.session_state.click_lat     = 20.0
    if "click_lon"     not in st.session_state: st.session_state.click_lon     = 0.0
    if "route_origin"  not in st.session_state: st.session_state.route_origin  = (None, None)
    if "selected_route"    not in st.session_state: st.session_state.selected_route    = None
    if "route_target_name" not in st.session_state: st.session_state.route_target_name = None
    if "route_bounds"  not in st.session_state: st.session_state.route_bounds  = None
    if "results"       not in st.session_state: st.session_state.results       = None
    if "searched_lat"  not in st.session_state: st.session_state.searched_lat  = st.session_state.click_lat
    if "searched_lon"  not in st.session_state: st.session_state.searched_lon  = st.session_state.click_lon
    if "searched_range"    not in st.session_state: st.session_state.searched_range    = 3000
    if "pml_lat"       not in st.session_state: st.session_state.pml_lat       = None
    if "pml_lon"       not in st.session_state: st.session_state.pml_lon       = None
    if "pml_result"    not in st.session_state: st.session_state.pml_result    = None

    # ── Controls ─────────────────────────────────────
    controls, spacer = st.columns([3, 5])

    with controls:
        c1, c2 = st.columns(2)

        with c1:
            layer_choice = st.radio(
                "Map Layer",
                options=list(MAP_LAYERS.keys()),
                horizontal=True,
            )

        with c2:
            search_range = st.slider(
                "Search Range (km)",
                500, 10000, 3000, step=500,
            )

    st.caption(
        f"Vessel Location: {st.session_state.click_lat:.4f}, "
        f"{st.session_state.click_lon:.4f} — Click map to move"
    )

    st.markdown("---")

    map_col, alert_col = st.columns([3, 1])

    layer = MAP_LAYERS[layer_choice]

    m = folium.Map(
        location=st.session_state.map_center,
        zoom_start=st.session_state.map_zoom,
        min_zoom=2,
        zoom_control=True,
        max_bounds=True,
        tiles=layer["tiles"],
        attr=layer["attr"],
    )

    m.fit_bounds([[-75, -180], [75, 180]])

    # Vessel marker
    folium.Marker(
        location=[st.session_state.click_lat, st.session_state.click_lon],
        tooltip="Your Vessel — click map to move",
        icon=folium.Icon(color="blue", icon="ship", prefix="fa"),
    ).add_to(m)

    results = st.session_state.results

    if results is not None and not results.empty:

        folium.Circle(
            location=[st.session_state.searched_lat, st.session_state.searched_lon],
            radius=st.session_state.searched_range * 1000,
            color="#ffffff",
            fill=False,
            weight=1,
            dash_array="6",
        ).add_to(m)

        for _, row in results.iterrows():
            color = SEVERITY_COLOR.get(row["severity"], "#aaaaaa")
            folium.CircleMarker(
                location=[row["lat"], row["lon"]],
                radius=14,
                color=color,
                fill=True,
                fill_color=color,
                fill_opacity=0.5,
                tooltip=f"{row['name']} — {row['distance_km']} km away",
                popup=row["name"],
            ).add_to(m)

    # ── Route ────────────────────────────────────────
    if st.session_state.selected_route:
        folium.PolyLine(
            locations=st.session_state.selected_route,
            color="#00ffff",
            weight=4,
            opacity=0.8,
            dash_array="10,10",
            tooltip=f"Route to {st.session_state.route_target_name}",
        ).add_to(m)

        folium.Marker(
            location=st.session_state.selected_route[-1],
            icon=folium.Icon(color="red", icon="flag", prefix="fa"),
            tooltip=f"Destination: {st.session_state.route_target_name}",
        ).add_to(m)

        if st.session_state.route_bounds:
            m.fit_bounds(st.session_state.route_bounds)

    # ── PML scan analysis circle ──────────────────────────────────────────────
    pml_lat = st.session_state.pml_lat
    pml_lon = st.session_state.pml_lon

    if pml_lat is not None and pml_lon is not None:
        folium.Circle(
            location=[pml_lat, pml_lon],
            radius=2000,
            color="#00e5cc",
            fill=True,
            fill_opacity=0.12,
            weight=2,
            dash_array="6 4",
            tooltip=f"PML Analysis ROI — {pml_lat:.4f}, {pml_lon:.4f}",
        ).add_to(m)

        folium.Marker(
            location=[pml_lat, pml_lon],
            icon=folium.Icon(color="green", icon="crosshairs", prefix="fa"),
            tooltip="Scan point",
        ).add_to(m)

    with map_col:
        map_data = st_folium(m, width=1050, height=600)

    with alert_col:
        render_alerts()

    # ── Vessel Move + Scan Point Capture ─────────────────────────────────────
    if map_data and map_data.get("last_clicked"):

        lat = round(map_data["last_clicked"]["lat"], 4)
        lon = round(map_data["last_clicked"]["lng"], 4)

        if is_land(lat, lon):
            st.warning("Selected location is on land. Please click on water.")
        else:
            # Update vessel position
            st.session_state.click_lat  = lat
            st.session_state.click_lon  = lon
            st.session_state.map_center = [lat, lon]
            st.session_state.map_zoom   = 6

            st.session_state.results = get_nearest(lat, lon, search_range)
            st.session_state.searched_lat   = lat
            st.session_state.searched_lon   = lon
            st.session_state.searched_range = search_range

            # Route to priority hotspot
            if not st.session_state.results.empty:
                calculate_maritime_route(st.session_state.results.iloc[0]["name"])
            else:
                st.session_state.selected_route    = None
                st.session_state.route_target_name = None
                st.session_state.route_bounds       = None

            # Stage PML scan (clears previous result)
            if st.session_state.pml_lat != lat or st.session_state.pml_lon != lon:
                st.session_state.pml_lat    = lat
                st.session_state.pml_lon    = lon
                st.session_state.pml_result = None

            st.rerun()

    # ── Hotspot Click Routing ──────────────────────────────────────────────────
    if map_data and map_data.get("last_object_clicked_popup"):
        hotspot_name = map_data["last_object_clicked_popup"]
        if hotspot_name:
            calculate_maritime_route(hotspot_name)
            st.rerun()

    # ── Results Table + Priority Panel ────────────────────────────────────────
    if results is not None and not results.empty:

        st.markdown("---")
        left, right = st.columns([1, 1])

        with left:
            st.markdown(f"#### {len(results)} Hotspot(s) Found")
            st.dataframe(
                results[[
                    "name", "severity", "distance_km", "fdi_score", "density"
                ]].rename(columns={
                    "name":        "Zone",
                    "severity":    "Severity",
                    "distance_km": "Distance (km)",
                    "fdi_score":   "FDI Score",
                    "density":     "Density (kg/km²)",
                }),
                use_container_width=True,
                hide_index=True,
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
                st.markdown(
                    f"""
<div style="border-left:5px solid {color};background:#0d0d0d;
border-radius:8px;padding:14px 16px;margin-bottom:12px;">
<div style="color:#888;font-size:0.75rem;letter-spacing:2px;">
PRIORITY {["1ST","2ND","3RD"][i]}</div>
<div style="color:#eee;font-weight:bold;margin-top:4px;">{row['name']}</div>
<div style="color:#aaa;font-size:0.85rem;margin-top:6px;">
<span style="color:{color};">{row['severity']}</span>
&nbsp;|&nbsp; {row['distance_km']} km
&nbsp;|&nbsp; {row['est_tonnes']:,} t
&nbsp;|&nbsp; FDI {row['fdi_score']}
</div></div>
""",
                    unsafe_allow_html=True,
                )

    # ── Sidebar PML panel ─────────────────────────────────────────────────────
    _render_pml_sidebar()