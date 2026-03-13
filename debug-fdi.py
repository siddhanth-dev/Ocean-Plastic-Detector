# debug_fdi.py
# Run this directly to test the full FDI pipeline against known locations.
# Usage:
#   python debug_fdi.py
#   python debug_fdi.py --lat 38.0 --lon 145.0   # custom location
#
# It will tell you exactly which data path was taken, what raw band values
# came back, and where the pipeline broke if it did.

import sys
import os
import argparse
import traceback
from datetime import datetime

# ── Colour helpers (no deps) ──────────────────────────────────────────────────
G  = "\033[92m"   # green
Y  = "\033[93m"   # yellow
R  = "\033[91m"   # red
B  = "\033[94m"   # blue
W  = "\033[97m"   # white bold
NC = "\033[0m"    # reset

def ok(msg):   print(f"  {G}✓{NC} {msg}")
def warn(msg): print(f"  {Y}⚠{NC} {msg}")
def err(msg):  print(f"  {R}✗{NC} {msg}")
def info(msg): print(f"  {B}→{NC} {msg}")
def hdr(msg):  print(f"\n{W}{'─'*60}\n  {msg}\n{'─'*60}{NC}")

# ── Known test locations ───────────────────────────────────────────────────────
TEST_LOCATIONS = [
    {"name": "Great Pacific Garbage Patch", "lat": 38.0,  "lon": 145.0,  "expected": "open_ocean"},
    {"name": "Manila Bay (coastal debris)", "lat": 14.52, "lon": 120.88, "expected": "coastal"},
    {"name": "Chennai Coast (your region)", "lat": 13.08, "lon": 80.29,  "expected": "coastal"},
]

# ── Step 1: Check imports ──────────────────────────────────────────────────────
def check_imports():
    hdr("STEP 1: Checking imports")
    results = {}

    for mod in ["requests", "numpy", "tifffile", "sklearn", "ee", "streamlit"]:
        try:
            __import__(mod)
            ok(mod)
            results[mod] = True
        except ImportError as e:
            err(f"{mod} — NOT INSTALLED: {e}")
            results[mod] = False

    for mod in ["fdi", "sentinel3", "gee_service"]:
        try:
            __import__(mod)
            ok(mod)
            results[mod] = True
        except Exception as e:
            err(f"{mod} — IMPORT FAILED: {e}")
            traceback.print_exc()
            results[mod] = False

    return results

# ── Step 2: Check env vars / secrets ──────────────────────────────────────────
def check_env():
    hdr("STEP 2: Checking environment variables")

    token = os.environ.get("NASA_EARTHDATA_TOKEN", "")
    if token:
        ok(f"NASA_EARTHDATA_TOKEN is set ({len(token)} chars)")
    else:
        warn("NASA_EARTHDATA_TOKEN not set — OPeNDAP fetch will be skipped, synthetic fallback will be used")

    for var in ["GOOGLE_APPLICATION_CREDENTIALS", "EARTHENGINE_TOKEN"]:
        val = os.environ.get(var, "")
        if val:
            ok(f"{var} = {val[:40]}...")
        else:
            info(f"{var} not set (may use st.secrets or ADC instead)")

# ── Step 3: Check FDI formula directly ────────────────────────────────────────
def check_fdi_formula():
    hdr("STEP 3: Verifying FDI formula with known values")

    try:
        from fdi import calculate_fdi
        from sentinel3 import calculate_fdi_olci

        # S2: known plastic pixel from literature (Biermann et al. 2020)
        red, nir, swir = 0.047, 0.091, 0.022
        fdi = calculate_fdi(red, nir, swir)
        expected_approx = 0.04   # should be small positive for debris
        info(f"S2 FDI(red={red}, nir={nir}, swir={swir}) = {fdi}")
        if -0.1 < fdi < 0.2:
            ok(f"S2 FDI in expected range (~0.01–0.10 for debris)")
        else:
            err(f"S2 FDI = {fdi} — UNEXPECTED. Check formula in fdi.py")

        # S3 OLCI: open ocean — should be near zero or slightly negative
        oa10, oa17, oa21 = 0.0082, 0.0043, 0.0018
        fdi_s3 = calculate_fdi_olci(oa10, oa17, oa21)
        info(f"S3 FDI(oa10={oa10}, oa17={oa17}, oa21={oa21}) = {fdi_s3}")
        if -0.05 < fdi_s3 < 0.05:
            ok("S3 FDI in expected range for clean ocean (~0)")
        else:
            err(f"S3 FDI = {fdi_s3} — UNEXPECTED for clean ocean pixel")

        # Sanity: if FDI comes back as thousands, the slope is still wrong
        if abs(fdi) > 10 or abs(fdi_s3) > 10:
            err(f"FDI values are in the thousands — slope is STILL WRONG")

    except Exception as e:
        err(f"FDI formula check failed: {e}")
        traceback.print_exc()

# ── Step 4: Check CMR connectivity ────────────────────────────────────────────
def check_cmr(lat, lon):
    hdr(f"STEP 4: CMR granule search ({lat}, {lon})")
    try:
        from sentinel3 import _find_granule
        granule = _find_granule(lat, lon)
        if granule:
            ok(f"Found granule: {granule.get('producer_granule_id') or granule.get('id', 'N/A')}")
            info(f"Cloud cover: {granule.get('cloud_cover', 'N/A')}%")
            links = granule.get("links", [])
            opendap = [l["href"] for l in links if "opendap" in l.get("href","").lower()]
            if opendap:
                ok(f"OPeNDAP URL found: {opendap[0][:80]}...")
            else:
                warn("No OPeNDAP URL in granule — will use synthetic fallback")
            return granule
        else:
            warn("No granule found in last 15 days — synthetic fallback will be used")
            return None
    except Exception as e:
        err(f"CMR search failed: {e}")
        traceback.print_exc()
        return None

