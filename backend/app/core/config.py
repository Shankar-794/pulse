import os
from typing import List, Union, Optional, Dict


PRODUCTION_FRONTEND_ORIGIN = "https://pulse-drab-eight.vercel.app"
DEFAULT_LOCAL_ORIGINS = [
    "http://localhost:5173",
    "http://127.0.0.1:5173",
    "http://localhost:3000",
    "http://127.0.0.1:3000"
]


def _parse_cors_origins(cors_input: Optional[Union[str, List[str]]] = None) -> List[str]:
    """
    Robust CORS origins parser supporting:
    - JSON array strings: '["https://pulse-drab-eight.vercel.app"]'
    - Single-quoted pseudo-JSON: "['https://pulse-drab-eight.vercel.app']"
    - Comma-separated strings: "https://pulse-drab-eight.vercel.app, http://localhost:5173"
    - Raw Python list of strings
    - Automatically strips trailing slashes, surrounding quotes, and whitespace.
    - Disallows wildcard '*' while guaranteeing production frontend and local dev origins.
    """
    if cors_input is None:
        cors_input = os.getenv("BACKEND_CORS_ORIGINS")

    raw_items: List[str] = []

    if isinstance(cors_input, (list, tuple, set)):
        raw_items = [str(x) for x in cors_input]
    elif isinstance(cors_input, str):
        s = cors_input.strip()
        # Strip outer quotes if the entire string was quoted
        if (s.startswith('"') and s.endswith('"')) or (s.startswith("'") and s.endswith("'")):
            s = s[1:-1].strip()

        if s.startswith("[") and s.endswith("]"):
            import json
            try:
                parsed = json.loads(s)
                if isinstance(parsed, list):
                    raw_items = [str(x) for x in parsed]
                else:
                    raw_items = [str(parsed)]
            except Exception:
                # Handle single-quoted list like ['https://...']
                inner = s[1:-1].strip()
                raw_items = inner.split(",")
        elif s:
            raw_items = s.split(",")
    else:
        raw_items = []

    cleaned_origins: List[str] = []
    for item in raw_items:
        clean = str(item).strip().strip("'\"").rstrip("/")
        if clean and clean != "*" and clean not in cleaned_origins:
            cleaned_origins.append(clean)

    # Always ensure the production frontend origin is allowed
    if PRODUCTION_FRONTEND_ORIGIN not in cleaned_origins:
        cleaned_origins.append(PRODUCTION_FRONTEND_ORIGIN)

    # Ensure local dev origins are available
    for loc in DEFAULT_LOCAL_ORIGINS:
        if loc not in cleaned_origins:
            cleaned_origins.append(loc)

    return cleaned_origins


def _is_debug_enabled() -> bool:
    env = os.getenv("ENVIRONMENT", "development").lower()
    default_debug = "false" if env == "production" else "true"
    return os.getenv("DEBUG", default_debug).lower() in ("true", "1", "yes")


