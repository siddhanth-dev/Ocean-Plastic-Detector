# components/services/constants.py
# Shared constants for map styling, severity levels, and tile layers.

SEVERITY_COLOR = {
    "Critical": "#FF5400",
    "High":     "#FF8500",
    "Medium":   "#FFB700",
    "Low":      "#FFD000",
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
