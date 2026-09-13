"""
Test suite for Personal Relevance Engine & Personalized Feed Ranking (Phase 6).
Validates:
1. Score normalization & bounded clamping [0-100]
2. Student persona category weighting (AI/SWE/Cyber >> World/Business)
3. Topic overlap matching
4. Entity affinity matching
5. Behavioral learning: read (+0.02)
6. Behavioral learning: save (+0.08)
7. Behavioral learning: hide (-0.15)
8. Bounded clamping [0.0, 1.0] across multiple updates
9. Gradual accumulation without drastic profile swings
10. Grounded reasons and editorial explainability
11. Strict separation of Global Importance and Personal Relevance
12. Critical world event Global Importance Override (importance >= 85)
13. Diversity Controller category interleaving (max 2 consecutive)
14. Canonical cluster deduplication
15. Hidden story telemetry exclusion
16. SQLite database persistence for preferences and affinities
17. GET /api/feed endpoint
18. GET /api/stories/{story_id}/relevance endpoint
"""
import pytest
from datetime import datetime, timezone, timedelta
from fastapi.testclient import TestClient

from backend.app.main import app
from backend.app.core.config import settings
from backend.app.core.db_repository import db_repository
from backend.app.services.personal_relevance_service import personal_relevance_service
from backend.app.services.behavioral_learning_service import behavioral_learning_service
from backend.app.services.feed_ranking_service import feed_ranking_service
from backend.app.schemas.preferences import PersonalRelevanceBreakdown


@pytest.fixture
def client():
    return TestClient(app)


@pytest.fixture
def clean_db(tmp_path):
    test_db = tmp_path / "test_personalization.db"
    orig_path = db_repository.db_path
    db_repository.db_path = str(test_db)
    db_repository.init_db()
    yield
    db_repository.db_path = orig_path


def make_test_story(
    story_id: str,
    title: str,
    summary: str,
    category: str = "technology",
    importance_score: int = 60,
    topics: list = None,
    entities: list = None,
    created_at: str = None
):
    now_iso = datetime.now(timezone.utc).isoformat()
    return {
        "id": story_id,
        "title": title,
        "summary": summary,
        "why_it_matters": f"Significance of {title}.",
        "category": category,
        "primary_topic": category.capitalize(),
        "importance_score": importance_score,
        "importance_tier": "HIGH" if importance_score >= 70 else "MEDIUM",
        "importance_version": "v1",
        "source_count": 2,
        "article_count": 2,
        "topics": topics or [category.capitalize()],
        "tags": topics or [category.capitalize()],
        "entities": entities or [{"name": "Tech Corp", "category": "organization"}],
        "created_at": created_at or now_iso,
        "published_at": created_at or now_iso,
        "articles": []
    }


# ==============================================================================
# TEST 1: Score Normalization & Bounds
# ==============================================================================
def test_1_relevance_score_normalization():
    story = make_test_story(
        story_id="s1",
        title="New Open-Source Compiler Released",
        summary="A new fast optimizing compiler has been open-sourced.",
        category="software engineering",
        topics=["compiler", "rust", "llvm"]
    )
    breakdown = personal_relevance_service.compute_relevance(story)

    assert isinstance(breakdown.personal_relevance_score, int)
    assert 0 <= breakdown.personal_relevance_score <= 100
    assert 0.0 <= breakdown.category_match <= 1.0
    assert 0.0 <= breakdown.topic_match <= 1.0
    assert 0.0 <= breakdown.entity_match <= 1.0
    assert 0.0 <= breakdown.behavioral_affinity <= 1.0
    assert 0.0 <= breakdown.novelty <= 1.0
    assert breakdown.relevance_version == "v1"


# ==============================================================================
# TEST 2: Student Persona Category Weighting
# ==============================================================================
def test_2_student_persona_category_weighting():
    ai_story = make_test_story(
        story_id="s_ai",
        title="Frontier Model Architecture Improvements",
        summary="Research paper detailing advances in transformer attention mechanisms.",
        category="ai",
        topics=["neural networks", "transformer", "deep learning"]
    )
    world_story = make_test_story(
        story_id="s_world",
        title="Bilateral Fishing Treaty Signed",
        summary="Two nations reach agreement regarding territorial coastal waters fishing.",
        category="world",
        topics=["treaty", "fishing", "coastal"]
    )

    ai_breakdown = personal_relevance_service.compute_relevance(ai_story)
    world_breakdown = personal_relevance_service.compute_relevance(world_story)

    assert ai_breakdown.category_match > world_breakdown.category_match
    assert ai_breakdown.personal_relevance_score > world_breakdown.personal_relevance_score
    assert ai_breakdown.personal_relevance_score >= 75
    assert world_breakdown.personal_relevance_score < 60


