"""RetailVision AI backend entrypoint."""
from __future__ import annotations

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from . import config, db
from .routes_analysis import router as analysis_router
from .routes_core import router as core_router

app = FastAPI(title="RetailVision AI", version="0.1.0",
              description="AI retail CCTV intelligence platform (local prototype)")

# Prototype: allow the Vercel-hosted frontend (any origin) to call the API.
# Lock down origins + credentials in production.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(core_router)
app.include_router(analysis_router)


@app.on_event("startup")
def _startup():
    db.init_db()


@app.get("/api/health")
def health():
    return {"ok": True, "app": "retailvision"}


# Frontend (static SPA) + uploaded video media (served with Range support).
config.ensure_dirs()
if config.STATIC_DIR.exists():
    app.mount("/static", StaticFiles(directory=str(config.STATIC_DIR)), name="static")
app.mount("/media", StaticFiles(directory=str(config.UPLOAD_DIR)), name="media")


@app.get("/", include_in_schema=False)
def index():
    return FileResponse(str(config.STATIC_DIR / "index.html"))
