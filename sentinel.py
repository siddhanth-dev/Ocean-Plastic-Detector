# sentinel.py
# Owned by: Siddhanth
# Job: Fetches real Sentinel-2 band values for a GPS location
#      then runs FDI on actual satellite data

import requests
from fdi import calculate_fdi, classify_fdi, ml_classify

# ── Your Copernicus credentials ───────────────────────────────────────────────
CLIENT_ID     = "sh-8b1fcf79-492b-46fc-8721-185d55b6d2b5"
CLIENT_SECRET = "24VgZm2mFiqwbWjpJLst9WclfRsZRj2s"
TOKEN_URL     = "https://identity.dataspace.copernicus.eu/auth/realms/CDSE/protocol/openid-connect/token"
PROCESS_URL   = "https://sh.dataspace.copernicus.eu/api/v1/process"

def get_access_token():
    """Get OAuth token from Copernicus"""
    response = requests.post(TOKEN_URL, data={
        "grant_type":    "client_credentials",
        "client_id":     CLIENT_ID,
        "client_secret": CLIENT_SECRET,
    })
    response.raise_for_status()
    return response.json()["access_token"]

def get_fdi_from_satellite(lat, lon, delta=0.05):
    """
    Given a GPS coordinate, fetches real Sentinel-2 band values
    and returns FDI score + classification.

    delta controls bounding box size (~5km at equator)
    """
    token = get_access_token()

    # Bounding box around the coordinate
    bbox = [lon - delta, lat - delta, lon + delta, lat + delta]

    # Evalscript — runs on Copernicus servers on real satellite data
    # Returns mean Red, NIR, SWIR values for the bounding box
    evalscript = """
    //VERSION=3
    function setup() {
        return {
            input: [{ bands: ["B04", "B08", "B11"] }],
            output: { bands: 3, sampleType: "FLOAT32" }
        };
    }
    function evaluatePixel(sample) {
        return [sample.B04, sample.B08, sample.B11];
    }
    """

    payload = {
        "input": {
            "bounds": {
                "bbox": bbox,
                "properties": {"crs": "http://www.opengis.net/def/crs/OGC/1.3/CRS84"}
            },
            "data": [{
                "type": "sentinel-2-l2a",
                "dataFilter": {
                    "timeRange": {
                        "from": "2024-01-01T00:00:00Z",
                        "to":   "2024-12-31T23:59:59Z"
                    },
                    "mosaickingOrder": "leastCC"  # least cloud cover
                }
            }]
        },
        "output": {
            "width":  10,
            "height": 10,
            "responses": [{"identifier": "default", "format": {"type": "application/json"}}]
        },
        "evalscript": evalscript
    }

    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type":  "application/json",
        "Accept":        "application/json"
    }

    response = requests.post(PROCESS_URL, json=payload, headers=headers)

    if response.status_code != 200:
        return None, f"API error: {response.status_code}"

    # Parse returned band means
    data   = response.json()
    pixels = data.get("data", [])

    if not pixels:
        return None, "No satellite data available for this location"

    # Average band values across returned pixels
    red_vals  = [p[0] for p in pixels]
    nir_vals  = [p[1] for p in pixels]
    swir_vals = [p[2] for p in pixels]

    red  = round(sum(red_vals)  / len(red_vals),  4)
    nir  = round(sum(nir_vals)  / len(nir_vals),  4)
    swir = round(sum(swir_vals) / len(swir_vals), 4)

    # Run your FDI formula on real values
    fdi_score        = calculate_fdi(red, nir, swir)
    severity, action = classify_fdi(fdi_score)
    ml_label, conf   = ml_classify(red, nir, swir)

    return {
        "red":       red,
        "nir":       nir,
        "swir":      swir,
        "fdi_score": fdi_score,
        "severity":  severity,
        "action":    action,
        "ml_label":  ml_label,
        "confidence": conf
    }, None