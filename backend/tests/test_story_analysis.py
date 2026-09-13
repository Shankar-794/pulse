"""
Comprehensive Unit Tests for Claim-Level Grounding & Evidence Attribution (Phase 4, 4.1 & 4.2).
Tests:
1. StoryAnalysis Pydantic schema validation with claims
2. JSON fence cleaning and markdown extraction
3. MockStoryAnalysisProvider multi-source grounding with valid GroundedClaim objects
4. MockStoryAnalysisProvider singleton synthesis with claims
5. Validator strips source names from extracted entities
6. Validator rejects hallucinated organization in prose (LG regression test: Gamers Nexus / Level1Techs pruned)
7. Validator rejects hallucinated person in prose
8. Validator rejects unsupported claim with zero evidence overlap
9. Correct article attribution and invalid article ID correction
10. Sentence-level fallback (drops unsupported sentence, retains supported sentence)
11. Conservative Why It Matters grounding
12. Validator topic filtering
13. Validator rejects false 'ai' category on non-AI stories
14. Dynamic evidence-based confidence scoring
15. Safe offline execution resilience
16. Database persistence of claims_json and versioning (v1.2)
17. Batch analysis orchestration and idempotency
"""
import pytest
from datetime import datetime
from pydantic import ValidationError

from backend.app.schemas.story import StoryAnalysis, StructuredEntity, GroundedClaim, EvidenceArticle
from backend.app.services.story_analysis_service import (
    StoryAnalysisService,
    MockStoryAnalysisProvider,
    LLMStoryAnalysisProvider
)
from backend.app.services.story_analysis_validator import story_analysis_validator
from backend.app.core.db_repository import DbRepository


@pytest.fixture
def test_repo(tmp_path):
    """Isolated SQLite database repository for test execution."""
    db_file = tmp_path / "test_story_analysis.db"
    repo = DbRepository(db_path=str(db_file))
    return repo


@pytest.fixture
def mock_service(test_repo):
    """Returns a StoryAnalysisService configured with the grounded Mock provider."""
    return StoryAnalysisService(
        provider=MockStoryAnalysisProvider(),
        db_repo=test_repo
    )


# 1. StoryAnalysis Pydantic schema validation with claims
def test_story_analysis_schema_valid():
    data = {
        "title": "LG Responds to Smart TV Data Collection Concerns",
        "summary": "LG has issued an official statement regarding smart TV telemetry.",
        "claims": [
            {
                "text": "LG has issued an official statement regarding smart TV telemetry.",
                "evidence_article_ids": ["art-1", "art-2"],
                "confidence": 0.92
            }
        ],
        "why_it_matters": "Smart TV privacy affects millions of consumers and raises regulatory questions.",
        "category": "cybersecurity",
        "entities": [
            {"name": "LG", "type": "organization"},
            {"name": "WebOS", "type": "product"}
        ],
        "topics": ["Consumer Privacy", "Smart TVs", "Telemetry"],
        "confidence": 0.88,
        "analysis_version": "v1.2"
    }
    model = StoryAnalysis.model_validate(data)
    assert model.title == data["title"]
    assert model.category == "cybersecurity"
    assert len(model.claims) == 1
    assert model.claims[0].evidence_article_ids == ["art-1", "art-2"]
    assert len(model.entities) == 2
    assert model.entities[0].name == "LG"
    assert model.analysis_version == "v1.2"


def test_story_analysis_schema_invalid_missing_summary():
    with pytest.raises(ValidationError):
        StoryAnalysis.model_validate({
            "title": "Title only",
            "category": "technology"
        })


# 2. JSON fence cleaning and markdown extraction
def test_clean_json_response_fences():
    provider = LLMStoryAnalysisProvider()

    raw_markdown = (
        "Here is the story analysis:\n\n"
        "```json\n"
        '{\n  "title": "Synthesized Title",\n  "summary": "Synthesized Summary",\n  "claims": [],\n  "why_it_matters": "Impact",\n  "category": "technology"\n}\n'
        "```\n\nHope this helps!"
    )
    cleaned = provider.clean_json_response(raw_markdown)
    assert cleaned.startswith("{")
    assert cleaned.endswith("}")
    assert '"title": "Synthesized Title"' in cleaned


