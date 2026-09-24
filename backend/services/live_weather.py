"""
Live weather for a point — what it is like there *right now*, and how sure we are.

  current     Open-Meteo Forecast API (best-match national models) — updated
              every 15 min: temperature, feels-like, humidity, rain, cloud,
              wind, pressure, UV, sky condition.
  next_24h    hourly temperature + rain probability.
  forecast    7 days: high / low / rain / rain chance / UV / sunrise-sunset.
  air_now     current PM2.5 / PM10 / AQI (CAMS via Open-Meteo).
  observed    the nearest airport METAR (NOAA Aviation Weather Center) — a
              MEASURED reading, reported with its distance and age, so the
              model value can be checked against a real thermometer.
  vs_normal   today's forecast high against this month's 10-year ERA5 normal.

Cached ~10 minutes per ~1 km. Any failing source becomes an explicit
`available: False` block with the reason — never a fabricated reading.
"""
from __future__ import annotations

import math
import threading
import time
from datetime import datetime, timedelta, timezone

import httpx

from services import data_registry as reg
from services import evidence_engine as ee

_TTL = 600  # seconds
_CACHE: dict[tuple, tuple[float, dict]] = {}
_LOCK = threading.Lock()
_UA = "NDP-land-evidence-prototype/0.1 (research)"
IST = timezone(timedelta(hours=5, minutes=30))

# WMO weather interpretation codes (as used by Open-Meteo)
WMO = {
    0: ("Clear sky", "☀️"), 1: ("Mainly clear", "🌤️"), 2: ("Partly cloudy", "⛅"),
    3: ("Overcast", "☁️"), 45: ("Fog", "🌫️"), 48: ("Freezing fog", "🌫️"),
    51: ("Light drizzle", "🌦️"), 53: ("Drizzle", "🌦️"), 55: ("Heavy drizzle", "🌧️"),
    56: ("Freezing drizzle", "🌧️"), 57: ("Freezing drizzle", "🌧️"),
    61: ("Light rain", "🌦️"), 63: ("Rain", "🌧️"), 65: ("Heavy rain", "🌧️"),
    66: ("Freezing rain", "🌧️"), 67: ("Freezing rain", "🌧️"),
    71: ("Light snow", "🌨️"), 73: ("Snow", "🌨️"), 75: ("Heavy snow", "🌨️"),
    77: ("Snow grains", "🌨️"), 80: ("Light showers", "🌦️"), 81: ("Showers", "🌧️"),
    82: ("Violent showers", "⛈️"), 85: ("Snow showers", "🌨️"), 86: ("Snow showers", "🌨️"),
    95: ("Thunderstorm", "⛈️"), 96: ("Thunderstorm with hail", "⛈️"),
    99: ("Thunderstorm with heavy hail", "⛈️"),
}
_COMPASS = ["N", "NNE", "NE", "ENE", "E", "ESE", "SE", "SSE",
            "S", "SSW", "SW", "WSW", "W", "WNW", "NW", "NNW"]


def _compass(deg):
    return None if deg is None else _COMPASS[int((deg % 360) / 22.5 + 0.5) % 16]


def _sky(code):
    label, icon = WMO.get(code, ("Unknown", "🌡️"))
    return {"code": code, "label": label, "icon": icon}


def _get(url, params, headers=None, timeout=15.0):
    last = None
    for _ in (1, 2):  # one retry
        try:
            with httpx.Client(timeout=timeout, headers=headers) as c:
                r = c.get(url, params=params)
                r.raise_for_status()
                return r.json()
        except Exception as exc:  # noqa: BLE001
            last = exc
    raise last  # type: ignore[misc]


def http_reason(exc: Exception) -> str:
    """'HTTP 429 (rate-limited)' rather than a bare exception class name."""
    status = getattr(getattr(exc, "response", None), "status_code", None)
    if status == 429:
        return "HTTP 429 (rate-limited)"
    if status:
        return f"HTTP {status}"
    return exc.__class__.__name__


