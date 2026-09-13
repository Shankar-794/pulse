"""
End-to-End Pipeline Integration Test Suite (Phase 8.1).

Validates the full Pulse intelligence pipeline from ingestion to feed delivery:
1. Complete 7-stage pipeline orchestration:
   ingestion -> clustering -> story analysis -> global importance ->
   story evolution -> personal relevance -> feed readiness.
2. Canonical story clustering:
   Multiple articles on the same event remain grouped under one canonical story.
3. Grounded story analysis:
   Structured analysis with grounded claims citing real constituent article IDs.
4. Deterministic Global Importance:
   Observable impact, reach, severity signals with tier assignment.
5. Story Evolution:
   Lifecycle state, breaking score, grounded timeline events, latest developments.
6. Personal Relevance:
   Personalized relevance scores and grounded editorial reasons.
7. Canonical Feed Contract (/api/feed):
   Exposes story_id, title, summary, category, importance_score, importance_tier,
   relevance_score, relevance_reason, breaking_score, breaking_level, story_status,
   latest_development, source_count, topics.
   Does NOT leak internal json fields (rowid, entities_json, topics_json, claims_json).
8. Hidden story telemetry exclusion:
   Hidden stories are strictly omitted from /api/feed.
9. Diversity Controller:
   Interleaves categories (max 2 consecutive from same category).
10. Global Importance Independence:
    User preferences and behavioral interactions never alter global importance.
11. Pipeline Idempotency:
    Re-running the pipeline creates zero duplicate stories and zero duplicate timeline events.
12. System Health Endpoint (/api/system/health):
    Reports database health, pipeline status/duration, story counts, and source status.
"""
import os
import json
import asyncio
import pytest
from datetime import datetime, timezone, timedelta
from unittest.mock import patch
from fastapi.testclient import TestClient

from backend.app.main import app
from backend.app.core.db_repository import db_repository
from backend.app.services.source_registry import NewsSource, source_registry
from backend.app.services.pulse_pipeline import pulse_pipeline
from backend.app.services.personal_relevance_service import personal_relevance_service
from backend.app.services.behavioral_learning_service import behavioral_learning_service


# ==============================================================================
# Controlled Fixture Data
# ==============================================================================

MOCK_SOURCES = [
    NewsSource(
        id="src_tech_1",
        name="Global Tech Wire",
        base_url="https://techwire.example.com",
        feed_url="https://techwire.example.com/rss",
        category="technology",
        primary_topic="Cloud Computing",
        reliability_score=0.95
    ),
    NewsSource(
        id="src_cyber_1",
        name="Security Dispatch",
        base_url="https://secdispatch.example.com",
        feed_url="https://secdispatch.example.com/rss",
        category="cybersecurity",
        primary_topic="Vulnerabilities",
        reliability_score=0.90
    ),
    NewsSource(
        id="src_space_1",
        name="Astro Today",
        base_url="https://astrotoday.example.com",
        feed_url="https://astrotoday.example.com/rss",
        category="space",
        primary_topic="Astrophysics",
        reliability_score=0.92
    ),
    NewsSource(
        id="src_ai_1",
        name="AI Frontiers",
        base_url="https://aifrontiers.example.com",
        feed_url="https://aifrontiers.example.com/rss",
        category="ai",
        primary_topic="Machine Learning",
        reliability_score=0.94
    ),
    NewsSource(
        id="src_biz_1",
        name="Market Digest",
        base_url="https://marketdigest.example.com",
        feed_url="https://marketdigest.example.com/rss",
        category="business",
        primary_topic="Enterprise",
        reliability_score=0.88
    )
]

NOW_ISO = datetime.now(timezone.utc).isoformat()
T_MINUS_1H = (datetime.now(timezone.utc) - timedelta(hours=1)).isoformat()
T_MINUS_2H = (datetime.now(timezone.utc) - timedelta(hours=2)).isoformat()
T_MINUS_3H = (datetime.now(timezone.utc) - timedelta(hours=3)).isoformat()