def test_clean_json_response_raw():
    provider = LLMStoryAnalysisProvider()
    raw = '{"title": "Direct", "summary": "No fences", "claims": [], "why_it_matters": "Fast", "category": "ai"}'
    cleaned = provider.clean_json_response(raw)
    assert cleaned == raw


# 3. MockStoryAnalysisProvider multi-source grounding with valid GroundedClaim objects
def test_mock_provider_multi_source_grounding():
    provider = MockStoryAnalysisProvider()
    story = {
        "id": "story-multi-1",
        "title": "Anthropic boss Dario Amodei calls for AI development to slow down",
        "category": "world",
        "primary_topic": "Global Technology & Policy"
    }
    articles = [
        {
            "id": "art-1",
            "title": "Anthropic boss Dario Amodei calls for AI development to slow down",
            "source_name": "BBC Technology",
            "description": "The call comes amid growing concerns that AI models may become able to inflict serious damage worldwide."
        },
        {
            "id": "art-2",
            "title": "Everyone should slow down AI development except for me",
            "source_name": "Hacker News",
            "description": "Comments"
        }
    ]

    analysis = provider.analyze_story(story, articles)
    assert isinstance(analysis, StoryAnalysis)

    # Validate claims
    assert len(analysis.claims) >= 1
    assert any("Anthropic boss Dario Amodei" in c.text for c in analysis.claims)
    # The article ID 'art-1' must be cited in claims
    assert any("art-1" in c.evidence_article_ids for c in analysis.claims)

    # Entities must contain the REAL story entities, NOT source names
    entity_names = [e.name for e in analysis.entities]
    assert "Anthropic" in entity_names
    assert "Dario Amodei" in entity_names
    assert "BBC Technology" not in entity_names
    assert "Hacker News" not in entity_names
    assert analysis.analysis_version == "v1.2"


# 4. MockStoryAnalysisProvider singleton synthesis with claims
def test_mock_provider_singleton_synthesis():
    provider = MockStoryAnalysisProvider()
    story = {
        "id": "story-single-1",
        "title": "DeepSeek introduces open weights reasoning model",
        "category": "technology",
        "primary_topic": "AI"
    }
    articles = [
        {
            "id": "art-single",
            "title": "DeepSeek introduces open weights reasoning model",
            "source_name": "Ars Technica",
            "description": "DeepSeek has released an open-source reasoning model rivaling frontier models."
        }
    ]

    analysis = provider.analyze_story(story, articles)
    assert isinstance(analysis, StoryAnalysis)
    assert len(analysis.claims) >= 1
    assert any("art-single" in c.evidence_article_ids for c in analysis.claims)
    entity_names = [e.name for e in analysis.entities]
    assert "DeepSeek" in entity_names
    assert "Ars Technica" not in entity_names
    assert analysis.analysis_version == "v1.2"


# 5. Validator strips source names from extracted entities
def test_validator_strips_source_names():
    story = {"id": "story-test", "title": "New Tech Breakthrough", "category": "technology"}
    articles = [
        {"id": "a1", "title": "Breakthrough announced", "source_name": "The Verge", "source_domain": "theverge.com", "description": "Details here"},
        {"id": "a2", "title": "Discussion on breakthrough", "source_name": "Hacker News", "source_domain": "news.ycombinator.com", "description": "Comments"}
    ]

    raw_analysis = StoryAnalysis(
        title="Breakthrough announced",
        summary="Reporting covers a new breakthrough.",
        claims=[GroundedClaim(text="Reporting covers a new breakthrough.", evidence_article_ids=["a1"], confidence=0.88)],
        why_it_matters="Relevant impact.",
        category="technology",
        entities=[
            StructuredEntity(name="The Verge", type="organization"),
            StructuredEntity(name="Hacker News", type="organization"),
            StructuredEntity(name="Breakthrough", type="technology")
        ],
        topics=["Technology", "Breakthrough"],
        confidence=0.85,
        analysis_version="v1.2"
    )

    validated = story_analysis_validator.validate_analysis(raw_analysis, story, articles)
    val_names = [e.name for e in validated.entities]
    assert "The Verge" not in val_names
    assert "Hacker News" not in val_names


