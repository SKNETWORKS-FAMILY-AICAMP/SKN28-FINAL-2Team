from __future__ import annotations

import math

EARTH_RADIUS_KM = 6371.0088


def haversine_km(
    lat1: float | None,
    lon1: float | None,
    lat2: float | None,
    lon2: float | None,
) -> float | None:
    """Great-circle distance in kilometers, or ``None`` if coordinates are missing."""

    if lat1 is None or lon1 is None or lat2 is None or lon2 is None:
        return None
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    delta_phi = math.radians(lat2 - lat1)
    delta_lambda = math.radians(lon2 - lon1)
    a = (
        math.sin(delta_phi / 2) ** 2
        + math.cos(phi1) * math.cos(phi2) * math.sin(delta_lambda / 2) ** 2
    )
    return EARTH_RADIUS_KM * 2 * math.asin(min(1.0, math.sqrt(a)))
