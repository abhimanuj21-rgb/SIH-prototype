"""API contract tests (Phases 2-6). Network-tolerant: climate/infrastructure
may be VERIFIED or a GAP depending on connectivity — both are valid."""
from tests.conftest import BHOPAL_CORE, CORE, KOVILPATTI_CORE, OUTSIDE

KNOWN_GAP_TOPICS = {
    "cadastral_parcel", "ownership_title", "flood_hazard",
    "zoning_landuse_plan", "soil_capability", "groundwater",
}


# --- health / registry ------------------------------------------------
def test_health(client):
    assert client.get("/api/v1/health").json()["status"] == "ok"


def test_registry_list(client):
    body = client.get("/api/v1/data-registry/").json()
    assert body["count"] == 42
    assert len(body["datasets"]) == 42


def test_registry_filter_by_city(client):
    body = client.get("/api/v1/data-registry/?city=bhopal").json()
    ids = {d["id"] for d in body["datasets"]}
    assert "mp_cadastral_geometry" in ids
    assert "cadastral_geometry" not in ids  # Madurai-only dataset excluded
    assert "open_meteo_climate" in ids  # national dataset always included


def test_registry_filter_by_status(client):
    body = client.get("/api/v1/data-registry/?status=AVAILABLE").json()
    assert body["count"] >= 4
    assert all(d["status"] == "AVAILABLE" for d in body["datasets"])


def test_registry_gate_endpoint(client):
    assert client.get("/api/v1/data-registry/gate/demo_cadastral_grid").json()[
        "can_use_for_analysis"] is False
    assert client.get("/api/v1/data-registry/gate/open_meteo_climate").json()[
        "can_use_for_analysis"] is True
    assert client.get("/api/v1/data-registry/gate/nope").status_code == 404


def test_registry_detail_404(client):
    assert client.get("/api/v1/data-registry/nonexistent").status_code == 404


# --- data quality ---------------------------------------------------
def test_quality_audit_all_pass(client):
    a = client.get("/api/v1/data-quality/audit").json()
    assert a["total"] == 42
    assert a["passed"] == 42
    assert a["failed"] == 0
    assert a["demo_data_leak"] is False
    assert a["provenance_complete_all"] is True


# --- evidence ------------------------------------------------------
def test_evidence_location_structure(client):
    r = client.post("/api/v1/evidence/location", json=CORE).json()
    assert r["location"]["in_city_core"] is True
    topics = {g["topic"] for g in r["data_gaps"]}
    assert KNOWN_GAP_TOPICS <= topics
    # live sources are either verified or appear as gaps
    seen = {v["topic"] for v in r["verified_evidence"]} | topics
    assert {"climate", "infrastructure", "terrain", "soil", "air_quality",
            "locality", "land_cover"} <= seen
    # GLO-90 terrain closes the terrain gap only when it actually verified
    verified = {v["topic"] for v in r["verified_evidence"]}
    assert ("terrain" in verified) != ("terrain_elevation_slope" in topics)
    assert ("land_cover" in verified) != ("land_cover_class" in topics)


def test_evidence_resolves_bhopal_as_its_own_city(client):
    r = client.post("/api/v1/evidence/location", json=BHOPAL_CORE).json()
    assert r["location"]["city"] == "bhopal"
    assert r["location"]["in_city_core"] is True
    assert "Bhopal" in r["location"]["area_of_interest"]
    gap_datasets = {g.get("dataset") for g in r["data_gaps"]}
    assert "mp_cadastral_geometry" in gap_datasets
    assert "cadastral_geometry" not in gap_datasets  # that's Madurai's, not Bhopal's


def test_evidence_resolves_kovilpatti_and_shares_tn_datasets_with_madurai(client):
    r = client.post("/api/v1/evidence/location", json=KOVILPATTI_CORE).json()
    assert r["location"]["city"] == "kovilpatti"
    assert r["location"]["in_city_core"] is True
    gap_datasets = {g.get("dataset") for g in r["data_gaps"]}
    # Same real Tamil Nadu authorities as Madurai — not a duplicated dataset.
    assert "cadastral_geometry" in gap_datasets
    assert "tnsdma_flood_hazard" in gap_datasets
    # But its own town-specific master plan, which is genuinely different
    # (still in preparation, unlike Madurai's published one).
    assert "kovilpatti_master_plan" in gap_datasets
    assert "master_plan" not in gap_datasets


def test_registry_filter_by_city_shares_state_datasets(client):
    """Madurai and Kovilpatti are both Tamil Nadu — a state-authority dataset
    (not a per-town one like a boundary or master plan) must appear for both."""
    maps = {}
    for city in ("madurai", "kovilpatti"):
        body = client.get(f"/api/v1/data-registry/?city={city}").json()
        maps[city] = {d["id"] for d in body["datasets"]}
    assert "cadastral_geometry" in maps["madurai"] & maps["kovilpatti"]
    assert "madurai_boundary" in maps["madurai"] - maps["kovilpatti"]
    assert "kovilpatti_boundary" in maps["kovilpatti"] - maps["madurai"]


def test_site_context_uses_the_right_citys_cache(client):
    """Regression: site_context.py once read a single un-suffixed cache file
    (osm_hydrology.geojson etc.), so a Bhopal point silently got Madurai's
    cached OSM layers — Bhopal's real lakes would show up as "no water"."""
    # Warm both cities' hydrology caches first (mirrors gis.warm_infrastructure_cache).
    client.get("/api/v1/gis/madurai/hydrology/osm")
    client.get("/api/v1/gis/bhopal/hydrology/osm")
    r = client.post("/api/v1/evidence/site-context", json=BHOPAL_CORE).json()
    assert r["location"]["city"] == "bhopal"
    if r.get("available"):
        # Bhopal's core sits right by the Upper Lake — if this ever reports
        # zero waterbodies again, it's reading the wrong city's cache.
        assert r["water"]["counts_within_2_5km"]["waterbodies"] > 0
        assert "Madurai" not in r["water"]["coast"]["note"]