# 6. CRITICAL REGRESSION TEST: Validator rejects hallucinated organization in prose (LG test case)
def test_validator_prunes_hallucinated_organizations_in_prose():
    story = {"id": "story-lg", "title": "LG responds to TV spying allegations", "category": "technology"}
    # Articles mention LG, TV, spying, telemetry, but DO NOT mention Gamers Nexus or Level1Techs
    articles = [
        {
            "id": "art-verge",
            "title": "LG responds to TV spying allegations",
            "source_name": "The Verge",
            "source_domain": "theverge.com",
            "description": "LG says user privacy is respected and smart TV telemetry can be turned off in preferences."
        },
        {
            "id": "art-hn",
            "title": "LG denies TV spying claims",
            "source_name": "Hacker News",
            "source_domain": "news.ycombinator.com",
            "description": "Comments"
        }
    ]

    # Suppose LLM generated claims mentioning 'Gamers Nexus' and 'Level1Techs'
    raw_analysis = StoryAnalysis(
        title="LG Responds to Telemetry Concerns",
        summary="LG addresses smart TV telemetry. Gamers Nexus and Level1Techs discovered alarming findings.",
        claims=[
            GroundedClaim(
                text="LG has responded to allegations regarding TV telemetry.",
                evidence_article_ids=["art-verge"],
                confidence=0.92
            ),
            GroundedClaim(
                text="Gamers Nexus and Level1Techs discovered alarming findings regarding TV monitoring.",
                evidence_article_ids=["art-verge"],
                confidence=0.90
            )
        ],
        why_it_matters="Privacy impact for connected devices.",
        category="technology",
        entities=[StructuredEntity(name="LG", type="organization")],
        topics=["Smart TV Privacy", "Telemetry"],
        confidence=0.85,
        analysis_version="v1.2"
    )

    validated = story_analysis_validator.validate_analysis(raw_analysis, story, articles)

    # 1. Claim 2 must be rejected because 'Gamers Nexus' and 'Level1Techs' are ungrounded!
    assert len(validated.claims) == 1
    assert "Gamers Nexus" not in validated.claims[0].text
    assert "Level1Techs" not in validated.claims[0].text

    # 2. Reconstructed summary must NOT contain 'Gamers Nexus' or 'Level1Techs'!
    assert "Gamers Nexus" not in validated.summary
    assert "Level1Techs" not in validated.summary
    assert "LG has responded to allegations" in validated.summary


# 7. Validator rejects hallucinated person in prose
def test_validator_prunes_hallucinated_person():
    story = {"id": "story-p", "title": "Quantum Chip Demonstrated", "category": "science"}
    articles = [
        {"id": "a-sc", "title": "Quantum Chip Demonstrated", "source_name": "Nature", "description": "Lab demonstrates 100 qubit coherence."}
    ]
    raw_analysis = StoryAnalysis(
        title="Quantum Chip Demonstrated",
        summary="Lab demonstrates 100 qubit coherence.",
        claims=[
            GroundedClaim(text="Lab demonstrates 100 qubit coherence.", evidence_article_ids=["a-sc"], confidence=0.9),
            GroundedClaim(text="Albert Einstein praised the new quantum design.", evidence_article_ids=["a-sc"], confidence=0.8)
        ],
        why_it_matters="Quantum impact.",
        category="science",
        entities=[],
        topics=["Quantum Computing"],
        confidence=0.85,
        analysis_version="v1.2"
    )

    validated = story_analysis_validator.validate_analysis(raw_analysis, story, articles)
    assert len(validated.claims) == 1
    assert "Albert Einstein" not in validated.summary