# ── Step 5: Check GEE connectivity ────────────────────────────────────────────
def check_gee():
    hdr("STEP 5: GEE initialisation")
    try:
        from gee_service import _init_ee
        mode = _init_ee()
        ok(f"GEE initialised — auth mode: {mode}")
        return True
    except Exception as e:
        err(f"GEE init failed: {e}")
        info("Tip: run `earthengine authenticate` or check st.secrets['gee']")
        return False

# ── Step 6: Full pipeline test ─────────────────────────────────────────────────
def run_full_pipeline(lat, lon, name):
    hdr(f"STEP 6: Full pipeline — {name} ({lat}, {lon})")

    # Shore distance
    try:
        from sentinel import distance_to_shore
        dist = distance_to_shore(lat, lon)
        info(f"Distance to shore: {dist:.1f} km")
        path = "coastal (S2)" if dist <= 20 else "open ocean (S3)"
        ok(f"Will use: {path}")
    except Exception as e:
        warn(f"Shore distance check failed: {e} — assuming open ocean")
        dist = 999

    # Run the appropriate fetch
    if dist <= 20:
        try:
            from gee_service import fetch_s2_fdi
            info("Calling fetch_s2_fdi()...")
            result, error = fetch_s2_fdi(lat, lon)
            _print_result(result, error, "S2 GEE")
        except Exception as e:
            err(f"fetch_s2_fdi crashed: {e}")
            traceback.print_exc()
    else:
        try:
            from gee_service import fetch_s3_fdi
            info("Calling fetch_s3_fdi()...")
            result, error = fetch_s3_fdi(lat, lon)
            _print_result(result, error, "S3 GEE/CMR")
        except Exception as e:
            err(f"fetch_s3_fdi crashed: {e}")
            traceback.print_exc()

def _print_result(result, error, source):
    if error:
        err(f"{source} returned error: {error}")
        return

    if not result:
        err(f"{source} returned None with no error message")
        return

    ok(f"{source} succeeded — sensor: {result.get('sensor', 'unknown')}")
    print()

    # Band values — most important diagnostic
    print(f"  {'Band Values':─<40}")
    for key in ["red","nir","swir","oa10","oa17","oa21"]:
        if key in result:
            val = result[key]
            in_range = 0.0 <= val <= 1.0
            status = f"{G}✓{NC}" if in_range else f"{R}✗ OUT OF RANGE{NC}"
            print(f"    {key:6} = {val:.5f}  {status}")

    print()
    print(f"  {'FDI & Classification':─<40}")
    fdi = result.get("fdi_score", None)
    if fdi is not None:
        if abs(fdi) > 10:
            err(f"fdi_score = {fdi}  ← STILL BROKEN (should be -0.1 to 0.2)")
        elif fdi > 0.02:
            ok(f"fdi_score = {fdi}  ← debris signal detected")
        else:
            info(f"fdi_score = {fdi}  ← clean water / no debris")

    for key in ["fdi_max","severity","action","ml_label","confidence","mode"]:
        if key in result:
            print(f"    {key:20} = {result[key]}")

    print()
    print(f"  {'Area & Mass':─<40}")
    area = result.get("detected_area_m2")
    mass = result.get("mass_kg")
    if area is not None:
        area_km2 = area / 1_000_000
        info(f"detected_area = {area:,.0f} m²  ({area_km2:.3f} km²)")
        if area > 50_000_000:
            err("Area > 50 km² — likely still disproportional, check debris_fraction calc")
        elif area > 0:
            ok("Area looks proportional")
    if mass is not None:
        info(f"mass_kg       = {mass:,.1f} kg  ({mass/1000:.1f} tonnes)")
    if result.get("mass_capped"):
        warn("mass_capped=True — result flagged as possible false positive")
    if result.get("is_synthetic"):
        warn("is_synthetic=True — no real satellite data was used")
    if result.get("flag"):
        warn(f"flag: {result['flag']}")

# ── Main ───────────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Debug FDI pipeline")
    parser.add_argument("--lat",  type=float, default=None)
    parser.add_argument("--lon",  type=float, default=None)
    parser.add_argument("--name", type=str,   default="Custom location")
    parser.add_argument("--quick", action="store_true",
                        help="Skip GEE check and full pipeline, just test formula + CMR")
    args = parser.parse_args()

    print(f"\n{W}FDI Pipeline Debug  —  {datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S')} UTC{NC}")

    imports = check_imports()
    check_env()
    check_fdi_formula()

    # Pick test location
    if args.lat and args.lon:
        locations = [{"name": args.name, "lat": args.lat, "lon": args.lon}]
    else:
        locations = TEST_LOCATIONS

    for loc in locations:
        check_cmr(loc["lat"], loc["lon"])

    if not args.quick:
        gee_ok = check_gee()
        for loc in locations:
            run_full_pipeline(loc["lat"], loc["lon"], loc["name"])

    hdr("SUMMARY")
    print("  If you saw any RED ✗ lines above, those are your bugs.")
    print("  If all values are GREEN and fdi_score is between -0.1 and 0.2,")
    print("  the pipeline is working correctly.\n")