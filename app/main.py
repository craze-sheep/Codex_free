"""Codex Relay — FastAPI application entry point."""

from __future__ import annotations

import logging
from contextlib import asynccontextmanager

import uvicorn
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from app.config import settings
from app.database import init_db
from app.middleware.logger import AccessLogMiddleware

# Routers
from app.routers.models import router as models_router
from app.routers.responses import router as responses_router
from app.routers.admin.user import router as admin_user_router
from app.routers.admin.apikey import router as admin_apikey_router
from app.routers.admin.provider import router as admin_provider_router
from app.routers.admin.route import router as admin_route_router
from app.routers.admin.usage import router as admin_usage_router


# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------

def _setup_logging():
    level = getattr(logging, settings.log_level.upper(), logging.INFO)
    logging.basicConfig(
        level=level,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )


# ---------------------------------------------------------------------------
# Lifespan
# ---------------------------------------------------------------------------

@asynccontextmanager
async def lifespan(app: FastAPI):
    _setup_logging()
    logger = logging.getLogger(__name__)
    logger.info("Starting Codex Relay on port %s", settings.port)
    await init_db()
    logger.info("Database initialized")
    yield
    logger.info("Shutting down")


# ---------------------------------------------------------------------------
# App
# ---------------------------------------------------------------------------

app = FastAPI(
    title="Codex Relay",
    description="Codex Responses API 中转网关",
    version="0.1.0",
    lifespan=lifespan,
)

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Access logging
app.add_middleware(AccessLogMiddleware)

# Codex API routes
app.include_router(models_router)
app.include_router(responses_router)

# Admin API routes
app.include_router(admin_user_router)
app.include_router(admin_apikey_router)
app.include_router(admin_provider_router)
app.include_router(admin_route_router)
app.include_router(admin_usage_router)


# Health check
@app.get("/health")
async def health():
    return {"status": "ok"}


# Static files for admin dashboard
import os
_static_dir = os.path.join(os.path.dirname(__file__), "static")
if os.path.isdir(_static_dir):
    app.mount("/", StaticFiles(directory=_static_dir, html=True), name="static")


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    uvicorn.run(
        "app.main:app",
        host="0.0.0.0",
        port=settings.port,
        log_level=settings.log_level.lower(),
    )
