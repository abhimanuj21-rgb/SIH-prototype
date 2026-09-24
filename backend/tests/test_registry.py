"""Data registry + analytical gate (Phase 2)."""
from services import data_registry as reg


def test_exactly_44_datasets():
    assert len(reg.DATASETS) == 44
    assert len({d["id"] for d in reg.DATASETS}) == 44


def test_every_dataset_has_complete_provenance():
    required = ("source", "authority", "license", "limitations", "acquisition")
    for d in reg.DATASETS:
        missing = [f for f in required if not d.get(f)]
        assert not missing, f"{d['id']} missing provenance: {missing}"


def test_status_values_are_valid():
    valid = {s.value for s in reg.Status}
    for d in reg.DATASETS:
        assert d["status"] in valid


def test_analytical_gate_matches_status_and_flag():
    for d in reg.DATASETS:
        expected = d["status"] == "AVAILABLE" and d["analytical_eligible"]
        assert reg.can_use_for_analysis(d["id"]) is bool(expected)


def test_demo_data_never_passes_gate():
    for d in reg.DATASETS:
        if d["status"] == "DEMO_ONLY":
            assert reg.can_use_for_analysis(d["id"]) is False


def test_known_restricted_datasets_are_closed():
    for ds in ("bhuvan_lulc", "cadastral_geometry", "ownership_records",
               "tnsdma_flood_hazard", "nbsslup_soil"):
        assert reg.can_use_for_analysis(ds) is False


def test_known_available_datasets_are_open():
    for ds in ("open_meteo_climate", "osm_infrastructure", "madurai_boundary"):
        assert reg.can_use_for_analysis(ds) is True


def test_unknown_dataset_is_closed():
    assert reg.can_use_for_analysis("does_not_exist") is False


def test_summary_counts_add_up():
    s = reg.summary()
    assert s["total"] == 44
    assert sum(s["by_status"].values()) == 44
    assert s["analytically_usable_count"] == len(s["analytically_usable"])
