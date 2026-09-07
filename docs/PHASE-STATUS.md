# Phase status

Built from scratch on 2026-09-08 following the development execution plan.
The plan assumed an existing codebase with a blank-page bug; the target folder
was empty, so Phase 1 became "build the app shell" rather than "debug" it.

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

- Boundary: **placeholder bbox, labelled DEMO**, red dashed. Real fetch:
  `backend/scripts/fetch_boundary.py`.
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

## Not done / next

- Phase 7 end-to-end + perf pass (manual click-through done; no automated tests
  yet).
- Acquire open rasters: run a DEM fetch (OpenTopography / AWS COG) and Esri
  LULC AOI export, store under `backend/data/`, flip registry statuses, and the
  terrain/LULC extractors + suitability scoring light up automatically.
- Replace placeholder boundary via `fetch_boundary.py`.
- Richer A4 PDF (reportlab/weasyprint) if needed.
- Phase 6F-3+ (spatial application, historical validation, prediction) — not
  before historical validation, per the plan.
