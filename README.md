# National Digital Platform — Land Governance & Research (Madurai Prototype)

Evidence-first national digital platform for land governance and research.
Prototype area: **Madurai, Tamil Nadu**.

## Core principle

> Real data first → verified evidence → analytical features → validated models → prediction → policy simulation.

No fabricated data. Demo data is always labelled. Restricted data shows
`OFFICIAL_ACCESS_REQUIRED`. Provenance is tracked for every dataset.

## Structure

```
backend/    FastAPI service (data registry, evidence engine, analytics, GIS)
frontend/   React + Vite + Leaflet client
```

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

Phase 1 — Frontend stabilization & backend scaffold. Built from scratch on
2026-09-08 following the development execution plan. See `docs/` for phase notes.
