"""
Evidence engine — assembles *verified* evidence for a location and reports
*honest gaps* for everything the platform cannot yet substantiate.

Hard rules:
  * Never invent a value. If a source is unavailable, it becomes a gap.
  * Only datasets that pass data_registry.can_use_for_analysis() may
    contribute verified evidence.
  * Conclusions are descriptive, never predictive.
"""
from __future__ import annotations

import json
import math
from datetime import date
from pathlib import Path

import httpx

from services import data_registry as reg

_DATA_DIR = Path(__file__).resolve().parent.parent / "data"

# Prototype area of interest. Wider than the city core so district-edge
# clicks still resolve, but callers are told when a point is outside the core.
AOI = {"lat_min": 9.75, "lat_max": 10.15, "lon_min": 77.95, "lon_max": 78.35}
CITY_CORE = {"lat_min": 9.86, "lat_max": 9.98, "lon_min": 78.06, "lon_max": 78.18}

_HTTP_TIMEOUT = 8.0


# --- coordinate handling ------------------------------------------------
def validate_coordinate(lat: float, lon: float) -> dict:
    try:
        lat = float(lat)
        lon = float(lon)
    except (TypeError, ValueError):
        return {"valid": False, "reason": "Latitude/longitude must be numbers."}
    if not (-90 <= lat <= 90 and -180 <= lon <= 180):
        return {"valid": False, "reason": "Coordinate out of global range."}
    in_aoi = (AOI["lat_min"] <= lat <= AOI["lat_max"]
              and AOI["lon_min"] <= lon <= AOI["lon_max"])
    if not in_aoi:
        return {
            "valid": False,
            "reason": "Outside the Madurai prototype area of interest.",
            "aoi": AOI,
        }
    in_core = (CITY_CORE["lat_min"] <= lat <= CITY_CORE["lat_max"]
               and CITY_CORE["lon_min"] <= lon <= CITY_CORE["lon_max"])
    return {"valid": True, "in_city_core": in_core, "lat": lat, "lon": lon}


def _haversine_m(lat1, lon1, lat2, lon2) -> float:
    r = 6371000.0
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dp = math.radians(lat2 - lat1)
    dl = math.radians(lon2 - lon1)
    a = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 2 * r * math.asin(math.sqrt(a))


# Climate normals barely move day to day; cache by ~1 km rounded coord for the
# process lifetime so repeat evidence/feature/suitability calls stay fast.
_CLIMATE_CACHE: dict[tuple[float, float], dict] = {}


# --- verified evidence sources ---------------------------------------------
def _climate_evidence(lat: float, lon: float) -> dict:
    """Real ERA5 climate normals from Open-Meteo Archive (keyless)."""
    if not reg.can_use_for_analysis("open_meteo_climate"):
        return {"ok": False, "reason": "open_meteo_climate not analytically eligible"}

    ckey = (round(lat, 2), round(lon, 2))
    if ckey in _CLIMATE_CACHE:
        return _CLIMATE_CACHE[ckey]
    end = date.today().replace(year=date.today().year - 1)
    start = end.replace(year=end.year - 9)  # ~10 climate years
    url = "https://archive-api.open-meteo.com/v1/archive"
    params = {
        "latitude": round(lat, 4),
        "longitude": round(lon, 4),
        "start_date": start.isoformat(),
        "end_date": end.isoformat(),
        "daily": "temperature_2m_mean,precipitation_sum",
        "timezone": "auto",
    }
    try:
        with httpx.Client(timeout=_HTTP_TIMEOUT) as c:
            r = c.get(url, params=params)
            r.raise_for_status()
            data = r.json()
    except Exception as exc:  # noqa: BLE001 - degrade to gap, never fabricate
        return {"ok": False, "reason": f"Open-Meteo unreachable: {exc.__class__.__name__}"}

    daily = data.get("daily", {})
    temps = [t for t in daily.get("temperature_2m_mean", []) if t is not None]
    precs = [p for p in daily.get("precipitation_sum", []) if p is not None]
    if not temps or not precs:
        return {"ok": False, "reason": "Open-Meteo returned no usable values"}

    years = max(1, len(precs) / 365.25)
    result = {
        "ok": True,
        "value": {
            "period": f"{start.isoformat()} to {end.isoformat()}",
            "mean_temperature_c": round(sum(temps) / len(temps), 1),
            "min_daily_mean_temp_c": round(min(temps), 1),
            "max_daily_mean_temp_c": round(max(temps), 1),
            "annual_precipitation_mm": round(sum(precs) / years, 0),
            "wet_days_per_year": round(sum(1 for p in precs if p >= 1.0) / years, 0),
        },
        "provenance": {
            "dataset": "open_meteo_climate",
            "source": "Open-Meteo Archive API (ERA5)",
            "resolution": "~9 km reanalysis grid",
            "retrieved": date.today().isoformat(),
            "confidence": "high",
        },
    }
    _CLIMATE_CACHE[ckey] = result
    return result