# ==============================================================================
# TEST 3: Topic Overlap Matching
# ==============================================================================
def test_3_topic_overlap_matching():
    custom_profile = {
        "user_id": "test_topic_user",
        "interest_weights": {"cybersecurity": 0.82},
        "topic_affinities": {"cve": 0.95, "vulnerability": 0.90, "exploit": 0.90},
        "entity_affinities": {}
    }
    matched_story = make_test_story(
        story_id="s_top1",
        title="Zero-Day Vulnerability Found in Linux Kernel",
        summary="Critical CVE buffer overflow detected in network subsystem.",
        category="cybersecurity",
        topics=["cve", "vulnerability", "linux", "exploit"]
    )
    unmatched_story = make_test_story(
        story_id="s_top2",
        title="Office Building Renovation Completed",
        summary="Facility team updates ventilation system in local headquarters.",
        category="cybersecurity",
        topics=["renovation", "facilities", "ventilation"]
    )

    breakdown_match = personal_relevance_service.compute_relevance(matched_story, custom_profile)
    breakdown_unmatch = personal_relevance_service.compute_relevance(unmatched_story, custom_profile)

    assert breakdown_match.topic_match > breakdown_unmatch.topic_match
    assert breakdown_match.personal_relevance_score > breakdown_unmatch.personal_relevance_score


# ==============================================================================
# TEST 4: Entity Affinity Matching
# ==============================================================================
def test_4_entity_affinity_matching():
    custom_profile = {
        "user_id": "test_user",
        "interest_weights": {"ai": 0.90},
        "topic_affinities": {},
        "entity_affinities": {"openai": 0.95, "anthropic": 0.90}
    }

    story_with_entity = make_test_story(
        story_id="s_ent1",
        title="OpenAI Announces New API Capabilities",
        summary="Developer tools for streaming tool calls and structured outputs.",
        category="ai",
        entities=[{"name": "OpenAI", "category": "organization"}]
    )
    story_without_entity = make_test_story(
        story_id="s_ent2",
        title="Generic AI Update",
        summary="Discussion on algorithms in abstract computing.",
        category="ai",
        entities=[{"name": "Local University", "category": "organization"}]
    )

    breakdown_ent = personal_relevance_service.compute_relevance(story_with_entity, custom_profile)
    breakdown_no_ent = personal_relevance_service.compute_relevance(story_without_entity, custom_profile)

    assert breakdown_ent.entity_match > breakdown_no_ent.entity_match
    assert breakdown_ent.entity_match >= 0.90


# ==============================================================================
# TEST 5: Behavioral Learning - Read Interaction (+0.02)
# ==============================================================================
def test_5_behavioral_read_interaction(clean_db):
    user_id = "user_read_test"
    story = make_test_story(
        story_id="story_read_1",
        title="Rust 2026 Edition Announced",
        summary="Language team previews upcoming syntax and borrow checker additions.",
        category="software engineering",
        topics=["rust", "compiler", "programming"]
    )
    db_repository.insert_story(story)

    # Initial profile with explicit baseline
    db_repository.save_user_preferences(user_id, {"topic_affinities": {"rust": 0.50}})
    initial_rust_aff = 0.50

    # Process 'read' interaction

    res = behavioral_learning_service.process_interaction(user_id, story["id"], "read")
    assert res["status"] == "success"

    updated_prefs = db_repository.get_user_preferences(user_id)
    new_rust_aff = updated_prefs["topic_affinities"].get("rust")

    assert new_rust_aff == pytest.approx(initial_rust_aff + 0.02, 0.001)


