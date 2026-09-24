"""Live weather — network-tolerant: every block is either real and sane, or an
explicit `available: False` with a reason."""
from services import data_registry as reg
from services import live_weather as lw
from tests.conftest import CORE, OUTSIDE


def test_humidity_from_dew_point_is_physical():
    assert lw._rh(30, 30) == 100
    assert 35 <= lw._rh(34, 18) <= 42      # the METAR 34/18 case → ~39 %
    assert lw._rh(30, 10) < lw._rh(30, 20)


def test_compass_and_codes():
    assert lw._compass(0) == "N" and lw._compass(250) == "WSW" and lw._compass(None) is None
    assert lw._sky(95)["label"] == "Thunderstorm"
    assert lw._sky(12345)["label"] == "Unknown"  # unknown code is never guessed


def test_live_sources_are_registered():
    for ds in ("open_meteo_forecast", "awc_metar"):
        assert reg.can_use_for_analysis(ds) is True
        assert reg.get_dataset(ds)["limitations"]


def test_live_weather_endpoint(client):
    r = client.get("/api/v1/evidence/live-weather",
                   params={"latitude": CORE["latitude"], "longitude": CORE["longitude"]}).json()
    m = r["model"]
    if m["available"]:
        c = m["current"]
        assert -5 < c["temperature_c"] < 50
        assert 0 <= c["humidity_pct"] <= 100
        assert len(m["forecast_7d"]) == 7
        assert len(m["next_24h"]) == 24
    else:
        assert m["reason"]
    o = r["observed"]
    if o["available"]:
        assert o["distance_km"] < 300 and o["station"]
    else:
        assert o["reason"]


def test_live_weather_rejects_outside_aoi(client):
    r = client.get("/api/v1/evidence/live-weather",
                   params={"latitude": OUTSIDE["latitude"], "longitude": OUTSIDE["longitude"]}).json()
    assert "error" in r
