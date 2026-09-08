import json
import time
from pathlib import Path

from fastapi import APIRouter

from services import data_registry as reg
from services import evidence_engine as ee
from services import overpass

router = APIRouter()

DATA_DIR = Path(__file__).resolve().parent.parent / "data"
DATA_DIR.mkdir(exist_ok=True)


def _unavailable(dataset_id: str, what: str) -> dict:
    d = reg.get_dataset(dataset_id) or {}
    return {
        "available": False,
        "layer": what,
        "dataset": dataset_id,
        "status": d.get("status", "UNKNOWN"),
        "reason": d.get("limitations", ""),
        "acquisition": d.get("acquisition", ""),
        "note": "No geometry returned. The platform does not synthesise "
                "layers it has not acquired.",
    }


@router.get("/madurai/boundary")
def boundary():
    path = DATA_DIR / "madurai_boundary_clean.geojson"
    d = reg.get_dataset("madurai_boundary")
    if not path.exists():
        return _unavailable("madurai_boundary", "boundary")
    gj = json.loads(path.read_text(encoding="utf-8"))
    return {
        "available": True,
        "layer": "boundary",
        "dataset": "madurai_boundary",
        "status": d["status"],
        "is_demo": d["status"] == reg.Status.DEMO_ONLY.value,
        "label": ("DEMO DATA — placeholder bounding box"
                  if d["status"] == reg.Status.DEMO_ONLY.value
                  else "Madurai administrative boundary"),
        "geojson": gj,
    }


@router.get("/madurai/infrastructure/osm")
def infrastructure_osm(refresh: bool = False):
    cache = DATA_DIR / "osm_infrastructure.geojson"
    max_age = 7 * 24 * 3600
    if cache.exists() and not refresh and time.time() - cache.stat().st_mtime < max_age:
        return {"available": True, "dataset": "osm_infrastructure",
                "cached": True, "geojson": json.loads(cache.read_text("utf-8"))}

    a = ee.AOI
    bbox = f"{a['lat_min']},{a['lon_min']},{a['lat_max']},{a['lon_max']}"
    # Roads with full geometry (rendered as lines); amenities as points.
    # Kept to the higher road classes so a single Overpass call stays fast.
    q = f"""
    [out:json][timeout:120];
    (
      way({bbox})["highway"~"motorway|trunk|primary"];
      node({bbox})["amenity"~"hospital|clinic"];
      node({bbox})["amenity"~"school|college|university"];
      node({bbox})["railway"="station"];
    );
    out geom tags;
    """
    try:
        els = overpass.query(q, timeout=125.0)
    except overpass.OverpassError as exc:
        return {"available": False, "dataset": "osm_infrastructure",
                "reason": f"Overpass unreachable ({exc})",
                "geojson": {"type": "FeatureCollection", "features": []}}

    feats = []
    for e in els:
        tags = e.get("tags", {})
        if e.get("type") == "way" and "highway" in tags:
            geom = e.get("geometry") or []
            coords = [[p["lon"], p["lat"]] for p in geom if p.get("lon") is not None]
            if len(coords) < 2:
                continue
            feats.append({
                "type": "Feature",
                "geometry": {"type": "LineString", "coordinates": coords},
                "properties": {"kind": "road", "name": tags.get("name", ""),
                               "osm_id": e.get("id"), "highway": tags.get("highway", "")},
            })
            continue
        lat_, lon_ = e.get("lat"), e.get("lon")
        if lat_ is None:
            c = e.get("center") or {}
            lat_, lon_ = c.get("lat"), c.get("lon")
        if lat_ is None:
            continue
        kind = ("hospital" if tags.get("amenity") in ("hospital", "clinic") else
                "education" if tags.get("amenity") in ("school", "college", "university") else
                "rail_station" if tags.get("railway") == "station" else "other")
        feats.append({
            "type": "Feature",
            "geometry": {"type": "Point", "coordinates": [lon_, lat_]},
            "properties": {"kind": kind, "name": tags.get("name", ""),
                           "osm_id": e.get("id")},
        })
    fc = {"type": "FeatureCollection", "features": feats,
          "properties": {"source": "OpenStreetMap via Overpass",
                         "retrieved": time.strftime("%Y-%m-%d")}}
    cache.write_text(json.dumps(fc), encoding="utf-8")
    return {"available": True, "dataset": "osm_infrastructure",
            "cached": False, "count": len(feats), "geojson": fc}


def warm_infrastructure_cache() -> None:
    """Best-effort background prefetch so Explorer + site context have data."""
    for fn in (infrastructure_osm, hydrology_osm, landuse_osm):
        try:
            fn(refresh=False)
        except Exception:  # noqa: BLE001 - warm-up must never crash startup
            pass


def _ways_to_features(els: list, line_tags: tuple, poly_kind: str) -> list:
    """Split Overpass ways into LineString/Polygon features by their tags."""
    feats = []
    for e in els:
        if e.get("type") != "way":
            continue
        tags = e.get("tags", {})
        coords = [[p["lon"], p["lat"]] for p in e.get("geometry", []) if p.get("lon") is not None]
        if len(coords) < 2:
            continue
        is_line = any(t in tags for t in line_tags)
        closed = len(coords) >= 4 and coords[0] == coords[-1]
        if is_line and not closed:
            geom = {"type": "LineString", "coordinates": coords}
            kind = "line"
        else:
            if not closed:
                coords = coords + [coords[0]]
            geom = {"type": "Polygon", "coordinates": [coords]}
            kind = poly_kind
        feats.append({"type": "Feature", "geometry": geom,
                      "properties": {"kind": kind, "name": tags.get("name", ""),
                                     "osm_id": e.get("id"),
                                     "tag": tags.get("waterway") or tags.get("water")
                                     or tags.get("natural") or tags.get("landuse", "")}})
    return feats


