"""
Comprehensive Unit Tests for Story Intelligence Semantic Clustering (Phase 3 & 3B).
Tests:
1. Similar article lexical similarity
2. Entity overlap calculation
3. Hybrid similarity calculation
4. Different-event separation
5. Related-category candidate selection
6. Threshold calibration behavior
7. Diagnostics calculation
8. Idempotent clustering re-runs
9. Multi-source story creation
"""
import pytest
from datetime import datetime

from backend.app.services.clustering_service import ClusteringService
from backend.app.services.entity_extractor import entity_extractor
from backend.app.services.similarity_provider import TFIDFSimilarityProvider
from backend.app.core.db_repository import DbRepository


@pytest.fixture
def test_repo(tmp_path):
    """Creates an isolated temporary SQLite database for testing."""
    db_file = tmp_path / "test_clustering.db"
    repo = DbRepository(db_path=str(db_file))
    return repo


@pytest.fixture
def clustering_service(test_repo):
    """Returns an upgraded ClusteringService instance connected to the test repository."""
    return ClusteringService(
        similarity_threshold=0.32,
        time_window_hours=72,
        lexical_weight=0.65,
        entity_weight=0.35,
        db_repo=test_repo
    )


# 1. Similar article lexical similarity
def test_lexical_similarity_same_event():
    provider = TFIDFSimilarityProvider()
    t1 = "Anthropic boss Dario Amodei calls for AI development to slow down"
    t2 = "Anthropic CEO Dario Amodei says AI development must slow down"
    sim = provider.compute_pairwise(t1, t2)
    assert sim >= 0.50, f"Expected high lexical similarity, got {sim}"


# 2. Entity overlap calculation
def test_entity_overlap_extraction_and_scoring():
    t1 = "NASA moving at warp speed to set up US Space Academy"
    t2 = "NASA Answers Presidents Call to Establish United States Space Academy"
    e1 = entity_extractor.extract_entities(t1)
    e2 = entity_extractor.extract_entities(t2)

    assert "nasa" in e1
    assert "space" in e1 or "space academy" in e1
    score, common = entity_extractor.compute_overlap(e1, e2, title_similarity=0.31)
    assert score >= 0.50, f"Expected strong entity overlap score, got {score}"
    assert "nasa" in common


# 3. Hybrid similarity calculation
def test_hybrid_similarity_calculation(clustering_service):
    a1 = {
        "title": "LG responds to TV spying allegations",
        "description": "LG says user tracking concerns are unfounded.",
        "category": "ai",
        "primary_topic": "Privacy"
    }
    a2 = {
        "title": "LG denies TV spying claims, says tracking and snooping concerns 'not true'",
        "description": "LG electronics pushes back against smart TV surveillance reports.",
        "category": "technology",
        "primary_topic": "Hardware"
    }
    t_sim = 0.38
    f_sim = 0.35
    e1 = entity_extractor.extract_entities(a1["title"])
    e2 = entity_extractor.extract_entities(a2["title"])

    hybrid, lex, ent, common = clustering_service.compute_pair_similarity(
        a1, a2, t_sim, f_sim, e1, e2
    )
    assert hybrid >= 0.35, f"Expected hybrid >= 0.35, got {hybrid}"
    assert "lg" in common


# 4. Different-event separation
def test_different_event_separation(clustering_service):
    """Articles about different events should have low similarity and not cluster."""
    a1 = {
        "title": "OpenAI releases new reasoning model GPT-5",
        "description": "OpenAI today unveiled GPT-5 with multimodal reasoning.",
        "category": "ai"
    }
    a2 = {
        "title": "Google announces Pixel 9 Pro camera features",
        "description": "Google launches new flagship smartphone with advanced camera sensors.",
        "category": "technology"
    }
    e1 = entity_extractor.extract_entities(a1["title"])
    e2 = entity_extractor.extract_entities(a2["title"])
    hybrid, _, _, _ = clustering_service.compute_pair_similarity(
        a1, a2, title_sim=0.0, full_sim=0.05, entities_a=e1, entities_b=e2
    )
    assert hybrid < 0.20, f"Expected low hybrid similarity for different events, got {hybrid}"


# 5. Related-category candidate selection
def test_related_category_candidate_selection(clustering_service):
    # Same category
    assert clustering_service.is_candidate_pair("technology", "technology") is True
    # Related categories
    assert clustering_service.is_candidate_pair("ai", "technology") is True
    assert clustering_service.is_candidate_pair("technology", "world") is True
    assert clustering_service.is_candidate_pair("space", "science") is True
    assert clustering_service.is_candidate_pair("cybersecurity", "technology") is True


