# sentinel3.py
# Sentinel-3 OLCI open-ocean FDI fetcher via NASA Earthdata CMR.
# Used automatically when the selected hotspot is >20 km from shore.

import os
import requests
import numpy as np
from datetime import datetime, timedelta
from fdi import classify_fdi, ml_classify

# ── NASA Earthdata endpoints ───────────────────────────────────────────────────
CMR_SEARCH_URL = "https://cmr.earthdata.nasa.gov/search/granules.json"

# Short name for Sentinel-3 OLCI L2 full resolution land/water product
# (OL_2_LFR___ or OL_2_WFR___ — we prefer the water product for open ocean)
COLLECTION_SHORT_NAME = "SENTINEL-3_OLCI_L2_WFR"

# Oa10 ≈ 681.25 nm  (red-edge / chlorophyll absorption)
# Oa17 ≈ 865.00 nm  (NIR narrow / floating debris baseline)
# Oa21 ≈ 1020.0 nm  (NIR broad / SWIR proxy for FDI)
OLCI_BANDS = ("Oa10", "Oa17", "Oa21")

# ── FIX: Define constants that were used in get_fdi_from_sentinel3() but
# never declared, causing NameError at runtime.
MASS_PROXY = 1.5        # kg per m² (empirical debris density estimate)
MASS_CAP   = 500_000.0  # kg — cap to flag likely false positives / high turbidity


# ── FDI adapted for OLCI bands ─────────────────────────────────────────────────
def calculate_fdi_olci(oa10: float, oa17: float, oa21: float) -> float:
    """
    PML-adapted FDI for Sentinel-3 OLCI.

    FDI_S3 = Oa17 − [Oa10 + (Oa21 − Oa10) × slope]

    Bands:
        Oa10 (~681 nm)  — red-edge, plays role of RED anchor
        Oa17 (~865 nm)  — NIR narrow, floating debris signal
        Oa21 (~1020 nm) — NIR broad, SWIR proxy (closest available on OLCI)

    Correct slope = (λOa17 − λOa10) / (λOa21 − λOa10)
                  = (865 − 681) / (1020 − 681)
                  = 184 / 339
                  ≈ 0.5428

    The old slope of 0.12 was copied from an S2 approximation and is
    incorrect for OLCI wavelengths — it underestimates the baseline and
    produces grossly inflated FDI scores (as seen with the ~29 000 values).
    """
    # ── FIX: correct spectral slope for OLCI wavelengths
    slope    = (865 - 681) / (1020 - 681)   # ≈ 0.5428
    baseline = oa10 + (oa21 - oa10) * slope
    return round(oa17 - baseline, 6)


# ── CMR Granule Search ─────────────────────────────────────────────────────────
def _find_granule(lat: float, lon: float, delta: float = 1.5) -> dict | None:
    """
    Query NASA CMR for the most recent OLCI L2 granule that intersects
    the bounding box around (lat, lon).  Returns the first granule entry
    or None if nothing found.
    """
    end   = datetime.utcnow()
    start = end - timedelta(days=15)

    params = {
        "short_name":      COLLECTION_SHORT_NAME,
        "temporal":        f"{start.strftime('%Y-%m-%dT%H:%M:%SZ')},"
                           f"{end.strftime('%Y-%m-%dT%H:%M:%SZ')}",
        "bounding_box":    f"{lon - delta},{lat - delta},{lon + delta},{lat + delta}",
        "sort_key":        "-start_date",
        "page_size":       1,
    }

    try:
        r = requests.get(CMR_SEARCH_URL, params=params, timeout=10)
        r.raise_for_status()
        entries = r.json().get("feed", {}).get("entry", [])
        return entries[0] if entries else None
    except Exception:
        return None


