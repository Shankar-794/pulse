"""
Test suite for Story Evolution, Breaking News Engine & Event Lifecycle (Phase 7).

Validates:
1. Incremental story update detection (NEW_STORY, SAME_REPORTING, MEANINGFUL_UPDATE, ESCALATION, CONTRADICTION, CORRECTION).
2. Deterministic lifecycle states (NEW, DEVELOPING, ACTIVE, ESCALATING, STABLE, RESOLVED).
3. Breaking News score normalization (0-100) and level assignment (BREAKING, DEVELOPING, UPDATED, STABLE).
4. Guardrail: routine software release 5 minutes ago does NOT become BREAKING.
5. High-urgency/severity incident CAN become BREAKING even with limited initial reporting.
6. Strict Independence: Breaking News engine cannot alter global importance_score or personal relevance.
7. Grounded timeline events referencing real article citations.
8. Conflicting perspectives detection across sources without artificial consensus.
9. Latest development grounded extraction.
10. Database persistence in story_events table.
11. API contract extensions for GET /api/stories and GET /api/stories/{id}.
12. POST /api/stories/{id}/evolve and GET /api/stories/{id}/timeline endpoints.
"""
import pytest
from datetime import datetime, timezone, timedelta
from fastapi.testclient import TestClient

from backend.app.main import app
from backend.app.core.config import settings
from backend.app.core.db_repository import db_repository
from backend.app.services.story_evolution_service import story_evolution_service


@pytest.fixture
def client():
    return TestClient(app)


@pytest.fixture
def clean_db(tmp_path):
    test_db = tmp_path / "test_story_evolution.db"
    orig_path = db_repository.db_path
    db_repository.db_path = str(test_db)
    db_repository.init_db()
    yield
    db_repository.db_path = orig_path


def make_art(
    art_id: str,
    title: str,
    description: str,
    source_name: str = "Tech Wire",
    category: str = "cybersecurity",
    published_at: str = None
) -> dict:
    now_iso = datetime.now(timezone.utc).isoformat()
    return {
        "id": art_id,
        "title": title,
        "description": description,
        "url": f"https://example.com/{art_id}",
        "canonical_url": f"https://example.com/{art_id}",
        "source_id": "tech_wire_src",
        "source_name": source_name,
        "source_domain": "example.com",
        "category": category,
        "primary_topic": category.capitalize(),
        "published_at": published_at or now_iso,
        "created_at": published_at or now_iso
    }


def make_story(
    story_id: str,
    title: str,
    summary: str,
    category: str = "cybersecurity",
    importance_score: int = 70,
    severity_score: float = 0.70,
    urgency_score: float = 0.60,
    escalation_score: float = 0.10,
    published_at: str = None,
    articles: list = None
) -> dict:
    now_iso = datetime.now(timezone.utc).isoformat()
    arts = articles or []
    return {
        "id": story_id,
        "title": title,
        "summary": summary,
        "why_it_matters": f"Significance of {title}.",
        "category": category,
        "primary_topic": category.capitalize(),
        "importance_score": importance_score,
        "importance_tier": "CRITICAL" if importance_score >= 85 else "HIGH" if importance_score >= 70 else "MEDIUM",
        "severity_score": severity_score,
        "urgency_score": urgency_score,
        "escalation_score": escalation_score,
        "novelty_score": 0.80,
        "reach_score": 0.80,
        "impact_score": 0.75,
        "reporting_breadth_score": 0.60,
        "source_count": len(set(a.get("source_name") for a in arts)) if arts else 1,
        "article_count": len(arts) if arts else 1,
        "first_published_at": published_at or now_iso,
        "last_published_at": published_at or now_iso,
        "created_at": published_at or now_iso,
        "updated_at": published_at or now_iso,
        "topics": [category.capitalize()],
        "tags": [category.capitalize()],
        "entities": [{"name": "Global Corp", "category": "organization"}],
        "claims": [],
        "articles": arts
    }


