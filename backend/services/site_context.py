"""
Site context for a point - water, land use, development - computed LOCALLY from
the cached area-of-interest OpenStreetMap layers:

    backend/data/osm_hydrology.geojson       (rivers, canals, waterbodies)
    backend/data/osm_landuse.geojson         (farmland / residential / ...)
    backend/data/osm_infrastructure.geojson  (major roads, health, education)

Those AOI layers are fetched once by the /gis endpoints (and a startup warm-up)
and reused here, so this runs in milliseconds with no Overpass call on the
request path. If a layer has not been fetched yet the corresponding block
degrades to an explicit gap - never a guess.

OSM land use is a *tag*, not a classified satellite raster; confidence is
capped at medium and the provenance says so.
"""
from __future__ import annotations

import json
import time
from datetime import date
from pathlib import Path

from services import data_registry as reg
from services import geo

_DATA = Path(__file__).resolve().parent.parent / "data"
_WATER_M = 2500      # water search radius
_DEV_M = 600         # development context radius

_CATEGORY = {
    "farmland": "Agricultural", "farmyard": "Agricultural", "orchard": "Agricultural",
    "vineyard": "Agricultural", "plant_nursery": "Agricultural", "allotments": "Agricultural",
    "residential": "Built-up / developed", "commercial": "Built-up / developed",
    "retail": "Built-up / developed", "industrial": "Built-up / developed",
    "construction": "Built-up / developed", "garages": "Built-up / developed",
    "forest": "Natural / vegetation", "meadow": "Natural / vegetation",
    "grass": "Natural / vegetation", "scrub": "Natural / vegetation",
    "recreation_ground": "Open / recreation", "cemetery": "Open / recreation",
    "reservoir": "Water", "basin": "Water", "water": "Water", "wetland": "Water",
    "quarry": "Extractive", "brownfield": "Vacant / undeveloped",
    "greenfield": "Vacant / undeveloped",
}
_BUILT = {"residential", "commercial", "retail", "industrial", "construction", "garages"}
_AGRI = {"farmland", "farmyard", "orchard", "vineyard", "allotments"}


def _load(name: str):
    p = _DATA / name
    if not p.exists():
        return None
    try:
        fc = json.loads(p.read_text("utf-8"))
        return fc, (fc.get("properties") or {}).get("retrieved", "")
    except Exception:  # noqa: BLE001
        return None


def _bbox_hit(lat, lon, geom, pad_deg):
    """Cheap pre-filter: does geom have any vertex within pad_deg of the point?"""
    for glon, glat in geo.iter_lonlat(geom):
        if abs(glat - lat) <= pad_deg and abs(glon - lon) <= pad_deg:
            return True
    return False


# --- water --------------------------------------------------------
def _water(lat: float, lon: float, city: str) -> dict:
    loaded = _load(f"osm_hydrology_{city}.geojson")
    if loaded is None:
        return {"available": False,
                "reason": "OSM hydrology layer not fetched yet - open the "
                          "Explorer 'Water bodies & rivers' layer once, or wait "
                          "for the startup warm-up."}
    fc, retrieved = loaded
    pad = _WATER_M / 111_000 * 1.4

    rivers, canals, bodies = [], [], []
    for f in fc.get("features", []):
        g, props = f.get("geometry", {}), f.get("properties", {})
        tag = (props.get("tag") or "").lower()
        if not _bbox_hit(lat, lon, g, pad):
            continue
        d = geo.min_distance_m(lat, lon, g)
        if d is None or d > _WATER_M:
            continue
        rec = {"name": props.get("name") or None, "osm_type": tag or props.get("kind"),
               "distance_m": round(d)}
        if tag in ("river", "stream"):
            rivers.append(rec)
        elif tag in ("canal", "drain", "ditch"):
            canals.append(rec)
        else:
            bodies.append(rec)

    rivers.sort(key=lambda r: r["distance_m"])
    canals.sort(key=lambda r: r["distance_m"])
    bodies.sort(key=lambda r: r["distance_m"])
    nr = rivers[0] if rivers else None
    nb = bodies[0] if bodies else None
    nc = canals[0] if canals else None

    parts = []
    if nr:
        parts.append(f"{nr['name'] or 'a river/stream'} ~{nr['distance_m']} m")
    if nb:
        parts.append(f"{nb['name'] or 'a tank/pond/reservoir'} ~{nb['distance_m']} m")
    if nc and not nr:
        parts.append(f"a canal/channel ~{nc['distance_m']} m")
    summary = ("Nearest surface water: " + "; ".join(parts) + "."
               if parts else
               f"No river, canal or waterbody mapped in OpenStreetMap within "
               f"{_WATER_M} m of this point.")

    return {
        "available": True,
        "nearest_river_or_stream": nr,
        "nearest_waterbody": nb,
        "nearest_canal_or_drain": nc,
        "counts_within_2_5km": {"rivers_streams": len(rivers),
                                "canals_drains": len(canals),
                                "waterbodies": len(bodies)},
        "coast": {"in_search_radius": False,
                  "note": f"This is an inland location; no coastline is mapped "
                          f"within the {_WATER_M} m search radius."},
        "summary": summary,
        "retrieved": retrieved,
    }


