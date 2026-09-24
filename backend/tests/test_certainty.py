"""Raising certainty honestly: satellite land cover, flood screening,
satellite-vs-OSM cross-checks and the soil fallback."""
from services import data_registry as reg
from services import land_details as ld
from services import land_profile as lp
from tests.conftest import CORE

LOW_WET = {"relative_to_1km_m": -6, "slope_deg": 0.4, "relative_position": "Lower than its surroundings"}
HIGH_DRY = {"relative_to_1km_m": 7, "slope_deg": 2.5, "relative_position": "Higher than its surroundings"}


def test_flood_screening_orders_sites_sensibly():
    wet = lp.flood_screening(LOW_WET, 120, {"years_with_water_nearby": 8})
    dry = lp.flood_screening(HIGH_DRY, 2500, {"years_with_water_nearby": 0})
    assert wet["level"] == "Elevated" and dry["level"] == "Low"
    assert wet["points"] > dry["points"]
    assert "not the official" in wet["note"]           # never passed off as the official map
    assert lp.flood_screening(None, 100, None)["available"] is False


def test_effective_development_prefers_satellite():
    assert lp.effective_development("Undeveloped / open land",
                                    {"built_pct": 67, "crops_pct": 20}) == "Urban / built-up"
    assert lp.effective_development("Undeveloped / open land",
                                    {"built_pct": 27, "crops_pct": 73}) == "Agricultural / rural"
    assert lp.effective_development("Sparsely developed", None) == "Sparsely developed"


def test_cross_check_flags_osm_vs_satellite_disagreement():
    site = {"development": {"level": "Undeveloped / open land"},
            "land_use": {"available": True, "is_built_up": False, "is_agricultural": False}}
    lc = {"built_pct": 67, "crops_pct": 20, "year": 2025, "site_class": "Built area"}
    checks = {c["check"]: c["result"] for c in lp._cross_checks(site, lc)}
    assert checks["Development level — OpenStreetMap vs satellite"] == "disagree"
    assert checks["Land use — OpenStreetMap vs satellite"] == "filled"


def test_land_cover_source_is_registered():
    d = reg.get_dataset("esri_lulc_timeseries")
    assert d and reg.can_use_for_analysis("esri_lulc_timeseries")
    assert "accuracy" in d["limitations"]
    # the full rasters for map layers are still honestly pending
    assert reg.can_use_for_analysis("esri_lulc_2024") is False


def test_land_cover_live_is_verified_or_a_gap():
    r = ld.SOURCES["land_cover"](9.97, 78.18)
    if not r["ok"]:
        assert r["reason"]
        return
    s = r["detail"]["series"]
    assert s[0]["year"] == 2017 and len(s) >= 2
    for row in s:
        assert 0 <= row["built_pct"] <= 100 and 0 <= row["crops_pct"] <= 100


def test_profile_reports_evidence_kinds(client):
    p = client.post("/api/v1/evidence/land-profile", json=CORE).json()
    cov = p["evidence_coverage"]
    assert all(k.get("kind") for k in cov["known"])
    assert "cross_checks" in cov
    # the official flood map stays a gap even when the screening is available
    assert "flood_hazard" in {u["topic"] for u in cov["unknown"]}