# 8. Validator rejects unsupported claim with zero evidence overlap
def test_validator_rejects_unsupported_claim():
    story = {"id": "story-un", "title": "Mars Rover Discovers Water", "category": "space"}
    articles = [
        {"id": "a-m", "title": "Mars Rover Discovers Water", "source_name": "NASA", "description": "Subsurface ice detected."}
    ]
    raw_analysis = StoryAnalysis(
        title="Mars Rover Discovers Water",
        summary="Subsurface ice detected.",
        claims=[
            GroundedClaim(text="Subsurface ice detected on Mars.", evidence_article_ids=["a-m"], confidence=0.9),
            GroundedClaim(text="The price of gold fell drastically in London.", evidence_article_ids=["a-m"], confidence=0.8)
        ],
        why_it_matters="Space science.",
        category="space",
        entities=[],
        topics=["Mars Exploration"],
        confidence=0.85,
        analysis_version="v1.2"
    )

    validated = story_analysis_validator.validate_analysis(raw_analysis, story, articles)
    assert len(validated.claims) == 1
    assert "price of gold" not in validated.summary


# 9. Correct article attribution and invalid article ID correction
def test_correct_article_attribution_and_repair():
    story = {"id": "story-att", "title": "Space Academy Initiative", "category": "space"}
    articles = [
        {"id": "art-nasa-real", "title": "Space Academy Initiative", "source_name": "NASA", "description": "NASA sets up US Space Academy."}
    ]
    raw_analysis = StoryAnalysis(
        title="Space Academy Initiative",
        summary="NASA sets up US Space Academy.",
        claims=[
            # Model cited a hallucinated ID "fake-article-999", but the text is supported by art-nasa-real
            GroundedClaim(text="NASA sets up US Space Academy.", evidence_article_ids=["fake-article-999"], confidence=0.9)
        ],
        why_it_matters="Education.",
        category="space",
        entities=[StructuredEntity(name="NASA", type="organization")],
        topics=["Space Policy"],
        confidence=0.85,
        analysis_version="v1.2"
    )

    validated = story_analysis_validator.validate_analysis(raw_analysis, story, articles)
    assert len(validated.claims) == 1
    # Should be re-attributed to the real article ID
    assert "art-nasa-real" in validated.claims[0].evidence_article_ids


# 10. Sentence-level fallback (drops unsupported sentence, retains supported sentence)
def test_sentence_level_fallback():
    story = {"id": "story-fb", "title": "Linux Kernel Update", "category": "technology"}
    articles = [
        {"id": "art-linux", "title": "Linux Kernel 6.9 Released", "source_name": "LWN", "description": "Linux Kernel 6.9 includes memory management fixes."}
    ]
    # Free-form summary without claims: first sentence supported, second sentence contains hallucinated entity
    raw_analysis = StoryAnalysis(
        title="Linux Kernel 6.9 Released",
        summary="Linux Kernel 6.9 includes memory management fixes. Satya Nadella announced new personal endorsement.",
        claims=[],  # Empty claims triggers sentence-level fallback
        why_it_matters="Operating systems.",
        category="technology",
        entities=[],
        topics=["Linux"],
        confidence=0.85,
        analysis_version="v1.2"
    )

    validated = story_analysis_validator.validate_analysis(raw_analysis, story, articles)
    assert len(validated.claims) == 1
    assert "memory management fixes" in validated.summary
    assert "Satya Nadella" not in validated.summary


