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
    city: Optional[str] = None,
    state: Optional[str] = None,
) -> dict:
    """Build a registry record with complete provenance fields.

    `city` ties a dataset to one prototype area (services/cities.py) — use it
    for things that are genuinely per-place, like an administrative boundary
    or a town's own master plan.
    `state` ties a dataset to a STATE government authority shared by every
    prototype city in that state (TN Survey & Settlement, TNSDMA, …) — use it
    instead of `city` so e.g. Madurai and Kovilpatti (both Tamil Nadu) reuse
    the one real dataset rather than duplicating it under a second city tag.
    National-body datasets (CGWB, NBSS&LUP, ISRO, Esri, …) leave both None.
    """
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
        "city": city,
        "state": state,
    }


# --- The 42 core datasets --------------------------------------------------
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
        analytical_eligible=True, city="madurai"),
    _ds("bhopal_boundary", "Bhopal administrative boundary", "Boundary",
        Status.AVAILABLE,
        source="OpenStreetMap relation 1976080 (Bhopal, admin_level 5)",
        authority="OpenStreetMap contributors",
        acquisition_date="2026-09-18",
        last_updated="2026-09-18",
        license="ODbL 1.0",
        limitations="This is the Bhopal DISTRICT boundary (admin_level 5) — "
                    "OSM has no separately mapped Bhopal Municipal Corporation "
                    "relation. It is wider than the built-up city; the "
                    "platform's AOI/city-core for evidence lookups is scoped "
                    "tighter than the full district. Refresh with "
                    "scripts/fetch_boundary.py.",
        acquisition="scripts/fetch_boundary.py bhopal (Overpass).",
        analytical_eligible=True, city="bhopal"),
    _ds("kovilpatti_boundary", "Kovilpatti administrative boundary", "Boundary",
        Status.AVAILABLE,
        source="OpenStreetMap relation 10311689 (Kovilpatti, admin_level 6)",
        authority="OpenStreetMap contributors",
        acquisition_date="2026-09-18",
        last_updated="2026-09-18",
        license="ODbL 1.0",
        limitations="This is the Kovilpatti TALUK/DIVISION boundary "
                    "(admin_level 6) — OSM has no separately mapped Kovilpatti "
                    "Municipality relation (the municipal limits are ~6.5 km², "
                    "per thoothukudi.nic.in, far smaller than this taluk). The "
                    "platform's AOI/city-core for evidence lookups is scoped "
                    "to the town, not the full taluk. Refresh with "
                    "scripts/fetch_boundary.py.",
        acquisition="scripts/fetch_boundary.py kovilpatti (Overpass).",
        analytical_eligible=True, city="kovilpatti"),

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

    # --- Live weather (keyless, refreshed every 10 min) ---
    _ds("open_meteo_forecast", "Open-Meteo current weather & 7-day forecast", "Climate",
        Status.AVAILABLE,
        source="Open-Meteo Forecast API (best-match NWP: ECMWF IFS, GFS, ICON …)",
        authority="Open-Meteo; national weather-service models",
        acquisition_date="live", last_updated="every 15 minutes",
        license="CC-BY 4.0 (Open-Meteo)",
        limitations="Model analysis/forecast on a ~9–25 km grid, not a "
                    "thermometer at the site. Cross-checked against the nearest "
                    "airport METAR observation where one exists.",
        acquisition="HTTPS GET to api.open-meteo.com/v1/forecast, no key."),
    _ds("awc_metar", "Airport weather observations (METAR)", "Climate",
        Status.AVAILABLE,
        source="NOAA Aviation Weather Center METAR API",
        authority="NOAA AWC; observations by the India Meteorological Department "
                  "at airport stations",
        acquisition_date="live", last_updated="every 30–60 minutes",
        license="US Government public domain",
        limitations="A MEASURED reading, but at the nearest airport — which "
                    "may be tens of km from the site and at a different "
                    "elevation. Shown with its distance and age.",
        acquisition="HTTPS GET to aviationweather.gov/api/data/metar, no key."),

    _ds("openaq_stations", "Air-quality monitoring stations (CPCB / SPCB via OpenAQ)", "Environment",
        Status.AVAILABLE,
        source="OpenAQ API v3 (aggregating CPCB CAAQMS and state board monitors)",
        authority="Central Pollution Control Board / State Pollution Control Boards; "
                  "aggregated by OpenAQ",
        acquisition_date="live", last_updated="hourly (station dependent)",
        license="CC-BY 4.0 (OpenAQ); source-agency terms apply",
        limitations="MEASURED station data, but only where a monitor exists (most "
                    "are in city centres). Needs a free OpenAQ API key in the "
                    "OPENAQ_API_KEY environment variable — without it the source is "
                    "skipped and the page says so.",
        acquisition="HTTPS GET to api.openaq.org/v3 with X-API-Key."),

    _ds("esri_lulc_timeseries", "Sentinel-2 10 m land cover, 2017–2025 (live point sampling)", "Land cover",
        Status.AVAILABLE,
        source="Esri Living Atlas ImageServer — Sentinel-2 10 m Land Use/Land Cover time series",
        authority="Esri, Impact Observatory, Microsoft; imagery ESA Copernicus Sentinel-2",
        acquisition_date="live", last_updated="annual (2017–2025)",
        license="CC-BY 4.0",
        limitations="Machine-learning classification (~85% overall accuracy per the "
                    "producers) — small plots, shade and mixed pixels can be "
                    "mis-classed. Sampled live at a 7x7 point grid around a location; "
                    "the full rasters for map layers (esri_lulc_2017 / 2024) are "
                    "still pending local acquisition.",
        acquisition="HTTPS getSamples on ic.imagery1.arcgis.com, no key."),

    # --- Point-sampled open APIs (keyless, live, cached per ~100 m) ---
    _ds("open_meteo_elevation", "Copernicus DEM GLO-90 elevation (via Open-Meteo)", "Terrain",
        Status.AVAILABLE,
        source="Open-Meteo Elevation API (Copernicus DEM GLO-90)",
        authority="ESA / Copernicus; served by Open-Meteo",
        acquisition_date="live", last_updated="static DEM (2021 release)",
        license="Copernicus free & open; CC-BY 4.0 (Open-Meteo)",
        limitations="90 m posting — slope is computed over ~100 m and smooths "
                    "small banks, bunds and cuttings. Surface model: includes "
                    "buildings and tree canopy. The 30 m GLO-30 upgrade "
                    "(copernicus_dem) is still pending local acquisition.",
        acquisition="HTTPS GET to api.open-meteo.com/v1/elevation, no key."),
    _ds("soilgrids", "ISRIC SoilGrids 2.0 (250 m modelled soil properties)", "Soil",
        Status.AVAILABLE,
        source="ISRIC SoilGrids REST API v2.0",
        authority="ISRIC — World Soil Information",
        acquisition_date="live", last_updated="SoilGrids 2.0 (2020)",
        license="CC-BY 4.0",
        limitations="Global machine-learning MODEL at 250 m, not a field soil "
                    "survey; masks built-up land (no values in dense urban "
                    "cells). Gives texture / pH / carbon, NOT a land-capability "
                    "class — the official NBSS&LUP survey remains a gap.",
        acquisition="HTTPS GET to rest.isric.org/soilgrids/v2.0, no key."),
    _ds("open_meteo_air_quality", "CAMS air quality (via Open-Meteo)", "Environment",
        Status.AVAILABLE,
        source="Open-Meteo Air Quality API (CAMS global forecast/analysis)",
        authority="ECMWF Copernicus Atmosphere Monitoring Service; served by Open-Meteo",
        acquisition_date="live", last_updated="hourly",
        license="Copernicus licence; CC-BY 4.0 (Open-Meteo)",
        limitations="~45 km global model grid — a regional background level, "
                    "not a street-level monitor reading. CPCB station data is "
                    "authoritative where a station exists.",
        acquisition="HTTPS GET to air-quality-api.open-meteo.com, no key."),
    _ds("nominatim_geocoding", "OSM Nominatim reverse geocoding (locality)", "Base",
        Status.AVAILABLE,
        source="Nominatim (OpenStreetMap) reverse geocoder",
        authority="OpenStreetMap contributors / OSMF",
        acquisition_date="live", last_updated="continuous",
        license="ODbL 1.0",
        limitations="Names the nearest mapped OSM address objects; ward / "
                    "village names are as mapped, not an official revenue "
                    "village lookup. Rate-limited (1 req/s), cached.",
        acquisition="HTTPS GET to nominatim.openstreetmap.org/reverse."),
    _ds("osm_amenities", "OSM everyday amenities (banks, shops, transit, …)", "Infrastructure",
        Status.AVAILABLE,
        source="OpenStreetMap via Overpass API",
        authority="OpenStreetMap contributors",
        acquisition_date="live", last_updated="continuous",
        license="ODbL 1.0",
        limitations="Community-mapped; Indian towns are under-mapped for shops "
                    "and bus stops, so a low count can mean 'not mapped', not "
                    "'absent'.",
        acquisition="Overpass API query per city AOI, cached under backend/data/."),

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
        acquisition="Formal request to TN Survey & Settlement Dept.",
        state="Tamil Nadu"),
    _ds("mp_cadastral_geometry", "Cadastral parcel geometry", "Cadastre",
        Status.OFFICIAL_ACCESS_REQUIRED,
        source="Madhya Pradesh Revenue Department — Land Records (Bhu-Abhilekh)",
        authority="MP Revenue Dept (landrecords.mp.gov.in)",
        license="Restricted — govt MoU",
        limitations="Not public as bulk GIS. Requires data-sharing agreement.",
        acquisition="Formal request to MP Revenue Dept, Bhu-Abhilekh cell.",
        state="Madhya Pradesh"),
    _ds("ownership_records", "Ownership / title records", "Cadastre",
        Status.OFFICIAL_ACCESS_REQUIRED,
        source="TN Registration Department (e-services)",
        authority="Inspector General of Registration, TN",
        license="Restricted — personal data",
        limitations="Personally identifiable; strict access controls apply.",
        acquisition="Govt MoU; anonymised extract only.",
        state="Tamil Nadu"),
    _ds("mp_ownership_records", "Ownership / title records", "Cadastre",
        Status.OFFICIAL_ACCESS_REQUIRED,
        source="MP Department of Registration & Stamps (IGRS / SAMPADA)",
        authority="Inspector General of Registration, Madhya Pradesh",
        license="Restricted — personal data",
        limitations="Personally identifiable; strict access controls apply.",
        acquisition="Govt MoU; anonymised extract only.",
        state="Madhya Pradesh"),
    _ds("e_adangal", "e-Adangal / village accounts", "Land records",
        Status.OFFICIAL_ACCESS_REQUIRED,
        source="TN e-Adangal portal",
        authority="Commissionerate of Revenue Administration, TN",
        license="Restricted",
        limitations="Per-survey-number access, no bulk export.",
        acquisition="Revenue Dept data-sharing request.",
        state="Tamil Nadu"),
    _ds("tnsdma_flood_hazard", "Flood hazard / inundation zones", "Hazard",
        Status.OFFICIAL_ACCESS_REQUIRED,
        source="TN State Disaster Management Authority",
        authority="TNSDMA",
        license="Restricted",
        limitations="Not published as GIS; request required.",
        acquisition="Formal request to TNSDMA.",
        state="Tamil Nadu"),
    _ds("mpsdma_flood_hazard", "Flood hazard / inundation zones", "Hazard",
        Status.OFFICIAL_ACCESS_REQUIRED,
        source="Madhya Pradesh State Disaster Management Authority",
        authority="MPSDMA",
        license="Restricted",
        limitations="Not published as GIS; request required.",
        acquisition="Formal request to MPSDMA.",
        state="Madhya Pradesh"),
    _ds("wrd_hydrology", "WRD hydrology / tank network", "Hydrology",
        Status.OFFICIAL_ACCESS_REQUIRED,
        source="TN Water Resources Department",
        authority="WRD, PWD Tamil Nadu",
        license="Restricted",
        limitations="Authoritative tank/anicut network; not public GIS.",
        acquisition="WRD data-sharing request.",
        state="Tamil Nadu"),
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
        acquisition="Agriculture Dept data request.",
        state="Tamil Nadu"),
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
        acquisition="DTCP published master plan PDFs.",
        city="madurai"),
    _ds("kovilpatti_master_plan", "Kovilpatti GIS Master Plan (AMRUT 2.0)", "Planning",
        Status.DATA_UNAVAILABLE,
        source="Directorate of Town & Country Planning, Tamil Nadu",
        authority="DTCP, Government of Tamil Nadu",
        license="Public document (once published)",
        limitations="Kovilpatti's GIS-based master plan (~135.85 km² planning "
                    "area, AMRUT 2.0 Package 3) is still IN PREPARATION as of "
                    "this build — not yet published, unlike Madurai's approved "
                    "Second Master Plan. No statutory zoning document exists "
                    "to acquire yet.",
        acquisition="Watch tcp.tn.gov.in/masterplans for publication.",
        analytical_eligible=False, city="kovilpatti"),
    _ds("bhopal_master_plan", "Bhopal Development Plan 2031", "Planning",
        Status.DOCUMENT_ONLY,
        source="Directorate of Town & Country Planning, Madhya Pradesh",
        authority="Urban Development & Housing Dept, MP (DT&CP)",
        license="Public document",
        limitations="PDF maps and text (BDP 2031); zoning not digitised as GIS.",
        acquisition="DT&CP MP published Bhopal Development Plan PDFs.",
        city="bhopal"),
    _ds("tncdbr_regulations", "TN Combined Development & Building Rules", "Regulation",
        Status.DOCUMENT_ONLY,
        source="TCP Act / TNCDBR 2019 gazette",
        authority="Housing & Urban Development Dept, TN",
        license="Public document",
        limitations="Legal text; must be encoded into rules manually.",
        acquisition="Gazette notification PDF.",
        state="Tamil Nadu"),
    _ds("tn_agricultural_stats", "TN Season & Crop Report / agricultural statistics", "Agriculture",
        Status.DOCUMENT_ONLY,
        source="Dept of Economics & Statistics, TN",
        authority="DES, Government of Tamil Nadu",
        license="Public document",
        limitations="District/taluk tables in PDF; no parcel detail.",
        acquisition="DES published season & crop reports.",
        state="Tamil Nadu"),

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

assert len(DATASETS) == 42, f"expected 42 datasets, found {len(DATASETS)}"


def _applies_to_city(d: dict, city: str, state: Optional[str]) -> bool:
    """A dataset applies to a queried city if it's tied to that exact city
    (a boundary, a town's own master plan, …), tied to that city's STATE (a
    state-government authority shared by every city there), or tied to
    neither (a national body — CGWB, NBSS&LUP, ISRO, Esri, OSM, …)."""
    if d["city"] is not None:
        return d["city"] == city
    if d["state"] is not None:
        return d["state"] == state
    return True


# --- Public API ----------------------------------------------------------
def list_datasets(status: Optional[str] = None, category: Optional[str] = None,
                  city: Optional[str] = None) -> list[dict]:
    rows = DATASETS
    if status:
        rows = [d for d in rows if d["status"] == status]
    if category:
        rows = [d for d in rows if d["category"].lower() == category.lower()]
    if city:
        from services import cities as city_registry
        cfg = city_registry.get_city(city)
        state = cfg["state"] if cfg else None
        rows = [d for d in rows if _applies_to_city(d, city, state)]
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
