# sentinel.py
# Owned by: Siddhanth

import requests
import numpy as np
import io
import math
import tifffile
from datetime import datetime, timedelta
from fdi import calculate_fdi, classify_fdi, ml_classify


# ── Shore-Distance Helper ──────────────────────────────────────────────────────
def distance_to_shore(lat: float, lon: float, threshold_km: float = 20.0) -> float:
    """
    Return the approximate minimum distance (km) from (lat, lon) to the
    nearest land boundary, using the already-cached LAND GeoDataFrame.

    Samples boundary vertices from every polygon rather than doing a full
    nearest-point calculation, which is fast enough for a single query.
    A result > threshold_km reliably identifies open-ocean positions.
    """
    from components.services.geo_service import LAND
    from shapely.geometry import Point

    query_pt = Point(lon, lat)

    min_dist_km = float("inf")

    for geom in LAND.geometry:
        # Get exterior coords of each polygon (and any interior rings)
        try:
            exteriors = [geom.exterior] if hasattr(geom, "exterior") else \
                        [g.exterior for g in geom.geoms]
        except Exception:
            continue

        for ring in exteriors:
            # Sample every 5th vertex to keep it fast
            coords = list(ring.coords)[::5]
            for lnd_lon, lnd_lat in coords:
                # Haversine approximation
                dlat = math.radians(lnd_lat - lat)
                dlon = math.radians(lnd_lon - lon)
                a = (math.sin(dlat / 2) ** 2
                     + math.cos(math.radians(lat))
                     * math.cos(math.radians(lnd_lat))
                     * math.sin(dlon / 2) ** 2)
                dist_km = 6371.0 * 2 * math.asin(math.sqrt(a))
                if dist_km < min_dist_km:
                    min_dist_km = dist_km
                    if min_dist_km < 1.0:   # early exit — definitely coastal
                        return min_dist_km

    return min_dist_km

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

def calculate_fdi_map(red, nir, swir):
    """
    Compute FDI per pixel.

    FDI = NIR − (RED + (SWIR − RED) * (λNIR − λRED)/(λSWIR − λRED))

    All bands must be in REFLECTANCE units (0.0 – 1.0) and at the same
    spatial resolution before calling this function.
    """
    lambda_red  = 665
    lambda_nir  = 842
    lambda_swir = 1610

    baseline = red + (swir - red) * ((lambda_nir - lambda_red) / (lambda_swir - lambda_red))

    return nir - baseline

def get_fdi_from_satellite(lat, lon, delta=0.02):
    try:
        token = get_access_token()
    except Exception as e:
        return None, f"Auth failed: {e}"

    bbox = [lon - delta, lat - delta, lon + delta, lat + delta]

    end   = datetime.utcnow()
    start = end - timedelta(days=30)

    # ── FIX: request all three bands in REFLECTANCE units.
    # B11 (SWIR) is natively 20 m while B04/B08 are 10 m.
    # By setting resx/resy to 20 m in the output block, Sentinel Hub
    # resamples B04 and B08 down to 20 m, giving all three bands the
    # same scale and preventing the ~337 000 raw-DN value that was
    # corrupting the FDI baseline term.
    evalscript = """
    //VERSION=3
    function setup() {
        return {
            input: [{
                bands: ["B04", "B08", "B11"],
                units: "REFLECTANCE"   // ensures 0-1 float output for every band
            }],
            output: { bands: 3, sampleType: "FLOAT32" }
        };
    }
    function evaluatePixel(sample) {
        return [
            sample.B04,   // index 0 → Red   (665 nm)
            sample.B08,   // index 1 → NIR   (842 nm)
            sample.B11    // index 2 → SWIR  (1610 nm)
        ];
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
                        "from": start.strftime("%Y-%m-%dT%H:%M:%SZ"),
                        "to":   end.strftime("%Y-%m-%dT%H:%M:%SZ"),
                    },
                    "mosaickingOrder": "leastCC",
                    "maxCloudCoverage": 80
                }
            }]
        },
        "output": {
            "width":  64,
            "height": 64,
            # ── FIX: lock output to 20 m (SWIR native res) so all bands
            # are resampled to the same resolution and reflectance range.
            "resx": 20,
            "resy": 20,
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
        arr = tifffile.imread(io.BytesIO(r.content))

        # Guard against unexpected array shapes
        if arr.ndim != 3 or arr.shape[2] < 3:
            return None, f"Unexpected TIFF shape: {arr.shape}"

        red_band  = arr[:, :, 0].astype(np.float32)
        nir_band  = arr[:, :, 1].astype(np.float32)
        swir_band = arr[:, :, 2].astype(np.float32)

        # Sanity-check: reflectance values must be in [0, 1].
        # If they're not, the band units are wrong — fail loudly.
        for name, band in [("Red", red_band), ("NIR", nir_band), ("SWIR", swir_band)]:
            valid = band[np.isfinite(band)]
            if valid.size > 0 and (valid.max() > 2.0 or valid.min() < -0.5):
                return None, (
                    f"{name} band values out of reflectance range "
                    f"(min={valid.min():.4f}, max={valid.max():.4f}). "
                    "Check that evalscript units are set to REFLECTANCE."
                )

        # Compute FDI map
        fdi_map = calculate_fdi_map(red_band, nir_band, swir_band)

        # Remove invalid pixels
        fdi_map = np.where(np.isfinite(fdi_map), fdi_map, np.nan)

        # Strongest anomaly
        fdi_score = float(np.nanmax(fdi_map))

        # Representative spectral values (scene averages)
        red  = float(np.nanmean(red_band))
        nir  = float(np.nanmean(nir_band))
        swir = float(np.nanmean(swir_band))

    except Exception as e:
        return None, f"Parsing failed: {e}"

    try:
        severity, action    = classify_fdi(fdi_score)
        ml_label, conf      = ml_classify(red, nir, swir)
    except Exception as e:
        return None, f"FDI computation failed: {e}"

    result = {
        "red":        round(red,       5),
        "nir":        round(nir,       5),
        "swir":       round(swir,      5),
        "fdi_score":  round(fdi_score, 6),
        "severity":   severity,
        "action":     action,
        "ml_label":   ml_label,
        "confidence": conf,
    }

    return result, None