import os
from typing import List, Union, Optional, Dict


try:
    from pydantic_settings import BaseSettings
    class Settings(BaseSettings):
        PROJECT_NAME: str = "Pulse Personal News Intelligence"
        API_V1_STR: str = "/api"
        ENVIRONMENT: str = "development"
        DEBUG: bool = True
        
        # CORS
        BACKEND_CORS_ORIGINS: List[str] = [
            "http://localhost:5173",
            "http://127.0.0.1:5173",
            "http://localhost:3000",
            "http://127.0.0.1:3000"
        ]
        
        # PostgreSQL Connection Config
        DATABASE_URL: str = os.getenv(
            "DATABASE_URL",
            "postgresql+asyncpg://pulse_user:pulse_password@localhost:5432/pulse_intelligence"
        )
        USE_IN_MEMORY_STORE: bool = True
        
        # Intelligence Pipeline Defaults
        BREAKING_NEWS_IMPORTANCE_THRESHOLD: int = 85
        DEFAULT_IMPORTANCE_FILTER: int = 50
        DEFAULT_USER_INTERESTS: List[str] = [
            "AI",
            "Software Engineering",
            "Cybersecurity",
            "Semiconductors",
            "Space",
            "Science"
        ]

        # Semantic Clustering Configuration (Phase 3 & 3B)
        CLUSTER_SIMILARITY_THRESHOLD: float = 0.32
        CLUSTER_TIME_WINDOW_HOURS: int = 72
        CLUSTER_LEXICAL_WEIGHT: float = 0.65
        CLUSTER_ENTITY_WEIGHT: float = 0.35
        CATEGORY_RELATIONSHIPS: dict = {
            "technology": ["ai", "cybersecurity", "software engineering", "semiconductors", "science", "space", "world"],
            "ai": ["technology", "software engineering", "science", "world"],
            "cybersecurity": ["technology", "software engineering", "world"],
            "space": ["science", "technology"],
            "science": ["space", "technology", "ai"],
            "world": ["technology", "ai", "cybersecurity", "general"]
        }
        # AI Story Understanding Configuration (Phase 4)

        LLM_PROVIDER: str = os.getenv("LLM_PROVIDER", "auto")
        LLM_API_KEY: Optional[str] = os.getenv("LLM_API_KEY", os.getenv("GEMINI_API_KEY", os.getenv("OPENAI_API_KEY", None)))
        LLM_MODEL: str = os.getenv("LLM_MODEL", "gemini-1.5-flash")
        ANALYSIS_VERSION: str = "v1.2"

        # Global Importance Engine Configuration (Phase 5)
        IMPORTANCE_VERSION: str = "v1"
        IMPORTANCE_WEIGHTS: dict = {
            "severity": 0.25,
            "reach": 0.20,
            "impact": 0.20,
            "urgency": 0.10,
            "novelty": 0.10,
            "escalation": 0.10,
            "reporting_breadth": 0.05
        }
        IMPORTANCE_TIERS: dict = {
            "CRITICAL": 85,
            "HIGH": 70,
            "MEDIUM": 45,
            "LOW": 0
        }
        REACH_LEVEL_WEIGHTS: dict = {
            "local": 0.20,
            "regional": 0.40,
            "national": 0.60,
            "international": 0.80,
            "global": 1.00
        }
        NOVELTY_LEVEL_WEIGHTS: dict = {
            "new": 1.00,
            "development": 0.75,
            "follow_up": 0.50,
            "minor_update": 0.30,
            "repeated": 0.15
        }

        # Personal Relevance & Feed Ranking Configuration (Phase 6)
        RELEVANCE_VERSION: str = "v1"
        RELEVANCE_WEIGHTS: dict = {
            "category_match": 0.25,
            "topic_match": 0.35,
            "entity_match": 0.15,
            "behavioral_affinity": 0.20,
            "novelty": 0.05
        }
        DEFAULT_INTEREST_WEIGHTS: dict = {
            "ai": 0.95,
            "software engineering": 0.90,
            "cybersecurity": 0.82,
            "technology": 0.80,
            "science": 0.70,
            "space": 0.60,
            "world": 0.45,
            "business": 0.40
        }
        FEED_RANKING_WEIGHTS: dict = {
            "personal_relevance": 0.40,
            "global_importance": 0.30,
            "freshness": 0.15,
            "urgency": 0.10,
            "diversity_penalty": 0.05
        }
        GLOBAL_IMPORTANCE_OVERRIDE_THRESHOLD: int = 85
        DIVERSITY_MAX_CONSECUTIVE_CATEGORY: int = 2

        # Story Evolution, Breaking News & Event Lifecycle Configuration (Phase 7)
        EVOLUTION_VERSION: str = "v1"
        BREAKING_NEWS_WEIGHTS: dict = {
            "recency": 0.25,
            "urgency": 0.20,
            "severity": 0.20,
            "velocity": 0.15,
            "escalation": 0.10,
            "source_diversity": 0.05,
            "novelty": 0.05
        }
        BREAKING_LEVEL_THRESHOLDS: dict = {
            "BREAKING": 75,
            "DEVELOPING": 55,
            "UPDATED": 35,
            "STABLE": 0
        }
        LIFECYCLE_STATES: List[str] = [
            "NEW", "DEVELOPING", "ACTIVE", "ESCALATING", "STABLE", "RESOLVED"
        ]
        UPDATE_CLASSIFICATIONS: List[str] = [
            "NEW_STORY", "SAME_REPORTING", "MEANINGFUL_UPDATE", "ESCALATION", "CONTRADICTION", "CORRECTION"
        ]
        ESCALATION_KEYWORDS: List[str] = [
            "death toll", "emergency declared", "critical severity", "spreads", "exploited in the wild",
            "ransom demanded", "nationwide outage", "flights grounded", "evacuation", "fatal",
            "casualties", "breach expands", "urgent advisory", "active exploit"
        ]
        CONTRADICTION_KEYWORDS: List[str] = [
            "denies", "disputes", "contradicts", "refutes", "refuses to acknowledge",
            "claims otherwise", "conflicting reports", "denied allegation", "disputed claims"
        ]
        CORRECTION_KEYWORDS: List[str] = [
            "correction", "retracts", "clarifies", "walks back", "statement amended",
            "previously reported incorrectly", "retraction", "erratum"
        ]
        RESOLUTION_KEYWORDS: List[str] = [
            "resolved", "patch released", "service restored", "containment achieved",
            "all clear", "settlement reached", "verdict reached", "fix deployed", "mitigated"
        ]

        class Config:
            env_file = ".env"
            case_sensitive = True

    settings = Settings()


