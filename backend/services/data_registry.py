"""
Data registry — single source of truth for every dataset the platform knows about.

Design rules (evidence-first):
  * A dataset is analytically usable ONLY when status == AVAILABLE and
    analytical_eligible is True.
  * DEMO_ONLY data must never pass the analytical gate.
  * OFFICIAL_ACCESS_REQUIRED / DOCUMENT_ONLY / DATA_UNAVAILABLE are recorded
    honestly so the UI can show real gaps instead of fabricated values.

This project was scaffolded from scratch on 2026-09-08. Nothing has been
acquired to local storage yet, so most raster/official layers are
DATA_UNAVAILABLE or OFFICIAL_ACCESS_REQUIRED. The keyless public APIs
(Open-Meteo, OpenStreetMap / Overpass) are the only sources wired live.
"""
from __future__ import annotations

from enum import Enum
from typing import Optional


class Status(str, Enum):
    AVAILABLE = "AVAILABLE"                              # real data, usable now
    OFFICIAL_ACCESS_REQUIRED = "OFFICIAL_ACCESS_REQUIRED"  # exists, needs govt access
    DATA_UNAVAILABLE = "DATA_UNAVAILABLE"               # open source, not yet acquired
    DOCUMENT_ONLY = "DOCUMENT_ONLY"                     # PDF / text, not machine-readable
    DEMO_ONLY = "DEMO_ONLY"                             # synthetic sample, never analytical


# Status -> badge metadata consumed by the frontend registry page.
STATUS_META = {
    Status.AVAILABLE: {"label": "Available", "color": "#16a34a", "icon": "🟢"},
    Status.OFFICIAL_ACCESS_REQUIRED: {"label": "Official access required", "color": "#dc2626", "icon": "🔴"},
    Status.DATA_UNAVAILABLE: {"label": "Data unavailable", "color": "#64748b", "icon": "⚪"},
    Status.DOCUMENT_ONLY: {"label": "Document only", "color": "#ea580c", "icon": "🟠"},
    Status.DEMO_ONLY: {"label": "Demo only", "color": "#111827", "icon": "⚫"},
}


def _ds(
    dataset_id: str,
    name: str,
    category: str,
    status: Status,
    *,
    source: str,
    authority: str,
    acquisition_date: Optional[str] = None,
    last_updated: Optional[str] = None,
    license: str = "Unknown",
    limitations: str = "",
    acquisition: str = "",
    analytical_eligible: Optional[bool] = None,
) -> dict:
    """Build a registry record with complete provenance fields."""
    if analytical_eligible is None:
        analytical_eligible = status == Status.AVAILABLE
    return {
        "id": dataset_id,
        "name": name,
        "category": category,
        "status": status.value,
        "source": source,
        "authority": authority,
        "acquisition_date": acquisition_date,
        "last_updated": last_updated,
        "license": license,
        "limitations": limitations,
        "acquisition": acquisition,
        "analytical_eligible": bool(analytical_eligible),
    }