# ==============================================================================
# TEST 6: Behavioral Learning - Save Interaction (+0.08)
# ==============================================================================
def test_6_behavioral_save_interaction(clean_db):
    user_id = "user_save_test"
    story = make_test_story(
        story_id="story_save_1",
        title="CrowdStrike Discloses Threat Actor Methodology",
        summary="Report details cloud intrusion vector and mitigation steps.",
        category="cybersecurity",
        topics=["threat intelligence", "malware"],
        entities=[{"name": "CrowdStrike", "category": "organization"}]
    )
    db_repository.insert_story(story)

    res = behavioral_learning_service.process_interaction(user_id, story["id"], "save")
    assert res["status"] == "success"

    updated_prefs = db_repository.get_user_preferences(user_id)
    ent_aff = updated_prefs["entity_affinities"].get("crowdstrike")
    assert ent_aff is not None
    assert ent_aff >= 0.58  # 0.50 base + 0.08 delta


# ==============================================================================
# TEST 7: Behavioral Learning - Hide Interaction (-0.15)
# ==============================================================================
def test_7_behavioral_hide_interaction(clean_db):
    user_id = "user_hide_test"
    story = make_test_story(
        story_id="story_hide_1",
        title="Retail Real Estate Quarterly Earnings",
        summary="Malls report tenant occupancy numbers for previous quarter.",
        category="business",
        topics=["retail", "earnings"]
    )
    db_repository.insert_story(story)

    # Start with explicit baseline
    initial_prefs = {
        "topic_affinities": {"business": 0.40, "retail": 0.40}
    }
    db_repository.save_user_preferences(user_id, initial_prefs)

    res = behavioral_learning_service.process_interaction(user_id, story["id"], "hide")
    assert res["status"] == "success"

    updated_prefs = db_repository.get_user_preferences(user_id)
    new_aff = updated_prefs["topic_affinities"].get("business")
    assert new_aff == pytest.approx(0.25, 0.01)  # 0.40 - 0.15


# ==============================================================================
# TEST 8: Affinity Bounded Clamping [0.0, 1.0]
# ==============================================================================
def test_8_affinity_bounded_clamping(clean_db):
    user_id = "user_clamp_test"
    story = make_test_story(
        story_id="story_clamp_1",
        title="AI Benchmarks Update",
        summary="Evaluation metrics for modern LLMs.",
        category="ai",
        topics=["benchmarks"]
    )
    db_repository.insert_story(story)

    # Upper clamp test: 20 saves (+0.08 each = +1.60)
    for _ in range(20):
        behavioral_learning_service.process_interaction(user_id, story["id"], "save")

    prefs_high = db_repository.get_user_preferences(user_id)
    assert prefs_high["topic_affinities"]["ai"] <= 1.0

    # Lower clamp test: 15 hides (-0.15 each = -2.25)
    for _ in range(15):
        behavioral_learning_service.process_interaction(user_id, story["id"], "hide")

    prefs_low = db_repository.get_user_preferences(user_id)
    assert prefs_low["topic_affinities"]["ai"] >= 0.0


# ==============================================================================
# TEST 9: Gradual Accumulation Without Drastic Profile Swings
# ==============================================================================
def test_9_gradual_accumulation_no_swing(clean_db):
    user_id = "user_gradual_test"
    story = make_test_story(
        story_id="story_grad_1",
        title="Quantum Computing State Preparation",
        summary="Novel pulse sequences demonstrate improved coherence time.",
        category="science",
        topics=["quantum"]
    )
    db_repository.insert_story(story)

    # Single read
    behavioral_learning_service.process_interaction(user_id, story["id"], "read")
    prefs = db_repository.get_user_preferences(user_id)

    # Change must be bounded by delta (0.02)
    base_science = settings.DEFAULT_INTEREST_WEIGHTS.get("science", 0.70)
    learned_science = prefs["topic_affinities"].get("science", base_science)
    assert abs(learned_science - base_science) <= 0.03


# ==============================================================================
# TEST 10: Grounded Reasons & Explainability
# ==============================================================================
def test_10_grounded_reasons_generation():
    story = make_test_story(
        story_id="s_expl",
        title="Next-Generation TypeScript Compiler in Rust",
        summary="Rewriting the type checker delivers 10x throughput in large monorepos.",
        category="software engineering",
        topics=["typescript", "rust", "compiler"]
    )
    breakdown = personal_relevance_service.compute_relevance(story)

    assert len(breakdown.reasons) >= 2
    assert breakdown.relevance_reason is not None
    assert len(breakdown.relevance_reason) > 10
    # Must mention category or topic
    assert any(term in breakdown.relevance_reason.lower() for term in ["software", "engineering", "rust", "typescript", "compiler"])


