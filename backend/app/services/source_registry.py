"""
Source Registry for Pulse News Intelligence.
Maintains the centralized catalogue of permitted, verified public feeds.
Adding a new source is as simple as adding an entry to DEFAULT_SOURCES.
"""
from dataclasses import dataclass, asdict
from typing import List, Optional, Dict
from datetime import datetime

@dataclass
class NewsSource:
    id: str
    name: str
    base_url: str
    feed_url: str
    category: str
    primary_topic: str
    reliability_score: float = 0.9
    enabled: bool = True
    last_fetched_at: Optional[str] = None
    last_fetch_status: Optional[str] = None
    articles_fetched_count: int = 0

    def to_dict(self) -> Dict:
        return asdict(self)

DEFAULT_SOURCES = [
    NewsSource(
        id="hackernews",
        name="Hacker News",
        base_url="https://news.ycombinator.com",
        feed_url="https://news.ycombinator.com/rss",
        category="technology",
        primary_topic="Software Engineering",
        reliability_score=0.92,
        enabled=True
    ),
    NewsSource(
        id="arstechnica",
        name="Ars Technica",
        base_url="https://arstechnica.com",
        feed_url="https://feeds.arstechnica.com/arstechnica/index",
        category="technology",
        primary_topic="Semiconductors & Systems",
        reliability_score=0.95,
        enabled=True
    ),
    NewsSource(
        id="krebsonsecurity",
        name="Krebs on Security",
        base_url="https://krebsonsecurity.com",
        feed_url="https://krebsonsecurity.com/feed/",
        category="cybersecurity",
        primary_topic="Cybersecurity Threats",
        reliability_score=0.96,
        enabled=True
    ),
    NewsSource(
        id="bleepingcomputer",
        name="BleepingComputer",
        base_url="https://www.bleepingcomputer.com",
        feed_url="https://www.bleepingcomputer.com/feed/",
        category="cybersecurity",
        primary_topic="Vulnerabilities & Exploits",
        reliability_score=0.94,
        enabled=True
    ),
    NewsSource(
        id="mitnews",
        name="MIT News Research",
        base_url="https://news.mit.edu",
        feed_url="https://news.mit.edu/rss/research",
        category="science",
        primary_topic="Applied Sciences",
        reliability_score=0.98,
        enabled=True
    ),
    NewsSource(
        id="nasa",
        name="NASA Breaking News",
        base_url="https://www.nasa.gov",
        feed_url="https://www.nasa.gov/news-release/feed/",
        category="space",
        primary_topic="Space Exploration",
        reliability_score=0.97,
        enabled=True
    ),
    NewsSource(
        id="bbctech",
        name="BBC Technology",
        base_url="https://www.bbc.com/news/technology",
        feed_url="https://feeds.bbci.co.uk/news/technology/rss.xml",
        category="world",
        primary_topic="Global Technology & Policy",
        reliability_score=0.93,
        enabled=True
    ),
    NewsSource(
        id="theverge",
        name="The Verge",
        base_url="https://www.theverge.com",
        feed_url="https://www.theverge.com/rss/index.xml",
        category="ai",
        primary_topic="Artificial Intelligence",
        reliability_score=0.90,
        enabled=True
    )
]

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
        return source

    def update_fetch_status(self, source_id: str, status: str, count: int = 0):
        source = self._sources.get(source_id)
        if source:
            source.last_fetched_at = datetime.utcnow().isoformat()
            source.last_fetch_status = status
            source.articles_fetched_count += count

source_registry = SourceRegistry()
