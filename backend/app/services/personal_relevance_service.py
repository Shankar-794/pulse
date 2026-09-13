"""
Personal Relevance Engine (Phase 6)

Calculates deterministic, explainable Personal Relevance Scores (0-100) for news stories
tailored to a user profile (e.g. Engineering Student persona).

Maintains strict separation between:
- GLOBAL IMPORTANCE ("How important is this event to the world?")
- PERSONAL RELEVANCE ("How relevant is this event specifically to this user?")

Signals:
1. Category Match (0.25)
2. Topic Match (0.35)
3. Entity Match (0.15)
4. Behavioral Affinity (0.20)
5. Novelty (0.05)
"""
import re
from datetime import datetime, timezone
from typing import Dict, Any, List, Optional, Tuple

from backend.app.core.config import settings
from backend.app.schemas.preferences import PersonalRelevanceBreakdown, UserInterestProfile


# Category canonical synonyms and alias mappings
CATEGORY_ALIASES: Dict[str, str] = {
    "ai": "ai",
    "artificial intelligence": "ai",
    "machine learning": "ai",
    "ml": "ai",
    "deep learning": "ai",
    "software": "software engineering",
    "software engineering": "software engineering",
    "coding": "software engineering",
    "programming": "software engineering",
    "dev": "software engineering",
    "development": "software engineering",
    "open source": "software engineering",
    "security": "cybersecurity",
    "cyber": "cybersecurity",
    "cybersecurity": "cybersecurity",
    "infosec": "cybersecurity",
    "technology": "technology",
    "tech": "technology",
    "science": "science",
    "space": "space",
    "aerospace": "space",
    "astronomy": "space",
    "world": "world",
    "geopolitics": "world",
    "politics": "world",
    "global": "world",
    "business": "business",
    "finance": "business",
    "economy": "business",
    "market": "business",
    "markets": "business"
}

# Semantic keyword taxonomy linking topics to interest categories
TOPIC_TAXONOMY: Dict[str, List[str]] = {
    "ai": [
        "ai", "artificial intelligence", "machine learning", "ml", "llm", "llms", "gpt",
        "chatgpt", "claude", "gemini", "transformer", "neural", "deep learning", "diffusion",
        "agent", "agents", "openai", "anthropic", "mistral", "deepseek", "model", "models"
    ],
    "software engineering": [
        "software", "programming", "code", "python", "rust", "typescript", "javascript",
        "golang", "go", "c++", "compiler", "framework", "library", "git", "linux",
        "kernel", "docker", "kubernetes", "api", "database", "sql", "architecture",
        "web", "frontend", "backend", "devops", "ci/cd", "refactor", "bug", "release"
    ],
    "cybersecurity": [
        "cybersecurity", "security", "vulnerability", "cve", "zero-day", "exploit",
        "breach", "hacker", "hacking", "malware", "ransomware", "phishing", "encryption",
        "crypto", "infosec", "ddos", "authentication", "backdoor", "patch", "advisory"
    ],
    "technology": [
        "technology", "tech", "hardware", "semiconductor", "chip", "chips", "processor",
        "gpu", "cpu", "nvidia", "intel", "amd", "apple", "google", "cloud", "server",
        "device", "gadget", "sensor", "telecom", "5g", "battery"
    ],
    "science": [
        "science", "physics", "quantum", "biology", "genetics", "health", "medicine",
        "climate", "energy", "fusion", "chemistry", "research", "study", "paper", "lab"
    ],
    "space": [
        "space", "nasa", "spacex", "mars", "moon", "orbit", "satellite", "astronomy",
        "telescope", "artemis", "rocket", "launch", "astronaut", "esa", "iss"
    ],
    "world": [
        "world", "geopolitics", "election", "war", "treaty", "government", "policy",
        "sanctions", "diplomacy", "international", "summit", "nation", "crisis"
    ],
    "business": [
        "business", "economy", "market", "stock", "ipo", "acquisition", "merger",
        "revenue", "startup", "venture", "vc", "earnings", "valuation", "antitrust"
    ]
}

# Major entities known in the tech/engineering student sphere
KNOWN_TECH_ENTITIES: Dict[str, float] = {
    "openai": 0.95,
    "anthropic": 0.92,
    "google": 0.88,
    "microsoft": 0.85,
    "apple": 0.82,
    "nvidia": 0.90,
    "meta": 0.82,
    "linux": 0.90,
    "github": 0.88,
    "amazon": 0.78,
    "intel": 0.75,
    "amd": 0.80,
    "crowdstrike": 0.85,
    "cloudflare": 0.84,
    "spacex": 0.82,
    "nasa": 0.80,
    "tesla": 0.75
}