# 11. Conservative Why It Matters grounding
def test_why_it_matters_conservative_grounding():
    story = {"id": "story-wim", "title": "LG TV Privacy", "category": "technology"}
    articles = [
        {"id": "a1", "title": "LG TV Telemetry Questions", "source_name": "The Verge", "description": "Consumers raise smart TV tracking questions."}
    ]
    # Why it matters makes wild claim about criminal indictments absent from text
    raw_analysis = StoryAnalysis(
        title="LG TV Telemetry Questions",
        summary="Consumers raise smart TV tracking questions.",
        claims=[GroundedClaim(text="Consumers raise smart TV tracking questions.", evidence_article_ids=["a1"], confidence=0.88)],
        why_it_matters="This could trigger criminal indictments against company executives.",
        category="technology",
        entities=[StructuredEntity(name="LG", type="organization")],
        topics=["Smart TV Privacy"],
        confidence=0.85,
        analysis_version="v1.2"
    )

    validated = story_analysis_validator.validate_analysis(raw_analysis, story, articles)
    # Must replace wild indictment claim with grounded consumer privacy statement
    assert "indictment" not in validated.why_it_matters.lower()
    assert "privacy" in validated.why_it_matters.lower()


# 12. Validator topic filtering
def test_validator_topic_filtering():
    story = {"id": "story-top", "title": "NASA establishes Space Academy", "category": "space"}
    articles = [
        {"id": "a-nasa", "title": "NASA establishes Space Academy", "source_name": "NASA", "description": "NASA-led initiative to shape aerospace education."}
    ]
    raw_analysis = StoryAnalysis(
        title="NASA Space Academy Initiative",
        summary="NASA begins Space Academy work.",
        claims=[GroundedClaim(text="NASA begins Space Academy work.", evidence_article_ids=["a-nasa"], confidence=0.85)],
        why_it_matters="Aerospace education impact.",
        category="space",
        entities=[StructuredEntity(name="NASA", type="organization")],
        topics=["News", "Breaking", "Article", "Space Academy", "Aerospace"],
        confidence=0.85,
        analysis_version="v1.2"
    )

    validated = story_analysis_validator.validate_analysis(raw_analysis, story, articles)
    assert "News" not in validated.topics
    assert "Breaking" not in validated.topics
    assert "Article" not in validated.topics
    assert any("Space" in t for t in validated.topics)


# 13. Validator rejects false 'ai' category on non-AI stories
def test_validator_rejects_false_ai_category():
    story = {"id": "story-cat", "title": "LG responds to TV spying allegations", "category": "ai"}
    articles = [
        {"id": "a-lg", "title": "LG responds to TV spying allegations", "source_name": "The Verge", "description": "LG pushes back against smart TV data tracking concerns."}
    ]
    raw_analysis = StoryAnalysis(
        title="LG TV Tracking Response",
        summary="LG clarifies data practices.",
        claims=[GroundedClaim(text="LG clarifies data practices.", evidence_article_ids=["a-lg"], confidence=0.85)],
        why_it_matters="Privacy impact.",
        category="ai",
        entities=[StructuredEntity(name="LG", type="organization")],
        topics=["Smart TV Privacy", "Telemetry"],
        confidence=0.85,
        analysis_version="v1.2"
    )

    validated = story_analysis_validator.validate_analysis(raw_analysis, story, articles)
    assert validated.category in {"cybersecurity", "technology"}


# 14. Dynamic evidence-based confidence scoring
def test_dynamic_confidence_scoring():
    short_articles = [
        EvidenceArticle(article_id="1", source_name="Wire", title="Brief Update", summary="Minimal text.")
    ]
    conf_short = story_analysis_validator.compute_grounded_confidence(
        evidence_articles=short_articles, retention_ratio=1.0, source_count=1, claim_retention_ratio=1.0
    )
    assert conf_short <= 0.72

    long_articles = [
        EvidenceArticle(article_id="1", source_name="S1", title="Detailed report part one", summary="A " * 70),
        EvidenceArticle(article_id="2", source_name="S2", title="Detailed report part two", summary="B " * 70)
    ]
    conf_long = story_analysis_validator.compute_grounded_confidence(
        evidence_articles=long_articles, retention_ratio=1.0, source_count=2, claim_retention_ratio=1.0
    )
    assert conf_long >= 0.85


