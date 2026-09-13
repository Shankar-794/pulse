"""
Tests for Phase 9.1 Step 2 & Step 3:
- Self-Healing Pipeline Recovery & Administrative Abort (Step 2)
- Atomic Active Pipeline Run Acquisition & Concurrency Hardening (Step 3)

Verifies:
1. Startup reconciliation of running pipeline runs.
2. Startup reconciliation of queued pipeline runs.
3. Multiple orphan runs reconciliation.
4. Non-active runs (success, failed, partial_failure, interrupted) remain untouched.
5. Administrative abort endpoint POST /api/pipeline/runs/active/abort on active run.
6. Administrative abort endpoint POST /api/pipeline/runs/active/abort when no active run exists.
7. Existing 409 conflict contract preservation for concurrent runs.
8. Aborting active run clears 409 conflict and permits subsequent pipeline trigger.
9. FastAPI lifespan startup executes orphan reconciliation automatically.
10. Atomic first acquisition succeeds (Step 3).
11. Atomic second acquisition while first is queued/running is rejected (Step 3).
12. Concurrent acquisition attempts cannot produce two active runs (Step 3).
13. Existing 409 API behavior remains intact under atomic acquisition (Step 3).
14. Scheduler acquisition uses the atomic path (Step 3).
15. Scheduler skips when another active run exists (Step 3).
16. Aborted/interrupted run no longer blocks a new atomic acquisition (Step 3).
"""
import pytest
import asyncio
import threading
from concurrent.futures import ThreadPoolExecutor
from unittest.mock import patch
from datetime import datetime, timezone, timedelta
from fastapi.testclient import TestClient

from backend.app.main import app, lifespan
from backend.app.core.db_repository import db_repository
from backend.app.services.pulse_pipeline import pulse_pipeline
from backend.app.services.pipeline_scheduler import PipelineScheduler, pipeline_scheduler


@pytest.fixture
def clean_recovery_db(tmp_path):
    """Sets up an isolated clean SQLite database for recovery and concurrency tests."""
    test_db = tmp_path / "test_recovery.db"
    orig_path = db_repository.db_path
    db_repository.db_path = str(test_db)
    db_repository.init_db()

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
# Test 1 — Startup reconciliation of running pipeline run
# ==============================================================================

def test_1_startup_reconciliation_running_run(clean_recovery_db):
    """
    Test 1: Startup reconciliation
    Create a pipeline_runs record in running state.
    Call db_repository.reconcile_orphan_pipeline_runs()
    Assert:
      returned count is 1
      status becomes interrupted
      completed_at is populated
      error message contains Execution interrupted by server restart
    """
    run_id = clean_recovery_db.create_pipeline_run(
        run_id="run_orphan_running_01",
        status="running",
        trigger_type="manual",
        started_at=datetime.now(timezone.utc).isoformat()
    )

    reconciled_count = clean_recovery_db.reconcile_orphan_pipeline_runs()
    assert reconciled_count == 1

    run = clean_recovery_db.get_pipeline_run(run_id)
    assert run is not None
    assert run["status"] == "interrupted"
    assert run["completed_at"] is not None
    assert "Execution interrupted by server restart" in (run["error_message"] or "")


# ==============================================================================
# Test 2 — Startup reconciliation of queued pipeline run
# ==============================================================================

def test_2_startup_reconciliation_queued_run(clean_recovery_db):
    """
    Test 2: Queued run reconciliation
    Create a queued pipeline run.
    Reconcile it.
    Assert it becomes interrupted with completed_at populated.
    """
    run_id = clean_recovery_db.create_pipeline_run(
        run_id="run_orphan_queued_01",
        status="queued",
        trigger_type="scheduler",
        started_at=datetime.now(timezone.utc).isoformat()
    )

    reconciled_count = clean_recovery_db.reconcile_orphan_pipeline_runs()
    assert reconciled_count == 1

    run = clean_recovery_db.get_pipeline_run(run_id)
    assert run is not None
    assert run["status"] == "interrupted"
    assert run["completed_at"] is not None
    assert "Execution interrupted by server restart" in (run["error_message"] or "")


