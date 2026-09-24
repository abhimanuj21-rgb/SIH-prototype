"""
Live air quality for a point — fetched fresh (cached 10 min).

  model     Open-Meteo Air Quality API (Copernicus CAMS): current PM2.5, PM10,
            NO2, SO2, O3, CO, dust, aerosol optical depth, plus hourly values
            for the past 24 h and the next 48 h.
  india_aqi The Indian National Air Quality Index, computed with the CPCB
            method: sub-index per pollutant from its CPCB breakpoints
            (24-h average for PM2.5, PM10, NO2, SO2; 8-h average for O3, CO);
            AQI = the highest sub-index, provided PM2.5 or PM10 is one of at
            least three pollutants.
  stations  Optional MEASURED readings from the nearest CPCB/state monitoring
            stations via OpenAQ — only when OPENAQ_API_KEY is set (free key);
            otherwise reported as not configured, never faked.

The model is a ~45 km regional estimate; station readings, where present, are
the authoritative local measurement and are shown alongside it.
"""
from __future__ import annotations

import os
import threading
import time
from datetime import datetime, timezone

import httpx

from services import data_registry as reg
from services import evidence_engine as ee

_TTL = 600
_CACHE: dict[tuple, tuple[float, dict]] = {}
_LOCK = threading.Lock()

# CPCB National AQI breakpoints: (concentration low, high) per index band.
# Units µg/m³, except CO in mg/m³. Bands map to AQI 0-50, 51-100, 101-200,
# 201-300, 301-400, 401-500.
_AQI_BANDS = [(0, 50), (51, 100), (101, 200), (201, 300), (301, 400), (401, 500)]
CPCB_BREAKPOINTS = {
    "pm2_5": [(0, 30), (31, 60), (61, 90), (91, 120), (121, 250), (251, 380)],
    "pm10": [(0, 50), (51, 100), (101, 250), (251, 350), (351, 430), (431, 510)],
    "nitrogen_dioxide": [(0, 40), (41, 80), (81, 180), (181, 280), (281, 400), (401, 520)],
    "sulphur_dioxide": [(0, 40), (41, 80), (81, 380), (381, 800), (801, 1600), (1601, 2100)],
    "ozone": [(0, 50), (51, 100), (101, 168), (169, 208), (209, 748), (749, 1000)],
    "carbon_monoxide": [(0, 1.0), (1.1, 2.0), (2.1, 10), (10.1, 17), (17.1, 34), (34.1, 50)],
}
CATEGORIES = [
    (50, "Good", "#2F7D4A", "Minimal impact."),
    (100, "Satisfactory", "#7BAF3F", "Minor breathing discomfort for sensitive people."),
    (200, "Moderate", "#D1A20A", "Breathing discomfort for people with lung or heart "
                                 "disease, children and older adults."),
    (300, "Poor", "#E07B24", "Breathing discomfort for most people on prolonged exposure."),
    (400, "Very poor", "#C0392B", "Respiratory illness on prolonged exposure."),
    (500, "Severe", "#7B1F1F", "Affects healthy people; serious impact on those with "
                               "existing disease."),
]
POLLUTANTS = {
    "pm2_5": ("PM2.5", "fine particles — smoke, vehicle and industrial exhaust"),
    "pm10": ("PM10", "coarse dust — roads, construction, soil"),
    "nitrogen_dioxide": ("NO₂", "mainly traffic exhaust"),
    "sulphur_dioxide": ("SO₂", "coal / fuel burning, industry"),
    "ozone": ("O₃", "formed in sunlight from traffic and industrial gases"),
    "carbon_monoxide": ("CO", "incomplete burning — traffic, stoves"),
}
_AVG_HOURS = {"ozone": 8, "carbon_monoxide": 8}  # the rest are 24-h averages


def _category(aqi: float | None):
    if aqi is None:
        return None
    for top, name, colour, health in CATEGORIES:
        if aqi <= top:
            return {"name": name, "colour": colour, "health": health}
    return {"name": "Severe", "colour": "#7B1F1F", "health": CATEGORIES[-1][3]}


