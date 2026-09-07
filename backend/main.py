"""
National Digital Platform — API entrypoint.

Run:  uvicorn main:app --reload --port 8000
Docs: http://localhost:8000/docs
"""
import logging
import threading
from contextlib import asynccontextmanager

from fastapi import FastAPI
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
                "(Madurai prototype).",
    version="0.1.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
    allow_methods=["*"],
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


@app.get("/")
def root():
    return {"service": "National Digital Platform API",
            "docs": "/docs", "health": "/api/v1/health"}