# ==============================================================================
# Test 3 — Multiple orphan runs reconciliation
# ==============================================================================

def test_3_multiple_orphan_runs_reconciliation(clean_recovery_db):
    """
    Test 3: Multiple orphan runs
    Create multiple queued and running records.
    Reconcile.
    Assert all eligible runs are interrupted and returned count is correct.
    """
    r1 = clean_recovery_db.create_pipeline_run(run_id="run_multi_01", status="running")
    r2 = clean_recovery_db.create_pipeline_run(run_id="run_multi_02", status="queued")
    r3 = clean_recovery_db.create_pipeline_run(run_id="run_multi_03", status="running")
    r4 = clean_recovery_db.create_pipeline_run(run_id="run_multi_04", status="queued")

    reconciled_count = clean_recovery_db.reconcile_orphan_pipeline_runs()
    assert reconciled_count == 4

    for r_id in [r1, r2, r3, r4]:
        run = clean_recovery_db.get_pipeline_run(r_id)
        assert run is not None
        assert run["status"] == "interrupted"
        assert run["completed_at"] is not None
        assert "Execution interrupted by server restart" in (run["error_message"] or "")


# ==============================================================================
# Test 4 — Non-active runs remain untouched
# ==============================================================================

def test_4_non_active_runs_remain_untouched(clean_recovery_db):
    """
    Test 4: Non-active runs remain untouched
    Create successful, failed, partial_failure, and already-interrupted records.
    Reconcile.
    Assert they remain unchanged.
    """
    clean_recovery_db.create_pipeline_run(
        run_id="run_success_01",
        status="success",
        completed_at="2026-09-13T10:00:00",
        error_message=None
    )
    clean_recovery_db.create_pipeline_run(
        run_id="run_failed_01",
        status="failed",
        completed_at="2026-09-13T10:05:00",
        error_message="Network failure during ingestion"
    )
    clean_recovery_db.create_pipeline_run(
        run_id="run_partial_01",
        status="partial_failure",
        completed_at="2026-09-13T10:10:00",
        error_message="Stage story_analysis failed"
    )
    clean_recovery_db.create_pipeline_run(
        run_id="run_interrupted_prior",
        status="interrupted",
        completed_at="2026-09-13T10:15:00",
        error_message="Earlier interruption by operator"
    )

    reconciled_count = clean_recovery_db.reconcile_orphan_pipeline_runs()
    assert reconciled_count == 0

    s = clean_recovery_db.get_pipeline_run("run_success_01")
    assert s["status"] == "success"
    assert s["completed_at"] == "2026-09-13T10:00:00"
    assert s["error_message"] is None

    f = clean_recovery_db.get_pipeline_run("run_failed_01")
    assert f["status"] == "failed"
    assert f["completed_at"] == "2026-09-13T10:05:00"
    assert f["error_message"] == "Network failure during ingestion"

    p = clean_recovery_db.get_pipeline_run("run_partial_01")
    assert p["status"] == "partial_failure"
    assert p["completed_at"] == "2026-09-13T10:10:00"
    assert p["error_message"] == "Stage story_analysis failed"

    i = clean_recovery_db.get_pipeline_run("run_interrupted_prior")
    assert i["status"] == "interrupted"
    assert i["completed_at"] == "2026-09-13T10:15:00"
    assert i["error_message"] == "Earlier interruption by operator"


# ==============================================================================
# Test 5 — Administrative abort endpoint with active run
# ==============================================================================

def test_5_administrative_abort_active_run(clean_recovery_db, client):
    """
    Test 5: Administrative abort
    Create an active pipeline run.
    Invoke POST /api/pipeline/runs/active/abort through FastAPI test client.
    Assert:
      HTTP success response (200)
      correct run ID
      status becomes interrupted
      error message is Manually aborted by operator
    """
    run_id = clean_recovery_db.create_pipeline_run(
        run_id="run_active_to_abort",
        status="running",
        trigger_type="manual",
        started_at=datetime.now(timezone.utc).isoformat()
    )

    resp = client.post("/api/pipeline/runs/active/abort")
    assert resp.status_code == 200
    data = resp.json()

    assert data["status"] == "interrupted"
    assert data["run_id"] == "run_active_to_abort"
    assert "Manually aborted by operator" in data["error_message"]

    # Verify database persistence
    run_in_db = clean_recovery_db.get_pipeline_run(run_id)
    assert run_in_db is not None
    assert run_in_db["status"] == "interrupted"
    assert run_in_db["completed_at"] is not None
    assert run_in_db["error_message"] == "Manually aborted by operator"