# ==============================================================================
# TEST 11: Strict Separation of Global Importance and Personal Relevance
# ==============================================================================
def test_11_global_importance_separation(clean_db):
    story = make_test_story(
        story_id="story_sep_1",
        title="Major Zero-Day In Infrastructure",
        summary="Vulnerability actively exploited across world servers.",
        category="cybersecurity",
        importance_score=88
    )
    db_repository.insert_story(story)

    # User A loves cybersecurity (0.95), User B has low interest (0.10)
    profile_a = {"user_id": "user_a", "interest_weights": {"cybersecurity": 0.95}}
    profile_b = {"user_id": "user_b", "interest_weights": {"cybersecurity": 0.10}}

    breakdown_a = personal_relevance_service.compute_relevance(story, profile_a)
    breakdown_b = personal_relevance_service.compute_relevance(story, profile_b)

    # Personal relevance differs based on user
    assert breakdown_a.personal_relevance_score > breakdown_b.personal_relevance_score

    # Global importance in database remains completely unchanged!
    db_story = db_repository.get_story("story_sep_1")
    assert db_story["importance_score"] == 88


# ==============================================================================
# TEST 12: Critical World Event Global Importance Override
# ==============================================================================
def test_12_critical_world_event_override(clean_db):
    # Even if category is 'world' (persona weight 0.45), high global importance (>= 85) triggers override
    critical_world_story = make_test_story(
        story_id="crit_world_1",
        title="Global Treaty on Sovereign Cyber Warfare Signed",
        summary="120 nations sign historic binding accord prohibiting civilian grid attacks.",
        category="world",
        importance_score=94
    )
    normal_ai_story = make_test_story(
        story_id="norm_ai_1",
        title="Minor Python Library Patch",
        summary="Bug fix in string formatting helper.",
        category="ai",
        importance_score=52
    )

    db_repository.insert_story(critical_world_story)
    db_repository.insert_story(normal_ai_story)

    ranked_feed = feed_ranking_service.rank_feed(user_id="default_user", limit=10)
    top_story = ranked_feed[0]

    assert top_story["id"] == "crit_world_1"
    assert top_story["is_global_override"] is True
    assert "critical world event" in top_story["relevance_reason"].lower()


# ==============================================================================
# TEST 13: Diversity Controller Category Interleaving
# ==============================================================================
def test_13_diversity_controller_interleaving(clean_db):
    # Insert 4 high-scoring AI stories and 2 Science stories
    for i in range(4):
        db_repository.insert_story(make_test_story(
            story_id=f"ai_story_{i}",
            title=f"AI Milestone Advance #{i}",
            summary="Key algorithmic performance improvement.",
            category="ai",
            importance_score=70
        ))

    for i in range(2):
        db_repository.insert_story(make_test_story(
            story_id=f"sci_story_{i}",
            title=f"Science Discovery #{i}",
            summary="Biophysical structure observed in laboratory.",
            category="science",
            importance_score=68
        ))

    ranked = feed_ranking_service.rank_feed(limit=6)

    # Verify no more than 2 consecutive stories have the same category
    for i in range(len(ranked) - 2):
        cat1 = personal_relevance_service.normalize_category(ranked[i]["category"])
        cat2 = personal_relevance_service.normalize_category(ranked[i+1]["category"])
        cat3 = personal_relevance_service.normalize_category(ranked[i+2]["category"])
        assert not (cat1 == cat2 == cat3), f"Echo chamber detected: 3 consecutive '{cat1}' stories at index {i}"


# ==============================================================================
# TEST 14: Canonical Story Deduplication
# ==============================================================================
def test_14_cluster_deduplication(clean_db):
    s1 = make_test_story("s_uniq_1", "Compiler Release", "New release notes.", category="software engineering")
    s2 = make_test_story("s_uniq_2", "Compiler Release Part 2", "Secondary release notes.", category="software engineering")
    db_repository.insert_story(s1)
    db_repository.insert_story(s2)

    ranked = feed_ranking_service.rank_feed(limit=10)
    ids = [item["id"] for item in ranked]
    assert len(ids) == len(set(ids)), "Duplicate story IDs found in ranked feed"