# 6. Threshold behavior
def test_threshold_behavior(clustering_service):
    # Cluster threshold should reject borderline unconfirmed pairings below 0.32
    articles = [
        {"id": "1", "title": "Apple announces M4 MacBook Air", "category": "technology"},
        {"id": "2", "title": "Google unveils Chromebook Plus lineup", "category": "technology"}
    ]
    clusters = clustering_service.cluster_candidates(articles)
    assert len(clusters) == 2, "Unrelated product announcements should not merge"


# 7. Diagnostics calculation
def test_diagnostics_calculation(test_repo, clustering_service):
    articles = [
        {
            "id": "a1",
            "source_id": "src-verge",
            "source_name": "The Verge",
            "source_domain": "theverge.com",
            "title": "LG responds to TV spying allegations",
            "description": "LG responds to claims regarding TV monitoring.",
            "url": "https://theverge.com/lg",
            "canonical_url": "https://theverge.com/lg",
            "category": "ai",
            "published_at": "2026-09-12T10:00:00Z"
        },
        {
            "id": "a2",
            "source_id": "src-hn",
            "source_name": "Hacker News",
            "source_domain": "news.ycombinator.com",
            "title": "LG denies TV spying claims, says tracking concerns not true",
            "description": "LG electronics denies smart TV snooping allegations.",
            "url": "https://news.ycombinator.com/item?id=123",
            "canonical_url": "https://news.ycombinator.com/item?id=123",
            "category": "technology",
            "published_at": "2026-09-12T10:30:00Z"
        }
    ]
    for art in articles:
        test_repo.insert_article(art)

    diag = clustering_service.compute_diagnostics()
    assert diag["articles"] == 2
    assert diag["candidate_pairs"] == 1
    assert diag["similarity"]["max"] >= 0.30
    assert "thresholds" in diag
    assert len(diag["top_pairs"]) == 1


# 8. Idempotent clustering & 9. Multi-source story creation
def test_idempotent_multi_source_clustering(test_repo, clustering_service):
    articles = [
        {
            "id": "art-1",
            "source_id": "src-bbc",
            "source_name": "BBC Technology",
            "source_domain": "bbc.com",
            "title": "Anthropic boss Dario Amodei calls for AI development to slow down",
            "description": "Anthropic chief executive Dario Amodei warns of AI risks.",
            "url": "https://bbc.com/amodei",
            "canonical_url": "https://bbc.com/amodei",
            "category": "world",
            "published_at": "2026-09-12T08:00:00Z"
        },
        {
            "id": "art-2",
            "source_id": "src-hn",
            "source_name": "Hacker News",
            "source_domain": "news.ycombinator.com",
            "title": "Everyone should slow down AI development except for me",
            "description": "Discussion on Dario Amodei calls for AI development to slow down.",
            "url": "https://news.ycombinator.com/amodei",
            "canonical_url": "https://news.ycombinator.com/amodei",
            "category": "technology",
            "published_at": "2026-09-12T08:30:00Z"
        },
        {
            "id": "art-3",
            "source_id": "src-krebs",
            "source_name": "Krebs on Security",
            "source_domain": "krebsonsecurity.com",
            "title": "Major cyber extortion group leaks executive credentials",
            "description": "Extortion ring publishes corporate tokens.",
            "url": "https://krebsonsecurity.com/extortion",
            "canonical_url": "https://krebsonsecurity.com/extortion",
            "category": "cybersecurity",
            "published_at": "2026-09-12T09:00:00Z"
        }
    ]

    for art in articles:
        test_repo.insert_article(art)

    # First run
    metrics1 = clustering_service.run_clustering()
    assert metrics1["articles_processed"] == 3
    assert metrics1["stories_created"] == 2
    assert metrics1["multi_source_stories"] == 1
    assert metrics1["singleton_stories"] == 1
    assert metrics1["max_sources_in_story"] == 2

    # Verify story in DB has 2 articles and 2 sources
    stories = test_repo.get_stories(min_sources=2)
    assert len(stories) == 1
    assert stories[0]["source_count"] == 2
    assert len(stories[0]["articles"]) == 2

    # Second run (Idempotency test)
    metrics2 = clustering_service.run_clustering()
    assert metrics2["stories_created"] == 2
    assert metrics2["multi_source_stories"] == 1
    assert test_repo.get_total_story_count() == 2, "Re-running must NOT duplicate stories"
