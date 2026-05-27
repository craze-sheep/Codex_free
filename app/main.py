"""Codex Relay — FastAPI application entry point."""

from __future__ import annotations

import logging
from contextlib import asynccontextmanager

import uvicorn
from fastapi import FastAPI, HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.config import settings
from app.database import get_db, init_db
from app.http_client import init_http_client, close_http_client
from app.middleware.logger import AccessLogMiddleware
from app.middleware.security import SecurityHeadersMiddleware, RequestSizeLimitMiddleware

logger = logging.getLogger(__name__)

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
# Lifespan (startup + graceful shutdown)
# ---------------------------------------------------------------------------

@asynccontextmanager
async def lifespan(app: FastAPI):
    _setup_logging()
    logger = logging.getLogger(__name__)
    logger.info("Starting Codex Relay on port %s", settings.port)

    # Init database
    await init_db()
    logger.info("Database initialized")

    # Init httpx singleton client (connection pool)
    init_http_client()
    logger.info("HTTP client initialized (connection pool ready)")

    yield

    # Graceful shutdown
    logger.info("Shutting down...")
    await close_http_client()
    logger.info("HTTP client closed")


# ---------------------------------------------------------------------------
# App
# ---------------------------------------------------------------------------

_is_prod = settings.log_level.upper() == "WARNING" or settings.log_level.upper() == "ERROR"

app = FastAPI(
    title="Codex Relay" if not _is_prod else None,
    description="Codex Responses API 中转网关" if not _is_prod else None,
    version="0.2.0",
    lifespan=lifespan,
    docs_url="/docs" if not _is_prod else None,
    redoc_url="/redoc" if not _is_prod else None,
    openapi_url="/openapi.json" if not _is_prod else None,
)

# CORS — restrict origins in production
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"] if not _is_prod else ["http://localhost", "http://127.0.0.1"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
    max_age=3600,
)

# Security headers + request tracing
app.add_middleware(SecurityHeadersMiddleware)

# Request size limit (10 MB)
app.add_middleware(RequestSizeLimitMiddleware)

# Access logging
app.add_middleware(AccessLogMiddleware)


# ---------------------------------------------------------------------------
# Exception handlers (don't leak internals)
# ---------------------------------------------------------------------------

@app.exception_handler(StarletteHTTPException)
async def custom_http_exception_handler(request: Request, exc: StarletteHTTPException):
    logger.warning("HTTP %d: %s [%s]", exc.status_code, exc.detail, request.url.path)
    return JSONResponse(
        status_code=exc.status_code,
        content={"error": {"message": str(exc.detail), "type": "http_error"}},
    )


@app.exception_handler(RequestValidationError)
async def custom_validation_handler(request: Request, exc: RequestValidationError):
    logger.info("Validation error: %s", exc.errors())
    return JSONResponse(
        status_code=422,
        content={"error": {"message": "Validation error", "type": "invalid_request_error", "details": exc.errors()}},
    )


@app.exception_handler(Exception)
async def unhandled_exception_handler(request: Request, exc: Exception):
    logger.exception("Unhandled error on %s %s", request.method, request.url.path)
    return JSONResponse(
        status_code=500,
        content={"error": {"message": "Internal server error", "type": "server_error"}},
    )


# ---------------------------------------------------------------------------
# Health checks
# ---------------------------------------------------------------------------

@app.get("/health", include_in_schema=False)
async def liveness():
    """Liveness probe — always OK if process is running."""
    return {"status": "ok"}


@app.get("/health/ready", include_in_schema=False)
async def readiness():
    """Readiness probe — checks DB connectivity."""
    try:
        db = await get_db()
        await db.execute("SELECT 1")
        await db.close()
        return {"status": "ready"}
    except Exception as e:
        logger.error("Readiness check failed: %s", e)
        return JSONResponse(
            status_code=503,
            content={"status": "not_ready", "error": str(e)},
        )


# Codex API routes
app.include_router(models_router)
app.include_router(responses_router)

# Admin API routes
app.include_router(admin_user_router)
app.include_router(admin_apikey_router)
app.include_router(admin_provider_router)
app.include_router(admin_route_router)
app.include_router(admin_usage_router)


# Static files for admin dashboard (must be last — catches all remaining routes)
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
        timeout_graceful_shutdown=30,
    )
