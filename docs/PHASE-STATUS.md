# Phase status

Built from scratch on 2026-09-08 following the development execution plan.
The plan assumed an existing codebase with a blank-page bug; the target folder
was empty, so Phase 1 became "build the app shell" rather than "debug" it.

## Phase 9 — Third prototype city: Kovilpatti (2026-09-18)

Same pattern as Phase 8's Bhopal addition, but same-state as Madurai, which
surfaced a real modelling gap and forced a small architecture correction.

- **Registry: `city` vs `state`.** Phase 8 tagged every state-authority
  dataset (`cadastral_geometry`, `ownership_records`, `tnsdma_flood_hazard`,
  `wrd_hydrology`, `tngis_crop_survey`, `tncdbr_regulations`,
  `tn_agricultural_stats`) with `city="madurai"`. That was wrong the moment a
  second Tamil Nadu city showed up — TN Survey & Settlement, TNSDMA etc. are
  the same real dataset regardless of which TN town you ask about, so
  duplicating them under `kovilpatti_*` ids would have been dishonest
  (implying two different datasets that don't exist). Fixed by adding a
  `state` field to `_ds()` alongside `city`: `city` for genuinely per-place
  things (a boundary, a town's own master plan), `state` for a
  state-government authority shared by every prototype city there,
  `None`/`None` for national bodies (CGWB, NBSS&LUP, ISRO, Esri, OSM). A
  dataset applies to a queried city if it matches that city exactly, else
  matches that city's state, else is national — see
  `data_registry._applies_to_city()`. `evidence_engine._STATE_GAPS` was
  re-keyed by state name the same way, with a new `_CITY_GAPS` layer for the
  genuinely per-town exception (each city's master plan/zoning status).
- **Kovilpatti's own master plan is a different case, correctly.** Verified
  via web search before writing anything: Kovilpatti's GIS-based master plan
  (~135.85 km² planning area) is under AMRUT 2.0 Package 3 and still **in
  preparation**, not published — unlike Madurai's approved Second Master
  Plan. So `kovilpatti_master_plan` is `DATA_UNAVAILABLE` (no document exists
  to acquire yet), not `DOCUMENT_ONLY` like Madurai's. Reusing Madurai's
  entry, or copy-pasting its status, would have fabricated a document that
  doesn't exist.
- **Boundary: taluk, not municipality, and said so.** Kovilpatti's real
  municipal limits are ~6.5 km² (thoothukudi.nic.in), but OSM has no
  admin_level-8 relation for the municipality — same situation as Bhopal.
  `scripts/fetch_boundary.py kovilpatti` fell back to relation 10311689,
  Kovilpatti **taluk/division** (admin_level 6), bbox roughly 8.88–9.25°N /
  77.67–77.98°E. Registry `limitations` says exactly that, rather than
  implying a tight municipal boundary. AOI/city_core/cadastral_patch in
  `services/cities.py` are scoped to the town regardless of the boundary
  polygon's real extent (same independence as Madurai/Bhopal).
- **Registry: 31 → 33 datasets** (`kovilpatti_boundary`,
  `kovilpatti_master_plan`). Reused rather than duplicated: `cadastral_geometry`,
  `ownership_records`, `tnsdma_flood_hazard`, `wrd_hydrology`,
  `tngis_crop_survey`, `tncdbr_regulations`, `tn_agricultural_stats` (now
  `state="Tamil Nadu"`, so they show for both Madurai and Kovilpatti).
- **Frontend:** `ExplorerPage`'s city switcher, `MapView`'s per-city
  center/zoom, `IntelligencePage`'s AOI hint and city-core label, and the
  Landing/Dashboard/Layout copy all extended to three cities.
- **Tests:** 41 pytest cases (was 39). New: dataset-count assertions (33),
  a Kovilpatti evidence-resolution test asserting it shares TN's real
  datasets with Madurai (`cadastral_geometry`, `tnsdma_flood_hazard`) but has
  its own distinct `kovilpatti_master_plan`, and a registry filter test
  proving a state dataset appears for both TN cities while a per-city one
  (a boundary) doesn't leak across them.

## Phase 8 — Second prototype city (Bhopal) + UI redesign (2026-09-14 to 2026-09-18)

Two independent efforts landed together: a full front-end visual redesign,
and expanding the platform from a single hard-coded city to a real
multi-city architecture, proven out with Bhopal, Madhya Pradesh.

### UI redesign

- **Theme.** Replaced the dark navy theme with a light, warm-neutral canvas
  (`#F7F5F0`) plus a dark charcoal sidebar (`#171A21`) — a two-tone
  professional layout (Linear/Stripe-style), terracotta (`#B4543A`) as the
  single brand accent app-wide, sage/amber/crimson retuned for legibility on
  light surfaces. Map legend/popups switched from dark overlays to white
  panels; left the actual map *data* colours (POI dots, land-use fills)
  untouched since those are legend-tied, not theme.
- **Landing page hero.** Real Esri World Imagery satellite capture of the
  Madurai AOI (same source the app's own map already uses — not a stock
  photo) as the hero background, `frontend/public/madurai-hero.jpg`. Fixed a
  real stacking-context bug along the way: the hero's background pseudo
  layer had no `z-index` of its own, so it painted *behind* the page
  background instead of in front of it (`z-index: 0` on `.lp-hero` fixed
  it). Rebuilt as real DOM elements (`.lp-hero__bg` / `.lp-hero__fade`)
  instead of a `::before`, giving the hero rounded corners, a soft shadow,
  a bottom fade into the page (no hard photo cutoff), and a scroll-linked
  parallax (`translateY(scrollY * 0.12)`, capped, skipped under
  `prefers-reduced-motion`).
- **Scroll reveal.** `useReveal` (IntersectionObserver) + a `<Reveal>`
  wrapper, staggered per grid item. Initially wired up scoped to `.lp` only
  (landing-page CSS selector), which silently no-opped everywhere else —
  found and fixed by making `.reveal`/`.reveal.in` global, then wired into
  every other page's cards/stat-tiles (Dashboard, Explorer, Land
  Intelligence + Site Character, History, Climate, Data Registry, Data
  Quality, Official Data Access).
- **3D-style depth, not a 3D library.** Considered and rejected a full
  React-Three-Fiber cadastral-plot visualiser (the shape of an earlier,
  unrelated land-*sales* redesign brief) as the wrong scope for a government
  evidence platform. Built `useTilt` instead — cursor-tracked
  `perspective/rotateX/rotateY` tilt + lift on the hero evidence card and the
  three governance cards, gated on `pointer: fine` and
  `prefers-reduced-motion`.
- **Custom cursor.** Terracotta dot + a `mix-blend-mode: difference` ring
  (so it reads correctly on both the light content and the dark sidebar
  without per-surface theming) that grows on hover over anything clickable;
  hidden over text inputs and the Leaflet map so native affordances
  (text caret, grab-hand) still work. `pointer: fine` gated.

### Multi-city architecture (Bhopal)

- **Why Bhopal.** Different state (Madhya Pradesh vs Tamil Nadu — genuinely
  tests the "national" framing) and known for its lakes, a direct contrast
  to Madurai's river-based water evidence.
- **`services/cities.py`** (new): a small registry — id, label, state, aoi,
  city_core, cadastral_patch, boundary file/dataset id, OSM name pattern,
  flood authority — replacing the module-level `AOI`/`CITY_CORE` constants
  in `evidence_engine.py`. `resolve_city_for_point(lat, lon)` picks the
  city whose AOI contains a coordinate; `evidence.py`/`analytics.py` needed
  **no signature changes** since they already treated lat/lon as generic
  floats — only `routers/gis.py` (hard-coded `/madurai/...` paths) and
  `evidence_engine`'s AOI/CITY_CORE were actually Madurai-specific.
- **GIS routes parameterised**: `/gis/madurai/...` → `/gis/{city}/...`
  (backward compatible — `madurai` still matches as a path value). OSM
  layer caches split per city: `osm_{infrastructure,hydrology,landuse}_{city}.geojson`.
- **Real boundary, verified names.** `scripts/fetch_boundary.py` generalised
  to take a city argument. Bhopal has no admin_level-8 (municipal
  corporation) relation in OSM either — fell back to admin_level 5
  (**district**, relation 1976080) and the registry says so honestly rather
  than implying a tight city boundary. Every Madhya Pradesh authority name
  (MP Revenue Dept/Bhu-Abhilekh, MPIGRS/SAMPADA, MPSDMA, DT&CP MP) was
  **web-verified before writing**, not guessed — matches the platform's own
  no-fabrication rule applied to its own metadata.
- **Cadastral demo, upgraded and fixed.** The old uniform 6×6
  `demo_cadastral_grid` became `services/cadastral_demo.py`: a randomised
  recursive guillotine split into irregular parcels with real geodesic area
  (equirectangular approximation, accurate at this scale) in m² / cents /
  sq ft, click-to-inspect popups, hover highlight — still `DEMO_ONLY`,
  still excluded from the evidence engine and analytics gate. Caught and
  fixed a real scale bug while building it: the first version spanned the
  entire city core, averaging **2.3 million m² per "parcel."** Added a
  separate, much smaller `cadastral_patch` per city (~one street block,
  ~200 m across) so the demo now averages a plausible few-hundred m².
- **Real bug found while testing, not by the test suite.** `site_context.py`
  (water/land-use/development for the Land Intelligence "Site Character"
  card) still read the old *un-suffixed* cache filenames
  (`osm_hydrology.geojson` etc.) after the per-city cache rename — so a
  Bhopal coordinate was silently checking Bhopal's lat/lon against
  *Madurai's* cached water layer. Bhopal's real Upper/Lower Lakes would have
  shown as "no water nearby." Found by manually running a live Bhopal
  evidence lookup after the automated suite passed; fixed by threading
  `city` through `_water`/`_land_use`/`_development`/`build_site_context`
  and the two call sites (`routers/evidence.py`, `evidence_engine.py`'s
  `include_site_context` path); added a regression test
  (`test_site_context_uses_the_right_citys_cache`) asserting Bhopal's
  waterbody count is nonzero and its coast note doesn't say "Madurai."
- **Registry: 26 → 31 datasets.** New Bhopal counterparts for the
  state-authority entries (`mp_cadastral_geometry`, `mp_ownership_records`,
  `mpsdma_flood_hazard`, `bhopal_master_plan`) plus `bhopal_boundary`.
- **Frontend:** city switcher on Explorer (button group, fetched from
  `/gis/cities`), `MapView` re-centers and re-fetches every layer on city
  change, Data Registry's list endpoint gained a `city` filter, IntelligencePage
  shows the resolved city's label instead of a hard-coded "Madurai."
- **Tests: 26 → 39** pytest cases (Phase 7 had 26; new coverage added for
  city resolution, the site-context cache-key regression, and per-city GIS
  endpoints). Full suite green throughout.

## Addendum (2026-09-09) — landing page, marker audit

- **Marker data-quality fix.** Reported issue: "schools marked where there are
  none" near the Teppakulam. Root cause: `amenity=clinic` was rendered
  identically to `amenity=hospital` (coral dots that read yellow on
  satellite), and there is genuinely *nothing* educational within 500 m of the
  tank in OSM. Fixes: `hospital` / `clinic` / `school` / `college` are now
  distinct kinds with distinct colours and honest legend labels; every marker
  popup shows the real name, the raw OSM tag, operator, and a
  `openstreetmap.org/{type}/{id}` "verify / fix on OSM" link; POI markers are
  hidden below zoom 13 (a hint shows instead) so the city view isn't a blob;
  white halo on every marker for contrast on any base map. Infra cache rebuilt
  with `osm_type` / `osm_tag` / `operator` properties. Evidence now reports
  `distance_to_hospital_m` and `distance_to_clinic_or_hospital_m` separately
  (same for school / school-or-college).
- **Landing page.** `/` is now a marketing/orientation page (hero with a
  contour-texture backdrop, sample-evidence card, the six-stage pipeline with
  a "you are here" marker on *Verified evidence*, live registry numbers, a
  "what you can check" grid, data-governance cards, footer). The app shell
  moved under `/app/*` (`/app/dashboard`, `/app/explorer`, …). Warm-earth
  secondary accent (`--land`), hover transitions, non-clipping page scroll.
- Tests: 33 pytest cases green.

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
