"""
National Digital Platform — API entrypoint.

Run:  uvicorn main:app --reload --port 8000
Docs: http://localhost:8000/docs
"""
import logging
import os
import threading
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware

from routers import analytics, data_registry, evidence, gis, quality

logging.basicConfig(level=logging.INFO,
                    format="%(asctime)s %(levelname)s %(name)s: %(message)s")

@asynccontextmanager
async def lifespan(_app: FastAPI):
    # Warm the OSM infrastructure cache off the request path.
    threading.Thread(target=gis.warm_infrastructure_cache, daemon=True).start()
    yield


app = FastAPI(
    title="National Digital Platform API",
    description="Evidence-first land governance & research platform "
                "(Madurai, Bhopal & Kovilpatti prototypes).",
    version="0.1.0",
    lifespan=lifespan,
)

# Which websites may call this API from the browser. Local dev + any Netlify
# site by default; add more (e.g. a custom domain) with a comma-separated
# ALLOWED_ORIGINS env var. The API is read-only public data with no cookies.
_extra_origins = [o.strip() for o in os.environ.get("ALLOWED_ORIGINS", "").split(",") if o.strip()]
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173", *_extra_origins],
    allow_origin_regex=r"https://([a-z0-9-]+\.)*netlify\.app",
    allow_methods=["GET", "POST"],
    allow_headers=["*"],
)

app.include_router(data_registry.router, prefix="/api/v1/data-registry",
                   tags=["data-registry"])
app.include_router(quality.router, prefix="/api/v1/data-quality",
                   tags=["data-quality"])
app.include_router(evidence.router, prefix="/api/v1/evidence", tags=["evidence"])
app.include_router(analytics.router, prefix="/api/v1/analytics", tags=["analytics"])
app.include_router(gis.router, prefix="/api/v1/gis", tags=["gis"])


@app.get("/api/v1/health")
def health():
    return {"status": "ok", "service": "ndp-api", "version": app.version}


# --- the built web app (frontend/dist) --------------------------------------
# When `npm run build` has produced frontend/dist, this one server also serves
# the website, so the whole platform is a single URL (for sharing / deploying).
# In development the Vite dev server on :5173 is used instead.
_DIST = Path(__file__).resolve().parent.parent / "frontend" / "dist"

if (_DIST / "index.html").is_file():
    app.mount("/assets", StaticFiles(directory=_DIST / "assets"), name="assets")

    @app.get("/{path:path}", include_in_schema=False)
    def web_app(path: str):
        if path.startswith("api/"):
            raise HTTPException(404, "Unknown API route")
        f = (_DIST / path).resolve()
        if path and f.is_file() and _DIST in f.parents:
            return FileResponse(f)
        return FileResponse(_DIST / "index.html")  # client-side routes
else:
    @app.get("/")
    def root():
        return {"service": "National Digital Platform API",
                "docs": "/docs", "health": "/api/v1/health"}