# ==============================================================================
# Test 6 — Administrative abort endpoint with no active run
# ==============================================================================

def test_6_administrative_abort_no_active_run(clean_recovery_db, client):
    """
    Test 6: Abort with no active run
    Invoke POST /api/pipeline/runs/active/abort when no queued/running run exists.
    Assert:
      clean successful response (HTTP 200)
      no exception
      no database mutation
    """
    clean_recovery_db.create_pipeline_run(
        run_id="run_completed_earlier",
        status="success",
        completed_at=datetime.now(timezone.utc).isoformat()
    )

    resp = client.post("/api/pipeline/runs/active/abort")
    assert resp.status_code == 200
    data = resp.json()

    assert data["status"] == "no_active_run"
    assert data["run_id"] is None

    # Assert no mutation occurred to existing runs
    run = clean_recovery_db.get_pipeline_run("run_completed_earlier")
    assert run["status"] == "success"


# ==============================================================================
# Test 7 — Existing 409 behavior remains intact
# ==============================================================================

def test_7_existing_409_behavior_intact(clean_recovery_db, client):
    """
    Test 7: Existing 409 behavior remains intact
    Verify that an active run still causes the existing manual pipeline endpoint
    to return HTTP 409.
    """
    active_id = clean_recovery_db.create_pipeline_run(
        run_id="run_blocking_concurrent_01",
        status="running",
        trigger_type="manual",
        started_at=datetime.now(timezone.utc).isoformat()
    )

    resp = client.post("/api/pipeline/run")
    assert resp.status_code == 409
    detail = resp.json().get("detail", {})
    assert "already in progress" in detail.get("message", "")
    assert detail.get("active_run_id") == active_id
    assert detail.get("status") == "running"


# ==============================================================================
# Test 8 — Post-abort unblocking allows new run
# ==============================================================================

def test_8_post_abort_unblocks_concurrency(clean_recovery_db, client):
    """
    Verifies that administratively aborting an active run frees the pipeline
    and allows subsequent runs without 409 Conflict.
    """
    clean_recovery_db.create_pipeline_run(
        run_id="run_stuck_blocking",
        status="running",
        trigger_type="scheduler"
    )

    # First attempt: blocked by 409
    resp1 = client.post("/api/pipeline/run")
    assert resp1.status_code == 409

    # Abort the stuck run
    abort_resp = client.post("/api/pipeline/runs/active/abort")
    assert abort_resp.status_code == 200
    assert abort_resp.json()["status"] == "interrupted"

    # Subsequent run: should now be accepted
    with patch.object(pulse_pipeline, "run_pipeline", return_value={"status": "success"}):
        resp2 = client.post("/api/pipeline/run")
        assert resp2.status_code == 200
        assert resp2.json()["status"] == "accepted"


# ==============================================================================
# Test 9 — FastAPI lifespan automatically executes reconciliation
# ==============================================================================

def test_9_lifespan_startup_reconciles_orphan_runs(clean_recovery_db):
    """
    Verifies that the FastAPI lifespan context manager executes
    reconcile_orphan_pipeline_runs() during startup.
    """
    r_id = clean_recovery_db.create_pipeline_run(
        run_id="run_stuck_at_boot",
        status="running"
    )

    async def simulate_lifespan():
        async with lifespan(app):
            pass

    asyncio.run(simulate_lifespan())

    run = clean_recovery_db.get_pipeline_run(r_id)
    assert run["status"] == "interrupted"
    assert "Execution interrupted by server restart" in run["error_message"]


# ==============================================================================
# Phase 9.1 Step 3: Atomic Pipeline Acquisition Tests
# ==============================================================================

