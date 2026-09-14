"""
Tests for Business and Economy category feeds, source registry, and story retrieval.
Verifies that:
1. SourceRegistry includes BBC Business (category: business) and NPR Economy (category: economy).
2. Category relationships in config include business and economy.
3. /api/stories?category=business returns real stories.
4. /api/stories?category=economy returns real stories.
"""
import pytest
from fastapi.testclient import TestClient
from backend.app.main import app
from backend.app.services.source_registry import source_registry
from backend.app.core.config import settings

client = TestClient(app)


def test_source_registry_business_economy():
    """Verifies that business and economy sources are registered and enabled."""
    sources = {s.id: s for s in source_registry.get_all()}
    assert "bbcbusiness" in sources
    assert sources["bbcbusiness"].category == "business"
    assert sources["bbcbusiness"].enabled is True

    assert "nprbusiness" in sources
    assert sources["nprbusiness"].category == "economy"
    assert sources["nprbusiness"].enabled is True


def test_category_relationships_config():
    """Verifies that settings include Business and Economy in default interests and relationships."""
    assert "Business" in settings.DEFAULT_USER_INTERESTS
    assert "Economy" in settings.DEFAULT_USER_INTERESTS
    assert "business" in settings.CATEGORY_RELATIONSHIPS
    assert "economy" in settings.CATEGORY_RELATIONSHIPS


def test_business_and_economy_story_endpoints():
    """Verifies that /api/stories?category=business and /api/stories?category=economy return stories."""
    res_b = client.get("/api/stories?category=business")
    assert res_b.status_code == 200
    data_b = res_b.json()
    assert data_b["total"] > 0
    assert len(data_b["items"]) > 0
    for story in data_b["items"][:5]:
        assert story["category"].lower() in ("business", "economy", "technology")

    res_e = client.get("/api/stories?category=economy")
    assert res_e.status_code == 200
    data_e = res_e.json()
    assert data_e["total"] > 0
    assert len(data_e["items"]) > 0
    for story in data_e["items"][:5]:
        assert story["category"].lower() in ("economy", "business")


def test_empty_database_feed_and_stories_consistency(tmp_path):
    """
    Verifies that on an empty database:
    1. /api/feed returns total=0, items=[], is_empty=True
    2. /api/stories returns total=0, items=[], is_empty=True
    3. /api/stories?category=technology returns total=0, items=[], is_empty=True
    4. Neither endpoint falls back to hardcoded mock stories.
    """
    from backend.app.core.db_repository import db_repository
    test_db = tmp_path / "empty_test.db"
    orig_path = db_repository.db_path
    try:
        db_repository.db_path = str(test_db)
        db_repository.init_db()

        res_feed = client.get("/api/feed?limit=50&offset=0")
        assert res_feed.status_code == 200
        feed_data = res_feed.json()
        assert feed_data["total"] == 0
        assert feed_data["items"] == []
        assert feed_data.get("is_empty") is True

        res_stories = client.get("/api/stories")
        assert res_stories.status_code == 200
        stories_data = res_stories.json()
        assert stories_data["total"] == 0
        assert stories_data["items"] == []
        assert stories_data.get("is_empty") is True

        res_tech = client.get("/api/stories?category=technology")
        assert res_tech.status_code == 200
        tech_data = res_tech.json()
        assert tech_data["total"] == 0
        assert tech_data["items"] == []
        assert tech_data.get("is_empty") is True
    finally:
        db_repository.db_path = orig_path


def test_authoritative_data_source_consistency():
    """
    Verifies that /api/feed and /api/stories operate against the same authoritative DB dataset.
    """
    from backend.app.core.db_repository import db_repository

    # Verify feed items all exist in DB stories
    res_feed = client.get("/api/feed?limit=50&offset=0")
    assert res_feed.status_code == 200
    feed_data = res_feed.json()
    assert feed_data["total"] > 0
    for item in feed_data["items"]:
        db_story = db_repository.get_story_by_id(item["id"])
        assert db_story is not None
        assert not item["id"].startswith("mock-")
        assert not item["id"].startswith("story-00")

    # Verify category feeds all return consistent categories
    for cat in ["technology", "ai", "business", "economy"]:
        res_cat = client.get(f"/api/stories?category={cat}")
        assert res_cat.status_code == 200
        cat_data = res_cat.json()
        assert cat_data["total"] > 0
        for item in cat_data["items"]:
            db_story = db_repository.get_story_by_id(item["id"])
            assert db_story is not None
            assert item["category"].lower() in (cat, "technology", "business", "economy", "ai")
