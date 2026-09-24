# Handoff — National Digital Platform (Madurai · Bhopal · Kovilpatti prototypes)

Snapshot for continuing in a fresh chat. Last commit: `d678392` (everything
below this line in git history is uncommitted working-tree state as of
2026-09-18 — see `git status` before assuming it's landed).

## What this is

Evidence-first national digital platform for land governance & research.
Three prototype areas of interest, each a real place with a real state
government behind it: **Madurai, Tamil Nadu**; **Bhopal, Madhya Pradesh**;
**Kovilpatti, Tamil Nadu**. Core rule: **report only what real data
substantiates; name every gap; never fabricate — including in the platform's
own metadata** (dataset authority names are web-verified before being
written, not guessed). Descriptive only — no prediction yet.

Path: `C:\Users\Abhinav\Downloads\backup\SIH-prototype` · git branch `master`
(main branch for PRs is `main`).

## Stack & layout

```
backend/   FastAPI (Python 3.12, venv at backend/.venv  ← note the dot)
  main.py               app + CORS + startup warm-up thread (warms all cities)
  routers/             data_registry, quality, evidence, analytics, gis
  services/
    cities.py           the city registry — id/label/state/aoi/city_core/
                        cadastral_patch/boundary file per prototype city.
                        Add a city here + fetch its boundary; nowhere else
                        hard-codes "madurai".
    data_registry.py   33 datasets, provenance, the analytical gate.
                        Each dataset carries `city` (genuinely per-place,
                        e.g. a boundary or a town's own master plan) XOR
                        `state` (a state-authority shared by every prototype
                        city there, e.g. TN Survey & Settlement) XOR neither
                        (a national body). See _applies_to_city().
    evidence_engine.py  resolves lat/lon -> city via cities.py, then climate
                        (Open-Meteo/ERA5) + infra distances (per-city cache)
                        + gaps (_NATIONAL_GAPS + _STATE_GAPS[state] +
                        _CITY_GAPS[city]) + report/exports
    site_context.py     water / land-use / development from cached PER-CITY
                        AOI GeoJSON (fast, no live Overpass). Takes a `city`
                        arg — this bit it before (see Gotchas).
    cadastral_demo.py   synthetic parcel fabric for the Explorer "demo"
                        layer — randomised recursive split, real geodesic
                        area. DEMO_ONLY, excluded from the analytical gate.
    land_profile.py     the plain-language OUTCOME layer behind Land
                        Intelligence: per-facility access scores (platform's
                        own reference bands, stated as such), comparison vs a
                        12x12 sample grid over the city core (per-city,
                        cached, warmed at startup), an INDICATIVE use-fit
                        screen (each fit lists the open checks it needs), and
                        evidence coverage. POST /evidence/land-profile.
    land_details.py     extra VERIFIED point facts from keyless APIs, each
                        registry-gated, cached per point, one retry, gap on
                        failure: terrain (Copernicus DEM GLO-90 via Open-Meteo
                        Elevation: elevation, slope, aspect, position vs 1 km
                        ring, 2 km W-E/S-N profiles), soil (ISRIC SoilGrids
                        250 m MODEL — masks built-up land, so city points are
                        a gap), air quality (CAMS via Open-Meteo, 12-month
                        PM2.5/PM10 vs NAAQS 2009 + WHO 2021), locality
                        (Nominatim). Fetched in parallel by evidence_engine.
                        Climate now also carries monthly normals, rain by
                        year, days >= 40 C and solar kWh/m2/day.
    pdf_report.py       reportlab A4 "Land Profile" PDF (gauge, comparison
                        chart, use-fit chart, open checks) — what
                        /evidence/export/pdf returns; falls back to the old
                        plain-text PDF if reportlab is missing.
    feature_engineering.py / suitability.py   partial-by-design; refuse to
                        score w/o terrain+LULC
    geo.py             haversine / point-in-polygon / min-distance
    overpass.py        mirror-aware Overpass client (3 endpoints, retries)
  scripts/fetch_boundary.py   fetch/refresh a city's real OSM boundary —
                        takes a city id arg: `python scripts/fetch_boundary.py bhopal`
  data/                 {madurai,bhopal,kovilpatti}_boundary_clean.geojson
                        (tracked); osm_{infrastructure,hydrology,landuse}_{city}.geojson
                        + *_cache.json (gitignored, runtime, per-city)
  tests/               71 pytest cases  (python -m pytest)
frontend/  React 18 + Vite + Leaflet + react-router 6
  src/App.jsx          "/" = LandingPage ; "/app/*" = Layout shell + pages
  src/components/       Layout, MapView (city-aware, re-centers per city),
                       SiteContext, Bits, ErrorBoundary, CustomCursor,
                       Reveal (scroll-reveal wrapper, optional tilt)
  src/hooks/            useAsync, useReveal (IntersectionObserver), useTilt
                       (cursor-tracked 3D tilt, pointer:fine gated)
  src/pages/            Landing, Dashboard, Explorer (city switcher),
                       Intelligence, History, Climate, DataRegistry,
                       DataQuality, OfficialDataAccess
  src/services/api.js  thin fetch client, base "/api/v1", every gis.* call
                       takes a city param (default "madurai")
  src/index.css        light warm-neutral theme + dark sidebar (two-tone),
                       terracotta brand accent, custom-cursor rules,
                       .reveal/.reveal.in (GLOBAL, not landing-scoped)
  public/madurai-hero.jpg   real Esri World Imagery capture of the Madurai
                       AOI, used as the landing hero background
.claude/launch.json    backend + frontend dev configs
run.ps1                starts both
```

## Run

```powershell
# backend  (venv is .venv WITH a dot)
cd C:\Users\Abhinav\Downloads\backup\SIH-prototype\backend
.\.venv\Scripts\python.exe -m uvicorn main:app --port 8000        # do NOT use --reload here (orphans a python3.13.exe child on the port)
.\.venv\Scripts\python.exe -m pytest -q

# frontend
cd C:\Users\Abhinav\Downloads\backup\SIH-prototype\frontend
npm run dev            # :5173, proxies /api -> :8000
npm run build          # sanity check

# or both:
C:\Users\Abhinav\Downloads\backup\SIH-prototype\run.ps1
```

Kill a stuck backend (the Store Python runs as `python3.13.exe`, and
`--reload` children have no "uvicorn" in their cmdline, so match by port):

```powershell
Get-NetTCPConnection -LocalPort 8000 -State Listen | ForEach-Object { Stop-Process -Id $_.OwningProcess -Force }
Get-Process | Where-Object { $_.ProcessName -like 'python*' } | Stop-Process -Force
```

## Data registry (33 datasets) — current statuses

AVAILABLE 7 · DATA_UNAVAILABLE 9 · OFFICIAL_ACCESS_REQUIRED 12 ·
DOCUMENT_ONLY 4 · DEMO_ONLY 1

Analytically usable now: `madurai_boundary`, `bhopal_boundary`,
`kovilpatti_boundary`, `osm_infrastructure`, `osm_hydrology`, `osm_landuse`,
`open_meteo_climate`. Everything else is a declared gap with an
`acquisition` path. The gate is `status == AVAILABLE and analytical_eligible`.
Quality audit proves no DEMO_ONLY dataset can pass it (33/33 pass, no leak).

State-shared vs per-city datasets (see `services/data_registry.py::_ds`):
Madurai and Kovilpatti (both Tamil Nadu) share `cadastral_geometry`,
`ownership_records`, `tnsdma_flood_hazard`, `wrd_hydrology`,
`tngis_crop_survey`, `tncdbr_regulations`, `tn_agricultural_stats` — real TN
state bodies, not duplicated per town. Bhopal has its own Madhya Pradesh
counterparts (`mp_cadastral_geometry`, `mp_ownership_records`,
`mpsdma_flood_hazard`). Each town's master plan is genuinely per-city
(`master_plan`, `bhopal_master_plan`, `kovilpatti_master_plan`) since each
is a different real document with a different publication status —
Kovilpatti's GIS master plan is still in preparation (AMRUT 2.0), so that
one is `DATA_UNAVAILABLE`, not `DOCUMENT_ONLY` like the other two.

## Key architecture notes

- **City registry (`services/cities.py`).** Every prototype city's AOI,
  tighter `city_core`, and an even tighter `cadastral_patch` (~one street
  block, for the demo cadastral fabric — NOT the same as city_core; using
  the full core there once produced 2.3-million-m² "parcels", see Phase 8 in
  PHASE-STATUS.md). `resolve_city_for_point(lat, lon)` is how
  `evidence_engine.validate_coordinate` figures out which city a coordinate
  belongs to; `evidence.py`/`analytics.py` needed no signature changes
  since they already passed lat/lon through generically.
- **AOI-cache pattern, now per city.** The three OSM layers are fetched once
  per city (Overpass is slow: 60–180 s), cached to
  `backend/data/osm_*_{city}.geojson`, warmed by a startup thread for every
  city in the registry, refreshed weekly. `evidence_engine` and
  `site_context` compute everything **locally** from those files —
  endpoints respond in ~0.3 s. Never add a live Overpass call on a request
  path. **`site_context.py` takes an explicit `city` arg and reads the
  suffixed cache file** — it did not always (see Gotchas).
- **Climate cache**: in-process, keyed by ~1 km rounded coord — genuinely
  city-agnostic, needed no changes when cities were added.
- Evidence `/report` does NOT include site context (opt-in flag); the
  frontend calls `/evidence/site-context` separately with its own loading
  state.
- Boundaries are real OSM relations, but at whatever admin level OSM
  actually has — **not always the tight municipal one**: Madurai got its
  real Corporation boundary (admin_level 8, relation 11268397); Bhopal and
  Kovilpatti have no municipal-level relation in OSM, so they fell back to
  district (relation 1976080, admin_level 5) and taluk (relation 10311689,
  admin_level 6) respectively. The registry `limitations` field says so
  honestly for each — never silently upgrades "biggest polygon found" to
  "municipal boundary."

## What's done

- Phases 1–9 — see `docs/PHASE-STATUS.md` for the detailed checklist.
  Phases 1–7 were the original from-scratch build (scaffold, registry,
  evidence engine, map layers, feature engineering, suitability framework,
  integration + tests). Phase 8 was a full UI redesign (light/dark two-tone
  theme, real-satellite-photo hero with parallax, global scroll-reveal,
  cursor-tilt 3D touches, custom cursor) plus the first multi-city expansion
  (Bhopal). Phase 9 added Kovilpatti and forced a `city` → `state` dataset
  tagging correction so same-state cities share real datasets instead of
  duplicating them.
- Site character: water (nearest river/tank/canal + counts + inland note),
  land use (agri vs built, point-in-polygon over OSM landuse), development
  level (OSM landuse + road proxy) — all now city-aware.
- Explorer: base-map switcher (OSM / Esri Satellite / Light / Dark / HOT),
  a **city switcher** (Madurai / Bhopal / Kovilpatti, re-centers the map and
  re-fetches every layer), hydrology + land-use overlays, an upgraded demo
  cadastral layer (irregular parcels, real computed area, click-to-inspect),
  legend, POI markers zoom-gated at ≥13 with white halos, split
  hospital/clinic/school/college colours, popups with real name + raw OSM
  tag + `openstreetmap.org` verify link.
- Landing page at `/` — real satellite-photo hero (parallax, rounded panel,
  bottom fade), scroll-reveal pipeline/stats/checks/governance sections,
  tilt-on-hover cards. App shell under `/app/*`, now with a custom cursor
  (terracotta dot + blend-mode ring, `pointer:fine` gated) across the whole
  app.
- External per-point links: OSM, Google Maps, Google Street View, Mapillary,
  Bhuvan.

## Not done / next

- **Acquire the open rasters** (user deferred): Copernicus DEM GLO-30 and
  Esri Global Land Cover 2017 + 2024 → store under `backend/data/`, flip the
  registry statuses to AVAILABLE/eligible, **per city**. `rasterio` +
  `numpy` are already in the venv. The terrain/LULC extractors in
  `feature_engineering.py` and the suitability scoring already thread a
  `city` arg through and are gate-checked — they light up automatically
  once the data + a sampler exist.
- Certainty ("How sure are we?", 36% -> ~61-67%): live Sentinel-2 10 m land
  cover 2017-2025 (dataset esri_lulc_timeseries, 7x7 getSamples per year)
  closes land_cover_class + land_cover_change; flood SCREENING (terrain +
  mapped water + satellite water years) is its own verified topic while the
  official flood_hazard gap stays open; SoilGrids falls back to open ground
  1.5 km away for built-up points; every verified topic carries an evidence
  kind (Satellite / Reanalysis / Model / Derived / Community-mapped) and
  OSM-vs-satellite cross-checks are reported (satellite wins on conflict via
  land_profile.effective_development). Live sources share a 15 s deadline in
  evidence_engine; a late one (usually SoilGrids) shows as "fetching" and
  fills its cache in the background.
- Live air: services/live_air.py, GET /evidence/live-air — CAMS pollutants +
  Indian National AQI computed with CPCB breakpoints; optional MEASURED
  CPCB/SPCB station readings via OpenAQ when the OPENAQ_API_KEY env var is
  set (dataset openaq_stations, off and labelled as such without a key).
- Registry is now 42 datasets (+ esri_lulc_timeseries) (+ open_meteo_forecast & awc_metar for the
  live-weather panel — services/live_weather.py, GET /evidence/live-weather,
  10-min cache, model value cross-checked against the nearest airport METAR;
  + open_meteo_elevation, soilgrids,
  open_meteo_air_quality, nominatim_geocoding, osm_amenities). The
  terrain_elevation_slope gap is dropped from a report only when GLO-90
  terrain actually verified for that point; nbsslup_soil stays a gap
  (SoilGrids is a model, not a capability survey).
- `osm_amenities_{city}.geojson` (gitignored) is a 4th per-city Overpass
  layer, warmed at startup — Madurai/Bhopal take ~5 min each to build.
- A first Land Intelligence lookup for a new point is ~7-10 s (five live
  APIs in parallel); repeats are instant from the in-process caches.
- Land profile access bands / use-fit weights are hand-set, transparent
  and documented in `land_profile.py`, but not calibrated against anything
  yet. Once terrain + LULC land, fold them into the use-fit factors (and
  the flood/zoning checks will still gate any real decision).
- Two-stack dev: `.claude/launch.json` also has `backend-alt` (:8001) and
  `frontend-alt` (:5174, proxies to :8001 via the API_TARGET env var in
  vite.config.js) for when another session already holds :8000/:5173.
- No automated frontend tests (only `npm run build` + manual click-through
  via the browser preview tool this session).
- Phase 6F-3+ (spatial suitability application, historical validation, then
  prediction, then policy simulation) — per the plan, do NOT build
  prediction before historical validation.
- A fourth city would be free architecturally (add one `cities.py` entry +
  fetch its boundary) *except* for the state-authority datasets: a city in
  a THIRD state still needs its own web-verified `state=`-tagged entries
  (cadastral/ownership/flood/etc.) the way Bhopal got Madhya Pradesh's —
  never assume another state's department names carry over.
- OSM data caveats surfaced but not curated: e.g. `amenity=hospital` in OSM
  includes a veterinary hospital near Madurai; `amenity=clinic` covers
  single doctor practices. The UI labels these honestly and links to OSM to
  fix.

## Gotchas

- venv dir is `.venv` (dot).
- Don't run uvicorn with `--reload` from a plain terminal in this
  environment — it can orphan a child holding port 8000. (The Claude Code
  browser-preview tool's own dev-server launcher handles this fine and was
  used throughout this session with `--reload` active.)
- Overpass public endpoints are slow/rate-limited; first cache build of a
  layer can take 1–3 min per city. `overpass.py` already rotates mirrors.
- **`site_context.py` must take a `city` arg and read the per-city cache
  file.** It didn't for a while during the Bhopal work — silently fell back
  to reading un-suffixed filenames left over from before the multi-city
  refactor, so a Bhopal point got Madurai's cached water/land-use data.
  Caught by manual testing, not the automated suite; there's now a
  regression test (`test_site_context_uses_the_right_citys_cache`) but if
  you add a fourth city, manually spot-check its Land Intelligence page
  too, not just `pytest`.
- When adding a city in a state that already has entries (Tamil Nadu), tag
  the shared authority datasets with `state=`, not `city=` — see the Phase 9
  note in PHASE-STATUS.md for exactly what broke when this wasn't done.
- Boundary fetches don't always get the tight administrative level you
  want — check what `scripts/fetch_boundary.py <city>` actually found
  (prints the relation id and admin_level) before writing the registry
  `limitations` text; don't assume it's municipal-level.
- In the Claude Code browser pane, screenshots can come back blank or show
  a stale/partially-composited frame right after a scroll or a dev-server
  reload — this is a pane rendering artifact, not a real bug. Verify with
  `get_page_text` / `read_page` / direct `javascript_tool` DOM queries
  before concluding something is broken, especially right after an edit
  that triggers `--reload`.
- LF→CRLF git warnings on Windows are harmless.
