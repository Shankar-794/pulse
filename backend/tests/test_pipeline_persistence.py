"""
Pipeline Run Persistence and Asynchronous Readiness Test Suite (Phase 8.2).

Validates:
1. Pipeline run persistence:
   - Runs receive a unique run_id.
   - Full execution state, status, duration, metrics, and stage results persist in SQLite.
2. Pipeline history:
   - Sequential runs are retrievable via repository and API.
   - Runs are returned ordered newest first.
   - Limit query parameter restricts result count correctly.
3. Process restart simulation:
   - A newly instantiated PulsePipeline retrieves the latest persistent run from DB.
4. Failure persistence:
   - Isolated stage errors mark the run as 'partial_failure'.
   - The failed stage name is accurately persisted in failed_stages.
5. API contracts:
   - POST /api/pipeline/run returns run_id and execution summary.
   - GET /api/pipeline/status returns the latest persistent run.
   - GET /api/pipeline/runs returns historical executions list.
"""
import asyncio
import pytest
from unittest.mock import patch
from fastapi.testclient import TestClient

from backend.app.main import app
from backend.app.core.db_repository import db_repository
from backend.app.services.source_registry import source_registry
from backend.app.services.pulse_pipeline import PulsePipeline, pulse_pipeline
from backend.tests.test_pipeline_integration import MOCK_SOURCES, mock_feed_fetch


@pytest.fixture
def client():
    return TestClient(app)


@pytest.fixture
def clean_persistence_db(tmp_path):
    """Sets up an isolated clean SQLite database for persistence tests."""
    test_db = tmp_path / "test_persistence.db"
    orig_path = db_repository.db_path
    db_repository.db_path = str(test_db)
    db_repository.init_db()

    # Populate registered sources in test DB
    with db_repository._get_connection() as conn:
        for s in MOCK_SOURCES:
            conn.execute("""
            INSERT OR REPLACE INTO sources (id, name, base_url, feed_url, category, reliability_score, enabled)
            VALUES (?, ?, ?, ?, ?, ?, 1)
            """, (s.id, s.name, s.base_url, s.feed_url, s.category, s.reliability_score))
        conn.commit()

    # Update source_registry to use mock sources
    orig_sources = source_registry._sources
    source_registry._sources = {s.id: s for s in MOCK_SOURCES}

    yield

    db_repository.db_path = orig_path
    source_registry._sources = orig_sources


# ==============================================================================
# TESTS
# ==============================================================================

def test_pipeline_run_persistence(clean_persistence_db):
    """
    Verifies that running the pipeline creates a persistent database record
    with unique run_id, stage metrics, duration, and summary counts.
    """
    with patch.object(pulse_pipeline.ingestion.fetcher, "fetch_source_feed", side_effect=mock_feed_fetch):
        summary = asyncio.run(pulse_pipeline.run_pipeline(trigger_type="manual"))

    # 1. Verify returned summary contains run_id
    run_id = summary.get("run_id")
    assert run_id is not None
    assert run_id.startswith("run_")
    assert summary["status"] == "success"
    assert summary["total_duration_seconds"] > 0

    # 2. Retrieve persistent record from db_repository
    record = db_repository.get_pipeline_run(run_id)
    assert record is not None
    assert record["run_id"] == run_id
    assert record["status"] == "success"
    assert record["trigger_type"] == "manual"
    assert record["duration_seconds"] > 0
    assert record["total_duration_seconds"] > 0
    assert record["started_at"] is not None
    assert record["completed_at"] is not None

    # 3. Verify persisted summary counts
    assert record["total_articles"] == 6
    assert record["new_articles"] == 6
    assert record["total_stories"] == 5
    assert record["stories_created"] == 5
    assert record["stories_analyzed"] == 5
    assert record["stories_scored"] == 5
    assert record["stories_evolved"] == 5
    assert record["feed_items"] == 5

    # 4. Verify persisted stage metrics
    assert len(record["stages"]) == 7
    assert record["failed_stages"] == []
    assert record["error_message"] is None


