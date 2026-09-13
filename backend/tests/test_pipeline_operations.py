"""
Comprehensive Tests for Phase 8.2 Step 4: Pipeline Operations & Observability.
Covers run history, filtering, detail endpoints, 404 handling, scheduler controls (start/stop/pause/resume),
runtime configuration, job deduplication, failure tracking, and health operational blocks.
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
    """Mock articles for operational tests without internet access."""
    return [
        {
            "title": f"Operations Test Article from {source_id}",
            "url": f"https://test.example.com/{source_id}/article1",
            "source_id": source_id,
            "category": "technology",
            "published_at": datetime.now(timezone.utc).isoformat(),
            "raw_summary": "Testing pipeline operational observability."
        }
    ]


@pytest.fixture
def clean_ops_db(tmp_path):
    """Sets up an isolated clean SQLite database for operations tests."""
    test_db = tmp_path / "test_ops.db"
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

    orig_last_run = pulse_pipeline._last_run
    pulse_pipeline._last_run = None

    yield db_repository

    db_repository.db_path = orig_path
    pulse_pipeline._last_run = orig_last_run
    if pipeline_scheduler.is_running():
        pipeline_scheduler.stop(wait=False)


@pytest.fixture
def client():
    return TestClient(app)


# ==============================================================================
# 1. Pipeline Run History
# ==============================================================================

def test_1_pipeline_run_history(clean_ops_db, client):
    """Verifies GET /api/pipeline/runs returns historical executions with operational metrics."""
    clean_ops_db.create_pipeline_run(
        run_id="run_hist_01",
        status="success",
        trigger_type="manual",
        started_at=datetime.now(timezone.utc).isoformat(),
        duration_seconds=5.2,
        total_articles=10,
        stages={"ingestion": {"duplicates": 4, "failed_sources": 0}, "personal_relevance": {"stories_evaluated": 8}}
    )

    resp = client.get("/api/pipeline/runs?limit=10")
    assert resp.status_code == 200
    runs = resp.json()
    assert len(runs) >= 1
    r0 = runs[0]
    assert r0["run_id"] == "run_hist_01"
    assert r0["status"] == "success"
    assert r0["trigger_type"] == "manual"
    assert r0["duplicate_articles"] == 4
    assert r0["failed_ingestion_sources"] == 0
    assert r0["stories_relevance_scored"] == 8


# ==============================================================================
# 2. Run Filtering by Status
# ==============================================================================

def test_2_run_filtering_by_status(clean_ops_db, client):
    """Verifies GET /api/pipeline/runs?status=... filters runs appropriately."""
    clean_ops_db.create_pipeline_run(run_id="run_succ_01", status="success")
    clean_ops_db.create_pipeline_run(run_id="run_fail_01", status="failed")
    clean_ops_db.create_pipeline_run(run_id="run_part_01", status="partial_failure")

    succ_resp = client.get("/api/pipeline/runs?status=success")
    assert succ_resp.status_code == 200
    succ_runs = succ_resp.json()
    assert all(r["status"] == "success" for r in succ_runs)
    assert any(r["run_id"] == "run_succ_01" for r in succ_runs)

    fail_resp = client.get("/api/pipeline/runs?status=failed")
    assert fail_resp.status_code == 200
    fail_runs = fail_resp.json()
    assert all(r["status"] == "failed" for r in fail_runs)
    assert any(r["run_id"] == "run_fail_01" for r in fail_runs)


# ==============================================================================
# 3. Run Filtering by Trigger Type
# ==============================================================================

def test_3_run_filtering_by_trigger_type(clean_ops_db, client):
    """Verifies GET /api/pipeline/runs?trigger_type=... filters runs appropriately."""
    clean_ops_db.create_pipeline_run(run_id="run_trig_sched", status="success", trigger_type="scheduler")
    clean_ops_db.create_pipeline_run(run_id="run_trig_api", status="success", trigger_type="api")
    clean_ops_db.create_pipeline_run(run_id="run_trig_manual", status="success", trigger_type="manual")

    sched_resp = client.get("/api/pipeline/runs?trigger_type=scheduler")
    assert sched_resp.status_code == 200
    sched_runs = sched_resp.json()
    assert all(r["trigger_type"] == "scheduler" for r in sched_runs)
    assert any(r["run_id"] == "run_trig_sched" for r in sched_runs)


# ==============================================================================
# 4. Run Detail Endpoint
# ==============================================================================

def test_4_run_detail_endpoint(clean_ops_db, client):
    """Verifies GET /api/pipeline/runs/{run_id} returns the complete execution record."""
    clean_ops_db.create_pipeline_run(
        run_id="run_detail_target",
        status="success",
        trigger_type="scheduler",
        started_at="2026-09-13T10:00:00Z",
        completed_at="2026-09-13T10:00:08Z",
        duration_seconds=8.0,
        stages={
            "ingestion": {"status": "success", "duration_seconds": 3.2},
            "clustering": {"status": "success", "duration_seconds": 1.1}
        }
    )

    resp = client.get("/api/pipeline/runs/run_detail_target")
    assert resp.status_code == 200
    detail = resp.json()
    assert detail["run_id"] == "run_detail_target"
    assert detail["status"] == "success"
    assert detail["trigger_type"] == "scheduler"
    assert "stages" in detail
    assert detail["stages"]["ingestion"]["duration_seconds"] == 3.2


# ==============================================================================
# 5. Missing Run Returns 404
# ==============================================================================

def test_5_missing_run_returns_404(clean_ops_db, client):
    """Verifies GET /api/pipeline/runs/{run_id} returns HTTP 404 for an unknown run_id."""
    resp = client.get("/api/pipeline/runs/non_existent_run_9999")
    assert resp.status_code == 404
    body = resp.json()
    assert "not found" in body["detail"].lower()


# ==============================================================================
# 6. Scheduler Start
# ==============================================================================

def test_6_scheduler_start(client):
    """Verifies POST /api/pipeline/scheduler/start starts the scheduler."""
    if pipeline_scheduler.is_running():
        pipeline_scheduler.stop(wait=False)

    resp = client.post("/api/pipeline/scheduler/start")
    assert resp.status_code == 200
    data = resp.json()
    assert data["running"] is True
    assert data["status"] == "running"
    assert pipeline_scheduler.is_running() is True


# ==============================================================================
# 7. Scheduler Stop
# ==============================================================================

def test_7_scheduler_stop(client):
    """Verifies POST /api/pipeline/scheduler/stop terminates the scheduler cleanly."""
    pipeline_scheduler.start()
    assert pipeline_scheduler.is_running() is True

    resp = client.post("/api/pipeline/scheduler/stop")
    assert resp.status_code == 200
    data = resp.json()
    assert data["running"] is False
    assert data["status"] == "stopped"
    assert pipeline_scheduler.is_running() is False


# ==============================================================================
# 8. Scheduler Pause
# ==============================================================================

def test_8_scheduler_pause(client):
    """Verifies POST /api/pipeline/scheduler/pause pauses scheduled triggers."""
    pipeline_scheduler.start()
    assert pipeline_scheduler.is_running() is True

    resp = client.post("/api/pipeline/scheduler/pause")
    assert resp.status_code == 200
    data = resp.json()
    assert data["running"] is True
    assert data["paused"] is True
    assert data["status"] == "paused"
    assert data["next_run_time"] is None


# ==============================================================================
# 9. Scheduler Resume
# ==============================================================================

def test_9_scheduler_resume(client):
    """Verifies POST /api/pipeline/scheduler/resume resumes paused scheduled triggers."""
    pipeline_scheduler.start()
    pipeline_scheduler.pause()
    assert pipeline_scheduler.paused is True

    resp = client.post("/api/pipeline/scheduler/resume")
    assert resp.status_code == 200
    data = resp.json()
    assert data["running"] is True
    assert data["paused"] is False
    assert data["status"] == "running"
    assert data["next_run_time"] is not None


# ==============================================================================
# 10. Repeated Start is Safe (Idempotency)
# ==============================================================================

def test_10_repeated_start_is_safe(client):
    """Verifies starting an already started scheduler is idempotent and safe."""
    pipeline_scheduler.start()
    resp1 = client.post("/api/pipeline/scheduler/start")
    assert resp1.status_code == 200
    resp2 = client.post("/api/pipeline/scheduler/start")
    assert resp2.status_code == 200
    assert resp2.json()["running"] is True


# ==============================================================================
# 11. Repeated Stop is Safe (Idempotency)
# ==============================================================================

def test_11_repeated_stop_is_safe(client):
    """Verifies stopping an already stopped scheduler is idempotent and safe."""
    pipeline_scheduler.stop(wait=False)
    resp1 = client.post("/api/pipeline/scheduler/stop")
    assert resp1.status_code == 200
    resp2 = client.post("/api/pipeline/scheduler/stop")
    assert resp2.status_code == 200
    assert resp2.json()["running"] is False


# ==============================================================================
# 12. Runtime Interval Update
# ==============================================================================

def test_12_runtime_interval_update(client):
    """Verifies POST /api/pipeline/scheduler/config updates the interval without restart."""
    pipeline_scheduler.start(interval_minutes=30)
    assert pipeline_scheduler.interval_minutes == 30

    resp = client.post("/api/pipeline/scheduler/config", json={"interval_minutes": 15})
    assert resp.status_code == 200
    data = resp.json()
    assert data["interval_minutes"] == 15
    assert pipeline_scheduler.interval_minutes == 15


# ==============================================================================
# 13. Invalid Interval Rejected
# ==============================================================================

def test_13_invalid_interval_rejected(client):
    """Verifies POST /api/pipeline/scheduler/config rejects zero or negative intervals."""
    resp_zero = client.post("/api/pipeline/scheduler/config", json={"interval_minutes": 0})
    assert resp_zero.status_code == 400

    resp_neg = client.post("/api/pipeline/scheduler/config", json={"interval_minutes": -10})
    assert resp_neg.status_code == 400


# ==============================================================================
# 14. Interval Update Does Not Duplicate Jobs
# ==============================================================================

def test_14_interval_update_does_not_duplicate_jobs(client):
    """Verifies that multiple interval changes update the existing job in-place."""
    pipeline_scheduler.start(interval_minutes=20)
    initial_jobs = len(pipeline_scheduler._scheduler.get_jobs())
    assert initial_jobs == 1

    client.post("/api/pipeline/scheduler/config", json={"interval_minutes": 25})
    client.post("/api/pipeline/scheduler/config", json={"interval_minutes": 35})

    jobs_after = len(pipeline_scheduler._scheduler.get_jobs())
    assert jobs_after == 1
    assert pipeline_scheduler._scheduler.get_job(pipeline_scheduler.JOB_ID) is not None


# ==============================================================================
# 15. Consecutive Failure Counting
# ==============================================================================

def test_15_consecutive_failure_counting(clean_ops_db):
    """Verifies consecutive failures are counted across failed and partial_failure runs."""
    clean_ops_db.create_pipeline_run(
        run_id="run_fail_1",
        status="failed",
        error_message="Fatal crash in ingestion"
    )
    clean_ops_db.create_pipeline_run(
        run_id="run_fail_2",
        status="partial_failure",
        error_message="Stage clustering failed"
    )

    stats = clean_ops_db.get_failure_stats()
    assert stats["consecutive_failure_count"] == 2
    assert stats["last_failure_at"] is not None
    assert "clustering" in stats["last_failure_message"] or "Stage" in stats["last_failure_message"]


# ==============================================================================
# 16. Failure Counter Reset After Success
# ==============================================================================

def test_16_failure_counter_reset_after_success(clean_ops_db):
    """Verifies consecutive failure count resets to 0 when a run succeeds."""
    clean_ops_db.create_pipeline_run(run_id="run_fail_old", status="failed", error_message="Old error")
    clean_ops_db.create_pipeline_run(run_id="run_succ_new", status="success")

    stats = clean_ops_db.get_failure_stats()
    assert stats["consecutive_failure_count"] == 0
    # Historical last failure is still preserved
    assert stats["last_failure_at"] is not None
    assert "Old error" in stats["last_failure_message"]


# ==============================================================================
# 17. Health Endpoint Exposes Operational Metrics
# ==============================================================================

def test_17_health_endpoint_exposes_operational_metrics(clean_ops_db, client):
    """Verifies GET /api/system/health returns enhanced pipeline and scheduler metrics."""
    clean_ops_db.create_pipeline_run(
        run_id="run_health_succ",
        status="success",
        duration_seconds=4.5
    )

    resp = client.get("/api/system/health")
    assert resp.status_code == 200
    health = resp.json()

    assert "pipeline" in health
    p = health["pipeline"]
    assert "consecutive_failure_count" in p
    assert p["consecutive_failure_count"] == 0
    assert "last_failure_at" in p
    assert "last_failure_message" in p

    assert "scheduler" in health
    s = health["scheduler"]
    assert "enabled" in s
    assert "running" in s
    assert "paused" in s
    assert "interval_minutes" in s
    assert "last_run_status" in s


# ==============================================================================
# 18. Scheduler Does Not Overlap Active Pipeline
# ==============================================================================

def test_18_scheduler_does_not_overlap_active_pipeline(clean_ops_db):
    """Verifies scheduler tick skips when another pipeline is currently running."""
    clean_ops_db.create_pipeline_run(
        run_id="run_in_flight",
        status="running",
        started_at=datetime.now(timezone.utc).isoformat()
    )

    scheduler = PipelineScheduler(enabled=True)
    with patch.object(pulse_pipeline, "run_pipeline") as mock_run:
        result = scheduler.execute_tick()
        mock_run.assert_not_called()

    assert result is None
    assert scheduler._last_skipped_at is not None
    assert "run_in_flight" in scheduler._last_skip_reason


# ==============================================================================
# 19. Stopping Scheduler Does Not Stop Active Pipeline
# ==============================================================================

def test_19_stopping_scheduler_does_not_stop_active_pipeline(clean_ops_db):
    """Verifies stopping or pausing the scheduler leaves active pipeline runs untouched."""
    active_id = "run_persisting_during_stop"
    clean_ops_db.create_pipeline_run(
        run_id=active_id,
        status="running",
        started_at=datetime.now(timezone.utc).isoformat()
    )

    scheduler = PipelineScheduler(enabled=True)
    scheduler.start()
    scheduler.pause()
    # Active run record remains in running status
    record_paused = clean_ops_db.get_pipeline_run(active_id)
    assert record_paused["status"] == "running"

    scheduler.stop(wait=False)
    record_stopped = clean_ops_db.get_pipeline_run(active_id)
    assert record_stopped["status"] == "running"


# ==============================================================================
# 20. Existing Pipeline Behavior Remains Unchanged
# ==============================================================================

def test_20_existing_pipeline_behavior_remains_unchanged(clean_ops_db, client):
    """Verifies end-to-end execution retains standard pipeline output and metrics."""
    with patch.object(pulse_pipeline.ingestion.fetcher, "fetch_source_feed", side_effect=mock_feed_fetch):
        post_resp = client.post("/api/pipeline/run?skip_ingestion=false")
        assert post_resp.status_code == 200
        run_data = post_resp.json()
        assert run_data["status"] == "accepted"
        run_id = run_data["run_id"]

        status_resp = client.get("/api/pipeline/status")
        assert status_resp.status_code == 200
        status_data = status_resp.json()
        assert status_data["run_id"] == run_id
        assert status_data["status"] in ("success", "partial_failure")
        assert "stages" in status_data
        assert "pipeline" in status_data
        assert "scheduler" in status_data
