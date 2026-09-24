"""
Land details — extra *verified* facts about a point from keyless open APIs:

  terrain      Copernicus DEM GLO-90 via Open-Meteo: elevation, slope/aspect
               over ~100 m, position relative to the surrounding 1 km, and
               W-E / S-N elevation profiles across 2 km.
  soil         ISRIC SoilGrids 2.0 (250 m MODEL): texture, pH, organic
               carbon, nitrogen, CEC, bulk density — top 0-5 cm and 15-30 cm.
  air_quality  CAMS via Open-Meteo: last-12-month PM2.5 / PM10 background
               level vs the Indian NAAQS and WHO 2021 guideline values.
  locality     Nominatim reverse geocode: neighbourhood / ward / district / PIN.

Same rules as the evidence engine: each source is gate-checked in the
registry, every value carries provenance, and any failure becomes an explicit
gap with the reason — never a guess or a fallback number. Interpretation
bands (e.g. "gentle slope", "neutral pH") are general reference ranges and
are labelled as such.
"""
from __future__ import annotations

import json
import math
import threading
from datetime import date, timedelta

import httpx

from services import data_registry as reg

_UA = "NDP-land-evidence-prototype/0.1 (research; contact via project repo)"
_TIMEOUT = 20.0
_CACHE: dict[tuple, dict] = {}
_LOCK = threading.Lock()


def _cached(kind: str, lat: float, lon: float, nd: int, fn):
    key = (kind, round(lat, nd), round(lon, nd))
    with _LOCK:
        if key in _CACHE:
            return _CACHE[key]
    res = fn(lat, lon)
    if res.get("ok"):  # never cache a failure — the source may come back
        with _LOCK:
            _CACHE[key] = res
    return res


def _get_json(url: str, params, timeout: float = _TIMEOUT, headers=None, attempts: int = 2):
    """GET with one retry — a transient blip shouldn't turn real data into a gap."""
    last: Exception | None = None
    for _attempt in range(attempts):
        try:
            with httpx.Client(timeout=timeout, headers=headers) as c:
                r = c.get(url, params=params)
                r.raise_for_status()
                return r.json()
        except Exception as exc:  # noqa: BLE001
            last = exc
    raise last  # type: ignore[misc]


def _http_reason(exc: Exception) -> str:
    status = getattr(getattr(exc, "response", None), "status_code", None)
    return ("HTTP 429 (rate-limited)" if status == 429 else f"HTTP {status}" if status
            else exc.__class__.__name__)


def _gate(ds: str) -> dict | None:
    if not reg.can_use_for_analysis(ds):
        return {"ok": False, "reason": f"{ds} not analytically eligible"}
    return None


def _offset(lat: float, lon: float, north_m: float, east_m: float) -> tuple[float, float]:
    dlat = north_m / 111_320.0
    dlon = east_m / (111_320.0 * math.cos(math.radians(lat)))
    return lat + dlat, lon + dlon


# --- terrain -----------------------------------------------------------------
SLOPE_CLASSES = [(1, "Nearly level"), (3, "Gentle"), (8, "Moderate"),
                 (15, "Strong"), (90, "Steep")]
_ASPECTS = ["N", "NE", "E", "SE", "S", "SW", "W", "NW"]