# --- The 26 core datasets --------------------------------------------------
DATASETS: list[dict] = [
    # --- Base / boundary ---
    _ds("madurai_boundary", "Madurai administrative boundary", "Boundary",
        Status.AVAILABLE,
        source="OpenStreetMap relation 11268397 (Madurai, admin_level 8)",
        authority="OpenStreetMap contributors",
        acquisition_date="2026-09-08",
        last_updated="2026-09-08",
        license="ODbL 1.0",
        limitations="Municipal Corporation boundary as mapped in OSM; not a "
                    "surveyed cadastral limit. Refresh with "
                    "scripts/fetch_boundary.py.",
        acquisition="scripts/fetch_boundary.py (Overpass).",
        analytical_eligible=True),

    # --- OpenStreetMap (keyless, live) ---
    _ds("osm_infrastructure", "OSM infrastructure (roads, health, education, transit)", "Infrastructure",
        Status.AVAILABLE,
        source="OpenStreetMap via Overpass API",
        authority="OpenStreetMap contributors",
        acquisition_date="live",
        last_updated="continuous",
        license="ODbL 1.0",
        limitations="Community-maintained; completeness varies by feature type "
                    "and locality. Not an authoritative asset register.",
        acquisition="Overpass API query, cached under backend/data/."),
    _ds("osm_hydrology", "OSM hydrology (rivers, canals, water bodies)", "Hydrology",
        Status.AVAILABLE,
        source="OpenStreetMap via Overpass API",
        authority="OpenStreetMap contributors",
        acquisition_date="live", last_updated="continuous",
        license="ODbL 1.0",
        limitations="Supplementary only. Does not replace WRD hydrology.",
        acquisition="Overpass API query."),
    _ds("osm_landuse", "OSM land use / land cover tags", "Land cover",
        Status.AVAILABLE,
        source="OpenStreetMap via Overpass API",
        authority="OpenStreetMap contributors",
        acquisition_date="live", last_updated="continuous",
        license="ODbL 1.0",
        limitations="Sparse and inconsistent tagging; not a classified raster.",
        acquisition="Overpass API query."),

    # --- Climate (Open-Meteo, keyless, live) ---
    _ds("open_meteo_climate", "Open-Meteo historical climate (2015–present)", "Climate",
        Status.AVAILABLE,
        source="Open-Meteo Archive API (ERA5 reanalysis)",
        authority="Open-Meteo / ECMWF ERA5",
        acquisition_date="live", last_updated="daily (~5-day lag)",
        license="CC-BY 4.0 (Open-Meteo); ERA5 Copernicus licence",
        limitations="~9 km reanalysis grid; local microclimate not resolved.",
        acquisition="HTTPS GET to archive-api.open-meteo.com, no key."),

    # --- Open EO / raster: not yet acquired locally ---
    _ds("copernicus_dem", "Copernicus DEM GLO-30 (elevation)", "Terrain",
        Status.DATA_UNAVAILABLE,
        source="Copernicus DEM GLO-30",
        authority="ESA / Copernicus",
        license="Copernicus free & open",
        limitations="Open data, acquisition to local storage still pending. "
                    "30 m posting; vertical accuracy ~4 m.",
        acquisition="AWS Open Data (copernicus-dem-30m) or OpenTopography API.",
        analytical_eligible=False),
    _ds("esri_lulc_2017", "Esri Global Land Cover 2017 (Sentinel-2 10 m)", "Land cover",
        Status.DATA_UNAVAILABLE,
        source="Esri / Impact Observatory / Sentinel-2",
        authority="Esri, Impact Observatory",
        license="CC-BY 4.0",
        limitations="Open data, not yet clipped/stored for Madurai.",
        acquisition="Esri Living Atlas ImageServer, export AOI.",
        analytical_eligible=False),
    _ds("esri_lulc_2024", "Esri Global Land Cover 2024 (Sentinel-2 10 m)", "Land cover",
        Status.DATA_UNAVAILABLE,
        source="Esri / Impact Observatory / Sentinel-2",
        authority="Esri, Impact Observatory",
        license="CC-BY 4.0",
        limitations="Open data, not yet clipped/stored for Madurai.",
        acquisition="Esri Living Atlas ImageServer, export AOI.",
        analytical_eligible=False),
    _ds("esa_worldcover_2021", "ESA WorldCover 2021 (10 m)", "Land cover",
        Status.DATA_UNAVAILABLE,
        source="ESA WorldCover",
        authority="ESA",
        license="CC-BY 4.0",
        limitations="Open data, acquisition pending. Cross-check layer only.",
        acquisition="AWS Open Data (esa-worldcover) tile S21E078.",
        analytical_eligible=False),
    _ds("sentinel2_imagery", "Sentinel-2 L2A surface reflectance", "Imagery",
        Status.DATA_UNAVAILABLE,
        source="Copernicus Sentinel-2",
        authority="ESA / Copernicus",
        license="Copernicus free & open",
        limitations="Open data; needs cloud-free scene selection and storage.",
        acquisition="Copernicus Data Space / Element84 Earth Search STAC.",
        analytical_eligible=False),
    _ds("ghsl_built_up", "GHSL built-up surface (GHS-BUILT-S)", "Built environment",
        Status.DATA_UNAVAILABLE,
        source="Global Human Settlement Layer",
        authority="European Commission JRC",
        license="CC-BY 4.0",
        limitations="Open data, acquisition pending.",
        acquisition="JRC GHSL download, tile for Madurai.",
        analytical_eligible=False),
    _ds("worldpop_population", "WorldPop population count (100 m)", "Population",
        Status.DATA_UNAVAILABLE,
        source="WorldPop",
        authority="WorldPop, University of Southampton",
        license="CC-BY 4.0",
        limitations="Modelled estimate, not a census. Acquisition pending.",
        acquisition="WorldPop REST API, IND 100 m constrained.",
        analytical_eligible=False),
    _ds("viirs_nightlights", "VIIRS night-time lights (monthly)", "Socio-economic proxy",
        Status.DATA_UNAVAILABLE,
        source="VIIRS DNB / Earth Observation Group",
        authority="NOAA / Colorado School of Mines",
        license="Public domain (US Govt)",
        limitations="Proxy only. Acquisition pending.",
        acquisition="EOG API monthly composites.",
        analytical_eligible=False),

    # --- Official / restricted (exist, need govt access) ---
    _ds("bhuvan_lulc", "Bhuvan LULC 50K", "Land cover",
        Status.OFFICIAL_ACCESS_REQUIRED,
        source="Bhuvan / NRSC",
        authority="National Remote Sensing Centre, ISRO",
        license="Restricted — registered access",
        limitations="Requires Bhuvan account and data request approval.",
        acquisition="bhuvan.nrsc.gov.in thematic services, formal request."),
    _ds("cadastral_geometry", "Cadastral parcel geometry", "Cadastre",
        Status.OFFICIAL_ACCESS_REQUIRED,
        source="Tamil Nadu Survey & Settlement Department",
        authority="TN Survey & Settlement / Registration Dept",
        license="Restricted — govt MoU",
        limitations="Not public. Requires data-sharing agreement.",
        acquisition="Formal request to TN Survey & Settlement Dept."),
    _ds("ownership_records", "Ownership / title records", "Cadastre",
        Status.OFFICIAL_ACCESS_REQUIRED,
        source="TN Registration Department (e-services)",
        authority="Inspector General of Registration, TN",
        license="Restricted — personal data",
        limitations="Personally identifiable; strict access controls apply.",
        acquisition="Govt MoU; anonymised extract only."),
    _ds("e_adangal", "e-Adangal / village accounts", "Land records",
        Status.OFFICIAL_ACCESS_REQUIRED,
        source="TN e-Adangal portal",
        authority="Commissionerate of Revenue Administration, TN",
        license="Restricted",
        limitations="Per-survey-number access, no bulk export.",
        acquisition="Revenue Dept data-sharing request."),
    _ds("tnsdma_flood_hazard", "Flood hazard / inundation zones", "Hazard",
        Status.OFFICIAL_ACCESS_REQUIRED,
        source="TN State Disaster Management Authority",
        authority="TNSDMA",
        license="Restricted",
        limitations="Not published as GIS; request required.",
        acquisition="Formal request to TNSDMA."),
    _ds("wrd_hydrology", "WRD hydrology / tank network", "Hydrology",
        Status.OFFICIAL_ACCESS_REQUIRED,
        source="TN Water Resources Department",
        authority="WRD, PWD Tamil Nadu",
        license="Restricted",
        limitations="Authoritative tank/anicut network; not public GIS.",
        acquisition="WRD data-sharing request."),
    _ds("nbsslup_soil", "Soil series / land capability", "Soil",
        Status.OFFICIAL_ACCESS_REQUIRED,
        source="NBSS&LUP",
        authority="ICAR — NBSS&LUP",
        license="Restricted — licensed product",
        limitations="1:50,000 soil maps sold under licence.",
        acquisition="Purchase / MoU with NBSS&LUP Nagpur."),
    _ds("tngis_crop_survey", "Digital crop survey", "Agriculture",
        Status.OFFICIAL_ACCESS_REQUIRED,
        source="TN Agriculture Dept / TNGIS",
        authority="Directorate of Agriculture, TN",
        license="Restricted",
        limitations="Season-wise, parcel-level; not public.",
        acquisition="Agriculture Dept data request."),
    _ds("cgwb_groundwater", "Groundwater level & quality (observation wells)", "Hydrogeology",
        Status.OFFICIAL_ACCESS_REQUIRED,
        source="Central Ground Water Board / TWAD",
        authority="CGWB, Ministry of Jal Shakti",
        license="Restricted — bulk; some station data public",
        limitations="Station-level public via India-WRIS; full series needs request.",
        acquisition="India-WRIS API (partial) or CGWB request (full)."),

    # --- Document-only ---
    _ds("master_plan", "Madurai Master Plan / Second Master Plan", "Planning",
        Status.DOCUMENT_ONLY,
        source="Madurai Local Planning Authority / DTCP",
        authority="Directorate of Town & Country Planning, TN",
        license="Public document",
        limitations="PDF maps and text; zoning not digitised as GIS.",
        acquisition="DTCP published master plan PDFs."),
    _ds("tncdbr_regulations", "TN Combined Development & Building Rules", "Regulation",
        Status.DOCUMENT_ONLY,
        source="TCP Act / TNCDBR 2019 gazette",
        authority="Housing & Urban Development Dept, TN",
        license="Public document",
        limitations="Legal text; must be encoded into rules manually.",
        acquisition="Gazette notification PDF."),
    _ds("tn_agricultural_stats", "TN Season & Crop Report / agricultural statistics", "Agriculture",
        Status.DOCUMENT_ONLY,
        source="Dept of Economics & Statistics, TN",
        authority="DES, Government of Tamil Nadu",
        license="Public document",
        limitations="District/taluk tables in PDF; no parcel detail.",
        acquisition="DES published season & crop reports."),

    # --- Demo (never analytical) ---
    _ds("demo_cadastral_grid", "DEMO DATA — sample digital cadastral grid", "Demo",
        Status.DEMO_ONLY,
        source="Synthetic — generated by this platform",
        authority="None (illustrative only)",
        last_updated="2026-09-08",
        license="N/A — synthetic",
        limitations="Fabricated regular grid for UI demonstration. MUST NOT be "
                    "used for analysis, evidence, or any decision. Excluded from "
                    "the evidence engine and all analytics.",
        acquisition="Generated on demand.",
        analytical_eligible=False),
]