def _has_keyword(text: str, keyword: str) -> bool:
    """Safe keyword matching using regex word boundaries."""
    pattern = r"\b" + re.escape(keyword.lower()) + r"\b"
    return bool(re.search(pattern, text.lower()))


class PersonalRelevanceService:
    """
    Deterministic Personal Relevance Engine (Phase 6).
    Scores stories against a user's explicit interest profile, topic affinities,
    entity affinities, and telemetry interaction history.
    """

    def __init__(self):
        self.version: str = getattr(settings, "RELEVANCE_VERSION", "v1")
        self.weights: Dict[str, float] = getattr(settings, "RELEVANCE_WEIGHTS", {
            "category_match": 0.25,
            "topic_match": 0.35,
            "entity_match": 0.15,
            "behavioral_affinity": 0.20,
            "novelty": 0.05
        })
        self.default_interest_weights: Dict[str, float] = getattr(
            settings,
            "DEFAULT_INTEREST_WEIGHTS",
            {
                "ai": 0.95,
                "software engineering": 0.90,
                "cybersecurity": 0.82,
                "technology": 0.80,
                "science": 0.70,
                "space": 0.60,
                "world": 0.45,
                "business": 0.40
            }
        )

    def normalize_category(self, category: Optional[str]) -> str:
        """Maps any raw category or synonym to canonical category string."""
        if not category:
            return "technology"
        cleaned = category.strip().lower()
        return CATEGORY_ALIASES.get(cleaned, cleaned)

    def compute_category_match(
        self,
        story: Dict[str, Any],
        interest_weights: Dict[str, float]
    ) -> Tuple[float, str]:
        """
        Computes category match signal (0.0 - 1.0).
        Evaluates story category and ai_category against user interest weights.
        """
        raw_cat = story.get("category") or story.get("ai_category") or "technology"
        canon_cat = self.normalize_category(raw_cat)

        # Check direct match in interest weights
        if canon_cat in interest_weights:
            score = float(interest_weights[canon_cat])
            return min(1.0, max(0.0, score)), canon_cat

        # Check partial or synonym match
        for key, weight in interest_weights.items():
            norm_key = self.normalize_category(key)
            if norm_key == canon_cat:
                return min(1.0, max(0.0, float(weight))), norm_key

        # Check secondary category
        ai_cat = story.get("ai_category")
        if ai_cat:
            canon_ai_cat = self.normalize_category(ai_cat)
            if canon_ai_cat in interest_weights:
                return min(1.0, max(0.0, float(interest_weights[canon_ai_cat]))), canon_ai_cat

        # Fallback baseline for unrecognized categories
        return 0.35, canon_cat

    def compute_topic_match(
        self,
        story: Dict[str, Any],
        interest_weights: Dict[str, float],
        topic_affinities: Dict[str, float]
    ) -> Tuple[float, Optional[str]]:
        """
        Computes topic match signal (0.0 - 1.0).
        Evaluates structured topics, tags, primary_topic, and title keywords
        against explicit topic affinities and categorized taxonomy.
        """
        # Collect all candidate topic terms
        candidate_topics: List[str] = []
        if story.get("topics") and isinstance(story["topics"], list):
            candidate_topics.extend(story["topics"])
        if story.get("tags") and isinstance(story["tags"], list):
            candidate_topics.extend(story["tags"])
        if story.get("primary_topic"):
            candidate_topics.append(story["primary_topic"])

        title_text = (story.get("title") or "") + " " + (story.get("ai_title") or "")
        summary_text = (story.get("summary") or "") + " " + (story.get("ai_summary") or "")
        full_text = (title_text + " " + summary_text).lower()


        best_score = 0.0
        best_topic: Optional[str] = None

        # 1. Match against learned/explicit user topic affinities
        for topic in candidate_topics:
            norm_topic = topic.strip().lower()
            if norm_topic in topic_affinities:
                aff = float(topic_affinities[norm_topic])
                if aff > best_score:
                    best_score = aff
                    best_topic = topic

        # 2. Check candidate topics against taxonomy interest weights
        for cat, keywords in TOPIC_TAXONOMY.items():
            cat_weight = float(interest_weights.get(cat, self.default_interest_weights.get(cat, 0.40)))
            for topic in candidate_topics:
                norm_topic = topic.strip().lower()
                for kw in keywords:
                    if kw == norm_topic or (len(kw) > 3 and kw in norm_topic):
                        effective = cat_weight
                        if effective > best_score:
                            best_score = effective
                            best_topic = topic

        # 3. Check full story text for high-interest domain keywords if candidates yielded low score
        if best_score < 0.60:
            for cat, keywords in TOPIC_TAXONOMY.items():
                cat_weight = float(interest_weights.get(cat, self.default_interest_weights.get(cat, 0.40)))
                for kw in keywords:
                    if _has_keyword(full_text, kw):
                        # Slight dampening for pure text match vs structured topic
                        effective = cat_weight * 0.90
                        if effective > best_score:
                            best_score = effective
                            best_topic = kw.capitalize()

        # If no topics found at all, fall back to category score baseline
        if best_score <= 0.0:
            raw_cat = story.get("category", "technology")
            canon_cat = self.normalize_category(raw_cat)
            fallback_score = float(interest_weights.get(canon_cat, 0.40)) * 0.85
            return min(1.0, max(0.0, fallback_score)), None

        return min(1.0, max(0.0, best_score)), best_topic

    def compute_entity_match(
        self,
        story: Dict[str, Any],
        entity_affinities: Dict[str, float]
    ) -> Tuple[float, Optional[str]]:
        """
        Computes entity match signal (0.0 - 1.0).
        Evaluates story entities against user entity affinities and known tech entities.
        """
        story_entities = story.get("entities") or []
        entity_names: List[str] = []
        for e in story_entities:
            if isinstance(e, dict) and e.get("name"):
                entity_names.append(e["name"])
            elif isinstance(e, str):
                entity_names.append(e)

        best_score = 0.0
        best_entity: Optional[str] = None

        # 1. Match against learned/explicit entity affinities
        for name in entity_names:
            norm_name = name.strip().lower()
            if norm_name in entity_affinities:
                score = float(entity_affinities[norm_name])
                if score > best_score:
                    best_score = score
                    best_entity = name

        # 2. Match against known engineering/tech entities
        for name in entity_names:
            norm_name = name.strip().lower()
            if norm_name in KNOWN_TECH_ENTITIES:
                score = KNOWN_TECH_ENTITIES[norm_name]
                if score > best_score:
                    best_score = score
                    best_entity = name

        # Also check title if entities list was empty
        if not entity_names:
            title_lower = ((story.get("title") or "") + " " + (story.get("ai_title") or "")).lower()
            for known_ent, score in KNOWN_TECH_ENTITIES.items():

                if _has_keyword(title_lower, known_ent):
                    if score > best_score:
                        best_score = score * 0.90
                        best_entity = known_ent.capitalize()

        return min(1.0, max(0.0, best_score)), best_entity

    def compute_behavioral_affinity(
        self,
        story: Dict[str, Any],
        profile: Dict[str, Any],
        category_match: float
    ) -> Tuple[float, Optional[str]]:
        """
        Computes behavioral affinity signal (0.0 - 1.0) learned from interaction history.
        If user has no interaction history, yields a neutral baseline.
        """
        topic_affinities = profile.get("topic_affinities") or {}
        raw_cat = story.get("category") or "technology"
        canon_cat = self.normalize_category(raw_cat)

        # Check if user has explicitly interacted with this category
        if canon_cat in topic_affinities:
            learned = float(topic_affinities[canon_cat])
            return min(1.0, max(0.0, learned)), f"Reading history in {canon_cat.capitalize()}"

        # Check if user interacted with any of the story's topics
        story_topics = story.get("topics") or []
        matched_learned: List[float] = []
        for top in story_topics:
            norm_top = top.strip().lower()
            if norm_top in topic_affinities:
                matched_learned.append(float(topic_affinities[norm_top]))

        if matched_learned:
            avg_learned = sum(matched_learned) / len(matched_learned)
            return min(1.0, max(0.0, avg_learned)), "Reading history on related topics"

        # Check saved stories count in this category
        saved_ids = profile.get("saved_story_ids") or []
        if story.get("id") in saved_ids:
            return 0.95, "Bookmarked story"

        # Neutral baseline for fresh/unengaged topics
        baseline = max(0.40, category_match * 0.70 + 0.15)
        return min(1.0, max(0.0, baseline)), None

    def compute_novelty(self, story: Dict[str, Any]) -> float:
        """
        Computes novelty / freshness signal (0.0 - 1.0).
        Stories published recently have higher novelty value.
        """
        pub_str = story.get("published_at") or story.get("created_at")
        if not pub_str:
            return 0.70

        try:
            # Parse ISO timestamp
            dt_clean = pub_str.replace("Z", "+00:00")
            dt = datetime.fromisoformat(dt_clean)
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=timezone.utc)
            now = datetime.now(timezone.utc)
            diff_hours = (now - dt).total_seconds() / 3600.0

            if diff_hours < 6:
                return 1.00
            elif diff_hours < 24:
                return 0.85
            elif diff_hours < 48:
                return 0.65
            elif diff_hours < 72:
                return 0.45
            else:
                return 0.25
        except Exception:
            return 0.70

    def compute_relevance(
        self,
        story: Dict[str, Any],
        profile: Optional[Dict[str, Any]] = None
    ) -> PersonalRelevanceBreakdown:
        """
        Computes the complete, deterministic Personal Relevance breakdown
        for a given story and user profile.
        """
        if profile is None:
            from backend.app.core.db_repository import db_repository
            profile = db_repository.get_user_preferences("default_user")

        interest_weights = dict(self.default_interest_weights)
        if profile.get("interest_weights"):
            interest_weights.update(profile["interest_weights"])

        topic_affinities = profile.get("topic_affinities") or {}
        entity_affinities = profile.get("entity_affinities") or {}

        # 1. Compute individual signals
        cat_score, canon_cat = self.compute_category_match(story, interest_weights)
        top_score, matched_topic = self.compute_topic_match(story, interest_weights, topic_affinities)
        ent_score, matched_entity = self.compute_entity_match(story, entity_affinities)
        beh_score, beh_desc = self.compute_behavioral_affinity(story, profile, cat_score)
        nov_score = self.compute_novelty(story)

        # 2. Weighted sum calculation
        w = self.weights
        raw_composite = (
            w.get("category_match", 0.25) * cat_score +
            w.get("topic_match", 0.35) * top_score +
            w.get("entity_match", 0.15) * ent_score +
            w.get("behavioral_affinity", 0.20) * beh_score +
            w.get("novelty", 0.05) * nov_score
        )

        final_score = int(round(min(1.0, max(0.0, raw_composite)) * 100))

        # 3. Generate structured explanations
        reasons: List[str] = []
        cat_display = canon_cat.replace("_", " ").title()
        if cat_score >= 0.75:
            reasons.append(f"Strong alignment with your interest in {cat_display} ({int(cat_score*100)}%)")
        elif cat_score >= 0.50:
            reasons.append(f"Matches your interest in {cat_display} ({int(cat_score*100)}%)")

        if matched_topic and top_score >= 0.70:
            reasons.append(f"Direct match on topic: {matched_topic}")

        if matched_entity and ent_score >= 0.60:
            reasons.append(f"Features prominent entity: {matched_entity}")

        if beh_desc:
            reasons.append(beh_desc)

        if nov_score >= 0.80:
            reasons.append("Recently published reporting")

        # 4. Generate user-facing editorial explanation (relevance_reason)
        editorial_reason: str
        if matched_topic and top_score >= 0.80:
            editorial_reason = f"Matches your high interest in {cat_display} and {matched_topic}."
        elif matched_entity and ent_score >= 0.75:
            editorial_reason = f"Recommended for coverage of {matched_entity} in {cat_display}."
        elif cat_score >= 0.80:
            editorial_reason = f"Matches your primary interest in {cat_display}."
        elif beh_desc:
            editorial_reason = f"Recommended based on your reading patterns in {cat_display}."
        else:
            editorial_reason = f"Curated for your general interest in {cat_display}."

        return PersonalRelevanceBreakdown(
            personal_relevance_score=final_score,
            category_match=round(cat_score, 4),
            topic_match=round(top_score, 4),
            entity_match=round(ent_score, 4),
            behavioral_affinity=round(beh_score, 4),
            novelty=round(nov_score, 4),
            reasons=reasons,
            relevance_reason=editorial_reason,
            relevance_version=self.version,
            calculated_at=datetime.utcnow().isoformat()
        )


personal_relevance_service = PersonalRelevanceService()
