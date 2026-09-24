"""
Phase 6F-1 — analytical feature extraction from verified datasets only.

Each extractor returns either:
  {"available": True, "features": {...}, "provenance": {...}}
or
  {"available": False, "reason": "...", "dataset": "<id>"}

Nothing is fabricated. Terrain and LULC extractors are wired but inert until
their rasters are acquired (data_registry marks them DATA_UNAVAILABLE), so the
feature vector will grow automatically once the data lands.
"""
from __future__ import annotations

from datetime import date

from services import data_registry as reg
from services import evidence_engine as ev


def extract_terrain_features(lat: float, lon: float, city: str) -> dict:
    if not reg.can_use_for_analysis("copernicus_dem"):
        return {"available": False, "dataset": "copernicus_dem",
                "reason": "Copernicus DEM not acquired; elevation/slope/aspect "
                          "cannot be sampled without fabricating values."}
    # --- implemented when the DEM is present -------------------------------
    # sample = raster.sample(dem_path, lat, lon)  ... slope/aspect via 3x3 window
    return {"available": False, "dataset": "copernicus_dem",
            "reason": "DEM sampler not yet implemented."}


def extract_climate_features(lat: float, lon: float, city: str) -> dict:
    res = ev._climate_evidence(lat, lon)
    if not res.get("ok"):
        return {"available": False, "dataset": "open_meteo_climate",
                "reason": res.get("reason", "unavailable")}
    v = res["value"]
    return {
        "available": True,
        "features": {
            "annual_precipitation_mm": v["annual_precipitation_mm"],
            "mean_temperature_c": v["mean_temperature_c"],
            "temperature_range_c": round(v["max_daily_mean_temp_c"]
                                         - v["min_daily_mean_temp_c"], 1),
            "wet_days_per_year": v["wet_days_per_year"],
        },
        "provenance": {**res["provenance"], "extracted": date.today().isoformat()},
    }


def extract_lulc_features(lat: float, lon: float, city: str) -> dict:
    if not (reg.can_use_for_analysis("esri_lulc_2024")
            and reg.can_use_for_analysis("esri_lulc_2017")):
        return {"available": False, "dataset": "esri_lulc_2024",
                "reason": "Esri land-cover rasters not acquired; class and "
                          "2017→2024 transition cannot be derived."}
    return {"available": False, "dataset": "esri_lulc_2024",
            "reason": "LULC sampler not yet implemented."}


def extract_infrastructure_features(lat: float, lon: float, city: str) -> dict:
    res = ev._infrastructure_evidence(lat, lon, city)
    if not res.get("ok"):
        return {"available": False, "dataset": "osm_infrastructure",
                "reason": res.get("reason", "unavailable")}
    v = res["value"]
    return {
        "available": True,
        "features": {
            "distance_to_road_m": v["distance_to_road_m"],
            "distance_to_hospital_m": v["distance_to_clinic_or_hospital_m"],
            "distance_to_school_m": v["distance_to_school_or_college_m"],
            "distance_to_transit_m": v["distance_to_railway_station_m"],
        },
        "provenance": {**res["provenance"], "extracted": date.today().isoformat()},
    }


_EXTRACTORS = {
    "terrain": extract_terrain_features,
    "climate": extract_climate_features,
    "lulc": extract_lulc_features,
    "infrastructure": extract_infrastructure_features,
}


def _realistic(name: str, value) -> bool:
    if value is None:
        return True  # explicit "not mapped" is allowed
    ranges = {
        "annual_precipitation_mm": (0, 6000),
        "mean_temperature_c": (-30, 55),
        "temperature_range_c": (0, 60),
        "wet_days_per_year": (0, 366),
        "distance_to_road_m": (0, 50000),
        "distance_to_hospital_m": (0, 50000),
        "distance_to_school_m": (0, 50000),
        "distance_to_transit_m": (0, 50000),
        "elevation_m": (-100, 3000),
        "slope_deg": (0, 90),
        "aspect_deg": (0, 360),
    }
    lo, hi = ranges.get(name, (float("-inf"), float("inf")))
    return lo <= value <= hi


def validate_feature_block(block: dict) -> dict:
    """Range / completeness / provenance check for one extractor result."""
    if not block.get("available"):
        return {"valid": True, "skipped": True}
    problems = []
    feats = block.get("features", {})
    if not feats:
        problems.append("no features returned though marked available")
    for k, val in feats.items():
        if not _realistic(k, val):
            problems.append(f"{k}={val} outside realistic range")
    prov = block.get("provenance", {})
    for req in ("source", "extracted"):
        if req not in prov:
            problems.append(f"provenance missing '{req}'")
    return {"valid": not problems, "problems": problems}


def build_feature_vector(lat: float, lon: float) -> dict:
    check = ev.validate_coordinate(lat, lon)
    if not check["valid"]:
        return {"error": check["reason"], "coordinate_check": check}

    blocks, available, missing = {}, [], []
    for name, fn in _EXTRACTORS.items():
        b = fn(lat, lon, check["city"])
        v = validate_feature_block(b)
        b["_validation"] = v
        blocks[name] = b
        (available if b.get("available") else missing).append(name)

    return {
        "location": {"latitude": round(float(lat), 6),
                     "longitude": round(float(lon), 6),
                     "in_city_core": check.get("in_city_core", False)},
        "features": blocks,
        "available_blocks": available,
        "missing_blocks": missing,
        "provenance_complete": all(
            blocks[b]["_validation"]["valid"] for b in available
        ),
        "note": "Feature vector is intentionally partial. Missing blocks are "
                "real data gaps, not zeros.",
        "generated": date.today().isoformat(),
    }
