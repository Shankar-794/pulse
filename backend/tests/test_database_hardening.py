"""
Focused Tests for Phase 9 Step 1: SQLite Concurrency & Database Connection Hardening.
Verifies:
1. Database initialization & WAL mode.
2. Busy timeout & synchronous pragma configuration.
3. Connection cleanup & closure after context exit.
4. Transaction commit on success.
5. Transaction rollback after failure.
6. Concurrent read access during active writer (WAL snapshot isolation).
7. Concurrent write coordination without database locks.
8. Pipeline repository operations under concurrent multi-threaded access.
9. Scheduler/background-thread database access.
10. System health diagnostics exposure.
"""
import time
import pytest
import sqlite3
import threading
from concurrent.futures import ThreadPoolExecutor
from fastapi.testclient import TestClient

from backend.app.main import app
from backend.app.core.config import settings
from backend.app.core.db_repository import DbRepository, HardenedSQLiteConnection


@pytest.fixture
def hardened_test_repo(tmp_path):
    """Creates an isolated temporary SQLite database configured with hardening."""
    db_file = tmp_path / "test_hardened.db"
    repo = DbRepository(db_path=str(db_file))
    return repo


def test_database_initialization_wal_mode(hardened_test_repo):
    """Verifies that database initializes with WAL mode, NORMAL sync, and 30s busy timeout."""
    diag = hardened_test_repo.get_db_diagnostics()
    assert diag["is_wal_mode"] is True
    assert diag["journal_mode"].lower() == "wal"
    assert diag["busy_timeout_ms"] >= 30000
    assert diag["synchronous"] == 1  # 1 = NORMAL
    assert diag["cache_size"] == -64000
    assert diag["temp_store"] == 2  # 2 = MEMORY


def test_busy_timeout_configuration(hardened_test_repo):
    """Verifies that busy timeout pragma is actively applied on every connection."""
    with hardened_test_repo._get_connection() as conn:
        cursor = conn.cursor()
        timeout_row = cursor.execute("PRAGMA busy_timeout;").fetchone()
        assert timeout_row[0] >= 30000


def test_connection_cleanup_and_closed_on_exit(hardened_test_repo):
    """Verifies that the underlying connection is closed immediately upon context exit."""
    raw_conn = None
    with hardened_test_repo._get_connection() as conn:
        raw_conn = conn
        # Connection is open inside block
        res = conn.execute("SELECT 1;").fetchone()
        assert res[0] == 1

    # After exiting context manager, the connection must be closed
    with pytest.raises((sqlite3.ProgrammingError, sqlite3.OperationalError)):
        raw_conn.execute("SELECT 1;")


def test_transaction_commit_on_success(hardened_test_repo):
    """Verifies that data modifications are committed automatically when no exceptions occur."""
    with hardened_test_repo._get_connection() as conn:
        conn.execute("""
            CREATE TABLE test_items (id INT PRIMARY KEY, name TEXT);
        """)
        conn.execute("INSERT INTO test_items VALUES (1, 'item_one');")

    # Verify visibility from a completely fresh connection
    with hardened_test_repo._get_connection() as conn:
        row = conn.execute("SELECT name FROM test_items WHERE id = 1;").fetchone()
        assert row is not None
        assert row["name"] == "item_one"


def test_transaction_rollback_after_failure(hardened_test_repo):
    """Verifies that unhandled exceptions trigger an automatic rollback before closing."""
    with hardened_test_repo._get_connection() as conn:
        conn.execute("""
            CREATE TABLE test_rollback (id INT PRIMARY KEY, val TEXT);
        """)
        conn.execute("INSERT INTO test_rollback VALUES (1, 'initial');")

    # Attempt a transaction that raises an unhandled exception
    with pytest.raises(RuntimeError):
        with hardened_test_repo._get_connection() as conn:
            conn.execute("INSERT INTO test_rollback VALUES (2, 'aborted');")
            raise RuntimeError("Forced simulation error")

    # Verify that id=2 was rolled back and only id=1 exists
    with hardened_test_repo._get_connection() as conn:
        rows = conn.execute("SELECT * FROM test_rollback;").fetchall()
        assert len(rows) == 1
        assert rows[0]["id"] == 1


def test_concurrent_read_access_during_writer(hardened_test_repo):
    """
    Verifies WAL snapshot isolation: concurrent readers are NEVER blocked by an active writer.
    Uses deterministic synchronization barriers.
    """
    # Pre-populate sample articles
    for i in range(10):
        hardened_test_repo.insert_article({
            "id": f"art_{i}",
            "url": f"https://example.com/art_{i}",
            "canonical_url": f"https://example.com/art_{i}",
            "title": f"Article {i}",
            "category": "technology",
            "published_at": "2026-09-13T12:00:00Z"
        })

    writer_in_tx = threading.Event()
    readers_done = threading.Event()
    reader_results = []
    reader_errors = []

    def writer_task():
        with hardened_test_repo._get_connection() as conn:
            conn.execute("UPDATE articles SET title = 'Writer In Progress' WHERE id = 'art_0';")
            # Signal readers that writer holds an active transaction
            writer_in_tx.set()
            # Wait for readers to finish reading before committing
            readers_done.wait(timeout=5.0)

    def reader_task(reader_id):
        writer_in_tx.wait(timeout=5.0)
        try:
            articles = hardened_test_repo.get_articles(limit=10)
            reader_results.append((reader_id, len(articles)))
        except Exception as e:
            reader_errors.append((reader_id, str(e)))

    t_writer = threading.Thread(target=writer_task)
    t_writer.start()

    # Launch 5 concurrent reader threads
    threads = [threading.Thread(target=reader_task, args=(i,)) for i in range(5)]
    for t in threads:
        t.start()

    for t in threads:
        t.join(timeout=5.0)

    readers_done.set()
    t_writer.join(timeout=5.0)

    assert len(reader_errors) == 0, f"Reader errors occurred during write: {reader_errors}"
    assert len(reader_results) == 5
    for _, count in reader_results:
        assert count == 10