def _uv_note(uv):
    if uv is None:
        return None
    return ("Low" if uv < 3 else "Moderate" if uv < 6 else "High" if uv < 8
            else "Very high" if uv < 11 else "Extreme")


def _aqi_note(aqi):
    if aqi is None:
        return None
    return ("Good" if aqi <= 50 else "Moderate" if aqi <= 100 else
            "Unhealthy for sensitive groups" if aqi <= 150 else
            "Unhealthy" if aqi <= 200 else "Very unhealthy" if aqi <= 300 else "Hazardous")


# --- model: current + forecast ------------------------------------------------
def _forecast(lat, lon) -> dict:
    """Open-Meteo first; MET Norway if Open-Meteo refuses (e.g. a shared cloud
    IP over its free limit). Either way the source is named in provenance."""
    primary = _forecast_open_meteo(lat, lon)
    if primary.get("available"):
        return primary
    backup = _forecast_metno(lat, lon)
    if backup.get("available"):
        backup["provenance"]["fallback_reason"] = primary.get("reason")
        return backup
    return {"available": False,
            "reason": f"{primary.get('reason')}; backup {backup.get('reason')}"}


def _forecast_open_meteo(lat, lon) -> dict:
    if not reg.can_use_for_analysis("open_meteo_forecast"):
        return {"available": False, "reason": "open_meteo_forecast not analytically eligible"}
    try:
        j = _get("https://api.open-meteo.com/v1/forecast", {
            "latitude": f"{lat:.4f}", "longitude": f"{lon:.4f}", "timezone": "auto",
            "current": "temperature_2m,relative_humidity_2m,apparent_temperature,"
                       "precipitation,rain,weather_code,cloud_cover,wind_speed_10m,"
                       "wind_direction_10m,wind_gusts_10m,pressure_msl,is_day,"
                       "uv_index,dew_point_2m",
            "hourly": "temperature_2m,precipitation_probability,precipitation,weather_code",
            "daily": "weather_code,temperature_2m_max,temperature_2m_min,precipitation_sum,"
                     "precipitation_probability_max,sunrise,sunset,uv_index_max,"
                     "wind_speed_10m_max",
            "forecast_days": 7, "forecast_hours": 24})
    except Exception as exc:  # noqa: BLE001
        return {"available": False,
                "reason": f"Open-Meteo forecast unreachable: {http_reason(exc)}"}
    c, h, d = j.get("current") or {}, j.get("hourly") or {}, j.get("daily") or {}
    if c.get("temperature_2m") is None:
        return {"available": False, "reason": "Forecast service returned no current values"}
    current = {
        "time_local": c.get("time"),
        "temperature_c": c.get("temperature_2m"),
        "feels_like_c": c.get("apparent_temperature"),
        "humidity_pct": c.get("relative_humidity_2m"),
        "dew_point_c": c.get("dew_point_2m"),
        "precipitation_mm": c.get("precipitation"),
        "cloud_cover_pct": c.get("cloud_cover"),
        "wind_kmh": c.get("wind_speed_10m"),
        "wind_gust_kmh": c.get("wind_gusts_10m"),
        "wind_from": _compass(c.get("wind_direction_10m")),
        "pressure_hpa": c.get("pressure_msl"),  # sea-level, comparable with METAR QNH
        "uv_index": None if c.get("uv_index") is None else round(c["uv_index"], 1),
        "uv_note": _uv_note(c.get("uv_index")),
        "is_day": bool(c.get("is_day")),
        "sky": _sky(c.get("weather_code")),
    }
    hourly = [{"time": t[11:16], "temp_c": tc, "rain_chance_pct": pp, "rain_mm": pr,
               "sky": _sky(wc)["icon"]}
              for t, tc, pp, pr, wc in zip(h.get("time", []), h.get("temperature_2m", []),
                                           h.get("precipitation_probability", []),
                                           h.get("precipitation", []), h.get("weather_code", []))]
    daily = []
    for i, day in enumerate(d.get("time", [])):
        g = lambda k: (d.get(k) or [None] * 7)[i]  # noqa: E731
        dt = datetime.fromisoformat(day)
        daily.append({
            "date": day, "weekday": "Today" if i == 0 else dt.strftime("%a"),
            "sky": _sky(g("weather_code")),
            "max_c": g("temperature_2m_max"), "min_c": g("temperature_2m_min"),
            "rain_mm": g("precipitation_sum"), "rain_chance_pct": g("precipitation_probability_max"),
            "uv_max": None if g("uv_index_max") is None else round(g("uv_index_max"), 1),
            "wind_max_kmh": g("wind_speed_10m_max"),
            "sunrise": (g("sunrise") or "")[11:16], "sunset": (g("sunset") or "")[11:16],
        })
    return {"available": True, "current": current, "next_24h": hourly, "forecast_7d": daily,
            "grid_elevation_m": j.get("elevation"),
            "provenance": {"dataset": "open_meteo_forecast",
                           "source": "Open-Meteo Forecast API (best-match models)",
                           "updated": "every 15 minutes",
                           "note": "Model value for the ~km grid cell, not a site thermometer."}}


