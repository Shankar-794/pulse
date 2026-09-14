"""
Database Repository for Pulse News Intelligence.
Provides reliable relational storage for sources, ingested articles, and stories.
Supports PostgreSQL for persistent production deployments (e.g. Render),
and SQLite for zero-friction local development and testing.
"""
import os
import re
import json
import uuid
import sqlite3
import logging
from datetime import datetime, timezone, timedelta
from typing import List, Dict, Any, Optional

from pathlib import Path
from backend.app.core.config import settings

try:
    import psycopg2
    import psycopg2.extras
    import psycopg2.pool
    PSYCOPG2_AVAILABLE = True
except ImportError:
    psycopg2 = None
    PSYCOPG2_AVAILABLE = False

logger = logging.getLogger("pulse.db.repository")

DB_DIR = Path(__file__).resolve().parent.parent.parent
DEFAULT_SQLITE_PATH = DB_DIR / "pulse.db"


def normalize_postgres_url(raw_url: str) -> str:
    """
    Normalizes PostgreSQL connection string for psycopg2:
    - Replaces protocol prefixes ('postgres://', 'postgresql+asyncpg://') with 'postgresql://'
    - Ensures sslmode=require for remote hosts (Render requirement) while leaving localhost unforced.
    """
    if not raw_url:
        return ""
    url = raw_url.strip()
    clean = re.sub(r"^postgres(ql)?(\+[a-zA-Z0-9_]+)?://", "postgresql://", url)
    if "sslmode" not in clean and "@localhost" not in clean and "@127.0.0.1" not in clean:
        sep = "&" if "?" in clean else "?"
        clean = f"{clean}{sep}sslmode=require"
    return clean


def adapt_query_for_postgres(query: str, params: Any = None) -> str:
    """
    Translates SQLite parameter placeholders and pseudo-columns to PostgreSQL format:
    1. Replaces SQLite 'rowid' with portable primary key 'run_id'
    2. Converts SQLite 'INSERT OR IGNORE INTO' to 'INSERT INTO ... ON CONFLICT DO NOTHING'
    3. If params is a dict: converts named :param_name to %(param_name)s
    4. If params is a sequence or None: converts ? to %s
    """
    # Replace rowid with run_id
    adapted = re.sub(r'\browid\b', 'run_id', query, flags=re.IGNORECASE)

    # Convert INSERT OR IGNORE INTO to INSERT INTO ... ON CONFLICT DO NOTHING
    if re.search(r'\bINSERT\s+OR\s+IGNORE\s+INTO\b', adapted, flags=re.IGNORECASE):
        adapted = re.sub(r'\bINSERT\s+OR\s+IGNORE\s+INTO\b', 'INSERT INTO', adapted, flags=re.IGNORECASE)
        if "ON CONFLICT" not in adapted.upper():
            adapted = adapted.rstrip().rstrip(";") + " ON CONFLICT DO NOTHING;"

    if isinstance(params, dict):
        # Convert :name to %(name)s when not preceded by another colon
        adapted = re.sub(r'(?<!:):([a-zA-Z_][a-zA-Z0-9_]*)', r'%(\1)s', adapted)
    else:
        adapted = adapted.replace('?', '%s')

    return adapted


class HardenedSQLiteConnection:
    """
    Proxy and context manager that hardens SQLite connections for concurrent environments (Phase 9 Step 1):
    1. Delegates transaction boundary management to sqlite3.Connection.__enter__ / __exit__
       (automatically commits on clean exit, automatically rolls back on exception).
    2. Guaranteed connection closure in a finally block (prevents leaked locks and file descriptors).
    3. Seamlessly proxies all connection methods/attributes (execute, cursor, commit, etc.).
    """
    def __init__(self, raw_conn: sqlite3.Connection):
        self._raw_conn = raw_conn

    def __enter__(self) -> sqlite3.Connection:
        self._raw_conn.__enter__()
        return self._raw_conn

    def __exit__(self, exc_type, exc_val, exc_tb):
        try:
            return self._raw_conn.__exit__(exc_type, exc_val, exc_tb)
        finally:
            self._raw_conn.close()

    def __getattr__(self, name: str):
        return getattr(self._raw_conn, name)


class HardenedPostgresCursor:
    """
    Cursor proxy that automatically adapts queries from SQLite placeholders (? / :param)
    to PostgreSQL placeholders (%s / %(param)s).
    """
    def __init__(self, raw_cursor):
        self._raw_cursor = raw_cursor

    def execute(self, query: str, params: Any = None):
        adapted = adapt_query_for_postgres(query, params)
        if params is not None:
            return self._raw_cursor.execute(adapted, params)
        return self._raw_cursor.execute(adapted)

    def executemany(self, query: str, params_seq: Any):
        first_item = params_seq[0] if params_seq else None
        adapted = adapt_query_for_postgres(query, first_item)
        return self._raw_cursor.executemany(adapted, params_seq)

    def fetchone(self):
        return self._raw_cursor.fetchone()

    def fetchall(self):
        return self._raw_cursor.fetchall()

    def fetchmany(self, size=None):
        return self._raw_cursor.fetchmany(size)

    @property
    def rowcount(self):
        return self._raw_cursor.rowcount

    def __getattr__(self, name: str):
        return getattr(self._raw_cursor, name)


class HardenedPostgresConnection:
    """
    Context manager and connection proxy for PostgreSQL with automatic commit/rollback
    and connection pooling integration.
    """
    def __init__(self, raw_conn, pool=None):
        self._raw_conn = raw_conn
        self._pool = pool

    def cursor(self):
        return HardenedPostgresCursor(
            self._raw_conn.cursor(cursor_factory=psycopg2.extras.DictCursor)
        )

    def execute(self, query: str, params: Any = None):
        cur = self.cursor()
        cur.execute(query, params)
        return cur

    def commit(self):
        self._raw_conn.commit()

    def rollback(self):
        self._raw_conn.rollback()

    def close(self):
        if self._pool is not None:
            try:
                self._pool.putconn(self._raw_conn)
            except Exception:
                self._raw_conn.close()
        else:
            self._raw_conn.close()

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        try:
            if exc_type is not None:
                self.rollback()
            else:
                self.commit()
        finally:
            self.close()

    def __getattr__(self, name: str):
        return getattr(self._raw_conn, name)