def sub_index(pollutant: str, conc: float | None) -> int | None:
    """CPCB sub-index by linear interpolation inside the pollutant's band."""
    if conc is None:
        return None
    bps = CPCB_BREAKPOINTS[pollutant]
    c = round(conc, 1) if pollutant == "carbon_monoxide" else round(conc)
    for (lo, hi), (ilo, ihi) in zip(bps, _AQI_BANDS):
        if c <= hi:
            c = max(c, lo)
            return round(ilo + (ihi - ilo) * (c - lo) / ((hi - lo) or 1))
    return 500


def india_aqi(averages: dict[str, float | None]) -> dict:
    subs = {p: sub_index(p, v) for p, v in averages.items() if p in CPCB_BREAKPOINTS}
    have = {p: s for p, s in subs.items() if s is not None}
    if len(have) < 3 or not ({"pm2_5", "pm10"} & set(have)):
        return {"available": False,
                "reason": "CPCB method needs PM2.5 or PM10 plus at least two other pollutants."}
    lead = max(have, key=have.get)
    aqi = have[lead]
    return {"available": True, "aqi": aqi, "category": _category(aqi),
            "prominent_pollutant": POLLUTANTS[lead][0], "sub_indices": subs}


def _get(url, params, headers=None, timeout=15.0):
    last = None
    for _ in (1, 2):
        try:
            with httpx.Client(timeout=timeout, headers=headers) as c:
                r = c.get(url, params=params)
                r.raise_for_status()
                return r.json()
        except Exception as exc:  # noqa: BLE001
            last = exc
    raise last  # type: ignore[misc]


def _model(lat, lon) -> dict:
    if not reg.can_use_for_analysis("open_meteo_air_quality"):
        return {"available": False, "reason": "open_meteo_air_quality not analytically eligible"}
    keys = list(CPCB_BREAKPOINTS)
    try:
        j = _get("https://air-quality-api.open-meteo.com/v1/air-quality", {
            "latitude": f"{lat:.4f}", "longitude": f"{lon:.4f}", "timezone": "auto",
            "current": ",".join(keys + ["dust", "aerosol_optical_depth", "us_aqi"]),
            "hourly": ",".join(keys), "past_days": 1, "forecast_days": 2})
    except Exception as exc:  # noqa: BLE001
        return {"available": False, "reason": f"Air-quality service unreachable: {exc.__class__.__name__}"}
    cur, h = j.get("current") or {}, j.get("hourly") or {}
    if cur.get("pm2_5") is None:
        return {"available": False, "reason": "Air-quality service returned no current values"}
    times = h.get("time", [])
    now = cur.get("time", "")
    # index of the current hour in the hourly series
    i_now = max((i for i, t in enumerate(times) if t <= now), default=len(times) - 1)

    def trailing_avg(p, hours):
        vals = [v for v in (h.get(p) or [])[max(0, i_now - hours + 1): i_now + 1] if v is not None]
        return sum(vals) / len(vals) if vals else None

    avgs = {}
    for p in keys:
        a = trailing_avg(p, _AVG_HOURS.get(p, 24))
        avgs[p] = None if a is None else (a / 1000 if p == "carbon_monoxide" else a)  # CO → mg/m³
    idx = india_aqi(avgs)
    pollutants = []
    for p in keys:
        name, what = POLLUTANTS[p]
        now_v = cur.get(p)
        pollutants.append({
            "key": p, "name": name, "what": what,
            "now": None if now_v is None else round(now_v / 1000, 2) if p == "carbon_monoxide" else round(now_v, 1),
            "average": None if avgs[p] is None else round(avgs[p], 2 if p == "carbon_monoxide" else 1),
            "average_window": f"{_AVG_HOURS.get(p, 24)} h",
            "unit": "mg/m³" if p == "carbon_monoxide" else "µg/m³",
            "sub_index": (idx.get("sub_indices") or {}).get(p),
            "category": (_category((idx.get("sub_indices") or {}).get(p)) or {}).get("name"),
        })
    series = [{"time": t, "label": t[11:13] + "h", "pm2_5": v,
               "past": k <= i_now, "now": k == i_now}
              for k, (t, v) in enumerate(zip(times, h.get("pm2_5") or []))]
    lo, hi = max(0, i_now - 23), min(len(series), i_now + 25)
    upcoming = [s["pm2_5"] for s in series[i_now + 1: i_now + 25] if s["pm2_5"] is not None]
    trend = None
    if upcoming and cur.get("pm2_5") is not None:
        d = max(upcoming) - cur["pm2_5"]
        trend = ("likely to worsen" if d > 10 else "likely to improve"
                 if max(upcoming) < cur["pm2_5"] - 5 else "roughly steady")
    return {
        "available": True,
        "time_local": now,
        "india_aqi": idx,
        "us_aqi": cur.get("us_aqi"),
        "pollutants": pollutants,
        "dust": cur.get("dust"),
        "aerosol_optical_depth": cur.get("aerosol_optical_depth"),
        "pm2_5_series": series[lo:hi],
        "next_24h_peak_pm2_5": round(max(upcoming), 1) if upcoming else None,
        "trend_next_24h": trend,
        "provenance": {
            "dataset": "open_meteo_air_quality",
            "source": "Open-Meteo Air Quality API (Copernicus CAMS)",
            "note": "Regional model (~45 km) — a background level, not a street-side "
                    "reading. Indian AQI computed with CPCB breakpoints from the "
                    "model's trailing 24-h (8-h for O3/CO) averages.",
        },
    }