# --- backup: MET Norway Locationforecast (keyless, global, ECMWF-based) -------
_MET_SYMBOLS = [  # (symbol_code prefix, label, icon, severity)
    ("heavyrainandthunder", "Thunderstorm with heavy rain", "⛈️", 9),
    ("rainandthunder", "Thunderstorm", "⛈️", 8), ("rainshowersandthunder", "Thunderstorm", "⛈️", 8),
    ("lightrainandthunder", "Thunderstorm", "⛈️", 8),
    ("lightrainshowersandthunder", "Thunderstorm", "⛈️", 8),
    ("heavyrainshowersandthunder", "Thunderstorm with heavy rain", "⛈️", 9),
    ("heavyrainshowers", "Heavy showers", "🌧️", 7), ("heavyrain", "Heavy rain", "🌧️", 7),
    ("rainshowers", "Showers", "🌦️", 6), ("rain", "Rain", "🌧️", 6),
    ("lightrainshowers", "Light showers", "🌦️", 5), ("lightrain", "Light rain", "🌦️", 5),
    ("fog", "Fog", "🌫️", 3), ("cloudy", "Overcast", "☁️", 2),
    ("partlycloudy", "Partly cloudy", "⛅", 1), ("fair", "Mainly clear", "🌤️", 1),
    ("clearsky", "Clear sky", "☀️", 0),
]


def _met_sky(symbol: str | None) -> dict:
    code = (symbol or "").split("_")[0]
    for prefix, label, icon, sev in _MET_SYMBOLS:
        if code == prefix:
            return {"code": code, "label": label, "icon": icon, "severity": sev}
    return {"code": code or None, "label": code.replace("and", " and ").capitalize() or "Unknown",
            "icon": "🌡️", "severity": 4}


