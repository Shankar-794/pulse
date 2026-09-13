"""
PostgreSQL-ready SQLAlchemy Entities for Pulse Personal News Intelligence.
These models represent the normalized relational schema for ingested articles,
clustered stories, sources, topics, and personalization profiles.
"""
from datetime import datetime
from typing import List, Optional

try:
    from sqlalchemy import (
        Column,
        String,
        Integer,
        Float,
        Boolean,
        DateTime,
        ForeignKey,
        Text,
        JSON
    )
    from sqlalchemy.orm import relationship
    from backend.app.core.database import Base

    class SourceModel(Base):
        __tablename__ = "sources"

        id = Column(String(64), primary_key=True, index=True)
        name = Column(String(128), nullable=False)
        domain = Column(String(128), nullable=False, unique=True, index=True)
        reliability_score = Column(Float, default=1.0)
        is_active = Column(Boolean, default=True)
        created_at = Column(DateTime, default=datetime.utcnow)

        articles = relationship("ArticleModel", back_populates="source")

    class StoryModel(Base):
        """
        Represents a deduplicated, synthesized news event clustered from multiple articles.
        """
        __tablename__ = "stories"

        id = Column(String(64), primary_key=True, index=True)
        title = Column(String(512), nullable=False)
        summary = Column(Text, nullable=False)
        why_it_matters = Column(Text, nullable=True)
        category = Column(String(64), nullable=False, index=True)
        primary_topic = Column(String(64), nullable=False, index=True)
        
        # Scoring metrics
        importance_score = Column(Integer, default=50, index=True) # 0-100
        relevance_score = Column(Integer, default=50, index=True)  # 0-100
        freshness_score = Column(Integer, default=100)            # Decay over time
        source_count = Column(Integer, default=1)
        
        # Intelligence metadata
        timeline = Column(JSON, default=list)                     # Chronological milestones
        entities = Column(JSON, default=list)                     # Extracted named entities
        tags = Column(JSON, default=list)                         # Topic tags
        
        created_at = Column(DateTime, default=datetime.utcnow, index=True)
        updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

        articles = relationship("ArticleModel", back_populates="story", cascade="all, delete-orphan")

    class ArticleModel(Base):
        """
        Individual ingested article from an external permitted source.
        """
        __tablename__ = "articles"

        id = Column(String(64), primary_key=True, index=True)
        story_id = Column(String(64), ForeignKey("stories.id", ondelete="SET NULL"), nullable=True, index=True)
        source_id = Column(String(64), ForeignKey("sources.id"), nullable=False, index=True)
        
        title = Column(String(512), nullable=False)
        description = Column(Text, nullable=True)
        url = Column(String(1024), nullable=False, unique=True)
        author = Column(String(128), nullable=True)
        published_at = Column(DateTime, nullable=False, index=True)
        raw_content_hash = Column(String(64), nullable=True)
        created_at = Column(DateTime, default=datetime.utcnow)

        story = relationship("StoryModel", back_populates="articles")
        source = relationship("SourceModel", back_populates="articles")

    class TopicModel(Base):
        __tablename__ = "topics"

        id = Column(String(64), primary_key=True, index=True)
        name = Column(String(64), nullable=False, unique=True)
        slug = Column(String(64), nullable=False, unique=True, index=True)
        description = Column(Text, nullable=False)
        category = Column(String(64), nullable=False)
        follower_count = Column(Integer, default=0)
        created_at = Column(DateTime, default=datetime.utcnow)

    class UserPreferenceModel(Base):
        __tablename__ = "user_preferences"

        id = Column(String(64), primary_key=True, index=True)
        user_id = Column(String(64), default="default_user", unique=True, index=True)
        interests = Column(JSON, default=list)
        breaking_sensitivity = Column(String(32), default="standard")
        importance_threshold = Column(Integer, default=50)
        preferred_sources = Column(JSON, default=list)
        hidden_topics = Column(JSON, default=list)
        theme = Column(String(32), default="terminal-dark")
        updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    class UserInteractionModel(Base):
        __tablename__ = "user_interactions"

        id = Column(String(64), primary_key=True, index=True)
        user_id = Column(String(64), nullable=False, index=True)
        story_id = Column(String(64), ForeignKey("stories.id", ondelete="CASCADE"), nullable=False, index=True)
        interaction_type = Column(String(32), nullable=False) # view, save, unsave, hide, click_source
        timestamp = Column(DateTime, default=datetime.utcnow, index=True)

except ImportError:
    # If SQLAlchemy is not installed in the current environment
    SourceModel = object
    StoryModel = object
    ArticleModel = object
    TopicModel = object
    UserPreferenceModel = object
    UserInteractionModel = object