# --- land use ----------------------------------------------------
def _land_use(lat: float, lon: float, city: str) -> dict:
    loaded = _load(f"osm_landuse_{city}.geojson")
    if loaded is None:
        return {"available": False,
                "reason": "OSM land-use layer not fetched yet - open the "
                          "Explorer 'Land use' layer once, or wait for the "
                          "startup warm-up (first build is slow)."}
    fc, retrieved = loaded
    pad = _DEV_M / 111_000 * 1.6

    containing, nearby = [], {}
    for f in fc.get("features", []):
        g, props = f.get("geometry", {}), f.get("properties", {})
        tag = (props.get("tag") or "").lower()
        if not tag or not _bbox_hit(lat, lon, g, pad):
            continue
        nearby[tag] = nearby.get(tag, 0) + 1
        if geo.point_in_geom(lon, lat, g):
            containing.append((tag, props.get("name")))

    on_parcel = None
    if containing:
        tag, name = containing[0]
        on_parcel = {"osm_tag": f"landuse={tag}",
                     "category": _CATEGORY.get(tag, "Other / unclassified"),
                     "name": name}

    cats: dict[str, int] = {}
    for t, n in nearby.items():
        c = _CATEGORY.get(t, "Other / unclassified")
        cats[c] = cats.get(c, 0) + n
    total = sum(cats.values())
    dominant = max(cats, key=cats.get) if cats else None
    # Only trust the surrounding mix when there is a real sample AND a clear
    # majority — otherwise a couple of stray residential polygons must not turn
    # an empty rural point "built-up".
    confident = bool(dominant and total >= 4 and cats[dominant] / total >= 0.55)

    if on_parcel:
        cat = on_parcel["category"]
        summary = f"This point falls on OSM {on_parcel['osm_tag']} -> {cat}."
        if confident and dominant != cat:
            summary += f" Surroundings lean {dominant.lower()}."
    elif confident:
        cat = f"{dominant} (surrounding area)"
        summary = (f"No land-use polygon covers this exact point in OSM, but the "
                   f"mapped land within {_DEV_M} m is predominantly "
                   f"{dominant.lower()} ({cats[dominant]}/{total} parcels).")
    elif total:
        cat = "Unclassified in OSM (sparse)"
        mix = ", ".join(f"{k} x{v}" for k, v in sorted(nearby.items(), key=lambda x: -x[1])[:4])
        summary = (f"Only {total} land-use polygon(s) mapped within {_DEV_M} m "
                   f"({mix}) - not enough for a land-use call. A classified "
                   f"satellite land-cover layer (Esri / Sentinel-2) is needed.")
    else:
        cat = "Unclassified in OSM"
        summary = (f"OpenStreetMap has no land-use polygons within {_DEV_M} m of "
                   f"this point. A classified satellite land-cover layer "
                   f"(Esri / Sentinel-2) is needed for a definitive answer.")

    return {
        "available": True,
        "on_parcel": on_parcel,
        "nearby_tags_within_600m": nearby,
        "nearby_categories": cats,
        "effective_category": cat,
        "is_agricultural": "Agricultural" in cat,
        "is_built_up": "Built-up" in cat,
        "summary": summary,
        "retrieved": retrieved,
    }


