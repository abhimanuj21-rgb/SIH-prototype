"""API contract tests (Phases 2-6). Network-tolerant: climate/infrastructure
may be VERIFIED or a GAP depending on connectivity — both are valid."""
from tests.conftest import CORE, OUTSIDE

KNOWN_GAP_TOPICS = {
    "terrain_elevation_slope", "land_cover_class", "land_cover_change",
    "cadastral_parcel", "ownership_title", "flood_hazard",
    "zoning_landuse_plan", "soil_capability", "groundwater",
}


# --- health / registry ------------------------------------------------
def test_health(client):
    assert client.get("/api/v1/health").json()["status"] == "ok"


def test_registry_list(client):
    body = client.get("/api/v1/data-registry/").json()
    assert body["count"] == 26
    assert len(body["datasets"]) == 26


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
    assert a["total"] == 26
    assert a["passed"] == 26
    assert a["failed"] == 0
    assert a["demo_data_leak"] is False
    assert a["provenance_complete_all"] is True


# --- evidence ------------------------------------------------------
def test_evidence_location_structure(client):
    r = client.post("/api/v1/evidence/location", json=CORE).json()
    assert r["location"]["in_city_core"] is True
    topics = {g["topic"] for g in r["data_gaps"]}
    assert KNOWN_GAP_TOPICS <= topics
    # climate + infra are either verified or appear as gaps
    seen = {v["topic"] for v in r["verified_evidence"]} | topics
    assert {"climate", "infrastructure"} <= seen


def test_evidence_rejects_outside_aoi(client):
    r = client.post("/api/v1/evidence/location", json=OUTSIDE).json()
    assert "error" in r
    assert "area of interest" in r["error"].lower()


def test_evidence_report_is_descriptive(client):
    r = client.post("/api/v1/evidence/report", json=CORE).json()
    assert r["report_type"] == "location_evidence"
    assert "evidence_matrix" in r
    assert len(r["data_gaps"]) >= 9
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
    assert len(m["datasets"]) == 26
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


# --- gis -------------------------------------------------------
def test_boundary_available_and_real(client):
    b = client.get("/api/v1/gis/madurai/boundary").json()
    assert b["available"] is True
    assert b["is_demo"] is False
    assert b["geojson"]["features"][0]["geometry"]["type"] in ("Polygon", "MultiPolygon")


def test_terrain_reports_unavailable_not_fake(client):
    t = client.get("/api/v1/gis/madurai/terrain").json()
    assert t["available"] is False
    assert t["status"] == "DATA_UNAVAILABLE"
    assert "acquisition" in t and t["acquisition"]


def test_demo_grid_is_flagged(client):
    g = client.get("/api/v1/gis/madurai/demo-cadastral-grid").json()
    assert g["is_demo"] is True
    assert g["analytical_use"] == "forbidden"
    assert all(f["properties"]["is_demo"] for f in g["geojson"]["features"])
