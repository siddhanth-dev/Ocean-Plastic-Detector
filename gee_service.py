# gee_service.py
# Google Earth Engine integration — lazy init, S2 + S3 pixel fetch,
# QA60 cloud masking, FDI / detection-stats computation.
# Mock mode DISABLED — GEE must be configured to use this module.

import streamlit as st

_EE_INITIALISED = False
_GEE_MODE = "unknown"


# ── Initialisation ─────────────────────────────────────────────────────────────
def _init_ee() -> str:
    """
    Initialise the EE client once per process. Raises on failure — no mock fallback.

    Auth priority:
        1. Service Account (st.secrets["gee"]["service_account"] + private_key)
        2. OAuth token    (st.secrets["gee"]["ee_token"])
        3. Application Default Credentials  (`earthengine authenticate`)
    """
    global _EE_INITIALISED, _GEE_MODE
    if _EE_INITIALISED:
        return _GEE_MODE

    import ee

    gee_secrets = st.secrets.get("gee", {})
    sa  = gee_secrets.get("service_account", "").strip()
    key = gee_secrets.get("private_key",     "").strip()
    tok = gee_secrets.get("ee_token",        "").strip()

    if sa and key:
        credentials = ee.ServiceAccountCredentials(sa, key_data=key)
        ee.Initialize(credentials)
        _GEE_MODE = "service_account"

    elif tok:
        import google.oauth2.credentials as g_creds
        creds = g_creds.Credentials(
            token=None, refresh_token=tok,
            token_uri="https://oauth2.googleapis.com/token",
            client_id="517222506229-vsmmajv00ul0bs7p89v5m89qs8eb9359.apps.googleusercontent.com",
            client_secret="RUP0RZ6e0WWUD3deCFH-cGhN",
        )
        ee.Initialize(creds)
        _GEE_MODE = "oauth"

    else:
        ee.Initialize()   # Application Default Credentials
        _GEE_MODE = "adc"

    _EE_INITIALISED = True
    return _GEE_MODE


# ── QA60 Cloud Mask ────────────────────────────────────────────────────────────
def _qa60_mask(img):
    """Mask opaque cloud (bit 10) and cirrus (bit 11); scale DN → reflectance."""
    import ee
    qa   = img.select("QA60")
    mask = (qa.bitwiseAnd(1 << 10).eq(0)
              .And(qa.bitwiseAnd(1 << 11).eq(0)))
    # ── FIX: S2_SR_HARMONIZED is already in surface reflectance units
    # scaled by 10000. Dividing by 10000 gives correct 0–1 reflectance.
    # The original divide(10_000) was correct; no change here.
    return img.updateMask(mask).divide(10_000)


# ── Detection Stats ────────────────────────────────────────────────────────────
def _detection_stats(fdi_img, roi):
    """
    Count pixels where FDI > 0.01.
    S2 pixel = 100 m² (10 m × 10 m).  Returns (area_m2, mass_kg).
    """
    import ee
    pixel_count = (fdi_img.gt(0.01)
                   .reduceRegion(
                       reducer  = ee.Reducer.sum(),
                       geometry = roi,
                       scale    = 10,
                       maxPixels= 1e7,
                   ).getInfo().get("FDI", 0) or 0)

    area_m2 = int(pixel_count) * 100
    mass_kg = round(area_m2 * 1.5, 1)
    return area_m2, mass_kg


