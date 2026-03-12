import pandas as pd
import math

# Sources:
# - Eriksen et al. 2014, PLOS ONE — 5 subtropical gyres
# - Lebreton et al. 2018, Scientific Reports — GPGP extent
# - Lebreton et al. 2024, Environmental Research Letters — GPGP growth
# - Lavers & Bond 2017, PNAS — Henderson Island
# - Nakajima et al. 2024, Marine Pollution Bulletin — Seto Inland Sea
# - UNEP 2021 — From Pollution to Solution — SE Asia
# - Frontiers in Marine Science 2021 — Indian coastal accumulation zones
# - Scientific Reports 2024 — Southern Ocean microplastic hotspots
# - ACS Environmental Science & Technology 2024 — North Pacific hotspots
# - Law et al. 2010, Science — North Atlantic

HOTSPOTS = [

    # ── THE 5 MAJOR GYRE PATCHES ──────────────────────────────────────────────
    {
        "name": "Great Pacific Garbage Patch (East)",
        "lat": 38.0, "lon": -145.0,
        "severity": "Critical", "density": 94.2, "area_km2": 1600000,
        "fdi_score": 0.87,
        "source": "Lebreton et al. 2018, Scientific Reports"
    },
    {
        "name": "Great Pacific Garbage Patch (West)",
        "lat": 35.0, "lon": 158.0,
        "severity": "Critical", "density": 68.0, "area_km2": 980000,
        "fdi_score": 0.79,
        "source": "Eriksen et al. 2014, PLOS ONE"
    },
    {
        "name": "North Atlantic Garbage Patch",
        "lat": 28.0, "lon": -45.0,
        "severity": "High", "density": 55.0, "area_km2": 700000,
        "fdi_score": 0.71,
        "source": "Law et al. 2010, Science"
    },
    {
        "name": "South Atlantic Garbage Patch",
        "lat": -32.0, "lon": -15.0,
        "severity": "High", "density": 38.0, "area_km2": 400000,
        "fdi_score": 0.61,
        "source": "Eriksen et al. 2014, PLOS ONE"
    },
    {
        "name": "Indian Ocean Garbage Patch",
        "lat": -28.0, "lon": 80.0,
        "severity": "High", "density": 45.0, "area_km2": 500000,
        "fdi_score": 0.65,
        "source": "Eriksen et al. 2014, PLOS ONE"
    },
    {
        "name": "South Pacific Garbage Patch",
        "lat": -38.0, "lon": -95.0,
        "severity": "High", "density": 33.0, "area_km2": 350000,
        "fdi_score": 0.58,
        "source": "Eriksen et al. 2014, PLOS ONE"
    },

    # ── NORTH PACIFIC SECONDARY HOTSPOTS (ACS 2024) ───────────────────────────
    {
        "name": "Papahanaumokuakea Marine Monument Hotspot",
        "lat": 25.0, "lon": -170.0,
        "severity": "Critical", "density": 78.4, "area_km2": 362000,
        "fdi_score": 0.83,
        "source": "ACS Environmental Science & Technology 2024"
    },
    {
        "name": "North Pacific Subtropical Convergence Zone",
        "lat": 32.0, "lon": -155.0,
        "severity": "High", "density": 52.0, "area_km2": 280000,
        "fdi_score": 0.69,
        "source": "ACS Environmental Science & Technology 2024"
    },

    # ── INDIAN COASTAL ZONES (Frontiers Marine Science 2021) ─────────────────
    {
        "name": "Gulf of Khambhat Accumulation Zone",
        "lat": 21.5, "lon": 72.5,
        "severity": "High", "density": 44.0, "area_km2": 22000,
        "fdi_score": 0.64,
        "source": "Frontiers in Marine Science 2021"
    },
    {
        "name": "Andaman and Nicobar Islands Sink",
        "lat": 11.5, "lon": 92.5,
        "severity": "Medium", "density": 28.0, "area_km2": 35000,
        "fdi_score": 0.51,
        "source": "Frontiers in Marine Science 2021"
    },
    {
        "name": "Lakshadweep Islands Accumulation Zone",
        "lat": 10.5, "lon": 72.5,
        "severity": "Medium", "density": 24.0, "area_km2": 18000,
        "fdi_score": 0.46,
        "source": "Frontiers in Marine Science 2021"
    },

    # ── SOUTHERN OCEAN (Scientific Reports 2024) ──────────────────────────────
    {
        "name": "Antarctic Peninsula Microplastic Hotspot",
        "lat": -63.0, "lon": -58.0,
        "severity": "Medium", "density": 19.0, "area_km2": 55000,
        "fdi_score": 0.42,
        "source": "Scientific Reports 2024 — Southern Ocean Microplastics"
    },
    {
        "name": "South Georgia Island Accumulation Zone",
        "lat": -54.5, "lon": -37.0,
        "severity": "Low", "density": 12.0, "area_km2": 28000,
        "fdi_score": 0.29,
        "source": "Scientific Reports 2024 — Southern Ocean Microplastics"
    },

    # ── COASTAL HOTSPOTS ──────────────────────────────────────────────────────
    {
        "name": "Henderson Island Accumulation Zone",
        "lat": -24.4, "lon": -128.3,
        "severity": "High", "density": 671.6, "area_km2": 43,
        "fdi_score": 0.74,
        "source": "Lavers & Bond 2017, PNAS"
    },
    {
        "name": "Mediterranean Sea Plastic Sink",
        "lat": 35.5, "lon": 18.0,
        "severity": "High", "density": 41.8, "area_km2": 95000,
        "fdi_score": 0.66,
        "source": "Eriksen et al. 2014, PLOS ONE"
    },
    {
        "name": "Seto Inland Sea Convergence Zone",
        "lat": 34.3, "lon": 133.5,
        "severity": "Medium", "density": 18.5, "area_km2": 9000,
        "fdi_score": 0.41,
        "source": "Nakajima et al. 2024, Marine Pollution Bulletin"
    },
    {
        "name": "Bay of Bengal Coastal Sink",
        "lat": 13.0, "lon": 86.0,
        "severity": "Medium", "density": 22.9, "area_km2": 80000,
        "fdi_score": 0.44,
        "source": "Eriksen et al. 2014, PLOS ONE"
    },
    {
        "name": "Southeast Asia Coastal Accumulation Zone",
        "lat": 8.0, "lon": 110.0,
        "severity": "Critical", "density": 62.4, "area_km2": 420000,
        "fdi_score": 0.78,
        "source": "UNEP 2021 — From Pollution to Solution"
    },
    {
        "name": "Arctic Microplastic Sink",
        "lat": 78.0, "lon": 10.0,
        "severity": "Low", "density": 15.2, "area_km2": 45000,
        "fdi_score": 0.31,
        "source": "Montes et al. 2025, Nature"
    },
    {
        "name": "Black Sea Plastic Accumulation Zone",
        "lat": 42.5, "lon": 34.0,
        "severity": "Medium", "density": 26.0, "area_km2": 42000,
        "fdi_score": 0.48,
        "source": "Eriksen et al. 2014, PLOS ONE"
    },
    {
        "name": "Yellow Sea Coastal Hotspot",
        "lat": 36.0, "lon": 123.0,
        "severity": "High", "density": 48.0, "area_km2": 67000,
        "fdi_score": 0.68,
        "source": "UNEP 2021 — From Pollution to Solution"
    },
]

def get_hotspots():
    return pd.DataFrame(HOTSPOTS)

def get_by_severity(severity):
    df = get_hotspots()
    return df[df["severity"] == severity]

def get_nearest(vessel_lat, vessel_lon, max_range_km=1000):
    df = get_hotspots()

    def haversine(row):
        R    = 6371
        dlat = math.radians(row["lat"] - vessel_lat)
        dlon = math.radians(row["lon"] - vessel_lon)
        a    = (math.sin(dlat/2)**2 +
                math.cos(math.radians(vessel_lat)) *
                math.cos(math.radians(row["lat"])) *
                math.sin(dlon/2)**2)
        return round(R * 2 * math.asin(math.sqrt(a)), 1)

    df["distance_km"] = df.apply(haversine, axis=1)
    return df[df["distance_km"] <= max_range_km].sort_values("distance_km").reset_index(drop=True)