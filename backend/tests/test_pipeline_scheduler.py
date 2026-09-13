"""
Tests for Phase 8.2 Step 3: Automatic Pipeline Scheduler.
Validates scheduler configuration, lifecycle, tick execution, concurrency protection,
status exposure, and API compatibility.
"""
import pytest
from unittest.mock import patch
from datetime import datetime, timezone
from fastapi.testclient import TestClient

from backend.app.main import app
from backend.app.core.config import settings
from backend.app.core.db_repository import db_repository
from backend.app.services.pulse_pipeline import pulse_pipeline
from backend.app.services.pipeline_scheduler import PipelineScheduler, pipeline_scheduler


def mock_feed_fetch(source_id: str, max_articles: int = 10):
    """Mock articles for scheduler tests without internet access."""
    return [
        {
            "title": f"Scheduler Test Article from {source_id}",
            "url": f"https://test.example.com/{source_id}/article1",
            "source_id": source_id,
            "category": "technology",
            "published_at": datetime.now(timezone.utc).isoformat(),
            "raw_summary": "Testing scheduled pipeline execution."
        }
    ]


@pytest.fixture
def clean_scheduler_db(tmp_path):
    """Sets up an isolated clean SQLite database for scheduler tests."""
    test_db = tmp_path / "test_scheduler.db"
    orig_path = db_repository.db_path
    db_repository.db_path = str(test_db)
    db_repository.init_db()

    # Pre-register default sources
    with db_repository._get_connection() as conn:
        conn.execute("""
        INSERT OR REPLACE INTO sources (id, name, base_url, feed_url, category, reliability_score, enabled)
        VALUES ('hackernews', 'Hacker News', 'https://news.ycombinator.com', 'https://news.ycombinator.com/rss', 'technology', 0.9, 1),
               ('arstechnica', 'Ars Technica', 'https://arstechnica.com', 'https://feeds.arstechnica.com/arstechnica/index', 'technology', 0.9, 1)
        """)
        conn.commit()

    # Reset in-memory pipeline cache
    orig_last_run = pulse_pipeline._last_run
    pulse_pipeline._last_run = None

    yield db_repository

    db_repository.db_path = orig_path
    pulse_pipeline._last_run = orig_last_run
    # Ensure scheduler is stopped if running
    if pipeline_scheduler.is_running():
        pipeline_scheduler.shutdown(wait=False)


@pytest.fixture
def client():
    return TestClient(app)


def test_scheduler_configuration_loads_correctly():
    """Verifies that scheduler settings are properly configured and typed."""
    assert hasattr(settings, "SCHEDULER_ENABLED")
    assert isinstance(settings.SCHEDULER_ENABLED, bool)
    assert hasattr(settings, "SCHEDULER_INTERVAL_MINUTES")
    assert isinstance(settings.SCHEDULER_INTERVAL_MINUTES, int)
    assert settings.SCHEDULER_INTERVAL_MINUTES > 0


def test_disabled_scheduler_does_not_start():
    """Verifies that a disabled scheduler will not start."""
    scheduler = PipelineScheduler(enabled=False, interval_minutes=15)
    started = scheduler.start()
    assert started is False
    assert scheduler.is_running() is False
    status = scheduler.get_status()
    assert status["enabled"] is False
    assert status["status"] == "disabled"
    assert status["running"] is False
    assert status["next_run_time"] is None


def test_scheduler_start_and_shutdown_cleanly():
    """Verifies starting, next run time calculation, and clean shutdown."""
    scheduler = PipelineScheduler(enabled=True, interval_minutes=20)
    assert scheduler.is_running() is False

    started = scheduler.start()
    assert started is True
    assert scheduler.is_running() is True

    status = scheduler.get_status()
    assert status["enabled"] is True
    assert status["status"] == "running"
    assert status["running"] is True
    assert status["interval_minutes"] == 20
    assert status["next_run_time"] is not None

    # Idempotent start: calling start again while running returns True without error
    assert scheduler.start() is True
    assert scheduler.is_running() is True

    # Shutdown
    scheduler.shutdown(wait=False)
    assert scheduler.is_running() is False
    assert scheduler.get_next_run_time() is None

    post_status = scheduler.get_status()
    assert post_status["status"] == "stopped"
    assert post_status["running"] is False