# Controlled feed items returned by mock fetcher
MOCK_FEED_ITEMS = {
    "src_tech_1": [
        # Article A1: Zero-Day in CloudDB
        {
            "id": "art_clouddb_1",
            "title": "Critical Zero-Day Vulnerability Discovered in CloudDB Database Engine",
            "summary": "Security researchers identified an unauthenticated remote execution flaw in CloudDB enterprise servers.",
            "link": "https://techwire.example.com/clouddb-zero-day",
            "published": T_MINUS_2H
        }
    ],
    "src_cyber_1": [
        # Article A2: Corroborating reporting on same Zero-Day in CloudDB (should cluster with A1!)
        {
            "id": "art_clouddb_2",
            "title": "CloudDB Database Engine Zero-Day Vulnerability Confirmed with Active Exploits",
            "summary": "Security researchers and vendors confirmed the unauthenticated CloudDB remote execution flaw affecting enterprise deployments.",
            "link": "https://secdispatch.example.com/clouddb-flaw-confirmed",
            "published": T_MINUS_1H
        },
        # Article B: Independent Cybersecurity story
        {
            "id": "art_cisco_patch",
            "title": "Cisco Issues Urgent Firmware Updates for Core Enterprise Switches",
            "summary": "Hardware networking vendor patches denial-of-service condition in Catalyst switches.",
            "link": "https://secdispatch.example.com/cisco-catalyst-patch",
            "published": T_MINUS_3H
        }
    ],
    "src_space_1": [
        # Article C: Space story
        {
            "id": "art_jwst_space",
            "title": "James Webb Space Telescope Identifies Atmospheric Methane on Distant Exoplanet",
            "summary": "Spectroscopic analysis reveals definitive hydrocarbon atmospheric signatures in a temperate stellar system.",
            "link": "https://astrotoday.example.com/jwst-methane-exoplanet",
            "published": T_MINUS_2H
        }
    ],
    "src_ai_1": [
        # Article D: AI story
        {
            "id": "art_open_weights",
            "title": "Open Source Foundation Releases Next-Gen Neural Weights Under Apache License",
            "summary": "A high-performance language model foundation releases open weights competitive with proprietary systems.",
            "link": "https://aifrontiers.example.com/open-weights-released",
            "published": T_MINUS_1H
        }
    ],
    "src_biz_1": [
        # Article E: Business story
        {
            "id": "art_cloud_rev",
            "title": "Cloud Infrastructure Spending Surges 28% in Global Quarterly Filings",
            "summary": "Enterprise cloud infrastructure investments accelerated according to consensus quarterly earnings.",
            "link": "https://marketdigest.example.com/cloud-spend-q3",
            "published": T_MINUS_3H
        }
    ]
}


class MockFeedEntry:
    def __init__(self, d):
        self.id = d.get("id")
        self.guid = d.get("id")
        self.title = d.get("title")
        self.description = d.get("summary")
        self.summary = d.get("summary")
        self.link = d.get("link")
        self.published = d.get("published")
        self.pubDate = d.get("published")


def get_mock_source_items(source):
    items = MOCK_FEED_ITEMS.get(source.id, [])
    return [
        {
            "raw_entry": MockFeedEntry(item),
            "source_id": source.id,
            "source_name": source.name,
            "source_base_url": source.base_url,
            "category": source.category,
            "primary_topic": source.primary_topic,
            "reliability_score": source.reliability_score
        }
        for item in items
    ]


async def mock_feed_fetch(source):
    return get_mock_source_items(source)


@pytest.fixture
def client():
    return TestClient(app)


@pytest.fixture
def clean_pipeline_db(tmp_path):
    """Sets up an isolated clean SQLite database for pipeline integration tests."""
    test_db = tmp_path / "test_pipeline.db"
    orig_path = db_repository.db_path
    db_repository.db_path = str(test_db)
    db_repository.init_db()

    # Populate registered sources in test DB
    with db_repository._get_connection() as conn:
        for s in MOCK_SOURCES:
            conn.execute("""
            INSERT OR REPLACE INTO sources (id, name, base_url, feed_url, category, reliability_score, enabled)
            VALUES (?, ?, ?, ?, ?, ?, 1)
            """, (s.id, s.name, s.base_url, s.feed_url, s.category, s.reliability_score))
        conn.commit()

    # Update source_registry to use these sources
    orig_sources = source_registry._sources
    source_registry._sources = {s.id: s for s in MOCK_SOURCES}

    yield

    db_repository.db_path = orig_path
    source_registry._sources = orig_sources


# ==============================================================================
# PIPELINE INTEGRATION TESTS
# ==============================================================================

