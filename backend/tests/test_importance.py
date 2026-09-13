"""
Test suite for Global Importance Engine (Phase 5).
Validates deterministic scoring, signal extraction, weighting, urgency/importance separation,
source-count restraint, database persistence, API responses, and versioning.
"""
import pytest
from datetime import datetime
from fastapi.testclient import TestClient

from backend.app.main import app
from backend.app.core.config import settings
from backend.app.core.db_repository import db_repository
from backend.app.services.importance_service import importance_service
from backend.app.schemas.story import ImportanceSignals, ImportanceBreakdown


@pytest.fixture
def client():
    return TestClient(app)


@pytest.fixture
def clean_db(tmp_path):
    test_db = tmp_path / "test_importance.db"
    orig_path = db_repository.db_path
    db_repository.db_path = str(test_db)
    db_repository.init_db()
    yield
    db_repository.db_path = orig_path


# ==============================================================================
# Archetype Story Fixtures (Part 20)
# ==============================================================================

def make_story(
    story_id: str,
    title: str,
    summary: str,
    category: str = "technology",
    source_count: int = 1,
    article_count: int = 1,
    claims: list = None
):
    return {
        "id": story_id,
        "title": title,
        "summary": summary,
        "why_it_matters": f"Grounded briefing for {title}.",
        "category": category,
        "primary_topic": category.capitalize(),
        "source_count": source_count,
        "article_count": article_count,
        "claims": claims or [],
        "entities": [{"name": "Key Entity", "type": "organization"}],
        "topics": [category.capitalize()],
        "created_at": datetime.utcnow().isoformat()
    }


# ==============================================================================
# PART 21 — REQUIRED TESTS
# ==============================================================================

def test_1_score_normalization():
    """
    Test 1: Calculated importance score is strictly bounded between 0 and 100.
    """
    # Max possible signals
    max_signals = ImportanceSignals(
        source_count=10,
        article_count=20,
        category="cybersecurity",
        geographic_scope="global",
        severity=1.0,
        security_impact=1.0,
        technological_impact=1.0,
        economic_impact=1.0,
        urgency=1.0,
        novelty=1.0,
        escalation=1.0
    )
    max_breakdown = importance_service.calculate_importance(max_signals)
    assert 0 <= max_breakdown.importance_score <= 100
    assert max_breakdown.importance_score >= 90
    assert max_breakdown.importance_tier == "CRITICAL"

    # Min possible signals
    min_signals = ImportanceSignals(
        source_count=1,
        article_count=1,
        category="general",
        geographic_scope="local",
        severity=0.0,
        urgency=0.0,
        novelty=0.0,
        escalation=0.0
    )
    min_breakdown = importance_service.calculate_importance(min_signals)
    assert 0 <= min_breakdown.importance_score <= 100
    assert min_breakdown.importance_score <= 30
    assert min_breakdown.importance_tier == "LOW"


def test_2_severity_weighting():
    """
    Test 2: Higher severity produces higher score when other signals are constant.
    """
    low_sev_signals = ImportanceSignals(
        category="technology",
        geographic_scope="national",
        severity=0.20,
        technological_impact=0.50,
        urgency=0.50,
        novelty=0.50,
        escalation=0.10
    )
    high_sev_signals = ImportanceSignals(
        category="technology",
        geographic_scope="national",
        severity=0.90,
        technological_impact=0.50,
        urgency=0.50,
        novelty=0.50,
        escalation=0.10
    )
    low_res = importance_service.calculate_importance(low_sev_signals)
    high_res = importance_service.calculate_importance(high_sev_signals)

    assert high_res.importance_score > low_res.importance_score
    # Delta should reflect ~ severity weight (0.25 * 0.70 * 100 ≈ 17.5 points)
    assert high_res.importance_score - low_res.importance_score >= 15