def test_scheduler_uses_configured_interval():
    """Verifies that the scheduler configures APScheduler with the specified interval."""
    custom_interval = 45
    scheduler = PipelineScheduler(enabled=True, interval_minutes=custom_interval)
    scheduler.start()
    assert scheduler.interval_minutes == custom_interval

    job = scheduler._scheduler.get_job(scheduler.JOB_ID)
    assert job is not None
    # Verify trigger interval in minutes
    assert job.trigger.interval.total_seconds() == custom_interval * 60

    scheduler.shutdown(wait=False)


def test_scheduled_tick_triggers_pipeline_run(clean_scheduler_db):
    """Verifies that execute_tick() triggers a complete pipeline execution when no active run exists."""
    scheduler = PipelineScheduler(enabled=True)

    with patch.object(pulse_pipeline.ingestion.fetcher, "fetch_source_feed", side_effect=mock_feed_fetch):
        summary = scheduler.execute_tick()

    assert summary is not None
    assert summary["status"] in ("success", "partial_failure")
    run_id = summary["run_id"]
    assert summary["trigger_type"] == "scheduler"

    # Verify run record in DB
    db_run = clean_scheduler_db.get_pipeline_run(run_id)
    assert db_run is not None
    assert db_run["trigger_type"] == "scheduler"
    assert db_run["status"] in ("success", "partial_failure")

    # Verify scheduler metadata tracking
    assert scheduler._last_triggered_run_id == run_id
    assert scheduler._last_triggered_at is not None
    status = scheduler.get_status()
    assert status["last_triggered_run_id"] == run_id


def test_scheduled_tick_skips_when_active_run_exists(clean_scheduler_db):
    """Verifies that execute_tick() skips if a pipeline run is already queued or running."""
    scheduler = PipelineScheduler(enabled=True)

    # 1. Create a simulated active run
    active_run_id = "run_active_sim_01"
    clean_scheduler_db.create_pipeline_run(
        run_id=active_run_id,
        status="running",
        started_at=datetime.now(timezone.utc).isoformat(),
        trigger_type="api",
        user_id="default_user"
    )

    # 2. Trigger scheduled tick
    with patch.object(pulse_pipeline, "run_pipeline") as mock_run:
        result = scheduler.execute_tick()
        # Must not run the pipeline
        mock_run.assert_not_called()

    assert result is None
    assert scheduler._last_skipped_at is not None
    assert active_run_id in scheduler._last_skip_reason
    assert "running" in scheduler._last_skip_reason

    status = scheduler.get_status()
    assert status["last_skipped_at"] is not None
    assert active_run_id in status["last_skip_reason"]


def test_scheduled_tick_skips_when_queued_run_exists(clean_scheduler_db):
    """Verifies that execute_tick() skips even when the active run is in queued state."""
    scheduler = PipelineScheduler(enabled=True)

    # 1. Create a queued run
    queued_run_id = "run_queued_sim_02"
    clean_scheduler_db.create_pipeline_run(
        run_id=queued_run_id,
        status="queued",
        started_at=datetime.now(timezone.utc).isoformat(),
        trigger_type="api",
        user_id="default_user"
    )

    # 2. Trigger scheduled tick
    result = scheduler.execute_tick()
    assert result is None
    assert scheduler._last_skipped_at is not None
    assert queued_run_id in scheduler._last_skip_reason
    assert "queued" in scheduler._last_skip_reason