def _iter_feature_points(feat: dict):
    """Yield (lat, lon) vertices for Point / LineString / (Multi)Polygon."""
    geom = feat.get("geometry") or {}
    gtype, coords = geom.get("type"), geom.get("coordinates")
    if not coords:
        return
    if gtype == "Point":
        yield coords[1], coords[0]
    elif gtype in ("LineString", "MultiPoint"):
        for c in coords:
            yield c[1], c[0]
    elif gtype in ("Polygon", "MultiLineString"):
        for ring in coords:
            for c in ring:
                yield c[1], c[0]
    elif gtype == "MultiPolygon":
        for poly in coords:
            for ring in poly:
                for c in ring:
                    yield c[1], c[0]


def _infrastructure_evidence(lat: float, lon: float) -> dict:
    """
    Nearest road / hospital / school / transit, computed locally from the
    cached AOI OpenStreetMap layer (backend/data/osm_infrastructure.geojson).

    No network call on the request path: the layer is fetched once by the
    /gis infrastructure endpoint (and a startup warm-up) and reused here.
    Road distance is approximated as distance to the nearest road vertex.
    """
    if not reg.can_use_for_analysis("osm_infrastructure"):
        return {"ok": False, "reason": "osm_infrastructure not analytically eligible"}

    cache = _DATA_DIR / "osm_infrastructure.geojson"
    if not cache.exists():
        return {"ok": False, "reason": "OSM infrastructure layer is still "
                                       "warming up; retry shortly."}
    try:
        fc = json.loads(cache.read_text(encoding="utf-8"))
    except Exception as exc:  # noqa: BLE001
        return {"ok": False, "reason": f"cached layer unreadable: {exc.__class__.__name__}"}

    # nearest by the individual kinds emitted by the /gis layer
    raw = {"road": None, "hospital": None, "clinic": None,
           "school": None, "college": None, "rail_station": None}
    for feat in fc.get("features", []):
        kind = (feat.get("properties") or {}).get("kind")
        if kind not in raw:
            continue
        for plat, plon in _iter_feature_points(feat):
            d = _haversine_m(lat, lon, plat, plon)
            if raw[kind] is None or d < raw[kind]:
                raw[kind] = d

    def nearest(*keys):
        vals = [raw[k] for k in keys if raw[k] is not None]
        return round(min(vals), 0) if vals else None

    if all(v is None for v in raw.values()):
        return {"ok": False, "reason": "No usable features in the cached layer."}

    return {
        "ok": True,
        "value": {
            "distance_to_road_m": nearest("road"),
            "distance_to_hospital_m": nearest("hospital"),
            "distance_to_clinic_or_hospital_m": nearest("hospital", "clinic"),
            "distance_to_school_m": nearest("school"),
            "distance_to_school_or_college_m": nearest("school", "college"),
            "distance_to_railway_station_m": nearest("rail_station"),
        },
        "provenance": {
            "dataset": "osm_infrastructure",
            "source": "OpenStreetMap via Overpass API (cached AOI layer)",
            "retrieved": (fc.get("properties") or {}).get("retrieved",
                                                          date.today().isoformat()),
            "confidence": "medium",
            "note": "Road distance is to the nearest road vertex of the "
                    "motorway/trunk/primary network. 'null' means nothing of "
                    "that type is in the cached AOI layer, not that none exists.",
        },
    }


# Everything the platform is expected to know but cannot yet substantiate.
_KNOWN_GAPS = [
    ("terrain_elevation_slope", "copernicus_dem",
     "Elevation, slope and aspect need the Copernicus DEM, which has not been "
     "acquired to local storage yet."),
    ("land_cover_class", "esri_lulc_2024",
     "Current land-cover class requires the Esri/Sentinel-2 classified raster "
     "(open, acquisition pending)."),
    ("land_cover_change", "esri_lulc_2017",
     "2017→2024 land-cover change needs both Esri epochs (acquisition pending)."),
    ("cadastral_parcel", "cadastral_geometry",
     "Parcel boundary is government data — OFFICIAL ACCESS REQUIRED."),
    ("ownership_title", "ownership_records",
     "Ownership/title is restricted personal data — OFFICIAL ACCESS REQUIRED."),
    ("flood_hazard", "tnsdma_flood_hazard",
     "Flood/inundation hazard is held by TNSDMA — OFFICIAL ACCESS REQUIRED."),
    ("zoning_landuse_plan", "master_plan",
     "Statutory zoning exists only as Master Plan PDFs — DOCUMENT ONLY, not "
     "digitised."),
    ("soil_capability", "nbsslup_soil",
     "Soil series / land-capability is a licensed NBSS&LUP product — OFFICIAL "
     "ACCESS REQUIRED."),
    ("groundwater", "cgwb_groundwater",
     "Groundwater level/quality series is held by CGWB — OFFICIAL ACCESS "
     "REQUIRED."),
]


