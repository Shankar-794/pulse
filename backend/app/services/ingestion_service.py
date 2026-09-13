"""
Ingestion Service for Pulse News Intelligence.
Orchestrates fetching, normalizing, deduplicating, and persisting news articles
from permitted sources into the database.
"""
import time
import logging
from typing import Dict, Any, List
from datetime import datetime

from backend.app.services.source_registry import source_registry, NewsSource
from backend.app.services.feed_fetcher import feed_fetcher
from backend.app.services.article_normalizer import article_normalizer
from backend.app.services.duplicate_detector import duplicate_detector
from backend.app.core.db_repository import db_repository

logger = logging.getLogger("pulse.ingestion")

class IngestionService:
    def __init__(self):
        self.registry = source_registry
        self.fetcher = feed_fetcher
        self.normalizer = article_normalizer
        self.detector = duplicate_detector
        self.repo = db_repository
        self._last_summary: Dict[str, Any] = {}

    async def run_ingestion_cycle(self) -> Dict[str, Any]:
        """
        Executes a complete ingestion run across all enabled registered sources.
        """
        start_time = time.time()
        print("\n[INGESTION] Starting ingestion cycle")
        logger.info("[INGESTION] Starting ingestion cycle")

        enabled_sources = self.registry.get_enabled()
        total_sources = len(enabled_sources)
        articles_seen = 0
        new_articles_count = 0
        duplicates_count = 0
        failed_sources_count = 0
        source_breakdowns = []

        for source in enabled_sources:
            print(f"\n[SOURCE] {source.name}")
            logger.info(f"[SOURCE] {source.name}")

            raw_items = await self.fetcher.fetch_source_feed(source)
            if not raw_items:
                print(f"[SOURCE FAILED] {source.name} returned 0 items or encountered error")
                self.registry.update_fetch_status(source.id, "failed", 0)
                failed_sources_count += 1
                source_breakdowns.append({
                    "source_id": source.id,
                    "source_name": source.name,
                    "seen": 0,
                    "new": 0,
                    "duplicates": 0,
                    "status": "failed"
                })
                continue

            entries_count = len(raw_items)
            articles_seen += entries_count
            print(f"[FETCH] {entries_count} entries")

            source_new = 0
            source_dup = 0

            for raw_item in raw_items:
                normalized = self.normalizer.normalize_entry(raw_item)
                if not normalized:
                    continue

                is_dup, reason = self.detector.is_duplicate(normalized)
                if is_dup:
                    source_dup += 1
                    duplicates_count += 1
                else:
                    inserted = self.repo.insert_article(normalized)
                    if inserted:
                        source_new += 1
                        new_articles_count += 1
                    else:
                        source_dup += 1
                        duplicates_count += 1

            print(f"[NEW] {source_new} articles")
            print(f"[DUPLICATE] {source_dup} articles")

            self.registry.update_fetch_status(source.id, "success", source_new)
            source_breakdowns.append({
                "source_id": source.id,
                "source_name": source.name,
                "seen": entries_count,
                "new": source_new,
                "duplicates": source_dup,
                "status": "success"
            })

        duration = round(time.time() - start_time, 2)
        summary = {
            "sources_checked": total_sources,
            "articles_seen": articles_seen,
            "new_articles": new_articles_count,
            "duplicates": duplicates_count,
            "failed_sources": failed_sources_count,
            "duration_seconds": duration,
            "completed_at": datetime.utcnow().isoformat(),
            "source_breakdowns": source_breakdowns
        }

        self._last_summary = summary

        print("\n[INGESTION] Complete")
        print(f"Sources: {total_sources}")
        print(f"New articles: {new_articles_count}")
        print(f"Duplicates: {duplicates_count}")
        print(f"Failures: {failed_sources_count}")
        print(f"Duration: {duration}s\n")

        logger.info(
            f"[INGESTION] Complete: Sources={total_sources}, New={new_articles_count}, "
            f"Duplicates={duplicates_count}, Failures={failed_sources_count}, Duration={duration}s"
        )

        return summary

    def get_last_summary(self) -> Dict[str, Any]:
        return self._last_summary

ingestion_service = IngestionService()
