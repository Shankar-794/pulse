from fastapi import APIRouter
from typing import Dict, Any, List
from backend.app.services.ingestion_service import ingestion_service
from backend.app.services.source_registry import source_registry
from backend.app.core.db_repository import db_repository

router = APIRouter(prefix="/ingestion", tags=["ingestion"])

@router.post("/run")
async def run_ingestion() -> Dict[str, Any]:
    """
    Trigger a manual news ingestion cycle across all enabled registered sources.
    Fetches real RSS feeds, normalizes articles, filters duplicates, and stores new articles.
    """
    summary = await ingestion_service.run_ingestion_cycle()
    return summary

@router.get("/sources")
async def get_registered_sources() -> List[Dict[str, Any]]:
    """
    Retrieve list of all registered news wire and technical feeds.
    """
    sources = source_registry.get_all()
    return [s.to_dict() for s in sources]

@router.get("/status")
async def get_ingestion_status() -> Dict[str, Any]:
    """
    Retrieve the status of the ingestion pipeline and database article metrics.
    """
    last_summary = ingestion_service.get_last_summary()
    total_stored = db_repository.get_total_count()
    return {
        "pipeline_status": "ready",
        "total_stored_articles": total_stored,
        "last_ingestion_run": last_summary or None
    }