def test_3_reach_weighting():
    """
    Test 3: Global reach produces higher score than local reach when other signals are constant.
    """
    local_signals = ImportanceSignals(
        category="technology",
        geographic_scope="local",
        severity=0.60,
        technological_impact=0.60,
        urgency=0.50,
        novelty=0.50,
        escalation=0.10
    )
    global_signals = ImportanceSignals(
        category="technology",
        geographic_scope="global",
        severity=0.60,
        technological_impact=0.60,
        urgency=0.50,
        novelty=0.50,
        escalation=0.10
    )
    local_res = importance_service.calculate_importance(local_signals)
    global_res = importance_service.calculate_importance(global_signals)

    assert global_res.importance_score > local_res.importance_score
    # Delta should reflect reach weight (0.20 * (1.0 - 0.2) * 100 = 16 points)
    assert global_res.importance_score - local_res.importance_score >= 14


def test_4_impact_weighting():
    """
    Test 4: Higher impact dimension scores produce higher overall impact and importance.
    """
    mod_impact_signals = ImportanceSignals(
        category="technology",
        geographic_scope="international",
        severity=0.70,
        technological_impact=0.40,
        urgency=0.50,
        novelty=0.50,
        escalation=0.10
    )
    high_multi_impact_signals = ImportanceSignals(
        category="technology",
        geographic_scope="international",
        severity=0.70,
        technological_impact=0.90,
        economic_impact=0.70,
        urgency=0.50,
        novelty=0.50,
        escalation=0.10
    )
    mod_res = importance_service.calculate_importance(mod_impact_signals)
    high_res = importance_service.calculate_importance(high_multi_impact_signals)

    assert high_res.impact > mod_res.impact
    assert high_res.importance_score > mod_res.importance_score


def test_5_urgency_separation():
    """
    Test 5: Urgency and global importance are decoupled.
    Historic scientific discovery (high importance, low urgency) outranks
    local service outage (high urgency, low global importance).
    """
    # Archetype 4: Scientific discovery (historic exoplanet or physics finding)
    scientific_story = make_story(
        story_id="arch_science",
        title="Astronomers announce major scientific discovery of habitable exoplanet atmosphere",
        summary="Using the James Webb Space Telescope, researchers discovered chemical signatures of water vapor in an exoplanet atmosphere.",
        category="science",
        source_count=2,
        article_count=2
    )

    # Archetype 7: Local service outage (water main break disrupting morning commute)
    local_outage_story = make_story(
        story_id="arch_outage",
        title="Urgent breaking water main break causes local traffic delay and service outage downtown",
        summary="An emergency water main break downtown has prompted road closures and immediate municipal traffic detour.",
        category="general",
        source_count=1,
        article_count=1
    )

    sci_signals = importance_service.extract_signals(scientific_story)
    outage_signals = importance_service.extract_signals(local_outage_story)

    # Verify signal extraction decouples them
    assert sci_signals.urgency < 0.35  # Low urgency
    assert outage_signals.urgency >= 0.80  # High urgency

    sci_res = importance_service.calculate_importance(sci_signals)
    outage_res = importance_service.calculate_importance(outage_signals)

    # Globally, the landmark scientific discovery must outrank the local water outage!
    assert sci_res.importance_score > outage_res.importance_score
    assert sci_res.importance_tier in ("HIGH", "CRITICAL")
    assert outage_res.importance_tier in ("LOW", "MEDIUM")


def test_6_novelty_weighting():
    """
    Test 6: Brand new event scores higher than repeated reporting / minor update.
    """
    new_signals = ImportanceSignals(
        category="technology",
        geographic_scope="national",
        severity=0.60,
        technological_impact=0.60,
        urgency=0.50,
        novelty=1.00,  # "first ever / breakthrough"
        escalation=0.10
    )
    update_signals = ImportanceSignals(
        category="technology",
        geographic_scope="national",
        severity=0.60,
        technological_impact=0.60,
        urgency=0.50,
        novelty=0.30,  # "minor update / routine follow-up"
        escalation=0.10
    )
    new_res = importance_service.calculate_importance(new_signals)
    update_res = importance_service.calculate_importance(update_signals)

    assert new_res.importance_score > update_res.importance_score
    assert new_res.novelty > update_res.novelty


