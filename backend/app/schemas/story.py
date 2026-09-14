from datetime import datetime
from typing import List, Optional, Dict, Any
from pydantic import BaseModel, Field

from backend.app.schemas.article import ArticleResponse


class TimelineEvent(BaseModel):
    time: str
    title: str
    description: str
    event_type: Optional[str] = "UPDATE"
    article_ids: List[str] = Field(default_factory=list)


class StoryEventRecord(BaseModel):
    id: str
    story_id: str
    event_type: str = Field(description="INITIAL_REPORT, DEVELOPMENT, ESCALATION, UPDATE, CONTRADICTION, CORRECTION, RESOLUTION")
    title: str
    summary: str
    article_ids: List[str] = Field(default_factory=list)
    occurred_at: Optional[str] = None
    detected_at: Optional[str] = None
    significance: float = 0.5
    event_version: str = "v1"


class PerspectiveSource(BaseModel):
    source_name: str
    stance: str
    article_id: str
    claim_text: Optional[str] = None


class StoryPerspective(BaseModel):
    topic_or_issue: str
    status: str = "Conflicting reporting"
    sources: List[PerspectiveSource] = Field(default_factory=list)
    detected_at: Optional[str] = None


class EntityMention(BaseModel):
    name: str
    category: str  # 'organization', 'technology', 'person', 'concept'


class EvidenceArticle(BaseModel):
    article_id: str
    source_name: str
    title: str
    published_at: Optional[str] = None
    summary: Optional[str] = None
    content: Optional[str] = None


class GroundedClaim(BaseModel):
    text: str = Field(description="Factual claim statement")
    evidence_article_ids: List[str] = Field(default_factory=list, description="IDs of articles containing evidence for this claim")
    confidence: float = Field(default=0.85, ge=0.0, le=1.0, description="Claim confidence score")


class StructuredEntity(BaseModel):
    name: str = Field(description="Name of the entity, organization, person, product, or technology")
    type: str = Field(default="organization", description="Entity type: organization, person, technology, product, location, event")


class StoryAnalysis(BaseModel):
    title: str = Field(description="Synthesized canonical headline of the event")
    summary: str = Field(description="Clear, cross-source synthesized explanation of what happened")
    claims: List[GroundedClaim] = Field(default_factory=list, description="Structured factual claims with article citations")
    why_it_matters: str = Field(description="Editorial significance of why this story matters")
    category: str = Field(description="Recommended primary category")
    entities: List[StructuredEntity] = Field(default_factory=list, description="Extracted named entities")
    topics: List[str] = Field(default_factory=list, description="2 to 5 specific topics/sub-fields")
    confidence: float = Field(ge=0.0, le=1.0, default=0.85, description="Analysis confidence score (0.0 - 1.0)")
    analysis_version: str = Field(default="v1.2", description="Prompt/model analysis version")


class ImportanceSignals(BaseModel):
    source_count: int = Field(default=1, ge=1, description="Number of independent reporting sources")
    article_count: int = Field(default=1, ge=1, description="Total articles covering the story")
    category: str = Field(default="technology", description="Primary topic/category")
    entity_count: int = Field(default=0, ge=0, description="Count of validated named entities")
    geographic_scope: str = Field(default="regional", description="Scope: local, regional, national, international, global")
    severity: float = Field(default=0.5, ge=0.0, le=1.0, description="Observable severity score (0.0 to 1.0)")
    affected_population: Optional[str] = Field(default=None, description="Qualitative or estimated scale of affected population")

    # 10 Impact dimensions (0.0 to 1.0, or None if not applicable)
    security_impact: Optional[float] = Field(default=None, ge=0.0, le=1.0)
    economic_impact: Optional[float] = Field(default=None, ge=0.0, le=1.0)
    political_impact: Optional[float] = Field(default=None, ge=0.0, le=1.0)
    technological_impact: Optional[float] = Field(default=None, ge=0.0, le=1.0)
    scientific_impact: Optional[float] = Field(default=None, ge=0.0, le=1.0)
    environmental_impact: Optional[float] = Field(default=None, ge=0.0, le=1.0)
    public_safety_impact: Optional[float] = Field(default=None, ge=0.0, le=1.0)
    public_health_impact: Optional[float] = Field(default=None, ge=0.0, le=1.0)
    industry_impact: Optional[float] = Field(default=None, ge=0.0, le=1.0)
    cultural_impact: Optional[float] = Field(default=None, ge=0.0, le=1.0)

    urgency: float = Field(default=0.5, ge=0.0, le=1.0, description="Urgency / active timeliness")
    novelty: float = Field(default=0.8, ge=0.0, le=1.0, description="Novelty level (new event, update, follow-up)")
    escalation: float = Field(default=0.1, ge=0.0, le=1.0, description="Escalation factor if situation is intensifying")
    official_confirmation: bool = Field(default=True, description="Whether event has official or cross-verified confirmation")


