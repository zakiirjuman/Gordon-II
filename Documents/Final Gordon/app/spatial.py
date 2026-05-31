from __future__ import annotations

import math
import time
from collections import Counter
from importlib.util import find_spec
from typing import Any

from app.simulated_units import build_simulated_units_geojson, nearest_simulated_units


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


def _point_in_ring(lat: float, lng: float, ring: list[list[float]]) -> bool:
    inside = False
    j = len(ring) - 1
    for i in range(len(ring)):
        xi, yi = ring[i][0], ring[i][1]
        xj, yj = ring[j][0], ring[j][1]
        intersects = ((yi > lat) != (yj > lat)) and (
            lng < (xj - xi) * (lat - yi) / ((yj - yi) or 1e-12) + xi
        )
        if intersects:
            inside = not inside
        j = i
    return inside


def _point_in_polygon(lat: float, lng: float, geometry: dict[str, Any]) -> bool:
    geom_type = geometry.get("type")
    coords = geometry.get("coordinates") or []
    if geom_type == "Polygon" and coords:
        if not _point_in_ring(lat, lng, coords[0]):
            return False
        for hole in coords[1:]:
            if _point_in_ring(lat, lng, hole):
                return False
        return True
    if geom_type == "MultiPolygon":
        return any(_point_in_polygon(lat, lng, {"type": "Polygon", "coordinates": poly}) for poly in coords)
    return False


def _feature_points(feature: dict[str, Any]) -> list[tuple[float, float]]:
    geometry = feature.get("geometry") or {}
    coords = geometry.get("coordinates")
    if not coords:
        return []

    geom_type = geometry.get("type")
    if geom_type == "Point" and len(coords) >= 2:
        return [(float(coords[1]), float(coords[0]))]
    if geom_type == "MultiPoint":
        return [(float(lat), float(lng)) for lng, lat, *_ in coords]
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


def _ward_at_point(lat: float, lng: float, wards: dict[str, Any]) -> dict[str, Any] | None:
    for feature in wards.get("features", []):
        geometry = feature.get("geometry") or {}
        if not _point_in_polygon(lat, lng, geometry):
            continue
        props = feature.get("properties") or {}
        name = props.get("AREA_NAME") or props.get("AREA_DESC") or props.get("WARD_NAME")
        code = props.get("AREA_SHORT_CODE") or props.get("AREA_LONG_CODE") or props.get("WARD")
        if name or code:
            return {"name": name, "code": code}
    return None


def _near_point_features(
    features: list[dict[str, Any]],
    *,
    lat: float,
    lng: float,
    radius_m: int,
    props_builder,
) -> list[dict[str, Any]]:
    nearby: list[dict[str, Any]] = []
    for feature in features:
        is_near, distance_m = _near_feature(feature, lat=lat, lng=lng, radius_m=radius_m)
        if not is_near:
            continue
        props = feature.get("properties") or {}
        nearby.append({**props_builder(props), "distance_m": round(distance_m or 0)})
    return nearby


def build_point_snapshot(
    *,
    lat: float,
    lng: float,
    radius_m: int,
    restrictions: dict[str, Any],
    hubs: dict[str, Any],
    collisions: list[dict[str, str]],
    wards: dict[str, Any] | None = None,
    schools: dict[str, Any] | None = None,
    fire_stations: dict[str, Any] | None = None,
    simulated_units: dict[str, Any] | None = None,
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

    nearby_schools = _near_point_features(
        (schools or {}).get("features", []),
        lat=lat,
        lng=lng,
        radius_m=radius_m,
        props_builder=lambda props: {
            "name": props.get("NAME"),
            "type": props.get("SCHOOL_TYPE_DESC") or props.get("SCHOOL_TYPE"),
            "board": props.get("BOARD_NAME"),
        },
    )
    nearby_fire_stations = _near_point_features(
        (fire_stations or {}).get("features", []),
        lat=lat,
        lng=lng,
        radius_m=max(radius_m, 2500),
        props_builder=lambda props: {
            "station": props.get("STATION"),
            "address": props.get("ADDRESS") or props.get("LINEAR_NAME_FULL"),
            "ward_name": props.get("WARD_NAME"),
        },
    )

    ward = _ward_at_point(lat, lng, wards or {}) if wards else None
    units = simulated_units or build_simulated_units_geojson()
    nearest_units = nearest_simulated_units(lat, lng, units)

    collision_roads = Counter(
        row.get("stname1") or row.get("STREET1") or "Unknown"
        for row in nearby_collisions
    )
    collision_wards = Counter(
        row.get("wardname") or row.get("WARDNAME") or "Unknown"
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
        "ward": ward,
        "counts": {
            "active_road_restrictions": len(nearby_restrictions),
            "construction_hubs": len(nearby_hubs),
            "recent_ksi_collisions_12mo": len(nearby_collisions),
            "schools": len(nearby_schools),
            "fire_stations": len(nearby_fire_stations),
        },
        "top_restricted_roads": roads_with_restrictions.most_common(10),
        "top_collision_streets_12mo": collision_roads.most_common(10),
        "top_collision_wards_12mo": collision_wards.most_common(10),
        "sample_restrictions": sorted(
            nearby_restrictions,
            key=lambda row: row.get("distance_m", 10**9),
        )[:8],
        "sample_hubs": sorted(
            nearby_hubs,
            key=lambda row: row.get("distance_m", 10**9),
        )[:6],
        "sample_schools": sorted(nearby_schools, key=lambda row: row.get("distance_m", 10**9))[:6],
        "sample_fire_stations": sorted(
            nearby_fire_stations,
            key=lambda row: row.get("distance_m", 10**9),
        )[:4],
        "nearest_simulated_units": nearest_units,
        "simulated_resources_disclaimer": units.get("disclaimer"),
        "timings_ms": {
            "spatial": elapsed_ms,
            "gpu_join": None,
        },
        "spatial_engine": "python",
    }