def get_location_evidence(lat: float, lon: float,
                          include_site_context: bool = False) -> dict:
    check = validate_coordinate(lat, lon)
    if not check["valid"]:
        return {"error": check["reason"], "coordinate_check": check}

    verified: list[dict] = []
    gaps: list[dict] = []

    for key, fn in (("climate", _climate_evidence),
                    ("infrastructure", _infrastructure_evidence)):
        res = fn(lat, lon)
        if res.get("ok"):
            verified.append({"topic": key, **{k: res[k] for k in ("value", "provenance")}})
        else:
            gaps.append({
                "topic": key,
                "reason": res.get("reason", "unavailable"),
                "resolution": "Retry when the live source is reachable.",
            })

    # Site context (water / land use / development) from live OSM. This hits
    # Overpass and can be slow, so it is opt-in — the frontend requests it on a
    # separate call with its own loading state; /report never blocks on it.
    if include_site_context:
        from services import site_context as sc  # lazy: avoids an import cycle
        ctx = sc.build_site_context(lat, lon)
        if ctx.get("available"):
            for topic in ("water", "land_use", "development"):
                verified.append({"topic": topic, "value": ctx[topic],
                                 "provenance": ctx["provenance"]})
        else:
            for topic in ("water", "land_use", "development"):
                gaps.append({"topic": topic,
                             "reason": ctx.get("reason", "OSM site context unavailable"),
                             "resolution": "Retry when Overpass is reachable."})

    for topic, ds_id, reason in _KNOWN_GAPS:
        d = reg.get_dataset(ds_id)
        gaps.append({
            "topic": topic,
            "reason": reason,
            "dataset": ds_id,
            "dataset_status": d["status"] if d else "UNKNOWN",
            "resolution": d["acquisition"] if d else "",
        })

    return {
        "location": {
            "latitude": round(float(lat), 6),
            "longitude": round(float(lon), 6),
            "in_city_core": check.get("in_city_core", False),
            "area_of_interest": "Madurai prototype AOI",
        },
        "verified_evidence": verified,
        "data_gaps": gaps,
        "counts": {"verified": len(verified), "gaps": len(gaps)},
        "generated": date.today().isoformat(),
    }


def build_report(lat: float, lon: float) -> dict:
    ev = get_location_evidence(lat, lon)
    if "error" in ev:
        return ev

    matrix = []
    for v in ev["verified_evidence"]:
        matrix.append({"topic": v["topic"], "status": "VERIFIED",
                       "source": v["provenance"]["source"],
                       "confidence": v["provenance"].get("confidence", "n/a")})
    for g in ev["data_gaps"]:
        matrix.append({"topic": g["topic"], "status": "GAP",
                       "source": g.get("dataset", "—"),
                       "confidence": "none"})

    n_v, n_g = ev["counts"]["verified"], ev["counts"]["gaps"]
    conclusion = (
        f"For this location the platform can currently verify {n_v} topic(s) "
        f"from real sources and has {n_g} open data gap(s). This report is a "
        f"descriptive statement of what is and is not known; it contains no "
        f"prediction, valuation, or recommendation. Analytical products should "
        f"not be generated until the gaps marked OFFICIAL ACCESS REQUIRED or "
        f"acquisition-pending are closed."
    )

    return {
        "report_type": "location_evidence",
        "location": ev["location"],
        "verified_evidence": ev["verified_evidence"],
        "data_gaps": ev["data_gaps"],
        "evidence_matrix": matrix,
        "conclusion": conclusion,
        "generated": ev["generated"],
        "disclaimer": "Evidence-first prototype. Descriptive only. Not for "
                      "legal, valuation, or statutory use.",
    }


def provenance_manifest() -> dict:
    """All datasets with provenance — the export/manifest payload."""
    return {
        "generated": date.today().isoformat(),
        "platform": "National Digital Platform — Madurai prototype",
        "datasets": [
            {k: d[k] for k in ("id", "name", "status", "source", "authority",
                               "license", "acquisition_date", "last_updated",
                               "limitations", "analytical_eligible")}
            for d in reg.DATASETS
        ],
        "analytical_gate": "status == AVAILABLE and analytical_eligible == true",
    }