class ImportanceBreakdown(BaseModel):
    importance_score: int = Field(ge=0, le=100, description="Final deterministic global importance score (0-100)")
    importance_tier: str = Field(description="Tier: CRITICAL, HIGH, MEDIUM, LOW")
    severity: float = Field(ge=0.0, le=1.0, description="Normalized severity score")
    reach: float = Field(ge=0.0, le=1.0, description="Normalized reach score")
    impact: float = Field(ge=0.0, le=1.0, description="Combined impact dimension score")
    urgency: float = Field(ge=0.0, le=1.0, description="Urgency score")
    novelty: float = Field(ge=0.0, le=1.0, description="Novelty score")
    escalation: float = Field(ge=0.0, le=1.0, description="Escalation score")
    reporting_breadth: float = Field(ge=0.0, le=1.0, description="Reporting breadth score")
    explanation: str = Field(description="Deterministic grounded explanation")
    importance_version: str = Field(default="v1", description="Importance algorithm version")
    calculated_at: Optional[str] = Field(default=None, description="ISO timestamp of calculation")


class StoryBase(BaseModel):
    title: str
    summary: str
    why_it_matters: Optional[str] = None
    category: str
    primary_topic: str
    importance_score: int = Field(ge=0, le=100, default=50)
    relevance_score: int = Field(ge=0, le=100, default=50)
    freshness_score: int = Field(ge=0, le=100, default=100)
    source_count: int = Field(default=1)
    relevance_reason: Optional[str] = None
    timeline: List[TimelineEvent] = Field(default_factory=list)
    entities: List[EntityMention] = Field(default_factory=list)
    tags: List[str] = Field(default_factory=list)

    # Phase 7: Story Evolution Fields
    story_status: str = Field(default="ACTIVE", description="NEW, DEVELOPING, ACTIVE, ESCALATING, STABLE, RESOLVED")
    breaking_score: int = Field(ge=0, le=100, default=30, description="Deterministic Breaking News score (0-100)")
    breaking_level: str = Field(default="STABLE", description="BREAKING, DEVELOPING, UPDATED, STABLE")
    latest_development: Optional[str] = None
    latest_updated_at: Optional[str] = None
    update_count: int = Field(default=0)


class StoryCreate(StoryBase):
    pass


class StoryResponse(StoryBase):
    id: str
    story_id: Optional[str] = None
    is_breaking: bool = False
    is_saved: bool = False
    analyzed: bool = False
    ai_title: Optional[str] = None
    ai_summary: Optional[str] = None
    ai_category: Optional[str] = None
    analysis_confidence: Optional[float] = None
    analyzed_at: Optional[datetime] = None
    analysis_version: Optional[str] = "v1.2"
    topics: List[str] = Field(default_factory=list)
    claims: List[GroundedClaim] = Field(default_factory=list)
    importance_tier: Optional[str] = None
    importance_explanation: Optional[str] = None
    importance_version: Optional[str] = "v1"
    importance_breakdown: Optional[ImportanceBreakdown] = None
    relevance_version: Optional[str] = "v1"
    relevance_breakdown: Optional[Dict[str, Any]] = None
    final_rank_score: Optional[float] = None
    is_global_override: bool = False
    perspectives: List[StoryPerspective] = Field(default_factory=list)
    evolution_version: Optional[str] = "v1"
    created_at: datetime
    updated_at: Optional[datetime] = None
    articles: List[ArticleResponse] = Field(default_factory=list)

    class Config:
        from_attributes = True


class StoryListResponse(BaseModel):
    total: int
    items: List[StoryResponse]
    is_empty: Optional[bool] = False
    message: Optional[str] = None
