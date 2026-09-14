"""
Source Registry for Pulse News Intelligence.
Maintains the centralized catalogue of permitted, verified public feeds.
Adding a new source is as simple as adding an entry to DEFAULT_SOURCES.
"""
from typing import List, Optional, Dict
from datetime import datetime

from backend.app.core.sources_data import NewsSource, DEFAULT_SOURCES


class SourceRegistry:
    """
    Registry management for news feeds.
    """
    def __init__(self):
        self._sources: Dict[str, NewsSource] = {s.id: s for s in DEFAULT_SOURCES}

    def get_all(self) -> List[NewsSource]:
        return list(self._sources.values())

    def get_enabled(self) -> List[NewsSource]:
        return [s for s in self._sources.values() if s.enabled]

    def get_by_id(self, source_id: str) -> Optional[NewsSource]:
        return self._sources.get(source_id)

    def register(self, source: NewsSource) -> NewsSource:
        self._sources[source.id] = source
        try:
            from backend.app.core.db_repository import db_repository
            db_repository.upsert_source(source)
        except Exception:
            pass
        return source

    def update_fetch_status(self, source_id: str, status: str, count: int = 0):
        source = self._sources.get(source_id)
        if source:
            source.last_fetched_at = datetime.utcnow().isoformat()
            source.last_fetch_status = status
            source.articles_fetched_count += count
            try:
                from backend.app.core.db_repository import db_repository
                db_repository.update_source_fetch_status(source_id, source.last_fetched_at)
            except Exception:
                pass

source_registry = SourceRegistry()
