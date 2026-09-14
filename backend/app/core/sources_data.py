"""
Default sources and source data definitions for Pulse News Intelligence.
Kept in core to prevent circular import dependencies between core and services.
"""
from dataclasses import dataclass, asdict
from typing import List, Optional, Dict

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
    ),
    NewsSource(
        id="bbcbusiness",
        name="BBC Business",
        base_url="https://www.bbc.com/news/business",
        feed_url="https://feeds.bbci.co.uk/news/business/rss.xml",
        category="business",
        primary_topic="Business & Markets",
        reliability_score=0.94,
        enabled=True
    ),
    NewsSource(
        id="nprbusiness",
        name="NPR Economy",
        base_url="https://www.npr.org/sections/business/",
        feed_url="https://feeds.npr.org/1006/rss.xml",
        category="economy",
        primary_topic="Economy & Global Finance",
        reliability_score=0.93,
        enabled=True
    )
]
