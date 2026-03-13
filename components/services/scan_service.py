# components/services/scan_service.py
# Live Satellite Scan — interactive folium map picker, GEE-powered fetch,
# QA60 cloud masking, auto-triggered FDI/area/mass dashboard.
# Sensor routing: ≤ 20 km from shore → S2 (GEE), > 20 km → S3 (GEE/CMR).

import streamlit as st
import folium
from streamlit_folium import st_folium
from components.services.constants import SEVERITY_COLOR, MAP_LAYERS

SHORE_THRESHOLD_KM = 20.0
_SCAN_MAP_KEY      = "scan_map_click"   # unique st_folium key


def render_live_scan() -> None:
    """
    Full interactive Live Satellite Scan panel.

    Step 1 — Map picker: click any ocean point → captures lat/lon.
    Step 2 — Auto-scan: runs GEE fetch + FDI/area/mass dashboard immediately.
    """
    from sentinel import distance_to_shore
    from gee_service import fetch_s2_fdi, fetch_s3_fdi
    from fdi import classify_fdi, ml_classify

    st.markdown("---")
    st.markdown("#### 🛰 Live Satellite Scan")
    st.caption(
        "**Click any ocean point on the map** to instantly run a GEE-powered "
        "FDI scan for that location. "
        "Sentinel-2 SR is used within 20 km of shore; "
        "Sentinel-3 OLCI beyond."
    )

    # ── Session state defaults ─────────────────────────────────────────────────
    if "scan_lat" not in st.session_state:
        st.session_state.scan_lat = st.session_state.get("click_lat", 20.0)
    if "scan_lon" not in st.session_state:
        st.session_state.scan_lon = st.session_state.get("click_lon", 0.0)
    if "scan_result" not in st.session_state:
        st.session_state.scan_result = None
    if "scan_dist_km" not in st.session_state:
        st.session_state.scan_dist_km = None

    lat = st.session_state.scan_lat
    lon = st.session_state.scan_lon

    # ── Interactive map ────────────────────────────────────────────────────────
    layer = MAP_LAYERS.get("Dark", {"tiles": "CartoDB dark_matter", "attr": "CartoDB"})

    scan_map = folium.Map(
        location=[lat, lon],
        zoom_start=5,
        min_zoom=2,
        tiles=layer["tiles"],
        attr=layer["attr"],
    )

    # Pin current scan point
    folium.Marker(
        location=[lat, lon],
        tooltip=f"Scan point: {lat:.4f}, {lon:.4f}",
        icon=folium.Icon(color="green", icon="crosshairs", prefix="fa"),
    ).add_to(scan_map)

    # 2 km ROI circle
    folium.Circle(
        location=[lat, lon],
        radius=2000,
        color="#00e5cc",
        fill=True,
        fill_opacity=0.15,
        tooltip="2 km scan radius",
    ).add_to(scan_map)

    map_data = st_folium(scan_map, width=900, height=380, key=_SCAN_MAP_KEY)

    # ── Capture click → update state & rerun ──────────────────────────────────
    if map_data and map_data.get("last_clicked"):
        new_lat = round(map_data["last_clicked"]["lat"], 5)
        new_lon = round(map_data["last_clicked"]["lng"], 5)

        if new_lat != st.session_state.scan_lat or new_lon != st.session_state.scan_lon:
            st.session_state.scan_lat    = new_lat
            st.session_state.scan_lon    = new_lon
            st.session_state.scan_result = None   # invalidate old result
            st.session_state.scan_dist_km = None
            st.rerun()

    st.caption(
        f"📍 Scan point: **{lat:.5f}, {lon:.5f}** — click the map to change"
    )

    # ── Auto-scan on new coordinates ──────────────────────────────────────────
    if st.session_state.scan_result is None:

        with st.spinner("Measuring distance from shore…"):
            dist_km = distance_to_shore(lat, lon)
            st.session_state.scan_dist_km = dist_km

        is_coastal  = dist_km <= SHORE_THRESHOLD_KM
        sensor_name = "Sentinel-2 SR (GEE)" if is_coastal else "Sentinel-3 OLCI (GEE)"
        sensor_col  = "#00bfff"             if is_coastal else "#00e5cc"

        with st.spinner(f"Running GEE scan via {sensor_name}…"):
            if is_coastal:
                raw, error = fetch_s2_fdi(lat, lon, radius_m=2000)
            else:
                raw, error = fetch_s3_fdi(lat, lon, radius_m=2000)

        if error:
            st.error(f"Scan failed: {error}")
            return

        # Enrich with FDI classification
        fdi_val          = raw.get("fdi_score", 0)
        severity, action = classify_fdi(fdi_val)

        # ML classify — use whichever band triple is present
        b1 = raw.get("red",  raw.get("oa10", 0))
        b2 = raw.get("nir",  raw.get("oa17", 0))
        b3 = raw.get("swir", raw.get("oa21", 0))
        ml_label, conf = ml_classify(b1, b2, b3)

        st.session_state.scan_result = {
            **raw,
            "severity":   severity,
            "action":     action,
            "ml_label":   ml_label,
            "confidence": conf,
            "is_coastal": is_coastal,
            "sensor_col": sensor_col,
        }

    # ── Render dashboard ──────────────────────────────────────────────────────
    res        = st.session_state.scan_result
    dist_km    = st.session_state.scan_dist_km or 0
    is_coastal = res["is_coastal"]
    color      = SEVERITY_COLOR.get(res["severity"], "#aaaaaa")
    sensor_col = res["sensor_col"]

    # Sensor badge
    is_mock = res.get("mode", "") == "mock"
    mock_tag = "  ·  ⚠ synthetic estimate" if is_mock else ""

    st.markdown(
        f"""<div style="display:inline-block; background:#111;
        border:1px solid {sensor_col}; border-radius:20px;
        padding:4px 16px; color:{sensor_col};
        font-size:0.85rem; font-weight:600; margin-bottom:14px;">
        {res['sensor']}{mock_tag}
        &nbsp;·&nbsp; {dist_km:.1f} km from shore
        </div>""",
        unsafe_allow_html=True,
    )

    if is_mock:
        st.warning(
            "⚠️ **Mock mode** — GEE credentials not configured in `.streamlit/secrets.toml`. "
            "Band values are open-ocean climatology estimates. "
            "Add your Service Account or OAuth token to enable real GEE pixel retrieval."
        )

    # Row 1 — spectral bands
    if is_coastal:
        labels = ("Red (B04)", "NIR (B08)", "SWIR (B11)")
        vals   = (res.get("red", 0), res.get("nir", 0), res.get("swir", 0))
    else:
        labels = ("Oa10 (~681 nm)", "Oa17 (~865 nm)", "Oa21 (~1020 nm)")
        vals   = (res.get("oa10", 0), res.get("oa17", 0), res.get("oa21", 0))

    c1, c2, c3, c4 = st.columns(4)
    c1.metric(labels[0], vals[0])
    c2.metric(labels[1], vals[1])
    c3.metric(labels[2], vals[2])
    c4.metric("FDI Score", res["fdi_score"])

    # Row 2 — detection metrics (area / mass / ML)
    st.markdown("##### Detection Metrics  —  2 km ROI")

    area_m2  = res.get("detected_area_m2")
    mass_kg  = res.get("mass_kg")
    clr_pct  = res.get("clear_pixel_pct")

    d1, d2, d3, d4 = st.columns(4)
    d1.metric("Detected Area",
              f"{area_m2:,} m²" if area_m2 is not None else "N/A",
              help="Pixels where FDI > 0.01 × pixel area (100 m² for S2, 90 000 m² for S3)")
    d2.metric("Est. Plastic Mass",
              f"{mass_kg:,} kg" if mass_kg is not None else "N/A",
              help="Area × 1.5 kg/m² marine debris proxy")
    d3.metric("ML Classification", res["ml_label"],
              help=f"Confidence: {res['confidence']}%")
    d4.metric("Cloud-Free Pixels",
              f"{clr_pct:.1f}%" if clr_pct is not None else "N/A",
              help="Fraction of 2 km ROI passing QA60 cloud mask")

    # Severity card
    st.markdown(
        f"""
<div style="border-left:5px solid {color};
padding:14px 18px; background:#111;
border-radius:6px; margin-top:14px;">
<div style="color:{color}; font-weight:bold; font-size:1.1rem;">
{res['severity'].upper()}</div>
<div style="color:#ccc; margin-top:6px;">{res['action']}</div>
<div style="color:#888; margin-top:4px; font-size:0.82rem;">
{res['ml_label']} — {res['confidence']}% confidence</div>
</div>
""",
        unsafe_allow_html=True,
    )

    # FDI formula caption
    if is_coastal:
        b4, b8, b11 = vals
        baseline = round(b4 + (b11 - b4) * 0.12, 5)
        st.caption(
            f"FDI (PML) = B8 − [B4 + (B11 − B4) × 0.12] "
            f"= {b8} − [{b4} + ({b11} − {b4}) × 0.12] "
            f"= {b8} − {baseline} = **{res['fdi_score']}**"
        )
    else:
        oa10, oa17, oa21 = vals
        baseline = round(oa10 + (oa21 - oa10) * 0.12, 5)
        st.caption(
            f"FDI_S3 = Oa17 − [Oa10 + (Oa21 − Oa10) × 0.12] "
            f"= {oa17} − [{oa10} + ({oa21} − {oa10}) × 0.12] "
            f"= {oa17} − {baseline} = **{res['fdi_score']}**"
        )
