# sentinel.py
# Owned by: Siddhanth

import requests
import numpy as np
import io
import tifffile
from fdi import calculate_fdi, classify_fdi, ml_classify

CLIENT_ID     = "sh-8b1fcf79-492b-46fc-8721-185d55b6d2b5"
CLIENT_SECRET = "24VgZm2mFiqwbWjpJLst9WclfRsZRj2s"
TOKEN_URL     = "https://identity.dataspace.copernicus.eu/auth/realms/CDSE/protocol/openid-connect/token"
PROCESS_URL   = "https://sh.dataspace.copernicus.eu/api/v1/process"

def get_access_token():
    r = requests.post(TOKEN_URL, data={
        "grant_type":    "client_credentials",
        "client_id":     CLIENT_ID,
        "client_secret": CLIENT_SECRET,
    })
    r.raise_for_status()
    return r.json()["access_token"]

def get_fdi_from_satellite(lat, lon, delta=1.0):
    try:
        token = get_access_token()
    except Exception as e:
        return None, f"Auth failed: {e}"

    bbox = [lon - delta, lat - delta, lon + delta, lat + delta]

    evalscript = """
    //VERSION=3
    function setup() {
        return {
            input: [{ bands: ["B04", "B08", "B11"], units: "REFLECTANCE" }],
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
                "properties": {"crs": "http://www.opengis.net/def/crs/EPSG/0/4326"}
            },
            "data": [{
                "type": "sentinel-2-l2a",
                "dataFilter": {
                    "timeRange": {
                        "from": "2024-01-01T00:00:00Z",
                        "to":   "2024-12-31T23:59:59Z"
                    },
                    "mosaickingOrder": "leastCC",
                    "maxCloudCoverage": 30
                }
            }]
        },
        "output": {
            "width":  300,
            "height": 300,
            "responses": [{
                "identifier": "default",
                "format": {"type": "image/tiff"}
            }]
        },
        "evalscript": evalscript
    }

    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type":  "application/json",
        "Accept":        "image/tiff"
    }

    r = requests.post(PROCESS_URL, json=payload, headers=headers)

    if r.status_code != 200:
        return None, f"API error: {r.status_code} — {r.text[:200]}"

    try:
        arr  = tifffile.imread(io.BytesIO(r.content))
        red  = round(float(np.nanmean(arr[:, :, 0])), 4)
        nir  = round(float(np.nanmean(arr[:, :, 1])), 4)
        swir = round(float(np.nanmean(arr[:, :, 2])), 4)
    except Exception as e:
        return None, f"Parsing failed: {e}"

    fdi_score        = calculate_fdi(red, nir, swir)
    severity, action = classify_fdi(fdi_score)
    ml_label, conf   = ml_classify(red, nir, swir)

    return {
        "red":        red,
        "nir":        nir,
        "swir":       swir,
        "fdi_score":  fdi_score,
        "severity":   severity,
        "action":     action,
        "ml_label":   ml_label,
        "confidence": conf
    }, None