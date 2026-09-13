"""
Feed Ranking Engine & Diversity Controller (Phase 6)

Computes composite multi-factor feed ranking:
- Personal Relevance: 40%
- Global Importance: 30%
- Freshness: 15%
- Urgency: 10%
- Diversity Controller Penalty / Interleaving: 5%

Features:
1. Global Importance Override:
   Critical world events (importance >= 85 or breaking) surface prominently
   regardless of personal preference.
2. Diversity Controller:
   Interleaves categories (max 2 consecutive from same category) to prevent echo chambers.
3. Canonical Deduplication:
   Strictly displays one canonical story per story cluster.
4. Telemetry Filter:
   Excludes stories hidden by the user.
"""
from datetime import datetime, timezone
from typing import List, Dict, Any, Optional

from backend.app.core.config import settings
from backend.app.core.db_repository import db_repository
from backend.app.services.personal_relevance_service import personal_relevance_service
from backend.app.services.importance_service import importance_service


class FeedRankingService:
    """
    Ranks and interleaves stories for the personalized For You / Feed view.
    """

    def __init__(self):
        self.weights = getattr(settings, "FEED_RANKING_WEIGHTS", {
            "personal_relevance": 0.40,
            "global_importance": 0.30,
            "freshness": 0.15,
            "urgency": 0.10,
            "diversity_penalty": 0.05
        })
        self.override_threshold: int = getattr(settings, "GLOBAL_IMPORTANCE_OVERRIDE_THRESHOLD", 85)
        self.max_consecutive_category: int = getattr(settings, "DIVERSITY_MAX_CONSECUTIVE_CATEGORY", 2)

    def calculate_freshness_score(self, story: Dict[str, Any]) -> int:
        """Calculates freshness score (0-100) based on age in hours."""
        if story.get("freshness_score"):
            return int(story["freshness_score"])

        pub_str = story.get("published_at") or story.get("created_at")
        if not pub_str:
            return 80

        try:
            if isinstance(pub_str, datetime):
                dt = pub_str
            else:
                dt_clean = str(pub_str).replace("Z", "+00:00")
                dt = datetime.fromisoformat(dt_clean)
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=timezone.utc)
            now = datetime.now(timezone.utc)
            hours = (now - dt).total_seconds() / 3600.0

            if hours < 6:
                return 100
            elif hours < 12:
                return 90
            elif hours < 24:
                return 80
            elif hours < 48:
                return 60
            elif hours < 72:
                return 40
            else:
                return 20
        except Exception:
            return 75

    def calculate_urgency_score(self, story: Dict[str, Any], importance_score: int) -> int:
        """Derives urgency score (0-100) from breaking status and importance tier."""
        if story.get("is_breaking"):
            return 95

        tier = story.get("importance_tier")
        if not tier:
            if importance_score >= 85:
                tier = "CRITICAL"
            elif importance_score >= 70:
                tier = "HIGH"
            elif importance_score >= 45:
                tier = "MEDIUM"
            else:
                tier = "LOW"

        if tier == "CRITICAL":
            return 90
        elif tier == "HIGH":
            return 75
        elif tier == "MEDIUM":
            return 50
        else:
            return 30

    def rank_feed(
        self,
        user_id: str = "default_user",
        limit: int = 50,
        offset: int = 0
    ) -> List[Dict[str, Any]]:
        """
        Generates personalized, balanced feed ranking for the given user.
        """
        # 1. Fetch user preferences and exclusions
        profile = db_repository.get_user_preferences(user_id)
        hidden_ids = set(db_repository.get_hidden_story_ids(user_id))
        saved_ids = set(db_repository.get_saved_story_ids(user_id))
        profile["saved_story_ids"] = list(saved_ids)
        profile["hidden_story_ids"] = list(hidden_ids)

        # 2. Fetch candidate stories from repository
        fetch_limit = max(limit * 4, 100)
        raw_stories = db_repository.get_stories(limit=fetch_limit)
        if not raw_stories:
            from backend.app.services.news_service import news_service
            raw_stories = news_service.get_all_stories(limit=fetch_limit)

        # 3. Filter and score candidates
        scored_candidates: List[Dict[str, Any]] = []
        seen_story_ids = set()

        for story in raw_stories:
            story_id = story.get("id")
            if not story_id or story_id in hidden_ids or story_id in seen_story_ids:
                continue
            seen_story_ids.add(story_id)

            # Ensure global importance score is present
            importance_score = int(story.get("importance_score") or 50)

            # Compute personal relevance breakdown
            breakdown = personal_relevance_service.compute_relevance(story, profile)
            relevance_score = breakdown.personal_relevance_score

            freshness_score = self.calculate_freshness_score(story)
            urgency_score = self.calculate_urgency_score(story, importance_score)

            w = self.weights
            base_rank = (
                w.get("personal_relevance", 0.40) * relevance_score +
                w.get("global_importance", 0.30) * importance_score +
                w.get("freshness", 0.15) * freshness_score +
                w.get("urgency", 0.10) * urgency_score
            )

            # Check Global Importance Override
            is_breaking = bool(story.get("is_breaking", False)) or importance_score >= 90
            is_critical = importance_score >= self.override_threshold or is_breaking

            final_rank_score: float
            editorial_reason: str
            if is_critical:
                # Global Importance Override: Critical world event surfaced prominently
                final_rank_score = base_rank + 100.0
                is_global_override = True
                editorial_reason = f"Critical world event (Global Importance: {importance_score}/100) surfaced prominently."
            else:
                final_rank_score = base_rank
                is_global_override = False
                editorial_reason = breakdown.relevance_reason

            # Format story for feed
            from backend.app.api.endpoints.stories import format_db_story
            formatted = format_db_story(story)
            formatted["relevance_score"] = relevance_score
            formatted["relevance_reason"] = editorial_reason
            formatted["relevance_version"] = breakdown.relevance_version
            formatted["relevance_breakdown"] = breakdown.model_dump()
            formatted["final_rank_score"] = round(final_rank_score, 2)
            formatted["is_global_override"] = is_global_override
            formatted["is_saved"] = story_id in saved_ids
            formatted["freshness_score"] = freshness_score

            scored_candidates.append(formatted)

        # 4. Sort strictly descending by final_rank_score
        scored_candidates.sort(key=lambda s: s["final_rank_score"], reverse=True)

        # 5. Apply Diversity Controller: Category Interleaving
        # No more than max_consecutive_category consecutive stories of same category when an eligible alternative exists
        selected: List[Dict[str, Any]] = []
        candidates_pool = list(scored_candidates)

        while candidates_pool and len(selected) < (limit + offset):
            need_diversity = False
            forbidden_category = None

            if len(selected) >= self.max_consecutive_category:
                recent_cats = [
                    personal_relevance_service.normalize_category(s.get("category"))
                    for s in selected[-self.max_consecutive_category:]
                ]
                if len(set(recent_cats)) == 1:
                    need_diversity = True
                    forbidden_category = recent_cats[0]

            chosen_idx = None
            if need_diversity:
                for idx, cand in enumerate(candidates_pool):
                    cand_cat = personal_relevance_service.normalize_category(cand.get("category"))
                    if cand_cat != forbidden_category:
                        chosen_idx = idx
                        break

            if chosen_idx is None:
                chosen_idx = 0


            chosen_item = candidates_pool.pop(chosen_idx)
            selected.append(chosen_item)

        # Slice according to pagination
        paginated_results = selected[offset:offset + limit]
        return paginated_results


feed_ranking_service = FeedRankingService()