def _forecast_metno(lat, lon) -> dict:
    if not reg.can_use_for_analysis("met_norway_forecast"):
        return {"available": False, "reason": "met_norway_forecast not analytically eligible"}
    try:
        j = _get("https://api.met.no/weatherapi/locationforecast/2.0/complete",
                 {"lat": f"{lat:.4f}", "lon": f"{lon:.4f}"},
                 headers={"User-Agent": "NDP-land-evidence-prototype/0.1 "
                                        "github.com/abhimanuj21-rgb/SIH-prototype"})
    except Exception as exc:  # noqa: BLE001
        return {"available": False, "reason": f"MET Norway unreachable: {http_reason(exc)}"}
    ts = (j.get("properties") or {}).get("timeseries") or []
    if not ts:
        return {"available": False, "reason": "MET Norway returned no forecast steps"}

    def local(t):  # "2026-09-24T16:00:00Z" -> IST datetime
        return datetime.fromisoformat(t.replace("Z", "+00:00")).astimezone(IST)

    d0 = ts[0]["data"]
    ins = d0["instant"]["details"]
    n1 = d0.get("next_1_hours") or {}
    kmh = lambda v: None if v is None else round(v * 3.6, 1)  # noqa: E731
    current = {
        "time_local": local(ts[0]["time"]).strftime("%Y-%m-%dT%H:%M"),
        "temperature_c": ins.get("air_temperature"),
        "feels_like_c": ins.get("apparent_air_temperature"),
        "humidity_pct": None if ins.get("relative_humidity") is None else round(ins["relative_humidity"]),
        "dew_point_c": ins.get("dew_point_temperature"),
        "precipitation_mm": (n1.get("details") or {}).get("precipitation_amount"),
        "cloud_cover_pct": None if ins.get("cloud_area_fraction") is None else round(ins["cloud_area_fraction"]),
        "wind_kmh": kmh(ins.get("wind_speed")),
        "wind_gust_kmh": kmh(ins.get("wind_speed_of_gust")),
        "wind_from": _compass(ins.get("wind_from_direction")),
        "pressure_hpa": ins.get("air_pressure_at_sea_level"),
        "uv_index": ins.get("ultraviolet_index_clear_sky"),
        "uv_note": _uv_note(ins.get("ultraviolet_index_clear_sky")),
        "is_day": None,
        "sky": _met_sky((n1.get("summary") or {}).get("symbol_code")),
    }
    hourly = []
    for step in ts:
        n = step["data"].get("next_1_hours")
        if not n or len(hourly) >= 24:
            continue
        hourly.append({"time": local(step["time"]).strftime("%H:%M"),
                       "temp_c": step["data"]["instant"]["details"].get("air_temperature"),
                       "rain_chance_pct": None,
                       "rain_mm": (n.get("details") or {}).get("precipitation_amount"),
                       "sky": _met_sky((n.get("summary") or {}).get("symbol_code"))["icon"]})
    days: dict[str, dict] = {}
    for step in ts:
        lt = local(step["time"])
        day = days.setdefault(lt.date().isoformat(), {"temps": [], "rain": 0.0, "sky": [],
                                                       "uv": [], "wind": [], "hours": set()})
        det = step["data"]["instant"]["details"]
        if det.get("air_temperature") is not None:
            day["temps"].append(det["air_temperature"])
        if det.get("ultraviolet_index_clear_sky") is not None:
            day["uv"].append(det["ultraviolet_index_clear_sky"])
        if det.get("wind_speed") is not None:
            day["wind"].append(det["wind_speed"])
        day["hours"].add(lt.hour)
        nxt = step["data"].get("next_1_hours") or step["data"].get("next_6_hours")
        if nxt:
            day["rain"] += (nxt.get("details") or {}).get("precipitation_amount") or 0
            n6 = step["data"].get("next_6_hours") or {}
            for k in ("air_temperature_max", "air_temperature_min"):
                if (n6.get("details") or {}).get(k) is not None:
                    day["temps"].append(n6["details"][k])
            day["sky"].append(_met_sky((nxt.get("summary") or {}).get("symbol_code")))
    daily = []
    for i, (date_s, d) in enumerate(sorted(days.items())[:7]):
        if not d["temps"]:
            continue
        worst = max(d["sky"], key=lambda s: s["severity"]) if d["sky"] else _met_sky(None)
        daily.append({
            "date": date_s,
            "weekday": "Today" if i == 0 else datetime.fromisoformat(date_s).strftime("%a"),
            "sky": {k: worst[k] for k in ("code", "label", "icon")},
            "max_c": round(max(d["temps"]), 1), "min_c": round(min(d["temps"]), 1),
            "rain_mm": round(d["rain"], 1), "rain_chance_pct": None,
            "uv_max": round(max(d["uv"]), 1) if d["uv"] else None,
            "wind_max_kmh": kmh(max(d["wind"])) if d["wind"] else None,
            "sunrise": "", "sunset": "",
            # today's remaining hours only, if the forecast starts in the afternoon
            "partial": not any(10 <= h <= 16 for h in d["hours"]),
        })
    current["sky"] = {k: current["sky"][k] for k in ("code", "label", "icon")}
    return {"available": True, "current": current, "next_24h": hourly, "forecast_7d": daily,
            "grid_elevation_m": None,
            "provenance": {"dataset": "met_norway_forecast",
                           "source": "MET Norway Locationforecast 2.0 (ECMWF-based)",
                           "updated": "hourly",
                           "note": "Backup source, used because Open-Meteo did not answer. "
                                   "Model value for the grid cell; UV is the clear-sky index; "
                                   "no rain-probability field outside the Nordics."}}