def test_scheduled_execution_concurrency_rejection_for_subsequent_api_run(clean_scheduler_db, client):
    """Verifies that while scheduled run is queued/running, POST /api/pipeline/run is rejected with 409."""
    # Simulate scheduler queuing a run
    sched_run_id = "run_sched_in_flight"
    clean_scheduler_db.create_pipeline_run(
        run_id=sched_run_id,
        status="running",
        started_at=datetime.now(timezone.utc).isoformat(),
        trigger_type="scheduler",
        user_id="default_user"
    )

    # Concurrent API run attempt
    resp = client.post("/api/pipeline/run")
    assert resp.status_code == 409
    body = resp.json()
    assert body["detail"]["active_run_id"] == sched_run_id
    assert body["detail"]["status"] == "running"


def test_api_pipeline_status_backward_compatibility_and_scheduler_fields(clean_scheduler_db, client):
    """
    Verifies that GET /api/pipeline/status:
    1. Returns 'never_run' with scheduler info when no run exists
    2. Preserves legacy top-level pipeline fields after a run
    3. Exposes nested 'pipeline' and 'scheduler' objects
    """
    # 1. Status before any run
    init_resp = client.get("/api/pipeline/status")
    assert init_resp.status_code == 200
    init_data = init_resp.json()
    assert init_data["status"] == "never_run"
    assert "scheduler" in init_data
    assert init_data["scheduler"]["enabled"] == settings.SCHEDULER_ENABLED
    assert "pipeline" in init_data

    # 2. Trigger pipeline run via API
    with patch.object(pulse_pipeline.ingestion.fetcher, "fetch_source_feed", side_effect=mock_feed_fetch):
        post_resp = client.post("/api/pipeline/run?skip_ingestion=false")
        assert post_resp.status_code == 200
        run_id = post_resp.json()["run_id"]

    # 3. Status after run completes
    status_resp = client.get("/api/pipeline/status")
    assert status_resp.status_code == 200
    status_data = status_resp.json()

    # Legacy backward-compatible top-level keys
    assert status_data["run_id"] == run_id
    assert status_data["status"] in ("success", "partial_failure")
    assert status_data["total_duration_seconds"] >= 0
    assert "stages" in status_data

    # Nested contract keys
    assert "pipeline" in status_data
    assert status_data["pipeline"]["run_id"] == run_id
    assert "scheduler" in status_data
    assert "enabled" in status_data["scheduler"]
    assert "status" in status_data["scheduler"]
    assert "interval_minutes" in status_data["scheduler"]


def test_api_pipeline_scheduler_endpoint(client):
    """Verifies GET /api/pipeline/scheduler returns operational status."""
    resp = client.get("/api/pipeline/scheduler")
    assert resp.status_code == 200
    data = resp.json()
    assert "enabled" in data
    assert "status" in data
    assert "running" in data
    assert "interval_minutes" in data
    assert "next_run_time" in data


def test_api_system_health_includes_scheduler(clean_scheduler_db, client):
    """Verifies GET /api/system/health includes scheduler metadata."""
    resp = client.get("/api/system/health")
    assert resp.status_code == 200
    data = resp.json()
    assert "scheduler" in data
    assert "status" in data["scheduler"]
    assert "interval_minutes" in data["scheduler"]


def test_fastapi_lifespan_lifecycle_management():
    """Verifies that FastAPI lifespan cleanly starts and shuts down the scheduler."""
    # Ensure scheduler is stopped initially
    if pipeline_scheduler.is_running():
        pipeline_scheduler.shutdown(wait=False)

    with TestClient(app) as test_client:
        # Inside lifespan context
        if settings.SCHEDULER_ENABLED:
            assert pipeline_scheduler.is_running() is True
            assert pipeline_scheduler.get_next_run_time() is not None

        resp = test_client.get("/api/pipeline/scheduler")
        assert resp.status_code == 200

    # Outside lifespan context (shutdown called)
    assert pipeline_scheduler.is_running() is False