def test_10_atomic_first_acquisition_succeeds(clean_recovery_db):
    """
    Test 10 (A): First acquisition succeeds.
    Verifies that calling acquire_active_pipeline_run when no run is active
    successfully acquires the write lock and returns acquired=True with queued record.
    """
    result = clean_recovery_db.acquire_active_pipeline_run(
        run_id="run_atomic_first_01",
        trigger_type="manual",
        user_id="operator_1",
        skip_ingestion=False
    )

    assert result["acquired"] is True
    assert result["run_id"] == "run_atomic_first_01"
    assert result["active_run"] is None
    assert result["run"] is not None
    assert result["run"]["status"] == "queued"
    assert result["run"]["trigger_type"] == "manual"

    # Verify database persistence
    persisted = clean_recovery_db.get_pipeline_run("run_atomic_first_01")
    assert persisted is not None
    assert persisted["status"] == "queued"


def test_11_atomic_second_acquisition_rejected_while_active(clean_recovery_db):
    """
    Test 11 (B): Second acquisition while first is queued/running is rejected.
    Verifies mutual exclusion: when an active run exists, subsequent acquisition
    is rejected and returns the active run's details.
    """
    # 1. Acquire initial run
    first = clean_recovery_db.acquire_active_pipeline_run(
        run_id="run_atomic_active_01",
        trigger_type="manual"
    )
    assert first["acquired"] is True

    # 2. Second attempt while first is in 'queued' status
    second = clean_recovery_db.acquire_active_pipeline_run(
        run_id="run_atomic_conflict_02",
        trigger_type="scheduler"
    )
    assert second["acquired"] is False
    assert second["run_id"] is None
    assert second["active_run"] is not None
    assert second["active_run"]["run_id"] == "run_atomic_active_01"
    assert second["active_run"]["status"] == "queued"

    # 3. Transition first run to 'running'
    clean_recovery_db.update_pipeline_run("run_atomic_active_01", {"status": "running"})

    # 4. Third attempt while first is in 'running' status
    third = clean_recovery_db.acquire_active_pipeline_run(
        run_id="run_atomic_conflict_03",
        trigger_type="api"
    )
    assert third["acquired"] is False
    assert third["active_run"]["run_id"] == "run_atomic_active_01"
    assert third["active_run"]["status"] == "running"

    # Exactly 1 run must exist in the database
    all_runs = clean_recovery_db.get_pipeline_runs()
    assert len(all_runs) == 1
    assert all_runs[0]["run_id"] == "run_atomic_active_01"


def test_12_concurrent_acquisitions_cannot_produce_two_active_runs(clean_recovery_db):
    """
    Test 12 (C): Concurrent acquisition attempts cannot produce two active runs.
    Dispatches 10 concurrent threads simultaneously competing to acquire the active slot.
    Guarantees exactly 1 thread acquires successfully and 9 are rejected.
    """
    num_threads = 10
    results = []
    lock = threading.Lock()

    def try_acquire(worker_id):
        res = clean_recovery_db.acquire_active_pipeline_run(
            run_id=f"run_race_worker_{worker_id}",
            trigger_type="api"
        )
        with lock:
            results.append(res)

    with ThreadPoolExecutor(max_workers=num_threads) as executor:
        futures = [executor.submit(try_acquire, i) for i in range(num_threads)]
        for f in futures:
            f.result()

    acquired = [r for r in results if r["acquired"]]
    rejected = [r for r in results if not r["acquired"]]

    assert len(acquired) == 1, f"Expected exactly 1 acquired run, got {len(acquired)}"
    assert len(rejected) == num_threads - 1

    winning_run_id = acquired[0]["run_id"]

    # All rejected attempts must point to the winning run
    for r in rejected:
        assert r["active_run"]["run_id"] == winning_run_id
        assert r["active_run"]["status"] in ("queued", "running")

    # Verify only 1 record exists in the database
    runs_in_db = clean_recovery_db.get_pipeline_runs()
    assert len(runs_in_db) == 1
    assert runs_in_db[0]["run_id"] == winning_run_id


