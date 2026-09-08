# Phase status

Built from scratch on 2026-09-08 following the development execution plan.
The plan assumed an existing codebase with a blank-page bug; the target folder
was empty, so Phase 1 became "build the app shell" rather than "debug" it.

## Addendum (2026-09-08) — site context, base maps, UI pass

- **Site character** (`POST /api/v1/evidence/site-context`, shown on Land
  Intelligence): water source & bodies (nearest river/stream, tank/pond,
  canal; counts within 2.5 km; inland-coast note), land use (agricultural vs
  built-up, from OSM `landuse` polygons + point-in-polygon), and a development
  level (Urban / Suburban / Rural / …) from an OSM land-use + road-network
  proxy. Computed locally from the cached AOI layers — **~0.3 s**, no Overpass
  call on the request path — after a one-time layer warm-up. Honest caveats
  throughout: OSM land-use is a tag, not a raster; definitive land cover still
  needs the Esri/Sentinel-2 gap.
- **New map layers & base maps** — Explorer now has OSM Standard, Esri
  Satellite / Light / Dark, OSM Humanitarian base layers, plus toggleable
  hydrology (`/gis/madurai/hydrology/osm`) and land-use
  (`/gis/madurai/landuse/osm`) overlays, a legend, and `invalidateSize`
  handling. Satellite view gives the "street-level / how-built-up" read.
- **External views** — per-point links to OpenStreetMap, Google Maps, Google
  Street View, Mapillary and Bhuvan (plain anchors, nothing sent until click).
- **UI pass** — refined dark theme (tokens, shadows, radii), grouped sidebar
  with icons, sticky header with page title, stat tiles, section headers,
  skeleton loaders, chips, responsive < 900 px.
- Tests: 32 pytest cases green (added site-context + geometry helpers).
  `services/geo.py` extracted for shared geometry.

## Phase 1 — Frontend stabilization & backend scaffold ✅

| Success criterion | State |
|---|---|
| All pages render without errors | ✅ 8 routes, all render |
| Map displays on Explorer | ✅ Leaflet + OSM tiles, boundary + infra layers, click-to-pick |
| No console errors | ✅ (only React Router v7 future-flag warnings) |
| Navigation works between all routes | ✅ |
| API connections functional | ✅ health indicator, proxied `/api` → :8000 |
| Dark theme | ✅ |
| Production build | ✅ `npm run build` clean, 91 modules |

Notable fix during build: `useAsync` left `mounted.current === false` after
StrictMode's simulated unmount, so every `setState` was skipped and pages hung
on "Loading". Fixed by restoring the flag on (re)mount.

Routes: `/` `/explorer` `/intelligence` `/history` `/climate` `/data-registry`
`/data-quality` `/official-data-access` (unknown → redirect to `/`).

## Phase 2 — Data registry ✅ (structure; statuses reflect a from-scratch build)

- 26 datasets registered with full provenance (`source`, `authority`,
  `license`, `limitations`, `acquisition`, `analytical_eligible`).
- Analytical gate: `status == AVAILABLE and analytical_eligible` — verified by
  `/api/v1/data-registry/gate/{id}` and the Data Quality audit (26/26 pass, no
  demo-data leak, provenance complete).
- Status split: AVAILABLE 4 · DATA_UNAVAILABLE 8 · OFFICIAL_ACCESS_REQUIRED 9 ·
  DOCUMENT_ONLY 3 · DEMO_ONLY 2.
- **Honesty note:** the plan marked Copernicus DEM / Esri LULC as AVAILABLE
  (real files). Nothing has been acquired to local storage, so those are
  `DATA_UNAVAILABLE` with an `acquisition` path. Only keyless live sources
  (Open-Meteo, OSM/Overpass) are `AVAILABLE`.

## Phase 3 — Evidence engine ✅ (for available data)

- `POST /api/v1/evidence/location` and `/report`: real ERA5 climate + OSM
  infrastructure distances, plus 9 explicit gaps (terrain, LULC ×2, cadastral,
  ownership, flood, zoning, soil, groundwater) each with status + resolution.
- Conclusion is descriptive only; no prediction/valuation.
- Exports: `/export/json`, `/export/pdf` (dependency-free PDF writer),
  `/export/manifest` (provenance for all 26 datasets). All return 200.
- Infrastructure distances are computed locally from the cached AOI OSM layer
  (no Overpass call on the request path).

## Phase 4 — Map layers ✅ (available layers)

- Boundary: **real** — OSM relation 11268397 (Madurai Corporation, admin_level
  8, Q228405), MultiPolygon, fetched via `backend/scripts/fetch_boundary.py`.
  Registry flipped to AVAILABLE / analytically eligible. Renders solid blue.
- OSM infrastructure: live Overpass, cached to `backend/data/`, warmed on
  startup. Roads as lines, hospitals/schools/stations as points.
- Terrain / LULC / LULC history / LULC change endpoints return a structured
  "unavailable + how to acquire" payload — never fake geometry.
- Demo cadastral grid: synthetic, `is_demo: true`, distinct dashed-red style,
  `analytical_use: forbidden`, excluded from evidence + analytics.

## Phase 5 — Feature engineering ✅ (partial by design)

- `POST /api/v1/analytics/features`: climate + infrastructure blocks with
  provenance; terrain + lulc report `available: false` with a reason. Range /
  completeness / provenance validation per block.

## Phase 6 — Suitability ✅ (refuses to score on incomplete evidence)

- `POST /api/v1/analytics/suitability` (`type`: agricultural | development):
  rule-based weighted checklist. With terrain + LULC missing it returns
  `scorable: false` and lists the missing features rather than guessing.
  Scoring path is implemented and unit-shaped for when the data lands.

## Phase 7 — Integration & testing ✅

- **Automated tests:** `backend/tests/` — 26 pytest cases, all green in ~1.4 s
  (`cd backend && python -m pytest`). Cover registry + gate, quality audit,
  evidence structure + AOI rejection, descriptive-only report, PDF/JSON/manifest
  exports, partial feature vector, suitability refusing incomplete evidence,
  real boundary, terrain "unavailable not fake", demo-grid flagging.
- **E2E click-through:** Explorer map click → "Land Intelligence for …" →
  auto-analysed evidence report. Verified in-browser.
- **Performance (warm):** static/GIS endpoints ~0.2–0.36 s; POST endpoints
  1.3–1.8 s first hit (Open-Meteo), ~0.23 s after the per-coord climate cache.
  PDF export ~1.4 s. All within the plan's targets (API < 2 s, report < 5 s,
  PDF < 10 s).
- Added a process-lifetime climate cache keyed by ~1 km rounded coordinate.

## Not done / next

- Acquire open rasters from their providers (DEM, Esri LULC 2017/2024), store
  under `backend/data/`, flip registry statuses; the terrain/LULC extractors +
  suitability scoring then light up automatically. `rasterio`/`numpy` are
  already installed in the venv for this. *(User chose to fetch these later.)*
- Richer A4 PDF (reportlab/weasyprint) if needed.
- Phase 6F-3+ (spatial application, historical validation, prediction) — not
  before historical validation, per the plan.