# ── Sentinel-2 SR (Coastal ≤ 20 km) ───────────────────────────────────────────
def fetch_s2_fdi(lat: float, lon: float, radius_m: int = 2000) -> tuple[dict | None, str | None]:
    """
    Cloud-masked S2 SR Harmonized fetch for a 2 km ROI.
    Returns (result_dict, error_str_or_None).

    Keys: red, nir, swir, fdi_score, fdi_max, detected_area_m2,
          mass_kg, clear_pixel_pct, sensor, mode
    """
    try:
        mode = _init_ee()
    except Exception as e:
        return None, f"GEE init failed: {e}"

    try:
        import ee
        from datetime import datetime, timedelta

        roi   = ee.Geometry.Point([lon, lat]).buffer(radius_m)
        end   = datetime.utcnow()
        start = end - timedelta(days=45)

        col = (ee.ImageCollection("COPERNICUS/S2_SR_HARMONIZED")
               .filterBounds(roi)
               .filterDate(start.strftime("%Y-%m-%d"), end.strftime("%Y-%m-%d"))
               .filter(ee.Filter.lt("CLOUDY_PIXEL_PERCENTAGE", 80))
               .map(_qa60_mask)
               .select(["B4", "B8", "B11"]))

        if col.size().getInfo() == 0:
            return None, "No cloud-free S2 scenes found in the last 45 days for this location."

        mosaic = col.median()

        # ── FIX: Use the correct spectral-baseline FDI formula.
        # Old formula was:  NIR - (RED + (SWIR - RED) * 0.12)
        # That hardcoded 0.12 is WRONG — the correct slope is:
        #   (λNIR − λRED) / (λSWIR − λRED) = (842−665) / (1610−665) = 0.1873
        # Using 0.12 underestimates the baseline, inflating FDI scores.
        fdi_img = mosaic.expression(
            "NIR - (RED + (SWIR - RED) * 0.1873)",
            {
                "NIR":  mosaic.select("B8"),
                "RED":  mosaic.select("B4"),
                "SWIR": mosaic.select("B11"),
            }
        ).rename("FDI")

        # ── Two separate reduceRegion calls to avoid Reducer.combine band-count bug ──
        mean_stats = mosaic.addBands(fdi_img).reduceRegion(
            reducer  = ee.Reducer.mean(),
            geometry = roi,
            scale    = 10,
            maxPixels= 1e7,
        ).getInfo()

        max_stats = fdi_img.reduceRegion(
            reducer  = ee.Reducer.max(),
            geometry = roi,
            scale    = 10,
            maxPixels= 1e7,
        ).getInfo()

        red      = mean_stats.get("B4",   0) or 0
        nir      = mean_stats.get("B8",   0) or 0
        swir     = mean_stats.get("B11",  0) or 0
        fdi_mean = mean_stats.get("FDI",  0) or 0
        fdi_max  = max_stats.get("FDI",   0) or 0

        area_m2, mass_kg = _detection_stats(fdi_img, roi)

        # ── FIX: clear_pixel_pct was computing debris fraction, not clear-sky fraction.
        # A correct approximation: count unmasked pixels via a constant image.
        unmasked_px = (mosaic.select("B4").mask()
                       .reduceRegion(
                           reducer  = ee.Reducer.sum(),
                           geometry = roi,
                           scale    = 10,
                           maxPixels= 1e7,
                       ).getInfo().get("B4", 0) or 0)
        total_px  = roi.area(1).getInfo() / 100   # ROI area in m² ÷ 100 m²/pixel
        clear_pct = round(min(int(unmasked_px) / max(total_px, 1) * 100, 100), 1)

        return {
            "red":              round(red,      5),
            "nir":              round(nir,      5),
            "swir":             round(swir,     5),
            "fdi_score":        round(fdi_mean, 6),
            "fdi_max":          round(fdi_max,  6),
            "detected_area_m2": area_m2,
            "mass_kg":          mass_kg,
            "clear_pixel_pct":  clear_pct,
            "sensor":           "Sentinel-2 SR (GEE)",
            "mode":             mode,
        }, None

    except Exception as e:
        return None, f"GEE S2 fetch failed: {e}"


