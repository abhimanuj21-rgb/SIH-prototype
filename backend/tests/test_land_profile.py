"""Land profile (plain-language outcome) + the A4 PDF built from it."""
from services import land_profile as lp
from tests.conftest import BHOPAL_CORE, CORE, OUTSIDE


# --- pure scoring --------------------------------------------------------------
def test_access_score_bands_are_monotonic():
    bands = (500, 1500, 4000)
    assert lp.access_score(0, bands) == 100
    assert lp.access_score(500, bands) == 100
    assert lp.access_score(1500, bands) == 70
    assert lp.access_score(4000, bands) == 40
    assert lp.access_score(50_000, bands) == 10
    assert lp.access_score(None, bands) is None  # a gap is never scored
    scores = [lp.access_score(d, bands) for d in range(0, 9000, 250)]
    assert scores == sorted(scores, reverse=True)


def test_nearest_index_matches_brute_force():
    pts = [(9.90 + i * 0.003, 78.10 + (i % 7) * 0.004, f"p{i}") for i in range(60)]
    idx = lp._NearestIndex(pts)
    for q in [(9.93, 78.12), (9.80, 78.30), (10.1, 78.0)]:
        d, _ = idx.nearest(*q)
        brute = min(lp.ee._haversine_m(q[0], q[1], a, b) for a, b, _ in pts)
        assert abs(d - brute) < 1e-6
    assert lp._NearestIndex([]).nearest(9.9, 78.1) == (None, None)


# --- API ---------------------------------------------------------------------
def test_land_profile_shape(client):
    p = client.post("/api/v1/evidence/land-profile", json=CORE).json()
    assert p["report_type"] == "land_profile"
    assert p["location"]["city"] == "madurai"
    v = p["verdict"]
    assert v["title"] and v["summary"]
    assert {f["key"] for f in p["facilities"]} == {"road", "health", "school", "rail", "water"}
    for f in p["facilities"]:
        assert f["score"] is None or 0 <= f["score"] <= 100
    # every use fit names the open checks it depends on, and says it's indicative
    assert len(p["use_fit"]) == 6
    assert all(u["verify_before_deciding"] for u in p["use_fit"])
    assert "not a zoning" in p["method"]["use_fit"].lower()
    cov = p["evidence_coverage"]
    assert 0 <= cov["pct"] <= 100
    assert {u["topic"] for u in cov["unknown"]} >= {"flood_hazard", "zoning_landuse_plan"}


def test_land_profile_benchmark_is_per_city(client):
    m = client.post("/api/v1/evidence/land-profile", json=CORE).json()
    b = client.post("/api/v1/evidence/land-profile", json=BHOPAL_CORE).json()
    assert m["benchmark"]["city"] == "madurai"
    assert b["benchmark"]["city"] == "bhopal"
    assert m["benchmark"]["sample_points"] == 144


def test_land_profile_rejects_outside_aoi(client):
    p = client.post("/api/v1/evidence/land-profile", json=OUTSIDE).json()
    assert "error" in p


def test_export_pdf_is_the_land_profile(client):
    r = client.get("/api/v1/evidence/export/pdf",
                   params={"latitude": CORE["latitude"], "longitude": CORE["longitude"]})
    assert r.status_code == 200
    assert r.content[:5] == b"%PDF-"
    assert "land_profile_madurai" in r.headers["content-disposition"]


def test_export_pdf_outside_aoi_still_returns_a_pdf(client):
    r = client.get("/api/v1/evidence/export/pdf",
                   params={"latitude": OUTSIDE["latitude"], "longitude": OUTSIDE["longitude"]})
    assert r.status_code == 200
    assert r.content[:5] == b"%PDF-"