def test_evidence_rejects_outside_aoi(client):
    r = client.post("/api/v1/evidence/location", json=OUTSIDE).json()
    assert "error" in r
    assert "area of interest" in r["error"].lower()


def test_site_context_shape(client):
    r = client.post("/api/v1/evidence/site-context", json=CORE).json()
    assert "location" in r
    if r.get("available"):
        for block in ("water", "land_use", "development"):
            assert block in r
        assert "level" in r["development"]
        assert "not a" in r["development"]["method"].lower()  # honest caveat
        assert r["provenance"]["confidence"] == "medium"
    else:
        assert r.get("reason")


def test_site_context_rejects_outside_aoi(client):
    r = client.post("/api/v1/evidence/site-context", json=OUTSIDE).json()
    assert r["available"] is False


def test_infrastructure_evidence_splits_hospital_and_clinic(client):
    r = client.post("/api/v1/evidence/location", json=CORE).json()
    infra = next((v for v in r["verified_evidence"] if v["topic"] == "infrastructure"), None)
    if infra is None:
        return  # infra layer not warmed in this environment; other tests cover it
    val = infra["value"]
    for k in ("distance_to_hospital_m", "distance_to_clinic_or_hospital_m",
              "distance_to_school_m", "distance_to_school_or_college_m",
              "distance_to_railway_station_m"):
        assert k in val


def test_evidence_report_is_descriptive(client):
    r = client.post("/api/v1/evidence/report", json=CORE).json()
    assert r["report_type"] == "location_evidence"
    assert "evidence_matrix" in r
    # the government-held gaps never close from open data alone
    assert {"soil_capability", "groundwater", "cadastral_parcel", "ownership_title",
            "flood_hazard", "zoning_landuse_plan"} <= {g["topic"] for g in r["data_gaps"]}
    text = (r["conclusion"] + " " + r["disclaimer"]).lower()
    assert "descriptive" in text
    assert "not for" in text or "not a prediction" in text or "no prediction" in text


# --- exports -----------------------------------------------------
def test_export_pdf_is_pdf(client):
    r = client.get("/api/v1/evidence/export/pdf",
                   params={"latitude": CORE["latitude"], "longitude": CORE["longitude"]})
    assert r.status_code == 200
    assert r.content[:5] == b"%PDF-"
    assert b"%%EOF" in r.content[-8:]


def test_export_json_and_manifest(client):
    j = client.get("/api/v1/evidence/export/json",
                   params={"latitude": CORE["latitude"], "longitude": CORE["longitude"]})
    assert j.status_code == 200 and j.json()["report_type"] == "location_evidence"
    m = client.get("/api/v1/evidence/export/manifest").json()
    assert len(m["datasets"]) == 42
    assert m["analytical_gate"].startswith("status == AVAILABLE")


# --- analytics ---------------------------------------------------
def test_features_partial_by_design(client):
    f = client.post("/api/v1/analytics/features", json=CORE).json()
    assert "terrain" in f["missing_blocks"]
    assert "lulc" in f["missing_blocks"]
    assert f["provenance_complete"] is True


def test_suitability_refuses_incomplete_evidence(client):
    for kind in ("agricultural", "development"):
        s = client.post("/api/v1/analytics/suitability",
                        json={**CORE, "type": kind}).json()
        assert s["scorable"] is False
        assert "terrain.slope_deg" in s["missing_features"]
        assert "no ml" in s["method"].lower()


def test_suitability_bad_type(client):
    s = client.post("/api/v1/analytics/suitability",
                    json={**CORE, "type": "banana"}).json()
    assert "error" in s


ALL_CITIES = ("madurai", "bhopal", "kovilpatti")


# --- gis -------------------------------------------------------
def test_gis_lists_all_cities(client):
    body = client.get("/api/v1/gis/cities").json()
    ids = {c["id"] for c in body["cities"]}
    assert ids == set(ALL_CITIES)


def test_gis_unknown_city_404(client):
    assert client.get("/api/v1/gis/atlantis/boundary").status_code == 404


def test_boundary_available_and_real(client):
    for city in ALL_CITIES:
        b = client.get(f"/api/v1/gis/{city}/boundary").json()
        assert b["available"] is True
        assert b["is_demo"] is False
        assert b["geojson"]["features"][0]["geometry"]["type"] in ("Polygon", "MultiPolygon")


def test_terrain_reports_unavailable_not_fake(client):
    t = client.get("/api/v1/gis/madurai/terrain").json()
    assert t["available"] is False
    assert t["status"] == "DATA_UNAVAILABLE"
    assert "acquisition" in t and t["acquisition"]


def test_demo_grid_is_flagged(client):
    for city in ALL_CITIES:
        g = client.get(f"/api/v1/gis/{city}/demo-cadastral-grid").json()
        assert g["is_demo"] is True
        assert g["analytical_use"] == "forbidden"
        feats = g["geojson"]["features"]
        assert len(feats) >= 4
        assert all(f["properties"]["is_demo"] for f in feats)
        assert all(f["properties"]["area_sqm"] > 0 for f in feats)


def test_demo_grid_parcel_count_is_configurable(client):
    g = client.get("/api/v1/gis/madurai/demo-cadastral-grid",
                   params={"parcels": 12, "seed": 7}).json()
    assert len(g["geojson"]["features"]) == 12