# ── OPeNDAP Band Extraction ────────────────────────────────────────────────────
def _fetch_olci_bands_opendap(opendap_url: str) -> tuple[float, float, float] | None:
    """
    Download mean Oa10, Oa17, Oa21 reflectance values from an OLCI
    OPeNDAP endpoint using a NASA Earthdata Bearer token.

    Returns (oa10, oa17, oa21) as floats, or None on any error.
    Requires env var NASA_EARTHDATA_TOKEN.
    """
    token = os.environ.get("NASA_EARTHDATA_TOKEN", "")
    if not token:
        return None

    session = requests.Session()
    session.headers.update({"Authorization": f"Bearer {token}"})

    values = {}
    for band in OLCI_BANDS:
        # OPeNDAP ASCII endpoint for a specific variable
        url = f"{opendap_url}/{band}_reflectance.ascii?{band}_reflectance[0:1:63][0:1:63]"
        try:
            r = session.get(url, timeout=20)
            if r.status_code != 200:
                return None
            # Parse ASCII grid — values follow the header after a blank line
            lines = r.text.strip().split("\n")
            data_lines = [l for l in lines if l and not l.startswith(band)]
            nums = []
            for line in data_lines:
                for tok in line.split(","):
                    tok = tok.strip()
                    if tok:
                        try:
                            val = float(tok)
                            if 0.0 <= val <= 1.5:   # valid reflectance range
                                nums.append(val)
                        except ValueError:
                            pass
            if nums:
                values[band] = float(np.nanmean(nums))
            else:
                return None
        except Exception:
            return None

    if len(values) < 3:
        return None

    return values["Oa10"], values["Oa17"], values["Oa21"]


# ── Synthetic Fallback ─────────────────────────────────────────────────────────
def _synthetic_estimate(
    granule: dict,
    red_hint: float | None = None,
    nir_hint: float | None = None,
    swir_hint: float | None = None,
) -> tuple[float, float, float, bool]:
    """
    Derive plausible OLCI reflectances that are spectrally consistent with
    Sentinel-2 values (when available) or open-ocean climatology (when not).

    S2 → S3 OLCI band mapping (by wavelength proximity):
        S2 B4  (665 nm)  ≈  Oa10 (681 nm)  — small red-edge correction ~+8%
        S2 B8  (842 nm)  ≈  Oa17 (865 nm)  — very close, minor NIR slope ~+3%
        S2 B11 (1610 nm) →  Oa21 (1020 nm) — different region; empirical ratio ~0.35

    When S2 hints are not available, falls back to open-ocean climatology
    scaled by cloud cover from CMR metadata.

    Returns (oa10, oa17, oa21, is_synthetic=True).
    """
    if red_hint is not None and nir_hint is not None and swir_hint is not None:
        # ── S2-guided path ────────────────────────────────────────────────────
        # Oa10 (~681 nm) ≈ B4 (665 nm) with a small positive red-edge offset
        oa10 = red_hint  * 1.08

        # Oa17 (~865 nm) ≈ B8 (842 nm) with a small NIR slope correction
        oa17 = nir_hint  * 1.03

        # Oa21 (~1020 nm): no direct S2 equivalent.
        # Empirically ocean Oa21 ≈ 0.35 × B11 (water absorption rises past 1000 nm)
        oa21 = swir_hint * 0.35

        oa10 = round(min(max(oa10, 0.0), 1.0), 5)
        oa17 = round(min(max(oa17, 0.0), 1.0), 5)
        oa21 = round(min(max(oa21, 0.0), 1.0), 5)

    else:
        # ── Climatology path (no S2 data available) ───────────────────────────
        cloud_str = (granule.get("cloud_cover") or "50")
        try:
            cloud = float(cloud_str) / 100.0
        except (ValueError, TypeError):
            cloud = 0.5

        oa10_clear = 0.0082
        oa17_clear = 0.0043
        oa21_clear = 0.0018
        cloud_add  = cloud * 0.015

        oa10 = round(oa10_clear + cloud_add, 5)
        oa17 = round(oa17_clear + cloud_add, 5)
        oa21 = round(oa21_clear + cloud_add, 5)

    return oa10, oa17, oa21, True