try:
    from pydantic_settings import BaseSettings
    from pydantic import field_validator

    class Settings(BaseSettings):
        PROJECT_NAME: str = "Pulse Personal News Intelligence"
        API_V1_STR: str = "/api"
        ENVIRONMENT: str = os.getenv("ENVIRONMENT", "development")
        DEBUG: bool = _is_debug_enabled()
        
        # CORS
        BACKEND_CORS_ORIGINS: List[str] = _parse_cors_origins()

        @field_validator("BACKEND_CORS_ORIGINS", mode="before")
        @classmethod
        def assemble_cors_origins(cls, v: Any) -> List[str]:
            return _parse_cors_origins(v)
        
        # PostgreSQL Connection Config (Production on Render)
        DATABASE_URL: Optional[str] = os.getenv("DATABASE_URL") or None
        USE_IN_MEMORY_STORE: bool = False

        @property
        def is_postgres_enabled(self) -> bool:
            url = (self.DATABASE_URL or "").strip().lower()
            return url.startswith("postgres://") or url.startswith("postgresql://") or url.startswith("postgresql+")

        # SQLite Concurrency & Hardening (Phase 9 Step 1)
        SQLITE_DB_PATH: Optional[str] = os.getenv("SQLITE_DB_PATH", None)
        SQLITE_BUSY_TIMEOUT_MS: int = int(os.getenv("SQLITE_BUSY_TIMEOUT_MS", "30000"))
        SQLITE_WAL_MODE: bool = os.getenv("SQLITE_WAL_MODE", "true").lower() in ("true", "1", "yes")
        SQLITE_SYNCHRONOUS: str = os.getenv("SQLITE_SYNCHRONOUS", "NORMAL")
        AUTO_INGEST_ON_EMPTY_STARTUP: bool = os.getenv("AUTO_INGEST_ON_EMPTY_STARTUP", "true").lower() in ("true", "1", "yes")
        
        # Intelligence Pipeline Defaults
        BREAKING_NEWS_IMPORTANCE_THRESHOLD: int = 85
        DEFAULT_IMPORTANCE_FILTER: int = 50
        DEFAULT_USER_INTERESTS: List[str] = [
            "AI",
            "Software Engineering",
            "Cybersecurity",
            "Semiconductors",
            "Space",
            "Science",
            "Business",
            "Economy"
        ]

        # Semantic Clustering Configuration (Phase 3 & 3B)
        CLUSTER_SIMILARITY_THRESHOLD: float = 0.32
        CLUSTER_TIME_WINDOW_HOURS: int = 72
        CLUSTER_LEXICAL_WEIGHT: float = 0.65
        CLUSTER_ENTITY_WEIGHT: float = 0.35
        CATEGORY_RELATIONSHIPS: dict = {
            "technology": ["ai", "cybersecurity", "software engineering", "semiconductors", "science", "space", "world", "business"],
            "ai": ["technology", "software engineering", "science", "world", "business"],
            "cybersecurity": ["technology", "software engineering", "world", "business"],
            "space": ["science", "technology"],
            "science": ["space", "technology", "ai"],
            "world": ["technology", "ai", "cybersecurity", "business", "economy", "general"],
            "business": ["economy", "technology", "world", "ai"],
            "economy": ["business", "world", "technology"]
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

        # Automatic Pipeline Scheduler Configuration (Phase 8.2 Step 3)
        SCHEDULER_ENABLED: bool = os.getenv("SCHEDULER_ENABLED", "true").lower() in ("true", "1", "yes")
        SCHEDULER_INTERVAL_MINUTES: int = int(os.getenv("SCHEDULER_INTERVAL_MINUTES", "30"))

        # Stale Pipeline Run Detection & Resilience Configuration (Phase 9.1 Step 4)
        PIPELINE_STALE_TIMEOUT_SECONDS: int = int(os.getenv("PIPELINE_STALE_TIMEOUT_SECONDS", "600"))
        PIPELINE_STALE_QUEUE_TIMEOUT_SECONDS: int = int(os.getenv("PIPELINE_STALE_QUEUE_TIMEOUT_SECONDS", "300"))
        PIPELINE_STALE_CHECK_INTERVAL_SECONDS: int = int(os.getenv("PIPELINE_STALE_CHECK_INTERVAL_SECONDS", "60"))

        # Authentication & Google OAuth Configuration
        GOOGLE_CLIENT_ID: Optional[str] = os.getenv("GOOGLE_CLIENT_ID", None)
        GOOGLE_CLIENT_SECRET: Optional[str] = os.getenv("GOOGLE_CLIENT_SECRET", None)
        _default_redirect = "https://pulse-363y.onrender.com/api/auth/google/callback" if os.getenv("ENVIRONMENT", "development").lower() in ("production", "prod") else "http://localhost:8000/api/auth/google/callback"
        GOOGLE_REDIRECT_URI: str = os.getenv("GOOGLE_REDIRECT_URI", _default_redirect)
        FRONTEND_URL: str = os.getenv("FRONTEND_URL", PRODUCTION_FRONTEND_ORIGIN if os.getenv("ENVIRONMENT", "development").lower() in ("production", "prod") else "http://localhost:5173")
        AUTH_SECRET_KEY: str = os.getenv("AUTH_SECRET_KEY", "pulse-production-session-secret-key-replace-in-env-at-launch")
        AUTH_TOKEN_EXPIRE_DAYS: int = int(os.getenv("AUTH_TOKEN_EXPIRE_DAYS", "7"))

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
        DEBUG: bool = _is_debug_enabled()
        BACKEND_CORS_ORIGINS: List[str] = _parse_cors_origins()
        DATABASE_URL: Optional[str] = os.getenv("DATABASE_URL") or None
        USE_IN_MEMORY_STORE: bool = False

        @property
        def is_postgres_enabled(self) -> bool:
            url = (self.DATABASE_URL or "").strip().lower()
            return url.startswith("postgres://") or url.startswith("postgresql://") or url.startswith("postgresql+")
        SQLITE_DB_PATH: Optional[str] = os.getenv("SQLITE_DB_PATH", None)
        SQLITE_BUSY_TIMEOUT_MS: int = int(os.getenv("SQLITE_BUSY_TIMEOUT_MS", "30000"))
        SQLITE_WAL_MODE: bool = os.getenv("SQLITE_WAL_MODE", "true").lower() in ("true", "1", "yes")
        SQLITE_SYNCHRONOUS: str = os.getenv("SQLITE_SYNCHRONOUS", "NORMAL")
        AUTO_INGEST_ON_EMPTY_STARTUP: bool = os.getenv("AUTO_INGEST_ON_EMPTY_STARTUP", "true").lower() in ("true", "1", "yes")
        BREAKING_NEWS_IMPORTANCE_THRESHOLD: int = 85
        DEFAULT_IMPORTANCE_FILTER: int = 50
        DEFAULT_USER_INTERESTS: List[str] = [
            "AI",
            "Software Engineering",
            "Cybersecurity",
            "Semiconductors",
            "Space",
            "Science",
            "Business",
            "Economy"
        ]
        CLUSTER_SIMILARITY_THRESHOLD: float = 0.32
        CLUSTER_TIME_WINDOW_HOURS: int = 72
        CLUSTER_LEXICAL_WEIGHT: float = 0.65
        CLUSTER_ENTITY_WEIGHT: float = 0.35
        CATEGORY_RELATIONSHIPS: dict = {
            "technology": ["ai", "cybersecurity", "software engineering", "semiconductors", "science", "space", "world", "business"],
            "ai": ["technology", "software engineering", "science", "world", "business"],
            "cybersecurity": ["technology", "software engineering", "world", "business"],
            "space": ["science", "technology"],
            "science": ["space", "technology", "ai"],
            "world": ["technology", "ai", "cybersecurity", "business", "economy", "general"],
            "business": ["economy", "technology", "world", "ai"],
            "economy": ["business", "world", "technology"]
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

        # Automatic Pipeline Scheduler Configuration (Phase 8.2 Step 3)
        SCHEDULER_ENABLED: bool = os.getenv("SCHEDULER_ENABLED", "true").lower() in ("true", "1", "yes")
        SCHEDULER_INTERVAL_MINUTES: int = int(os.getenv("SCHEDULER_INTERVAL_MINUTES", "30"))

        # Stale Pipeline Run Detection & Resilience Configuration (Phase 9.1 Step 4)
        PIPELINE_STALE_TIMEOUT_SECONDS: int = int(os.getenv("PIPELINE_STALE_TIMEOUT_SECONDS", "600"))
        PIPELINE_STALE_QUEUE_TIMEOUT_SECONDS: int = int(os.getenv("PIPELINE_STALE_QUEUE_TIMEOUT_SECONDS", "300"))
        PIPELINE_STALE_CHECK_INTERVAL_SECONDS: int = int(os.getenv("PIPELINE_STALE_CHECK_INTERVAL_SECONDS", "60"))

        # Authentication & Google OAuth Configuration
        GOOGLE_CLIENT_ID: Optional[str] = os.getenv("GOOGLE_CLIENT_ID", None)
        GOOGLE_CLIENT_SECRET: Optional[str] = os.getenv("GOOGLE_CLIENT_SECRET", None)
        _default_redirect = "https://pulse-363y.onrender.com/api/auth/google/callback" if os.getenv("ENVIRONMENT", "development").lower() in ("production", "prod") else "http://localhost:8000/api/auth/google/callback"
        GOOGLE_REDIRECT_URI: str = os.getenv("GOOGLE_REDIRECT_URI", _default_redirect)
        FRONTEND_URL: str = os.getenv("FRONTEND_URL", PRODUCTION_FRONTEND_ORIGIN if os.getenv("ENVIRONMENT", "development").lower() in ("production", "prod") else "http://localhost:5173")
        AUTH_SECRET_KEY: str = os.getenv("AUTH_SECRET_KEY", "pulse-production-session-secret-key-replace-in-env-at-launch")
        AUTH_TOKEN_EXPIRE_DAYS: int = int(os.getenv("AUTH_TOKEN_EXPIRE_DAYS", "7"))

    settings = Settings()


