import sys
from pathlib import Path

# Ensure root directory (containing backend/) is in sys.path
_pkg_root = Path(__file__).resolve().parent.parent.parent
if str(_pkg_root) not in sys.path:
    sys.path.insert(0, str(_pkg_root))

_backend_dir = Path(__file__).resolve().parent.parent
if str(_backend_dir) not in sys.path:
    sys.path.insert(0, str(_backend_dir))

import logging
from contextlib import asynccontextmanager
from fastapi import FastAPI, HTTPException
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from starlette.exceptions import HTTPException as StarletteHTTPException
from backend.app.core.config import settings
from backend.app.core.db_repository import db_repository
from backend.app.api.api_router import api_router
from backend.app.services.pipeline_scheduler import pipeline_scheduler

logger = logging.getLogger("pulse.main")


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup: Reconcile orphan pipeline runs left in 'queued' or 'running' state (Phase 9.1 Step 2)
    try:
        reconciled = db_repository.reconcile_orphan_pipeline_runs()
        if reconciled > 0:
            logger.warning(
                f"[LIFECYCLE] Reconciled {reconciled} orphan pipeline run(s) left in queued/running status -> marked as interrupted."
            )
        else:
            logger.info("[LIFECYCLE] Startup check: No orphan pipeline runs found to reconcile.")
    except Exception as e:
        logger.error(f"[LIFECYCLE] Failed to reconcile orphan pipeline runs on startup: {e}", exc_info=True)

    # Startup: Start automatic pipeline scheduler if enabled
    if settings.SCHEDULER_ENABLED:
        logger.info("[LIFECYCLE] Starting Pulse pipeline scheduler...")
        pipeline_scheduler.start()
    else:
        logger.info("[LIFECYCLE] Pulse pipeline scheduler is disabled by configuration.")

    yield

    # Shutdown: Cleanly shut down scheduler
    if pipeline_scheduler.is_running():
        logger.info("[LIFECYCLE] Shutting down Pulse pipeline scheduler...")
        pipeline_scheduler.shutdown(wait=False)


app = FastAPI(
    title=settings.PROJECT_NAME,
    description=(
        "Personal News Intelligence Engine - Foundation API. "
        "Continuously collects, deduplicates, clusters, ranks, and personalizes news for technology and engineering."
    ),
    version="0.1.0-foundation",
    openapi_url=f"{settings.API_V1_STR}/openapi.json",
    docs_url=f"{settings.API_V1_STR}/docs",
    redoc_url=f"{settings.API_V1_STR}/redoc",
    lifespan=lifespan,
)

# Configure CORS (environment-driven, production-safe, Bearer token compatible)
cors_origins = [orig for orig in settings.BACKEND_CORS_ORIGINS if orig and orig != "*"]
app.add_middleware(
    CORSMiddleware,
    allow_origins=cors_origins,
    allow_credentials=False,
    allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
    allow_headers=["Authorization", "Content-Type", "Accept", "Origin", "X-Requested-With"],
)

# Production error handling: Never leak tracebacks, SQL queries, or internal exceptions
@app.exception_handler(Exception)
async def unhandled_exception_handler(request, exc):
    if isinstance(exc, (HTTPException, StarletteHTTPException)):
        return JSONResponse(
            status_code=exc.status_code,
            content={"detail": exc.detail},
            headers=getattr(exc, "headers", None)
        )
    logger.error(f"Unhandled server error: {exc}", exc_info=True)
    return JSONResponse(
        status_code=500,
        content={"detail": "An internal server error occurred."}
    )

# Include core API router under /api
app.include_router(api_router, prefix=settings.API_V1_STR)

@app.get("/")
async def root():
    return {
        "system": "Pulse Personal News Intelligence",
        "tagline": "Your world. Filtered intelligently.",
        "version": "0.1.0-foundation",
        "docs": f"{settings.API_V1_STR}/docs",
        "health": f"{settings.API_V1_STR}/health"
    }

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("backend.app.main:app", host="127.0.0.1", port=8000, reload=True)