def test_1_full_pipeline_orchestration_and_metrics(clean_pipeline_db):
    """
    Executes the complete 7-stage pipeline with mocked feed fetching.
    Verifies all 7 stages execute and return structured metrics.
    """
    with patch.object(pulse_pipeline.ingestion.fetcher, "fetch_source_feed", side_effect=mock_feed_fetch):
        summary = asyncio.run(pulse_pipeline.run_pipeline())

    # Verify overall pipeline outcome
    assert summary["status"] == "success"
    assert summary["total_duration_seconds"] > 0
    assert "started_at" in summary
    assert "completed_at" in summary

    stages = summary["stages"]
    assert "ingestion" in stages
    assert "clustering" in stages
    assert "story_analysis" in stages
    assert "global_importance" in stages
    assert "story_evolution" in stages
    assert "personal_relevance" in stages
    assert "feed_readiness" in stages

    # Check stage 1 metrics: Ingestion
    ing_stage = stages["ingestion"]
    assert ing_stage["status"] == "success"
    assert ing_stage["sources_checked"] == len(MOCK_SOURCES)
    assert ing_stage["new_articles"] == 6  # 2 CloudDB + 1 Cisco + 1 JWST + 1 AI + 1 Biz
    assert ing_stage["duplicates"] == 0

    # Check stage 2 metrics: Clustering
    clust_stage = stages["clustering"]
    assert clust_stage["status"] == "success"
    assert clust_stage["articles_processed"] == 6
    assert clust_stage["multi_source_stories"] == 1  # Exactly 1 multi-source story (CloudDB)
    assert clust_stage["stories_created"] == 5       # 1 multi-source + 4 singletons = 5 canonical stories

    # Check stage 3 metrics: Story Analysis
    ana_stage = stages["story_analysis"]
    assert ana_stage["status"] == "success"
    assert ana_stage["analyzed_count"] == 5

    # Check stage 4 metrics: Global Importance
    imp_stage = stages["global_importance"]
    assert imp_stage["status"] == "success"
    assert imp_stage["scored_count"] >= 5

    # Check stage 5 metrics: Story Evolution
    evo_stage = stages["story_evolution"]
    assert evo_stage["status"] == "success"
    assert evo_stage["stories_evolved"] == 5

    # Check stage 6 metrics: Personal Relevance
    rel_stage = stages["personal_relevance"]
    assert rel_stage["status"] == "success"
    assert rel_stage["stories_evaluated"] == 5

    # Check stage 7 metrics: Feed Readiness
    feed_stage = stages["feed_readiness"]
    assert feed_stage["status"] == "success"
    assert feed_stage["feed_items_count"] == 5
    assert len(feed_stage["categories_represented"]) >= 4


def test_2_canonical_clustering_multi_articles(clean_pipeline_db):
    """
    Verifies that multiple articles on the same story remain grouped under
    a single canonical story, and constituent articles cite it.
    """
    with patch.object(pulse_pipeline.ingestion.fetcher, "fetch_source_feed", side_effect=mock_feed_fetch):
        asyncio.run(pulse_pipeline.run_pipeline())

    stories = db_repository.get_stories(limit=10)
    assert len(stories) == 5

    # Find the multi-source CloudDB story
    clouddb_stories = [s for s in stories if "clouddb" in s["title"].lower() or "clouddb" in s["summary"].lower()]
    assert len(clouddb_stories) == 1, "Must form exactly one canonical CloudDB story"

    story = clouddb_stories[0]
    assert story["article_count"] == 2
    assert story["source_count"] == 2

    articles = db_repository.get_articles_for_story(story["id"])
    assert len(articles) == 2
    source_names = {a["source_name"] for a in articles}
    assert "Global Tech Wire" in source_names
    assert "Security Dispatch" in source_names


def test_3_grounded_story_analysis_and_claims(clean_pipeline_db):
    """
    Verifies that story analysis is created and grounded claims cite
    real constituent article IDs.
    """
    with patch.object(pulse_pipeline.ingestion.fetcher, "fetch_source_feed", side_effect=mock_feed_fetch):
        asyncio.run(pulse_pipeline.run_pipeline())

    stories = db_repository.get_stories(limit=10)
    for s in stories:
        assert s.get("analyzed_at") is not None
        assert s.get("ai_summary") is not None
        claims = s.get("claims") or []
        assert len(claims) >= 1

        constituent_arts = db_repository.get_articles_for_story(s["id"])
        art_id_set = {a["id"] for a in constituent_arts}

        for claim in claims:
            assert len(claim["evidence_article_ids"]) >= 1
            # Every cited article must be one of the story's actual constituent articles
            for cited_id in claim["evidence_article_ids"]:
                assert cited_id in art_id_set, f"Cited article {cited_id} must belong to story"