def test_7_escalation_weighting():
    """
    Test 7: An event with verified escalation scores higher than a static equivalent.
    """
    baseline_signals = ImportanceSignals(
        category="cybersecurity",
        geographic_scope="international",
        severity=0.80,
        security_impact=0.85,
        urgency=0.60,
        novelty=0.70,
        escalation=0.10
    )
    escalated_signals = ImportanceSignals(
        category="cybersecurity",
        geographic_scope="international",
        severity=0.80,
        security_impact=0.85,
        urgency=0.60,
        novelty=0.70,
        escalation=0.85  # "Cyberattack spreads to 500 additional hospital networks"
    )
    base_res = importance_service.calculate_importance(baseline_signals)
    esc_res = importance_service.calculate_importance(escalated_signals)

    assert esc_res.importance_score > base_res.importance_score
    assert esc_res.escalation > base_res.escalation


def test_8_source_count_restraint():
    """
    Test 8: Source count does NOT dominate importance.
    A viral celebrity gossip story reported by 10 sources must score LOW (< 45),
    while a critical zero-day exploit reported by only 1 source must score HIGH or CRITICAL (>= 70).
    """
    celebrity_story = make_story(
        story_id="arch_celeb",
        title="Celebrity actor couple spotted on red carpet at glamorous Hollywood film premiere",
        summary="Paparazzi and gossip magazines report on red carpet dating appearances during the festival weekend.",
        category="entertainment",
        source_count=10,
        article_count=15
    )

    zero_day_story = make_story(
        story_id="arch_zeroday",
        title="Critical zero-day vulnerability in global infrastructure software actively exploited",
        summary="CISA issues emergency directive warning of a remote code execution CVE actively exploited by threat actors worldwide.",
        category="cybersecurity",
        source_count=1,
        article_count=1
    )

    celeb_signals = importance_service.extract_signals(celebrity_story)
    zeroday_signals = importance_service.extract_signals(zero_day_story)

    celeb_res = importance_service.calculate_importance(celeb_signals)
    zeroday_res = importance_service.calculate_importance(zeroday_signals)

    # Celebrity gossip with 10 sources must remain LOW
    assert celeb_res.importance_score < 45
    assert celeb_res.importance_tier == "LOW"

    # Critical zero-day with 1 source must be at least HIGH
    assert zeroday_res.importance_score >= 70
    assert zeroday_res.importance_tier in ("HIGH", "CRITICAL")
    assert zeroday_res.importance_score > celeb_res.importance_score


def test_9_importance_level_thresholds():
    """
    Test 9: Verifies tier classifications:
    85-100: CRITICAL
    70-84: HIGH
    45-69: MEDIUM
    0-44: LOW
    """
    def eval_score(target_severity: float) -> ImportanceBreakdown:
        s = ImportanceSignals(
            category="technology",
            geographic_scope="global",
            severity=target_severity,
            technological_impact=target_severity,
            urgency=target_severity,
            novelty=target_severity,
            escalation=target_severity
        )
        return importance_service.calculate_importance(s)

    crit = eval_score(0.95)
    assert crit.importance_score >= 85
    assert crit.importance_tier == "CRITICAL"

    high = eval_score(0.75)
    assert 70 <= high.importance_score <= 84
    assert high.importance_tier == "HIGH"

    med = eval_score(0.50)
    assert 45 <= med.importance_score <= 69
    assert med.importance_tier == "MEDIUM"

    low = eval_score(0.20)
    assert low.importance_score < 45
    assert low.importance_tier == "LOW"


def test_10_explanation_generation():
    """
    Test 10: Grounded explanation generation:
    Must mention tier, score, and grounded dimensions without generic filler.
    """
    cyber_signals = ImportanceSignals(
        category="cybersecurity",
        geographic_scope="global",
        severity=0.92,
        security_impact=0.95,
        urgency=0.85,
        novelty=0.80,
        escalation=0.20
    )
    res = importance_service.calculate_importance(cyber_signals)
    assert res.explanation is not None
    assert len(res.explanation) > 20
    assert "cybersecurity" in res.explanation.lower() or "critical" in res.explanation.lower()
    assert "many sources" not in res.explanation.lower()


def test_11_missing_signal_handling():
    """
    Test 11: Missing or sparse signals fallback cleanly without crashing.
    """
    minimal_story = {
        "id": "minimal_001",
        "title": "Something happened",
        "summary": "Brief note.",
        "category": "technology"
    }
    signals = importance_service.extract_signals(minimal_story)
    assert signals.source_count == 1
    assert signals.geographic_scope in ("local", "regional", "national", "international", "global")
    breakdown = importance_service.calculate_importance(signals)
    assert 0 <= breakdown.importance_score <= 100
    assert breakdown.importance_tier in ("CRITICAL", "HIGH", "MEDIUM", "LOW")