def test_pipeline_history_ordering(clean_persistence_db, client):
    """
    Verifies that executing multiple runs produces ordered history via GET /api/pipeline/runs.
    """
    with patch.object(pulse_pipeline.ingestion.fetcher, "fetch_source_feed", side_effect=mock_feed_fetch):
        # Run 1
        run1 = asyncio.run(pulse_pipeline.run_pipeline(trigger_type="cron"))
        # Run 2
        run2 = asyncio.run(pulse_pipeline.run_pipeline(trigger_type="manual"))

    # Query pipeline runs via API
    resp = client.get("/api/pipeline/runs?limit=20")
    assert resp.status_code == 200
    runs = resp.json()
    assert isinstance(runs, list)
    assert len(runs) >= 2

    # Verify newest first ordering
    assert runs[0]["run_id"] == run2["run_id"]
    assert runs[1]["run_id"] == run1["run_id"]
    assert runs[0]["trigger_type"] == "manual"
    assert runs[1]["trigger_type"] == "cron"

    # Verify limit parameter works
    resp_limit_1 = client.get("/api/pipeline/runs?limit=1")
    assert resp_limit_1.status_code == 200
    limited = resp_limit_1.json()
    assert len(limited) == 1
    assert limited[0]["run_id"] == run2["run_id"]


def test_restart_simulation_retrieves_latest_run(clean_persistence_db):
    """
    Simulates process restart: a newly instantiated PulsePipeline must retrieve
    the latest persistent run from the database even with an empty in-memory cache.
    """
    with patch.object(pulse_pipeline.ingestion.fetcher, "fetch_source_feed", side_effect=mock_feed_fetch):
        summary = asyncio.run(pulse_pipeline.run_pipeline())

    run_id = summary["run_id"]

    # Instantiate fresh pipeline instance (simulating app restart)
    fresh_pipeline = PulsePipeline(db_repo=db_repository)
    assert fresh_pipeline._last_run is None

    latest = fresh_pipeline.get_last_run()
    assert latest is not None
    assert latest["run_id"] == run_id
    assert latest["status"] == "success"
    assert latest["total_duration_seconds"] > 0
    assert len(latest["stages"]) == 7


def test_failure_persistence_partial_failure(clean_persistence_db):
    """
    Simulates an isolated stage failure (e.g. clustering failure).
    Verifies that the run is persisted as 'partial_failure' with the failed stage recorded.
    """
    with patch.object(pulse_pipeline.ingestion.fetcher, "fetch_source_feed", side_effect=mock_feed_fetch):
        # Cause clustering stage to raise an error
        with patch.object(pulse_pipeline.clustering, "run_clustering", side_effect=RuntimeError("Clustering vectorization failed")):
            summary = asyncio.run(pulse_pipeline.run_pipeline())

    assert summary["status"] == "partial_failure"
    assert "clustering" in summary["failed_stages"]

    # Verify DB persistence of the partial failure
    record = db_repository.get_pipeline_run(summary["run_id"])
    assert record is not None
    assert record["status"] == "partial_failure"
    assert "clustering" in record["failed_stages"]
    assert record["stages"]["clustering"]["status"] == "failed"
    assert "Clustering vectorization failed" in record["stages"]["clustering"]["error"]


def test_unrecoverable_fatal_failure_persistence(clean_persistence_db):
    """
    Simulates an unrecoverable failure in the pipeline orchestration loop.
    Verifies that the run is persisted as 'failed' with error_message.
    """
    with patch.object(pulse_pipeline.db, "get_total_count", side_effect=RuntimeError("Fatal database corruption")):
        summary = asyncio.run(pulse_pipeline.run_pipeline(skip_ingestion=True))

    assert summary["status"] == "failed"
    assert "Fatal database corruption" in summary["error_message"]

    record = db_repository.get_pipeline_run(summary["run_id"])
    assert record is not None
    assert record["status"] == "failed"
    assert "Fatal database corruption" in record["error_message"]


def test_api_endpoints_contracts(clean_persistence_db, client):
    """
    Verifies API contract responses for:
    - POST /api/pipeline/run returns accepted and queued run_id
    - Background task finishes and GET /api/pipeline/status shows success
    - GET /api/pipeline/runs returns historical list
    """
    with patch.object(pulse_pipeline.ingestion.fetcher, "fetch_source_feed", side_effect=mock_feed_fetch):
        # 1. Trigger run via API (returns accepted immediately)
        post_resp = client.post("/api/pipeline/run?skip_ingestion=false&trigger_type=api")
        assert post_resp.status_code == 200
        run_data = post_resp.json()
        assert "run_id" in run_data
        assert run_data["status"] == "accepted"
        assert run_data["message"] == "Pipeline execution queued."

        # 2. Inspect status via API (in TestClient, background task completes during call)
        status_resp = client.get("/api/pipeline/status")
        assert status_resp.status_code == 200
        status_data = status_resp.json()
        assert status_data["run_id"] == run_data["run_id"]
        assert status_data["status"] == "success"
        assert status_data["total_duration_seconds"] > 0

        # 3. Retrieve history via API
        runs_resp = client.get("/api/pipeline/runs?limit=10")
        assert runs_resp.status_code == 200
        runs_data = runs_resp.json()
        assert len(runs_data) >= 1
        assert runs_data[0]["run_id"] == run_data["run_id"]


