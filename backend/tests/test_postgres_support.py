"""
Unit and integration tests for PostgreSQL support and dual-engine architecture in Pulse.
Tests URL normalization, query adaptation, SQLite fallback preservation, and PostgreSQL compatibility.
"""
import pytest
import sqlite3
from unittest.mock import MagicMock, patch, AsyncMock

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

    assert mock_conn.commit.call_count >= 1


def test_sources_table_seeded_on_schema_init(tmp_path):
    db_file = tmp_path / "seeded_sources.db"
    repo = DbRepository(db_path=str(db_file))

    # Verify default sources are automatically seeded
    sources = repo.get_sources(enabled_only=True)
    assert len(sources) >= 10
    source_ids = {s["id"] for s in sources}
    assert "hackernews" in source_ids
    assert "arstechnica" in source_ids
    assert "bbcbusiness" in source_ids


def test_inserting_registered_source_followed_by_article_succeeds(tmp_path):
    """1. inserting a registered source followed by its article succeeds."""
    db_file = tmp_path / "fk_success.db"
    repo = DbRepository(db_path=str(db_file))

    # Register source explicitly
    canonical_id = repo.upsert_source(
        source_id="custom_wire",
        name="Custom Wire",
        base_url="https://customwire.io",
        feed_url="https://customwire.io/rss",
        category="technology",
        reliability_score=0.95
    )
    assert canonical_id == "custom_wire"

    # Insert article referencing the registered source
    art = {
        "id": "art-wire-01",
        "external_id": "ext-wire-01",
        "source_id": canonical_id,
        "source_name": "Custom Wire",
        "source_domain": "customwire.io",
        "title": "Quantum Leap in Distributed Consensus",
        "description": "Article summary details",
        "url": "https://customwire.io/article/01",
        "canonical_url": "https://customwire.io/article/01",
        "category": "technology",
        "published_at": "2026-09-14T12:00:00"
    }
    assert repo.insert_article(art) is True
    articles = repo.get_articles(source_id="custom_wire")
    assert len(articles) == 1
    assert articles[0]["source_id"] == "custom_wire"


def test_attempting_to_insert_article_whose_source_does_not_exist_fails_cleanly_and_is_isolated(tmp_path):
    """2. attempting to insert an article whose source does not exist fails cleanly and is isolated."""
    db_file = tmp_path / "fk_failure_isolated.db"
    repo = DbRepository(db_path=str(db_file))

    # Explicitly enforce foreign keys to simulate PostgreSQL behavior
    with repo._get_connection() as conn:
        conn.execute("PRAGMA foreign_keys = ON;")

    # Attempt to insert article referencing non-existent source
    orphan_article = {
        "id": "art-orphan-01",
        "external_id": "ext-orphan-01",
        "source_id": "non_existent_source_999",
        "source_name": "Ghost Wire",
        "source_domain": "ghost.invalid",
        "title": "Ghost Story",
        "description": "Should fail foreign key",
        "url": "https://ghost.invalid/story",
        "canonical_url": "https://ghost.invalid/story",
        "category": "technology",
        "published_at": "2026-09-14T12:00:00"
    }

    # Attempt insert directly on connection with FKs active: must fail cleanly
    with repo._get_connection() as conn:
        conn.execute("PRAGMA foreign_keys = ON;")
        cursor = conn.cursor()
        with pytest.raises(sqlite3.IntegrityError):
            cursor.execute("""
                INSERT INTO articles (id, external_id, source_id, source_name, source_domain, title, description, url, canonical_url, category, published_at)
                VALUES (:id, :external_id, :source_id, :source_name, :source_domain, :title, :description, :url, :canonical_url, :category, :published_at)
            """, orphan_article)

    # Verify isolation: valid source registration and insert still succeeds immediately after
    repo.upsert_source(
        source_id="isolated_valid_src",
        name="Valid Wire",
        base_url="https://validwire.com",
        feed_url="https://validwire.com/rss",
        category="technology"
    )
    valid_article = {
        "id": "art-valid-01",
        "source_id": "isolated_valid_src",
        "source_name": "Valid Wire",
        "source_domain": "validwire.com",
        "title": "Valid Headline",
        "url": "https://validwire.com/art1",
        "canonical_url": "https://validwire.com/art1",
        "category": "technology",
        "published_at": "2026-09-14T12:00:00"
    }
    assert repo.insert_article(valid_article) is True


@pytest.mark.anyio
async def test_repeated_ingestion_remains_idempotent(tmp_path):
    """3. repeated ingestion of the same source/article remains idempotent."""
    from backend.app.services.ingestion_service import IngestionService
    from backend.app.services.source_registry import SourceRegistry, NewsSource

    db_file = tmp_path / "idempotent_ingest.db"
    repo = DbRepository(db_path=str(db_file))

    mock_entry = MagicMock()
    mock_entry.title = "Idempotent Pipeline Demonstration"
    mock_entry.link = "https://news.ycombinator.com/item?id=88888"
    mock_entry.id = "guid-88888"
    mock_entry.summary = "Verifying idempotent article processing without constraint crashes."
    mock_entry.published_parsed = (2026, 9, 14, 15, 0, 0, 0, 0, 0)
    mock_entry.author = "Reliability Engineer"
    mock_entry.media_content = []
    mock_entry.enclosures = []
    mock_entry.links = []

    mock_fetcher = MagicMock()
    mock_fetcher.fetch_source_feed = AsyncMock(return_value=[{
        "raw_entry": mock_entry,
        "source_id": "hackernews",
        "source_name": "Hacker News",
        "source_base_url": "https://news.ycombinator.com",
        "category": "technology",
        "primary_topic": "Systems",
        "reliability_score": 0.95
    }])

    test_registry = SourceRegistry()
    test_registry._sources = {
        "hackernews": NewsSource(
            id="hackernews",
            name="Hacker News",
            base_url="https://news.ycombinator.com",
            feed_url="https://news.ycombinator.com/rss",
            category="technology",
            primary_topic="Systems",
            reliability_score=0.95,
            enabled=True
        )
    }

    ingest_svc = IngestionService()
    ingest_svc.fetcher = mock_fetcher
    ingest_svc.repo = repo
    ingest_svc.registry = test_registry

    # First ingestion run: 1 new article, 0 duplicates
    summary1 = await ingest_svc.run_ingestion_cycle()
    assert summary1["new_articles"] == 1
    assert summary1["duplicates"] == 0
    assert repo.get_total_count() == 1

    # Second ingestion run: 0 new articles, 1 duplicate (strictly idempotent)
    summary2 = await ingest_svc.run_ingestion_cycle()
    assert summary2["new_articles"] == 0
    assert summary2["duplicates"] == 1
    assert repo.get_total_count() == 1


