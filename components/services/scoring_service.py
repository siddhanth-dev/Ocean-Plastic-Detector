# components/services/scoring_service.py
# Hotspot scoring and cleanup estimation helpers.

from components.services.constants import SEVERITY_WEIGHT


def priority_score(row, max_range: float) -> float:
    """Compute a priority score for a hotspot row.

    Combines severity weight, FDI score, density, and distance.
    """
    w = SEVERITY_WEIGHT.get(row["severity"], 1.0)
    return round(
        (w * row["fdi_score"])
        + (row["density"] / 100)
        - (row["distance_km"] / max_range),
        3,
    )


def estimated_tonnes(row) -> float:
    """Estimate plastic mass (tonnes) for a hotspot row."""
    return round((row["density"] * row["area_km2"]) / 1_000_000, 1)
