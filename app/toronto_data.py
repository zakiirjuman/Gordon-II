from __future__ import annotations

import csv
import io
import time
from collections import Counter
from datetime import datetime, timedelta, timezone
from typing import Any

import httpx

from app.config import (
    CACHE_TTL_SECONDS,
    CONSTRUCTION_HUBS_LAYER,
    GIS_BASE,
    KSI_COLLISIONS_CSV,
    ROAD_RESTRICTIONS_LAYER,
)

_cache: dict[str, tuple[float, Any]] = {}


async def _fetch_geojson(layer_id: int) -> dict[str, Any]:
    url = f"{GIS_BASE}/{layer_id}/query"
    params = {
        "where": "1=1",
        "outFields": "*",
        "outSR": "4326",
        "f": "geojson",
    }
    async with httpx.AsyncClient(timeout=60.0) as client:
        response = await client.get(url, params=params)
        response.raise_for_status()
        return response.json()


async def fetch_road_restrictions() -> dict[str, Any]:
    key = "road_restrictions"
    now = time.time()
    entry = _cache.get(key)
    if entry and now - entry[0] < CACHE_TTL_SECONDS:
        return entry[1]
    value = await _fetch_geojson(ROAD_RESTRICTIONS_LAYER)
    _cache[key] = (now, value)
    return value


async def fetch_construction_hubs() -> dict[str, Any]:
    key = "construction_hubs"
    now = time.time()
    entry = _cache.get(key)
    if entry and now - entry[0] < CACHE_TTL_SECONDS:
        return entry[1]
    value = await _fetch_geojson(CONSTRUCTION_HUBS_LAYER)
    _cache[key] = (now, value)
    return value


async def fetch_recent_collisions(days: int = 365) -> list[dict[str, str]]:
    key = f"collisions_{days}"
    now = time.time()
    entry = _cache.get(key)
    if entry and now - entry[0] < CACHE_TTL_SECONDS:
        return entry[1]
    value = _load_recent_collisions(days)
    _cache[key] = (now, value)
    return value


def _load_recent_collisions(days: int) -> list[dict[str, str]]:
    cutoff = datetime.now(timezone.utc) - timedelta(days=days)
    rows: list[dict[str, str]] = []

    with httpx.Client(timeout=120.0, follow_redirects=True) as client:
        response = client.get(KSI_COLLISIONS_CSV)
        response.raise_for_status()
        reader = csv.DictReader(io.StringIO(response.text))
        for row in reader:
            occurred = _parse_date(row.get("accdate") or row.get("OCC_DATE") or "")
            if occurred and occurred >= cutoff:
                rows.append(row)
    return rows


def _parse_date(value: str) -> datetime | None:
    value = value.strip()
    if not value:
        return None
    if "T" in value:
        try:
            parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
            if parsed.tzinfo is None:
                parsed = parsed.replace(tzinfo=timezone.utc)
            return parsed
        except ValueError:
            pass
    for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%d", "%m/%d/%Y"):
        try:
            parsed = datetime.strptime(value, fmt)
            return parsed.replace(tzinfo=timezone.utc)
        except ValueError:
            continue
    return None


def build_ops_snapshot(
    restrictions: dict[str, Any],
    hubs: dict[str, Any],
    collisions: list[dict[str, str]],
) -> dict[str, Any]:
    restriction_features = restrictions.get("features", [])
    hub_features = hubs.get("features", [])

    districts = Counter(
        (feature.get("properties") or {}).get("CLOSURE_LOCATION")
        or (feature.get("properties") or {}).get("MAIN_ROAD", "Unknown")
        for feature in restriction_features
    )
    closure_types = Counter(
        (feature.get("properties") or {}).get("ROAD_CLOSURE_TYPE", "Unknown")
        for feature in restriction_features
    )
    issue_types = Counter(
        (feature.get("properties") or {}).get("ISSUE_TYPE", "Unknown")
        for feature in restriction_features
    )
    active_status = Counter(
        (feature.get("properties") or {}).get("STATUS", "Unknown")
        for feature in restriction_features
    )

    roads_with_restrictions = Counter(
        (feature.get("properties") or {}).get("MAIN_ROAD", "Unknown")
        for feature in restriction_features
        if (feature.get("properties") or {}).get("MAIN_ROAD")
    )

    collision_roads = Counter(
        row.get("stname1") or row.get("STREET1") or "Unknown"
        for row in collisions
    )
    collision_wards = Counter(
        row.get("wardname") or "Unknown"
        for row in collisions
    )

    sample_restrictions = []
    for feature in restriction_features[:12]:
        props = feature.get("properties") or {}
        sample_restrictions.append(
            {
                "road": props.get("MAIN_ROAD"),
                "location": props.get("CLOSURE_LOCATION"),
                "type": props.get("ROAD_CLOSURE_TYPE"),
                "issue": props.get("ISSUE_TYPE"),
                "status": props.get("STATUS"),
                "description": (props.get("DESCRIPTION") or "")[:220],
            }
        )

    sample_hubs = []
    for feature in hub_features[:8]:
        props = feature.get("properties") or {}
        sample_hubs.append(
            {
                "name": props.get("NAME") or props.get("MAIN_ROAD") or "Construction hub",
                "description": (props.get("DESCRIPTION") or props.get("NOTES") or "")[:220],
            }
        )

    return {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "counts": {
            "active_road_restrictions": len(restriction_features),
            "construction_hubs": len(hub_features),
            "recent_ksi_collisions_12mo": len(collisions),
        },
        "districts": districts.most_common(8),
        "closure_types": closure_types.most_common(8),
        "issue_types": issue_types.most_common(8),
        "statuses": active_status.most_common(8),
        "top_restricted_roads": roads_with_restrictions.most_common(10),
        "top_collision_streets_12mo": collision_roads.most_common(10),
        "top_collision_wards_12mo": collision_wards.most_common(10),
        "sample_restrictions": sample_restrictions,
        "sample_hubs": sample_hubs,
    }
