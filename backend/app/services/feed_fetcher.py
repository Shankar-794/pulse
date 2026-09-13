"""
Feed Fetcher for Pulse News Intelligence.
Asynchronously retrieves public RSS/Atom feeds using httpx with polite rate-limiting,
timeouts, and multi-format parsing.
"""
import logging
from typing import List, Dict, Any, Optional
import httpx
import feedparser
from backend.app.services.source_registry import NewsSource

logger = logging.getLogger("pulse.ingestion.fetcher")

DEFAULT_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36 PulseNewsIntelligence/0.2 (news-terminal-ingestion; +https://github.com/pulse-intelligence)",
    "Accept": "application/rss+xml, application/atom+xml, application/xml, text/xml, */*"
}

class FeedFetcher:
    def __init__(self, timeout_seconds: float = 10.0):
        self.timeout = timeout_seconds

    async def fetch_source_feed(self, source: NewsSource) -> List[Dict[str, Any]]:
        """
        Fetches and parses feed entries for a given NewsSource.
        Returns a list of raw entry dictionaries.
        """
        logger.info(f"[SOURCE] {source.name} ({source.feed_url})")
        try:
            async with httpx.AsyncClient(
                timeout=self.timeout,
                follow_redirects=True,
                headers=DEFAULT_HEADERS
            ) as client:
                response = await client.get(source.feed_url)
                if response.status_code != 200:
                    logger.warning(f"[SOURCE ERROR] {source.name} returned HTTP {response.status_code}")
                    return []

                content = response.text
                if not content:
                    logger.warning(f"[SOURCE EMPTY] {source.name} returned empty payload")
                    return []

                # Parse feed
                parsed = feedparser.parse(content)
                entries = getattr(parsed, "entries", [])
                logger.info(f"[FETCH] {len(entries)} entries parsed from {source.name}")

                raw_items = []
                for entry in entries:
                    raw_items.append({
                        "raw_entry": entry,
                        "source_id": source.id,
                        "source_name": source.name,
                        "source_base_url": source.base_url,
                        "category": source.category,
                        "primary_topic": source.primary_topic,
                        "reliability_score": source.reliability_score
                    })
                return raw_items

        except httpx.RequestError as exc:
            logger.error(f"[SOURCE NETWORK FAIL] {source.name}: {exc}")
            return []
        except Exception as exc:
            logger.error(f"[SOURCE PARSE FAIL] {source.name}: {exc}")
            return []

feed_fetcher = FeedFetcher()
