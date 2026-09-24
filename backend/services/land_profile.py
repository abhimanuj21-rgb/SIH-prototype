"""
Land profile — the plain-language "outcome" layer over the verified evidence.

It answers, for one point, the questions a non-specialist actually asks:

  * How well served is this land?   -> per-facility access scores (0-100)
  * Compared to what?               -> the same measure at a grid of sample
                                       points across the same city core
  * What could it be good for?      -> an *indicative* use-fit screen
  * How sure are we?                -> evidence coverage: verified vs open checks

Rules carried over from the evidence engine:
  * Every number is derived from a verified, gate-passing dataset (OSM
    infrastructure / hydrology / land use, Open-Meteo climate). Nothing is
    invented; a missing input makes a factor "not scored", never a guess.
  * The access bands below are this platform's own transparent reference
    bands, not a statutory norm, and the output says so.
  * Use fit is an indicative screen on access + site character only. It is
    NOT a zoning, valuation or legal determination; the checks that would be
    needed before any real decision (zoning, flood, terrain, title) are listed
    alongside every fit.
"""
from __future__ import annotations

import json
import math
import threading
from pathlib import Path

from services import cities as city_registry
from services import data_registry as reg
from services import evidence_engine as ee
from services import land_details as ld
from services import site_context as sc

_DATA = Path(__file__).resolve().parent.parent / "data"

# key, label, OSM kinds, (excellent, good, fair) distance bands in metres,
# weight in the overall access score (0 = shown but not part of the score)
FACILITIES = [
    ("road", "Main road", ("road",), (100, 400, 1500), 30),
    ("health", "Hospital / clinic", ("hospital", "clinic"), (500, 1500, 4000), 25),
    ("school", "School / college", ("school", "college"), (500, 1500, 4000), 25),
    ("rail", "Railway station", ("rail_station",), (1500, 4000, 10000), 20),
    ("water", "Surface water", None, (300, 1000, 2500), 0),
]
_WATER_TAGS = {"river", "stream", "canal", "drain", "ditch", "reservoir",
               "pond", "lake", "water", "basin", "wetland"}

BAND_NOTE = ("Access bands are this platform's own reference bands "
             "(e.g. hospital / clinic: excellent <=0.5 km, good <=1.5 km, fair <=4 km), "
             "not a statutory norm.")


# --- scoring -------------------------------------------------------------
def access_score(d: float | None, bands: tuple[int, int, int]) -> int | None:
    """Piecewise-linear 0-100: 100 inside 'excellent', 70 at 'good',
    40 at 'fair', easing to 10 at twice 'fair'."""
    if d is None:
        return None
    b1, b2, b3 = bands
    pts = [(0, 100), (b1, 100), (b2, 70), (b3, 40), (2 * b3, 10)]
    if d >= pts[-1][0]:
        return 10
    for (x0, y0), (x1, y1) in zip(pts, pts[1:]):
        if x0 <= d <= x1:
            return round(y0 + (y1 - y0) * (d - x0) / ((x1 - x0) or 1))
    return 10


def rating(score: float | None) -> str:
    if score is None:
        return "Not scored"
    return ("Excellent" if score >= 85 else "Good" if score >= 65
            else "Fair" if score >= 40 else "Poor")