# ==============================================================================
# TEST 1: Update Detection & Classification Classes
# ==============================================================================
def test_1_update_detection_classes():
    base_story = make_story(
        story_id="s_evo_1",
        title="Zero-Day Vulnerability Discovered in Cloud Database",
        summary="Security researchers identified an unauthenticated memory corruption flaw in CloudDB.",
        category="cybersecurity"
    )

    # 1. NEW_STORY (completely unrelated topic)
    unrelated_art = make_art(
        "art_unrel",
        "James Webb Space Telescope Observes Distant Exoplanet Atmosphere",
        "Spectroscopic analysis reveals methane signatures in habitable zone.",
        category="space"
    )
    c1 = story_evolution_service.classify_article_update(unrelated_art, base_story)
    assert c1["classification"] == "NEW_STORY"
    assert c1["is_meaningful"] is False

    # 2. SAME_REPORTING (reiterating existing facts without new entities)
    duplicate_art = make_art(
        "art_dup",
        "Cloud Database Zero-Day Vulnerability Reported by Researchers",
        "Security researchers identified an unauthenticated memory corruption flaw in CloudDB.",
        category="cybersecurity"
    )
    c2 = story_evolution_service.classify_article_update(duplicate_art, base_story)
    assert c2["classification"] == "SAME_REPORTING"
    assert c2["is_meaningful"] is False

    # 3. MEANINGFUL_UPDATE (confirms incident and identifies new affected systems)
    update_art = make_art(
        "art_upd",
        "CloudDB Confirms Zero-Day Vulnerability and Identifies Affected v4 Systems",
        "Vendor confirms the flaw affects all enterprise v4 clusters and promises patch.",
        category="cybersecurity"
    )
    c3 = story_evolution_service.classify_article_update(update_art, base_story)
    assert c3["classification"] == "MEANINGFUL_UPDATE"
    assert c3["is_meaningful"] is True

    # 4. ESCALATION (active exploitation in the wild and emergency declared)
    escalate_art = make_art(
        "art_esc",
        "Emergency Declared as Cloud Database Exploit Spread in the Wild",
        "Critical severity incident spreads as active zero-day exploit is traded on dark web.",
        category="cybersecurity"
    )
    c4 = story_evolution_service.classify_article_update(escalate_art, base_story)
    assert c4["classification"] == "ESCALATION"
    assert c4["is_meaningful"] is True

    # 5. CONTRADICTION (company denies the allegations / disputed reporting)
    contradict_art = make_art(
        "art_contra",
        "CloudDB Denies Zero-Day Vulnerability Allegations in Security Advisory",
        "CloudDB spokesperson refutes and disputes researcher findings as unverified.",
        category="cybersecurity"
    )
    c5 = story_evolution_service.classify_article_update(contradict_art, base_story)
    assert c5["classification"] == "CONTRADICTION"
    assert c5["is_meaningful"] is True

    # 6. CORRECTION (retraction or formal correction)
    correct_art = make_art(
        "art_corr",
        "Correction: CloudDB Statement Retracts Earlier Vulnerability Advisory",
        "Official correction clarifies that earlier memory corruption report was in third-party plugin.",
        category="cybersecurity"
    )
    c6 = story_evolution_service.classify_article_update(correct_art, base_story)
    assert c6["classification"] == "CORRECTION"
    assert c6["is_meaningful"] is True


