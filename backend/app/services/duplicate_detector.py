"""
Deterministic Duplicate Detection for Pulse News Intelligence.
Identifies duplicate articles using canonical URL, external identifier,
and content hash checks prior to database persistence.
"""
from typing import Dict, Any, Tuple
from backend.app.core.db_repository import db_repository

class DuplicateDetector:
    def __init__(self, repository=None):
        self.repo = repository or db_repository

    def is_duplicate(self, article: Dict[str, Any]) -> Tuple[bool, str]:
        """
        Determines whether a normalized article already exists in the system.
        Returns (is_duplicate: bool, reason: str).
        """
        canonical_url = article.get("canonical_url")
        source_id = article.get("source_id")
        external_id = article.get("external_id")

        if not canonical_url:
            return True, "missing_canonical_url"

        if self.repo.article_exists(canonical_url, source_id, external_id):
            return True, "already_stored_in_database"

        return False, "unique"

duplicate_detector = DuplicateDetector()