def test_concurrent_write_coordination(hardened_test_repo):
    """
    Verifies that multiple concurrent writer threads coordinate cleanly under SQLite's busy handler
    without throwing 'database is locked' OperationalErrors.
    """
    num_threads = 6
    articles_per_thread = 5
    barrier = threading.Barrier(num_threads)
    write_errors = []

    def writer_worker(thread_idx):
        barrier.wait(timeout=5.0)
        for i in range(articles_per_thread):
            try:
                hardened_test_repo.insert_article({
                    "id": f"thread_{thread_idx}_art_{i}",
                    "url": f"https://example.com/t{thread_idx}/art_{i}",
                    "canonical_url": f"https://example.com/t{thread_idx}/art_{i}",
                    "title": f"Thread {thread_idx} Article {i}",
                    "category": "technology",
                    "published_at": "2026-09-13T12:00:00Z"
                })
            except Exception as e:
                write_errors.append((thread_idx, i, str(e)))

    threads = [threading.Thread(target=writer_worker, args=(t,)) for t in range(num_threads)]
    for t in threads:
        t.start()
    for t in threads:
        t.join(timeout=10.0)

    assert len(write_errors) == 0, f"Write errors occurred under concurrency: {write_errors}"
    assert hardened_test_repo.get_total_count() == num_threads * articles_per_thread


def test_pipeline_repository_operations_under_concurrency(hardened_test_repo):
    """
    Simulates high-frequency pipeline status updates while concurrent clients read execution history.
    """
    stop_event = threading.Event()
    read_errors = []
    read_counts = []

    def continuous_reader():
        while not stop_event.is_set():
            try:
                runs = hardened_test_repo.get_pipeline_runs(limit=10)
                active = hardened_test_repo.get_active_pipeline_run()
                stats = hardened_test_repo.get_failure_stats()
                read_counts.append(len(runs))
                time.sleep(0.01)
            except Exception as e:
                read_errors.append(str(e))

    reader_thread = threading.Thread(target=continuous_reader)
    reader_thread.start()

    # Writer performs pipeline run lifecycle updates
    try:
        for i in range(5):
            run_id = f"run_concurrent_{i}"
            hardened_test_repo.create_pipeline_run(
                run_id=run_id,
                status="queued",
                trigger_type="scheduler",
                user_id="default_user"
            )
            hardened_test_repo.update_pipeline_run(run_id, {
                "status": "running",
                "stages": {"ingestion": {"status": "running"}}
            })
            time.sleep(0.02)
            hardened_test_repo.update_pipeline_run(run_id, {
                "status": "success",
                "duration_seconds": 1.23,
                "stages": {"ingestion": {"status": "success"}}
            })
    finally:
        stop_event.set()
        reader_thread.join(timeout=5.0)

    assert len(read_errors) == 0, f"Concurrent reader errors: {read_errors}"
    assert len(read_counts) > 0
    all_runs = hardened_test_repo.get_pipeline_runs(limit=10)
    assert len(all_runs) == 5


def test_scheduler_background_thread_db_access(hardened_test_repo):
    """
    Verifies that background scheduler executor threads access the hardened repository cleanly.
    """
    def simulated_scheduler_tick():
        active = hardened_test_repo.get_active_pipeline_run()
        if active is None:
            run_id = "sched_tick_01"
            hardened_test_repo.create_pipeline_run(
                run_id=run_id,
                status="queued",
                trigger_type="scheduler"
            )
            return run_id
        return None

    with ThreadPoolExecutor(max_workers=2) as executor:
        future = executor.submit(simulated_scheduler_tick)
        result_run_id = future.result(timeout=5.0)

    assert result_run_id == "sched_tick_01"
    run = hardened_test_repo.get_pipeline_run("sched_tick_01")
    assert run is not None
    assert run["trigger_type"] == "scheduler"


def test_system_health_endpoint_diagnostics(monkeypatch, tmp_path):
    """Verifies that GET /api/system/health exposes SQLite WAL mode and concurrency diagnostics."""
    test_db = tmp_path / "test_health_concurrency.db"
    repo = DbRepository(db_path=str(test_db))

    from backend.app.core.db_repository import db_repository
    monkeypatch.setattr(db_repository, "db_path", str(test_db))

    client = TestClient(app)
    response = client.get("/api/system/health")
    assert response.status_code == 200
    data = response.json()

    assert data["database_health"] == "healthy"
    assert "database_wal_mode" in data
    assert data["database_wal_mode"] is True
    assert data["database_journal_mode"] == "wal"
    assert data["database_busy_timeout_ms"] >= 30000
