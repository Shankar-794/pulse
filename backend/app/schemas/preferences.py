from datetime import datetime
from typing import List, Optional, Dict
from pydantic import BaseModel, Field


class PersonalRelevanceBreakdown(BaseModel):
    personal_relevance_score: int = Field(ge=0, le=100, description="Final deterministic personal relevance score (0-100)")
    category_match: float = Field(ge=0.0, le=1.0, description="Normalized category interest alignment")
    topic_match: float = Field(ge=0.0, le=1.0, description="Normalized topic interest alignment")
    entity_match: float = Field(ge=0.0, le=1.0, description="Normalized entity affinity match")
    behavioral_affinity: float = Field(ge=0.0, le=1.0, description="Learned interaction affinity score")
    novelty: float = Field(ge=0.0, le=1.0, description="Novelty component score")
    reasons: List[str] = Field(default_factory=list, description="Structured reasons for recommendation")
    relevance_reason: str = Field(description="Primary user-facing editorial explanation")
    relevance_version: str = Field(default="v1", description="Relevance algorithm version")
    calculated_at: Optional[str] = Field(default=None, description="ISO timestamp of calculation")


class UserInterestProfile(BaseModel):
    user_id: str = "default_user"
    interest_weights: Dict[str, float] = Field(default_factory=dict)
    topic_affinities: Dict[str, float] = Field(default_factory=dict)
    entity_affinities: Dict[str, float] = Field(default_factory=dict)
    hidden_story_ids: List[str] = Field(default_factory=list)
    saved_story_ids: List[str] = Field(default_factory=list)


class UserPreferenceBase(BaseModel):
    interests: List[str] = Field(default_factory=list)
    interest_weights: Dict[str, float] = Field(default_factory=dict)
    topic_affinities: Dict[str, float] = Field(default_factory=dict)
    entity_affinities: Dict[str, float] = Field(default_factory=dict)
    breaking_sensitivity: str = "standard"  # "all", "standard", "critical_only"
    importance_threshold: int = Field(default=50, ge=0, le=100)
    preferred_sources: List[str] = Field(default_factory=list)
    hidden_topics: List[str] = Field(default_factory=list)
    theme: str = "terminal-dark"


class UserPreferenceUpdate(BaseModel):
    interests: Optional[List[str]] = None
    interest_weights: Optional[Dict[str, float]] = None
    topic_affinities: Optional[Dict[str, float]] = None
    entity_affinities: Optional[Dict[str, float]] = None
    breaking_sensitivity: Optional[str] = None
    importance_threshold: Optional[int] = Field(default=None, ge=0, le=100)
    preferred_sources: Optional[List[str]] = None
    hidden_topics: Optional[List[str]] = None
    theme: Optional[str] = None


class UserPreferenceResponse(UserPreferenceBase):
    user_id: str
    updated_at: Optional[datetime] = None

    class Config:
        from_attributes = True


class UserInteractionCreate(BaseModel):
    story_id: str
    interaction_type: str  # 'view', 'save', 'unsave', 'hide', 'read', 'share'
    metadata: Optional[dict] = None
