import json
import time
from pathlib import Path

from fastapi import APIRouter, HTTPException

from services import cities as city_registry
from services import data_registry as reg
from services import overpass

router = APIRouter()

DATA_DIR = Path(__file__).resolve().parent.parent / "data"
DATA_DIR.mkdir(exist_ok=True)


def _city_or_404(city: str) -> dict:
    c = city_registry.get_city(city)
    if c is None:
        known = ", ".join(city_registry.CITIES)
        raise HTTPException(404, f"Unknown city '{city}'. Known: {known}.")
    return c


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


@router.get("/cities")
def list_cities():
    return {"cities": [
        {"id": c["id"], "label": c["label"], "state": c["state"], "center": c["center"]}
        for c in city_registry.list_cities()
    ]}


@router.get("/{city}/boundary")
def boundary(city: str):
    c = _city_or_404(city)
    path = DATA_DIR / c["boundary_file"]
    d = reg.get_dataset(c["boundary_dataset_id"])
    if not path.exists():
        return _unavailable(c["boundary_dataset_id"], "boundary")
    gj = json.loads(path.read_text(encoding="utf-8"))
    return {
        "available": True,
        "layer": "boundary",
        "dataset": c["boundary_dataset_id"],
        "status": d["status"],
        "is_demo": d["status"] == reg.Status.DEMO_ONLY.value,
        "label": ("DEMO DATA — placeholder bounding box"
                  if d["status"] == reg.Status.DEMO_ONLY.value
                  else f"{c['label']} administrative boundary"),
        "geojson": gj,
    }


@router.get("/{city}/infrastructure/osm")
def infrastructure_osm(city: str, refresh: bool = False):
    c = _city_or_404(city)
    cache = DATA_DIR / f"osm_infrastructure_{c['id']}.geojson"
    max_age = 7 * 24 * 3600
    if cache.exists() and not refresh and time.time() - cache.stat().st_mtime < max_age:
        return {"available": True, "dataset": "osm_infrastructure",
                "cached": True, "geojson": json.loads(cache.read_text("utf-8"))}

    a = c["aoi"]
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
                               "osm_id": e.get("id"), "osm_type": "way",
                               "highway": tags.get("highway", "")},
            })
            continue
        lat_, lon_ = e.get("lat"), e.get("lon")
        if lat_ is None:
            c2 = e.get("center") or {}
            lat_, lon_ = c2.get("lat"), c2.get("lon")
        if lat_ is None:
            continue
        amenity = tags.get("amenity", "")
        railway = tags.get("railway", "")
        # Keep OSM's own distinction: a "clinic" (single practice) is not a
        # "hospital". A "college"/"university" is not a "school".
        kind = ({"hospital": "hospital", "clinic": "clinic",
                 "school": "school", "college": "college",
                 "university": "college"}.get(amenity)
                or ("rail_station" if railway == "station" else "other"))
        feats.append({
            "type": "Feature",
            "geometry": {"type": "Point", "coordinates": [lon_, lat_]},
            "properties": {"kind": kind,
                           "name": tags.get("name") or tags.get("name:en") or "",
                           "osm_id": e.get("id"), "osm_type": e.get("type", "node"),
                           "osm_tag": f"amenity={amenity}" if amenity else f"railway={railway}",
                           "operator": tags.get("operator", "")},
        })
    fc = {"type": "FeatureCollection", "features": feats,
          "properties": {"source": "OpenStreetMap via Overpass",
                         "retrieved": time.strftime("%Y-%m-%d")}}
    cache.write_text(json.dumps(fc), encoding="utf-8")
    return {"available": True, "dataset": "osm_infrastructure",
            "cached": False, "count": len(feats), "geojson": fc}


# OSM tag value -> everyday-amenity group shown in the land report
AMENITY_GROUPS = {
    "bank": "Banks & ATMs", "atm": "Banks & ATMs",
    "pharmacy": "Pharmacies",
    "police": "Police & fire", "fire_station": "Police & fire",
    "post_office": "Post offices",
    "marketplace": "Shops & markets", "supermarket": "Shops & markets",
    "convenience": "Shops & markets", "general": "Shops & markets",
    "mall": "Shops & markets", "department_store": "Shops & markets",
    "greengrocer": "Shops & markets",
    "bus_station": "Bus stops & stations", "bus_stop": "Bus stops & stations",
    "fuel": "Fuel stations",
    "place_of_worship": "Places of worship",
    "restaurant": "Food & eating out", "cafe": "Food & eating out",
    "fast_food": "Food & eating out",
    "library": "Civic & community", "townhall": "Civic & community",
    "community_centre": "Civic & community", "kindergarten": "Civic & community",
    "park": "Parks & sport", "playground": "Parks & sport",
    "sports_centre": "Parks & sport", "stadium": "Parks & sport",
    "substation": "Power infrastructure", "plant": "Power infrastructure",
}