class DbRepository:
    def __init__(self, db_path: Optional[str] = None, postgres_url: Optional[str] = None):
        explicit_sqlite = db_path is not None and (":memory:" in db_path or db_path.endswith(".db") or db_path.endswith(".sqlite"))
        env_pg_url = postgres_url or (getattr(settings, "DATABASE_URL", None) if not explicit_sqlite else None)

        if env_pg_url and not explicit_sqlite:
            self.is_postgres = True
            self.pg_url = normalize_postgres_url(env_pg_url)
            self.db_path = None
            self._pg_pool = None
            self._init_pg_pool()
        else:
            self.is_postgres = False
            self.pg_url = None
            self._pg_pool = None
            configured_path = db_path or getattr(settings, "SQLITE_DB_PATH", None) or os.getenv("SQLITE_DB_PATH")
            self.db_path = str(configured_path) if configured_path else str(DEFAULT_SQLITE_PATH)
            if self.db_path != ":memory:" and not self.db_path.startswith("file:"):
                try:
                    Path(self.db_path).parent.mkdir(parents=True, exist_ok=True)
                except Exception as e:
                    logger.warning(f"Could not create parent directory for SQLite DB {self.db_path}: {e}")

        self.init_db()

    def _init_pg_pool(self):
        if not PSYCOPG2_AVAILABLE:
            logger.warning("psycopg2 is not installed; PostgreSQL pooling unavailable.")
            return
        try:
            self._pg_pool = psycopg2.pool.ThreadedConnectionPool(
                minconn=1,
                maxconn=20,
                dsn=self.pg_url
            )
            logger.info("Initialized PostgreSQL connection pool successfully.")
        except Exception as err:
            logger.error(f"Failed to initialize PostgreSQL connection pool: {err}")
            self._pg_pool = None

    def _get_pg_connection(self) -> HardenedPostgresConnection:
        if not PSYCOPG2_AVAILABLE:
            raise RuntimeError("PostgreSQL driver 'psycopg2' is not installed. Install psycopg2-binary to use PostgreSQL.")
        if self._pg_pool is None:
            self._init_pg_pool()
        if self._pg_pool is not None:
            try:
                raw_conn = self._pg_pool.getconn()
                raw_conn.autocommit = False
                return HardenedPostgresConnection(raw_conn, pool=self._pg_pool)
            except Exception as err:
                logger.error(f"Pool connection failed, falling back to direct connection: {err}")
        raw_conn = psycopg2.connect(self.pg_url)
        raw_conn.autocommit = False
        return HardenedPostgresConnection(raw_conn, pool=None)

    def _create_raw_connection(self) -> sqlite3.Connection:
        """
        Creates and configures a raw SQLite connection with concurrency pragmas (Phase 9 Step 1).
        Configures busy_timeout, WAL journal mode, and NORMAL synchronization.
        """
        timeout_sec = getattr(settings, "SQLITE_BUSY_TIMEOUT_MS", 30000) / 1000.0
        conn = sqlite3.connect(self.db_path, timeout=timeout_sec)
        conn.row_factory = sqlite3.Row

        busy_timeout_ms = getattr(settings, "SQLITE_BUSY_TIMEOUT_MS", 30000)
        conn.execute(f"PRAGMA busy_timeout = {busy_timeout_ms};")

        # Configure WAL mode and pragmas for persistent disk databases
        is_disk_db = self.db_path != ":memory:" and not self.db_path.startswith("file:")
        if is_disk_db and getattr(settings, "SQLITE_WAL_MODE", True):
            conn.execute("PRAGMA journal_mode = WAL;")
            sync_mode = getattr(settings, "SQLITE_SYNCHRONOUS", "NORMAL")
            conn.execute(f"PRAGMA synchronous = {sync_mode};")
            conn.execute("PRAGMA cache_size = -64000;")
            conn.execute("PRAGMA temp_store = MEMORY;")

        return conn

    def _get_connection(self):
        """
        Provides a hardened connection with deterministic transaction boundaries
        and guaranteed connection cleanup upon context exit.
        """
        if self.is_postgres:
            return self._get_pg_connection()
        raw_conn = self._create_raw_connection()
        return HardenedSQLiteConnection(raw_conn)

    def get_db_diagnostics(self) -> Dict[str, Any]:
        """
        Returns runtime database diagnostics for SQLite or PostgreSQL.
        """
        if self.is_postgres:
            with self._get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("SELECT version();")
                ver_row = cursor.fetchone()
                cursor.execute("SELECT current_database();")
                db_row = cursor.fetchone()
                return {
                    "engine": "postgresql",
                    "database_name": db_row[0] if db_row else "unknown",
                    "server_version": str(ver_row[0]) if ver_row else "unknown",
                    "pool_available": self._pg_pool is not None,
                    "is_wal_mode": False
                }

        with self._get_connection() as conn:
            cursor = conn.cursor()
            jm = cursor.execute("PRAGMA journal_mode;").fetchone()
            bt = cursor.execute("PRAGMA busy_timeout;").fetchone()
            sync = cursor.execute("PRAGMA synchronous;").fetchone()
            cs = cursor.execute("PRAGMA cache_size;").fetchone()
            ts = cursor.execute("PRAGMA temp_store;").fetchone()
            return {
                "engine": "sqlite",
                "db_path": str(self.db_path),
                "is_wal_mode": bool(jm and str(jm[0]).lower() == "wal"),
                "journal_mode": jm[0] if jm else "unknown",
                "busy_timeout_ms": bt[0] if bt else 0,
                "synchronous": sync[0] if sync else 0,
                "cache_size": cs[0] if cs else 0,
                "temp_store": ts[0] if ts else 0
            }

    def init_db(self):
        """Initializes database schema for PostgreSQL or SQLite."""
        if self.is_postgres:
            self.init_pg_db()
        else:
            self.init_sqlite_db()

    def init_pg_db(self):
        """
        Creates PostgreSQL tables, constraints, and indexes.
        Idempotent schema initialization suitable for Render PostgreSQL deployments.
        """
        with self._get_connection() as conn:
            cursor = conn.cursor()

            # 1. Sources table
            cursor.execute("""
            CREATE TABLE IF NOT EXISTS sources (
                id TEXT PRIMARY KEY,
                name TEXT NOT NULL,
                base_url TEXT NOT NULL,
                feed_url TEXT NOT NULL UNIQUE,
                category TEXT NOT NULL,
                reliability_score REAL DEFAULT 1.0,
                enabled INTEGER DEFAULT 1,
                last_fetched_at TEXT,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP
            );
            """)

            # 2. Stories table (created before articles to ensure foreign keys resolve)
            cursor.execute("""
            CREATE TABLE IF NOT EXISTS stories (
                id TEXT PRIMARY KEY,
                title TEXT NOT NULL,
                summary TEXT,
                why_it_matters TEXT,
                category TEXT NOT NULL,
                primary_topic TEXT DEFAULT 'Technology',
                importance_score INTEGER DEFAULT 50,
                relevance_score INTEGER DEFAULT 50,
                freshness_score INTEGER DEFAULT 100,
                source_count INTEGER DEFAULT 1,
                article_count INTEGER DEFAULT 1,
                first_published_at TEXT,
                last_published_at TEXT,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                updated_at TEXT DEFAULT CURRENT_TIMESTAMP,
                ai_title TEXT,
                ai_summary TEXT,
                ai_category TEXT,
                entities_json TEXT,
                topics_json TEXT,
                analysis_confidence REAL,
                analyzed_at TEXT,
                analysis_version TEXT,
                claims_json TEXT,
                severity_score REAL,
                reach_score REAL,
                impact_score REAL,
                urgency_score REAL,
                novelty_score REAL,
                escalation_score REAL,
                reporting_breadth_score REAL,
                importance_tier TEXT,
                importance_explanation TEXT,
                importance_version TEXT,
                importance_calculated_at TEXT,
                relevance_reason TEXT,
                relevance_calculated_at TEXT,
                relevance_version TEXT,
                story_status TEXT DEFAULT 'ACTIVE',
                breaking_score INTEGER DEFAULT 30,
                breaking_level TEXT DEFAULT 'STABLE',
                latest_development TEXT,
                latest_updated_at TEXT,
                update_count INTEGER DEFAULT 0,
                perspectives_json TEXT,
                evolution_version TEXT,
                evolution_calculated_at TEXT
            );
            """)

            cursor.execute("CREATE INDEX IF NOT EXISTS idx_stories_category ON stories(category);")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_stories_updated_at ON stories(updated_at DESC);")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_stories_importance ON stories(importance_score DESC);")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_stories_analyzed_at ON stories(analyzed_at DESC);")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_stories_status ON stories(story_status);")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_stories_breaking ON stories(breaking_score DESC);")

            # 3. Articles table
            cursor.execute("""
            CREATE TABLE IF NOT EXISTS articles (
                id TEXT PRIMARY KEY,
                external_id TEXT,
                source_id TEXT NOT NULL REFERENCES sources(id),
                source_name TEXT NOT NULL,
                source_domain TEXT NOT NULL,
                title TEXT NOT NULL,
                description TEXT,
                url TEXT NOT NULL,
                canonical_url TEXT NOT NULL,
                author TEXT,
                category TEXT NOT NULL,
                primary_topic TEXT DEFAULT 'Technology',
                image_url TEXT,
                published_at TEXT NOT NULL,
                raw_content_hash TEXT,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                story_id TEXT REFERENCES stories(id)
            );
            """)

            cursor.execute("CREATE UNIQUE INDEX IF NOT EXISTS idx_articles_canonical_url ON articles(canonical_url);")
            cursor.execute("""
            CREATE UNIQUE INDEX IF NOT EXISTS idx_articles_source_ext_id
            ON articles(source_id, external_id)
            WHERE external_id IS NOT NULL AND external_id != '';
            """)
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_articles_published_at ON articles(published_at DESC);")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_articles_category ON articles(category);")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_articles_story_id ON articles(story_id);")

            # 4. Story Events table
            cursor.execute("""
            CREATE TABLE IF NOT EXISTS story_events (
                id TEXT PRIMARY KEY,
                story_id TEXT NOT NULL REFERENCES stories(id),
                event_type TEXT NOT NULL,
                title TEXT NOT NULL,
                summary TEXT NOT NULL,
                article_ids_json TEXT NOT NULL,
                occurred_at TEXT,
                detected_at TEXT DEFAULT CURRENT_TIMESTAMP,
                significance REAL DEFAULT 0.5,
                event_version TEXT DEFAULT 'v1'
            );
            """)
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_story_events_story_id ON story_events(story_id);")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_story_events_detected_at ON story_events(detected_at DESC);")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_story_events_occurred_at ON story_events(occurred_at DESC);")

            # 5. User Preferences table
            cursor.execute("""
            CREATE TABLE IF NOT EXISTS user_preferences (
                user_id TEXT PRIMARY KEY,
                interests_json TEXT,
                interest_weights_json TEXT,
                topic_affinities_json TEXT,
                entity_affinities_json TEXT,
                breaking_sensitivity TEXT DEFAULT 'standard',
                importance_threshold INTEGER DEFAULT 50,
                updated_at TEXT DEFAULT CURRENT_TIMESTAMP
            );
            """)

            # 6. User Interactions table
            cursor.execute("""
            CREATE TABLE IF NOT EXISTS user_interactions (
                id TEXT PRIMARY KEY,
                user_id TEXT NOT NULL,
                story_id TEXT NOT NULL,
                interaction_type TEXT NOT NULL,
                metadata_json TEXT,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP
            );
            """)
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_interactions_user_story ON user_interactions(user_id, story_id);")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_interactions_created_at ON user_interactions(created_at DESC);")

            # 7. Users table
            cursor.execute("""
            CREATE TABLE IF NOT EXISTS users (
                id TEXT PRIMARY KEY,
                email TEXT UNIQUE NOT NULL,
                full_name TEXT,
                picture_url TEXT,
                oauth_provider TEXT DEFAULT 'google',
                oauth_sub TEXT,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                last_login_at TEXT DEFAULT CURRENT_TIMESTAMP
            );
            """)
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_users_email ON users(email);")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_users_oauth_sub ON users(oauth_sub);")

            # 8. User Saved Stories table
            cursor.execute("""
            CREATE TABLE IF NOT EXISTS user_saved_stories (
                user_id TEXT NOT NULL,
                story_id TEXT NOT NULL REFERENCES stories(id),
                saved_at TEXT DEFAULT CURRENT_TIMESTAMP,
                PRIMARY KEY (user_id, story_id)
            );
            """)
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_saved_stories_user ON user_saved_stories(user_id, saved_at DESC);")

            # 9. Pipeline Runs table
            cursor.execute("""
            CREATE TABLE IF NOT EXISTS pipeline_runs (
                run_id TEXT PRIMARY KEY,
                status TEXT NOT NULL,
                started_at TEXT,
                completed_at TEXT,
                duration_seconds REAL,
                trigger_type TEXT DEFAULT 'manual',
                user_id TEXT DEFAULT 'default_user',
                skip_ingestion INTEGER DEFAULT 0,
                total_articles INTEGER DEFAULT 0,
                new_articles INTEGER DEFAULT 0,
                total_stories INTEGER DEFAULT 0,
                stories_created INTEGER DEFAULT 0,
                stories_analyzed INTEGER DEFAULT 0,
                stories_scored INTEGER DEFAULT 0,
                stories_evolved INTEGER DEFAULT 0,
                feed_items INTEGER DEFAULT 0,
                failed_stages TEXT DEFAULT '[]',
                error_message TEXT,
                stage_metrics_json TEXT,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                last_heartbeat_at TEXT
            );
            """)
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_pipeline_runs_created_at ON pipeline_runs(created_at DESC);")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_pipeline_runs_started_at ON pipeline_runs(started_at DESC);")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_pipeline_runs_status ON pipeline_runs(status);")

            conn.commit()

    def init_sqlite_db(self):
        """Creates SQLite tables, constraints, and indexes with WAL mode enabled."""
        # For disk databases, explicitly set WAL mode and pragmas on initialization
        is_disk_db = self.db_path != ":memory:" and not self.db_path.startswith("file:")
        if is_disk_db and getattr(settings, "SQLITE_WAL_MODE", True):
            with self._get_connection() as conn:
                conn.execute("PRAGMA journal_mode = WAL;")
                conn.execute(f"PRAGMA synchronous = {getattr(settings, 'SQLITE_SYNCHRONOUS', 'NORMAL')};")

        with self._get_connection() as conn:
            cursor = conn.cursor()

            # Sources table
            cursor.execute("""
            CREATE TABLE IF NOT EXISTS sources (
                id TEXT PRIMARY KEY,
                name TEXT NOT NULL,
                base_url TEXT NOT NULL,
                feed_url TEXT NOT NULL UNIQUE,
                category TEXT NOT NULL,
                reliability_score REAL DEFAULT 1.0,
                enabled INTEGER DEFAULT 1,
                last_fetched_at TEXT,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP
            )
            """)

            # Articles table with constraints
            cursor.execute("""
            CREATE TABLE IF NOT EXISTS articles (
                id TEXT PRIMARY KEY,
                external_id TEXT,
                source_id TEXT NOT NULL,
                source_name TEXT NOT NULL,
                source_domain TEXT NOT NULL,
                title TEXT NOT NULL,
                description TEXT,
                url TEXT NOT NULL,
                canonical_url TEXT NOT NULL,
                author TEXT,
                category TEXT NOT NULL,
                primary_topic TEXT DEFAULT 'Technology',
                image_url TEXT,
                published_at TEXT NOT NULL,
                raw_content_hash TEXT,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (source_id) REFERENCES sources(id)
            )
            """)

            # Fast deterministic deduplication indexes
            cursor.execute("""
            CREATE UNIQUE INDEX IF NOT EXISTS idx_articles_canonical_url
            ON articles(canonical_url)
            """)

            cursor.execute("""
            CREATE UNIQUE INDEX IF NOT EXISTS idx_articles_source_ext_id
            ON articles(source_id, external_id)
            WHERE external_id IS NOT NULL AND external_id != ''
            """)

            cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_articles_published_at
            ON articles(published_at DESC)
            """)

            cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_articles_category
            ON articles(category)
            """)

            # Stories table (Phase 3: Story Intelligence)
            cursor.execute("""
            CREATE TABLE IF NOT EXISTS stories (
                id TEXT PRIMARY KEY,
                title TEXT NOT NULL,
                summary TEXT,
                why_it_matters TEXT,
                category TEXT NOT NULL,
                primary_topic TEXT DEFAULT 'Technology',
                importance_score INTEGER DEFAULT 50,
                relevance_score INTEGER DEFAULT 50,
                freshness_score INTEGER DEFAULT 100,
                source_count INTEGER DEFAULT 1,
                article_count INTEGER DEFAULT 1,
                first_published_at TEXT,
                last_published_at TEXT,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                updated_at TEXT DEFAULT CURRENT_TIMESTAMP
            )
            """)

            cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_stories_category
            ON stories(category)
            """)

            cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_stories_updated_at
            ON stories(updated_at DESC)
            """)

            cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_stories_importance
            ON stories(importance_score DESC)
            """)

            # Ensure story_id column exists on articles table (safe migration)
            cursor.execute("PRAGMA table_info(articles)")
            columns = [row["name"] for row in cursor.fetchall()]
            if "story_id" not in columns:
                cursor.execute("ALTER TABLE articles ADD COLUMN story_id TEXT REFERENCES stories(id)")

            cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_articles_story_id
            ON articles(story_id)
            """)

            # Ensure Phase 4 AI analysis columns exist on stories table (safe migration)
            cursor.execute("PRAGMA table_info(stories)")
            story_columns = [row["name"] for row in cursor.fetchall()]
            new_story_columns = [
                ("ai_title", "TEXT"),
                ("ai_summary", "TEXT"),
                ("ai_category", "TEXT"),
                ("entities_json", "TEXT"),
                ("topics_json", "TEXT"),
                ("analysis_confidence", "REAL"),
                ("analyzed_at", "TEXT"),
                ("analysis_version", "TEXT"),
                ("claims_json", "TEXT")
            ]
            for col_name, col_type in new_story_columns:
                if col_name not in story_columns:
                    cursor.execute(f"ALTER TABLE stories ADD COLUMN {col_name} {col_type}")

            cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_stories_analyzed_at
            ON stories(analyzed_at DESC)
            """)

            # Ensure Phase 5 Global Importance columns exist on stories table (safe migration)
            phase5_columns = [
                ("severity_score", "REAL"),
                ("reach_score", "REAL"),
                ("impact_score", "REAL"),
                ("urgency_score", "REAL"),
                ("novelty_score", "REAL"),
                ("escalation_score", "REAL"),
                ("reporting_breadth_score", "REAL"),
                ("importance_tier", "TEXT"),
                ("importance_explanation", "TEXT"),
                ("importance_version", "TEXT"),
                ("importance_calculated_at", "TEXT")
            ]
            for col_name, col_type in phase5_columns:
                if col_name not in story_columns:
                    cursor.execute(f"ALTER TABLE stories ADD COLUMN {col_name} {col_type}")

            # Phase 6: Relevance columns on stories
            phase6_columns = [
                ("relevance_reason", "TEXT"),
                ("relevance_calculated_at", "TEXT"),
                ("relevance_version", "TEXT")
            ]
            for col_name, col_type in phase6_columns:
                if col_name not in story_columns:
                    cursor.execute(f"ALTER TABLE stories ADD COLUMN {col_name} {col_type}")

            # Phase 7: Story Evolution, Breaking News & Event Lifecycle columns
            phase7_columns = [
                ("story_status", "TEXT DEFAULT 'ACTIVE'"),
                ("breaking_score", "INTEGER DEFAULT 30"),
                ("breaking_level", "TEXT DEFAULT 'STABLE'"),
                ("latest_development", "TEXT"),
                ("latest_updated_at", "TEXT"),
                ("update_count", "INTEGER DEFAULT 0"),
                ("perspectives_json", "TEXT"),
                ("evolution_version", "TEXT"),
                ("evolution_calculated_at", "TEXT")
            ]
            for col_name, col_type in phase7_columns:
                if col_name not in story_columns:
                    cursor.execute(f"ALTER TABLE stories ADD COLUMN {col_name} {col_type}")

            cursor.execute("CREATE INDEX IF NOT EXISTS idx_stories_status ON stories(story_status)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_stories_breaking ON stories(breaking_score DESC)")

            # Phase 7: Story Events table (persistent grounded timeline events)
            cursor.execute("""
            CREATE TABLE IF NOT EXISTS story_events (
                id TEXT PRIMARY KEY,
                story_id TEXT NOT NULL,
                event_type TEXT NOT NULL,
                title TEXT NOT NULL,
                summary TEXT NOT NULL,
                article_ids_json TEXT NOT NULL,
                occurred_at TEXT,
                detected_at TEXT DEFAULT CURRENT_TIMESTAMP,
                significance REAL DEFAULT 0.5,
                event_version TEXT DEFAULT 'v1',
                FOREIGN KEY(story_id) REFERENCES stories(id)
            )
            """)
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_story_events_story_id ON story_events(story_id)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_story_events_detected_at ON story_events(detected_at DESC)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_story_events_occurred_at ON story_events(occurred_at DESC)")

            # Phase 6: User Preferences table
            cursor.execute("""
            CREATE TABLE IF NOT EXISTS user_preferences (
                user_id TEXT PRIMARY KEY,
                interests_json TEXT,
                interest_weights_json TEXT,
                topic_affinities_json TEXT,
                entity_affinities_json TEXT,
                breaking_sensitivity TEXT DEFAULT 'standard',
                importance_threshold INTEGER DEFAULT 50,
                updated_at TEXT DEFAULT CURRENT_TIMESTAMP
            )
            """)

            # Phase 6: User Interactions table
            cursor.execute("""
            CREATE TABLE IF NOT EXISTS user_interactions (
                id TEXT PRIMARY KEY,
                user_id TEXT NOT NULL,
                story_id TEXT NOT NULL,
                interaction_type TEXT NOT NULL,
                metadata_json TEXT,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP
            )
            """)
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_interactions_user_story ON user_interactions(user_id, story_id)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_interactions_created_at ON user_interactions(created_at DESC)")

            # Users table (Authentication & Identity)
            cursor.execute("""
            CREATE TABLE IF NOT EXISTS users (
                id TEXT PRIMARY KEY,
                email TEXT UNIQUE NOT NULL,
                full_name TEXT,
                picture_url TEXT,
                oauth_provider TEXT DEFAULT 'google',
                oauth_sub TEXT,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                last_login_at TEXT DEFAULT CURRENT_TIMESTAMP
            )
            """)
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_users_email ON users(email)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_users_oauth_sub ON users(oauth_sub)")

            # User Saved Stories table (User Data Isolation)
            cursor.execute("""
            CREATE TABLE IF NOT EXISTS user_saved_stories (
                user_id TEXT NOT NULL,
                story_id TEXT NOT NULL,
                saved_at TEXT DEFAULT CURRENT_TIMESTAMP,
                PRIMARY KEY (user_id, story_id),
                FOREIGN KEY (story_id) REFERENCES stories(id)
            )
            """)
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_saved_stories_user ON user_saved_stories(user_id, saved_at DESC)")

            # Phase 8.2: Pipeline Runs table
            cursor.execute("""
            CREATE TABLE IF NOT EXISTS pipeline_runs (
                run_id TEXT PRIMARY KEY,
                status TEXT NOT NULL,
                started_at TEXT,
                completed_at TEXT,
                duration_seconds REAL,
                trigger_type TEXT DEFAULT 'manual',
                user_id TEXT DEFAULT 'default_user',
                skip_ingestion INTEGER DEFAULT 0,
                total_articles INTEGER DEFAULT 0,
                new_articles INTEGER DEFAULT 0,
                total_stories INTEGER DEFAULT 0,
                stories_created INTEGER DEFAULT 0,
                stories_analyzed INTEGER DEFAULT 0,
                stories_scored INTEGER DEFAULT 0,
                stories_evolved INTEGER DEFAULT 0,
                feed_items INTEGER DEFAULT 0,
                failed_stages TEXT DEFAULT '[]',
                error_message TEXT,
                stage_metrics_json TEXT,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                last_heartbeat_at TEXT
            )
            """)
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_pipeline_runs_created_at ON pipeline_runs(created_at DESC)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_pipeline_runs_started_at ON pipeline_runs(started_at DESC)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_pipeline_runs_status ON pipeline_runs(status)")

            # Ensure Phase 8.2 & Phase 9.1 columns exist (safe migration)
            cursor.execute("PRAGMA table_info(pipeline_runs)")
            existing_run_cols = [row["name"] for row in cursor.fetchall()]
            pipeline_run_cols = [
                ("run_id", "TEXT PRIMARY KEY"),
                ("status", "TEXT NOT NULL"),
                ("started_at", "TEXT"),
                ("completed_at", "TEXT"),
                ("duration_seconds", "REAL"),
                ("trigger_type", "TEXT DEFAULT 'manual'"),
                ("user_id", "TEXT DEFAULT 'default_user'"),
                ("skip_ingestion", "INTEGER DEFAULT 0"),
                ("total_articles", "INTEGER DEFAULT 0"),
                ("new_articles", "INTEGER DEFAULT 0"),
                ("total_stories", "INTEGER DEFAULT 0"),
                ("stories_created", "INTEGER DEFAULT 0"),
                ("stories_analyzed", "INTEGER DEFAULT 0"),
                ("stories_scored", "INTEGER DEFAULT 0"),
                ("stories_evolved", "INTEGER DEFAULT 0"),
                ("feed_items", "INTEGER DEFAULT 0"),
                ("failed_stages", "TEXT DEFAULT '[]'"),
                ("error_message", "TEXT"),
                ("stage_metrics_json", "TEXT"),
                ("created_at", "TEXT DEFAULT CURRENT_TIMESTAMP"),
                ("last_heartbeat_at", "TEXT")
            ]
            for col_name, col_type in pipeline_run_cols:
                if col_name not in existing_run_cols:
                    cursor.execute(f"ALTER TABLE pipeline_runs ADD COLUMN {col_name} {col_type}")

            conn.commit()


    def article_exists(self, canonical_url: str, source_id: str, external_id: Optional[str] = None) -> bool:
        """
        Fast deterministic check if an article is already recorded in the database.
        """
        with self._get_connection() as conn:
            cursor = conn.cursor()

            # 1. Canonical URL check
            cursor.execute("SELECT 1 FROM articles WHERE canonical_url = ? LIMIT 1", (canonical_url,))
            if cursor.fetchone():
                return True

            # 2. Source ID + External ID check
            if external_id:
                cursor.execute(
                    "SELECT 1 FROM articles WHERE source_id = ? AND external_id = ? LIMIT 1",
                    (source_id, external_id)
                )
                if cursor.fetchone():
                    return True

            return False

    def insert_article(self, article: Dict[str, Any]) -> bool:
        """
        Inserts a single normalized article.
        Returns True if newly inserted, False if it already exists (duplicate).
        """
        sql = """
        INSERT INTO articles (
            id, external_id, source_id, source_name, source_domain,
            title, description, url, canonical_url, author, category,
            primary_topic, image_url, published_at, raw_content_hash, story_id
        ) VALUES (
            :id, :external_id, :source_id, :source_name, :source_domain,
            :title, :description, :url, :canonical_url, :author, :category,
            :primary_topic, :image_url, :published_at, :raw_content_hash, :story_id
        )
        """
        data = dict(article)
        defaults = {
            "external_id": None,
            "source_id": "default_src",
            "source_name": "News Source",
            "source_domain": "example.com",
            "description": None,
            "author": None,
            "category": "technology",
            "primary_topic": "Technology",
            "image_url": None,
            "raw_content_hash": None,
            "story_id": None
        }
        for k, v in defaults.items():
            if k not in data:
                data[k] = v

        with self._get_connection() as conn:
            cursor = conn.cursor()
            try:
                cursor.execute(sql, data)
                conn.commit()
                return True
            except sqlite3.IntegrityError:
                # Duplicate canonical_url or source_id+external_id
                return False


    def get_articles(
        self,
        category: Optional[str] = None,
        source_id: Optional[str] = None,
        search: Optional[str] = None,
        limit: int = 50,
        offset: int = 0
    ) -> List[Dict[str, Any]]:
        """
        Retrieves real stored articles from the database with filtering and pagination.
        """
        query = "SELECT * FROM articles WHERE 1=1"
        params: List[Any] = []

        if category:
            query += " AND LOWER(category) = LOWER(?)"
            params.append(category)

        if source_id:
            query += " AND (LOWER(source_id) = LOWER(?) OR LOWER(source_domain) LIKE LOWER(?))"
            params.append(source_id)
            params.append(f"%{source_id}%")

        if search:
            query += " AND (LOWER(title) LIKE LOWER(?) OR LOWER(description) LIKE LOWER(?))"
            search_param = f"%{search}%"
            params.append(search_param)
            params.append(search_param)

        query += " ORDER BY published_at DESC LIMIT ? OFFSET ?"
        params.append(limit)
        params.append(offset)

        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(query, params)
            rows = cursor.fetchall()
            return [dict(row) for row in rows]

    def get_article_by_id(self, article_id: str) -> Optional[Dict[str, Any]]:
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM articles WHERE id = ?", (article_id,))
            row = cursor.fetchone()
            return dict(row) if row else None

    def get_articles_in_window(
        self,
        hours: int = 72,
        category: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """
        Retrieves articles within a time window.
        Uses the latest article timestamp as anchor if current UTC has no recent articles,
        ensuring deterministic behavior across ingestion batches.
        """
        with self._get_connection() as conn:
            cursor = conn.cursor()
            
            # Find the latest article timestamp in the DB to anchor window
            cursor.execute("SELECT MAX(published_at) FROM articles")
            max_pub = cursor.fetchone()[0]
            
            if not max_pub:
                return []

            # Compute cutoff in Python to ensure identical behavior on SQLite and PostgreSQL
            try:
                anchor_str = str(max_pub).replace("Z", "+00:00")
                anchor_dt = datetime.fromisoformat(anchor_str)
                cutoff_dt = anchor_dt - timedelta(hours=hours)
                cutoff_iso = cutoff_dt.isoformat()
            except Exception:
                cutoff_iso = str(max_pub)

            query = """
            SELECT * FROM articles
            WHERE published_at >= ?
            """
            params: List[Any] = [cutoff_iso]

            if category:
                query += " AND LOWER(category) = LOWER(?)"
                params.append(category)

            query += " ORDER BY published_at DESC"
            cursor.execute(query, params)
            rows = cursor.fetchall()
            return [dict(row) for row in rows]

    def get_total_count(self, category: Optional[str] = None) -> int:
        query = "SELECT COUNT(*) FROM articles"
        params = []
        if category:
            query += " WHERE LOWER(category) = LOWER(?)"
            params.append(category)

        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(query, params)
            return cursor.fetchone()[0]

    # -------------------------------------------------------------
    # Story Intelligence Methods (Phase 3)
    # -------------------------------------------------------------

    def upsert_story(self, story: Dict[str, Any]) -> str:
        """
        Inserts or updates a story cluster.
        """
        sql = """
        INSERT INTO stories (
            id, title, summary, why_it_matters, category, primary_topic,
            importance_score, relevance_score, freshness_score,
            source_count, article_count, first_published_at, last_published_at,
            created_at, updated_at
        ) VALUES (
            :id, :title, :summary, :why_it_matters, :category, :primary_topic,
            :importance_score, :relevance_score, :freshness_score,
            :source_count, :article_count, :first_published_at, :last_published_at,
            :created_at, :updated_at
        )
        ON CONFLICT(id) DO UPDATE SET
            title = excluded.title,
            summary = excluded.summary,
            why_it_matters = excluded.why_it_matters,
            category = excluded.category,
            primary_topic = excluded.primary_topic,
            importance_score = excluded.importance_score,
            relevance_score = excluded.relevance_score,
            freshness_score = excluded.freshness_score,
            source_count = excluded.source_count,
            article_count = excluded.article_count,
            first_published_at = excluded.first_published_at,
            last_published_at = excluded.last_published_at,
            updated_at = excluded.updated_at
        """
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(sql, story)
            conn.commit()
            return story["id"]

    def insert_story(self, story: Dict[str, Any]) -> str:
        """
        Inserts or updates a story including topics, entities, claims, relevance, and evolution fields.
        """
        now_iso = datetime.utcnow().isoformat()
        sql = """
        INSERT INTO stories (
            id, title, summary, why_it_matters, category, primary_topic,
            importance_score, relevance_score, freshness_score,
            source_count, article_count, first_published_at, last_published_at,
            entities_json, topics_json, claims_json,
            relevance_reason, relevance_version,
            importance_tier,
            story_status, breaking_score, breaking_level,
            latest_development, latest_updated_at, update_count,
            perspectives_json, evolution_version, evolution_calculated_at,
            created_at, updated_at
        ) VALUES (
            :id, :title, :summary, :why_it_matters, :category, :primary_topic,
            :importance_score, :relevance_score, :freshness_score,
            :source_count, :article_count, :first_published_at, :last_published_at,
            :entities_json, :topics_json, :claims_json,
            :relevance_reason, :relevance_version,
            :importance_tier,
            :story_status, :breaking_score, :breaking_level,
            :latest_development, :latest_updated_at, :update_count,
            :perspectives_json, :evolution_version, :evolution_calculated_at,
            :created_at, :updated_at
        )
        ON CONFLICT(id) DO UPDATE SET
            title = excluded.title,
            summary = excluded.summary,
            why_it_matters = excluded.why_it_matters,
            category = excluded.category,
            primary_topic = excluded.primary_topic,
            importance_score = excluded.importance_score,
            relevance_score = excluded.relevance_score,
            freshness_score = excluded.freshness_score,
            source_count = excluded.source_count,
            article_count = excluded.article_count,
            entities_json = excluded.entities_json,
            topics_json = excluded.topics_json,
            claims_json = excluded.claims_json,
            relevance_reason = excluded.relevance_reason,
            relevance_version = excluded.relevance_version,
            importance_tier = excluded.importance_tier,
            story_status = excluded.story_status,
            breaking_score = excluded.breaking_score,
            breaking_level = excluded.breaking_level,
            latest_development = excluded.latest_development,
            latest_updated_at = excluded.latest_updated_at,
            update_count = excluded.update_count,
            perspectives_json = excluded.perspectives_json,
            evolution_version = excluded.evolution_version,
            evolution_calculated_at = excluded.evolution_calculated_at,
            updated_at = excluded.updated_at
        """
        params = {
            "id": story["id"],
            "title": story.get("title", ""),
            "summary": story.get("summary", ""),
            "why_it_matters": story.get("why_it_matters", ""),
            "category": story.get("category", "technology"),
            "primary_topic": story.get("primary_topic", "Technology"),
            "importance_score": int(story.get("importance_score") or 50),
            "relevance_score": int(story.get("relevance_score") or 50),
            "freshness_score": int(story.get("freshness_score") or 90),
            "source_count": int(story.get("source_count") or 1),
            "article_count": int(story.get("article_count") or 1),
            "first_published_at": story.get("first_published_at") or story.get("published_at") or now_iso,
            "last_published_at": story.get("last_published_at") or story.get("published_at") or now_iso,
            "entities_json": json.dumps(story.get("entities") or []),
            "topics_json": json.dumps(story.get("topics") or []),
            "claims_json": json.dumps(story.get("claims") or []),
            "relevance_reason": story.get("relevance_reason"),
            "relevance_version": story.get("relevance_version") or "v1",
            "importance_tier": story.get("importance_tier") or (
                "CRITICAL" if int(story.get("importance_score") or 50) >= 85
                else "HIGH" if int(story.get("importance_score") or 50) >= 70
                else "MEDIUM" if int(story.get("importance_score") or 50) >= 40
                else "LOW"
            ),
            "story_status": story.get("story_status") or "ACTIVE",
            "breaking_score": int(story.get("breaking_score") or (85 if int(story.get("importance_score") or 50) >= 90 else 30)),
            "breaking_level": story.get("breaking_level") or ("BREAKING" if int(story.get("importance_score") or 50) >= 90 else "STABLE"),
            "latest_development": story.get("latest_development"),
            "latest_updated_at": story.get("latest_updated_at") or story.get("last_published_at") or now_iso,
            "update_count": int(story.get("update_count") or 0),
            "perspectives_json": json.dumps(story.get("perspectives") or []),
            "evolution_version": story.get("evolution_version") or "v1",
            "evolution_calculated_at": story.get("evolution_calculated_at") or now_iso,
            "created_at": story.get("created_at") or now_iso,
            "updated_at": story.get("updated_at") or now_iso,
        }
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(sql, params)
            conn.commit()
            return story["id"]

    def link_articles_to_story(self, story_id: str, article_ids: List[str]):

        """
        Associates a list of articles with a story ID.
        """
        if not article_ids:
            return
        placeholders = ",".join("?" for _ in article_ids)
        sql = f"UPDATE articles SET story_id = ? WHERE id IN ({placeholders})"
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(sql, [story_id] + article_ids)
            conn.commit()

    def get_articles_for_story(self, story_id: str) -> List[Dict[str, Any]]:
        """
        Returns all articles linked to a story, ordered by published_at DESC.
        """
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT * FROM articles WHERE story_id = ? ORDER BY published_at DESC",
                (story_id,)
            )
            rows = cursor.fetchall()
            return [dict(row) for row in rows]

    def _format_story_row(self, row: sqlite3.Row) -> Dict[str, Any]:
        """
        Formats a raw story row into a dictionary with deserialized AI fields.
        """
        d = dict(row)

        # Parse entities_json
        raw_entities = d.get("entities_json")
        if raw_entities:
            try:
                d["entities"] = json.loads(raw_entities)
            except Exception:
                d["entities"] = []
        else:
            d["entities"] = []

        # Parse topics_json
        raw_topics = d.get("topics_json")
        if raw_topics:
            try:
                d["topics"] = json.loads(raw_topics)
            except Exception:
                d["topics"] = []
        else:
            d["topics"] = []

        # Parse claims_json
        raw_claims = d.get("claims_json")
        if raw_claims:
            try:
                d["claims"] = json.loads(raw_claims)
            except Exception:
                d["claims"] = []
        else:
            d["claims"] = []

        d["analyzed"] = bool(d.get("analyzed_at"))

        # Build importance breakdown if calculated
        if d.get("severity_score") is not None or d.get("importance_calculated_at"):
            d["importance_breakdown"] = {
                "importance_score": int(d.get("importance_score") or 50),
                "importance_tier": d.get("importance_tier") or "MEDIUM",
                "severity": float(d.get("severity_score") or 0.0),
                "reach": float(d.get("reach_score") or 0.0),
                "impact": float(d.get("impact_score") or 0.0),
                "urgency": float(d.get("urgency_score") or 0.0),
                "novelty": float(d.get("novelty_score") or 0.0),
                "escalation": float(d.get("escalation_score") or 0.0),
                "reporting_breadth": float(d.get("reporting_breadth_score") or 0.0),
                "explanation": d.get("importance_explanation") or "",
                "importance_version": d.get("importance_version") or getattr(settings, "IMPORTANCE_VERSION", "v1"),
                "calculated_at": d.get("importance_calculated_at")
            }
        else:
            d["importance_breakdown"] = None

        d["relevance_score"] = int(d.get("relevance_score") or 50)
        d["relevance_reason"] = d.get("relevance_reason")
        d["relevance_version"] = d.get("relevance_version") or getattr(settings, "RELEVANCE_VERSION", "v1")
        d["relevance_calculated_at"] = d.get("relevance_calculated_at")

        # Parse perspectives_json (Phase 7)
        raw_perspectives = d.get("perspectives_json")
        if raw_perspectives:
            try:
                d["perspectives"] = json.loads(raw_perspectives)
            except Exception:
                d["perspectives"] = []
        else:
            d["perspectives"] = []

        d["story_status"] = d.get("story_status") or "ACTIVE"
        d["breaking_score"] = int(d.get("breaking_score") or 30)
        d["breaking_level"] = d.get("breaking_level") or "STABLE"
        d["latest_development"] = d.get("latest_development")
        d["latest_updated_at"] = d.get("latest_updated_at") or d.get("last_published_at") or d.get("updated_at")
        d["update_count"] = int(d.get("update_count") or 0)
        d["evolution_version"] = d.get("evolution_version") or getattr(settings, "EVOLUTION_VERSION", "v1")
        d["evolution_calculated_at"] = d.get("evolution_calculated_at")

        return d

    def save_story_importance(self, story_id: str, breakdown: Dict[str, Any]) -> bool:
        """
        Persists calculated Global Importance breakdown and scores to the database.
        """
        sql = """
        UPDATE stories SET
            importance_score = :importance_score,
            importance_tier = :importance_tier,
            severity_score = :severity_score,
            reach_score = :reach_score,
            impact_score = :impact_score,
            urgency_score = :urgency_score,
            novelty_score = :novelty_score,
            escalation_score = :escalation_score,
            reporting_breadth_score = :reporting_breadth_score,
            importance_explanation = :importance_explanation,
            importance_version = :importance_version,
            importance_calculated_at = :importance_calculated_at,
            updated_at = :updated_at
        WHERE id = :id
        """
        now_iso = datetime.utcnow().isoformat()
        params = {
            "id": story_id,
            "importance_score": int(breakdown.get("importance_score", 50)),
            "importance_tier": breakdown.get("importance_tier", "MEDIUM"),
            "severity_score": float(breakdown.get("severity", 0.0)),
            "reach_score": float(breakdown.get("reach", 0.0)),
            "impact_score": float(breakdown.get("impact", 0.0)),
            "urgency_score": float(breakdown.get("urgency", 0.0)),
            "novelty_score": float(breakdown.get("novelty", 0.0)),
            "escalation_score": float(breakdown.get("escalation", 0.0)),
            "reporting_breadth_score": float(breakdown.get("reporting_breadth", 0.0)),
            "importance_explanation": breakdown.get("explanation", ""),
            "importance_version": str(breakdown.get("importance_version", getattr(settings, "IMPORTANCE_VERSION", "v1"))),
            "importance_calculated_at": breakdown.get("calculated_at") or now_iso,
            "updated_at": now_iso
        }
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(sql, params)
            conn.commit()
            return cursor.rowcount > 0

    def get_unscored_stories(self, limit: int = 20) -> List[Dict[str, Any]]:
        """
        Retrieves stories that have not yet had their importance calculated.
        """
        query = """
        SELECT * FROM stories
        WHERE importance_calculated_at IS NULL
        ORDER BY source_count DESC, updated_at DESC
        LIMIT ?
        """
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(query, (limit,))
            stories = [self._format_story_row(row) for row in cursor.fetchall()]

        for story in stories:
            story["articles"] = self.get_articles_for_story(story["id"])
        return stories

    # =========================================================================
    # Phase 6: Personalization & User Telemetry Methods
    # =========================================================================

    def get_user_preferences(self, user_id: str = "default_user") -> Dict[str, Any]:
        """Retrieves personalization profile and interest weights."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM user_preferences WHERE user_id = ?", (user_id,))
            row = cursor.fetchone()
            if not row:
                return {
                    "user_id": user_id,
                    "interests": list(getattr(settings, "DEFAULT_USER_INTERESTS", ["AI", "Software Engineering", "Cybersecurity", "Technology", "Science", "Space", "World", "Business", "Economy"])),
                    "interest_weights": dict(getattr(settings, "DEFAULT_INTEREST_WEIGHTS", {})),
                    "topic_affinities": {},
                    "entity_affinities": {},
                    "breaking_sensitivity": "standard",
                    "importance_threshold": 50,
                    "updated_at": datetime.utcnow().isoformat()
                }
            d = dict(row)
            return {
                "user_id": d["user_id"],
                "interests": json.loads(d["interests_json"]) if d.get("interests_json") else [],
                "interest_weights": json.loads(d["interest_weights_json"]) if d.get("interest_weights_json") else dict(getattr(settings, "DEFAULT_INTEREST_WEIGHTS", {})),
                "topic_affinities": json.loads(d["topic_affinities_json"]) if d.get("topic_affinities_json") else {},
                "entity_affinities": json.loads(d["entity_affinities_json"]) if d.get("entity_affinities_json") else {},
                "breaking_sensitivity": d.get("breaking_sensitivity", "standard"),
                "importance_threshold": d.get("importance_threshold", 50),
                "updated_at": d.get("updated_at")
            }

    def save_user_preferences(self, user_id: str, prefs: Dict[str, Any]) -> bool:
        """Saves or updates user interest profile and affinities."""
        sql = """
        INSERT INTO user_preferences (
            user_id, interests_json, interest_weights_json, topic_affinities_json,
            entity_affinities_json, breaking_sensitivity, importance_threshold, updated_at
        ) VALUES (
            :user_id, :interests_json, :interest_weights_json, :topic_affinities_json,
            :entity_affinities_json, :breaking_sensitivity, :importance_threshold, :updated_at
        )
        ON CONFLICT(user_id) DO UPDATE SET
            interests_json = excluded.interests_json,
            interest_weights_json = excluded.interest_weights_json,
            topic_affinities_json = excluded.topic_affinities_json,
            entity_affinities_json = excluded.entity_affinities_json,
            breaking_sensitivity = excluded.breaking_sensitivity,
            importance_threshold = excluded.importance_threshold,
            updated_at = excluded.updated_at
        """
        now_iso = datetime.utcnow().isoformat()
        params = {
            "user_id": user_id,
            "interests_json": json.dumps(prefs.get("interests") or []),
            "interest_weights_json": json.dumps(prefs.get("interest_weights") or {}),
            "topic_affinities_json": json.dumps(prefs.get("topic_affinities") or {}),
            "entity_affinities_json": json.dumps(prefs.get("entity_affinities") or {}),
            "breaking_sensitivity": prefs.get("breaking_sensitivity", "standard"),
            "importance_threshold": prefs.get("importance_threshold", 50),
            "updated_at": now_iso
        }
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(sql, params)
            conn.commit()
            return True

    def record_interaction(
        self,
        user_id: str,
        story_id: str,
        interaction_type: str,
        metadata: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """Records user interaction telemetry in database."""
        now_iso = datetime.utcnow().isoformat()
        import uuid
        int_id = f"int_{uuid.uuid4().hex[:12]}"
        sql = """
        INSERT INTO user_interactions (id, user_id, story_id, interaction_type, metadata_json, created_at)
        VALUES (?, ?, ?, ?, ?, ?)
        """
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(sql, (
                int_id,
                user_id,
                story_id,
                interaction_type,
                json.dumps(metadata or {}),
                now_iso
            ))
            conn.commit()
        return {
            "id": int_id,
            "user_id": user_id,
            "story_id": story_id,
            "interaction_type": interaction_type,
            "metadata": metadata or {},
            "created_at": now_iso
        }

    def get_user_interactions(self, user_id: str = "default_user", limit: int = 100) -> List[Dict[str, Any]]:
        """Retrieves recent user telemetry interactions."""
        query = "SELECT * FROM user_interactions WHERE user_id = ? ORDER BY created_at DESC LIMIT ?"
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(query, (user_id, limit))
            rows = cursor.fetchall()
            results = []
            for row in rows:
                d = dict(row)
                d["metadata"] = json.loads(d["metadata_json"]) if d.get("metadata_json") else {}
                results.append(d)
            return results

    # =========================================================================
    # User Saved Stories (User Isolation)
    # =========================================================================

    def get_hidden_story_ids(self, user_id: str = "default_user") -> List[str]:
        """Returns set of hidden story IDs."""
        query = "SELECT DISTINCT story_id FROM user_interactions WHERE user_id = ? AND interaction_type = 'hide'"
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(query, (user_id,))
            return [row[0] for row in cursor.fetchall()]

    def save_story_relevance(
        self,
        story_id: str,
        relevance_score: int,
        relevance_reason: str,
        version: str = "v1"
    ) -> bool:
        """Persists personal relevance score and reason for a story."""
        sql = """
        UPDATE stories SET
            relevance_score = :relevance_score,
            relevance_reason = :relevance_reason,
            relevance_version = :relevance_version,
            relevance_calculated_at = :relevance_calculated_at,
            updated_at = :updated_at
        WHERE id = :id
        """
        now_iso = datetime.utcnow().isoformat()
        params = {
            "id": story_id,
            "relevance_score": int(relevance_score),
            "relevance_reason": relevance_reason,
            "relevance_version": version,
            "relevance_calculated_at": now_iso,
            "updated_at": now_iso
        }
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(sql, params)
            conn.commit()
            return cursor.rowcount > 0

    def save_story_analysis(self, story_id: str, analysis: Dict[str, Any]) -> bool:
        """
        Persists structured AI story analysis to the database.
        """
        sql = """
        UPDATE stories SET
            ai_title = :ai_title,
            ai_summary = :ai_summary,
            why_it_matters = :why_it_matters,
            ai_category = :ai_category,
            entities_json = :entities_json,
            topics_json = :topics_json,
            claims_json = :claims_json,
            analysis_confidence = :analysis_confidence,
            analyzed_at = :analyzed_at,
            analysis_version = :analysis_version,
            updated_at = :updated_at
        WHERE id = :id
        """
        entities = analysis.get("entities") or []
        entities_serialized = [
            e.model_dump() if hasattr(e, "model_dump") else dict(e)
            for e in entities
        ]

        claims = analysis.get("claims") or []
        claims_serialized = [
            c.model_dump() if hasattr(c, "model_dump") else dict(c)
            for c in claims
        ]

        params = {
            "id": story_id,
            "ai_title": analysis.get("title") or analysis.get("ai_title"),
            "ai_summary": analysis.get("summary") or analysis.get("ai_summary"),
            "why_it_matters": analysis.get("why_it_matters"),
            "ai_category": analysis.get("category") or analysis.get("ai_category"),
            "entities_json": json.dumps(entities_serialized),
            "topics_json": json.dumps(analysis.get("topics") or []),
            "claims_json": json.dumps(claims_serialized),
            "analysis_confidence": float(analysis.get("confidence", 0.9)),
            "analyzed_at": datetime.utcnow().isoformat(),
            "analysis_version": str(analysis.get("analysis_version", getattr(settings, "ANALYSIS_VERSION", "v1.2"))),
            "updated_at": datetime.utcnow().isoformat()
        }
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(sql, params)
            conn.commit()
            return cursor.rowcount > 0

    def get_unanalyzed_stories(self, limit: int = 10) -> List[Dict[str, Any]]:
        """
        Retrieves unanalyzed stories with their articles attached.
        """
        query = """
        SELECT * FROM stories
        WHERE analyzed_at IS NULL
        ORDER BY source_count DESC, importance_score DESC, updated_at DESC
        LIMIT ?
        """
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(query, (limit,))
            stories = [self._format_story_row(row) for row in cursor.fetchall()]

        for story in stories:
            story["articles"] = self.get_articles_for_story(story["id"])
        return stories

    def get_stories(
        self,
        category: Optional[str] = None,
        min_sources: int = 1,
        limit: int = 50,
        offset: int = 0
    ) -> List[Dict[str, Any]]:
        """
        Retrieves stories with populated articles and structured intelligence.
        """
        query = "SELECT * FROM stories WHERE source_count >= ?"
        params: List[Any] = [min_sources]

        if category:
            query += " AND LOWER(category) = LOWER(?)"
            params.append(category)

        query += " ORDER BY importance_score DESC, updated_at DESC LIMIT ? OFFSET ?"
        params.append(limit)
        params.append(offset)

        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(query, params)
            stories = [self._format_story_row(row) for row in cursor.fetchall()]

        # Attach articles to each story
        for story in stories:
            story["articles"] = self.get_articles_for_story(story["id"])

        return stories

    def get_story_by_id(self, story_id: str) -> Optional[Dict[str, Any]]:
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM stories WHERE id = ?", (story_id,))
            row = cursor.fetchone()
            if not row:
                return None
            story = self._format_story_row(row)

        story["articles"] = self.get_articles_for_story(story_id)
        return story

    def get_story(self, story_id: str) -> Optional[Dict[str, Any]]:
        return self.get_story_by_id(story_id)

    def get_article_by_id(self, article_id: str) -> Optional[Dict[str, Any]]:
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM articles WHERE id = ?", (article_id,))
            row = cursor.fetchone()
            return dict(row) if row else None


    def get_total_story_count(self, category: Optional[str] = None, min_sources: int = 1) -> int:

        query = "SELECT COUNT(*) FROM stories WHERE source_count >= ?"
        params: List[Any] = [min_sources]
        if category:
            query += " AND LOWER(category) = LOWER(?)"
            params.append(category)

        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(query, params)
            return cursor.fetchone()[0]

    def get_system_health_stats(self) -> Dict[str, Any]:
        """
        Retrieves aggregated health statistics for the system health monitor.
        """
        with self._get_connection() as conn:
            cursor = conn.cursor()
            # 1. DB responsive check
            cursor.execute("SELECT 1")
            db_healthy = bool(cursor.fetchone())

            # 2. Counts
            cursor.execute("SELECT COUNT(*) FROM articles")
            total_articles = cursor.fetchone()[0]

            cursor.execute("SELECT COUNT(*) FROM stories")
            total_stories = cursor.fetchone()[0]

            cursor.execute("SELECT COUNT(*) FROM stories WHERE analyzed_at IS NOT NULL")
            analyzed_stories = cursor.fetchone()[0]

            cursor.execute("SELECT COUNT(*) FROM stories WHERE importance_calculated_at IS NOT NULL")
            importance_scored_stories = cursor.fetchone()[0]

            cursor.execute("SELECT COUNT(*) FROM stories WHERE story_status IS NOT NULL OR evolution_calculated_at IS NOT NULL")
            evolved_stories = cursor.fetchone()[0]

            cursor.execute("SELECT COUNT(*) FROM sources WHERE enabled = 1")
            source_count = cursor.fetchone()[0]
            if source_count == 0:
                try:
                    from backend.app.services.source_registry import source_registry
                    source_count = len(source_registry.get_enabled())
                except Exception:
                    pass

            # 3. Concurrency / Diagnostics
            if self.is_postgres:
                wal_active = False
                journal_mode = "postgres"
                busy_timeout_ms = 0
            else:
                jm = cursor.execute("PRAGMA journal_mode;").fetchone()
                bt = cursor.execute("PRAGMA busy_timeout;").fetchone()
                wal_active = bool(jm and str(jm[0]).lower() == "wal")
                journal_mode = jm[0] if jm else "unknown"
                busy_timeout_ms = bt[0] if bt else 0

            return {
                "database_healthy": db_healthy,
                "engine": "postgresql" if self.is_postgres else "sqlite",
                "wal_mode_active": wal_active,
                "journal_mode": journal_mode,
                "busy_timeout_ms": busy_timeout_ms,
                "total_articles": total_articles,
                "total_stories": total_stories,
                "analyzed_stories": analyzed_stories,
                "importance_scored_stories": importance_scored_stories,
                "evolved_stories": evolved_stories,
                "ingestion_source_count": source_count
            }

    def reset_story_links(self, article_ids: Optional[List[str]] = None):
        """
        Unlinks articles and removes stories that no longer have articles.
        Enables clean idempotent re-clustering.
        """
        with self._get_connection() as conn:
            cursor = conn.cursor()
            if article_ids:
                placeholders = ",".join("?" for _ in article_ids)
                cursor.execute(f"UPDATE articles SET story_id = NULL WHERE id IN ({placeholders})", article_ids)
            else:
                cursor.execute("UPDATE articles SET story_id = NULL")

            # Remove stories with no linked articles
            cursor.execute("""
            DELETE FROM stories WHERE id NOT IN (
                SELECT DISTINCT story_id FROM articles WHERE story_id IS NOT NULL
            )
            """)
            conn.commit()

    # =========================================================================
    # Phase 7: Story Evolution & Timeline Event Repository Methods
    # =========================================================================
    def insert_story_event(self, event: Dict[str, Any]) -> str:
        """
        Inserts a persistent, grounded timeline event for a story.
        """
        now_iso = datetime.utcnow().isoformat()
        event_id = event.get("id") or f"event_{uuid.uuid4().hex[:12]}"
        sql = """
        INSERT INTO story_events (
            id, story_id, event_type, title, summary,
            article_ids_json, occurred_at, detected_at,
            significance, event_version
        ) VALUES (
            :id, :story_id, :event_type, :title, :summary,
            :article_ids_json, :occurred_at, :detected_at,
            :significance, :event_version
        )
        ON CONFLICT(id) DO UPDATE SET
            event_type = excluded.event_type,
            title = excluded.title,
            summary = excluded.summary,
            article_ids_json = excluded.article_ids_json,
            occurred_at = excluded.occurred_at,
            significance = excluded.significance,
            event_version = excluded.event_version
        """
        raw_article_ids = event.get("article_ids") or []
        if isinstance(raw_article_ids, list):
            article_ids_json = json.dumps(raw_article_ids)
        else:
            article_ids_json = json.dumps([str(raw_article_ids)])

        params = {
            "id": event_id,
            "story_id": event["story_id"],
            "event_type": event.get("event_type", "UPDATE"),
            "title": event.get("title", ""),
            "summary": event.get("summary", ""),
            "article_ids_json": article_ids_json,
            "occurred_at": event.get("occurred_at") or now_iso,
            "detected_at": event.get("detected_at") or now_iso,
            "significance": float(event.get("significance", 0.5)),
            "event_version": event.get("event_version", "v1")
        }
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(sql, params)
            conn.commit()
            return event_id

    def get_story_events(self, story_id: str) -> List[Dict[str, Any]]:
        """
        Retrieves all timeline events associated with a canonical story,
        ordered chronologically.
        """
        sql = """
        SELECT * FROM story_events
        WHERE story_id = ?
        ORDER BY occurred_at ASC, detected_at ASC
        """
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(sql, (story_id,))
            rows = cursor.fetchall()
            events = []
            for row in rows:
                ev = dict(row)
                try:
                    ev["article_ids"] = json.loads(ev.get("article_ids_json") or "[]")
                except Exception:
                    ev["article_ids"] = []
                events.append(ev)
            return events

    def save_story_evolution(self, story_id: str, evolution_data: Dict[str, Any]) -> bool:
        """
        Persists calculated story evolution, lifecycle state, breaking score,
        latest development, and conflicting perspectives.
        """
        now_iso = datetime.utcnow().isoformat()
        perspectives = evolution_data.get("perspectives") or []
        perspectives_json = json.dumps(perspectives)

        sql = """
        UPDATE stories SET
            story_status = :story_status,
            breaking_score = :breaking_score,
            breaking_level = :breaking_level,
            latest_development = :latest_development,
            latest_updated_at = :latest_updated_at,
            update_count = :update_count,
            perspectives_json = :perspectives_json,
            evolution_version = :evolution_version,
            evolution_calculated_at = :evolution_calculated_at,
            updated_at = :updated_at
        WHERE id = :id
        """
        params = {
            "id": story_id,
            "story_status": evolution_data.get("story_status", "ACTIVE"),
            "breaking_score": int(evolution_data.get("breaking_score", 30)),
            "breaking_level": evolution_data.get("breaking_level", "STABLE"),
            "latest_development": evolution_data.get("latest_development"),
            "latest_updated_at": evolution_data.get("latest_updated_at") or now_iso,
            "update_count": int(evolution_data.get("update_count", 0)),
            "perspectives_json": perspectives_json,
            "evolution_version": evolution_data.get("evolution_version") or getattr(settings, "EVOLUTION_VERSION", "v1"),
            "evolution_calculated_at": now_iso,
            "updated_at": now_iso
        }
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(sql, params)
            conn.commit()
            return cursor.rowcount > 0

    def clear_story_events(self, story_id: Optional[str] = None):
        """Clears timeline events for a given story or all stories."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            if story_id:
                cursor.execute("DELETE FROM story_events WHERE story_id = ?", (story_id,))
            else:
                cursor.execute("DELETE FROM story_events")
            conn.commit()

    def clear_stories(self):
        """Removes all stories, story events, and clears story links."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("UPDATE articles SET story_id = NULL")
            cursor.execute("DELETE FROM story_events")
            cursor.execute("DELETE FROM stories")
            conn.commit()

    # =========================================================================
    # Phase 8.2: Pipeline Runs Management
    # =========================================================================

    def _format_pipeline_run_row(self, row: sqlite3.Row) -> Dict[str, Any]:
        """
        Formats a raw pipeline_run row into a dict with deserialized JSON fields and aliases.
        """
        d = dict(row)

        # Parse stage_metrics_json
        raw_metrics = d.get("stage_metrics_json")
        if raw_metrics:
            try:
                d["stage_metrics"] = json.loads(raw_metrics)
            except Exception:
                d["stage_metrics"] = {}
        else:
            d["stage_metrics"] = {}

        # Provide "stages" alias so both `stages` and `stage_metrics` work seamlessly
        d["stages"] = d["stage_metrics"]

        # Parse failed_stages
        raw_failed = d.get("failed_stages")
        if raw_failed:
            try:
                if isinstance(raw_failed, str) and raw_failed.startswith("["):
                    d["failed_stages"] = json.loads(raw_failed)
                elif isinstance(raw_failed, str):
                    d["failed_stages"] = [s.strip() for s in raw_failed.split(",") if s.strip()]
                else:
                    d["failed_stages"] = list(raw_failed)
            except Exception:
                d["failed_stages"] = []
        else:
            d["failed_stages"] = []

        # Ensure total_duration_seconds alias
        d["total_duration_seconds"] = d.get("duration_seconds")
        # Ensure bool conversion for skip_ingestion
        d["skip_ingestion"] = bool(d.get("skip_ingestion"))

        # Operational metrics aliases (Phase 8.2 Step 4)
        stages = d.get("stages") or {}
        ingestion_metrics = stages.get("ingestion") or {}
        personal_relevance_metrics = stages.get("personal_relevance") or {}

        d["duplicate_articles"] = ingestion_metrics.get("duplicates", 0)
        d["duplicates"] = d["duplicate_articles"]
        d["failed_ingestion_sources"] = ingestion_metrics.get("failed_sources", 0)
        d["stories_importance_scored"] = d.get("stories_scored", 0)
        d["stories_relevance_scored"] = personal_relevance_metrics.get("stories_evaluated", 0)
        d["feed_items_ready"] = d.get("feed_items", 0)

        # Heartbeat liveness timestamp (Phase 9.1 Step 4)
        d["last_heartbeat_at"] = d.get("last_heartbeat_at") or d.get("started_at") or d.get("created_at")

        return d

    def create_pipeline_run(
        self,
        run_data: Optional[Dict[str, Any]] = None,
        **kwargs
    ) -> str:
        """
        Creates a new persistent pipeline execution record with initial status.
        """
        params = dict(run_data or {})
        params.update(kwargs)

        now_iso = datetime.utcnow().isoformat()
        run_id = params.get("run_id") or f"run_{uuid.uuid4().hex[:12]}"
        started_at = params.get("started_at") or now_iso
        heartbeat = params.get("last_heartbeat_at") or started_at or now_iso

        stage_metrics = params.get("stage_metrics") or params.get("stages") or {}
        if isinstance(stage_metrics, (dict, list)):
            stage_metrics_json = json.dumps(stage_metrics)
        else:
            stage_metrics_json = str(stage_metrics) if stage_metrics else "{}"

        failed_stages = params.get("failed_stages") or []
        if isinstance(failed_stages, (list, set)):
            failed_stages_json = json.dumps(list(failed_stages))
        else:
            failed_stages_json = str(failed_stages) if failed_stages else "[]"

        sql = """
        INSERT INTO pipeline_runs (
            run_id, status, started_at, completed_at, duration_seconds,
            trigger_type, user_id, skip_ingestion, total_articles, new_articles,
            total_stories, stories_created, stories_analyzed, stories_scored,
            stories_evolved, feed_items, failed_stages, error_message,
            stage_metrics_json, created_at, last_heartbeat_at
        ) VALUES (
            :run_id, :status, :started_at, :completed_at, :duration_seconds,
            :trigger_type, :user_id, :skip_ingestion, :total_articles, :new_articles,
            :total_stories, :stories_created, :stories_analyzed, :stories_scored,
            :stories_evolved, :feed_items, :failed_stages, :error_message,
            :stage_metrics_json, :created_at, :last_heartbeat_at
        )
        """
        db_params = {
            "run_id": run_id,
            "status": params.get("status", "running"),
            "started_at": started_at,
            "completed_at": params.get("completed_at"),
            "duration_seconds": params.get("duration_seconds") if params.get("duration_seconds") is not None else params.get("total_duration_seconds"),
            "trigger_type": params.get("trigger_type", "manual"),
            "user_id": params.get("user_id", "default_user"),
            "skip_ingestion": 1 if params.get("skip_ingestion") else 0,
            "total_articles": int(params.get("total_articles") or 0),
            "new_articles": int(params.get("new_articles") or 0),
            "total_stories": int(params.get("total_stories") or 0),
            "stories_created": int(params.get("stories_created") or 0),
            "stories_analyzed": int(params.get("stories_analyzed") or 0),
            "stories_scored": int(params.get("stories_scored") or 0),
            "stories_evolved": int(params.get("stories_evolved") or 0),
            "feed_items": int(params.get("feed_items") or 0),
            "failed_stages": failed_stages_json,
            "error_message": params.get("error_message"),
            "stage_metrics_json": stage_metrics_json,
            "created_at": params.get("created_at") or now_iso,
            "last_heartbeat_at": heartbeat
        }

        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(sql, db_params)
            conn.commit()

        return run_id

    def update_pipeline_run(self, run_id: str, updates: Dict[str, Any]) -> bool:
        """
        Updates specific fields of a persistent pipeline run.
        """
        if not updates:
            return False

        fields = []
        params = {"run_id": run_id}

        for k, v in updates.items():
            if k in ("stage_metrics", "stages"):
                fields.append("stage_metrics_json = :stage_metrics_json")
                params["stage_metrics_json"] = json.dumps(v) if isinstance(v, (dict, list)) else str(v)
            elif k == "failed_stages":
                fields.append("failed_stages = :failed_stages")
                params["failed_stages"] = json.dumps(list(v)) if isinstance(v, (list, set)) else str(v)
            elif k == "skip_ingestion":
                fields.append("skip_ingestion = :skip_ingestion")
                params["skip_ingestion"] = 1 if v else 0
            elif k == "total_duration_seconds":
                fields.append("duration_seconds = :duration_seconds")
                params["duration_seconds"] = float(v) if v is not None else None
            elif k in (
                "status", "started_at", "completed_at", "duration_seconds",
                "trigger_type", "user_id", "total_articles", "new_articles",
                "total_stories", "stories_created", "stories_analyzed",
                "stories_scored", "stories_evolved", "feed_items", "error_message",
                "last_heartbeat_at"
            ):
                fields.append(f"{k} = :{k}")
                params[k] = v

        if not fields:
            return False

        # Phase 9.1 Step 4: Advance heartbeat on progress unless explicitly specified
        if "last_heartbeat_at" not in updates:
            fields.append("last_heartbeat_at = :auto_heartbeat")
            params["auto_heartbeat"] = datetime.utcnow().isoformat()

        sql = f"UPDATE pipeline_runs SET {', '.join(fields)} WHERE run_id = :run_id"
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(sql, params)
            conn.commit()
            return cursor.rowcount > 0

    def get_pipeline_run(self, run_id: str) -> Optional[Dict[str, Any]]:
        """
        Retrieves a single pipeline run by run_id.
        """
        sql = "SELECT * FROM pipeline_runs WHERE run_id = ? LIMIT 1"
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(sql, (run_id,))
            row = cursor.fetchone()
            if not row:
                return None
            return self._format_pipeline_run_row(row)

    def get_active_pipeline_run(self) -> Optional[Dict[str, Any]]:
        """
        Retrieves any currently active pipeline run (status in 'queued' or 'running').
        """
        sql = "SELECT * FROM pipeline_runs WHERE status IN ('queued', 'running') ORDER BY created_at DESC, run_id DESC LIMIT 1"
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(sql)
            row = cursor.fetchone()
            if not row:
                return None
            return self._format_pipeline_run_row(row)

    def acquire_active_pipeline_run(
        self,
        run_data: Optional[Dict[str, Any]] = None,
        **kwargs
    ) -> Dict[str, Any]:
        """
        Atomically checks and acquires an active pipeline run slot using SQLite BEGIN IMMEDIATE or PostgreSQL transaction.
        Serializes acquisition across concurrent processes/threads:
        1. Acquires immediate write transaction lock.
        2. Checks whether a pipeline run with status 'queued' or 'running' exists.
        3. If an active run exists, immediately rolls back and returns rejection with active run metadata.
        4. If no active run exists, inserts the new run record in 'queued' status within the same transaction,
           commits atomically, and returns success confirmation with the created run record.
        Rolls back on error and guarantees connection closure.
        """
        params = dict(run_data or {})
        params.update(kwargs)

        now_iso = datetime.utcnow().isoformat()
        run_id = params.get("run_id") or f"run_{uuid.uuid4().hex[:12]}"
        trigger_type = params.get("trigger_type", "manual")
        user_id = params.get("user_id", "default_user")
        skip_ingestion = 1 if params.get("skip_ingestion") else 0
        started_at = params.get("started_at") or now_iso
        status = params.get("status", "queued")

        stage_metrics = params.get("stage_metrics") or params.get("stages") or {}
        if isinstance(stage_metrics, (dict, list)):
            stage_metrics_json = json.dumps(stage_metrics)
        else:
            stage_metrics_json = str(stage_metrics) if stage_metrics else "{}"

        failed_stages = params.get("failed_stages") or []
        if isinstance(failed_stages, (list, set)):
            failed_stages_json = json.dumps(list(failed_stages))
        else:
            failed_stages_json = str(failed_stages) if failed_stages else "[]"

        insert_sql = """
        INSERT INTO pipeline_runs (
            run_id, status, started_at, completed_at, duration_seconds,
            trigger_type, user_id, skip_ingestion, total_articles, new_articles,
            total_stories, stories_created, stories_analyzed, stories_scored,
            stories_evolved, feed_items, failed_stages, error_message,
            stage_metrics_json, created_at, last_heartbeat_at
        ) VALUES (
            :run_id, :status, :started_at, :completed_at, :duration_seconds,
            :trigger_type, :user_id, :skip_ingestion, :total_articles, :new_articles,
            :total_stories, :stories_created, :stories_analyzed, :stories_scored,
            :stories_evolved, :feed_items, :failed_stages, :error_message,
            :stage_metrics_json, :created_at, :last_heartbeat_at
        )
        """

        heartbeat = params.get("last_heartbeat_at") or started_at or now_iso
        db_params = {
            "run_id": run_id,
            "status": status,
            "started_at": started_at,
            "completed_at": params.get("completed_at"),
            "duration_seconds": params.get("duration_seconds") if params.get("duration_seconds") is not None else params.get("total_duration_seconds"),
            "trigger_type": trigger_type,
            "user_id": user_id,
            "skip_ingestion": skip_ingestion,
            "total_articles": int(params.get("total_articles") or 0),
            "new_articles": int(params.get("new_articles") or 0),
            "total_stories": int(params.get("total_stories") or 0),
            "stories_created": int(params.get("stories_created") or 0),
            "stories_analyzed": int(params.get("stories_analyzed") or 0),
            "stories_scored": int(params.get("stories_scored") or 0),
            "stories_evolved": int(params.get("stories_evolved") or 0),
            "feed_items": int(params.get("feed_items") or 0),
            "failed_stages": failed_stages_json,
            "error_message": params.get("error_message"),
            "stage_metrics_json": stage_metrics_json,
            "created_at": params.get("created_at") or now_iso,
            "last_heartbeat_at": heartbeat
        }

        with self._get_connection() as conn:
            cursor = conn.cursor()
            if not self.is_postgres:
                cursor.execute("BEGIN IMMEDIATE;")

            cursor.execute(
                "SELECT * FROM pipeline_runs WHERE status IN ('queued', 'running') ORDER BY created_at DESC, run_id DESC LIMIT 1"
            )
            existing_row = cursor.fetchone()
            if existing_row:
                active_run = self._format_pipeline_run_row(existing_row)
                conn.rollback()
                return {
                    "acquired": False,
                    "run_id": None,
                    "run": None,
                    "active_run": active_run,
                    "message": f"A pipeline execution is already in progress ({active_run['run_id']})."
                }

            cursor.execute(insert_sql, db_params)
            conn.commit()

        created_run = self.get_pipeline_run(run_id)
        return {
            "acquired": True,
            "run_id": run_id,
            "run": created_run,
            "active_run": None,
            "message": "Pipeline run acquired successfully."
        }

    def reconcile_orphan_pipeline_runs(self) -> int:
        """
        Reconciles orphan pipeline runs on startup (Phase 9.1 Step 2).
        Finds all pipeline_runs whose status is 'queued' or 'running', marks them as
        'interrupted', sets completed_at to the current UTC timestamp, and records
        an informative error message: 'Execution interrupted by server restart'.
        Returns the number of reconciled rows.
        """
        now_iso = datetime.utcnow().isoformat()
        sql = """
        UPDATE pipeline_runs
        SET status = 'interrupted',
            completed_at = :completed_at,
            error_message = :error_message
        WHERE status IN ('queued', 'running')
        """
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(sql, {
                "completed_at": now_iso,
                "error_message": "Execution interrupted by server restart"
            })
            conn.commit()
            return cursor.rowcount

    def abort_active_pipeline_run(self, run_id: Optional[str] = None) -> Optional[Dict[str, Any]]:
        """
        Administratively aborts an active ('queued' or 'running') pipeline run (Phase 9.1 Step 2).
        Transitions status to 'interrupted', records completed_at UTC timestamp,
        and sets error_message = 'Manually aborted by operator'.
        Returns the updated run dict, or None if no active run existed.
        """
        now = datetime.utcnow()
        now_iso = now.isoformat()
        with self._get_connection() as conn:
            cursor = conn.cursor()
            if run_id:
                cursor.execute(
                    "SELECT * FROM pipeline_runs WHERE run_id = ? AND status IN ('queued', 'running') LIMIT 1",
                    (run_id,)
                )
            else:
                cursor.execute(
                    "SELECT * FROM pipeline_runs WHERE status IN ('queued', 'running') ORDER BY created_at DESC, run_id DESC LIMIT 1"
                )
            row = cursor.fetchone()
            if not row:
                return None

            target_run_id = row["run_id"]
            started_at = row["started_at"]
            duration_seconds = None
            if started_at:
                try:
                    s_dt = datetime.fromisoformat(started_at.replace("Z", "+00:00")).replace(tzinfo=None)
                    duration_seconds = max(0.0, round((now - s_dt).total_seconds(), 2))
                except Exception:
                    pass

            cursor.execute(
                """
                UPDATE pipeline_runs
                SET status = 'interrupted',
                    completed_at = :completed_at,
                    duration_seconds = COALESCE(:duration_seconds, duration_seconds),
                    error_message = :error_message,
                    last_heartbeat_at = :completed_at
                WHERE run_id = :run_id AND status IN ('queued', 'running')
                """,
                {
                    "run_id": target_run_id,
                    "completed_at": now_iso,
                    "duration_seconds": duration_seconds,
                    "error_message": "Manually aborted by operator"
                }
            )
            conn.commit()

        return self.get_pipeline_run(target_run_id)

    def update_pipeline_heartbeat(self, run_id: str, timestamp: Optional[str] = None) -> bool:
        """
        Updates the durable liveness heartbeat timestamp for an active pipeline run (Phase 9.1 Step 4).
        """
        ts = timestamp or datetime.utcnow().isoformat()
        return self.update_pipeline_run(run_id, {"last_heartbeat_at": ts})

    def reconcile_stale_pipeline_runs(
        self,
        stale_timeout_seconds: Optional[int] = None,
        queue_timeout_seconds: Optional[int] = None,
        now: Optional[datetime] = None
    ) -> int:
        """
        Reconciles genuinely stale or abandoned pipeline runs (Phase 9.1 Step 4).
        Inspects only runs with status in ('queued', 'running'):
        - Running runs: stale if time since last heartbeat/progress exceeds stale_timeout_seconds.
        - Queued runs: stale if time in queue without starting exceeds queue_timeout_seconds.
        Transitions eligible runs to 'interrupted', sets completed_at, and records a clear
        error message. Never touches completed/failed/aborted runs.
        Returns the number of reclaimed stale runs.
        """
        if stale_timeout_seconds is None:
            stale_timeout_seconds = getattr(settings, "PIPELINE_STALE_TIMEOUT_SECONDS", 600)
        if queue_timeout_seconds is None:
            queue_timeout_seconds = getattr(settings, "PIPELINE_STALE_QUEUE_TIMEOUT_SECONDS", 300)

        current_time = now or datetime.utcnow()
        current_iso = current_time.isoformat()

        def _parse_ts(val: Optional[str]) -> Optional[datetime]:
            if not val:
                return None
            try:
                clean = val.replace("Z", "+00:00")
                dt = datetime.fromisoformat(clean)
                if dt.tzinfo is not None:
                    return dt.astimezone(timezone.utc).replace(tzinfo=None)
                return dt
            except Exception:
                return None

        stale_runs_to_reclaim = []

        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT * FROM pipeline_runs WHERE status IN ('queued', 'running') ORDER BY created_at ASC"
            )
            rows = cursor.fetchall()
            for r in rows:
                run = self._format_pipeline_run_row(r)
                status = run.get("status")
                ref_ts = run.get("last_heartbeat_at") or run.get("started_at") or run.get("created_at")
                ref_dt = _parse_ts(ref_ts)
                if not ref_dt:
                    continue

                elapsed = (current_time - ref_dt).total_seconds()
                if status == "running" and elapsed > stale_timeout_seconds:
                    stale_runs_to_reclaim.append({
                        "run_id": run["run_id"],
                        "error_message": f"Execution timed out: no heartbeat progress for {int(elapsed)}s (threshold: {stale_timeout_seconds}s)",
                        "started_at": run.get("started_at")
                    })
                elif status == "queued" and elapsed > queue_timeout_seconds:
                    stale_runs_to_reclaim.append({
                        "run_id": run["run_id"],
                        "error_message": f"Execution timed out in queue: abandoned for {int(elapsed)}s without starting (threshold: {queue_timeout_seconds}s)",
                        "started_at": run.get("started_at")
                    })

            if not stale_runs_to_reclaim:
                return 0

            reclaimed_count = 0
            for item in stale_runs_to_reclaim:
                duration_seconds = None
                s_dt = _parse_ts(item.get("started_at"))
                if s_dt:
                    duration_seconds = max(0.0, round((current_time - s_dt).total_seconds(), 2))

                cursor.execute(
                    """
                    UPDATE pipeline_runs
                    SET status = 'interrupted',
                        completed_at = :completed_at,
                        duration_seconds = COALESCE(:duration_seconds, duration_seconds),
                        error_message = :error_message,
                        last_heartbeat_at = :completed_at
                    WHERE run_id = :run_id AND status IN ('queued', 'running')
                    """,
                    {
                        "run_id": item["run_id"],
                        "completed_at": current_iso,
                        "duration_seconds": duration_seconds,
                        "error_message": item["error_message"]
                    }
                )
                if cursor.rowcount > 0:
                    reclaimed_count += cursor.rowcount

            conn.commit()
            return reclaimed_count

    def get_latest_pipeline_run(self) -> Optional[Dict[str, Any]]:
        """
        Retrieves the most recent pipeline execution.
        """
        sql = "SELECT * FROM pipeline_runs ORDER BY created_at DESC, run_id DESC LIMIT 1"
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(sql)
            row = cursor.fetchone()
            if not row:
                return None
            return self._format_pipeline_run_row(row)

    def get_pipeline_runs(
        self,
        limit: int = 20,
        status: Optional[str] = None,
        trigger_type: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """
        Retrieves recent pipeline executions ordered newest first, with optional status and trigger_type filters.
        """
        sql = "SELECT * FROM pipeline_runs"
        clauses = []
        params = []
        if status:
            clauses.append("status = ?")
            params.append(status)
        if trigger_type:
            clauses.append("trigger_type = ?")
            params.append(trigger_type)
        if clauses:
            sql += " WHERE " + " AND ".join(clauses)
        sql += " ORDER BY created_at DESC, run_id DESC LIMIT ?"
        params.append(limit)

        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(sql, tuple(params))
            rows = cursor.fetchall()
            return [self._format_pipeline_run_row(row) for row in rows]

    def get_failure_stats(self) -> Dict[str, Any]:
        """
        Calculates consecutive failure count, last failure timestamp, and last failure message
        from persistent pipeline execution history.
        """
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT status, completed_at, started_at, error_message, stage_metrics_json
                FROM pipeline_runs
                WHERE status IN ('success', 'partial_failure', 'failed')
                ORDER BY created_at DESC, run_id DESC
                LIMIT 50
            """)
            rows = cursor.fetchall()

        consecutive_failures = 0
        last_failure_at = None
        last_failure_message = None

        for row in rows:
            status = row["status"]
            if status in ("failed", "partial_failure"):
                consecutive_failures += 1
                if last_failure_at is None:
                    last_failure_at = row["completed_at"] or row["started_at"]
                    msg = row["error_message"]
                    if not msg and row["stage_metrics_json"]:
                        try:
                            stg = json.loads(row["stage_metrics_json"])
                            for s_name, s_data in stg.items():
                                if s_data.get("status") in ("failed", "partial_failure") and s_data.get("error"):
                                    msg = f"Stage {s_name}: {s_data.get('error')}"
                                    break
                        except Exception:
                            pass
                    last_failure_message = msg or ("Stage failure occurred" if status == "partial_failure" else "Pipeline failed")
            else:
                break

        if last_failure_at is None:
            with self._get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    SELECT completed_at, started_at, error_message, stage_metrics_json, status
                    FROM pipeline_runs
                    WHERE status IN ('partial_failure', 'failed')
                    ORDER BY created_at DESC, run_id DESC
                    LIMIT 1
                """)
                f_row = cursor.fetchone()
                if f_row:
                    last_failure_at = f_row["completed_at"] or f_row["started_at"]
                    last_failure_message = f_row["error_message"] or ("Stage failure occurred" if f_row["status"] == "partial_failure" else "Pipeline failed")

        return {
            "consecutive_failure_count": consecutive_failures,
            "last_failure_at": last_failure_at,
            "last_failure_message": last_failure_message
        }

    # ==========================================
    # User & Authentication Persistence
    # ==========================================

    def upsert_user(
        self,
        email: str,
        full_name: str,
        picture_url: str = "",
        oauth_provider: str = "google",
        oauth_sub: str = ""
    ) -> Dict[str, Any]:
        """
        Creates or updates a user upon authentication.
        Deterministic ID or UUID generation.
        """
        norm_email = email.strip().lower()
        now = datetime.now(timezone.utc).isoformat()
        with self._get_connection() as conn:
            cursor = conn.cursor()
            existing = None
            if oauth_sub:
                cursor.execute(
                    "SELECT * FROM users WHERE oauth_provider = ? AND oauth_sub = ? LIMIT 1",
                    (oauth_provider, oauth_sub)
                )
                existing = cursor.fetchone()
            if not existing:
                cursor.execute("SELECT * FROM users WHERE email = ? LIMIT 1", (norm_email,))
                existing = cursor.fetchone()

            if existing:
                user_id = existing["id"]
                cursor.execute("""
                    UPDATE users
                    SET email = ?, full_name = ?, picture_url = ?, oauth_provider = ?, oauth_sub = ?, last_login_at = ?
                    WHERE id = ?
                """, (norm_email, full_name, picture_url, oauth_provider, oauth_sub or existing["oauth_sub"], now, user_id))
                conn.commit()
                cursor.execute("SELECT * FROM users WHERE id = ?", (user_id,))
                return dict(cursor.fetchone())
            else:
                user_id = f"usr_{uuid.uuid4().hex[:12]}"
                cursor.execute("""
                    INSERT INTO users (id, email, full_name, picture_url, oauth_provider, oauth_sub, created_at, last_login_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """, (user_id, norm_email, full_name, picture_url, oauth_provider, oauth_sub, now, now))
                conn.commit()
                cursor.execute("SELECT * FROM users WHERE id = ?", (user_id,))
                return dict(cursor.fetchone())

    def get_user_by_id(self, user_id: str) -> Optional[Dict[str, Any]]:
        """Retrieves a user by user ID."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM users WHERE id = ?", (user_id,))
            row = cursor.fetchone()
            return dict(row) if row else None

    def get_user_by_email(self, email: str) -> Optional[Dict[str, Any]]:
        """Retrieves a user by email."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM users WHERE email = ? LIMIT 1", (email.strip().lower(),))
            row = cursor.fetchone()
            return dict(row) if row else None

    # ==========================================
    # Per-User Saved Stories Persistence
    # ==========================================

    def save_story(self, user_id: str, story_id: str) -> bool:
        """
        Saves a story for a specific user. Idempotent.
        """
        now = datetime.now(timezone.utc).isoformat()
        with self._get_connection() as conn:
            cursor = conn.cursor()
            if self.is_postgres:
                cursor.execute("""
                    INSERT INTO user_saved_stories (user_id, story_id, saved_at)
                    VALUES (?, ?, ?)
                    ON CONFLICT DO NOTHING
                """, (user_id, story_id, now))
            else:
                cursor.execute("""
                    INSERT OR IGNORE INTO user_saved_stories (user_id, story_id, saved_at)
                    VALUES (?, ?, ?)
                """, (user_id, story_id, now))
            conn.commit()
            return cursor.rowcount > 0

    def unsave_story(self, user_id: str, story_id: str) -> bool:
        """Removes a story from a user's saved list."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                DELETE FROM user_saved_stories
                WHERE user_id = ? AND story_id = ?
            """, (user_id, story_id))
            conn.commit()
            return cursor.rowcount > 0

    def get_saved_story_ids(self, user_id: str = "default_user") -> List[str]:
        """Returns the list of story IDs saved by a specific user."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT story_id FROM user_saved_stories
                WHERE user_id = ?
                ORDER BY saved_at DESC
            """, (user_id,))
            return [row["story_id"] for row in cursor.fetchall()]

    def get_saved_stories(self, user_id: str = "default_user", limit: int = 50) -> List[Dict[str, Any]]:
        """
        Returns full story objects saved by a user, ordered by save time descending.
        """
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT s.*, uss.saved_at
                FROM user_saved_stories uss
                JOIN stories s ON uss.story_id = s.id
                WHERE uss.user_id = ?
                ORDER BY uss.saved_at DESC
                LIMIT ?
            """, (user_id, limit))
            rows = cursor.fetchall()
            results = []
            for row in rows:
                story_dict = dict(row)
                story_dict["articles"] = self.get_articles_for_story(story_dict["id"])
                story_dict["is_saved"] = True
                results.append(story_dict)
            return results

    def clear_pipeline_runs(self):
        """Clears all pipeline runs (used in tests)."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("DELETE FROM pipeline_runs")
            conn.commit()

    def clear_all(self):
        """Clears all articles, story events, stories, and pipeline runs (used in tests)."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("UPDATE articles SET story_id = NULL")
            cursor.execute("DELETE FROM story_events")
            cursor.execute("DELETE FROM stories")
            cursor.execute("DELETE FROM articles")
            cursor.execute("DELETE FROM user_interactions")
            cursor.execute("DELETE FROM user_saved_stories")
            cursor.execute("DELETE FROM user_preferences")
            cursor.execute("DELETE FROM users")
            cursor.execute("DELETE FROM pipeline_runs")
            conn.commit()

db_repository = DbRepository()