_BY_ID = {d["id"]: d for d in DATASETS}

assert len(DATASETS) == 26, f"expected 26 datasets, found {len(DATASETS)}"


# --- Public API ----------------------------------------------------------
def list_datasets(status: Optional[str] = None, category: Optional[str] = None) -> list[dict]:
    rows = DATASETS
    if status:
        rows = [d for d in rows if d["status"] == status]
    if category:
        rows = [d for d in rows if d["category"].lower() == category.lower()]
    return rows


def get_dataset(dataset_id: str) -> Optional[dict]:
    return _BY_ID.get(dataset_id)


def can_use_for_analysis(dataset_id: str) -> bool:
    """The analytical gate. True only for real, analytically-eligible data."""
    d = _BY_ID.get(dataset_id)
    if d is None:
        return False
    return d["status"] == Status.AVAILABLE.value and d["analytical_eligible"] is True


def summary() -> dict:
    counts: dict[str, int] = {}
    for d in DATASETS:
        counts[d["status"]] = counts.get(d["status"], 0) + 1
    analytical = [d["id"] for d in DATASETS if can_use_for_analysis(d["id"])]
    return {
        "total": len(DATASETS),
        "by_status": counts,
        "status_meta": {s.value: STATUS_META[s] for s in Status},
        "analytically_usable": analytical,
        "analytically_usable_count": len(analytical),
    }
