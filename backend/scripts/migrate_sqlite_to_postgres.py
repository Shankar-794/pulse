#!/usr/bin/env python3
"""
Pulse Migration Utility: SQLite to PostgreSQL.

Copies existing relational data from a local SQLite database file into a
PostgreSQL database instance (such as Render PostgreSQL).
Handles:
- Automatic schema initialization (init_pg_db)
- Ordered table migration respecting foreign key constraints
- Batch inserts with ON CONFLICT DO NOTHING for idempotent retries
- Row count verification and detailed progress logging
"""
import os
import sys
import sqlite3
import argparse
import logging
from pathlib import Path

# Add project root to sys.path
PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from backend.app.core.config import settings
from backend.app.core.db_repository import (
    DbRepository,
    DEFAULT_SQLITE_PATH,
    normalize_postgres_url,
    PSYCOPG2_AVAILABLE
)

if PSYCOPG2_AVAILABLE:
    import psycopg2
    import psycopg2.extras

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s"
)
logger = logging.getLogger("pulse.migration")

# Ordered to preserve referential integrity
TABLES_IN_ORDER = [
    "sources",
    "stories",
    "articles",
    "story_events",
    "user_preferences",
    "user_interactions",
    "users",
    "user_saved_stories",
    "pipeline_runs"
]


def migrate(sqlite_path: str, postgres_url: str, batch_size: int = 200) -> bool:
    if not PSYCOPG2_AVAILABLE:
        logger.error("psycopg2 is not installed. Please run: pip install psycopg2-binary")
        return False

    sqlite_file = Path(sqlite_path)
    if not sqlite_file.exists():
        logger.error(f"SQLite database file not found at: {sqlite_path}")
        return False

    norm_pg_url = normalize_postgres_url(postgres_url)
    if not norm_pg_url:
        logger.error("A valid PostgreSQL connection URL must be provided.")
        return False

    logger.info(f"Connecting to SQLite: {sqlite_path}")
    sqlite_conn = sqlite3.connect(str(sqlite_file))
    sqlite_conn.row_factory = sqlite3.Row

    logger.info("Connecting to PostgreSQL and initializing schema...")
    try:
        pg_repo = DbRepository(postgres_url=norm_pg_url)
        pg_conn = psycopg2.connect(norm_pg_url)
    except Exception as e:
        logger.error(f"Failed to connect to PostgreSQL: {e}")
        return False

    migration_summary = {}

    try:
        for table in TABLES_IN_ORDER:
            # Check if table exists in SQLite
            cur_sqlite = sqlite_conn.cursor()
            cur_sqlite.execute(
                "SELECT name FROM sqlite_master WHERE type='table' AND name=?",
                (table,)
            )
            if not cur_sqlite.fetchone():
                logger.info(f"Table '{table}' does not exist in SQLite source. Skipping.")
                continue

            # Count rows in SQLite
            cur_sqlite.execute(f"SELECT COUNT(*) FROM {table}")
            total_source_rows = cur_sqlite.fetchone()[0]
            if total_source_rows == 0:
                logger.info(f"Table '{table}' is empty in source database (0 rows).")
                migration_summary[table] = {"source": 0, "migrated": 0}
                continue

            # Fetch all rows from SQLite
            cur_sqlite.execute(f"SELECT * FROM {table}")
            sample_row = cur_sqlite.fetchone()
            if not sample_row:
                continue

            column_names = list(sample_row.keys())
            cols_str = ", ".join(f'"{col}"' for col in column_names)
            placeholders = ", ".join(["%s"] * len(column_names))
            insert_sql = f"""
            INSERT INTO {table} ({cols_str})
            VALUES ({placeholders})
            ON CONFLICT DO NOTHING
            """

            # Reset cursor and fetch in batches
            cur_sqlite.execute(f"SELECT * FROM {table}")
            inserted_count = 0

            with pg_conn.cursor() as pg_cur:
                while True:
                    batch = cur_sqlite.fetchmany(batch_size)
                    if not batch:
                        break
                    batch_data = [tuple(row[col] for col in column_names) for row in batch]
                    psycopg2.extras.execute_batch(pg_cur, insert_sql, batch_data)
                    inserted_count += len(batch_data)
                    logger.info(f"Table '{table}': migrated {inserted_count}/{total_source_rows} rows...")

                pg_conn.commit()

            # Verify destination count
            with pg_conn.cursor() as pg_cur:
                pg_cur.execute(f"SELECT COUNT(*) FROM {table}")
                dest_count = pg_cur.fetchone()[0]

            migration_summary[table] = {
                "source": total_source_rows,
                "dest_total": dest_count,
                "transferred": inserted_count
            }
            logger.info(f"Successfully finished table '{table}': {inserted_count} rows processed.")

        logger.info("=" * 60)
        logger.info("DATABASE MIGRATION COMPLETED SUCCESSFULLY")
        logger.info("=" * 60)
        for tbl, stats in migration_summary.items():
            logger.info(f" - {tbl:20s}: source={stats.get('source', 0):4d} -> postgres_total={stats.get('dest_total', 0):4d}")
        logger.info("=" * 60)
        return True

    except Exception as err:
        logger.error(f"Migration failed with error: {err}", exc_info=True)
        pg_conn.rollback()
        return False
    finally:
        sqlite_conn.close()
        pg_conn.close()


def main():
    parser = argparse.ArgumentParser(description="Migrate Pulse SQLite database to PostgreSQL.")
    parser.add_argument(
        "--sqlite-path",
        default=str(getattr(settings, "SQLITE_DB_PATH", None) or DEFAULT_SQLITE_PATH),
        help="Path to the SQLite database file"
    )
    parser.add_argument(
        "--postgres-url",
        default=os.getenv("DATABASE_URL") or getattr(settings, "DATABASE_URL", ""),
        help="PostgreSQL connection URL (or set DATABASE_URL environment variable)"
    )
    parser.add_argument(
        "--batch-size",
        type=int,
        default=200,
        help="Batch size for batch inserts"
    )

    args = parser.parse_args()

    if not args.postgres_url:
        logger.error("Error: --postgres-url or DATABASE_URL environment variable is required.")
        sys.exit(1)

    success = migrate(args.sqlite_path, args.postgres_url, args.batch_size)
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
