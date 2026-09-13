"""
Automatic Pipeline Scheduler Service (Phase 8.2 Steps 3 & 4).
Periodically triggers the Pulse intelligence pipeline in the background using APScheduler.
Provides operational start, stop, pause, resume, configuration, and status controls.
"""
import uuid
import logging
import asyncio
import concurrent.futures
from datetime import datetime, timezone
from typing import Optional, Dict, Any

from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.interval import IntervalTrigger

from backend.app.core.config import settings
from backend.app.core.db_repository import db_repository
from backend.app.services.pulse_pipeline import pulse_pipeline

logger = logging.getLogger("pulse.services.pipeline_scheduler")


class PipelineScheduler:
    """
    Dedicated scheduler service responsible for periodic background execution of the Pulse pipeline.
    Uses APScheduler's BackgroundScheduler to run triggers without blocking the FastAPI event loop.
    """
    JOB_ID = "pulse_pipeline_scheduled_run"
    STALE_JOB_ID = "pulse_pipeline_stale_recovery"

    def __init__(
        self,
        enabled: Optional[bool] = None,
        interval_minutes: Optional[int] = None
    ):
        self.enabled: bool = (
            enabled if enabled is not None else settings.SCHEDULER_ENABLED
        )
        self.interval_minutes: int = (
            interval_minutes if interval_minutes is not None else settings.SCHEDULER_INTERVAL_MINUTES
        )
        self.paused: bool = False
        self._scheduler: Optional[BackgroundScheduler] = None
        self._stale_scheduler: Optional[BackgroundScheduler] = None
        self._last_triggered_run_id: Optional[str] = None
        self._last_triggered_at: Optional[str] = None
        self._last_skipped_at: Optional[str] = None
        self._last_skip_reason: Optional[str] = None
        # Stale run detection & recovery state (Phase 9.1 Step 4)
        self.stale_timeout_seconds: int = getattr(settings, "PIPELINE_STALE_TIMEOUT_SECONDS", 600)
        self.stale_check_interval_seconds: int = getattr(settings, "PIPELINE_STALE_CHECK_INTERVAL_SECONDS", 60)
        self._last_stale_recovery_at: Optional[str] = None
        self._last_stale_reclaimed_count: int = 0

    def is_running(self) -> bool:
        """Checks if the background scheduler is currently active."""
        return bool(self._scheduler and self._scheduler.running)

    def is_paused(self) -> bool:
        """Checks if the background scheduler is running but paused."""
        return bool(self.is_running() and self.paused)

    def start(self, interval_minutes: Optional[int] = None) -> bool:
        """
        Starts the automatic pipeline scheduler if enabled.
        Idempotent: will not launch duplicate scheduler instances if already running.
        If paused, calling start resumes the scheduler.
        """
        if interval_minutes is not None:
            self.interval_minutes = interval_minutes

        if not self.enabled:
            logger.info("[SCHEDULER] Automatic pipeline scheduler is disabled by configuration.")
            return False

        if self.is_running():
            if self.paused:
                self.resume()
            else:
                logger.warning("[SCHEDULER] Scheduler is already running. Skipping duplicate start.")
            return True

        self._scheduler = BackgroundScheduler(timezone="UTC")
        self._scheduler.add_job(
            func=self.execute_tick,
            trigger=IntervalTrigger(minutes=self.interval_minutes),
            id=self.JOB_ID,
            name="Pulse Pipeline Periodic Trigger",
            replace_existing=True,
            coalesce=True,
            max_instances=1
        )
        self._scheduler.start()

        self._stale_scheduler = BackgroundScheduler(timezone="UTC")
        self._stale_scheduler.add_job(
            func=self.reconcile_stale_runs,
            trigger=IntervalTrigger(seconds=self.stale_check_interval_seconds),
            id=self.STALE_JOB_ID,
            name="Pulse Pipeline Stale Run Self-Healing Monitor",
            replace_existing=True,
            coalesce=True,
            max_instances=1
        )
        self._stale_scheduler.start()

        self.paused = False
        logger.info(
            f"[SCHEDULER] Pipeline scheduler started with interval={self.interval_minutes}m. "
            f"Next run at: {self.get_next_run_time()}"
        )
        return True

    def stop(self, wait: bool = False) -> bool:
        """
        Cleanly terminates the background scheduler without aborting in-flight pipeline runs.
        Idempotent: safe to call repeatedly.
        """
        stopped = False
        if self._scheduler and self._scheduler.running:
            logger.info("[SCHEDULER] Stopping automatic pipeline scheduler...")
            self._scheduler.shutdown(wait=wait)
            stopped = True
        if self._stale_scheduler and self._stale_scheduler.running:
            self._stale_scheduler.shutdown(wait=wait)
            stopped = True

        self.paused = False
        if stopped:
            logger.info("[SCHEDULER] Pipeline scheduler and stale monitor stopped.")
            return True
        return False

    def shutdown(self, wait: bool = False) -> None:
        """Alias for stop() for lifecycle hooks."""
        self.stop(wait=wait)

    def pause(self) -> bool:
        """
        Pauses future scheduled ticks without terminating any currently running pipeline.
        Idempotent: safe to call repeatedly.
        """
        if not self.is_running():
            logger.warning("[SCHEDULER] Cannot pause: scheduler is not running.")
            return False

        if not self.paused:
            job = self._scheduler.get_job(self.JOB_ID)
            if job:
                self._scheduler.pause_job(self.JOB_ID)
            self.paused = True
            logger.info("[SCHEDULER] Pipeline scheduler paused.")
        return True

    def resume(self) -> bool:
        """
        Resumes scheduled ticks. If scheduler was stopped, starts it.
        Idempotent: safe to call repeatedly.
        """
        if not self.is_running():
            return self.start()

        if self.paused:
            job = self._scheduler.get_job(self.JOB_ID)
            if job:
                self._scheduler.resume_job(self.JOB_ID)
            self.paused = False
            logger.info("[SCHEDULER] Pipeline scheduler resumed.")
        return True

    def configure(
        self,
        interval_minutes: Optional[int] = None,
        enabled: Optional[bool] = None
    ) -> Dict[str, Any]:
        """
        Updates runtime scheduler configuration without requiring application restart.
        Validates interval_minutes >= 1 and reschedules the job in place without duplication.
        """
        if interval_minutes is not None:
            if not isinstance(interval_minutes, int) or interval_minutes < 1:
                raise ValueError("interval_minutes must be an integer greater than or equal to 1")
            if interval_minutes != self.interval_minutes:
                self.interval_minutes = interval_minutes
                if self.is_running() and self._scheduler:
                    self._scheduler.reschedule_job(
                        self.JOB_ID,
                        trigger=IntervalTrigger(minutes=self.interval_minutes)
                    )
                    logger.info(f"[SCHEDULER] Rescheduled job with new interval: {self.interval_minutes}m")

        if enabled is not None:
            self.enabled = bool(enabled)
            if not self.enabled and self.is_running():
                self.stop(wait=False)
            elif self.enabled and not self.is_running():
                self.start()

        return self.get_status()

    def get_next_run_time(self) -> Optional[str]:
        """Returns the ISO-8601 formatted timestamp of the next scheduled tick, or None."""
        if not self.is_running() or not self._scheduler or self.paused:
            return None
        job = self._scheduler.get_job(self.JOB_ID)
        if job and job.next_run_time:
            return job.next_run_time.isoformat()
        return None

    def reconcile_stale_runs(self) -> int:
        """
        Periodically checks for and reconciles genuinely stale or abandoned pipeline runs (Phase 9.1 Step 4).
        Runs safely in the background, does not create pipeline runs, and does not count as a pipeline failure.
        """
        try:
            reclaimed = db_repository.reconcile_stale_pipeline_runs(
                stale_timeout_seconds=self.stale_timeout_seconds
            )
            self._last_stale_recovery_at = datetime.now(timezone.utc).isoformat()
            self._last_stale_reclaimed_count = reclaimed
            if reclaimed > 0:
                logger.warning(
                    f"[SCHEDULER] Stale run self-healing monitor reclaimed {reclaimed} stale pipeline run(s) -> marked as interrupted."
                )
            return reclaimed
        except Exception as e:
            logger.error(f"[SCHEDULER] Error during stale pipeline run reconciliation: {e}", exc_info=True)
            return 0

    def get_status(self) -> Dict[str, Any]:
        """
        Exposes current scheduler status, configuration, execution metadata, and failure tracking.
        """
        running = self.is_running()
        paused = bool(running and self.paused)

        if not self.enabled:
            status_label = "disabled"
        elif running:
            status_label = "paused" if paused else "running"
        else:
            status_label = "stopped"

        latest_run = pulse_pipeline.get_last_run()
        last_run_status = latest_run.get("status") if latest_run else None
        failure_stats = db_repository.get_failure_stats()

        return {
            "enabled": self.enabled,
            "running": running,
            "paused": paused,
            "status": status_label,
            "interval_minutes": self.interval_minutes,
            "next_run_time": self.get_next_run_time(),
            "last_triggered_run_id": self._last_triggered_run_id,
            "last_triggered_at": self._last_triggered_at,
            "last_skipped_at": self._last_skipped_at,
            "last_skip_reason": self._last_skip_reason,
            "last_run_status": last_run_status,
            "consecutive_failure_count": failure_stats["consecutive_failure_count"],
            "last_failure_at": failure_stats["last_failure_at"],
            "last_failure_message": failure_stats["last_failure_message"],
            "stale_timeout_seconds": self.stale_timeout_seconds,
            "last_stale_recovery_at": self._last_stale_recovery_at,
            "last_stale_reclaimed_count": self._last_stale_reclaimed_count
        }

    def execute_tick(self) -> Optional[Dict[str, Any]]:
        """
        Executes a scheduled pipeline tick using atomic database active-run acquisition (Phase 9.1 Step 3).
        Atomically checks for and acquires the active run slot.
        If busy, skips execution and logs the event without failure metrics.
        Otherwise proceeds with execution via PulsePipeline in a background thread.
        """
        # Phase 9.1 Step 4: Reconcile any abandoned stale runs before checking active status
        try:
            self.reconcile_stale_runs()
        except Exception as e:
            logger.warning(f"[SCHEDULER] Pre-tick stale reconciliation check failed: {e}")

        logger.info("[SCHEDULER] Scheduled tick triggered. Attempting atomic pipeline acquisition...")

        run_id = f"run_{uuid.uuid4().hex[:12]}"
        start_dt = datetime.now(timezone.utc).isoformat()
        initial_stages = {
            "ingestion": {"status": "pending"},
            "clustering": {"status": "pending"},
            "story_analysis": {"status": "pending"},
            "global_importance": {"status": "pending"},
            "story_evolution": {"status": "pending"},
            "personal_relevance": {"status": "pending"},
            "feed_readiness": {"status": "pending"}
        }

        # Atomically check and acquire active run slot
        acquisition = db_repository.acquire_active_pipeline_run(
            run_id=run_id,
            status="queued",
            started_at=start_dt,
            trigger_type="scheduler",
            user_id="default_user",
            skip_ingestion=False,
            stages=initial_stages
        )

        if not acquisition["acquired"]:
            active = acquisition.get("active_run") or {}
            self._last_skipped_at = datetime.now(timezone.utc).isoformat()
            self._last_skip_reason = f"Active run {active.get('run_id', 'unknown')} ({active.get('status', 'active')}) in progress"
            logger.info(f"[SCHEDULER] {self._last_skip_reason}. Skipping scheduled tick.")
            return None

        self._last_triggered_run_id = run_id
        self._last_triggered_at = start_dt

        logger.info(f"[SCHEDULER] Queued scheduled run {run_id}. Executing pipeline...")

        # 4. Execute pipeline in scheduler worker thread (coroutine runner)
        try:
            summary = self._run_coroutine(
                pulse_pipeline.run_pipeline(
                    skip_ingestion=False,
                    trigger_type="scheduler",
                    run_id=run_id,
                    user_id="default_user"
                )
            )
            logger.info(f"[SCHEDULER] Scheduled run {run_id} completed with status: {summary.get('status')}")
            return summary
        except Exception as e:
            logger.error(f"[SCHEDULER] Error during scheduled execution of run {run_id}: {e}", exc_info=True)
            return None

    def _run_coroutine(self, coro):
        """Helper to run a coroutine whether called from a thread or an existing event loop."""
        try:
            loop = asyncio.get_running_loop()
        except RuntimeError:
            loop = None

        if loop and loop.is_running():
            with concurrent.futures.ThreadPoolExecutor(max_workers=1) as executor:
                return executor.submit(asyncio.run, coro).result()
        else:
            return asyncio.run(coro)

    def trigger_now(self) -> Optional[Dict[str, Any]]:
        """Convenience method to manually trigger a scheduled tick immediately."""
        return self.execute_tick()


pipeline_scheduler = PipelineScheduler()
