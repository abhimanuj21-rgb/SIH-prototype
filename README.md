# National Digital Platform — Land Governance & Research (Multi-City Prototype)

Evidence-first national digital platform for land governance and research.
Prototype areas: **Madurai, Tamil Nadu** · **Bhopal, Madhya Pradesh** ·
**Kovilpatti, Tamil Nadu**.

## Core principle

> Real data first → verified evidence → analytical features → validated models → prediction → policy simulation.

No fabricated data. Demo data is always labelled. Restricted data shows
`OFFICIAL_ACCESS_REQUIRED`. Provenance is tracked for every dataset.

## Structure

```
backend/    FastAPI service (data registry, evidence engine, analytics, GIS)
frontend/   React + Vite + Leaflet client
```

## Prototype cities

The platform isn't hard-coded to one place — `backend/services/cities.py` is
a small registry (area of interest, city core, boundary source) that every
GIS/evidence endpoint resolves a coordinate against. Adding a city means
adding one entry there, fetching its real OSM boundary
(`scripts/fetch_boundary.py <city>`), and — for a new *state* — adding
web-verified entries for that state's cadastral/ownership/flood authorities
in the data registry (never guessed).

| City | State | Why |
|---|---|---|
| Madurai | Tamil Nadu | Original prototype; real Corporation boundary, Vaigai river. |
| Bhopal | Madhya Pradesh | Different state; "City of Lakes" contrasts with Madurai's river-based water evidence. |
| Kovilpatti | Tamil Nadu | A small town, not a city — proves the same-state dataset-sharing model (reuses Madurai's real TN Survey & Settlement / TNSDMA entries rather than duplicating them). |

## Run

### Backend

```bash
cd backend
python -m venv .venv
.venv\Scripts\activate        # Windows
pip install -r requirements.txt
uvicorn main:app --reload --port 8000
```

API docs: http://localhost:8000/docs

### Frontend

```bash
cd frontend
npm install
npm run dev
```

App: http://localhost:5173 (proxies `/api` to `http://localhost:8000`)

## Status

Phases 1–9 complete. Built from scratch on 2026-09-08 following the
development execution plan; Phase 8 added a full UI redesign plus the first
multi-city expansion (Bhopal), Phase 9 added Kovilpatti and a `city`/`state`
dataset-tagging model so cities in the same state correctly share real
datasets instead of duplicating them. See `docs/PHASE-STATUS.md` for the
detailed checklist and `docs/HANDOFF.md` for a full architecture snapshot.