# --- live air ----------------------------------------------------------------
def _air_now(lat, lon) -> dict:
    if not reg.can_use_for_analysis("open_meteo_air_quality"):
        return {"available": False, "reason": "open_meteo_air_quality not analytically eligible"}
    try:
        j = _get("https://air-quality-api.open-meteo.com/v1/air-quality", {
            "latitude": f"{lat:.4f}", "longitude": f"{lon:.4f}", "timezone": "auto",
            "current": "pm2_5,pm10,us_aqi"})
    except Exception as exc:  # noqa: BLE001
        return {"available": False, "reason": f"Air-quality service unreachable: {exc.__class__.__name__}"}
    c = j.get("current") or {}
    if c.get("pm2_5") is None:
        return {"available": False, "reason": "No current air-quality value"}
    return {"available": True, "pm2_5": c.get("pm2_5"), "pm10": c.get("pm10"),
            "us_aqi": c.get("us_aqi"), "aqi_note": _aqi_note(c.get("us_aqi")),
            "time_local": c.get("time"),
            "note": "CAMS regional model (~45 km); AQI on the US EPA scale."}


# --- measured: nearest airport METAR -----------------------------------------
def _rh(t, td):
    """Relative humidity (%) from temperature and dew point (Magnus formula)."""
    a, b = 17.625, 243.04
    return round(100 * math.exp(a * td / (b + td)) / math.exp(a * t / (b + t)))


def _observed(lat, lon) -> dict:
    if not reg.can_use_for_analysis("awc_metar"):
        return {"available": False, "reason": "awc_metar not analytically eligible"}
    box = f"{lat - 2:.2f},{lon - 2:.2f},{lat + 2:.2f},{lon + 2:.2f}"
    try:
        rows = _get("https://aviationweather.gov/api/data/metar",
                    {"bbox": box, "format": "json", "hours": 3}, headers={"User-Agent": _UA})
    except Exception as exc:  # noqa: BLE001
        return {"available": False, "reason": f"Aviation Weather Center unreachable: {exc.__class__.__name__}"}
    best = None
    for r in rows or []:
        if r.get("temp") is None or r.get("lat") is None:
            continue
        d = ee._haversine_m(lat, lon, r["lat"], r["lon"]) / 1000
        # keep the latest report per station, then the nearest station
        if best is None or d < best[0] - 0.01 or (abs(d - best[0]) < 0.01 and
                                                  r.get("obsTime", 0) > best[1].get("obsTime", 0)):
            best = (d, r)
    if best is None:
        return {"available": False,
                "reason": "No airport weather station has reported within ~200 km in the last 3 hours."}
    dist, r = best
    obs = datetime.fromtimestamp(r["obsTime"], tz=timezone.utc)
    age_min = round((datetime.now(timezone.utc) - obs).total_seconds() / 60)
    vis = r.get("visib")
    try:
        vis_km = round(float(str(vis).rstrip("+")) * 1.609, 1)
    except (TypeError, ValueError):
        vis_km = None
    clouds = ", ".join(f"{c.get('cover')}{' at ' + str(round(c['base'] * 0.3048)) + ' m' if c.get('base') else ''}"
                       for c in r.get("clouds") or [] if c.get("cover"))
    return {
        "available": True,
        "station": r.get("name") or r.get("icaoId"),
        "icao": r.get("icaoId"),
        "distance_km": round(dist, 1),
        "observed_local": obs.astimezone(IST).strftime("%d %b %H:%M IST"),
        "age_minutes": age_min,
        "stale": age_min > 180,
        "temperature_c": r.get("temp"),
        "dew_point_c": r.get("dewp"),
        "humidity_pct": _rh(r["temp"], r["dewp"]) if r.get("dewp") is not None else None,
        "wind_kmh": None if r.get("wspd") is None else round(r["wspd"] * 1.852),
        "wind_gust_kmh": None if r.get("wgst") is None else round(r["wgst"] * 1.852),
        "wind_from": _compass(r["wdir"]) if isinstance(r.get("wdir"), (int, float)) else r.get("wdir"),
        "pressure_hpa": r.get("altim"),
        "visibility_km": vis_km,
        "weather": r.get("wxString"),
        "clouds": clouds or None,
        "raw": r.get("rawOb"),
        "station_elevation_m": r.get("elev"),
    }