def test_13_existing_409_api_behavior_with_atomic_acquisition(clean_recovery_db, client):
    """
    Test 13 (D): Existing 409 API behavior remains intact under atomic acquisition.
    Verifies that POST /api/pipeline/run rejects concurrent calls with HTTP 409 Conflict
    identifying the active run ID.
    """
    with patch.object(pulse_pipeline, "run_pipeline"):
        # First API call: acquired and accepted
        resp1 = client.post("/api/pipeline/run?trigger_type=manual")
        assert resp1.status_code == 200
        data1 = resp1.json()
        assert data1["status"] == "accepted"
        first_run_id = data1["run_id"]

        # Second API call: rejected with 409 Conflict
        resp2 = client.post("/api/pipeline/run?trigger_type=api")
        assert resp2.status_code == 409
        detail = resp2.json().get("detail", {})
        assert "already in progress" in detail.get("message", "")
        assert detail.get("active_run_id") == first_run_id
        assert detail.get("status") in ("queued", "running")


def test_14_scheduler_uses_atomic_acquisition_path(clean_recovery_db):
    """
    Test 14 (E): Scheduler acquisition uses the atomic path.
    Verifies that pipeline_scheduler.execute_tick() atomically acquires the queued run slot
    and records scheduler execution telemetry.
    """
    scheduler = PipelineScheduler(enabled=True)

    with patch.object(pulse_pipeline, "run_pipeline", return_value={"status": "success"}):
        result = scheduler.execute_tick()

    assert result is not None
    assert scheduler._last_triggered_run_id is not None
    assert scheduler._last_triggered_at is not None

    run = clean_recovery_db.get_pipeline_run(scheduler._last_triggered_run_id)
    assert run is not None
    assert run["trigger_type"] == "scheduler"


def test_15_scheduler_skips_when_active_run_exists(clean_recovery_db):
    """
    Test 15 (F): Scheduler skips when another active run exists.
    Verifies that execute_tick() does NOT create a second run and sets skip telemetry
    when an active run is already present.
    """
    # 1. Acquire an active run beforehand
    blocking = clean_recovery_db.acquire_active_pipeline_run(
        run_id="run_blocking_scheduler_tick",
        trigger_type="manual"
    )
    assert blocking["acquired"] is True

    scheduler = PipelineScheduler(enabled=True)

    # 2. Trigger scheduler tick
    with patch.object(pulse_pipeline, "run_pipeline") as mock_run:
        result = scheduler.execute_tick()
        mock_run.assert_not_called()

    assert result is None
    assert scheduler._last_skipped_at is not None
    assert "run_blocking_scheduler_tick" in scheduler._last_skip_reason
    assert "in progress" in scheduler._last_skip_reason

    # No second run was created in DB
    all_runs = clean_recovery_db.get_pipeline_runs()
    assert len(all_runs) == 1
    assert all_runs[0]["run_id"] == "run_blocking_scheduler_tick"


def test_16_aborted_run_allows_new_atomic_acquisition(clean_recovery_db, client):
    """
    Test 16 (G): Aborted/interrupted run no longer blocks a new acquisition.
    Verifies that after an active run is administratively aborted, subsequent
    atomic acquisitions immediately succeed without conflict.
    """
    # 1. Acquire active run
    run_1 = clean_recovery_db.acquire_active_pipeline_run(
        run_id="run_to_be_aborted_01",
        trigger_type="api"
    )
    assert run_1["acquired"] is True

    # 2. Abort active run via administrative endpoint
    abort_resp = client.post("/api/pipeline/runs/active/abort")
    assert abort_resp.status_code == 200
    assert abort_resp.json()["status"] == "interrupted"

    # Verify status in DB
    run_db = clean_recovery_db.get_pipeline_run("run_to_be_aborted_01")
    assert run_db["status"] == "interrupted"

    # 3. Subsequent acquisition succeeds immediately
    run_2 = clean_recovery_db.acquire_active_pipeline_run(
        run_id="run_acquired_post_abort",
        trigger_type="scheduler"
    )
    assert run_2["acquired"] is True
    assert run_2["run_id"] == "run_acquired_post_abort"
    assert run_2["run"]["status"] == "queued"