def test_12_database_persistence(clean_db):
    """
    Test 12: Verifies persistence of all breakdown fields in database repository.
    """
    # Insert an article and story
    art = {
        "id": "art_persist_1",
        "title": "Major cyberattack targets hospitals",
        "description": "Critical infrastructure breach reported.",
        "url": "https://cyberwire.example.com/hospital-breach",
        "canonical_url": "https://cyberwire.example.com/hospital-breach",
        "source_id": "cyberwire",
        "source_name": "CyberWire",
        "source_domain": "cyberwire.example.com",
        "category": "cybersecurity",
        "published_at": "2026-09-13T10:00:00Z"
    }
    db_repository.insert_article(art)

    story_id = "story_persist_1"
    with db_repository._get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("""
        INSERT INTO stories (id, title, summary, category, importance_score, source_count, article_count)
        VALUES (?, ?, ?, ?, 50, 1, 1)
        """, (story_id, art["title"], art["description"], "cybersecurity"))
        conn.commit()

    # Calculate importance
    breakdown = importance_service.calculate_story_importance(story_id)
    assert breakdown is not None
    assert breakdown.importance_score >= 70

    # Retrieve from DB
    retrieved = db_repository.get_story_by_id(story_id)
    assert retrieved is not None
    assert retrieved["importance_score"] == breakdown.importance_score
    assert retrieved["importance_tier"] == breakdown.importance_tier
    assert retrieved["importance_explanation"] == breakdown.explanation
    assert retrieved["importance_version"] == "v1"

    db_breakdown = retrieved.get("importance_breakdown")
    assert db_breakdown is not None
    assert db_breakdown["importance_score"] == breakdown.importance_score
    assert db_breakdown["severity"] == breakdown.severity
    assert db_breakdown["reach"] == breakdown.reach
    assert db_breakdown["impact"] == breakdown.impact


def test_13_api_endpoints(clean_db, client):
    """
    Test 13: Verifies POST and GET API endpoints for importance.
    """
    art = {
        "id": "art_api_1",
        "title": "Major economic announcement regarding interest rates and banking stability",
        "description": "The Federal Reserve announced key policy decisions affecting national banking stability.",
        "url": "https://financialwire.example.com/fed-decision",
        "canonical_url": "https://financialwire.example.com/fed-decision",
        "source_id": "finwire",
        "source_name": "Financial Wire",
        "source_domain": "financialwire.example.com",
        "category": "business",
        "published_at": "2026-09-13T11:00:00Z"
    }
    db_repository.insert_article(art)

    story_id = "story_api_1"
    with db_repository._get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("""
        INSERT INTO stories (id, title, summary, category, importance_score, source_count, article_count)
        VALUES (?, ?, ?, ?, 50, 1, 1)
        """, (story_id, art["title"], art["description"], "business"))
        conn.commit()

    # 1. POST /api/stories/{id}/importance
    post_res = client.post(f"/api/stories/{story_id}/importance")
    assert post_res.status_code == 200
    data = post_res.json()
    assert "importance_score" in data
    assert "importance_tier" in data
    assert "importance_explanation" in data
    assert data["importance_version"] == "v1"
    assert data["importance_breakdown"] is not None

    # 2. GET /api/stories/{id}
    get_res = client.get(f"/api/stories/{story_id}")
    assert get_res.status_code == 200
    get_data = get_res.json()
    assert get_data["importance_score"] == data["importance_score"]
    assert get_data["importance_tier"] == data["importance_tier"]
    assert get_data["importance_breakdown"]["severity"] == data["importance_breakdown"]["severity"]

    # 3. POST /api/stories/importance (batch)
    batch_res = client.post("/api/stories/importance?limit=5")
    assert batch_res.status_code == 200
    batch_data = batch_res.json()
    assert batch_data["processed_count"] >= 1
    assert batch_data["version"] == "v1"


