# Handoff — National Digital Platform (Madurai prototype)

Snapshot for continuing in a fresh chat. Last commit: `53e1cc1`.

## What this is

Evidence-first national digital platform for land governance & research.
Prototype AOI: **Madurai, Tamil Nadu**. Core rule: **report only what real data
substantiates; name every gap; never fabricate.** Descriptive only — no
prediction yet.

Path: `C:\Users\Abhinav\Documents\SIH-prototype` · git branch `master`
(main branch for PRs is `main`) · git user `abhinav_20xx`.

## Stack & layout

```
backend/   FastAPI (Python 3.13, venv at backend/.venv  ← note the dot)
  main.py               app + CORS + startup warm-up thread
  routers/             data_registry, quality, evidence, analytics, gis
  services/
    data_registry.py   26 datasets, provenance, the analytical gate
    evidence_engine.py  climate (Open-Meteo/ERA5) + infra distances + gaps + report/exports
    site_context.py     water / land-use / development from cached AOI GeoJSON (fast, no live Overpass)
    feature_engineering.py / suitability.py   partial-by-design; refuse to score w/o terrain+LULC
    geo.py             haversine / point-in-polygon / min-distance
    overpass.py        mirror-aware Overpass client (3 endpoints, retries)
  scripts/fetch_boundary.py   refresh the real OSM boundary
  data/                madurai_boundary_clean.geojson (tracked);
                       osm_infrastructure/hydrology/landuse.geojson + *_cache.json (gitignored, runtime)
  tests/               33 pytest cases  (python -m pytest)
frontend/  React 18 + Vite + Leaflet + react-router 6
  src/App.jsx          "/" = LandingPage ; "/app/*" = Layout shell + pages
  src/components/       Layout, MapView, SiteContext, Bits, ErrorBoundary
  src/pages/            Landing, Dashboard, Explorer, Intelligence, History,
                       Climate, DataRegistry, DataQuality, OfficialDataAccess
  src/services/api.js  thin fetch client, base "/api/v1", Vite proxies to :8000
  src/index.css        all styling (dark theme tokens + landing + map)
.claude/launch.json    backend + frontend dev configs
run.ps1                starts both
```

## Run

```powershell
# backend  (venv is .venv WITH a dot)
cd C:\Users\Abhinav\Documents\SIH-prototype\backend
.\.venv\Scripts\python.exe -m uvicorn main:app --port 8000        # do NOT use --reload here (orphans a python3.13.exe child on the port)
.\.venv\Scripts\python.exe -m pytest -q

# frontend
cd C:\Users\Abhinav\Documents\SIH-prototype\frontend
npm run dev            # :5173, proxies /api -> :8000
npm run build          # sanity check

# or both:
C:\Users\Abhinav\Documents\SIH-prototype\run.ps1
```

Kill a stuck backend (the Store Python runs as `python3.13.exe`, and
`--reload` children have no "uvicorn" in their cmdline, so match by port):

```powershell
Get-NetTCPConnection -LocalPort 8000 -State Listen | ForEach-Object { Stop-Process -Id $_.OwningProcess -Force }
Get-Process | Where-Object { $_.ProcessName -like 'python*' } | Stop-Process -Force
```

## Data registry (26 datasets) — current statuses

AVAILABLE 5 · DATA_UNAVAILABLE 8 · OFFICIAL_ACCESS_REQUIRED 9 · DOCUMENT_ONLY 3 · DEMO_ONLY 1

Analytically usable now: `madurai_boundary`, `osm_infrastructure`,
`osm_hydrology`, `osm_landuse`, `open_meteo_climate`. Everything else is a
declared gap with an `acquisition` path. The gate is
`status == AVAILABLE and analytical_eligible`. Quality audit proves no
DEMO_ONLY dataset can pass it.

## Key architecture notes

- **AOI-cache pattern.** The three OSM layers are fetched once (Overpass is
  slow: 60–180 s), cached to `backend/data/*.geojson`, warmed by a startup
  thread, and refreshed weekly. `evidence_engine` and `site_context` then
  compute everything **locally** from those files — endpoints respond in
  ~0.3 s. Never add a live Overpass call on a request path.
- **Climate cache**: in-process, keyed by ~1 km rounded coord.
- **site-context** also has a disk cache (`site_context_cache.json`, keyed by
  ~100 m).
- Evidence `/report` does NOT include site context (opt-in flag); the frontend
  calls `/evidence/site-context` separately with its own loading state.
- Boundary is the real OSM relation 11268397 (Madurai Corporation, adm8).

## What's done

- Phases 1–7 of the original plan (scaffold, registry, evidence engine, map
  layers, feature engineering, suitability framework, integration + tests +
  perf). See `docs/PHASE-STATUS.md` for the detailed checklist.
- Site character: water (nearest river/tank/canal + counts + inland-coast
  note), land use (agri vs built, point-in-polygon over OSM landuse),
  development level (OSM landuse + road proxy).
- Explorer: base-map switcher (OSM / Esri Satellite / Light / Dark / HOT),
  hydrology + land-use overlays, legend, POI markers **zoom-gated at ≥13** with
  white halos, split hospital/clinic/school/college colours, popups with real
  name + raw OSM tag + `openstreetmap.org` verify link.
- Landing page at `/` (hero, pipeline stepper, live stats, checks grid,
  governance cards). App shell under `/app/*`.
- External per-point links: OSM, Google Maps, Google Street View, Mapillary,
  Bhuvan.

## Not done / next

- **Acquire the open rasters** (user deferred): Copernicus DEM GLO-30 and Esri
  Global Land Cover 2017 + 2024 → store under `backend/data/`, flip the
  registry statuses to AVAILABLE/eligible. `rasterio` + `numpy` are already in
  the venv. The terrain/LULC extractors in `feature_engineering.py` and the
  suitability scoring are already wired and gate-checked — they light up
  automatically once the data + a sampler exist. (`extract_terrain_features` /
  `extract_lulc_features` currently return `available: False` with a reason.)
- PDF export is a hand-rolled text PDF; swap for reportlab/weasyprint if a
  real A4 layout is needed. It currently prints nested dicts (site-context
  style values) as JSON — tidy if used.
- No automated frontend tests (only `npm run build` + manual click-through).
- Phase 6F-3+ (spatial suitability application, historical validation, then
  prediction, then policy simulation) — per the plan, do NOT build prediction
  before historical validation.
- OSM data caveats surfaced but not curated: e.g. `amenity=hospital` in OSM
  includes a veterinary hospital near Madurai; `amenity=clinic` covers single
  doctor practices. The UI labels these honestly and links to OSM to fix.

## Gotchas

- venv dir is `.venv` (dot). Store Python process name is `python3.13.exe`.
- Don't run uvicorn with `--reload` in this environment — it orphans a child
  holding port 8000 that `taskkill /IM python.exe` won't match.
- Overpass public endpoints are slow/rate-limited; first cache build of a
  layer can take 1–3 min. `overpass.py` already rotates mirrors.
- In the Claude Code browser pane, screenshots come back blank when the pane
  is hidden — use `get_page_text` / `read_page` to verify, or ask the user to
  bring it forward.
- LF→CRLF git warnings on Windows are harmless.