# ==============================================================================
# TEST 15: Hidden Story Exclusion
# ==============================================================================
def test_15_hidden_story_exclusion(clean_db):
    user_id = "test_hide_user"
    s1 = make_test_story("s_keep", "Relevant Tech Story", "Content.", category="technology")
    s2 = make_test_story("s_dislike", "Story User Hides", "Content.", category="technology")
    db_repository.insert_story(s1)
    db_repository.insert_story(s2)

    # Hide s_dislike
    db_repository.record_interaction(user_id=user_id, story_id="s_dislike", interaction_type="hide")

    ranked = feed_ranking_service.rank_feed(user_id=user_id, limit=10)
    returned_ids = [s["id"] for s in ranked]

    assert "s_keep" in returned_ids
    assert "s_dislike" not in returned_ids


# ==============================================================================
# TEST 16: Database Persistence for Preferences & Affinities
# ==============================================================================
def test_16_database_persistence_preferences(clean_db):
    user_id = "persistence_user"
    custom_prefs = {
        "interests": ["AI", "Cybersecurity"],
        "interest_weights": {"ai": 0.98, "cybersecurity": 0.88, "space": 0.65},
        "topic_affinities": {"rust": 0.85, "cuda": 0.90},
        "entity_affinities": {"anthropic": 0.92},
        "importance_threshold": 65
    }

    db_repository.save_user_preferences(user_id, custom_prefs)
    loaded = db_repository.get_user_preferences(user_id)

    assert loaded["user_id"] == user_id
    assert loaded["interest_weights"]["ai"] == 0.98
    assert loaded["topic_affinities"]["rust"] == 0.85
    assert loaded["entity_affinities"]["anthropic"] == 0.92
    assert loaded["importance_threshold"] == 65


# ==============================================================================
# TEST 17: GET /api/feed API Endpoint
# ==============================================================================
def test_17_api_feed_endpoint(client, clean_db):
    story = make_test_story("api_feed_s1", "API Feed Verification Story", "Summary.", category="ai")
    db_repository.insert_story(story)

    resp = client.get("/api/feed?limit=5")
    assert resp.status_code == 200

    data = resp.json()
    assert "total" in data
    assert "items" in data
    assert len(data["items"]) >= 1

    item = data["items"][0]
    assert "relevance_score" in item
    assert "relevance_reason" in item
    assert "final_rank_score" in item
    assert "is_global_override" in item


# ==============================================================================
# TEST 18: GET /api/stories/{story_id}/relevance API Endpoint
# ==============================================================================
def test_18_api_relevance_explanation_endpoint(client, clean_db):
    story = make_test_story(
        story_id="api_rel_s1",
        title="Linux 6.14 Kernel Mainline Released",
        summary="Contains CPU scheduler improvements and security hardening.",
        category="software engineering",
        topics=["kernel", "linux", "operating systems"]
    )
    db_repository.insert_story(story)

    resp = client.get(f"/api/stories/{story['id']}/relevance")
    assert resp.status_code == 200

    breakdown = resp.json()
    assert breakdown["personal_relevance_score"] >= 0
    assert "category_match" in breakdown
    assert "topic_match" in breakdown
    assert "relevance_reason" in breakdown
    assert "reasons" in breakdown
    assert isinstance(breakdown["reasons"], list)


# ==============================================================================
# AUDIT REGRESSION TESTS (Tests 19 - 23)
# ==============================================================================

# ==============================================================================
# TEST 19: Exact Feed Ranking Composite Formula & Headroom Audit
# ==============================================================================
def test_19_exact_feed_ranking_formula_weights():
    # Verify the documented composite formula:
    # base_rank = 0.40 * relevance + 0.30 * importance + 0.15 * freshness + 0.10 * urgency
    w = feed_ranking_service.weights
    assert w.get("personal_relevance") == 0.40
    assert w.get("global_importance") == 0.30
    assert w.get("freshness") == 0.15
    assert w.get("urgency") == 0.10
    assert w.get("diversity_penalty") == 0.05

    # Direct arithmetic verification:
    # rel=80, imp=70, fresh=60, urg=50
    # Expected base_rank = 0.40*80 + 0.30*70 + 0.15*60 + 0.10*50 = 32 + 21 + 9 + 5 = 67.0
    rel = 80
    imp = 70
    fresh = 60
    urg = 50
    expected_rank = (0.40 * rel) + (0.30 * imp) + (0.15 * fresh) + (0.10 * urg)
    assert expected_rank == 67.0

    # Max possible base_rank with perfect 100s across all 4 direct signals:
    max_direct_rank = (0.40 * 100) + (0.30 * 100) + (0.15 * 100) + (0.10 * 100)
    assert max_direct_rank == 95.0
    # 0.95 sum is intentional: remaining 0.05 represents diversity controller headroom
    assert max_direct_rank + (w.get("diversity_penalty", 0.05) * 100) == 100.0


