import pandas as pd

HOTSPOTS = [
    {"name": "Great Pacific Garbage Patch (East)", "lat": 35.0, "lon": -140.0,
     "density": 94.2, "severity": "Critical", "area_km2": 1600000, "fdi_score": 0.87},

    {"name": "Great Pacific Garbage Patch (West)", "lat": 38.0, "lon": 155.0,
     "density": 76.5, "severity": "Critical", "area_km2": 980000, "fdi_score": 0.81},

    {"name": "North Atlantic Garbage Patch", "lat": 30.0, "lon": -40.0,
     "density": 58.3, "severity": "High", "area_km2": 700000, "fdi_score": 0.71},

    {"name": "Indian Ocean Garbage Patch", "lat": -30.0, "lon": 80.0,
     "density": 45.1, "severity": "High", "area_km2": 500000, "fdi_score": 0.63},

    {"name": "South Atlantic Accumulation Zone", "lat": -28.0, "lon": -15.0,
     "density": 32.7, "severity": "Medium", "area_km2": 310000, "fdi_score": 0.54},

    {"name": "Mediterranean Sea Hotspot", "lat": 35.5, "lon": 18.0,
     "density": 41.8, "severity": "High", "area_km2": 95000, "fdi_score": 0.67},

    {"name": "South Pacific Convergence Zone", "lat": -42.0, "lon": -100.0,
     "density": 28.4, "severity": "Medium", "area_km2": 270000, "fdi_score": 0.49},

    {"name": "Bay of Bengal Coastal Sink", "lat": 13.0, "lon": 86.0,
     "density": 22.9, "severity": "Medium", "area_km2": 80000, "fdi_score": 0.44},

    {"name": "Arctic Microplastic Sink", "lat": 78.0, "lon": 10.0,
     "density": 15.2, "severity": "Low", "area_km2": 45000, "fdi_score": 0.31},

    {"name": "Southeast Asia Coastal Zone", "lat": 8.0, "lon": 112.0,
     "density": 62.4, "severity": "Critical", "area_km2": 420000, "fdi_score": 0.78},
]

def get_hotspots():
    return pd.DataFrame(HOTSPOTS)

def get_by_severity(severity):
    df = get_hotspots()
    return df[df["severity"] == severity]

def get_nearest(vessel_lat, vessel_lon, max_range_km=1000):
    import math
    df = get_hotspots()
    def distance(row):
        dlat = math.radians(row["lat"] - vessel_lat)
        dlon = math.radians(row["lon"] - vessel_lon)
        a = math.sin(dlat/2)**2 + math.cos(math.radians(vessel_lat)) * \
            math.cos(math.radians(row["lat"])) * math.sin(dlon/2)**2
        return round(6371 * 2 * math.asin(math.sqrt(a)), 1)
    df["distance_km"] = df.apply(distance, axis=1)
    return df[df["distance_km"] <= max_range_km].sort_values("distance_km")
