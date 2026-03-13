# components/services/route_service.py
# Maritime route calculation using the searoute library.

import searoute
import streamlit as st
from data.hotspots import get_hotspots


def calculate_maritime_route(target_name: str) -> None:
    """
    Calculate and store a maritime route from the current vessel location
    to the selected hotspot.

    Updates st.session_state:
        selected_route
        route_origin
        route_target_name
        route_bounds
    """

    df = get_hotspots()
    match = df[df["name"] == target_name]

    if match.empty:
        return

    row = match.iloc[0]

    origin = [st.session_state.click_lon, st.session_state.click_lat]
    dest = [row["lon"], row["lat"]]

    try:
        route_data = searoute.searoute(origin, dest)
        raw_coords = route_data["geometry"]["coordinates"]

        # Convert [lon, lat] → [lat, lon]
        route_coords = [[c[1], c[0]] for c in raw_coords]

        if not route_coords:
            return

        # Force route start at vessel
        route_coords[0] = [
            st.session_state.click_lat,
            st.session_state.click_lon
        ]

        # Force route end at hotspot
        route_coords[-1] = [
            row["lat"],
            row["lon"]
        ]

        # Store route
        st.session_state.selected_route = route_coords
        st.session_state.route_origin = (
            st.session_state.click_lat,
            st.session_state.click_lon
        )
        st.session_state.route_target_name = target_name

        # Calculate route bounds for auto-zoom
        lats = [p[0] for p in route_coords]
        lons = [p[1] for p in route_coords]

        st.session_state.route_bounds = [
            [min(lats), min(lons)],
            [max(lats), max(lons)]
        ]

    except Exception as e:
        st.error(f"Routing failed: {e}")