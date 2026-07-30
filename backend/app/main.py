"""
FastAPI application: the three-way comparison endpoint, health check, and
(in production) serving of the built React frontend.
"""

from __future__ import annotations

import os
from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

from . import pipeline
from .auth import router as auth_router
from .conversations import router as conversations_router
from .config import settings
from .db import init_db
from .schemas import HealthResponse, QueryRequest

# frontend/dist (populated by `npm run build`) — served in production.
FRONTEND_DIST = Path(__file__).resolve().parent.parent.parent / "frontend" / "dist"

app = FastAPI(title="RAG Intelligence API", version=settings.version)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth_router)
app.include_router(conversations_router)


@app.post("/api/query")
async def handle_query(req: QueryRequest):
    query = req.query.strip()
    if not query:
        raise HTTPException(status_code=400, detail="Query cannot be empty.")
    try:
        return JSONResponse(pipeline.run_all(query))
    except Exception as e:  # noqa: BLE001 - surface a clean 500 to the client
        raise HTTPException(status_code=500, detail=str(e)) from e


@app.get("/api/health", response_model=HealthResponse)
async def health() -> HealthResponse:
    return HealthResponse(
        status="ok",
        version=settings.version,
        model_fast=settings.model_fast,
        model_quality=settings.model_quality,
    )


# ── Static frontend (production build) ─────────────────────────────
# Mounted last so /api/* routes always win. During development you instead run
# the Vite dev server (npm run dev), which proxies /api to this backend.
if FRONTEND_DIST.exists():
    assets = FRONTEND_DIST / "assets"
    if assets.exists():
        app.mount("/assets", StaticFiles(directory=assets), name="assets")

    @app.get("/{full_path:path}")
    async def spa(full_path: str):  # noqa: ARG001 - path captured for SPA fallback
        candidate = FRONTEND_DIST / full_path
        if full_path and candidate.is_file():
            return FileResponse(candidate)
        return FileResponse(FRONTEND_DIST / "index.html")
else:
    @app.get("/")
    async def dev_notice():
        return JSONResponse({
            "message": "Backend is running. Build the frontend (npm run build) to "
                       "serve the UI here, or run the Vite dev server (npm run dev) on :5173.",
            "health": "/api/health",
        })


def _maybe_warm_up() -> None:
    if os.environ.get("WARM_UP_MODELS", "").lower() in {"1", "true", "yes"}:
        from .ml_models import warm_up
        print("  [Startup] warming up embedding + reranker models...")
        warm_up()


@app.on_event("startup")
async def _startup() -> None:
    init_db()
    _maybe_warm_up()