def test_4_global_importance_and_story_evolution(clean_pipeline_db):
    """
    Verifies that global importance is scored and story evolution (lifecycle state,
    breaking score, timeline events) is populated.
    """
    with patch.object(pulse_pipeline.ingestion.fetcher, "fetch_source_feed", side_effect=mock_feed_fetch):
        asyncio.run(pulse_pipeline.run_pipeline())

    stories = db_repository.get_stories(limit=10)
    for s in stories:
        # Importance
        assert 0 <= s["importance_score"] <= 100
        assert s["importance_tier"] in {"CRITICAL", "HIGH", "MEDIUM", "LOW"}
        assert s.get("importance_calculated_at") is not None

        # Story Evolution
        assert s["story_status"] in {"NEW", "DEVELOPING", "ACTIVE", "ESCALATING", "STABLE", "RESOLVED"}
        assert 0 <= s["breaking_score"] <= 100
        assert s["breaking_level"] in {"BREAKING", "DEVELOPING", "UPDATED", "STABLE"}
        assert s.get("latest_development") is not None

        # Timeline events
        events = db_repository.get_story_events(s["id"])
        assert len(events) >= 1
        for ev in events:
            assert ev["event_type"] in {"INITIAL_REPORT", "UPDATE", "DEVELOPMENT", "ESCALATION", "CONTRADICTION", "CORRECTION", "RESOLUTION"}
            assert len(ev["article_ids"]) >= 1


def test_5_feed_endpoint_canonical_contract(client, clean_pipeline_db):
    """
    Verifies that GET /api/feed returns canonical stories with all required fields
    and strictly excludes internal database metadata / json dumps.
    """
    with patch.object(pulse_pipeline.ingestion.fetcher, "fetch_source_feed", side_effect=mock_feed_fetch):
        asyncio.run(pulse_pipeline.run_pipeline())

    resp = client.get("/api/feed?limit=20")
    assert resp.status_code == 200
    data = resp.json()

    assert data["total"] == 5
    items = data["items"]
    assert len(items) == 5

    # Check for exact canonical story uniqueness
    story_ids = [item["id"] for item in items]
    assert len(story_ids) == len(set(story_ids)), "Every story must appear exactly once in feed"

    for item in items:
        # Required Phase 8.1 fields
        assert "id" in item
        assert "story_id" in item
        assert item["id"] == item["story_id"]
        assert "title" in item and item["title"]
        assert "summary" in item and item["summary"]
        assert "category" in item
        assert "importance_score" in item and isinstance(item["importance_score"], int)
        assert "importance_tier" in item and item["importance_tier"] in {"CRITICAL", "HIGH", "MEDIUM", "LOW"}
        assert "relevance_score" in item and isinstance(item["relevance_score"], int)
        assert "relevance_reason" in item and item["relevance_reason"]
        assert "breaking_score" in item and isinstance(item["breaking_score"], int)
        assert "breaking_level" in item and item["breaking_level"] in {"BREAKING", "DEVELOPING", "UPDATED", "STABLE"}
        assert "story_status" in item and item["story_status"]
        assert "latest_development" in item and item["latest_development"]
        assert "source_count" in item and item["source_count"] >= 1
        assert "topics" in item and isinstance(item["topics"], list)

        # STRICT PROHIBITION: internal metadata & raw json fields must NOT be exposed
        assert "rowid" not in item
        assert "entities_json" not in item
        assert "topics_json" not in item
        assert "claims_json" not in item
        assert "raw_content_hash" not in item
        assert "internal_provider" not in item


def test_6_hidden_stories_excluded_from_feed(client, clean_pipeline_db):
    """
    Verifies that hiding a story immediately excludes it from /api/feed.
    """
    with patch.object(pulse_pipeline.ingestion.fetcher, "fetch_source_feed", side_effect=mock_feed_fetch):
        asyncio.run(pulse_pipeline.run_pipeline())

    initial_feed = client.get("/api/feed?limit=20").json()
    assert initial_feed["total"] == 5

    target_story = initial_feed["items"][0]
    target_id = target_story["id"]

    # Record hide interaction
    behavioral_learning_service.process_interaction(
        user_id="default_user",
        story_id=target_id,
        interaction_type="hide"
    )

    # Fetch feed again
    updated_feed = client.get("/api/feed?limit=20").json()
    updated_ids = [item["id"] for item in updated_feed["items"]]

    assert target_id not in updated_ids, "Hidden story must be excluded from feed"
    assert updated_feed["total"] == 4


def test_7_diversity_controller_category_interleaving(clean_pipeline_db):
    """
    Verifies that the Diversity Controller enforces category interleaving
    (max 2 consecutive stories from the same category).
    """
    with patch.object(pulse_pipeline.ingestion.fetcher, "fetch_source_feed", side_effect=mock_feed_fetch):
        asyncio.run(pulse_pipeline.run_pipeline())

    feed_items = pulse_pipeline.feed.rank_feed(user_id="default_user", limit=20)
    assert len(feed_items) == 5

    categories = [personal_relevance_service.normalize_category(item.get("category")) for item in feed_items]
    consecutive = 1
    for i in range(1, len(categories)):
        if categories[i] == categories[i - 1]:
            consecutive += 1
            assert consecutive <= 2, f"Diversity violation: category '{categories[i]}' appeared > 2 consecutive times"
        else:
            consecutive = 1


