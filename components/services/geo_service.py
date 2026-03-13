# components/services/geo_service.py
# Handles land polygon loading and land/ocean classification.

import geopandas as gpd
from shapely.geometry import Point
import streamlit as st


@st.cache_resource
def load_land_polygons():
    return gpd.read_file("data/ne_10m_land.shp")


LAND = load_land_polygons()


def is_land(lat: float, lon: float) -> bool:
    """Return True if the given coordinate falls on land."""
    point = Point(lon, lat)
    return LAND.contains(point).any()