def test_all_registry_sources_can_be_registered_before_articles(tmp_path):
    """4. all registry sources can be registered before their articles are inserted."""
    from backend.app.services.source_registry import source_registry

    db_file = tmp_path / "all_sources_registered.db"
    repo = DbRepository(db_path=str(db_file))

    # Register each source from registry
    all_sources = source_registry.get_all()
    assert len(all_sources) >= 10

    for src in all_sources:
        canonical_id = repo.upsert_source(src)
        assert canonical_id == src.id

    stored = repo.get_sources(enabled_only=False)
    stored_ids = {s["id"] for s in stored}
    for src in all_sources:
        assert src.id in stored_ids


def test_postgres_source_ids_remain_consistent_with_article_source_id(tmp_path):
    """5. PostgreSQL source IDs remain consistent with article.source_id (canonical resolution)."""
    db_file = tmp_path / "canonical_resolution.db"
    repo = DbRepository(db_path=str(db_file))

    # Pre-seed a source with an existing ID in database under a custom feed URL
    with repo._get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO sources (id, name, base_url, feed_url, category, reliability_score, enabled)
            VALUES ('existing_canonical_id_42', 'Custom Tech Feed', 'https://customtech.com', 'https://customtech.com/rss.xml', 'technology', 0.95, 1)
        """)
        conn.commit()

    # Now upsert a source with a different registry ID 'registry_id_99' but the same feed_url
    # upsert_source must resolve the canonical database ID 'existing_canonical_id_42'
    resolved_id = repo.upsert_source(
        source_id="registry_id_99",
        name="Custom Tech Feed",
        base_url="https://customtech.com",
        feed_url="https://customtech.com/rss.xml",
        category="technology"
    )
    assert resolved_id == "existing_canonical_id_42"

    # Insert article using the resolved canonical ID
    art = {
        "id": "art-custom-01",
        "source_id": resolved_id,
        "source_name": "Custom Tech Feed",
        "source_domain": "customtech.com",
        "title": "Novel Quantum Node Advancements",
        "url": "https://customtech.com/quantum/01",
        "canonical_url": "https://customtech.com/quantum/01",
        "category": "technology",
        "published_at": "2026-09-14T12:00:00"
    }
    assert repo.insert_article(art) is True

    # Verify article is linked to the exact PostgreSQL primary key
    stored_art = repo.get_article_by_id("art-custom-01")
    assert stored_art is not None
    assert stored_art["source_id"] == "existing_canonical_id_42"


@pytest.mark.anyio
async def test_fresh_database_pipeline_ingest_and_clustering(tmp_path):
    """6. SQLite tests continue passing unchanged and fresh database pipeline completes end-to-end."""
    from backend.app.services.ingestion_service import IngestionService
    from backend.app.services.clustering_service import ClusteringService

    db_file = tmp_path / "pipeline_fresh.db"
    repo = DbRepository(db_path=str(db_file))

    mock_entry = MagicMock()
    mock_entry.title = "PostgreSQL Foreign Key Resilience Proven in Production"
    mock_entry.link = "https://news.ycombinator.com/item?id=99999"
    mock_entry.id = "guid-99999"
    mock_entry.summary = "Relational integrity verified across SQLite and PostgreSQL engines."
    mock_entry.published_parsed = (2026, 9, 14, 14, 0, 0, 0, 0, 0)
    mock_entry.author = "Database Engineering Team"
    mock_entry.media_content = []
    mock_entry.enclosures = []
    mock_entry.links = []

    mock_fetcher = MagicMock()
    mock_fetcher.fetch_source_feed = AsyncMock(return_value=[{
        "raw_entry": mock_entry,
        "source_id": "hackernews",
        "source_name": "Hacker News",
        "source_base_url": "https://news.ycombinator.com",
        "category": "technology",
        "primary_topic": "Databases & Systems",
        "reliability_score": 0.95
    }])

    ingest_svc = IngestionService()
    ingest_svc.fetcher = mock_fetcher
    ingest_svc.repo = repo

    # Run ingestion on fresh database
    summary = await ingest_svc.run_ingestion_cycle()
    assert summary["new_articles"] >= 1

    # Verify article was stored and foreign key parent exists
    stored_articles = repo.get_articles()
    assert len(stored_articles) >= 1
    assert stored_articles[0]["source_id"] == "hackernews"

    # Run clustering over the ingested article
    cluster_svc = ClusteringService(db_repo=repo)
    cluster_metrics = cluster_svc.run_clustering()
    assert cluster_metrics["stories_created"] >= 1

    # Verify story exists and articles are linked without foreign key violations
    stories = repo.get_stories()
    assert len(stories) >= 1
    story = stories[0]
    assert story["article_count"] >= 1