# --- today vs the 10-year normal ---------------------------------------------
def _vs_normal(lat, lon, fc: dict) -> dict:
    if not fc.get("available") or not fc["forecast_7d"]:
        return {"available": False}
    clim = ee._climate_evidence(lat, lon)
    if not clim.get("ok") or not clim.get("detail"):
        return {"available": False, "reason": "10-year climate normals unavailable"}
    days = fc["forecast_7d"]
    today = next((d for d in days if not d.get("partial")), days[0])
    which = "Today's" if today is days[0] else "Tomorrow's" if len(days) > 1 and today is days[1] \
        else f"{today['weekday']}'s"
    month = datetime.fromisoformat(today["date"]).strftime("%b")
    norm = next((m for m in clim["detail"]["monthly"] if m["month"] == month), None)
    if not norm or norm.get("temp_max_c") is None or today.get("max_c") is None:
        return {"available": False}
    diff = round(today["max_c"] - norm["temp_max_c"], 1)
    word = ("warmer than" if diff >= 1.5 else "cooler than" if diff <= -1.5
            else "close to")
    return {"available": True, "month": month, "today_max_c": today["max_c"],
            "normal_max_c": norm["temp_max_c"], "difference_c": diff,
            "normal_month_rain_mm": norm.get("rain_mm"),
            "summary": f"{which} forecast high of {today['max_c']} °C is {word} the "
                       f"{month} normal of {norm['temp_max_c']} °C "
                       f"({'+' if diff > 0 else ''}{diff} °C, 10-year ERA5)."}


def _agreement(fc: dict, obs: dict) -> dict | None:
    """How close the model's current temperature is to the measured one."""
    if not (fc.get("available") and obs.get("available")) or obs.get("stale"):
        return None
    diff = round(fc["current"]["temperature_c"] - obs["temperature_c"], 1)
    level = ("close agreement" if abs(diff) <= 2 else "some difference" if abs(diff) <= 4
             else "large difference")
    return {"difference_c": diff, "level": level,
            "note": f"Model says {fc['current']['temperature_c']} °C here; "
                    f"{obs['station']} measured {obs['temperature_c']} °C "
                    f"{obs['distance_km']} km away ({level}; distance, elevation and the "
                    f"{obs['age_minutes']}-minute gap explain small differences)."}


def get_live_weather(lat: float, lon: float) -> dict:
    chk = ee.validate_coordinate(lat, lon)
    if not chk["valid"]:
        return {"error": chk["reason"]}
    key = (round(lat, 2), round(lon, 2))
    with _LOCK:
        hit = _CACHE.get(key)
        if hit and time.time() - hit[0] < _TTL:
            return hit[1]
    from concurrent.futures import ThreadPoolExecutor
    with ThreadPoolExecutor(max_workers=3) as pool:
        f_fc = pool.submit(_forecast, lat, lon)
        f_air = pool.submit(_air_now, lat, lon)
        f_obs = pool.submit(_observed, lat, lon)
    fc, air, obs = f_fc.result(), f_air.result(), f_obs.result()
    out = {
        "location": {"latitude": round(lat, 5), "longitude": round(lon, 5), "city": chk["city"]},
        "fetched_at": datetime.now(IST).strftime("%d %b %Y, %H:%M IST"),
        "refresh_seconds": _TTL,
        "model": fc,
        "air_now": air,
        "observed": obs,
        "agreement": _agreement(fc, obs),
        "vs_normal": _vs_normal(lat, lon, fc),
    }
    if fc.get("available"):
        with _LOCK:
            _CACHE[key] = (time.time(), out)
    return out