def test_17_healthy_active_run_with_recent_heartbeat_not_reclaimed(clean_recovery_db):
    """
    Test 17 (A): Healthy active run with a recent heartbeat is NOT reclaimed.
    Verifies that a running run with a recent heartbeat within the stale threshold
    remains untouched in 'running' status with no error message.
    """
    base_time = datetime(2026, 9, 13, 12, 0, 0)
    heartbeat_time = base_time - timedelta(seconds=30)
    now = base_time

    clean_recovery_db.create_pipeline_run(
        run_id="run_healthy_active",
        status="running",
        started_at=heartbeat_time.isoformat(),
        last_heartbeat_at=heartbeat_time.isoformat()
    )

    reclaimed = clean_recovery_db.reconcile_stale_pipeline_runs(
        stale_timeout_seconds=600,
        queue_timeout_seconds=300,
        now=now
    )

    assert reclaimed == 0
    run = clean_recovery_db.get_pipeline_run("run_healthy_active")
    assert run["status"] == "running"
    assert run["completed_at"] is None
    assert run["error_message"] is None


def test_18_genuinely_stale_running_run_reclaimed_as_interrupted(clean_recovery_db):
    """
    Test 18 (B): Genuinely stale running run is reclaimed as interrupted.
    Verifies that a running run with last heartbeat exceeding the stale timeout
    is transitioned to 'interrupted', completed_at is populated, duration is recorded,
    and a clear explanatory error message is stored.
    """
    base_time = datetime(2026, 9, 13, 12, 0, 0)
    started_time = base_time - timedelta(seconds=900)
    heartbeat_time = base_time - timedelta(seconds=700)  # 700s > 600s threshold
    now = base_time

    clean_recovery_db.create_pipeline_run(
        run_id="run_stale_running_01",
        status="running",
        started_at=started_time.isoformat(),
        last_heartbeat_at=heartbeat_time.isoformat()
    )

    reclaimed = clean_recovery_db.reconcile_stale_pipeline_runs(
        stale_timeout_seconds=600,
        queue_timeout_seconds=300,
        now=now
    )

    assert reclaimed == 1
    run = clean_recovery_db.get_pipeline_run("run_stale_running_01")
    assert run["status"] == "interrupted"
    assert run["completed_at"] == now.isoformat()
    assert run["duration_seconds"] == 900.0
    assert "Execution timed out: no heartbeat progress" in run["error_message"]
    assert "threshold: 600s" in run["error_message"]


def test_19_stale_queued_run_reclaimed_after_queue_threshold(clean_recovery_db):
    """
    Test 19 (C): Stale queued run is reclaimed only after the configured queue threshold.
    Verifies that a queued run that has been abandoned in the queue for longer than
    queue_timeout_seconds is marked interrupted, while a recently queued run is preserved.
    """
    base_time = datetime(2026, 9, 13, 12, 0, 0)
    recent_queued_time = base_time - timedelta(seconds=60)  # 60s < 300s
    abandoned_queued_time = base_time - timedelta(seconds=450)  # 450s > 300s
    now = base_time

    clean_recovery_db.create_pipeline_run(
        run_id="run_recent_queued",
        status="queued",
        started_at=recent_queued_time.isoformat(),
        created_at=recent_queued_time.isoformat(),
        last_heartbeat_at=recent_queued_time.isoformat()
    )
    clean_recovery_db.create_pipeline_run(
        run_id="run_abandoned_queued",
        status="queued",
        started_at=abandoned_queued_time.isoformat(),
        created_at=abandoned_queued_time.isoformat(),
        last_heartbeat_at=abandoned_queued_time.isoformat()
    )

    reclaimed = clean_recovery_db.reconcile_stale_pipeline_runs(
        stale_timeout_seconds=600,
        queue_timeout_seconds=300,
        now=now
    )

    assert reclaimed == 1

    # Recent queued run remains untouched
    recent = clean_recovery_db.get_pipeline_run("run_recent_queued")
    assert recent["status"] == "queued"
    assert recent["completed_at"] is None

    # Abandoned queued run is reclaimed as interrupted
    abandoned = clean_recovery_db.get_pipeline_run("run_abandoned_queued")
    assert abandoned["status"] == "interrupted"
    assert abandoned["completed_at"] == now.isoformat()
    assert "Execution timed out in queue: abandoned" in abandoned["error_message"]