# ==============================================================================
# TEST 2: Deterministic Story Lifecycle States
# ==============================================================================
def test_2_lifecycle_states():
    now = datetime.now(timezone.utc)
    recent_iso = (now - timedelta(hours=1)).isoformat()
    yesterday_iso = (now - timedelta(hours=28)).isoformat()
    old_iso = (now - timedelta(hours=80)).isoformat()

    # 1. NEW story (created 1 hour ago, singleton)
    new_art = make_art("art_new", "Headline 1", "Summary 1", published_at=recent_iso)
    story_new = make_story("s_new", "Headline 1", "Summary 1", published_at=recent_iso, articles=[new_art])
    assert story_evolution_service.determine_lifecycle_state(story_new, [new_art], []) == "NEW"

    # 2. DEVELOPING story (multiple articles within recent hours)
    dev_art1 = make_art("art_d1", "Crash Reported", "Desc", published_at=recent_iso)
    dev_art2 = make_art("art_d2", "Investigators on Scene", "Desc", published_at=recent_iso)
    story_dev = make_story(
        "s_dev", "Major Incident Developing", "Desc",
        urgency_score=0.85, published_at=recent_iso, articles=[dev_art1, dev_art2]
    )
    assert story_evolution_service.determine_lifecycle_state(story_dev, [dev_art1, dev_art2], []) == "DEVELOPING"

    # 3. ESCALATING story (active with escalation keywords or high escalation score)
    esc_art1 = make_art("art_e1", "Outage Starts", "Desc", published_at=recent_iso)
    esc_art2 = make_art("art_e2", "Nationwide Outage Expands and Emergency Declared", "Desc", published_at=recent_iso)
    story_esc = make_story(
        "s_esc", "Nationwide Outage Expands and Emergency Declared", "Critical infrastructure impacted.",
        escalation_score=0.85, published_at=recent_iso, articles=[esc_art1, esc_art2]
    )
    assert story_evolution_service.determine_lifecycle_state(story_esc, [esc_art1, esc_art2], []) == "ESCALATING"

    # 4. ACTIVE story (moderate velocity, steady coverage within last 24h)
    act_art1 = make_art("art_a1", "Spacecraft Enters Orbit", "Desc", published_at=yesterday_iso)
    act_art2 = make_art("art_a2", "Telemetry Streaming Normally", "Desc", published_at=(now - timedelta(hours=18)).isoformat())
    story_act = make_story("s_act", "Spacecraft In Orbit", "Desc", urgency_score=0.40, published_at=yesterday_iso, articles=[act_art1, act_art2])
    assert story_evolution_service.determine_lifecycle_state(story_act, [act_art1, act_art2], []) == "ACTIVE"

    # 5. STABLE story (no updates for > 36 hours and story age > 48 hours)
    old_art1 = make_art("art_o1", "Quarterly Financials", "Desc", published_at=old_iso)
    old_art2 = make_art("art_o2", "Analyst Reactions", "Desc", published_at=(now - timedelta(hours=60)).isoformat())
    story_stable = make_story("s_stb", "Quarterly Financials", "Desc", published_at=old_iso, articles=[old_art1, old_art2])
    assert story_evolution_service.determine_lifecycle_state(story_stable, [old_art1, old_art2], []) == "STABLE"

    # 6. RESOLVED story (explicit resolution signals present)
    res_art = make_art("art_res", "System Outage Resolved and Patch Released", "All clear issued as services restored.", published_at=recent_iso)
    story_res = make_story(
        "s_res", "Cloud Outage Resolved After Patch Released", "Service restored and all clear issued.",
        published_at=recent_iso, articles=[res_art]
    )
    assert story_evolution_service.determine_lifecycle_state(story_res, [res_art], []) == "RESOLVED"


# ==============================================================================
# TEST 3: Breaking News Engine Weighting & Level Boundaries
# ==============================================================================
def test_3_breaking_news_formula():
    w = story_evolution_service.breaking_weights
    assert w["recency"] == 0.25
    assert w["urgency"] == 0.20
    assert w["severity"] == 0.20
    assert w["velocity"] == 0.15
    assert w["escalation"] == 0.10
    assert w["source_diversity"] == 0.05
    assert w["novelty"] == 0.05
    assert sum(w.values()) == 1.0

    thresholds = story_evolution_service.breaking_thresholds
    assert thresholds["BREAKING"] == 75
    assert thresholds["DEVELOPING"] == 55
    assert thresholds["UPDATED"] == 35


# ==============================================================================
# TEST 4: Non-Recency Guardrail (Routine Patch vs Breaking)
# ==============================================================================
def test_4_routine_release_not_breaking():
    # A routine library patch published 5 minutes ago
    now = datetime.now(timezone.utc)
    just_now = (now - timedelta(minutes=5)).isoformat()

    art = make_art("art_patch", "Minor CSS Framework Release v1.2.3", "Bug fix in button padding.", category="software engineering", published_at=just_now)
    story = make_story(
        "s_patch",
        "Minor CSS Framework Release v1.2.3",
        "Routine patch release for styling helper.",
        category="software engineering",
        importance_score=35,
        severity_score=0.15,
        urgency_score=0.20,
        escalation_score=0.05,
        published_at=just_now,
        articles=[art]
    )

    score, level, signals = story_evolution_service.compute_breaking_score(story, [art])

    # Recency is high (1.0), but severity/urgency are low
    assert signals["recency"] >= 0.95
    assert signals["severity"] <= 0.20
    assert signals["urgency"] <= 0.25
    # Must NOT be classified as BREAKING!
    assert level != "BREAKING"
    assert score <= 45


