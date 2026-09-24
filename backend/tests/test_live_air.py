"""Live air: CPCB Indian AQI maths (pure) + the endpoint (network-tolerant)."""
from services import data_registry as reg
from services import live_air as la
from tests.conftest import CORE, OUTSIDE


def test_cpcb_sub_index_band_edges():
    # PM2.5 24-h: 0-30 -> 0-50, 31-60 -> 51-100, 121-250 -> 301-400
    assert la.sub_index("pm2_5", 0) == 0
    assert la.sub_index("pm2_5", 30) == 50
    assert la.sub_index("pm2_5", 31) == 51
    assert la.sub_index("pm2_5", 45) == 75
    assert la.sub_index("pm2_5", 250) == 400
    assert la.sub_index("pm10", 100) == 100
    assert la.sub_index("carbon_monoxide", 1.5) == 73   # mg/m³, 8-h
    assert la.sub_index("pm10", 9999) == 500              # capped, never beyond scale
    assert la.sub_index("ozone", None) is None           # missing is never guessed


def test_india_aqi_takes_the_worst_pollutant():
    r = la.india_aqi({"pm2_5": 45, "pm10": 80, "nitrogen_dioxide": 20})
    assert r["available"] and r["aqi"] == 80 and r["prominent_pollutant"] == "PM10"
    assert r["category"]["name"] == "Satisfactory"


def test_india_aqi_needs_pm_and_three_pollutants():
    assert la.india_aqi({"pm2_5": 45, "ozone": 60})["available"] is False
    assert la.india_aqi({"ozone": 60, "nitrogen_dioxide": 20,
                         "sulphur_dioxide": 10})["available"] is False


def test_station_source_is_registered_and_off_without_a_key(monkeypatch):
    assert reg.get_dataset("openaq_stations")["limitations"]
    monkeypatch.delenv("OPENAQ_API_KEY", raising=False)
    s = la._stations(9.9252, 78.1198)
    assert s["available"] is False and s["configured"] is False


def test_live_air_endpoint(client):
    r = client.get("/api/v1/evidence/live-air",
                   params={"latitude": CORE["latitude"], "longitude": CORE["longitude"]}).json()
    m = r["model"]
    if not m["available"]:
        assert m["reason"]
        return
    assert {p["key"] for p in m["pollutants"]} == set(la.CPCB_BREAKPOINTS)
    if m["india_aqi"]["available"]:
        assert 0 <= m["india_aqi"]["aqi"] <= 500
    assert any(s["now"] for s in m["pm2_5_series"])


def test_live_air_rejects_outside_aoi(client):
    r = client.get("/api/v1/evidence/live-air",
                   params={"latitude": OUTSIDE["latitude"], "longitude": OUTSIDE["longitude"]}).json()
    assert "error" in r