def test_20_stale_reconciliation_is_idempotent(clean_recovery_db):
    """
    Test 20 (D): Reconciliation is idempotent.
    Executing reconcile_stale_pipeline_runs() multiple times returns 0 for subsequent
    invocations and does not overwrite existing interrupted run data or messages.
    """
    base_time = datetime(2026, 9, 13, 12, 0, 0)
    heartbeat_time = base_time - timedelta(seconds=800)
    now = base_time

    clean_recovery_db.create_pipeline_run(
        run_id="run_idempotent_test",
        status="running",
        started_at=heartbeat_time.isoformat(),
        last_heartbeat_at=heartbeat_time.isoformat()
    )

    first_reclaim = clean_recovery_db.reconcile_stale_pipeline_runs(
        stale_timeout_seconds=600,
        now=now
    )
    assert first_reclaim == 1
    first_run_state = clean_recovery_db.get_pipeline_run("run_idempotent_test")

    # Second execution immediately
    second_reclaim = clean_recovery_db.reconcile_stale_pipeline_runs(
        stale_timeout_seconds=600,
        now=now + timedelta(seconds=10)
    )
    assert second_reclaim == 0
    second_run_state = clean_recovery_db.get_pipeline_run("run_idempotent_test")

    # Attributes preserved exactly
    assert second_run_state["status"] == "interrupted"
    assert second_run_state["completed_at"] == first_run_state["completed_at"]
    assert second_run_state["error_message"] == first_run_state["error_message"]


def test_21_completed_failed_partial_failure_interrupted_runs_untouched(clean_recovery_db):
    """
    Test 21 (E): Terminal/completed runs are never modified by stale reconciliation.
    Success, failed, partial_failure, and previously interrupted runs remain untouched
    even if their timestamps are ancient.
    """
    ancient_time = (datetime(2026, 9, 13, 12, 0, 0) - timedelta(days=10)).isoformat()

    clean_recovery_db.create_pipeline_run(
        run_id="run_success_old",
        status="success",
        started_at=ancient_time,
        completed_at=ancient_time,
        error_message=None
    )
    clean_recovery_db.create_pipeline_run(
        run_id="run_failed_old",
        status="failed",
        started_at=ancient_time,
        completed_at=ancient_time,
        error_message="Original failure reason"
    )
    clean_recovery_db.create_pipeline_run(
        run_id="run_partial_old",
        status="partial_failure",
        started_at=ancient_time,
        completed_at=ancient_time,
        error_message="Stage error"
    )
    clean_recovery_db.create_pipeline_run(
        run_id="run_interrupted_old",
        status="interrupted",
        started_at=ancient_time,
        completed_at=ancient_time,
        error_message="Previous interruption"
    )

    reclaimed = clean_recovery_db.reconcile_stale_pipeline_runs(
        stale_timeout_seconds=60,
        queue_timeout_seconds=30,
        now=datetime(2026, 9, 13, 12, 0, 0)
    )
    assert reclaimed == 0

    assert clean_recovery_db.get_pipeline_run("run_success_old")["status"] == "success"
    assert clean_recovery_db.get_pipeline_run("run_failed_old")["error_message"] == "Original failure reason"
    assert clean_recovery_db.get_pipeline_run("run_partial_old")["status"] == "partial_failure"
    assert clean_recovery_db.get_pipeline_run("run_interrupted_old")["error_message"] == "Previous interruption"