# --- nearest-feature index (per city, built once) ------------------------
class _NearestIndex:
    """Bucketed vertex index: fast nearest-vertex queries without numpy."""
    CELL = 0.01  # degrees (~1.1 km)

    def __init__(self, verts: list[tuple[float, float, str]]):
        self.cells: dict[tuple[int, int], list] = {}
        for la, lo, name in verts:
            self.cells.setdefault((int(la // self.CELL), int(lo // self.CELL)),
                                  []).append((la, lo, name))
        self.empty = not verts

    def nearest(self, lat: float, lon: float, max_ring: int = 60):
        if self.empty:
            return None, None
        ci, cj = int(lat // self.CELL), int(lon // self.CELL)
        best, best_name = None, None
        for r in range(max_ring + 1):
            for i in range(ci - r, ci + r + 1):
                for j in range(cj - r, cj + r + 1):
                    if max(abs(i - ci), abs(j - cj)) != r:
                        continue
                    for la, lo, name in self.cells.get((i, j), ()):
                        d = ee._haversine_m(lat, lon, la, lo)
                        if best is None or d < best:
                            best, best_name = d, name
            # anything in ring r+1 is at least r * cell away
            if best is not None and best <= r * self.CELL * 105_000:
                break
        return best, best_name


_INDEX: dict[str, dict] = {}
_BENCH: dict[str, dict] = {}
_LOCK = threading.Lock()


def _load(name: str):
    p = _DATA / name
    if not p.exists():
        return None
    try:
        return json.loads(p.read_text("utf-8"))
    except Exception:  # noqa: BLE001
        return None


def _city_index(city: str) -> dict:
    with _LOCK:
        if city in _INDEX:
            return _INDEX[city]
    verts: dict[str, list] = {k: [] for k, *_ in FACILITIES}
    infra = _load(f"osm_infrastructure_{city}.geojson")
    for f in (infra or {}).get("features", []):
        props = f.get("properties") or {}
        for key, _lbl, kinds, _b, _w in FACILITIES:
            if kinds and props.get("kind") in kinds:
                name = props.get("name") or ""
                for la, lo in ee._iter_feature_points(f):
                    verts[key].append((la, lo, name))
    hydro = _load(f"osm_hydrology_{city}.geojson")
    for f in (hydro or {}).get("features", []):
        props = f.get("properties") or {}
        if (props.get("tag") or "").lower() not in _WATER_TAGS:
            continue
        name = props.get("name") or ""
        for la, lo in ee._iter_feature_points(f):
            verts["water"].append((la, lo, name))
    idx = {
        "infra_ok": infra is not None,
        "hydro_ok": hydro is not None,
        "by_key": {k: _NearestIndex(v) for k, v in verts.items()},
    }
    # don't cache a half-warmed index — the layers may still be downloading
    if infra is not None and hydro is not None:
        with _LOCK:
            _INDEX[city] = idx
    return idx


def _nearest_all(idx: dict, lat: float, lon: float) -> dict:
    return {k: idx["by_key"][k].nearest(lat, lon) for k, *_ in FACILITIES}


def _percentile(sorted_vals: list[float], p: float) -> float:
    if not sorted_vals:
        return math.nan
    k = (len(sorted_vals) - 1) * p
    f, c = math.floor(k), math.ceil(k)
    return sorted_vals[f] + (sorted_vals[c] - sorted_vals[f]) * (k - f)


def city_benchmark(city: str, n: int = 12) -> dict:
    """Nearest-facility distances at an n x n grid across the city core."""
    with _LOCK:
        if city in _BENCH:
            return _BENCH[city]
    c = city_registry.get_city(city)
    idx = _city_index(city)
    core = c["city_core"]
    samples: dict[str, list[float]] = {k: [] for k, *_ in FACILITIES}
    for i in range(n):
        la = core["lat_min"] + (core["lat_max"] - core["lat_min"]) * (i + .5) / n
        for j in range(n):
            lo = core["lon_min"] + (core["lon_max"] - core["lon_min"]) * (j + .5) / n
            for k, (d, _nm) in _nearest_all(idx, la, lo).items():
                if d is not None:
                    samples[k].append(d)
    out = {"city": city, "city_label": c["label"], "sample_points": n * n,
           "method": f"Nearest-facility distance at a {n}x{n} grid of sample "
                     f"points across the {c['label']} city core, from the same "
                     f"OpenStreetMap layers.",
           "by_key": {}}
    for k, vals in samples.items():
        vals.sort()
        out["by_key"][k] = {
            "median_m": round(_percentile(vals, .5)) if vals else None,
            "p25_m": round(_percentile(vals, .25)) if vals else None,
            "p75_m": round(_percentile(vals, .75)) if vals else None,
            "sorted": vals,
        }
    if idx["infra_ok"] and idx["hydro_ok"]:
        with _LOCK:
            _BENCH[city] = out
    return out


def warm(city: str) -> None:
    """Build the index + benchmark off the request path (startup thread)."""
    try:
        city_benchmark(city)
    except Exception:  # noqa: BLE001 - warm-up must never crash the app
        pass


# --- the profile ---------------------------------------------------------
def _fmt_m(d: float | None) -> str:
    if d is None:
        return "not mapped"
    return f"{d / 1000:.1f} km" if d >= 1000 else f"{round(d)} m"


def _facilities(lat, lon, city) -> tuple[list[dict], dict]:
    idx = _city_index(city)
    bench = city_benchmark(city)
    near = _nearest_all(idx, lat, lon)
    rows = []
    for key, label, _kinds, bands, weight in FACILITIES:
        d, name = near[key]
        b = bench["by_key"].get(key, {})
        vals = b.get("sorted") or []
        better_than = None
        if d is not None and vals:
            better_than = round(100 * sum(1 for v in vals if v > d) / len(vals))
        typ = b.get("median_m")
        rows.append({
            "key": key, "label": label, "weight": weight,
            "distance_m": None if d is None else round(d),
            "nearest_name": name or None,
            "score": access_score(d, bands),
            "rating": rating(access_score(d, bands)),
            "bands_m": {"excellent": bands[0], "good": bands[1], "fair": bands[2]},
            "city_typical_m": typ,
            "city_typical_score": access_score(typ, bands),
            "city_p25_m": b.get("p25_m"), "city_p75_m": b.get("p75_m"),
            "closer_than_pct_of_city": better_than,
        })
    return rows, bench


def _weighted(rows: list[dict], field: str) -> int | None:
    num = den = 0
    for r in rows:
        if r["weight"] and r[field] is not None:
            num += r[field] * r["weight"]
            den += r["weight"]
    return round(num / den) if den else None


# --- everyday amenities (OSM, cached per city) -----------------------------
def amenities_near(lat: float, lon: float, city: str) -> dict:
    """Counts within 500 m / 1 km and the nearest of each amenity group."""
    if not reg.can_use_for_analysis("osm_amenities"):
        return {"available": False, "reason": "osm_amenities not analytically eligible"}
    fc = _load(f"osm_amenities_{city}.geojson")
    if fc is None:
        return {"available": False,
                "reason": "OSM amenities layer is still downloading for this "
                          "city (startup warm-up); retry in a few minutes."}
    groups: dict[str, dict] = {}
    for f in fc.get("features", []):
        props = f.get("properties") or {}
        plon, plat = (f.get("geometry") or {}).get("coordinates", [None, None])
        if plat is None or abs(plat - lat) > 0.05 or abs(plon - lon) > 0.05:
            continue  # ~5 km pre-filter
        d = ee._haversine_m(lat, lon, plat, plon)
        if d > 5000:
            continue
        g = groups.setdefault(props.get("group", "Other"), {
            "group": props.get("group", "Other"), "within_500m": 0, "within_1km": 0,
            "nearest_m": None, "nearest_name": None})
        g["within_500m"] += d <= 500
        g["within_1km"] += d <= 1000
        if g["nearest_m"] is None or d < g["nearest_m"]:
            g["nearest_m"], g["nearest_name"] = round(d), props.get("name") or None
    rows = sorted(groups.values(), key=lambda g: (-g["within_1km"], g["nearest_m"]))
    return {
        "available": True,
        "groups": rows,
        "total_within_500m": sum(g["within_500m"] for g in rows),
        "total_within_1km": sum(g["within_1km"] for g in rows),
        "groups_within_1km": sum(1 for g in rows if g["within_1km"]),
        "retrieved": (fc.get("properties") or {}).get("retrieved"),
        "note": "Features mapped in OpenStreetMap within 5 km. Indian towns are "
                "under-mapped for shops and bus stops, so a low count can mean "
                "'not mapped', not 'absent'.",
    }


def effective_development(osm_level: str | None, lc: dict | None) -> str | None:
    """OSM's development level is a mapping proxy and misses unmapped growth; when
    the Sentinel-2 series is available, what the satellite sees wins."""
    if not lc:
        return osm_level
    b = lc["built_pct"]
    if b >= 50:
        return "Urban / built-up"
    if lc["crops_pct"] >= 50 and b < 35:  # farmland with scattered buildings
        return "Agricultural / rural"
    if b >= 20:
        return "Suburban / peri-urban (mixed)"
    if lc["crops_pct"] >= 40:
        return "Agricultural / rural"
    return osm_level or "Sparsely developed"


def _slope_pts(terrain: dict | None, kind: str) -> int | None:
    if not terrain:
        return None
    d = terrain["slope_deg"]
    table = {"build": [(3, 100), (8, 75), (15, 40)],
             "farm": [(3, 100), (8, 70), (15, 40)],
             "solar": [(3, 100), (8, 70), (15, 35)]}[kind]
    return next((p for lim, p in table if d <= lim), 10)


def _position_pts(terrain: dict | None) -> int | None:
    if not terrain:
        return None
    pos = terrain["relative_position"]
    return 40 if pos.startswith("Lower") else 100 if pos.startswith("Higher") else 85


def _soil_pts(soil: dict | None) -> int | None:
    if not soil:
        return None
    tex = soil["texture_class"]
    t = (100 if tex in ("Loam", "Silt loam", "Sandy loam") else
         85 if tex in ("Clay loam", "Sandy clay loam", "Silty clay loam") else
         70 if tex == "Silt" else 40 if tex in ("Sand", "Loamy sand") else 60)
    ph = soil.get("ph")
    p = None if ph is None else 100 if 6 <= ph <= 7.5 else 70 if 5.5 <= ph <= 8.5 else 35
    soc = soil.get("organic_carbon_g_per_kg")
    c = None if soc is None else 100 if soc >= 10 else 70 if soc >= 5 else 40
    parts = [x for x in (t, p, c) if x is not None]
    return round(sum(parts) / len(parts))


def _use_fits(fac: dict, site: dict | None, climate: dict | None,
              open_checks: list[str], terrain: dict | None = None,
              soil: dict | None = None, amen: dict | None = None,
              lc: dict | None = None) -> list[dict]:
    """Indicative fit for common land uses, from verified factors only."""
    s = {k: v["score"] for k, v in fac.items()}
    land = (site or {}).get("land_use") or {}
    dev = effective_development(((site or {}).get("development") or {}).get("level"), lc) or ""
    urban = dev.startswith("Urban")
    suburban = dev.startswith("Suburban")
    rural = dev.startswith("Agricultural") or dev.startswith("Undeveloped")
    agri_land = bool(land.get("is_agricultural"))
    built_land = bool(land.get("is_built_up"))
    rain = (climate or {}).get("annual_precipitation_mm")
    solar = (climate or {}).get("solar_kwh_m2_day")
    amen_ok = bool((amen or {}).get("available"))
    amen_pts = (min(100, round(100 * amen["groups_within_1km"] / 8)) if amen_ok else None)
    busy = None
    if amen_ok:
        n = sum(g["within_500m"] for g in amen["groups"]
                if g["group"] in ("Shops & markets", "Food & eating out", "Banks & ATMs",
                                  "Bus stops & stations"))
        busy = 100 if n >= 15 else 80 if n >= 8 else 55 if n >= 3 else 25

    def dev_pts(table):
        for prefix, pts in table:
            if dev.startswith(prefix):
                return pts
        return None

    uses = [
        ("residential", "Housing / residential",
         "Homes need daily services close by — health care, schools and a road.",
         [("Hospital / clinic access", s["health"], 20),
          ("School access", s["school"], 20),
          ("Road access", s["road"], 15),
          ("Everyday amenities within 1 km", amen_pts, 15),
          ("Surrounding development",
           dev_pts([("Urban", 90), ("Suburban", 100), ("Sparsely", 55),
                    ("Agricultural", 35), ("Undeveloped", 30)]), 15),
          ("Ground slope", _slope_pts(terrain, "build"), 5),
          ("Not a low spot (drainage)", _position_pts(terrain), 10)],
         ["zoning_landuse_plan", "flood_hazard", "ownership_title"]),
        ("commercial", "Shops / offices (commercial)",
         "Commercial uses live on footfall: strong road frontage and a built-up setting.",
         [("Road access", s["road"], 30),
          ("Surrounding development",
           dev_pts([("Urban", 100), ("Suburban", 70), ("Sparsely", 40),
                    ("Agricultural", 20), ("Undeveloped", 20)]), 25),
          ("Footfall: shops, food, banks, bus stops within 500 m", busy, 25),
          ("Rail access", s["rail"], 15),
          ("Ground slope", _slope_pts(terrain, "build"), 5)],
         ["zoning_landuse_plan", "ownership_title"]),
        ("community", "School / clinic (community facility)",
         "A new facility makes most sense where the site is reachable but the "
         "nearest existing one of that kind is far away.",
         [("Road access", s["road"], 40),
          ("Gap in school coverage",
           None if s["school"] is None else 100 - s["school"], 30),
          ("Gap in health coverage",
           None if s["health"] is None else 100 - s["health"], 30)],
         ["zoning_landuse_plan", "cadastral_parcel", "ownership_title"]),
        ("logistics", "Warehousing / light industry",
         "Needs trucks and freight access, ideally away from dense housing.",
         [("Road access", s["road"], 30),
          ("Rail access", s["rail"], 15),
          ("Surrounding development",
           dev_pts([("Urban", 10), ("Suburban", 85), ("Sparsely", 90),
                    ("Agricultural", 60), ("Undeveloped", 80)]), 35),
          ("Flat ground", _slope_pts(terrain, "build"), 10),
          ("Not a low spot (drainage)", _position_pts(terrain), 10)],
         ["zoning_landuse_plan", "flood_hazard", "terrain_elevation_slope"]),
        ("agriculture", "Farming / agriculture",
         "Crops need water, rain and surrounding farmland — and suffer next to dense built-up land.",
         [("Surface water nearby", s["water"], 10),
          ("Annual rainfall",
           None if rain is None else (100 if rain >= 1000 else 80 if rain >= 800
                                      else 55 if rain >= 600 else 25), 15),
          ("Soil: texture, pH, organic carbon (modelled)", _soil_pts(soil), 20),
          ("Farmland on / around the site (satellite)", min(100, round(lc["crops_pct"] * 1.4)), 25)
          if lc else
          ("Farmland on / around the site (OSM)",
           None if not land.get("available") else
           (100 if agri_land else 10 if built_land else 55), 25),
          ("Surrounding development",
           dev_pts([("Urban", 10), ("Suburban", 40), ("Sparsely", 75),
                    ("Agricultural", 100), ("Undeveloped", 80)]), 25),
          ("Gentle slope", _slope_pts(terrain, "farm"), 5)],
         ["soil_capability", "groundwater", "terrain_elevation_slope",
          "land_cover_class"]),
        ("solar", "Solar farm / rooftop solar",
         "Solar needs strong sunshine, open flat land and a road for installation "
         "and maintenance.",
         [("Sunshine (solar energy per day)",
           None if solar is None else (100 if solar >= 5.5 else 85 if solar >= 5
                                       else 65 if solar >= 4.5 else 40), 40),
          ("Flat / gently sloping ground", _slope_pts(terrain, "solar"), 20),
          ("Open land (not dense built-up)",
           dev_pts([("Urban", 30), ("Suburban", 60), ("Sparsely", 90),
                    ("Agricultural", 80), ("Undeveloped", 100)]), 25),
          ("Road access", s["road"], 15)],
         ["zoning_landuse_plan", "cadastral_parcel", "land_cover_class"]),
    ]

    out = []
    for key, label, why, factors, needs in uses:
        num = den = 0
        rows = []
        for fname, pts, w in factors:
            rows.append({"factor": fname, "points": pts, "weight": w})
            if pts is not None:
                num += pts * w
                den += w
        total_w = sum(w for *_, w in factors)
        score = round(num / den) if den else None
        out.append({
            "key": key, "label": label, "why": why, "score": score,
            "fit": ("Not scored" if score is None else
                    "Strong fit" if score >= 70 else
                    "Possible fit" if score >= 50 else "Weak fit"),
            "factors": rows,
            "coverage_pct": round(100 * den / total_w) if total_w else 0,
            "verify_before_deciding": [n for n in needs if n in open_checks],
        })
    out.sort(key=lambda u: -(u["score"] or -1))
    # hints the frontend uses for tone, not additional evidence
    for u in out:
        u["context"] = ("urban" if urban else "suburban" if suburban
                        else "rural" if rural else "mixed")
    return out


_TOPIC_LABEL = {
    "climate": "Climate (10-yr ERA5)", "infrastructure": "Roads & facilities",
    "water": "Water bodies", "land_use": "Land use (OSM)",
    "development": "Development level",
    "terrain_elevation_slope": "Terrain & slope", "land_cover_class": "Satellite land cover",
    "land_cover_change": "Land-cover change", "soil_capability": "Soil quality",
    "groundwater": "Groundwater", "cadastral_parcel": "Parcel boundary",
    "ownership_title": "Ownership / title", "flood_hazard": "Flood risk",
    "zoning_landuse_plan": "Zoning / master plan",
    "terrain": "Elevation & slope (DEM)", "soil": "Soil (modelled)",
    "air_quality": "Air quality (CAMS)", "locality": "Locality / address",
    "amenities": "Everyday amenities (OSM)",
    "land_cover": "Satellite land cover & change (2017–2025)",
    "flood_screening": "Flood screening (satellite + terrain)",
}

# How each verified topic was obtained — shown so "how sure" is read correctly.
EVIDENCE_KIND = {
    "climate": "Reanalysis", "terrain": "Satellite", "land_cover": "Satellite",
    "flood_screening": "Derived", "soil": "Model", "air_quality": "Model",
    "infrastructure": "Community-mapped", "water": "Community-mapped",
    "land_use": "Community-mapped", "development": "Community-mapped",
    "amenities": "Community-mapped", "locality": "Community-mapped",
}


def topic_label(t: str) -> str:
    return _TOPIC_LABEL.get(t, t.replace("_", " ").capitalize())


def _headline(fac_rows, overall, best, dev_level, city_label) -> tuple[str, str]:
    tone = rating(overall)
    setting = {
        "Urban": "urban", "Suburban": "peri-urban", "Agricultural": "rural",
        "Sparsely": "thinly developed", "Undeveloped": "open",
    }
    where = next((v for k, v in setting.items() if (dev_level or "").startswith(k)),
                 "")
    title = {
        "Excellent": f"Very well-connected {where} site".strip(),
        "Good": f"Well-served {where} site".strip(),
        "Fair": f"Moderately served {where} site".strip(),
        "Poor": f"Poorly served {where} site".strip(),
    }.get(tone, "Location profile")
    title = title[0].upper() + title[1:]

    scored = [r for r in fac_rows if r["weight"] and r["score"] is not None]
    strong = sorted([r for r in scored if r["score"] >= 70], key=lambda r: -r["score"])
    weak = sorted([r for r in scored if r["score"] < 55], key=lambda r: r["score"])
    parts = []
    if strong:
        parts.append("Close to " + ", ".join(
            f"{r['label'].lower()} ({_fmt_m(r['distance_m'])})" for r in strong[:3]) + ".")
    if weak:
        parts.append("Farther from " + ", ".join(
            f"{r['label'].lower()} ({_fmt_m(r['distance_m'])})" for r in weak[:2]) + ".")
    if overall is not None:
        bench_avg = _weighted(fac_rows, "city_typical_score")
        if bench_avg is not None:
            diff = overall - bench_avg
            cmp = ("better than" if diff >= 8 else "worse than" if diff <= -8
                   else "about the same as")
            parts.append(f"Overall access is {cmp} a typical spot in the "
                         f"{city_label} city core ({overall} vs {bench_avg}).")
    if best and best["score"] is not None:
        parts.append(f"Best indicative fit: {best['label'].lower()}.")
    return title, " ".join(parts)


def flood_screening(terrain: dict | None, water_m: float | None, lc: dict | None) -> dict:
    """A transparent flood-exposure SCREEN from verified inputs — not the
    official flood-hazard map, which stays an open gap."""
    if not terrain and lc is None:
        return {"available": False, "reason": "Needs terrain or satellite land cover."}
    pts, reasons = 0, []
    if terrain:
        rel = terrain["relative_to_1km_m"]
        if rel <= -4:
            pts += 2
            reasons.append(f"sits {abs(rel):.0f} m below the land within 1 km")
        elif rel <= -1.5:
            pts += 1
            reasons.append(f"slightly below its surroundings ({rel:+} m)")
        else:
            reasons.append(f"not a low spot ({rel:+} m vs surroundings)")
        if terrain["slope_deg"] < 1:
            pts += 1
            reasons.append("very flat ground drains slowly")
    if water_m is not None:
        if water_m <= 300:
            pts += 2
            reasons.append(f"surface water {round(water_m)} m away")
        elif water_m <= 1000:
            pts += 1
            reasons.append(f"surface water {round(water_m)} m away")
        else:
            reasons.append(f"nearest mapped surface water {water_m / 1000:.1f} km away")
    if lc is not None:
        yrs = lc.get("years_with_water_nearby", 0)
        if yrs >= 3:
            pts += 2
            reasons.append(f"satellite saw water / flooded vegetation within ~300 m in {yrs} of 9 years")
        elif yrs >= 1:
            pts += 1
            reasons.append(f"satellite saw water within ~300 m in {yrs} of 9 years")
        else:
            reasons.append("no water seen within ~300 m by satellite in 2017–2025")
    level = "Elevated" if pts >= 5 else "Moderate" if pts >= 3 else "Low"
    return {"available": True, "level": level, "points": pts, "max_points": 7,
            "reasons": reasons,
            "note": "Screening from terrain, mapped water and 9 years of satellite land "
                    "cover. It is not the official flood-hazard map, which is still "
                    "needed before any decision."}


def _cross_checks(site: dict | None, lc: dict | None) -> list[dict]:
    """Where two independent sources describe the same thing, say whether they agree."""
    out = []
    osm_dev = ((site or {}).get("development") or {}).get("level")
    if lc and osm_dev:
        sat_dev = effective_development(None, lc)
        same = (osm_dev.split()[0] == sat_dev.split()[0]
                or {osm_dev.split()[0], sat_dev.split()[0]} <= {"Agricultural", "Sparsely", "Undeveloped"})
        out.append({
            "check": "Development level — OpenStreetMap vs satellite",
            "result": "agree" if same else "disagree",
            "note": (f"OSM mapping suggests '{osm_dev.lower()}'; satellite ({lc['year']}) sees "
                     f"{lc['built_pct']}% built-up within ~300 m ('{sat_dev.lower()}')."
                     + ("" if same else " OSM is likely under-mapped here — the report uses "
                                        "the satellite reading.")),
        })
    land = (site or {}).get("land_use") or {}
    if lc and land.get("available"):
        osm_built, osm_agri = bool(land.get("is_built_up")), bool(land.get("is_agricultural"))
        sat_built, sat_crops = lc["built_pct"] >= 50, lc["crops_pct"] >= 40
        if osm_built or osm_agri:
            agree = (osm_built and sat_built) or (osm_agri and sat_crops)
            out.append({
                "check": "Land use — OpenStreetMap vs satellite",
                "result": "agree" if agree else "disagree",
                "note": (f"OSM tags it {'built-up' if osm_built else 'farmland'}; satellite "
                         f"({lc['year']}) shows {lc['built_pct']}% built, {lc['crops_pct']}% crops "
                         f"within ~300 m."),
            })
        else:
            out.append({
                "check": "Land use — OpenStreetMap vs satellite",
                "result": "filled",
                "note": (f"OSM has no land-use tag here; the satellite fills the gap: "
                         f"{lc['site_class'].lower()} at the point, {lc['built_pct']}% built "
                         f"and {lc['crops_pct']}% crops within ~300 m."),
            })
    return out


def _key_facts(ev: dict, climate: dict | None, amen: dict) -> list[dict]:
    """Short, glanceable facts for the verdict card — every one sourced."""
    out = []
    loc = ev.get("locality")
    if loc:
        place = ", ".join(x for x in (loc.get("suburb_or_village") or loc.get("neighbourhood"),
                                      loc.get("district")) if x)
        if place:
            pin = f" · PIN {loc['postcode']}" if loc.get("postcode") else ""
            out.append({"label": "Locality", "value": place + pin})
    t = ev.get("terrain")
    if t:
        out.append({"label": "Ground", "value": f"{t['elevation_m']} m above sea level · "
                                                f"{t['slope_class'].lower()} slope ({t['slope_deg']}°)"})
    lcv = ev.get("land_cover")
    if lcv:
        out.append({"label": "Land cover", "value": f"{lcv['site_class']} ({lcv['year']}) · "
                                                    f"{lcv['trend'].lower()}"})
    so = ev.get("soil")
    if so:
        out.append({"label": "Soil", "value": f"{so['texture_class']}, pH {so['ph']} "
                                              f"({(so['ph_note'] or '').lower()})"})
    if climate:
        out.append({"label": "Climate", "value": f"{climate['mean_temperature_c']} °C avg · "
                                                 f"{climate['annual_precipitation_mm']:.0f} mm rain/yr"})
    aq = ev.get("air_quality")
    if aq:
        out.append({"label": "Air (PM2.5)", "value": f"{aq['pm2_5_annual_mean']} µg/m³ yearly avg"})
    if amen.get("available"):
        out.append({"label": "Amenities", "value": f"{amen['total_within_1km']} mapped within 1 km "
                                                   f"({amen['groups_within_1km']} kinds)"})
    return out


def build_profile(lat: float, lon: float) -> dict:
    report = ee.build_report(lat, lon)
    if "error" in report:
        return report
    loc = report["location"]
    city = loc["city"]
    city_label = city_registry.get_city(city)["label"]

    site = sc.build_site_context(lat, lon, city)
    site_ok = site if site.get("available") else None

    climate = next((v["value"] for v in report["verified_evidence"]
                    if v["topic"] == "climate"), None)
    infra_ok = any(v["topic"] == "infrastructure" for v in report["verified_evidence"])

    fac_rows, bench = _facilities(lat, lon, city)
    if not infra_ok:  # never score from a layer the evidence engine couldn't use
        for r in fac_rows:
            if r["key"] != "water":
                r.update(distance_m=None, score=None, rating="Not scored",
                         closer_than_pct_of_city=None)
    fac = {r["key"]: r for r in fac_rows}

    # the richer series (profiles, monthly normals) behind each verified topic;
    # these calls hit the per-point caches the evidence engine just filled
    ev = {v["topic"]: v["value"] for v in report["verified_evidence"]}
    details = {}
    for topic in ("terrain", "soil", "air_quality", "locality", "land_cover"):
        if topic in ev:
            res = ld.SOURCES[topic](lat, lon)
            details[topic] = {"value": ev[topic], "detail": res.get("detail"),
                              "provenance": res.get("provenance")}
        else:
            gap = next((g for g in report["data_gaps"] if g["topic"] == topic), {})
            details[topic] = {"value": None, "reason": gap.get("reason"),
                              "resolution": gap.get("resolution")}
    if climate:
        details["climate"] = {"value": climate,
                              "detail": ee._climate_evidence(lat, lon).get("detail")}
    amen = amenities_near(lat, lon, city)
    details["amenities"] = amen
    flood = flood_screening(ev.get("terrain"), fac.get("water", {}).get("distance_m"),
                            ev.get("land_cover"))
    details["flood_screening"] = flood

    open_checks = [g["topic"] for g in report["data_gaps"]]
    uses = _use_fits(fac, site_ok, climate, open_checks,
                     terrain=ev.get("terrain"), soil=ev.get("soil"), amen=amen,
                     lc=ev.get("land_cover"))
    overall = _weighted(fac_rows, "score")
    city_typical = _weighted(fac_rows, "city_typical_score")

    verified_topics = [v["topic"] for v in report["verified_evidence"]]
    if site_ok:
        verified_topics += ["water", "land_use", "development"]
    if amen.get("available"):
        verified_topics.append("amenities")
    if flood.get("available"):
        verified_topics.append("flood_screening")
    known = [{"topic": t, "label": topic_label(t), "kind": EVIDENCE_KIND.get(t, "Other")}
             for t in verified_topics]
    checks = _cross_checks(site_ok, ev.get("land_cover"))
    unknown = [{"topic": g["topic"], "label": topic_label(g["topic"]),
                "status": g.get("dataset_status", "UNAVAILABLE"),
                "pending": bool(g.get("pending")),
                "reason": g["reason"]} for g in report["data_gaps"]]
    coverage = round(100 * len(known) / max(1, len(known) + len(unknown)))

    dev_level = effective_development(
        ((site_ok or {}).get("development") or {}).get("level"), ev.get("land_cover"))
    best = uses[0] if uses else None
    title, summary = _headline(fac_rows, overall, best, dev_level, city_label)
    terr = ev.get("terrain")
    if terr and terr["relative_position"].startswith("Lower"):
        summary += (f" Note: the ground here sits ~{abs(terr['relative_to_1km_m']):.0f} m "
                    f"below the land around it — check drainage and the flood map.")
    facts = _key_facts(ev, climate, amen)

    return {
        "report_type": "land_profile",
        "location": {**loc, "city_label": city_label,
                     "state": city_registry.get_city(city)["state"]},
        "verdict": {
            "title": title,
            "summary": summary,
            "access_score": overall,
            "access_rating": rating(overall),
            "city_typical_access_score": city_typical,
            "best_use": best["label"] if best and best["score"] is not None else None,
            "facts": facts,
            # satellite-aware labels for the verdict chips (OSM alone can be stale)
            "development": dev_level,
            "land_label": (f"{ev['land_cover']['site_class']} (satellite {ev['land_cover']['year']})"
                           if ev.get("land_cover") else
                           ((site_ok or {}).get("land_use") or {}).get("effective_category")),
            "confidence": (("Medium-high" if coverage >= 65 and not any(
                               c["result"] == "disagree" for c in checks) else "Medium")
                           if coverage >= 50 else "Low-to-medium" if coverage >= 30 else "Low"),
            "confidence_note": (f"Based on {len(known)} verified topic(s); "
                                f"{len(unknown)} important check(s) — "
                                f"{', '.join(u['label'].lower() for u in unknown[:4])}"
                                f"{'…' if len(unknown) > 4 else ''} — are still open."),
        },
        "facilities": fac_rows,
        "benchmark": {k: v for k, v in bench.items() if k != "by_key"},
        "use_fit": uses,
        "climate": climate,
        "details": details,
        "site": site_ok,
        "evidence_coverage": {"pct": coverage, "known": known, "unknown": unknown,
                              "cross_checks": checks,
                              "by_kind": {k: sum(1 for x in known if x["kind"] == k)
                                          for k in dict.fromkeys(x["kind"] for x in known)}},
        "report": report,
        "method": {
            "access": BAND_NOTE + " Overall access = weighted mean of road 30%, "
                      "health 25%, school 25%, rail 20%. Distances are to the "
                      "nearest mapped OpenStreetMap feature.",
            "benchmark": bench.get("method"),
            "use_fit": "Indicative screen on verified access, amenities, terrain, "
                       "modelled soil, climate and site-character factors only. "
                       "Not a zoning, valuation or statutory determination — the "
                       "listed checks must be closed first.",
            "details": "Terrain: Copernicus DEM GLO-90 (Open-Meteo). Soil: ISRIC "
                       "SoilGrids 250 m model. Air: CAMS global model (Open-Meteo), "
                       "compared with India NAAQS 2009 and WHO 2021. Locality: "
                       "Nominatim. Amenities: OpenStreetMap.",
        },
        "generated": report["generated"],
        "disclaimer": report["disclaimer"],
    }