@router.get("/madurai/hydrology/osm")
def hydrology_osm(refresh: bool = False):
    cache = DATA_DIR / "osm_hydrology.geojson"
    if cache.exists() and not refresh and time.time() - cache.stat().st_mtime < 7 * 24 * 3600:
        return {"available": True, "dataset": "osm_hydrology", "cached": True,
                "geojson": json.loads(cache.read_text("utf-8"))}
    a = ee.AOI
    bbox = f"{a['lat_min']},{a['lon_min']},{a['lat_max']},{a['lon_max']}"
    q = f"""
    [out:json][timeout:150];
    (
      way({bbox})["natural"="water"];
      way({bbox})["waterway"~"^(river|canal|stream)$"];
      way({bbox})["landuse"~"^(reservoir|basin)$"];
    );
    out geom tags;
    """
    try:
        els = overpass.query(q, timeout=125.0)
    except overpass.OverpassError as exc:
        return {"available": False, "dataset": "osm_hydrology",
                "reason": f"Overpass unreachable ({exc})",
                "geojson": {"type": "FeatureCollection", "features": []}}
    feats = _ways_to_features(els, line_tags=("waterway",), poly_kind="waterbody")
    fc = {"type": "FeatureCollection", "features": feats,
          "properties": {"source": "OpenStreetMap via Overpass",
                         "retrieved": time.strftime("%Y-%m-%d")}}
    cache.write_text(json.dumps(fc), encoding="utf-8")
    return {"available": True, "dataset": "osm_hydrology", "cached": False,
            "count": len(feats), "geojson": fc}


@router.get("/madurai/landuse/osm")
def landuse_osm(refresh: bool = False):
    cache = DATA_DIR / "osm_landuse.geojson"
    if cache.exists() and not refresh and time.time() - cache.stat().st_mtime < 7 * 24 * 3600:
        return {"available": True, "dataset": "osm_landuse", "cached": True,
                "geojson": json.loads(cache.read_text("utf-8"))}
    a = ee.AOI
    bbox = f"{a['lat_min']},{a['lon_min']},{a['lat_max']},{a['lon_max']}"
    q = f"""
    [out:json][timeout:150];
    (
      way({bbox})["landuse"~"^(farmland|farmyard|orchard|residential|commercial|retail|industrial|forest|meadow|quarry|construction)$"];
    );
    out geom tags;
    """
    try:
        els = overpass.query(q, timeout=155.0)
    except overpass.OverpassError as exc:
        return {"available": False, "dataset": "osm_landuse",
                "reason": f"Overpass unreachable ({exc})",
                "geojson": {"type": "FeatureCollection", "features": []}}
    feats = _ways_to_features(els, line_tags=(), poly_kind="landuse")
    fc = {"type": "FeatureCollection", "features": feats,
          "properties": {"source": "OpenStreetMap via Overpass",
                         "retrieved": time.strftime("%Y-%m-%d")}}
    cache.write_text(json.dumps(fc), encoding="utf-8")
    return {"available": True, "dataset": "osm_landuse", "cached": False,
            "count": len(feats), "geojson": fc}


@router.get("/madurai/terrain")
def terrain():
    return _unavailable("copernicus_dem", "terrain")


@router.get("/madurai/lulc")
def lulc_current():
    return _unavailable("esri_lulc_2024", "lulc_current")


@router.get("/madurai/lulc/history")
def lulc_history():
    return _unavailable("esri_lulc_2017", "lulc_history")


@router.get("/madurai/lulc/change")
def lulc_change():
    return _unavailable("esri_lulc_2024", "lulc_change")


@router.get("/madurai/demo-cadastral-grid")
def demo_cadastral_grid(rows: int = 6, cols: int = 6):
    """
    Synthetic grid — LABELLED demo data. Excluded from analytics and evidence.
    Rendered in a distinct style by the frontend.
    """
    a = ee.CITY_CORE
    dlat = (a["lat_max"] - a["lat_min"]) / rows
    dlon = (a["lon_max"] - a["lon_min"]) / cols
    feats = []
    for i in range(rows):
        for j in range(cols):
            y0 = a["lat_min"] + i * dlat
            x0 = a["lon_min"] + j * dlon
            feats.append({
                "type": "Feature",
                "geometry": {"type": "Polygon", "coordinates": [[
                    [x0, y0], [x0 + dlon, y0], [x0 + dlon, y0 + dlat],
                    [x0, y0 + dlat], [x0, y0]]]},
                "properties": {"demo_parcel_id": f"DEMO-{i:02d}-{j:02d}",
                               "is_demo": True},
            })
    return {
        "available": True,
        "dataset": "demo_cadastral_grid",
        "status": reg.Status.DEMO_ONLY.value,
        "is_demo": True,
        "label": "DEMO DATA — SAMPLE DIGITAL CADASTRAL GRID (not real parcels)",
        "analytical_use": "forbidden",
        "geojson": {"type": "FeatureCollection", "features": feats},
    }