def test_22_new_atomic_acquisition_succeeds_after_stale_recovery(clean_recovery_db):
    """
    Test 22 (F): After stale recovery, a new atomic pipeline acquisition succeeds immediately.
    Verifies that a dead running run initially blocks acquisition, but after
    reconcile_stale_pipeline_runs(), acquire_active_pipeline_run() immediately succeeds.
    """
    base_time = datetime(2026, 9, 13, 12, 0, 0)
    old_heartbeat = base_time - timedelta(seconds=1200)

    clean_recovery_db.create_pipeline_run(
        run_id="run_blocking_dead",
        status="running",
        started_at=old_heartbeat.isoformat(),
        last_heartbeat_at=old_heartbeat.isoformat()
    )

    # 1. Acquisition fails while run is active
    acq1 = clean_recovery_db.acquire_active_pipeline_run(run_id="run_new_attempt_1")
    assert acq1["acquired"] is False

    # 2. Reconcile stale run
    reclaimed = clean_recovery_db.reconcile_stale_pipeline_runs(
        stale_timeout_seconds=600,
        now=base_time
    )
    assert reclaimed == 1

    # 3. Acquisition now succeeds atomically
    acq2 = clean_recovery_db.acquire_active_pipeline_run(run_id="run_new_attempt_2")
    assert acq2["acquired"] is True
    assert acq2["run_id"] == "run_new_attempt_2"
    assert acq2["run"]["status"] == "queued"


def test_23_administrative_abort_preserved_and_not_overwritten_by_stale_recovery(clean_recovery_db):
    """
    Test 23 (G): Administrative abort error message is preserved and never overwritten
    by stale run reconciliation.
    """
    base_time = datetime(2026, 9, 13, 12, 0, 0)
    old_time = base_time - timedelta(seconds=2000)

    # 1. Create run and abort it
    clean_recovery_db.create_pipeline_run(
        run_id="run_aborted_by_admin",
        status="running",
        started_at=old_time.isoformat(),
        last_heartbeat_at=old_time.isoformat()
    )
    aborted = clean_recovery_db.abort_active_pipeline_run("run_aborted_by_admin")
    assert aborted is not None
    assert aborted["status"] == "interrupted"
    assert aborted["error_message"] == "Manually aborted by operator"

    # 2. Trigger stale recovery in the far future
    reclaimed = clean_recovery_db.reconcile_stale_pipeline_runs(
        stale_timeout_seconds=60,
        now=base_time + timedelta(hours=5)
    )
    assert reclaimed == 0

    # 3. Message remains 'Manually aborted by operator'
    run = clean_recovery_db.get_pipeline_run("run_aborted_by_admin")
    assert run["status"] == "interrupted"
    assert run["error_message"] == "Manually aborted by operator"


def test_24_recovery_does_not_create_pipeline_runs_or_record_failures(clean_recovery_db):
    """
    Test 24 (H & I): Stale run recovery does not create additional pipeline runs,
    does not increment consecutive failure counters, and updates scheduler status.
    """
    scheduler = PipelineScheduler(enabled=True)

    initial_runs = clean_recovery_db.get_pipeline_runs()
    assert len(initial_runs) == 0

    # Trigger reconcile on scheduler with no stale runs
    count = scheduler.reconcile_stale_runs()
    assert count == 0

    runs_after = clean_recovery_db.get_pipeline_runs()
    assert len(runs_after) == 0

    status = scheduler.get_status()
    assert status["stale_timeout_seconds"] > 0
    assert status["last_stale_recovery_at"] is not None
    assert status["last_stale_reclaimed_count"] == 0

    # Failure statistics should remain clean (0 failures)
    failure_stats = clean_recovery_db.get_failure_stats()
    assert failure_stats["consecutive_failure_count"] == 0


def test_25_pipeline_stage_boundary_updates_heartbeat(clean_recovery_db):
    """
    Test 25: Verifies that updating pipeline run progress advances the heartbeat timestamp.
    """
    t0 = datetime(2026, 9, 13, 12, 0, 0).isoformat()
    clean_recovery_db.create_pipeline_run(
        run_id="run_stage_heartbeat_test",
        status="running",
        started_at=t0,
        last_heartbeat_at=t0
    )

    # Calling update_pipeline_run with new stage info
    clean_recovery_db.update_pipeline_run(
        "run_stage_heartbeat_test",
        {"stages": {"ingestion": {"status": "success"}}}
    )

    run = clean_recovery_db.get_pipeline_run("run_stage_heartbeat_test")
    assert run["last_heartbeat_at"] is not None
    assert run["last_heartbeat_at"] != t0