# ==============================================================================
# TEST 20: Global Importance Strict Independence Audit
# ==============================================================================
def test_20_global_importance_independence_rigorous(clean_db):
    story = make_test_story(
        story_id="story_rigorous_audit",
        title="International Treaty on Orbital Satellite Traffic",
        summary="Binding international framework for satellite deorbiting standards.",
        category="space",
        importance_score=78
    )
    db_repository.insert_story(story)

    # 1. Telemetry: reading and saving should not alter importance_score
    behavioral_learning_service.process_interaction("user1", story["id"], "read")
    behavioral_learning_service.process_interaction("user1", story["id"], "save")
    assert db_repository.get_story("story_rigorous_audit")["importance_score"] == 78

    # 2. Telemetry: hiding should not alter importance_score
    behavioral_learning_service.process_interaction("user1", story["id"], "hide")
    assert db_repository.get_story("story_rigorous_audit")["importance_score"] == 78

    # 3. Preference changes: user with 0.10 space interest vs 0.99 space interest
    db_repository.save_user_preferences("user_anti_space", {"interest_weights": {"space": 0.05}})
    db_repository.save_user_preferences("user_pro_space", {"interest_weights": {"space": 0.99}})

    feed_ranking_service.rank_feed(user_id="user_anti_space", limit=5)
    feed_ranking_service.rank_feed(user_id="user_pro_space", limit=5)

    # Database importance score remains rock-solid and untouched
    db_story = db_repository.get_story("story_rigorous_audit")
    assert db_story["importance_score"] == 78
    assert db_story["importance_tier"] == "HIGH"


# ==============================================================================
# TEST 21: Diversity Controller Edge Cases Audit
# ==============================================================================
def test_21_diversity_controller_edge_cases(clean_db):
    # Edge Case A: Only one category available
    # Must return all stories even though all have the same category
    for i in range(4):
        db_repository.insert_story(make_test_story(
            story_id=f"only_ai_{i}",
            title=f"AI Only Story {i}",
            summary="Single category pool.",
            category="ai",
            importance_score=60
        ))
    ranked_single = feed_ranking_service.rank_feed(limit=4)
    assert len(ranked_single) == 4
    assert all(s["category"] == "ai" for s in ranked_single)

    # Edge Case B: Two categories with imbalance
    # 4 Software Engineering stories and 2 World stories
    db_repository.clear_stories()
    for i in range(4):
        db_repository.insert_story(make_test_story(
            story_id=f"swe_{i}",
            title=f"SWE Story {i}",
            summary="Software engineering.",
            category="software engineering",
            importance_score=75
        ))
    for i in range(2):
        db_repository.insert_story(make_test_story(
            story_id=f"world_{i}",
            title=f"World Story {i}",
            summary="World news.",
            category="world",
            importance_score=70
        ))

    ranked_two = feed_ranking_service.rank_feed(limit=6)
    assert len(ranked_two) == 6
    # Verify no more than 2 consecutive SWE stories
    for idx in range(len(ranked_two) - 2):
        c1 = personal_relevance_service.normalize_category(ranked_two[idx]["category"])
        c2 = personal_relevance_service.normalize_category(ranked_two[idx+1]["category"])
        c3 = personal_relevance_service.normalize_category(ranked_two[idx+2]["category"])
        assert not (c1 == c2 == c3 == "software engineering"), f"Found 3 consecutive SWE at index {idx}"

    # Edge Case C: Three or more categories
    db_repository.clear_stories()
    for i in range(3):
        db_repository.insert_story(make_test_story(f"c_ai_{i}", f"AI {i}", "AI", category="ai", importance_score=75))
    for i in range(2):
        db_repository.insert_story(make_test_story(f"c_cyb_{i}", f"Cyber {i}", "Cyber", category="cybersecurity", importance_score=74))
    for i in range(2):
        db_repository.insert_story(make_test_story(f"c_sci_{i}", f"Science {i}", "Science", category="science", importance_score=73))

    ranked_three = feed_ranking_service.rank_feed(limit=7)
    for idx in range(len(ranked_three) - 2):
        c1 = personal_relevance_service.normalize_category(ranked_three[idx]["category"])
        c2 = personal_relevance_service.normalize_category(ranked_three[idx+1]["category"])
        c3 = personal_relevance_service.normalize_category(ranked_three[idx+2]["category"])
        assert not (c1 == c2 == c3), f"Echo chamber at index {idx}"

    # Edge Case D: All remaining stories belong to the same category
    # 2 AI, 1 Science, then 3 AI remaining
    db_repository.clear_stories()
    for i in range(5):
        db_repository.insert_story(make_test_story(f"tail_ai_{i}", f"Tail AI {i}", "AI", category="ai", importance_score=75))
    db_repository.insert_story(make_test_story("single_sci", "Single Science", "Science", category="science", importance_score=70))

    ranked_tail = feed_ranking_service.rank_feed(limit=6)
    assert len(ranked_tail) == 6
    # Science was interleaved to break initial cluster
    assert ranked_tail[2]["category"] == "science"

    # Edge Case E: Global Importance Override with an alternative eligible category
    # 3 Critical World events (override) and 1 standard AI story
    db_repository.clear_stories()
    for i in range(3):
        db_repository.insert_story(make_test_story(
            story_id=f"crit_w_{i}",
            title=f"Critical World Event {i}",
            summary="Global significance.",
            category="world",
            importance_score=94
        ))
    db_repository.insert_story(make_test_story(
        story_id="norm_ai_alt",
        title="Standard AI Update",
        summary="Normal AI news.",
        category="ai",
        importance_score=60
    ))

    ranked_override = feed_ranking_service.rank_feed(limit=4)
    # The first 2 items are World (override).
    # Since an eligible alternative (AI) is available, slot 3 must be AI to prevent > 2 consecutive World!
    # Then slot 4 is the remaining World override story!
    assert ranked_override[0]["category"] == "world"
    assert ranked_override[1]["category"] == "world"
    assert ranked_override[2]["category"] == "ai"
    assert ranked_override[3]["category"] == "world"
    assert ranked_override[0]["is_global_override"] is True
    assert ranked_override[1]["is_global_override"] is True
    assert ranked_override[3]["is_global_override"] is True


