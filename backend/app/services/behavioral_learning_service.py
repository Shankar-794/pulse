"""
Behavioral Learning Service (Phase 6)

Processes user telemetry interactions (read, save, unsave, hide, share)
and updates user topic and entity affinities smoothly with bounded clamping [0.0, 1.0].
Guarantees gradual accumulation so no single interaction drastically rewrites the profile.
"""
from typing import Dict, Any, Optional, List
from datetime import datetime

from backend.app.core.db_repository import db_repository
from backend.app.services.personal_relevance_service import personal_relevance_service


INTERACTION_DELTAS: Dict[str, float] = {
    "read": 0.02,
    "save": 0.08,
    "unsave": -0.08,
    "hide": -0.15,
    "share": 0.05,
    "view": 0.005
}


class BehavioralLearningService:
    """
    Learns topic, entity, and category preferences from user actions.
    """

    def __init__(self):
        self.deltas: Dict[str, float] = INTERACTION_DELTAS

    def process_interaction(
        self,
        user_id: str,
        story_id: str,
        interaction_type: str,
        metadata: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Records interaction telemetry and adapts user's learned affinities.
        """
        metadata = metadata or {}
        # 1. Record raw interaction in repository
        record = db_repository.record_interaction(
            user_id=user_id,
            story_id=story_id,
            interaction_type=interaction_type,
            metadata=metadata
        )

        # 2. Retrieve story context to extract topics, category, and entities
        story = db_repository.get_story(story_id)
        if not story:
            art = db_repository.get_article_by_id(story_id)
            if art:
                from backend.app.api.endpoints.stories import article_to_story
                story = article_to_story(art)
        if not story:
            from backend.app.services.news_service import news_service
            story = news_service.get_story_by_id(story_id)

        # 3. Retrieve user profile
        prefs = db_repository.get_user_preferences(user_id)
        topic_affinities: Dict[str, float] = dict(prefs.get("topic_affinities") or {})
        entity_affinities: Dict[str, float] = dict(prefs.get("entity_affinities") or {})
        interest_weights: Dict[str, float] = dict(prefs.get("interest_weights") or {})

        delta = self.deltas.get(interaction_type.lower(), 0.01)

        # 4. Extract story attributes
        if story:
            cat = story.get("category") or story.get("ai_category") or "technology"
            canon_cat = personal_relevance_service.normalize_category(cat)

            # Extract and deduplicate topics (excluding category to prevent double application)
            raw_topics: List[str] = []
            if story.get("topics"):
                raw_topics.extend(story["topics"])
            if story.get("tags"):
                raw_topics.extend(story["tags"])
            if story.get("primary_topic"):
                raw_topics.append(story["primary_topic"])

            topics: List[str] = []
            seen_topics = set()
            for t in raw_topics:
                norm_t = t.strip().lower()
                if norm_t and norm_t != canon_cat and norm_t not in seen_topics:
                    seen_topics.add(norm_t)
                    topics.append(norm_t)

            # Extract and deduplicate entities
            raw_entities = story.get("entities") or []
            entity_names: List[str] = []
            seen_entities = set()
            for e in raw_entities:
                name = e.get("name") if isinstance(e, dict) else e
                if name:
                    norm_e = name.strip().lower()
                    if norm_e not in seen_entities:
                        seen_entities.add(norm_e)
                        entity_names.append(norm_e)

            # A. Update Category Affinity in topic_affinities
            default_cat_baseline = interest_weights.get(canon_cat, 0.50)
            current_cat_aff = topic_affinities.get(canon_cat, default_cat_baseline)
            new_cat_aff = min(1.0, max(0.0, current_cat_aff + delta))
            topic_affinities[canon_cat] = round(new_cat_aff, 4)

            # B. Update Topic Affinities
            for norm_t in topics:
                current_top_aff = topic_affinities.get(norm_t, default_cat_baseline)
                new_top_aff = min(1.0, max(0.0, current_top_aff + delta))
                topic_affinities[norm_t] = round(new_top_aff, 4)

            # C. Update Entity Affinities (for save, unsave, share, read)
            if interaction_type in ("save", "unsave", "share", "read"):
                for norm_ent in entity_names:
                    current_ent_aff = entity_affinities.get(norm_ent, 0.50)
                    new_ent_aff = min(1.0, max(0.0, current_ent_aff + delta))
                    entity_affinities[norm_ent] = round(new_ent_aff, 4)


        # 5. Persist updated profile
        prefs["topic_affinities"] = topic_affinities
        prefs["entity_affinities"] = entity_affinities
        db_repository.save_user_preferences(user_id, prefs)

        return {
            "status": "success",
            "interaction_id": record["id"],
            "interaction_type": interaction_type,
            "story_id": story_id,
            "topic_affinities_count": len(topic_affinities),
            "entity_affinities_count": len(entity_affinities)
        }


behavioral_learning_service = BehavioralLearningService()