def test_8_global_importance_strict_independence(clean_pipeline_db):
    """
    Verifies that user interactions and preference updates NEVER modify
    the objective Global Importance score.
    """
    with patch.object(pulse_pipeline.ingestion.fetcher, "fetch_source_feed", side_effect=mock_feed_fetch):
        asyncio.run(pulse_pipeline.run_pipeline())

    stories = db_repository.get_stories(limit=10)
    story = stories[0]
    original_importance = story["importance_score"]
    original_tier = story["importance_tier"]

    # Update user preferences drastically (e.g. increase affinity, change interests)
    db_repository.save_user_preferences("default_user", {
        "interests": ["Space", "World"],
        "interest_weights": {"Space": 1.0, "World": 1.0, "Technology": 0.0, "Cybersecurity": 0.0},
        "topic_affinities": {"space": 0.95, "technology": 0.05},
        "entity_affinities": {}
    })

    # Record telemetry interactions
    behavioral_learning_service.process_interaction("default_user", story["id"], "read")
    behavioral_learning_service.process_interaction("default_user", story["id"], "save")

    # Fetch the story from DB again
    refetched_story = db_repository.get_story_by_id(story["id"])
    assert refetched_story["importance_score"] == original_importance, "Global Importance must NOT change due to user preferences"
    assert refetched_story["importance_tier"] == original_tier, "Importance tier must remain strictly unchanged"


def test_9_pipeline_idempotency(clean_pipeline_db):
    """
    Verifies that running the pipeline twice does not duplicate stories
    or timeline events.
    """
    with patch.object(pulse_pipeline.ingestion.fetcher, "fetch_source_feed", side_effect=mock_feed_fetch):
        # Run 1
        run1 = asyncio.run(pulse_pipeline.run_pipeline())
        assert run1["status"] == "success"
        count1 = db_repository.get_total_story_count()
        events1 = sum(len(db_repository.get_story_events(s["id"])) for s in db_repository.get_stories(limit=10))

        # Run 2 (re-execution over the same data)
        run2 = asyncio.run(pulse_pipeline.run_pipeline())
        assert run2["status"] == "success"
        count2 = db_repository.get_total_story_count()
        events2 = sum(len(db_repository.get_story_events(s["id"])) for s in db_repository.get_stories(limit=10))

    assert count1 == count2, "Story count must be identical across pipeline runs"
    assert events1 == events2, "Timeline events must not duplicate across pipeline runs"


def test_10_system_health_endpoint(client, clean_pipeline_db):
    """
    Verifies GET /api/system/health returns complete system metrics.
    """
    with patch.object(pulse_pipeline.ingestion.fetcher, "fetch_source_feed", side_effect=mock_feed_fetch):
        asyncio.run(pulse_pipeline.run_pipeline())

    resp = client.get("/api/system/health")
    assert resp.status_code == 200
    data = resp.json()

    assert data["status"] == "healthy"
    assert data["database_health"] == "healthy"
    assert data["total_stories"] == 5
    assert data["analyzed_stories"] == 5
    assert data["importance_scored_stories"] == 5
    assert data["evolved_stories"] == 5
    assert data["total_articles"] == 6
    assert data["ingestion_source_count"] == len(MOCK_SOURCES)
    assert data["last_ingestion_status"] == "success"

    pipeline_info = data["pipeline"]
    assert pipeline_info["last_run_status"] == "success"
    assert pipeline_info["last_run_time"] is not None
    assert pipeline_info["last_run_duration_seconds"] > 0
    assert len(pipeline_info["stages"]) == 7


def test_11_pipeline_api_endpoints(client, clean_pipeline_db):
    """
    Verifies POST /api/pipeline/run and GET /api/pipeline/status HTTP contracts.
    """
    with patch.object(pulse_pipeline.ingestion.fetcher, "fetch_source_feed", side_effect=mock_feed_fetch):
        # Trigger pipeline run via API
        post_resp = client.post("/api/pipeline/run?skip_ingestion=false")
        assert post_resp.status_code == 200
        run_data = post_resp.json()
        assert run_data["status"] == "accepted"
        assert "run_id" in run_data

        # Inspect pipeline status via API
        status_resp = client.get("/api/pipeline/status")
        assert status_resp.status_code == 200
        status_data = status_resp.json()
        assert status_data["status"] == "success"
        assert status_data["total_duration_seconds"] > 0