# ==============================================================================
# TEST 5: High-Urgency Incident Rapidly Classified as BREAKING
# ==============================================================================
def test_5_critical_crisis_becomes_breaking():
    now = datetime.now(timezone.utc)
    recent = (now - timedelta(minutes=20)).isoformat()

    art1 = make_art(
        "art_crisis_1",
        "Air Traffic Radar Failure Halts International Flights",
        "Fatal risks avoided as nationwide flights grounded in emergency.",
        source_name="Aviation Monitor",
        category="world",
        published_at=recent
    )
    art2 = make_art(
        "art_crisis_2",
        "Emergency Declared as Flight Control Outage Expands",
        "Critical severity failure spreads to neighboring airspace.",
        source_name="Global Wire",
        category="world",
        published_at=recent
    )

    story = make_story(
        "s_crisis",
        "Air Traffic Radar Failure Halts International Flights",
        "Nationwide airspace grounded under emergency advisory.",
        category="world",
        importance_score=92,
        severity_score=0.92,
        urgency_score=0.95,
        escalation_score=0.85,
        published_at=recent,
        articles=[art1, art2]
    )

    score, level, signals = story_evolution_service.compute_breaking_score(story, [art1, art2])

    assert score >= 75
    assert level == "BREAKING"
    assert signals["recency"] >= 0.85
    assert signals["urgency"] >= 0.90


# ==============================================================================
# TEST 6: Strict Independence of Breaking News & Global Importance
# ==============================================================================
def test_6_breaking_and_importance_strict_independence(clean_db):
    story = make_story(
        "s_indep",
        "International Maritime Border Agreement Ratified",
        "Comprehensive diplomatic treaty concluded after three years of talks.",
        category="world",
        importance_score=78,
        severity_score=0.78,
        urgency_score=0.30
    )
    db_repository.insert_story(story)

    # Initial state
    assert db_repository.get_story("s_indep")["importance_score"] == 78

    # Evolve story with high breaking velocity
    now_iso = datetime.now(timezone.utc).isoformat()
    arts = [
        make_art("a1", "Ratification Confirmed", "Desc", source_name="Outlet 1", published_at=now_iso),
        make_art("a2", "Treaty Formalized", "Desc", source_name="Outlet 2", published_at=now_iso),
        make_art("a3", "Signatures Exchanged", "Desc", source_name="Outlet 3", published_at=now_iso)
    ]
    for a in arts:
        db_repository.insert_article(a)
    db_repository.link_articles_to_story("s_indep", [a["id"] for a in arts])

    evolved = story_evolution_service.evolve_story("s_indep")

    # Global importance remains exactly 78!
    assert evolved["importance_score"] == 78
    assert evolved["importance_tier"] == "HIGH"

    # Breaking score is independent
    assert "breaking_score" in evolved
    assert evolved["breaking_score"] != evolved["importance_score"]

    # User preferences should NOT alter breaking status
    db_repository.save_user_preferences("user_anti_world", {"interest_weights": {"world": 0.05}})
    db_repository.save_user_preferences("user_pro_world", {"interest_weights": {"world": 0.99}})

    story_check = db_repository.get_story("s_indep")
    assert story_check["importance_score"] == 78
    assert story_check["breaking_score"] == evolved["breaking_score"]


# ==============================================================================
# TEST 7: Grounded Timeline Events with Real Article Citations
# ==============================================================================
def test_7_grounded_timeline_events():
    now = datetime.now(timezone.utc)
    t1 = (now - timedelta(hours=4)).isoformat()
    t2 = (now - timedelta(hours=2)).isoformat()

    a1 = make_art("art_ground_1", "Initial Report: Satellite Loses Telemetry", "Ground stations lose contact with scientific orbiter.", source_name="Space News", published_at=t1)
    a2 = make_art("art_ground_2", "NASA Confirms Backup Transmitter Reconnected", "Engineers re-establish low-bitrate connection with satellite.", source_name="Tech Wire", published_at=t2)

    story = make_story("s_ground", "Satellite Telemetry Anomaly", "Scientific satellite encounters communication glitch.", category="space", published_at=t1, articles=[a1, a2])

    events = story_evolution_service.generate_timeline_events(story, [a1, a2])

    assert len(events) == 2
    # 1. Initial report event
    ev1 = events[0]
    assert ev1["event_type"] == "INITIAL_REPORT"
    assert "art_ground_1" in ev1["article_ids"]
    assert "Space News" in ev1["title"]
    assert ev1["occurred_at"] == t1

    # 2. Subsequent development event
    ev2 = events[1]
    assert ev2["event_type"] in {"DEVELOPMENT", "UPDATE"}
    assert "art_ground_2" in ev2["article_ids"]
    assert "Tech Wire" in ev2["title"]
    assert ev2["occurred_at"] == t2


