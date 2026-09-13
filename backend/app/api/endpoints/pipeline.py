import uuid
import logging
from datetime import datetime, timezone
from typing import Optional, Dict, Any, List
from fastapi import APIRouter, Query, BackgroundTasks, HTTPException

from backend.app.core.db_repository import db_repository
from backend.app.services.pulse_pipeline import pulse_pipeline

logger = logging.getLogger("pulse.api.pipeline")
router = APIRouter()


@router.post("/pipeline/run", tags=["pipeline"])
async def run_pipeline(
    background_tasks: BackgroundTasks,
    skip_ingestion: bool = Query(False, description="Whether to skip RSS feed ingestion"),
    time_window_hours: Optional[int] = Query(None, description="Time window in hours for candidate clustering"),
    analysis_limit: int = Query(50, ge=1, le=200, description="Max unanalyzed stories to evaluate with AI understanding"),
    importance_limit: int = Query(100, ge=1, le=500, description="Max unscored stories to evaluate for global importance"),
    evolution_limit: int = Query(100, ge=1, le=500, description="Max stories to process for story evolution"),
    feed_limit: int = Query(50, ge=1, le=100, description="Number of stories to rank for feed readiness"),
    user_id: str = Query("default_user", description="User ID for personal relevance profiling"),
    trigger_type: str = Query("api", description="Trigger mechanism: manual, api, scheduled")
) -> Dict[str, Any]:
    """
    Triggers the Pulse end-to-end intelligence pipeline in a background task (Phase 8.2 Step 2).
    Returns immediately with status 'accepted' and a persistent run_id.
    Rejects concurrent runs with 409 Conflict if a pipeline is already queued or running.
    """
    # 1. Prevent concurrent runs
    active_run = db_repository.get_active_pipeline_run()
    if active_run:
        raise HTTPException(
            status_code=409,
            detail={
                "message": "A pipeline execution is already in progress.",
                "active_run_id": active_run["run_id"],
                "status": active_run["status"]
            }
        )

    run_id = f"run_{uuid.uuid4().hex[:12]}"
    start_dt = datetime.now(timezone.utc).isoformat()
    initial_stages = {
        "ingestion": {"status": "pending" if not skip_ingestion else "skipped"},
        "clustering": {"status": "pending"},
        "story_analysis": {"status": "pending"},
        "global_importance": {"status": "pending"},
        "story_evolution": {"status": "pending"},
        "personal_relevance": {"status": "pending"},
        "feed_readiness": {"status": "pending"}
    }

    # 2. Persist initial queued state
    db_repository.create_pipeline_run(
        run_id=run_id,
        status="queued",
        started_at=start_dt,
        trigger_type=trigger_type,
        user_id=user_id,
        skip_ingestion=skip_ingestion,
        stages=initial_stages
    )

    # 3. Dispatch to background execution
    background_tasks.add_task(
        pulse_pipeline.run_pipeline,
        skip_ingestion=skip_ingestion,
        time_window_hours=time_window_hours,
        analysis_limit=analysis_limit,
        importance_limit=importance_limit,
        evolution_limit=evolution_limit,
        feed_limit=feed_limit,
        user_id=user_id,
        trigger_type=trigger_type,
        run_id=run_id
    )

    # 4. Return accepted response immediately
    return {
        "status": "accepted",
        "run_id": run_id,
        "message": "Pipeline execution queued."
    }


@router.get("/pipeline/status", tags=["pipeline"])
async def get_pipeline_status() -> Dict[str, Any]:
    """
    Returns metrics and stage summaries from the most recent pipeline execution.
    """
    last_run = pulse_pipeline.get_last_run()
    if not last_run:
        return {
            "status": "never_run",
            "message": "No pipeline run has completed yet. Trigger via POST /api/pipeline/run."
        }
    return last_run


@router.get("/pipeline/runs", tags=["pipeline"])
async def get_pipeline_runs(
    limit: int = Query(20, ge=1, le=100, description="Max number of recent pipeline runs to return")
) -> List[Dict[str, Any]]:
    """
    Returns recent pipeline executions ordered newest first.
    """
    return db_repository.get_pipeline_runs(limit=limit)