# ── Public Entry Point ─────────────────────────────────────────────────────────
def get_fdi_from_sentinel3(
    lat: float,
    lon: float,
    red_hint:  float | None = None,
    nir_hint:  float | None = None,
    swir_hint: float | None = None,
) -> tuple[dict | None, str | None]:
    """
    Fetch Sentinel-3 OLCI band data and compute FDI for the given coordinates.

    Return shape mirrors get_fdi_from_satellite() exactly so the UI is
    sensor-agnostic:
        (result_dict, error_str_or_None)

    result_dict keys:
        oa10, oa17, oa21        — band reflectances
        fdi_score               — scalar FDI
        severity, action        — from classify_fdi()
        ml_label, confidence    — from ml_classify()
        sensor                  — "Sentinel-3 OLCI"
        is_synthetic            — bool, True when real data unavailable
        granule_id              — CMR granule UR or "N/A"
    """
    granule = _find_granule(lat, lon)

    is_synthetic = False
    granule_id   = "N/A"

    if granule is None:
        oa10, oa17, oa21, is_synthetic = _synthetic_estimate(
            {}, red_hint, nir_hint, swir_hint
        )
        granule_id = "No granule found (synthetic)"

    else:
        granule_id = granule.get("producer_granule_id") or granule.get("id", "N/A")

        opendap_url = None
        for link in granule.get("links", []):
            if "opendap" in link.get("href", "").lower():
                opendap_url = link["href"].rstrip("/")
                break

        if opendap_url:
            bands = _fetch_olci_bands_opendap(opendap_url)
            if bands:
                oa10, oa17, oa21 = bands
            else:
                oa10, oa17, oa21, is_synthetic = _synthetic_estimate(
                    granule, red_hint, nir_hint, swir_hint
                )
        else:
            oa10, oa17, oa21, is_synthetic = _synthetic_estimate(
                granule, red_hint, nir_hint, swir_hint
            )

    # ── Unit normalisation: force ALL bands into reflectance [0.0 – 1.0] ─────────
    # Sources deliver values at different scales:
    #   OPeNDAP raw DN  : ~0 – 65535  → divide by 10_000
    #   OPeNDAP physical: ~0.0 – 1.5  → already correct
    #   Synthetic       : ~0.001–0.02 → already correct
    #   GEE divide(400) : ~0.0 – 0.5  → already correct
    # We use bracket thresholds instead of a single > 1.0 check to avoid
    # over-dividing values that are legitimately just above 1.0 (e.g. 1.2).
    def _to_refl(v: float, name: str) -> float:
        if v > 2.0:
            # Definitely raw DN — scale down
            v /= 10_000
        if not (0.0 <= v <= 1.5):
            raise ValueError(
                f"Band {name} = {v:.5f} is outside valid reflectance range [0, 1.5] "
                "even after normalisation. Check data source units."
            )
        return float(v)

    try:
        oa10 = _to_refl(oa10, "Oa10")
        oa17 = _to_refl(oa17, "Oa17")
        oa21 = _to_refl(oa21, "Oa21")
    except ValueError as e:
        return None, str(e)

    try:
        fdi_score        = calculate_fdi_olci(oa10, oa17, oa21)
        severity, action = classify_fdi(fdi_score)
        ml_label, conf   = ml_classify(oa10, oa17, oa21)
    except Exception as e:
        return None, f"FDI computation failed: {e}"

    # Area/mass estimate: map FDI score to a fraction of the ROI area.
    # The old heuristic (fdi * 100 pixels * 90000 m2) was dimensionally wrong
    # and produced values in the millions. This uses a linear scale capped at
    # 30% of the default 2km radius ROI (approx 12.57 km2).
    #   FDI=0.02 -> 10% of ROI,  FDI=0.04 -> 20%,  FDI>=0.06 -> 30% (cap)
    ROI_AREA_M2     = 12_570_000
    fdi_clamped     = max(0.0, fdi_score)
    debris_fraction = min(fdi_clamped / 0.20, 0.30)
    detected_area   = round(ROI_AREA_M2 * debris_fraction, 1)
    mass_raw        = round(detected_area * MASS_PROXY, 1)
    mass_capped     = mass_raw > MASS_CAP
    mass_kg         = MASS_CAP if mass_capped else mass_raw
    flag            = "⚠ High Turbidity / Possible False Positive" if mass_capped else ""

    result = {
        "oa10":             round(oa10, 5),
        "oa17":             round(oa17, 5),
        "oa21":             round(oa21, 5),
        "fdi_score":        round(fdi_score, 6),
        "detected_area_m2": detected_area,
        "mass_kg":          mass_kg,
        "mass_capped":      mass_capped,
        "flag":             flag,
        "severity":         severity,
        "action":           action,
        "ml_label":         ml_label,
        "confidence":       conf,
        "sensor":           "Sentinel-3 OLCI",
        "is_synthetic":     is_synthetic,
        "granule_id":       granule_id,
    }

    return result, None