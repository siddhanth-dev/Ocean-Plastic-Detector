#!/usr/bin/env python3
"""
test_gee_scan.py — verifies GEE auth and runs a live S2 pixel fetch
for coordinates (12.97, 77.59) — Bangalore / Vembanad-area proxy.

Reads credentials directly from .streamlit/secrets.toml so this
can run outside a Streamlit context.
"""

import sys
import os

# ── Allow imports from project root ───────────────────────────────────────────
sys.path.insert(0, os.path.dirname(__file__))

try:
    import tomllib          # Python 3.11+
except ModuleNotFoundError:
    try:
        import tomli as tomllib     # pip install tomli
    except ModuleNotFoundError:
        import tomllib  # will raise – handled below

from datetime import datetime, timedelta

LAT, LON = 12.97, 77.59
RADIUS_M  = 2000

# ─────────────────────────────────────────────────────────────────────────────
def load_secrets(path=".streamlit/secrets.toml"):
    try:
        with open(path, "rb") as f:
            return tomllib.load(f)
    except Exception as e:
        print(f"[FAIL] Could not read secrets.toml: {e}")
        sys.exit(1)


def init_ee_direct(sa: str, key: str):
    """Initialise EE using the Service Account credentials directly."""
    import ee
    credentials = ee.ServiceAccountCredentials(sa, key_data=key)
    ee.Initialize(credentials, opt_url="https://earthengine.googleapis.com")
    print(f"[OK]   ee.Initialize() succeeded — mode: service_account")
    return True


def qa60_mask(img):
    import ee
    qa = img.select("QA60")
    mask = (qa.bitwiseAnd(1 << 10).eq(0)
              .And(qa.bitwiseAnd(1 << 11).eq(0)))
    return img.updateMask(mask).divide(10_000)


def run_s2_fetch(lat, lon):
    import ee

    roi   = ee.Geometry.Point([lon, lat]).buffer(RADIUS_M)
    end   = datetime.utcnow()
    start = end - timedelta(days=60)

    col = (ee.ImageCollection("COPERNICUS/S2_SR_HARMONIZED")
           .filterBounds(roi)
           .filterDate(start.strftime("%Y-%m-%d"), end.strftime("%Y-%m-%d"))
           .filter(ee.Filter.lt("CLOUDY_PIXEL_PERCENTAGE", 80))
           .map(qa60_mask)
           .select(["B4", "B8", "B11"]))

    count = col.size().getInfo()
    print(f"[INFO] Scenes found in last 60 days: {count}")

    if count == 0:
        print("[WARN] No cloud-free scenes — try a nearby ocean point instead.")
        return

    mosaic = col.median()

    fdi_img = mosaic.expression(
        "NIR - (RED + (SWIR - RED) * 0.12)",
        {"NIR": mosaic.select("B8"),
         "RED": mosaic.select("B4"),
         "SWIR": mosaic.select("B11")}
    ).rename("FDI")

    stats = mosaic.addBands(fdi_img).reduceRegion(
        reducer  = ee.Reducer.mean().combine(ee.Reducer.max(), sharedInputs=False),
        geometry = roi,
        scale    = 10,
        maxPixels= 1e7,
    ).getInfo()

    red      = round(stats.get("B4_mean",   0) or 0, 5)
    nir      = round(stats.get("B8_mean",   0) or 0, 5)
    swir     = round(stats.get("B11_mean",  0) or 0, 5)
    fdi_mean = round(stats.get("FDI_mean",  0) or 0, 6)
    fdi_max  = round(stats.get("FDI_max",   0) or 0, 6)

    baseline = round(red + (swir - red) * 0.12, 5)

    print()
    print("=" * 52)
    print("  GEE S2 SCAN RESULT")
    print(f"  Coords  : {lat}, {lon}")
    print(f"  ROI     : {RADIUS_M} m radius")
    print(f"  Scenes  : {count}")
    print("─" * 52)
    print(f"  Red  (B04) : {red}")
    print(f"  NIR  (B08) : {nir}")
    print(f"  SWIR (B11) : {swir}")
    print("─" * 52)
    print(f"  FDI formula: B8 - [B4 + (B11 - B4) * 0.12]")
    print(f"             = {nir} - [{red} + ({swir} - {red}) * 0.12]")
    print(f"             = {nir} - {baseline}")
    print(f"  FDI mean   : {fdi_mean}")
    print(f"  FDI max    : {fdi_max}")
    print("=" * 52)
    print()
    print("[OK]   Real GEE pixels confirmed — credentials are working.")


# ─────────────────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    print(f"[TEST] GEE pixel fetch — ({LAT}, {LON})\n")

    secrets = load_secrets()
    gee_sec = secrets.get("gee", {})

    sa  = gee_sec.get("service_account", "").strip()
    key = gee_sec.get("private_key", "").strip()

    if not sa or not key:
        print("[FAIL] No service_account or private_key in .streamlit/secrets.toml")
        sys.exit(1)

    print(f"[OK]   Service account : {sa}")
    print(f"[OK]   Private key     : {'*' * 20}  (loaded, {len(key)} chars)")
    print()

    # Step 1 — verify auth
    try:
        init_ee_direct(sa, key)
    except Exception as e:
        print(f"[FAIL] ee.Initialize() failed: {e}")
        sys.exit(1)

    # Step 2 — fetch S2 pixels
    print(f"\n[INFO] Fetching S2 SR data for ({LAT}, {LON}) …\n")
    try:
        run_s2_fetch(LAT, LON)
    except Exception as e:
        print(f"[FAIL] S2 fetch threw: {e}")
        sys.exit(1)
