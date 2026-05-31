from __future__ import annotations

import hashlib
import math
import time
from typing import Any

SIMULATED_UNITS_DISCLAIMER = (
    "Training demo — simulated resource picture, not live CAD/AVL or dispatch."
)

# Fixed anchors around downtown Toronto; jittered slightly per time bucket for demo movement.
_UNIT_ANCHORS: tuple[tuple[float, float, str, str], ...] = (
    (43.6532, -79.3832, "police", "Simulated backup — downtown core"),
    (43.6615, -79.3955, "police", "Simulated backup — traffic unit"),
    (43.6425, -79.4010, "fire", "Simulated engine — west corridor"),
    (43.6710, -79.3520, "paramedic", "Simulated EMS — east corridor"),
    (43.6485, -79.3710, "police", "Simulated backup — harbourfront"),
)


def _jitter_coordinate(lat: float, lng: float, *, seed: int, max_m: float) -> tuple[float, float]:
    rng = hashlib.sha256(str(seed).encode()).hexdigest()
    lat_offset = (int(rng[0:8], 16) / 0xFFFFFFFF - 0.5) * 2
    lng_offset = (int(rng[8:16], 16) / 0xFFFFFFFF - 0.5) * 2
    lat_delta = (max_m / 111_000) * lat_offset
    lng_delta = (max_m / (111_000 * max(math.cos(math.radians(lat)), 0.2))) * lng_offset
    return lat + lat_delta, lng + lng_delta


def build_simulated_units_geojson() -> dict[str, Any]:
    bucket = int(time.time() // 300)
    features: list[dict[str, Any]] = []
    for idx, (lat, lng, unit_type, label) in enumerate(_UNIT_ANCHORS):
        jlat, jlng = _jitter_coordinate(lat, lng, seed=bucket * 10 + idx, max_m=140)
        features.append(
            {
                "type": "Feature",
                "geometry": {"type": "Point", "coordinates": [jlng, jlat]},
                "properties": {
                    "unit_type": unit_type,
                    "label": label,
                    "simulated": True,
                    "disclaimer": SIMULATED_UNITS_DISCLAIMER,
                },
            }
        )
    return {
        "type": "FeatureCollection",
        "simulated": True,
        "disclaimer": SIMULATED_UNITS_DISCLAIMER,
        "features": features,
    }


def eta_minutes_from_distance(distance_m: float) -> int:
    """Rough urban response estimate for demo purposes only."""
    return max(3, round(distance_m / 450))


def _haversine_m(lat1: float, lng1: float, lat2: float, lng2: float) -> float:
    radius_m = 6_371_000
    phi1 = math.radians(lat1)
    phi2 = math.radians(lat2)
    d_phi = math.radians(lat2 - lat1)
    d_lam = math.radians(lng2 - lng1)
    a = (
        math.sin(d_phi / 2) ** 2
        + math.cos(phi1) * math.cos(phi2) * math.sin(d_lam / 2) ** 2
    )
    return radius_m * 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))


def nearest_simulated_units(
    lat: float,
    lng: float,
    simulated_units: dict[str, Any] | None = None,
    *,
    limit: int = 3,
) -> list[dict[str, Any]]:
    units = simulated_units or build_simulated_units_geojson()
    ranked: list[dict[str, Any]] = []
    for feature in units.get("features", []):
        coords = (feature.get("geometry") or {}).get("coordinates") or []
        if len(coords) < 2:
            continue
        flng, flat = float(coords[0]), float(coords[1])
        distance_m = _haversine_m(lat, lng, flat, flng)
        props = feature.get("properties") or {}
        ranked.append(
            {
                "unit_type": props.get("unit_type"),
                "label": props.get("label"),
                "simulated": True,
                "disclaimer": props.get("disclaimer"),
                "distance_m": round(distance_m),
                "eta_minutes": eta_minutes_from_distance(distance_m),
            }
        )
    ranked.sort(key=lambda row: row["distance_m"])
    return ranked[:limit]