except Exception:
    # Fallback if pydantic_settings is not yet installed
    class Settings:
        PROJECT_NAME: str = "Pulse Personal News Intelligence"
        API_V1_STR: str = "/api"
        ENVIRONMENT: str = os.getenv("ENVIRONMENT", "development")
        DEBUG: bool = True
        BACKEND_CORS_ORIGINS: List[str] = [
            "http://localhost:5173",
            "http://127.0.0.1:5173",
            "http://localhost:3000",
            "http://127.0.0.1:3000"
        ]
        DATABASE_URL: str = os.getenv(
            "DATABASE_URL",
            "postgresql+asyncpg://pulse_user:pulse_password@localhost:5432/pulse_intelligence"
        )
        USE_IN_MEMORY_STORE: bool = True
        BREAKING_NEWS_IMPORTANCE_THRESHOLD: int = 85
        DEFAULT_IMPORTANCE_FILTER: int = 50
        DEFAULT_USER_INTERESTS: List[str] = [
            "AI",
            "Software Engineering",
            "Cybersecurity",
            "Semiconductors",
            "Space",
            "Science"
        ]
        CLUSTER_SIMILARITY_THRESHOLD: float = 0.32
        CLUSTER_TIME_WINDOW_HOURS: int = 72
        CLUSTER_LEXICAL_WEIGHT: float = 0.65
        CLUSTER_ENTITY_WEIGHT: float = 0.35
        CATEGORY_RELATIONSHIPS: dict = {
            "technology": ["ai", "cybersecurity", "software engineering", "semiconductors", "science", "space", "world"],
            "ai": ["technology", "software engineering", "science", "world"],
            "cybersecurity": ["technology", "software engineering", "world"],
            "space": ["science", "technology"],
            "science": ["space", "technology", "ai"],
            "world": ["technology", "ai", "cybersecurity", "general"]
        }
        LLM_PROVIDER: str = os.getenv("LLM_PROVIDER", "auto")
        LLM_API_KEY: Optional[str] = os.getenv("LLM_API_KEY", os.getenv("GEMINI_API_KEY", os.getenv("OPENAI_API_KEY", None)))
        LLM_MODEL: str = os.getenv("LLM_MODEL", "gemini-1.5-flash")
        LLM_BASE_URL: Optional[str] = os.getenv("LLM_BASE_URL", None)
        ANALYSIS_VERSION: str = "v1.2"

        # Global Importance Engine Configuration (Phase 5)
        IMPORTANCE_VERSION: str = "v1"
        IMPORTANCE_WEIGHTS: dict = {
            "severity": 0.25,
            "reach": 0.20,
            "impact": 0.20,
            "urgency": 0.10,
            "novelty": 0.10,
            "escalation": 0.10,
            "reporting_breadth": 0.05
        }
        IMPORTANCE_TIERS: dict = {
            "CRITICAL": 85,
            "HIGH": 70,
            "MEDIUM": 45,
            "LOW": 0
        }
        REACH_LEVEL_WEIGHTS: dict = {
            "local": 0.20,
            "regional": 0.40,
            "national": 0.60,
            "international": 0.80,
            "global": 1.00
        }
        NOVELTY_LEVEL_WEIGHTS: dict = {
            "new": 1.00,
            "development": 0.75,
            "follow_up": 0.50,
            "minor_update": 0.30,
            "repeated": 0.15
        }

        # Personal Relevance & Feed Ranking Configuration (Phase 6)
        RELEVANCE_VERSION: str = "v1"
        RELEVANCE_WEIGHTS: dict = {
            "category_match": 0.25,
            "topic_match": 0.35,
            "entity_match": 0.15,
            "behavioral_affinity": 0.20,
            "novelty": 0.05
        }
        DEFAULT_INTEREST_WEIGHTS: dict = {
            "ai": 0.95,
            "software engineering": 0.90,
            "cybersecurity": 0.82,
            "technology": 0.80,
            "science": 0.70,
            "space": 0.60,
            "world": 0.45,
            "business": 0.40
        }
        FEED_RANKING_WEIGHTS: dict = {
            "personal_relevance": 0.40,
            "global_importance": 0.30,
            "freshness": 0.15,
            "urgency": 0.10,
            "diversity_penalty": 0.05
        }
        GLOBAL_IMPORTANCE_OVERRIDE_THRESHOLD: int = 85
        DIVERSITY_MAX_CONSECUTIVE_CATEGORY: int = 2

        # Story Evolution, Breaking News & Event Lifecycle Configuration (Phase 7)
        EVOLUTION_VERSION: str = "v1"
        BREAKING_NEWS_WEIGHTS: dict = {
            "recency": 0.25,
            "urgency": 0.20,
            "severity": 0.20,
            "velocity": 0.15,
            "escalation": 0.10,
            "source_diversity": 0.05,
            "novelty": 0.05
        }
        BREAKING_LEVEL_THRESHOLDS: dict = {
            "BREAKING": 75,
            "DEVELOPING": 55,
            "UPDATED": 35,
            "STABLE": 0
        }
        LIFECYCLE_STATES: List[str] = [
            "NEW", "DEVELOPING", "ACTIVE", "ESCALATING", "STABLE", "RESOLVED"
        ]
        UPDATE_CLASSIFICATIONS: List[str] = [
            "NEW_STORY", "SAME_REPORTING", "MEANINGFUL_UPDATE", "ESCALATION", "CONTRADICTION", "CORRECTION"
        ]
        ESCALATION_KEYWORDS: List[str] = [
            "death toll", "emergency declared", "critical severity", "spreads", "exploited in the wild",
            "ransom demanded", "nationwide outage", "flights grounded", "evacuation", "fatal",
            "casualties", "breach expands", "urgent advisory", "active exploit"
        ]
        CONTRADICTION_KEYWORDS: List[str] = [
            "denies", "disputes", "contradicts", "refutes", "refuses to acknowledge",
            "claims otherwise", "conflicting reports", "denied allegation", "disputed claims"
        ]
        CORRECTION_KEYWORDS: List[str] = [
            "correction", "retracts", "clarifies", "walks back", "statement amended",
            "previously reported incorrectly", "retraction", "erratum"
        ]
        RESOLUTION_KEYWORDS: List[str] = [
            "resolved", "patch released", "service restored", "containment achieved",
            "all clear", "settlement reached", "verdict reached", "fix deployed", "mitigated"
        ]

    settings = Settings()


