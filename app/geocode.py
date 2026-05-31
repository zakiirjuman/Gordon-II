from __future__ import annotations

import time
from typing import Any

import httpx

from app.config import APP_NAME, GEOCODE_CACHE_SIZE, NOMINATIM_TIMEOUT_S, NOMINATIM_URL

_GEOCODE_CACHE: dict[tuple[float, float], dict[str, Any]] = {}
_EMPTY_LOCATION: dict[str, Any] = {
    "display_name": None,
    "road": None,
    "neighbourhood": None,
    "city": None,
    "label": None,
    "source": None,
}


def _cache_key(lat: float, lng: float) -> tuple[float, float]:
    return (round(lat, 4), round(lng, 4))


def _build_label(address: dict[str, Any], display_name: str | None) -> str | None:
    road = (
        address.get("road")
        or address.get("pedestrian")
        or address.get("footway")
        or address.get("cycleway")
    )
    neighbourhood = (
        address.get("neighbourhood")
        or address.get("suburb")
        or address.get("quarter")
        or address.get("city_district")
    )
    city = address.get("city") or address.get("town") or address.get("municipality") or "Toronto"

    if road and neighbourhood:
        return f"{road} near {neighbourhood}, {city}"
    if road:
        return f"{road}, {city}"
    if display_name:
        parts = [part.strip() for part in display_name.split(",") if part.strip()]
        return ", ".join(parts[:3]) if parts else None
    return None


def _parse_nominatim_payload(payload: dict[str, Any]) -> dict[str, Any]:
    address = payload.get("address") or {}
    display_name = payload.get("display_name")
    neighbourhood = (
        address.get("neighbourhood")
        or address.get("suburb")
        or address.get("quarter")
        or address.get("city_district")
    )
    city = address.get("city") or address.get("town") or address.get("municipality")
    road = (
        address.get("road")
        or address.get("pedestrian")
        or address.get("footway")
        or address.get("cycleway")
    )
    return {
        "display_name": display_name,
        "road": road,
        "neighbourhood": neighbourhood,
        "city": city,
        "label": _build_label(address, display_name),
        "source": "nominatim",
    }


async def reverse_geocode(lat: float, lng: float) -> dict[str, Any]:
    """Resolve lat/lng to a human-readable Toronto-area label via Nominatim."""
    key = _cache_key(lat, lng)
    cached = _GEOCODE_CACHE.get(key)
    if cached is not None:
        return {**cached, "cached": True}

    started = time.perf_counter()
    headers = {
        "User-Agent": f"{APP_NAME}/0.3 (patrol demo; contact: local-only)",
        "Accept-Language": "en",
    }
    params = {
        "lat": lat,
        "lon": lng,
        "format": "json",
        "addressdetails": 1,
        "zoom": 18,
    }

    try:
        async with httpx.AsyncClient(timeout=NOMINATIM_TIMEOUT_S) as client:
            response = await client.get(NOMINATIM_URL, params=params, headers=headers)
            response.raise_for_status()
            payload = response.json()
    except Exception:  # noqa: BLE001
        return {**_EMPTY_LOCATION, "cached": False, "geocode_ms": 0}

    location = _parse_nominatim_payload(payload)
    location["cached"] = False
    location["geocode_ms"] = round((time.perf_counter() - started) * 1000)

    if len(_GEOCODE_CACHE) >= GEOCODE_CACHE_SIZE:
        _GEOCODE_CACHE.pop(next(iter(_GEOCODE_CACHE)))
    _GEOCODE_CACHE[key] = {k: v for k, v in location.items() if k != "cached"}

    return location
