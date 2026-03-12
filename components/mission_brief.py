# components/mission_brief.py
# Owned by: Naveen

import streamlit as st
import datetime
from data.hotspots import get_hotspots

SEVERITY_VESSELS = {
    "Critical": 5,
    "High":     3,
    "Medium":   2,
    "Low":      1,
}

SEVERITY_URGENCY = {
    "Critical": "IMMEDIATE — dispatch within 24 hours",
    "High":     "PRIORITY — dispatch within 72 hours",
    "Medium":   "SCHEDULED — dispatch within 2 weeks",
    "Low":      "ROUTINE — next available window",
}

def estimated_tonnes(row):
    return round((row["density"] * row["area_km2"]) / 1_000_000, 1)

def travel_time(distance_km):
    # Average cleanup vessel ~12 knots = 22.2 km/h
    hours = distance_km / 22.2
    days  = int(hours // 24)
    hrs   = int(hours % 24)
    if days > 0:
        return f"{days} days {hrs} hrs"
    return f"{hrs} hrs"

def render_mission_brief():
    st.markdown("#### Mission Brief Generator")
    st.caption("Generate a cleanup dispatch order for a selected hotspot zone.")
    st.markdown("---")

    df      = get_hotspots()
    results = st.session_state.get("results", None)

    # Use search results if available, else full list
    zones_df   = results if results is not None and not results.empty else df
    zone_names = zones_df["name"].tolist()

    selected = st.selectbox("Select target zone", zone_names)
    row      = df[df["name"] == selected].iloc[0]

    # Get distance if search was run
    distance = None
    if results is not None and not results.empty and "distance_km" in results.columns:
        match = results[results["name"] == selected]
        if not match.empty:
            distance = match["distance_km"].values[0]

    if st.button("Generate Mission Brief"):
        tonnes  = estimated_tonnes(row)
        vessels = SEVERITY_VESSELS.get(row["severity"], 1)
        urgency = SEVERITY_URGENCY.get(row["severity"], "")
        now     = datetime.datetime.utcnow().strftime("%Y-%m-%d %H:%M UTC")
        brief_id = f"MB-{datetime.datetime.utcnow().strftime('%Y%m%d%H%M')}"

        st.success(f"Mission Brief Generated — {brief_id}")
        st.markdown("---")

        # Row 1 — Zone identity
        st.markdown(f"**Target Zone:** {row['name']}")
        st.markdown(f"**Severity:** {row['severity']}")
        st.markdown(f"**Urgency:** {urgency}")
        st.markdown("---")

        # Row 2 — Location data
        c1, c2 = st.columns(2)
        with c1:
            st.metric("Latitude",  f"{row['lat']}°")
            st.metric("Longitude", f"{row['lon']}°")
        with c2:
            st.metric("FDI Score",  row["fdi_score"])
            st.metric("Density",    f"{row['density']} kg/km²")

        st.markdown("---")

        # Row 3 — Operational data
        c1, c2, c3 = st.columns(3)
        with c1:
            st.metric("Estimated Plastic Load", f"{tonnes:,} tonnes")
        with c2:
            st.metric("Affected Area",          f"{row['area_km2']:,} km²")
        with c3:
            st.metric("Vessels Required",       vessels)

        st.markdown("---")

        # Row 4 — Travel info
        c1, c2 = st.columns(2)
        with c1:
            if distance:
                st.metric("Distance from Vessel", f"{distance} km")
            else:
                st.metric("Distance from Vessel", "Search first in Map tab")
        with c2:
            if distance:
                st.metric("Estimated Travel Time", travel_time(distance))
            else:
                st.metric("Estimated Travel Time", "N/A")

        st.markdown("---")

        # Data source
        st.caption(f"Data source: {row['source']}")
        st.caption(f"Generated: {now}")

        # Plain text export
        st.markdown("---")
        st.markdown("**Plain text — copy for dispatch:**")
        st.code(f"""MISSION BRIEF {brief_id}
Generated : {now}
{'='*48}
TARGET    : {row['name']}
SEVERITY  : {row['severity']}
GPS       : {row['lat']}°, {row['lon']}°
FDI SCORE : {row['fdi_score']}
LOAD      : {tonnes:,} tonnes
AREA      : {row['area_km2']:,} km²
VESSELS   : {vessels}
DISTANCE  : {f"{distance} km" if distance else "N/A"}
TRAVEL    : {travel_time(distance) if distance else "N/A"}
URGENCY   : {urgency}
SOURCE    : {row['source']}
{'='*48}""")