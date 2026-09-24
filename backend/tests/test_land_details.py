"""Land details: terrain / soil / air / locality / amenities. Network-tolerant —
each live source is either verified with sane values or an explicit gap."""
from services import data_registry as reg
from services import land_details as ld
from services import land_profile as lp
from tests.conftest import CORE

RURAL = {"latitude": 9.80, "longitude": 78.30}  # open land inside the Madurai AOI


# --- pure logic ----------------------------------------------------------------
def test_usda_texture_triangle_reference_points():
    assert ld.texture_class(92, 5, 3) == "Sand"
    assert ld.texture_class(82, 12, 6) == "Loamy sand"
    assert ld.texture_class(65, 25, 10) == "Sandy loam"
    assert ld.texture_class(40, 40, 20) == "Loam"
    assert ld.texture_class(20, 65, 15) == "Silt loam"
    assert ld.texture_class(5, 88, 7) == "Silt"
    assert ld.texture_class(60, 13, 27) == "Sandy clay loam"
    assert ld.texture_class(35, 30, 35) == "Clay loam"
    assert ld.texture_class(10, 55, 35) == "Silty clay loam"
    assert ld.texture_class(50, 5, 45) == "Sandy clay"
    assert ld.texture_class(5, 45, 50) == "Silty clay"
    assert ld.texture_class(20, 20, 60) == "Clay"


def test_slope_and_soil_points_are_bounded_and_ordered():
    flat = {"slope_deg": 0.5, "relative_position": "Level with its surroundings"}
    steep = {"slope_deg": 20, "relative_position": "Lower than its surroundings"}
    assert lp._slope_pts(flat, "build") > lp._slope_pts(steep, "build")
    assert lp._position_pts(flat) > lp._position_pts(steep)
    assert lp._slope_pts(None, "build") is None  # a gap is never scored
    good = {"texture_class": "Loam", "ph": 6.8, "organic_carbon_g_per_kg": 15}
    poor = {"texture_class": "Sand", "ph": 9.2, "organic_carbon_g_per_kg": 2}
    assert lp._soil_pts(good) == 100
    assert 0 < lp._soil_pts(poor) < 50


def test_new_sources_are_registered_and_gated():
    for ds in ("open_meteo_elevation", "soilgrids", "open_meteo_air_quality",
               "nominatim_geocoding", "osm_amenities"):
        d = reg.get_dataset(ds)
        assert d and d["limitations"], ds
        assert reg.can_use_for_analysis(ds) is True
    # the modelled soil must not quietly replace the official survey gap
    assert reg.can_use_for_analysis("nbsslup_soil") is False


# --- live (network-tolerant) ------------------------------------------------------
def test_terrain_is_verified_or_a_gap():
    r = ld.SOURCES["terrain"](RURAL["latitude"], RURAL["longitude"])
    if not r["ok"]:
        assert r["reason"]
        return
    v = r["value"]
    assert 0 < v["elevation_m"] < 1000
    assert 0 <= v["slope_deg"] < 45
    assert v["relative_position"].split()[0] in ("Lower", "Higher", "Level")
    assert len(r["detail"]["profile_west_east"]) == 21


def test_soil_is_verified_or_an_explained_gap():
    r = ld.SOURCES["soil"](RURAL["latitude"], RURAL["longitude"])
    if not r["ok"]:
        assert r["reason"]
        return
    v = r["value"]
    assert abs(v["sand_pct"] + v["silt_pct"] + v["clay_pct"] - 100) < 3
    assert 3 < v["ph"] < 11
    assert "model" in r["provenance"]["note"].lower()


def test_profile_carries_details_and_new_use(client):
    p = client.post("/api/v1/evidence/land-profile", json=CORE).json()
    assert {"terrain", "soil", "air_quality", "locality", "amenities"} <= set(p["details"])
    assert "solar" in {u["key"] for u in p["use_fit"]}
    am = p["details"]["amenities"]
    if am.get("available"):
        assert am["total_within_500m"] <= am["total_within_1km"]
    for f in p["verdict"]["facts"]:
        assert f["label"] and f["value"]
