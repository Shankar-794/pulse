from fastapi import APIRouter, Depends
from typing import Dict, Any, Optional

from backend.app.core.db_repository import db_repository
from backend.app.services.news_service import news_service
from backend.app.services.behavioral_learning_service import behavioral_learning_service
from backend.app.services.personal_relevance_service import personal_relevance_service
from backend.app.api.deps import get_optional_user
from backend.app.schemas.preferences import (
    UserPreferenceResponse,
    UserPreferenceUpdate,
    UserInteractionCreate,
    UserInterestProfile
)

router = APIRouter()


@router.get("/preferences", response_model=UserPreferenceResponse, tags=["preferences"])
async def get_user_preferences(user: Optional[Dict[str, Any]] = Depends(get_optional_user)):
    """
    Retrieve personalization profile, interest matrix, and feed thresholds.
    Scoped to the authenticated user or default fallback.
    """
    user_id = user["id"] if user else "default_user"
    prefs = db_repository.get_user_preferences(user_id)
    if user_id == "default_user":
        news_service.update_preferences(prefs)
    return prefs


@router.put("/preferences", response_model=UserPreferenceResponse, tags=["preferences"])
async def update_user_preferences(
    updates: UserPreferenceUpdate,
    user: Optional[Dict[str, Any]] = Depends(get_optional_user)
):
    """
    Update user interest matrix, breaking news sensitivity, or minimum importance threshold.
    Scoped to the authenticated user.
    """
    user_id = user["id"] if user else "default_user"
    data = updates.model_dump(exclude_unset=True)
    current = db_repository.get_user_preferences(user_id)
    current.update(data)
    db_repository.save_user_preferences(user_id, current)
    if user_id == "default_user":
        news_service.update_preferences(data)
    return current


@router.post("/interactions", tags=["preferences"])
async def record_user_interaction(
    interaction: UserInteractionCreate,
    user: Optional[Dict[str, Any]] = Depends(get_optional_user)
):
    """
    Record user telemetry: story save, hide, view, or read actions to refine ranking.
    Scoped to the authenticated user.
    """
    user_id = user["id"] if user else "default_user"
    result = behavioral_learning_service.process_interaction(
        user_id=user_id,
        story_id=interaction.story_id,
        interaction_type=interaction.interaction_type,
        metadata=interaction.metadata
    )
    news_service.record_interaction(
        story_id=interaction.story_id,
        interaction_type=interaction.interaction_type,
        metadata=interaction.metadata
    )
    return {
        "status": "success",
        "interaction_id": result["interaction_id"],
        "recorded_type": result["interaction_type"],
        "user_id": user_id
    }


@router.get("/personalization/profile", response_model=UserInterestProfile, tags=["personalization"])
async def get_personalization_profile(user: Optional[Dict[str, Any]] = Depends(get_optional_user)):
    """
    Retrieve detailed interest weights, learned topic affinities, entity affinities,
    and active saved/hidden story lists for the current user.
    """
    user_id = user["id"] if user else "default_user"
    prefs = db_repository.get_user_preferences(user_id)
    saved_ids = db_repository.get_saved_story_ids(user_id)
    hidden_ids = db_repository.get_hidden_story_ids(user_id)

    return UserInterestProfile(
        user_id=user_id,
        interest_weights=prefs.get("interest_weights") or {},
        topic_affinities=prefs.get("topic_affinities") or {},
        entity_affinities=prefs.get("entity_affinities") or {},
        saved_story_ids=saved_ids,
        hidden_story_ids=hidden_ids
    )


@router.post("/personalization/recalculate", tags=["personalization"])
async def recalculate_all_personal_relevance(user: Optional[Dict[str, Any]] = Depends(get_optional_user)):
    """
    Batch recomputes personal relevance scores and reasons for all stored stories
    using the active user interest profile and affinities.
    """
    user_id = user["id"] if user else "default_user"
    profile = db_repository.get_user_preferences(user_id)
    stories = db_repository.get_stories(limit=1000)
    updated_count = 0

    for story in stories:
        breakdown = personal_relevance_service.compute_relevance(story, profile)
        db_repository.save_story_relevance(
            story_id=story["id"],
            relevance_score=breakdown.personal_relevance_score,
            relevance_reason=breakdown.relevance_reason,
            version=breakdown.relevance_version
        )
        updated_count += 1

    return {
        "status": "success",
        "user_id": user_id,
        "stories_updated": updated_count,
        "relevance_version": personal_relevance_service.version
    }