# --- optional: measured station readings (OpenAQ) ------------------------------
def _stations(lat, lon) -> dict:
    key = os.environ.get("OPENAQ_API_KEY", "").strip()
    if not key:
        return {"available": False, "configured": False,
                "reason": "Measured station readings are off: set a free OpenAQ API key "
                          "(OPENAQ_API_KEY) to show the nearest CPCB / state pollution "
                          "board monitors here."}
    if not reg.can_use_for_analysis("openaq_stations"):
        return {"available": False, "configured": True, "reason": "openaq_stations not analytically eligible"}
    hdr = {"X-API-Key": key}
    try:
        locs = _get("https://api.openaq.org/v3/locations", {
            "coordinates": f"{lat:.4f},{lon:.4f}", "radius": 25000, "limit": 5}, headers=hdr)
    except Exception as exc:  # noqa: BLE001
        return {"available": False, "configured": True,
                "reason": f"OpenAQ unreachable: {exc.__class__.__name__}"}
    out = []
    for loc in (locs.get("results") or [])[:3]:
        try:
            latest = _get(f"https://api.openaq.org/v3/locations/{loc['id']}/latest", {}, headers=hdr)
        except Exception:  # noqa: BLE001
            continue
        sensors = {s["id"]: s.get("parameter", {}) for s in loc.get("sensors", [])}
        readings = []
        for r in latest.get("results") or []:
            p = sensors.get(r.get("sensorsId"), {})
            if p.get("name") in ("pm25", "pm10", "no2", "so2", "o3", "co") and r.get("value") is not None:
                readings.append({"parameter": p.get("displayName") or p.get("name"),
                                 "value": r["value"], "unit": p.get("units"),
                                 "time": (r.get("datetime") or {}).get("local")})
        c = loc.get("coordinates") or {}
        out.append({"name": loc.get("name"), "provider": (loc.get("provider") or {}).get("name"),
                    "distance_km": round(ee._haversine_m(lat, lon, c.get("latitude"), c.get("longitude")) / 1000, 1)
                    if c.get("latitude") is not None else None,
                    "readings": readings})
    if not out:
        return {"available": False, "configured": True,
                "reason": "No monitoring station reports within 25 km of this point."}
    return {"available": True, "configured": True, "stations": out,
            "note": "Measured by CPCB / state pollution control board monitors, via OpenAQ."}


def get_live_air(lat: float, lon: float) -> dict:
    chk = ee.validate_coordinate(lat, lon)
    if not chk["valid"]:
        return {"error": chk["reason"]}
    key = (round(lat, 2), round(lon, 2))
    with _LOCK:
        hit = _CACHE.get(key)
        if hit and time.time() - hit[0] < _TTL:
            return hit[1]
    from concurrent.futures import ThreadPoolExecutor
    with ThreadPoolExecutor(max_workers=2) as pool:
        fm, fs = pool.submit(_model, lat, lon), pool.submit(_stations, lat, lon)
    out = {"location": {"latitude": round(lat, 5), "longitude": round(lon, 5), "city": chk["city"]},
           "fetched_at": datetime.now(timezone.utc).astimezone().strftime("%d %b %Y, %H:%M"),
           "refresh_seconds": _TTL, "model": fm.result(), "stations": fs.result()}
    if out["model"].get("available"):
        with _LOCK:
            _CACHE[key] = (time.time(), out)
    return out
