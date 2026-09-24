"""
City registry — the platform's prototype areas of interest.

Adding a city means adding one entry here (plus its boundary GeoJSON, fetched
via scripts/fetch_boundary.py) and, where state-government authorities are
named, real names in data_registry.py — never a placeholder.
"""
from __future__ import annotations

from typing import Optional

CITIES: dict[str, dict] = {
    "madurai": {
        "id": "madurai",
        "label": "Madurai",
        "state": "Tamil Nadu",
        # Wider than the city core so district-edge clicks still resolve.
        "aoi": {"lat_min": 9.75, "lat_max": 10.15, "lon_min": 77.95, "lon_max": 78.35},
        "city_core": {"lat_min": 9.86, "lat_max": 9.98, "lon_min": 78.06, "lon_max": 78.18},
        "center": [9.9252, 78.1198],
        # A single ~220m block, not the whole city core — real cadastral
        # parcels are a few hundred m² each, not km²-scale.
        "cadastral_patch": {"lat_min": 9.9242, "lat_max": 9.9262,
                            "lon_min": 78.1188, "lon_max": 78.1208},
        "boundary_file": "madurai_boundary_clean.geojson",
        "boundary_dataset_id": "madurai_boundary",
        "osm_name_pattern": "Madurai",
        "flood_authority": "TN State Disaster Management Authority (TNSDMA)",
    },
    "bhopal": {
        "id": "bhopal",
        "label": "Bhopal",
        "state": "Madhya Pradesh",
        "aoi": {"lat_min": 23.10, "lat_max": 23.42, "lon_min": 77.25, "lon_max": 77.55},
        "city_core": {"lat_min": 23.20, "lat_max": 23.31, "lon_min": 77.35, "lon_max": 77.46},
        "center": [23.2599, 77.4126],
        "cadastral_patch": {"lat_min": 23.2589, "lat_max": 23.2609,
                            "lon_min": 77.4116, "lon_max": 77.4136},
        "boundary_file": "bhopal_boundary_clean.geojson",
        "boundary_dataset_id": "bhopal_boundary",
        "osm_name_pattern": "Bhopal",
        "flood_authority": "Madhya Pradesh State Disaster Management Authority (MPSDMA)",
    },
    "kovilpatti": {
        "id": "kovilpatti",
        "label": "Kovilpatti",
        "state": "Tamil Nadu",
        # A small special-grade municipality (~6.5 km² municipal limits, per
        # thoothukudi.nic.in) — the AOI/core here are deliberately much
        # tighter than Madurai's or Bhopal's.
        "aoi": {"lat_min": 9.12, "lat_max": 9.23, "lon_min": 77.82, "lon_max": 77.92},
        "city_core": {"lat_min": 9.163, "lat_max": 9.186, "lon_min": 77.855, "lon_max": 77.881},
        "center": [9.1744, 77.8683],
        "cadastral_patch": {"lat_min": 9.1734, "lat_max": 9.1754,
                            "lon_min": 77.8673, "lon_max": 77.8693},
        "boundary_file": "kovilpatti_boundary_clean.geojson",
        "boundary_dataset_id": "kovilpatti_boundary",
        "osm_name_pattern": "Kovilpatti",
        "flood_authority": "TN State Disaster Management Authority (TNSDMA)",
    },
}


def get_city(city_id: str) -> Optional[dict]:
    return CITIES.get((city_id or "").lower())


def resolve_city_for_point(lat: float, lon: float) -> Optional[dict]:
    """Which prototype city's AOI (if any) contains this coordinate."""
    for city in CITIES.values():
        a = city["aoi"]
        if a["lat_min"] <= lat <= a["lat_max"] and a["lon_min"] <= lon <= a["lon_max"]:
            return city
    return None


def list_cities() -> list[dict]:
    return list(CITIES.values())