def test_14_versioning():
    """
    Test 14: Confirms importance_version == 'v1' and is decoupled from analysis_version.
    """
    assert settings.IMPORTANCE_VERSION == "v1"
    assert settings.ANALYSIS_VERSION == "v1.2"
    assert settings.IMPORTANCE_VERSION != settings.ANALYSIS_VERSION

    dummy = ImportanceSignals(category="technology")
    res = importance_service.calculate_importance(dummy)
    assert res.importance_version == "v1"


# ==============================================================================
# Archetype Relative Ranking Validation (Part 20)
# ==============================================================================

def test_archetypes_relative_ranking():
    """
    Verifies relative ranking across the 8 required archetypes:
    1. Major geopolitical escalation
    2. Major cyberattack
    3. Major AI model release
    4. Scientific discovery
    5. Minor software update
    6. Celebrity story
    7. Local outage
    8. Major economic announcement
    """
    archetypes = {
        "geopolitical": make_story(
            "arch_geo",
            "Major war escalation and missile strikes expand conflict to neighboring territory",
            "Military forces launched wide missile strikes as border conflicts escalate into full regional crisis.",
            category="world",
            source_count=3
        ),
        "cyberattack": make_story(
            "arch_cyber",
            "Massive cyberattack and critical zero-day exploit breaches nationwide infrastructure",
            "Threat actors launched a coordinated ransomware campaign targeting critical energy and hospital systems.",
            category="cybersecurity",
            source_count=2
        ),
        "ai_release": make_story(
            "arch_ai",
            "Frontier lab unveils next-generation AI model with breakthrough reasoning benchmarks",
            "Researchers announced a new foundation model demonstrating state-of-the-art capabilities across technical domains.",
            category="ai",
            source_count=2
        ),
        "science": make_story(
            "arch_sci",
            "Landmark scientific discovery of exoplanet atmosphere by James Webb telescope",
            "NASA astronomers have discovered complex chemical markers in a distant solar system.",
            category="science",
            source_count=2
        ),
        "economic": make_story(
            "arch_econ",
            "Federal Reserve announces major interest rate decision amidst inflation concerns",
            "Central bank officials unveiled monetary policy shifts affecting global financial markets.",
            category="business",
            source_count=2
        ),
        "local_outage": make_story(
            "arch_local",
            "Urgent local water main break causes morning traffic delay downtown",
            "City municipal crew responds to road closure following broken pipe.",
            category="general",
            source_count=1
        ),
        "software_update": make_story(
            "arch_update",
            "Minor software update release notes with bug fixes and UI tweak for desktop app",
            "The developer team published version 2.1.4 patch notes resolving minor layout issues.",
            category="technology",
            source_count=1
        ),
        "celebrity": make_story(
            "arch_celeb",
            "Celebrity actor couple spotted on vacation red carpet festival",
            "Entertainment gossip accounts and magazine photographers share red carpet photos.",
            category="entertainment",
            source_count=8
        )
    }

    scores = {}
    for name, story in archetypes.items():
        signals = importance_service.extract_signals(story)
        breakdown = importance_service.calculate_importance(signals)
        scores[name] = (breakdown.importance_score, breakdown.importance_tier)

    print("\nArchetype Scores:", scores)

    # 1. Geopolitical and Cyberattack should be High or Critical (>= 72)
    assert scores["geopolitical"][0] >= 80
    assert scores["cyberattack"][0] >= 72

    # 2. AI Release and Economic should be High (>= 68)
    assert scores["ai_release"][0] >= 68
    assert scores["economic"][0] >= 68

    # 3. Scientific discovery should be High (>= 68) despite low urgency
    assert scores["science"][0] >= 68

    # 4. Local outage has high urgency but low global importance (<= 45)
    assert scores["local_outage"][0] <= 45

    # 5. Minor software update and Celebrity gossip must be Low (< 45)
    assert scores["software_update"][0] < 45
    assert scores["celebrity"][0] < 45

    # 6. Strict hierarchy checks
    assert scores["geopolitical"][0] > scores["local_outage"][0]
    assert scores["cyberattack"][0] > scores["software_update"][0]
    assert scores["science"][0] > scores["celebrity"][0]
    assert scores["ai_release"][0] > scores["local_outage"][0]