# ==============================================================================
# TEST 8: Conflicting Perspectives Detection
# ==============================================================================
def test_8_conflicting_perspectives():
    a1 = make_art(
        "art_persp_1",
        "MegaCorp Denies All Allegations of Secret Data Collection",
        "Company spokesperson refutes and rejects findings of unauthorized telemetry.",
        source_name="Corporate Wire"
    )
    a2 = make_art(
        "art_persp_2",
        "Independent Researchers Reveal Evidence of Covert Telemetry in App",
        "Security audit uncovers network packet captures demonstrating unauthorized data transmission.",
        source_name="Cyber Audit"
    )

    story = make_story("s_dispute", "MegaCorp Data Tracking Dispute", "Dispute over privacy telemetry.", category="cybersecurity", articles=[a1, a2])

    perspectives = story_evolution_service.detect_perspectives(story, [a1, a2])

    assert len(perspectives) >= 1
    p = perspectives[0]
    assert p["status"] == "Conflicting reporting"
    assert len(p["sources"]) == 2

    source_names = [s["source_name"] for s in p["sources"]]
    assert "Corporate Wire" in source_names
    assert "Cyber Audit" in source_names

    for src in p["sources"]:
        assert src["article_id"] in ["art_persp_1", "art_persp_2"]
        assert len(src["stance"]) > 0


# ==============================================================================
# TEST 9: Grounded Latest Development Extraction
# ==============================================================================
def test_9_grounded_latest_development(clean_db):
    now = datetime.now(timezone.utc)
    t1 = (now - timedelta(hours=3)).isoformat()
    t2 = (now - timedelta(minutes=15)).isoformat()

    a1 = make_art("art_ld_1", "Space Exploration Rocket Launches From Pad 39A", "Initial launch successful.", published_at=t1)
    a2 = make_art("art_ld_2", "Payload Deployed Successfully in High Orbit", "Confirmed deployment of communications satellite constellation.", published_at=t2)

    db_repository.insert_article(a1)
    db_repository.insert_article(a2)

    story = make_story("s_ld", "Rocket Launch Mission", "Mission summary.", category="space", published_at=t1, articles=[a1, a2])
    db_repository.insert_story(story)
    db_repository.link_articles_to_story("s_ld", ["art_ld_1", "art_ld_2"])

    evolved = story_evolution_service.evolve_story("s_ld")

    assert evolved["latest_development"] is not None
    assert "Payload Deployed" in evolved["latest_development"]
    assert evolved["update_count"] == 1


# ==============================================================================
# TEST 10: Database Persistence in story_events Table
# ==============================================================================
def test_10_database_persistence_events(clean_db):
    story_id = "s_db_ev_1"
    story = make_story(story_id, "Title", "Summary")
    db_repository.insert_story(story)

    ev = {
        "id": "ev_test_10",
        "story_id": story_id,
        "event_type": "DEVELOPMENT",
        "title": "Major Breakthrough Announced",
        "summary": "Laboratory results verified by external team.",
        "article_ids": ["art_10_a", "art_10_b"],
        "occurred_at": datetime.now(timezone.utc).isoformat(),
        "significance": 0.85
    }

    db_repository.insert_story_event(ev)
    saved_events = db_repository.get_story_events(story_id)

    assert len(saved_events) == 1
    e = saved_events[0]
    assert e["id"] == "ev_test_10"
    assert e["event_type"] == "DEVELOPMENT"
    assert e["title"] == "Major Breakthrough Announced"
    assert "art_10_a" in e["article_ids"]
    assert "art_10_b" in e["article_ids"]


