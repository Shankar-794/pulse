"""
Unit and integration tests for PostgreSQL support and dual-engine architecture in Pulse.
Tests URL normalization, query adaptation, SQLite fallback preservation, and PostgreSQL compatibility.
"""
import pytest
import sqlite3
from unittest.mock import MagicMock, patch

from backend.app.core.db_repository import (
    DbRepository,
    normalize_postgres_url,
    adapt_query_for_postgres,
    HardenedPostgresCursor,
    HardenedPostgresConnection,
)


def test_normalize_postgres_url_render_format():
    # Render provides postgres:// urls
    raw = "postgres://pulse_user:secret_pass@dpg-abc12345.render.com/pulse_db"
    normalized = normalize_postgres_url(raw)
    assert normalized.startswith("postgresql://")
    assert "sslmode=require" in normalized
    assert "pulse_user:secret_pass@dpg-abc12345.render.com/pulse_db" in normalized


def test_normalize_postgres_url_asyncpg_format():
    raw = "postgresql+asyncpg://user:pass@ep-cool-host.render.com:5432/dbname"
    normalized = normalize_postgres_url(raw)
    assert normalized.startswith("postgresql://")
    assert not normalized.startswith("postgresql+asyncpg://")
    assert "sslmode=require" in normalized


def test_normalize_postgres_url_localhost():
    raw = "postgresql://postgres:postgres@localhost:5432/pulse"
    normalized = normalize_postgres_url(raw)
    assert "sslmode" not in normalized

    raw_ip = "postgresql://postgres:postgres@127.0.0.1:5432/pulse"
    assert "sslmode" not in normalize_postgres_url(raw_ip)


def test_normalize_postgres_url_preserves_existing_sslmode():
    raw = "postgresql://user:pass@remote.com/db?sslmode=verify-full"
    normalized = normalize_postgres_url(raw)
    assert normalized.count("sslmode") == 1
    assert "sslmode=verify-full" in normalized


def test_adapt_query_for_postgres_positional():
    query = "SELECT * FROM stories WHERE category = ? AND importance_score >= ?"
    adapted = adapt_query_for_postgres(query, ("tech", 50))
    assert adapted == "SELECT * FROM stories WHERE category = %s AND importance_score >= %s"


def test_adapt_query_for_postgres_named():
    query = "INSERT INTO user_preferences (user_id, updated_at) VALUES (:user_id, :updated_at)"
    params = {"user_id": "u1", "updated_at": "2026-09-14"}
    adapted = adapt_query_for_postgres(query, params)
    assert "%(user_id)s" in adapted
    assert "%(updated_at)s" in adapted
    assert ":user_id" not in adapted


def test_adapt_query_for_postgres_rowid():
    query = "SELECT * FROM pipeline_runs ORDER BY created_at DESC, rowid DESC LIMIT 1"
    adapted = adapt_query_for_postgres(query)
    assert "rowid" not in adapted.lower()
    assert "run_id" in adapted


def test_adapt_query_for_postgres_insert_ignore():
    query = "INSERT OR IGNORE INTO user_saved_stories (user_id, story_id) VALUES (?, ?)"
    adapted = adapt_query_for_postgres(query)
    assert "INSERT INTO user_saved_stories" in adapted
    assert "ON CONFLICT DO NOTHING" in adapted
    assert "IGNORE" not in adapted


def test_sqlite_mode_remains_functional(tmp_path):
    db_file = tmp_path / "sqlite_test.db"
    repo = DbRepository(db_path=str(db_file))
    assert not repo.is_postgres
    assert repo.db_path == str(db_file)

    # Verify user creation
    user = repo.upsert_user(
        email="test_pg_compat@example.com",
        full_name="Postgres Tester"
    )
    assert user["email"] == "test_pg_compat@example.com"

    fetched = repo.get_user_by_email("test_pg_compat@example.com")
    assert fetched is not None
    assert fetched["id"] == user["id"]

    # Verify pipeline run acquisition
    run_res = repo.acquire_active_pipeline_run({"status": "running"})
    assert run_res["acquired"] is True
    assert run_res["run_id"] is not None

    # Verify atomic concurrency check
    second_run = repo.acquire_active_pipeline_run({"status": "running"})
    assert second_run["acquired"] is False
    assert second_run["active_run"]["run_id"] == run_res["run_id"]


def test_mocked_postgres_connection_and_cursor():
    raw_mock_conn = MagicMock()
    raw_mock_cursor = MagicMock()
    raw_mock_conn.cursor.return_value = raw_mock_cursor

    pg_conn = HardenedPostgresConnection(raw_mock_conn)
    cursor = pg_conn.cursor()

    # Test positional adaptation in cursor
    cursor.execute("SELECT * FROM stories WHERE id = ?", ("story-123",))
    raw_mock_cursor.execute.assert_called_once_with(
        "SELECT * FROM stories WHERE id = %s",
        ("story-123",)
    )

    # Test context manager commit on success
    with HardenedPostgresConnection(raw_mock_conn) as conn:
        conn.execute("UPDATE stories SET title = %s", ("New Title",))
    raw_mock_conn.commit.assert_called()


def test_system_health_stats_postgres_branch(tmp_path):
    db_file = tmp_path / "diag_test.db"
    repo = DbRepository(db_path=str(db_file))

    # Emulate postgres mode with mocked connection
    repo.is_postgres = True
    mock_cursor = MagicMock()
    mock_cursor.fetchone.return_value = [10]

    mock_conn = MagicMock()
    mock_conn.cursor.return_value = mock_cursor
    mock_conn.__enter__.return_value = mock_conn
    mock_conn.__exit__.return_value = None

    with patch.object(repo, "_get_connection", return_value=mock_conn):
        stats = repo.get_system_health_stats()
        assert stats["engine"] == "postgresql"
        assert stats["database_healthy"] is True
        assert stats["wal_mode_active"] is False
        assert stats["journal_mode"] == "postgres"


def test_postgres_schema_initialization_statements(tmp_path):
    db_file = tmp_path / "ddl_test.db"
    repo = DbRepository(db_path=str(db_file))
    repo.is_postgres = True

    executed_statements = []
    mock_cursor = MagicMock()
    mock_cursor.execute.side_effect = lambda sql, *args: executed_statements.append(sql.strip())

    mock_conn = MagicMock()
    mock_conn.cursor.return_value = mock_cursor
    mock_conn.__enter__.return_value = mock_conn
    mock_conn.__exit__.return_value = None

    with patch.object(repo, "_get_connection", return_value=mock_conn):
        repo.init_pg_db()

    # Verify all expected tables and indexes are created
    ddl_blob = " ".join(executed_statements).lower()
    for table in ["sources", "stories", "articles", "story_events", "user_preferences", "user_interactions", "users", "user_saved_stories", "pipeline_runs"]:
        assert f"create table if not exists {table}" in ddl_blob

    for index in ["idx_articles_canonical_url", "idx_stories_category", "idx_pipeline_runs_created_at"]:
        assert index in ddl_blob

    mock_conn.commit.assert_called_once()