@router.get("/{city}/amenities/osm")
def amenities_osm(city: str, refresh: bool = False):
    """Everyday amenities (banks, shops, transit, worship, power …) as points."""
    c = _city_or_404(city)
    cache = DATA_DIR / f"osm_amenities_{c['id']}.geojson"
    if cache.exists() and not refresh and time.time() - cache.stat().st_mtime < 7 * 24 * 3600:
        return {"available": True, "dataset": "osm_amenities", "cached": True,
                "geojson": json.loads(cache.read_text("utf-8"))}
    a = c["aoi"]
    bbox = f"{a['lat_min']},{a['lon_min']},{a['lat_max']},{a['lon_max']}"
    q = f"""
    [out:json][timeout:170];
    (
      nwr({bbox})["amenity"~"^(bank|atm|pharmacy|police|fire_station|post_office|marketplace|bus_station|fuel|place_of_worship|restaurant|cafe|fast_food|library|townhall|community_centre|kindergarten)$"];
      nwr({bbox})["shop"~"^(supermarket|convenience|general|mall|department_store|greengrocer)$"];
      node({bbox})["highway"="bus_stop"];
      nwr({bbox})["leisure"~"^(park|playground|sports_centre|stadium)$"];
      nwr({bbox})["power"~"^(substation|plant)$"];
    );
    out center tags;
    """
    try:
        els = overpass.query(q, timeout=175.0)
    except overpass.OverpassError as exc:
        return {"available": False, "dataset": "osm_amenities",
                "reason": f"Overpass unreachable ({exc})",
                "geojson": {"type": "FeatureCollection", "features": []}}
    feats = []
    for e in els:
        tags = e.get("tags", {})
        key, val = next(((k, tags[k]) for k in ("amenity", "shop", "highway", "leisure", "power")
                         if tags.get(k) in AMENITY_GROUPS), (None, None))
        lat_, lon_ = e.get("lat"), e.get("lon")
        if lat_ is None:
            c2 = e.get("center") or {}
            lat_, lon_ = c2.get("lat"), c2.get("lon")
        if key is None or lat_ is None:
            continue
        feats.append({
            "type": "Feature",
            "geometry": {"type": "Point", "coordinates": [lon_, lat_]},
            "properties": {"kind": "amenity", "group": AMENITY_GROUPS[val],
                           "name": tags.get("name") or tags.get("name:en") or "",
                           "osm_id": e.get("id"), "osm_type": e.get("type", "node"),
                           "osm_tag": f"{key}={val}"},
        })
    fc = {"type": "FeatureCollection", "features": feats,
          "properties": {"source": "OpenStreetMap via Overpass",
                         "retrieved": time.strftime("%Y-%m-%d")}}
    cache.write_text(json.dumps(fc), encoding="utf-8")
    return {"available": True, "dataset": "osm_amenities", "cached": False,
            "count": len(feats), "geojson": fc}


def warm_infrastructure_cache() -> None:
    """Best-effort background prefetch so Explorer + site context have data."""
    for city_id in city_registry.CITIES:
        for fn in (infrastructure_osm, hydrology_osm, landuse_osm, amenities_osm):
            try:
                fn(city_id, refresh=False)
            except Exception:  # noqa: BLE001 - warm-up must never crash startup
                pass
        # nearest-facility index + city-core benchmark for the land profile
        from services import land_profile  # lazy: avoids an import cycle
        land_profile.warm(city_id)


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


@router.get("/{city}/hydrology/osm")
def hydrology_osm(city: str, refresh: bool = False):
    c = _city_or_404(city)
    cache = DATA_DIR / f"osm_hydrology_{c['id']}.geojson"
    if cache.exists() and not refresh and time.time() - cache.stat().st_mtime < 7 * 24 * 3600:
        return {"available": True, "dataset": "osm_hydrology", "cached": True,
                "geojson": json.loads(cache.read_text("utf-8"))}
    a = c["aoi"]
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


@router.get("/{city}/landuse/osm")
def landuse_osm(city: str, refresh: bool = False):
    c = _city_or_404(city)
    cache = DATA_DIR / f"osm_landuse_{c['id']}.geojson"
    if cache.exists() and not refresh and time.time() - cache.stat().st_mtime < 7 * 24 * 3600:
        return {"available": True, "dataset": "osm_landuse", "cached": True,
                "geojson": json.loads(cache.read_text("utf-8"))}
    a = c["aoi"]
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


@router.get("/{city}/terrain")
def terrain(city: str):
    _city_or_404(city)
    return _unavailable("copernicus_dem", "terrain")


@router.get("/{city}/lulc")
def lulc_current(city: str):
    _city_or_404(city)
    return _unavailable("esri_lulc_2024", "lulc_current")


@router.get("/{city}/lulc/history")
def lulc_history(city: str):
    _city_or_404(city)
    return _unavailable("esri_lulc_2017", "lulc_history")


@router.get("/{city}/lulc/change")
def lulc_change(city: str):
    _city_or_404(city)
    return _unavailable("esri_lulc_2024", "lulc_change")


@router.get("/{city}/demo-cadastral-grid")
def demo_cadastral_grid(city: str, parcels: int = 60, seed: int = 1):
    """
    Synthetic parcel subdivision — LABELLED demo data. Excluded from
    analytics and evidence. Rendered in a distinct style by the frontend.

    Recursively splits the city core into `parcels` irregular rectangular
    parcels (a randomized k-d style cut), which reads far more like a real
    cadastral fabric than a uniform grid, while staying honestly synthetic.
    """
    c = _city_or_404(city)
    from services import cadastral_demo

    feats = cadastral_demo.generate_parcels(c["cadastral_patch"], parcels, seed)
    return {
        "available": True,
        "dataset": "demo_cadastral_grid",
        "status": reg.Status.DEMO_ONLY.value,
        "is_demo": True,
        "label": "DEMO DATA — SAMPLE DIGITAL CADASTRAL FABRIC (not real parcels)",
        "analytical_use": "forbidden",
        "geojson": {"type": "FeatureCollection", "features": feats},
    }
