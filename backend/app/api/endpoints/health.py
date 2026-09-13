"""
System & Health API Endpoints (Phase 8.1).
Exposes /api/health and /api/system/health for operational monitoring.
"""
from datetime import datetime
from fastapi import APIRouter
from typing import Dict, Any

from backend.app.core.db_repository import db_repository
from backend.app.services.ingestion_service import ingestion_service
from backend.app.services.pulse_pipeline import pulse_pipeline

router = APIRouter()
START_TIME = datetime.utcnow()


@router.get("/health", tags=["system"])
async def health_check():
    """
    Basic health check endpoint returning system status, service name, and uptime.
    """
    return {
        "status": "healthy",
        "service": "Pulse News Intelligence API",
        "version": "0.1.0-foundation",
        "timestamp": datetime.utcnow().isoformat(),
        "uptime_seconds": int((datetime.utcnow() - START_TIME).total_seconds()),
        "capabilities": {
            "ingestion_pipeline": "ready",
            "deduplication_engine": "ready",
            "clustering_engine": "ready",
            "story_analysis": "ready",
            "importance_engine": "ready",
            "story_evolution": "ready",
            "personal_relevance": "ready",
            "feed_ranking": "ready",
            "database_readiness": "sqlite-ready"
        }
    }


@router.get("/system/health", tags=["system"])
async def system_health() -> Dict[str, Any]:
    """
    Comprehensive system health endpoint reporting:
    - database health
    - pipeline last run status/time/duration
    - total stories
    - analyzed stories
    - importance-scored stories
    - evolved stories
    - ingestion source count
    - last ingestion status
    """
    db_stats = db_repository.get_system_health_stats()
    last_pipeline = pulse_pipeline.get_last_run()
    last_ingestion = ingestion_service.get_last_summary()

    # Determine database health label
    db_status = "healthy" if db_stats.get("database_healthy") else "unhealthy"

    # Pipeline last run reporting
    pipeline_info = {
        "status": last_pipeline.get("status") if last_pipeline else "never_run",
        "last_run_status": last_pipeline.get("status") if last_pipeline else "never_run",
        "last_run_time": (last_pipeline.get("completed_at") or last_pipeline.get("started_at")) if last_pipeline else None,
        "last_run_duration_seconds": last_pipeline.get("total_duration_seconds") if last_pipeline else 0.0,
        "started_at": last_pipeline.get("started_at") if last_pipeline else None,
        "completed_at": last_pipeline.get("completed_at") if last_pipeline else None,
        "duration_seconds": last_pipeline.get("total_duration_seconds") if last_pipeline else 0.0,
        "stages": {k: v.get("status") for k, v in last_pipeline.get("stages", {}).items()} if last_pipeline else {}
    }

    # Ingestion status
    ingestion_status = "idle"
    if last_ingestion:
        if last_ingestion.get("failed_sources", 0) > 0 and last_ingestion.get("sources_checked", 0) > 0:
            if last_ingestion.get("failed_sources") == last_ingestion.get("sources_checked"):
                ingestion_status = "failed"
            else:
                ingestion_status = "partial_success"
        elif last_ingestion.get("completed_at"):
            ingestion_status = "success"

    return {
        "status": "healthy" if db_status == "healthy" else "degraded",
        "database_health": db_status,
        "timestamp": datetime.utcnow().isoformat(),
        "total_stories": db_stats.get("total_stories", 0),
        "analyzed_stories": db_stats.get("analyzed_stories", 0),
        "importance_scored_stories": db_stats.get("importance_scored_stories", 0),
        "evolved_stories": db_stats.get("evolved_stories", 0),
        "total_articles": db_stats.get("total_articles", 0),
        "ingestion_source_count": db_stats.get("ingestion_source_count", 0),
        "last_ingestion_status": ingestion_status,
        "pipeline_last_run_status": pipeline_info.get("last_run_status"),
        "pipeline_last_run_time": pipeline_info.get("last_run_time"),
        "pipeline_last_run_duration": pipeline_info.get("last_run_duration_seconds"),
        "last_ingestion_summary": {
            "completed_at": last_ingestion.get("completed_at"),
            "sources_checked": last_ingestion.get("sources_checked", 0),
            "new_articles": last_ingestion.get("new_articles", 0),
            "duplicates": last_ingestion.get("duplicates", 0),
            "failed_sources": last_ingestion.get("failed_sources", 0),
            "duration_seconds": last_ingestion.get("duration_seconds", 0.0)
        } if last_ingestion else None,
        "pipeline": pipeline_info
    }
