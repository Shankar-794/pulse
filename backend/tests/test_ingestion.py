"""
Unit tests for Pulse News Ingestion Pipeline.
Tests feed parsing, normalization, duplicate detection, failure isolation, and database insertion.
"""
import os
import pytest
from datetime import datetime
from unittest.mock import AsyncMock, patch

from backend.app.services.article_normalizer import (
    strip_html_tags,
    normalize_canonical_url,
    article_normalizer
)
from backend.app.services.source_registry import NewsSource, SourceRegistry
from backend.app.core.db_repository import DbRepository
from backend.app.services.duplicate_detector import DuplicateDetector
from backend.app.services.ingestion_service import IngestionService

SAMPLE_RSS_XML = """<?xml version="1.0" encoding="UTF-8" ?>
<rss version="2.0">
<channel>
 <title>Test Tech News</title>
 <description>Testing RSS Feed</description>
 <link>https://example.com</link>
 <item>
  <title>New Microprocessor Architecture Breakthrough</title>
  <description><![CDATA[<p>Researchers announced a new <b>nanosheet</b> transistor design with 30% lower leakage.</p>]]></description>
  <link>https://example.com/article/101?utm_source=rss&amp;utm_medium=feed&amp;ref=tracker</link>
  <guid>item-guid-101</guid>
  <pubDate>Sun, 13 Sep 2026 04:00:00 GMT</pubDate>
 </item>
 <item>
  <title>Critical Kernel Security Advisory Released</title>
  <description>Emergency patch released for memory safety issue.</description>
  <link>https://example.com/security/cve-2026?fbclid=xyz123</link>
  <guid>item-guid-102</guid>
  <pubDate>Sun, 13 Sep 2026 05:30:00 GMT</pubDate>
 </item>
</channel>
</rss>
"""

@pytest.fixture
def temp_db(tmp_path):
    db_file = tmp_path / "test_pulse.db"
    repo = DbRepository(db_path=str(db_file))
    yield repo
    if db_file.exists():
        try:
            os.remove(db_file)
        except Exception:
            pass

# 1. Test HTML Stripping & Normalization
def test_html_tag_stripping():
    raw_html = "<p>This is a <b>bold</b> test with <a href='https://example.com'>link</a> &amp; &quot;quotes&quot;.</p>"
    cleaned = strip_html_tags(raw_html)
    assert cleaned == 'This is a bold test with link & "quotes".'
    assert "<" not in cleaned and ">" not in cleaned

# 2. Test Canonical URL Cleaning
def test_canonical_url_cleaning():
    dirty_url = "https://ArsTechnica.com/technology/article/?utm_source=twitter&utm_medium=social&fbclid=12345&ref=banner#frag"
    cleaned = normalize_canonical_url(dirty_url)
    assert cleaned == "https://arstechnica.com/technology/article"
    assert "utm_source" not in cleaned
    assert "fbclid" not in cleaned

# 3. Test Entry Normalization
def test_article_normalization():
    import feedparser
    parsed = feedparser.parse(SAMPLE_RSS_XML)
    raw_item = {
        "raw_entry": parsed.entries[0],
        "source_id": "testsource",
        "source_name": "Test Source",
        "source_base_url": "https://example.com",
        "category": "technology",
        "primary_topic": "Semiconductors",
        "reliability_score": 0.95
    }

    normalized = article_normalizer.normalize_entry(raw_item)
    assert normalized is not None
    assert normalized["title"] == "New Microprocessor Architecture Breakthrough"
    assert "nanosheet" in normalized["description"]
    assert "<p>" not in normalized["description"]
    assert normalized["canonical_url"] == "https://example.com/article/101"
    assert normalized["external_id"] == "item-guid-101"
    assert normalized["category"] == "technology"

# 4. Test Duplicate Detection
def test_duplicate_detection(temp_db):
    detector = DuplicateDetector(repository=temp_db)
    article = {
        "id": "art-test-01",
        "external_id": "guid-001",
        "source_id": "testsource",
        "source_name": "Test Source",
        "source_domain": "example.com",
        "title": "Unique Article",
        "description": "Article summary",
        "url": "https://example.com/article/1",
        "canonical_url": "https://example.com/article/1",
        "author": "Alice",
        "category": "technology",
        "primary_topic": "Software",
        "image_url": None,
        "published_at": "2026-09-13T00:00:00",
        "raw_content_hash": "hash001"
    }

    # Initial check: should not be duplicate
    is_dup, reason = detector.is_duplicate(article)
    assert is_dup is False
    assert reason == "unique"

    # Insert into database
    inserted = temp_db.insert_article(article)
    assert inserted is True

    # Second check: must be recognized as duplicate
    is_dup, reason = detector.is_duplicate(article)
    assert is_dup is True
    assert reason == "already_stored_in_database"

# 5. Test Database Insertion & Queries
def test_database_insertion_and_filtering(temp_db):
    art1 = {
        "id": "art-01",
        "external_id": "id-1",
        "source_id": "src1",
        "source_name": "Source One",
        "source_domain": "one.com",
        "title": "Quantum Computing Gate Array",
        "description": "Quantum algorithms update",
        "url": "https://one.com/quantum",
        "canonical_url": "https://one.com/quantum",
        "author": "Dr. Smith",
        "category": "science",
        "primary_topic": "Quantum",
        "image_url": None,
        "published_at": "2026-09-13T02:00:00",
        "raw_content_hash": "hash1"
    }
    art2 = {
        "id": "art-02",
        "external_id": "id-2",
        "source_id": "src2",
        "source_name": "Source Two",
        "source_domain": "two.com",
        "title": "Linux Kernel Patch Released",
        "description": "Operating system update",
        "url": "https://two.com/linux",
        "canonical_url": "https://two.com/linux",
        "author": "Linus",
        "category": "cybersecurity",
        "primary_topic": "Security",
        "image_url": None,
        "published_at": "2026-09-13T03:00:00",
        "raw_content_hash": "hash2"
    }

    assert temp_db.insert_article(art1) is True
    assert temp_db.insert_article(art2) is True
    assert temp_db.get_total_count() == 2

    # Query with category filter
    science_articles = temp_db.get_articles(category="science")
    assert len(science_articles) == 1
    assert science_articles[0]["title"] == "Quantum Computing Gate Array"

    # Query with search keyword
    kernel_articles = temp_db.get_articles(search="Kernel")
    assert len(kernel_articles) == 1
    assert kernel_articles[0]["id"] == "art-02"

# 6. Test Source Failure Isolation in Ingestion Service
def test_source_failure_isolation(temp_db):
    import asyncio

    async def _test():
        service = IngestionService()
        service.repo = temp_db
        service.detector = DuplicateDetector(repository=temp_db)

        failing_source = NewsSource(
            id="failing_src",
            name="Failing Feed",
            base_url="https://invalid-non-existent-domain.xyz",
            feed_url="https://invalid-non-existent-domain.xyz/rss",
            category="technology",
            primary_topic="Testing",
            enabled=True
        )

        registry = SourceRegistry()
        registry._sources = {"failing_src": failing_source}
        service.registry = registry

        # Run ingestion with mock network failure
        with patch("backend.app.services.feed_fetcher.FeedFetcher.fetch_source_feed", new_callable=AsyncMock) as mock_fetch:
            mock_fetch.return_value = []
            summary = await service.run_ingestion_cycle()

        assert summary["sources_checked"] == 1
        assert summary["failed_sources"] == 1
        assert summary["new_articles"] == 0
        assert summary["duplicates"] == 0

    asyncio.run(_test())
