import uuid
import logging
from datetime import datetime, timezone
from typing import Optional, Dict, Any, List
from fastapi import APIRouter, Query, BackgroundTasks, HTTPException, Body
from pydantic import BaseModel, Field

from backend.app.core.db_repository import db_repository
from backend.app.services.pulse_pipeline import pulse_pipeline
from backend.app.services.pipeline_scheduler import pipeline_scheduler

logger = logging.getLogger("pulse.api.pipeline")
router = APIRouter()


class SchedulerConfigUpdate(BaseModel):
    interval_minutes: Optional[int] = Field(None, description="Interval between pipeline runs in minutes (>= 1)")
    enabled: Optional[bool] = Field(None, description="Whether the scheduler is enabled")


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

    # 1. Atomically acquire active pipeline run slot (Phase 9.1 Step 3)
    acquisition = db_repository.acquire_active_pipeline_run(
        run_id=run_id,
        status="queued",
        started_at=start_dt,
        trigger_type=trigger_type,
        user_id=user_id,
        skip_ingestion=skip_ingestion,
        stages=initial_stages
    )

    if not acquisition["acquired"]:
        active = acquisition.get("active_run") or {}
        raise HTTPException(
            status_code=409,
            detail={
                "message": "A pipeline execution is already in progress.",
                "active_run_id": active.get("run_id"),
                "status": active.get("status")
            }
        )

    # 2. Dispatch to background execution
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
    Returns metrics and stage summaries from the most recent pipeline execution,
    alongside automatic scheduler operational status and failure metrics (Phase 8.2 Step 4).
    """
    last_run = pulse_pipeline.get_last_run()
    scheduler_status = pipeline_scheduler.get_status()
    failure_stats = db_repository.get_failure_stats()

    if not last_run:
        return {
            "status": "never_run",
            "message": "No pipeline run has completed yet. Trigger via POST /api/pipeline/run.",
            "pipeline": None,
            "scheduler": scheduler_status,
            "consecutive_failure_count": failure_stats["consecutive_failure_count"],
            "last_failure_at": failure_stats["last_failure_at"],
            "last_failure_message": failure_stats["last_failure_message"]
        }

    # Backward compatible: preserve all last_run keys at top-level
    response = dict(last_run)
    response["pipeline"] = last_run
    response["scheduler"] = scheduler_status
    response["consecutive_failure_count"] = failure_stats["consecutive_failure_count"]
    response["last_failure_at"] = failure_stats["last_failure_at"]
    response["last_failure_message"] = failure_stats["last_failure_message"]
    return response


@router.get("/pipeline/scheduler", tags=["pipeline"])
async def get_scheduler_status() -> Dict[str, Any]:
    """
    Returns operational status of the automatic pipeline scheduler (Phase 8.2 Steps 3 & 4).
    """
    return pipeline_scheduler.get_status()


@router.post("/pipeline/scheduler/start", tags=["pipeline"])
async def start_scheduler() -> Dict[str, Any]:
    """
    Starts the automatic pipeline scheduler (Phase 8.2 Step 4).
    """
    pipeline_scheduler.start()
    return pipeline_scheduler.get_status()


@router.post("/pipeline/scheduler/stop", tags=["pipeline"])
async def stop_scheduler() -> Dict[str, Any]:
    """
    Stops the automatic pipeline scheduler without aborting active runs (Phase 8.2 Step 4).
    """
    pipeline_scheduler.stop(wait=False)
    return pipeline_scheduler.get_status()


@router.post("/pipeline/scheduler/pause", tags=["pipeline"])
async def pause_scheduler() -> Dict[str, Any]:
    """
    Pauses automatic pipeline scheduler ticks without terminating active runs (Phase 8.2 Step 4).
    """
    pipeline_scheduler.pause()
    return pipeline_scheduler.get_status()


@router.post("/pipeline/scheduler/resume", tags=["pipeline"])
async def resume_scheduler() -> Dict[str, Any]:
    """
    Resumes automatic pipeline scheduler ticks (Phase 8.2 Step 4).
    """
    pipeline_scheduler.resume()
    return pipeline_scheduler.get_status()


@router.post("/pipeline/scheduler/config", tags=["pipeline"])
async def configure_scheduler(
    config: Optional[SchedulerConfigUpdate] = Body(default=None),
    interval_minutes: Optional[int] = Query(None, description="Interval in minutes (>= 1)"),
    enabled: Optional[bool] = Query(None, description="Enable or disable scheduler")
) -> Dict[str, Any]:
    """
    Configures runtime scheduler properties including interval and enabled state (Phase 8.2 Step 4).
    """
    int_mins = None
    en = None
    if config:
        if config.interval_minutes is not None:
            int_mins = config.interval_minutes
        if config.enabled is not None:
            en = config.enabled

    if interval_minutes is not None:
        int_mins = interval_minutes
    if enabled is not None:
        en = enabled

    if int_mins is not None and int_mins < 1:
        raise HTTPException(
            status_code=400,
            detail="interval_minutes must be a positive integer greater than or equal to 1"
        )

    try:
        return pipeline_scheduler.configure(interval_minutes=int_mins, enabled=en)
    except ValueError as val_err:
        raise HTTPException(status_code=400, detail=str(val_err))


@router.get("/pipeline/runs", tags=["pipeline"])
async def get_pipeline_runs(
    limit: int = Query(20, ge=1, le=100, description="Max number of recent pipeline runs to return"),
    status: Optional[str] = Query(None, description="Filter by status (e.g. success, failed, partial_failure, running, queued)"),
    trigger_type: Optional[str] = Query(None, description="Filter by trigger type (e.g. manual, scheduler, api)")
) -> List[Dict[str, Any]]:
    """
    Returns recent pipeline executions ordered newest first, with optional status and trigger filtering (Phase 8.2 Step 4).
    """
    return db_repository.get_pipeline_runs(limit=limit, status=status, trigger_type=trigger_type)


@router.post("/pipeline/runs/active/abort", tags=["pipeline"])
@router.post("/pipeline/abort", tags=["pipeline"], include_in_schema=False)
async def abort_active_pipeline_run() -> Dict[str, Any]:
    """
    Aborts any currently active (queued or running) pipeline run (Phase 9.1 Step 2).
    Transitions the active run to 'interrupted' status, marks completed_at,
    and records error_message = 'Manually aborted by operator'.
    If no run is active, returns a clean response indicating no active run exists.
    """
    aborted_run = db_repository.abort_active_pipeline_run()
    if not aborted_run:
        return {
            "status": "no_active_run",
            "run_id": None,
            "error_message": None,
            "message": "No active pipeline run to abort."
        }

    return {
        "status": "interrupted",
        "run_id": aborted_run["run_id"],
        "error_message": aborted_run.get("error_message") or "Manually aborted by operator",
        "message": f"Pipeline run '{aborted_run['run_id']}' manually aborted by operator.",
        "run": aborted_run
    }


@router.get("/pipeline/runs/{run_id}", tags=["pipeline"])
async def get_pipeline_run_detail(run_id: str) -> Dict[str, Any]:
    """
    Returns the complete persisted execution record for a specific pipeline run (Phase 8.2 Step 4).
    Raises HTTP 404 if the run_id does not exist.
    """
    run = db_repository.get_pipeline_run(run_id)
    if not run:
        raise HTTPException(status_code=404, detail=f"Pipeline run '{run_id}' not found")
    return run