# ==============================================================================
# TEST 11: GET /api/stories Exposes Phase 7 Fields
# ==============================================================================
def test_11_api_stories_evolution_fields(client, clean_db):
    story = make_story(
        "api_evo_story",
        "Global Quantum Key Distribution Network Tested",
        "Researchers complete long-range entanglement link.",
        category="science"
    )
    story["story_status"] = "DEVELOPING"
    story["breaking_score"] = 62
    story["breaking_level"] = "DEVELOPING"
    story["update_count"] = 2
    story["latest_development"] = "Satellite optical link achieved 100km transmission."
    db_repository.insert_story(story)

    resp = client.get("/api/stories")
    assert resp.status_code == 200
    items = resp.json()["items"]
    assert len(items) >= 1

    item = next(it for it in items if it["id"] == "api_evo_story")
    assert item["story_status"] == "DEVELOPING"
    assert item["breaking_score"] == 62
    assert item["breaking_level"] == "DEVELOPING"
    assert item["update_count"] == 2
    assert "latest_updated_at" in item
    # Internal DB fields must not leak
    assert "perspectives_json" not in item
    assert "evolution_version" in item


# ==============================================================================
# TEST 12: GET /api/stories/{id} Exposes Timeline & Perspectives
# ==============================================================================
def test_12_api_story_detail_timeline_perspectives(client, clean_db):
    story_id = "detail_evo_story"
    now_iso = datetime.now(timezone.utc).isoformat()
    story = make_story(
        story_id,
        "Operating System Kernel Vulnerability Investigation",
        "Investigation into privilege escalation vulnerability.",
        category="software engineering"
    )
    story["story_status"] = "ACTIVE"
    story["breaking_score"] = 40
    story["breaking_level"] = "UPDATED"
    story["latest_development"] = "Maintainers prepare upstream security patch."
    story["perspectives"] = [
        {
            "topic_or_issue": "Patch Deployment Timing",
            "status": "Conflicting reporting",
            "sources": [
                {"source_name": "Vendor A", "stance": "patch ready immediately", "article_id": "art_v_a"},
                {"source_name": "Distro B", "stance": "requires further testing", "article_id": "art_v_b"}
            ]
        }
    ]
    db_repository.insert_story(story)

    db_repository.insert_story_event({
        "id": "ev_dtl_1",
        "story_id": story_id,
        "event_type": "INITIAL_REPORT",
        "title": "Initial advisory released",
        "summary": "CVE assigned for buffer flaw.",
        "article_ids": ["art_v_a"],
        "occurred_at": now_iso
    })

    resp = client.get(f"/api/stories/{story_id}")
    assert resp.status_code == 200
    detail = resp.json()

    assert detail["id"] == story_id
    assert detail["story_status"] == "ACTIVE"
    assert detail["breaking_score"] == 40
    assert detail["breaking_level"] == "UPDATED"
    assert detail["latest_development"] == "Maintainers prepare upstream security patch."
    assert "timeline" in detail and len(detail["timeline"]) >= 1
    assert detail["timeline"][0]["title"] == "Initial advisory released"
    assert "perspectives" in detail and len(detail["perspectives"]) == 1
    assert detail["perspectives"][0]["status"] == "Conflicting reporting"


# ==============================================================================
# TEST 13: POST /api/stories/{id}/evolve and GET /api/stories/{id}/timeline
# ==============================================================================
def test_13_api_evolve_and_timeline_endpoints(client, clean_db):
    story_id = "endpoint_evo_story"
    now_iso = datetime.now(timezone.utc).isoformat()
    a1 = make_art("art_ep_1", "Launch Announced", "Summary 1", published_at=now_iso)
    db_repository.insert_article(a1)

    story = make_story(story_id, "Space Mission Launch", "Summary.", category="space", published_at=now_iso, articles=[a1])
    db_repository.insert_story(story)
    db_repository.link_articles_to_story(story_id, ["art_ep_1"])

    # 1. Test POST /api/stories/{id}/evolve
    resp_evolve = client.post(f"/api/stories/{story_id}/evolve")
    assert resp_evolve.status_code == 200
    evolved_data = resp_evolve.json()
    assert evolved_data["id"] == story_id
    assert "story_status" in evolved_data
    assert "breaking_score" in evolved_data
    assert "breaking_level" in evolved_data

    # 2. Test GET /api/stories/{id}/timeline
    resp_timeline = client.get(f"/api/stories/{story_id}/timeline")
    assert resp_timeline.status_code == 200
    tl_data = resp_timeline.json()
    assert tl_data["story_id"] == story_id
    assert tl_data["total_events"] >= 1
    assert len(tl_data["events"]) >= 1
    assert tl_data["events"][0]["event_type"] == "INITIAL_REPORT"