# ── Sentinel-3 OLCI (Open Ocean > 20 km) ──────────────────────────────────────
def fetch_s3_fdi(lat: float, lon: float, radius_m: int = 2000) -> tuple[dict | None, str | None]:
    """
    S3 OLCI via GEE (COPERNICUS/S3/OLCI). Falls back to CMR if no scenes.
    Returns (result_dict, error_str_or_None).
    Keys: oa10, oa17, oa21, fdi_score, fdi_max, detected_area_m2,
          mass_kg, clear_pixel_pct, sensor, mode
    """
    try:
        mode = _init_ee()
    except Exception as e:
        return None, f"GEE init failed: {e}"

    try:
        import ee
        from datetime import datetime, timedelta

        roi   = ee.Geometry.Point([lon, lat]).buffer(radius_m)
        end   = datetime.utcnow()
        start = end - timedelta(days=15)

        col = (ee.ImageCollection("COPERNICUS/S3/OLCI")
               .filterBounds(roi)
               .filterDate(start.strftime("%Y-%m-%d"), end.strftime("%Y-%m-%d"))
               .select(["Oa10_radiance", "Oa17_radiance", "Oa21_radiance"]))

        if col.size().getInfo() > 0:
            # GEE's COPERNICUS/S3/OLCI stores each band as raw DN with a
            # documented scale factor of 0.00876125 per band. We apply it
            # per-band explicitly (not a blanket multiply) so that if GEE
            # ever changes one band's metadata it won't silently break others.
            # After scaling, all bands should be in reflectance [0.0 – 0.5].
            def scale_band(img, band):
                return img.select(band).multiply(0.00876125).rename(band)

            mosaic_raw = col.median()
            oa10_img   = scale_band(mosaic_raw, "Oa10_radiance")
            oa17_img   = scale_band(mosaic_raw, "Oa17_radiance")
            oa21_img   = scale_band(mosaic_raw, "Oa21_radiance")
            mosaic     = oa10_img.addBands(oa17_img).addBands(oa21_img)

            # Correct FDI slope for OLCI wavelengths:
            # (865-681)/(1020-681) = 184/339 = 0.5428
            fdi_img = mosaic.expression(
                "OA17 - (OA10 + (OA21 - OA10) * 0.5428)",
                {
                    "OA17": mosaic.select("Oa17_radiance"),
                    "OA10": mosaic.select("Oa10_radiance"),
                    "OA21": mosaic.select("Oa21_radiance"),
                }
            ).rename("FDI")

            # Add a simple cloud/sunglint mask: skip pixels where any band > 0.3
            # (open ocean reflectance is typically < 0.05; > 0.3 is cloud/glint)
            valid_mask = (mosaic.select("Oa17_radiance").lt(0.3)
                          .And(mosaic.select("Oa10_radiance").lt(0.3))
                          .And(mosaic.select("Oa21_radiance").lt(0.3)))
            fdi_img  = fdi_img.updateMask(valid_mask)
            mosaic   = mosaic.updateMask(valid_mask)

            mean_stats = mosaic.addBands(fdi_img).reduceRegion(
                reducer  = ee.Reducer.mean(),
                geometry = roi,
                scale    = 300,
                maxPixels= 1e7,
            ).getInfo()

            max_stats = fdi_img.reduceRegion(
                reducer  = ee.Reducer.max(),
                geometry = roi,
                scale    = 300,
                maxPixels= 1e7,
            ).getInfo()

            oa10    = mean_stats.get("Oa10_radiance", 0) or 0
            oa17    = mean_stats.get("Oa17_radiance", 0) or 0
            oa21    = mean_stats.get("Oa21_radiance", 0) or 0
            fdi     = mean_stats.get("FDI",           0) or 0
            fdi_max = max_stats.get("FDI",            0) or 0

            # Hard sanity check — any band > 0.5 after scaling = something is wrong
            for band_name, band_val in [("Oa10", oa10), ("Oa17", oa17), ("Oa21", oa21)]:
                if band_val > 0.5:
                    return None, (
                        f"S3 {band_name}={band_val:.4f} after scaling — "
                        f"likely cloud/glint contamination or wrong scale factor. "
                        f"Try a longer date range or check COPERNICUS/S3/OLCI metadata."
                    )

            # Area/mass: ROI-fraction approach
            ROI_AREA_M2     = 3.14159 * radius_m ** 2
            fdi_clamped     = max(0.0, fdi)
            debris_fraction = min(fdi_clamped / 0.20, 0.30)
            area_m2         = round(ROI_AREA_M2 * debris_fraction, 1)
            mass_kg         = round(area_m2 * 1.5, 1)

            return {
                "oa10":             round(oa10,    5),
                "oa17":             round(oa17,    5),
                "oa21":             round(oa21,    5),
                "fdi_score":        round(fdi,     6),
                "fdi_max":          round(fdi_max, 6),
                "detected_area_m2": area_m2,
                "mass_kg":          mass_kg,
                "clear_pixel_pct":  None,
                "sensor":           "Sentinel-3 OLCI (GEE)",
                "mode":             mode,
            }, None
    except Exception:
        pass  # fall through to CMR

    # ── CMR fallback ──────────────────────────────────────────────────────────
    # If we got this far, GEE S3 failed. Try to pull S2 values first so the
    # synthetic S3 estimate is spectrally consistent with S2 reflectances.
    from sentinel3 import get_fdi_from_sentinel3

    s2_result = None
    try:
        s2_result, _ = fetch_s2_fdi(lat, lon)
    except Exception:
        pass

    cmr, error = get_fdi_from_sentinel3(
        lat, lon,
        red_hint  = s2_result.get("red")  if s2_result else None,
        nir_hint  = s2_result.get("nir")  if s2_result else None,
        swir_hint = s2_result.get("swir") if s2_result else None,
    )
    if error:
        return None, error
    cmr.setdefault("detected_area_m2", None)
    cmr.setdefault("mass_kg",          None)
    cmr.setdefault("clear_pixel_pct",  None)
    cmr.setdefault("fdi_max",          cmr.get("fdi_score"))
    cmr["mode"] = "cmr"
    return cmr, None