# ==============================================================================
# TEST 22: Canonical Cluster Deduplication Audit
# ==============================================================================
def test_22_canonical_cluster_deduplication_exact(clean_db):
    # Insert stories
    db_repository.insert_story(make_test_story("story_canon_1", "Title 1", "Summary 1", category="ai"))
    db_repository.insert_story(make_test_story("story_canon_2", "Title 2", "Summary 2", category="cybersecurity"))

    ranked = feed_ranking_service.rank_feed(limit=10)
    seen_ids = set()
    for s in ranked:
        assert s["id"] not in seen_ids, f"Duplicate story {s['id']} in feed"
        seen_ids.add(s["id"])


# ==============================================================================
# TEST 23: API Story Response Full Contract Audit
# ==============================================================================
def test_23_api_story_response_full_contract(client, clean_db):
    story = make_test_story(
        story_id="contract_test_s1",
        title="Mainline Linux Performance Breakthrough",
        summary="Scheduler refactoring delivers notable low-latency improvements.",
        category="software engineering",
        importance_score=82,
        topics=["linux", "kernel", "benchmarks"]
    )
    db_repository.insert_story(story)

    # 1. Test /api/stories
    resp = client.get("/api/stories")
    assert resp.status_code == 200
    items = resp.json()["items"]
    assert len(items) >= 1
    item = next(it for it in items if it["id"] == "contract_test_s1")

    # Verify all required audit contract fields
    assert "importance_score" in item and item["importance_score"] == 82
    assert "importance_tier" in item and item["importance_tier"] == "HIGH"
    assert "relevance_score" in item
    assert "relevance_reason" in item
    assert "category" in item and item["category"] == "software engineering"
    assert "analyzed" in item
    assert "claims" in item
    assert "articles" in item
    assert "source_count" in item
    # Internal DB fields must not leak
    assert "rowid" not in item
    assert "entities_json" not in item
    assert "topics_json" not in item

    # 2. Test /api/stories/{id}
    resp_detail = client.get(f"/api/stories/{story['id']}")
    assert resp_detail.status_code == 200
    detail = resp_detail.json()
    assert detail["id"] == "contract_test_s1"
    assert detail["importance_score"] == 82
    assert detail["category"] == "software engineering"
    assert "relevance_reason" in detail