# 15. Safe offline execution resilience
def test_llm_provider_offline_fallback():
    provider = LLMStoryAnalysisProvider(api_key=None, provider="auto")
    assert provider.provider == "mock"

    story = {"id": "story-offline", "title": "Linux 6.9 Released", "category": "technology"}
    articles = [{"id": "art-lwn", "title": "Linux 6.9 Released", "source_name": "LWN", "description": "Kernel update"}]

    result = provider.analyze_story(story, articles)
    assert isinstance(result, StoryAnalysis)
    assert result.analysis_version == "v1.2"
    assert len(result.claims) >= 1


# 16. Database persistence of claims_json and versioning (v1.2)
def test_db_persistence_and_retrieval(test_repo, mock_service):
    test_repo.insert_article({
        "id": "art-pers-1",
        "title": "LG clarifies telemetry policies on newer TV models",
        "description": "LG states that data collection can be turned off in system preferences.",
        "content": "LG says data collection is optional.",
        "url": "https://theverge.com/lg-tv",
        "canonical_url": "https://theverge.com/lg-tv",
        "source_id": "src-verge",
        "source_name": "The Verge",
        "source_domain": "theverge.com",
        "category": "technology",
        "published_at": datetime.utcnow().isoformat()
    })

    story_id = "story-pers-1"
    test_repo.upsert_story({
        "id": story_id,
        "title": "LG clarifies telemetry policies on newer TV models",
        "summary": "Initial summary",
        "why_it_matters": "Initial impact",
        "category": "technology",
        "primary_topic": "Privacy",
        "importance_score": 95,
        "relevance_score": 50,
        "freshness_score": 100,
        "source_count": 1,
        "article_count": 1,
        "first_published_at": datetime.utcnow().isoformat(),
        "last_published_at": datetime.utcnow().isoformat(),
        "created_at": datetime.utcnow().isoformat(),
        "updated_at": datetime.utcnow().isoformat()
    })
    test_repo.link_articles_to_story(story_id, ["art-pers-1"])

    analysis = mock_service.analyze_story_by_id(story_id)
    assert analysis is not None

    fetched = test_repo.get_story_by_id(story_id)
    assert fetched is not None
    assert fetched["analyzed"] is True
    assert fetched["analysis_version"] == "v1.2"
    assert fetched["analysis_confidence"] > 0.60
    assert isinstance(fetched["claims"], list)
    assert len(fetched["claims"]) >= 1
    assert "art-pers-1" in fetched["claims"][0]["evidence_article_ids"]


# 17. Batch analysis orchestration and idempotency
def test_analyze_batch_orchestration(test_repo, mock_service):
    for idx in range(1, 5):
        s_id = f"story-batch-{idx}"
        test_repo.upsert_story({
            "id": s_id,
            "title": f"Batch Story {idx}",
            "summary": f"Summary {idx}",
            "why_it_matters": f"Impact {idx}",
            "category": "technology",
            "primary_topic": "Tech",
            "importance_score": 80,
            "relevance_score": 50,
            "freshness_score": 100,
            "source_count": 1,
            "article_count": 1,
            "first_published_at": datetime.utcnow().isoformat(),
            "last_published_at": datetime.utcnow().isoformat(),
            "created_at": datetime.utcnow().isoformat(),
            "updated_at": datetime.utcnow().isoformat()
        })

    batch_result = mock_service.analyze_batch(limit=3)
    assert batch_result["status"] == "complete"
    assert batch_result["total_evaluated"] == 3
    assert batch_result["success_count"] == 3

    assert len(test_repo.get_unanalyzed_stories()) == 1

    re_analysis = mock_service.analyze_story_by_id("story-batch-1")
    assert re_analysis is not None
    updated = test_repo.get_story_by_id("story-batch-1")
    assert updated["analyzed"] is True
    assert updated["analysis_version"] == "v1.2"
    assert isinstance(updated["claims"], list)
