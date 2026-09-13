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
