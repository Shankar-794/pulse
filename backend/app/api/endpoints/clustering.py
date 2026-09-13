from fastapi import APIRouter, Query
from typing import Optional, Dict, Any

from backend.app.services.clustering_service import clustering_service

router = APIRouter(prefix="/clustering", tags=["clustering"])


@router.post("/run")
async def run_clustering(
    time_window_hours: Optional[int] = Query(
        None,
        description="Sliding time window in hours to cluster articles (default: 72 hours)"
    )
) -> Dict[str, Any]:
    """
    Trigger the Story Intelligence hybrid clustering pipeline.
    Clusters ingested articles within the candidate window using hybrid TF-IDF + entity overlap.
    Idempotent: Re-running does not produce duplicate stories.
    """
    metrics = clustering_service.run_clustering(time_window_hours=time_window_hours)
    return metrics


@router.get("/metrics")
async def get_clustering_metrics() -> Dict[str, Any]:
    """
    Returns performance metrics and statistics from the latest clustering run.
    """
    return clustering_service.get_metrics()


@router.get("/diagnostics")
async def get_clustering_diagnostics(
    time_window_hours: Optional[int] = Query(
        None,
        description="Sliding time window in hours for diagnostic analysis (default: 72 hours)"
    )
) -> Dict[str, Any]:
    """
    Development diagnostic endpoint.
    Calculates pairwise similarity distributions, candidate pair counts,
    similarity percentiles, threshold distributions, and top pair details on actual data.
    """
    diagnostics = clustering_service.compute_diagnostics(time_window_hours=time_window_hours)
    return diagnostics
