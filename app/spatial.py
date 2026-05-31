from __future__ import annotations

import math
import time
from collections import Counter
from importlib.util import find_spec
from typing import Any


def cudf_available() -> bool:
    return find_spec("cudf") is not None


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


def _feature_points(feature: dict[str, Any]) -> list[tuple[float, float]]:
    geometry = feature.get("geometry") or {}
    coords = geometry.get("coordinates")
    if not coords:
        return []

    geom_type = geometry.get("type")
    if geom_type == "Point" and len(coords) >= 2:
        return [(float(coords[1]), float(coords[0]))]
    if geom_type == "LineString":
        return [(float(lat), float(lng)) for lng, lat, *_ in coords]
    if geom_type == "MultiLineString":
        points: list[tuple[float, float]] = []
        for line in coords:
            points.extend((float(lat), float(lng)) for lng, lat, *_ in line)
        return points
    if geom_type == "Polygon":
        points = []
        for ring in coords:
            points.extend((float(lat), float(lng)) for lng, lat, *_ in ring)
        return points
    return []


def _near_feature(
    feature: dict[str, Any],
    *,
    lat: float,
    lng: float,
    radius_m: int,
) -> tuple[bool, float | None]:
    distances = [
        _haversine_m(lat, lng, point_lat, point_lng)
        for point_lat, point_lng in _feature_points(feature)
    ]
    if not distances:
        return False, None
    nearest = min(distances)
    return nearest <= radius_m, nearest


def _collision_lat_lng(row: dict[str, str]) -> tuple[float, float] | None:
    for lat_key, lng_key in (
        ("latitude", "longitude"),
        ("LATITUDE", "LONGITUDE"),
        ("lat", "lon"),
        ("Y", "X"),
    ):
        try:
            lat = float(row.get(lat_key, "") or "")
            lng = float(row.get(lng_key, "") or "")
        except ValueError:
            continue
        if -90 <= lat <= 90 and -180 <= lng <= 180:
            return lat, lng
    return None


def build_point_snapshot(
    *,
    lat: float,
    lng: float,
    radius_m: int,
    restrictions: dict[str, Any],
    hubs: dict[str, Any],
    collisions: list[dict[str, str]],
) -> dict[str, Any]:
    started = time.perf_counter()
    nearby_restrictions: list[dict[str, Any]] = []
    nearby_hubs: list[dict[str, Any]] = []
    nearby_collisions: list[dict[str, str]] = []

    for feature in restrictions.get("features", []):
        is_near, distance_m = _near_feature(feature, lat=lat, lng=lng, radius_m=radius_m)
        if not is_near:
            continue
        props = feature.get("properties") or {}
        nearby_restrictions.append(
            {
                "road": props.get("MAIN_ROAD"),
                "location": props.get("CLOSURE_LOCATION"),
                "type": props.get("ROAD_CLOSURE_TYPE"),
                "issue": props.get("ISSUE_TYPE"),
                "status": props.get("STATUS"),
                "description": (props.get("DESCRIPTION") or "")[:220],
                "distance_m": round(distance_m or 0),
            }
        )

    for feature in hubs.get("features", []):
        is_near, distance_m = _near_feature(feature, lat=lat, lng=lng, radius_m=radius_m)
        if not is_near:
            continue
        props = feature.get("properties") or {}
        nearby_hubs.append(
            {
                "name": props.get("NAME") or props.get("MAIN_ROAD") or "Construction hub",
                "description": (props.get("DESCRIPTION") or props.get("NOTES") or "")[:220],
                "distance_m": round(distance_m or 0),
            }
        )

    for row in collisions:
        point = _collision_lat_lng(row)
        if not point:
            continue
        distance_m = _haversine_m(lat, lng, point[0], point[1])
        if distance_m <= radius_m:
            enriched = dict(row)
            enriched["distance_m"] = str(round(distance_m))
            nearby_collisions.append(enriched)

    collision_roads = Counter(
        row.get("stname1") or row.get("STREET1") or "Unknown"
        for row in nearby_collisions
    )
    roads_with_restrictions = Counter(
        row.get("road") or "Unknown"
        for row in nearby_restrictions
        if row.get("road")
    )
    elapsed_ms = round((time.perf_counter() - started) * 1000)

    return {
        "generated_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "scope": "point",
        "center": {"lat": lat, "lng": lng, "radius_m": radius_m},
        "counts": {
            "active_road_restrictions": len(nearby_restrictions),
            "construction_hubs": len(nearby_hubs),
            "recent_ksi_collisions_12mo": len(nearby_collisions),
        },
        "top_restricted_roads": roads_with_restrictions.most_common(10),
        "top_collision_streets_12mo": collision_roads.most_common(10),
        "top_collision_wards_12mo": [],
        "sample_restrictions": sorted(
            nearby_restrictions,
            key=lambda row: row.get("distance_m", 10**9),
        )[:8],
        "sample_hubs": sorted(
            nearby_hubs,
            key=lambda row: row.get("distance_m", 10**9),
        )[:6],
        "timings_ms": {
            "spatial": elapsed_ms,
            "gpu_join": None,
        },
        "spatial_engine": "python",
    }