def _terrain(lat: float, lon: float) -> dict:
    if (g := _gate("open_meteo_elevation")):
        return g
    step = 100.0
    pts = [(lat, lon)]
    pts += [_offset(lat, lon, n, e) for n, e in ((step, 0), (-step, 0), (0, step), (0, -step))]
    ring = [_offset(lat, lon, 1000 * math.cos(a), 1000 * math.sin(a))
            for a in (i * math.pi / 8 for i in range(16))]
    pts += ring
    prof_d = [i * 100 for i in range(-10, 11)]
    pts += [_offset(lat, lon, 0, d) for d in prof_d]     # west -> east
    pts += [_offset(lat, lon, d, 0) for d in prof_d]     # south -> north
    # Copernicus GLO-90 via Open-Meteo first; SRTM 90 m via OpenTopoData if
    # Open-Meteo refuses (shared cloud IPs can hit its free limit).
    z, source, dataset, primary_err = [], "Open-Meteo Elevation API (Copernicus DEM GLO-90)", \
        "open_meteo_elevation", None
    try:
        z = _get_json("https://api.open-meteo.com/v1/elevation", {
            "latitude": ",".join(f"{p[0]:.5f}" for p in pts),
            "longitude": ",".join(f"{p[1]:.5f}" for p in pts)}).get("elevation") or []
    except Exception as exc:  # noqa: BLE001
        primary_err = f"Open-Meteo elevation unreachable: {_http_reason(exc)}"
    if (len(z) != len(pts) or any(v is None for v in z)) and reg.can_use_for_analysis("opentopodata_srtm"):
        try:
            res = _get_json("https://api.opentopodata.org/v1/srtm90m", {
                "locations": "|".join(f"{p[0]:.5f},{p[1]:.5f}" for p in pts)}).get("results") or []
            z = [r.get("elevation") for r in res]
            source, dataset = "OpenTopoData (SRTM 90 m)", "opentopodata_srtm"
        except Exception as exc:  # noqa: BLE001
            return {"ok": False, "reason": f"{primary_err or 'Open-Meteo elevation incomplete'}; "
                                           f"backup OpenTopoData unreachable: {_http_reason(exc)}"}
    if len(z) != len(pts) or any(v is None for v in z):
        return {"ok": False, "reason": primary_err or "Elevation service returned incomplete values"}

    z0, zn, zs, ze, zw = z[:5]
    ring_z = z[5:21]
    we, sn = z[21:42], z[42:63]
    dzdx = (ze - zw) / (2 * step)
    dzdy = (zn - zs) / (2 * step)
    slope_pct = 100 * math.hypot(dzdx, dzdy)
    slope_deg = math.degrees(math.atan(math.hypot(dzdx, dzdy)))
    # aspect = the compass direction the slope FACES (downhill)
    aspect = None
    if slope_deg >= 0.5:
        ang = (math.degrees(math.atan2(-dzdx, -dzdy)) + 360) % 360
        aspect = _ASPECTS[int((ang + 22.5) // 45) % 8]
    ring_mean = sum(ring_z) / len(ring_z)
    rel = z0 - ring_mean
    if rel <= -4:
        position = "Lower than its surroundings"
        pos_note = ("Sits below the average ground level within 1 km — a "
                    "low spot where rain run-off tends to collect. Worth "
                    "checking drainage and the official flood map.")
    elif rel >= 4:
        position = "Higher than its surroundings"
        pos_note = "Sits above the surrounding ground — run-off drains away from it."
    else:
        position = "Level with its surroundings"
        pos_note = "About the same height as the land around it within 1 km."
    slope_class = next(lbl for lim, lbl in SLOPE_CLASSES if slope_deg <= lim)
    return {
        "ok": True,
        "value": {
            "elevation_m": round(z0),
            "slope_deg": round(slope_deg, 1),
            "slope_pct": round(slope_pct, 1),
            "slope_class": slope_class,
            "aspect": aspect,
            "relative_to_1km_m": round(rel, 1),
            "relative_position": position,
            "relative_position_note": pos_note,
            "relief_within_1km_m": round(max(ring_z + [z0]) - min(ring_z + [z0])),
        },
        "detail": {
            "profile_west_east": [{"offset_m": d, "elevation_m": v} for d, v in zip(prof_d, we)],
            "profile_south_north": [{"offset_m": d, "elevation_m": v} for d, v in zip(prof_d, sn)],
        },
        "provenance": {
            "dataset": dataset,
            "source": source,
            "resolution": "90 m DEM; slope over 200 m baseline",
            "retrieved": date.today().isoformat(),
            "confidence": "medium",
            "note": "Surface model (includes buildings/trees). Slope classes "
                    "are general reference bands, not a statutory class.",
        },
    }


# --- soil ----------------------------------------------------------------------
_SOIL_PROPS = ("clay", "sand", "silt", "phh2o", "soc", "nitrogen", "cec", "bdod")


_SOIL_FALLBACK_M = 1500


def _soil_query(lat: float, lon: float, timeout: float = 30.0, attempts: int = 2):
    params = [("lon", f"{lon:.5f}"), ("lat", f"{lat:.5f}"), ("value", "mean"),
              ("depth", "0-5cm"), ("depth", "15-30cm")]
    params += [("property", p) for p in _SOIL_PROPS]
    layers = _get_json("https://rest.isric.org/soilgrids/v2.0/properties/query",
                       params, timeout=timeout, attempts=attempts)["properties"]["layers"]
    vals: dict[str, dict[str, float | None]] = {}
    for layer in layers:
        f = layer["unit_measure"]["d_factor"] or 1
        vals[layer["name"]] = {d["label"]: (None if d["values"]["mean"] is None
                                            else d["values"]["mean"] / f)
                               for d in layer["depths"]}
    return ({k: v.get("0-5cm") for k, v in vals.items()},
            {k: v.get("15-30cm") for k, v in vals.items()})


def texture_class(sand: float, silt: float, clay: float) -> str:
    """USDA soil texture triangle (percentages)."""
    if silt + 1.5 * clay < 15:
        return "Sand"
    if silt + 1.5 * clay < 30:
        return "Loamy sand"
    if (7 <= clay < 20 and sand > 52 and silt + 2 * clay >= 30) or (clay < 7 and silt < 50 and silt + 2 * clay >= 30):
        return "Sandy loam"
    if 7 <= clay < 27 and 28 <= silt < 50 and sand <= 52:
        return "Loam"
    if (silt >= 50 and 12 <= clay < 27) or (50 <= silt < 80 and clay < 12):
        return "Silt loam"
    if silt >= 80 and clay < 12:
        return "Silt"
    if 20 <= clay < 35 and silt < 28 and sand > 45:
        return "Sandy clay loam"
    if 27 <= clay < 40 and 20 < sand <= 45:
        return "Clay loam"
    if 27 <= clay < 40 and sand <= 20:
        return "Silty clay loam"
    if clay >= 35 and sand > 45:
        return "Sandy clay"
    if clay >= 40 and silt >= 40:
        return "Silty clay"
    return "Clay"


def _ph_note(ph: float) -> str:
    return ("Strongly acidic" if ph < 5.5 else "Slightly acidic" if ph < 6.5
            else "Neutral" if ph <= 7.5 else "Alkaline" if ph <= 8.5
            else "Strongly alkaline (possible sodicity)")


def _texture_note(tex: str) -> str:
    if tex in ("Sand", "Loamy sand"):
        return "Light, fast-draining soil; holds little water or nutrient."
    if tex in ("Loam", "Silt loam", "Sandy loam"):
        return "Balanced, workable soil that drains well and holds moisture."
    if tex in ("Clay", "Silty clay", "Sandy clay"):
        return ("Heavy clay — holds water and nutrients but drains slowly; "
                "can swell/shrink (a foundation consideration).")
    return "Good water holding, moderate drainage."


def _soil(lat: float, lon: float) -> dict:
    if (g := _gate("soilgrids")):
        return g
    try:
        top, sub = _soil_query(lat, lon)
    except Exception as exc:  # noqa: BLE001
        return {"ok": False, "reason": f"SoilGrids unreachable: {exc.__class__.__name__}"}
    sampled = None
    if top.get("clay") is None or top.get("sand") is None:
        # SoilGrids masks built-up cells. Look for the nearest open ground in
        # four directions — one short, parallel call each (SoilGrids asks for
        # light use), so a dense city point costs ~12 s at worst, not minutes.
        from concurrent.futures import ThreadPoolExecutor
        dirs = (("north", _SOIL_FALLBACK_M, 0), ("east", 0, _SOIL_FALLBACK_M),
                ("south", -_SOIL_FALLBACK_M, 0), ("west", 0, -_SOIL_FALLBACK_M))
        with ThreadPoolExecutor(max_workers=4) as pool:
            futs = [(name, pool.submit(_soil_query, *_offset(lat, lon, n_m, e_m), 12.0, 1))
                    for name, n_m, e_m in dirs]
        for name, fut in futs:
            try:
                t2, s2 = fut.result()
            except Exception:  # noqa: BLE001
                continue
            if t2.get("clay") is not None and t2.get("sand") is not None:
                top, sub, sampled = t2, s2, {"direction": name, "distance_m": _SOIL_FALLBACK_M}
                break
    if top.get("clay") is None or top.get("sand") is None:
        return {"ok": False,
                "reason": "SoilGrids has no values here or on open ground within "
                          f"{_SOIL_FALLBACK_M / 1000:g} km — it masks built-up land.",
                "resolution": "Expected for dense built-up land. A field soil test or "
                              "the NBSS&LUP survey is needed here."}

    def rnd(x, n=1):
        return None if x is None else round(x, n)

    # SoilGrids: texture in %, pH, SOC g/kg (dg/kg /10), N g/kg (cg/kg /100),
    # CEC cmol(c)/kg (mmol/kg /10), bulk density kg/dm3 (cg/cm3 /100)
    tex = texture_class(top["sand"], top["silt"], top["clay"])
    soc = top.get("soc")
    return {
        "ok": True,
        "value": {
            "texture_class": tex,
            "texture_note": _texture_note(tex),
            "sand_pct": rnd(top["sand"]), "silt_pct": rnd(top["silt"]),
            "clay_pct": rnd(top["clay"]),
            "ph": rnd(top.get("phh2o")),
            "ph_note": _ph_note(top["phh2o"]) if top.get("phh2o") is not None else None,
            "organic_carbon_g_per_kg": rnd(soc),
            "organic_carbon_note": (None if soc is None else
                                    "Low" if soc < 5 else "Moderate" if soc < 10 else "High"),
            "nitrogen_g_per_kg": rnd(top.get("nitrogen"), 2),
            "cec_cmol_per_kg": rnd(top.get("cec")),
            "bulk_density_kg_per_dm3": rnd(top.get("bdod"), 2),
            "sampled_at": ("at the site" if sampled is None else
                           f"nearest open ground, ~{sampled['distance_m'] / 1000:g} km "
                           f"{sampled['direction']} (the site itself is built-up)"),
        },
        "detail": {"depths": {
            "0-5cm": {k: rnd(v, 2) for k, v in top.items()},
            "15-30cm": {k: rnd(v, 2) for k, v in sub.items()},
        }},
        "provenance": {
            "dataset": "soilgrids",
            "source": "ISRIC SoilGrids 2.0 REST API",
            "resolution": "250 m modelled grid",
            "retrieved": date.today().isoformat(),
            "confidence": "low-to-medium" if sampled is None else "low",
            "note": "Machine-learning model, not a field survey; interpretation "
                    "bands are general agronomic ranges. Not a land-capability "
                    "class (NBSS&LUP remains a gap).",
        },
    }


# --- air quality -----------------------------------------------------------
# Real reference values: India NAAQS (CPCB, 2009) and WHO 2021 AQG.
AQ_REFS = {
    "pm2_5": {"naaqs_annual": 40, "naaqs_24h": 60, "who_annual": 5},
    "pm10": {"naaqs_annual": 60, "naaqs_24h": 100, "who_annual": 15},
}


def _air_quality(lat: float, lon: float) -> dict:
    if (g := _gate("open_meteo_air_quality")):
        return g
    end = date.today() - timedelta(days=2)
    start = end - timedelta(days=364)
    try:
        h = _get_json("https://air-quality-api.open-meteo.com/v1/air-quality", {
            "latitude": f"{lat:.4f}", "longitude": f"{lon:.4f}",
            "hourly": "pm2_5,pm10", "timezone": "auto",
            "start_date": start.isoformat(), "end_date": end.isoformat()})["hourly"]
    except Exception as exc:  # noqa: BLE001
        return {"ok": False, "reason": f"Open-Meteo air quality unreachable: {exc.__class__.__name__}"}

    days: dict[str, dict[str, list[float]]] = {}
    for t, p25, p10 in zip(h["time"], h["pm2_5"], h["pm10"]):
        d = days.setdefault(t[:10], {"pm2_5": [], "pm10": []})
        if p25 is not None:
            d["pm2_5"].append(p25)
        if p10 is not None:
            d["pm10"].append(p10)
    daily = {k: {p: sum(v) / len(v) for p, v in d.items() if v} for k, d in days.items()}
    daily = {k: v for k, v in daily.items() if "pm2_5" in v and "pm10" in v}
    if len(daily) < 180:
        return {"ok": False, "reason": "Too few days of air-quality data for an annual level"}

    def mean(p):
        return sum(v[p] for v in daily.values()) / len(daily)

    monthly: dict[str, list[float]] = {}
    for k, v in daily.items():
        monthly.setdefault(k[:7], []).append(v["pm2_5"])
    pm25, pm10 = mean("pm2_5"), mean("pm10")
    over = sum(1 for v in daily.values() if v["pm2_5"] > AQ_REFS["pm2_5"]["naaqs_24h"])
    level = ("Within the Indian annual standard" if pm25 <= 40
             else "Above the Indian annual standard")
    return {
        "ok": True,
        "value": {
            "period": f"{min(daily)} to {max(daily)}",
            "pm2_5_annual_mean": round(pm25, 1),
            "pm10_annual_mean": round(pm10, 1),
            "days_pm2_5_above_naaqs_24h": over,
            "days_counted": len(daily),
            "summary": f"{level} for PM2.5 ({round(pm25)} vs 40 µg/m³); "
                       f"the WHO guideline is 5 µg/m³.",
        },
        "detail": {
            "monthly_pm2_5": [{"month": m, "pm2_5": round(sum(v) / len(v), 1)}
                              for m, v in sorted(monthly.items())],
            "references": AQ_REFS,
        },
        "provenance": {
            "dataset": "open_meteo_air_quality",
            "source": "Open-Meteo Air Quality API (CAMS global)",
            "resolution": "~45 km model grid",
            "retrieved": date.today().isoformat(),
            "confidence": "low-to-medium",
            "note": "Regional background model, not a street-level monitor. "
                    "References: India NAAQS 2009 (CPCB), WHO AQG 2021.",
        },
    }


# --- locality -----------------------------------------------------------------
def _locality(lat: float, lon: float) -> dict:
    if (g := _gate("nominatim_geocoding")):
        return g
    try:
        j = _get_json("https://nominatim.openstreetmap.org/reverse", {
            "format": "jsonv2", "lat": f"{lat:.6f}", "lon": f"{lon:.6f}",
            "zoom": 17, "addressdetails": 1, "accept-language": "en"},
            headers={"User-Agent": _UA})
    except Exception as exc:  # noqa: BLE001
        return {"ok": False, "reason": f"Nominatim unreachable: {exc.__class__.__name__}"}
    a = j.get("address") or {}
    if not a:
        return {"ok": False, "reason": "No address objects mapped near this point"}
    pick = lambda *ks: next((a[k] for k in ks if a.get(k)), None)  # noqa: E731
    return {
        "ok": True,
        "value": {
            "road": pick("road"),
            "neighbourhood": pick("neighbourhood", "quarter", "hamlet"),
            "suburb_or_village": pick("suburb", "village", "town"),
            "city": pick("city", "town", "municipality"),
            "sub_district": pick("county", "subdistrict"),
            "district": pick("state_district", "district"),
            "state": a.get("state"),
            "postcode": a.get("postcode"),
            "address": j.get("display_name"),
        },
        "provenance": {
            "dataset": "nominatim_geocoding",
            "source": "Nominatim (OpenStreetMap) reverse geocoder",
            "retrieved": date.today().isoformat(),
            "confidence": "medium",
            "note": "Names as mapped in OSM — not an official revenue-village lookup.",
        },
    }


_LC_URL = ("https://ic.imagery1.arcgis.com/arcgis/rest/services/"
           "Sentinel2_10m_LandCover/ImageServer/getSamples")
LC_CLASSES = {1: "Water", 2: "Trees", 4: "Flooded vegetation", 5: "Crops",
              7: "Built area", 8: "Bare ground", 9: "Snow / ice", 10: "Clouds",
              11: "Rangeland"}
LC_YEARS = list(range(2017, 2026))
_LC_STEP = 0.0009   # degrees (~100 m) between samples in the 7 x 7 window
_LC_HALF = 3


def _lc_year(lat: float, lon: float, year: int):
    pts = [[lon + dx * _LC_STEP, lat + dy * _LC_STEP]
           for dy in range(-_LC_HALF, _LC_HALF + 1) for dx in range(-_LC_HALF, _LC_HALF + 1)]
    from datetime import datetime
    j = _get_json(_LC_URL, {
        "geometry": json.dumps({"points": pts, "spatialReference": {"wkid": 4326}}),
        "geometryType": "esriGeometryMultipoint", "returnFirstValueOnly": "true",
        "time": int(datetime(year, 7, 1).timestamp() * 1000), "f": "json"}, timeout=40.0)
    vals = []
    for smp in j.get("samples") or []:
        try:
            vals.append(int(float(smp["value"])))
        except (KeyError, TypeError, ValueError):
            vals.append(None)
    return vals


def _land_cover(lat: float, lon: float) -> dict:
    if (g := _gate("esri_lulc_timeseries")):
        return g
    from concurrent.futures import ThreadPoolExecutor
    with ThreadPoolExecutor(max_workers=5) as pool:
        futs = {y: pool.submit(_lc_year, lat, lon, y) for y in LC_YEARS}
    by_year = {}
    for y, f in futs.items():
        try:
            v = f.result()
        except Exception:  # noqa: BLE001 - a missing year is simply left out
            continue
        if v and any(x is not None for x in v):
            by_year[y] = v
    if len(by_year) < 2:
        return {"ok": False, "reason": "Esri land-cover service returned too few years for this point."}

    centre = len(next(iter(by_year.values()))) // 2
    series = []
    for y in sorted(by_year):
        v = [x for x in by_year[y] if x is not None]
        share = lambda *cls: round(100 * sum(1 for x in v if x in cls) / len(v))  # noqa: E731
        series.append({"year": y, "site_class": LC_CLASSES.get(by_year[y][centre], "Unknown"),
                       "built_pct": share(7), "crops_pct": share(5), "trees_pct": share(2),
                       "water_pct": share(1, 4), "open_pct": share(8, 11)})
    first, last = series[0], series[-1]
    latest = [x for x in by_year[last["year"]] if x is not None]
    mix = sorted(((LC_CLASSES.get(c, "Other"), round(100 * latest.count(c) / len(latest)))
                  for c in set(latest)), key=lambda t: -t[1])
    water_years = [s["year"] for s in series if s["water_pct"] > 0]
    d_built = last["built_pct"] - first["built_pct"]
    d_crops = last["crops_pct"] - first["crops_pct"]
    parts = [f"The site is {last['site_class'].lower()} in {last['year']}"
             + ("" if first["site_class"] == last["site_class"]
                else f" (it was {first['site_class'].lower()} in {first['year']})") + "."]
    if abs(d_built) >= 5 or abs(d_crops) >= 5:
        parts.append(f"Within ~300 m, built-up land went from {first['built_pct']}% to "
                     f"{last['built_pct']}% and cropland from {first['crops_pct']}% to "
                     f"{last['crops_pct']}% ({first['year']}–{last['year']}).")
    else:
        parts.append(f"The surroundings (~300 m) have stayed broadly the same since {first['year']}.")
    trend = ("Urbanising fast" if d_built >= 15 else "Urbanising" if d_built >= 5
             else "Losing built cover" if d_built <= -5 else "Stable")
    return {
        "ok": True,
        "value": {
            "site_class": last["site_class"], "year": last["year"],
            "site_class_first": first["site_class"], "first_year": first["year"],
            "built_pct": last["built_pct"], "crops_pct": last["crops_pct"],
            "trees_pct": last["trees_pct"], "water_pct": last["water_pct"],
            "built_change_pp": d_built, "crops_change_pp": d_crops,
            "trend": trend,
            "summary": " ".join(parts),
            "years_with_water_nearby": len(water_years),
        },
        "detail": {"series": series, "latest_mix": [{"class": c, "pct": p} for c, p in mix],
                   "window": "7 x 7 samples, ~100 m apart (~600 m square) around the point",
                   "water_years": water_years},
        "provenance": {
            "dataset": "esri_lulc_timeseries",
            "source": "Esri / Impact Observatory Sentinel-2 10 m Land Use/Land Cover time series",
            "resolution": "10 m pixels, annual 2017–2025",
            "retrieved": date.today().isoformat(),
            "confidence": "medium",
            "note": "Machine-learning classification of Sentinel-2 imagery (~85% "
                    "overall accuracy reported by the producers); sampled live at 49 "
                    "points, not a full raster download.",
        },
    }


SOURCES = {
    "terrain": (lambda la, lo: _cached("terrain", la, lo, 4, _terrain)),
    "soil": (lambda la, lo: _cached("soil", la, lo, 3, _soil)),
    "air_quality": (lambda la, lo: _cached("aq", la, lo, 2, _air_quality)),
    "locality": (lambda la, lo: _cached("loc", la, lo, 4, _locality)),
    "land_cover": (lambda la, lo: _cached("lc", la, lo, 4, _land_cover)),
}