# --- development ----------------------------------------------
def _development(lat: float, lon: float, land: dict, city: str) -> dict:
    infra = _load(f"osm_infrastructure_{city}.geojson")
    road_segments = pois = 0
    if infra is not None:
        fc, _ = infra
        pad = _DEV_M / 111_000 * 1.6
        for f in fc.get("features", []):
            g = f.get("geometry", {})
            kind = (f.get("properties") or {}).get("kind")
            if not _bbox_hit(lat, lon, g, pad):
                continue
            d = geo.min_distance_m(lat, lon, g)
            if d is None or d > _DEV_M:
                continue
            if kind == "road":
                road_segments += 1
            else:
                pois += 1

    nearby = land.get("nearby_tags_within_600m", {}) if land.get("available") else {}
    built = sum(v for k, v in nearby.items() if k in _BUILT)
    agri = sum(v for k, v in nearby.items() if k in _AGRI)
    on_built = "Built-up" in ((land.get("on_parcel") or {}).get("category") or "")
    on_agri = "Agricultural" in ((land.get("on_parcel") or {}).get("category") or "")

    if on_built or built >= 8:
        level = "Urban / built-up"
    elif built >= 3:
        level = "Suburban / peri-urban (mixed)"
    elif on_agri or agri >= 3:
        level = "Agricultural / rural"
    elif built >= 1 or agri >= 1 or road_segments >= 3:
        level = "Sparsely developed"
    else:
        level = "Undeveloped / open land"

    summary = {
        "Urban / built-up": "Sits in or beside mapped residential/commercial land with a dense road network - an established built-up area.",
        "Suburban / peri-urban (mixed)": "Some built land and roads nearby with open gaps - a developing / peri-urban edge.",
        "Agricultural / rural": "Surrounded mainly by farmland - rural / agrarian land.",
        "Sparsely developed": "A few roads but little mapped built or farm land - thinly developed.",
        "Undeveloped / open land": "No built-up or farm land-use and almost no roads mapped nearby - open, undeveloped land.",
    }[level]

    return {
        "available": True,
        "level": level,
        "built_landuse_polys_within_600m": built,
        "agricultural_landuse_polys_within_600m": agri,
        "major_road_segments_within_600m": road_segments,
        "mapped_facilities_within_600m": pois,
        "summary": summary,
        "method": "OpenStreetMap land-use + road-network proxy. Not a census, "
                  "and not a built-up-area raster (GHSL / night-lights) - those "
                  "remain data gaps.",
    }


def build_site_context(lat: float, lon: float, city: str) -> dict:
    if not (reg.can_use_for_analysis("osm_landuse")
            and reg.can_use_for_analysis("osm_hydrology")):
        return {"available": False,
                "reason": "OSM land-use / hydrology not analytically eligible."}

    water = _water(lat, lon, city)
    land = _land_use(lat, lon, city)
    dev = _development(lat, lon, land, city)

    if not water["available"] and not land["available"]:
        return {"available": False,
                "reason": water.get("reason") or land.get("reason")
                or "OSM AOI layers not fetched yet."}

    return {
        "available": True,
        "water": water,
        "land_use": land,
        "development": dev,
        "provenance": {
            "datasets": ["osm_hydrology", "osm_landuse", "osm_infrastructure"],
            "source": "OpenStreetMap via Overpass API (cached AOI layers)",
            "retrieved": water.get("retrieved") or land.get("retrieved")
            or date.today().isoformat(),
            "confidence": "medium",
            "note": "Community-mapped data. OSM land use is a tag, not a "
                    "classified raster; completeness varies by locality.",
        },
    }