def test_concurrent_pipeline_execution_rejected_with_409(clean_persistence_db, client):
    """
    Verifies that starting a pipeline while another is 'running' or 'queued' returns 409 Conflict.
    """
    # 1. Simulate a currently running pipeline
    db_repository.create_pipeline_run(
        run_id="run_active_lock_test",
        status="running",
        started_at="2026-09-13T12:00:00Z"
    )

    conflict_resp = client.post("/api/pipeline/run")
    assert conflict_resp.status_code == 409
    err_body = conflict_resp.json()
    assert err_body["detail"]["active_run_id"] == "run_active_lock_test"
    assert err_body["detail"]["status"] == "running"

    # 2. Simulate a queued pipeline
    db_repository.update_pipeline_run("run_active_lock_test", {"status": "queued"})
    conflict_resp2 = client.post("/api/pipeline/run")
    assert conflict_resp2.status_code == 409
    assert conflict_resp2.json()["detail"]["status"] == "queued"

    # 3. Mark run as completed; subsequent post must succeed
    db_repository.update_pipeline_run("run_active_lock_test", {"status": "success"})
    with patch.object(pulse_pipeline.ingestion.fetcher, "fetch_source_feed", side_effect=mock_feed_fetch):
        success_resp = client.post("/api/pipeline/run")
        assert success_resp.status_code == 200
        assert success_resp.json()["status"] == "accepted"


def test_stage_progress_persistence(clean_persistence_db):
    """
    Verifies that stage progress transitions are persisted and each stage metrics are recorded.
    """
    recorded_states = []

    orig_update = db_repository.update_pipeline_run
    def capturing_update(run_id, updates):
        if "stages" in updates:
            stages_copy = {k: v.get("status") for k, v in updates["stages"].items()}
            recorded_states.append(stages_copy)
        return orig_update(run_id, updates)

    with patch.object(db_repository, "update_pipeline_run", side_effect=capturing_update):
        with patch.object(pulse_pipeline.ingestion.fetcher, "fetch_source_feed", side_effect=mock_feed_fetch):
            summary = asyncio.run(pulse_pipeline.run_pipeline())

    assert summary["status"] == "success"
    # Verify multiple stage updates were captured (at least one per stage)
    assert len(recorded_states) >= 7

    # Verify final persisted record in SQLite contains all 7 stages completed
    record = db_repository.get_pipeline_run(summary["run_id"])
    assert record is not None
    stages = record["stages"]
    for expected_stage in ["ingestion", "clustering", "story_analysis", "global_importance", "story_evolution", "personal_relevance", "feed_readiness"]:
        assert expected_stage in stages
        assert stages[expected_stage]["status"] == "success"
        assert stages[expected_stage]["duration_seconds"] >= 0


def test_background_fatal_exception_persists_as_failed(clean_persistence_db, client):
    """
    Verifies that unhandled fatal exceptions in background execution are captured and persisted as failed.
    """
    with patch.object(pulse_pipeline.db, "get_total_count", side_effect=RuntimeError("Unrecoverable background disk error")):
        post_resp = client.post("/api/pipeline/run?skip_ingestion=true")
        assert post_resp.status_code == 200
        run_id = post_resp.json()["run_id"]

        status_resp = client.get("/api/pipeline/status")
        assert status_resp.status_code == 200
        status_data = status_resp.json()
        assert status_data["run_id"] == run_id
        assert status_data["status"] == "failed"
        assert "Unrecoverable background disk error" in status_data["error_message"]

        db_record = db_repository.get_pipeline_run(run_id)
        assert db_record["status"] == "failed"
        assert "Unrecoverable background disk error" in db_record["error_message"]
