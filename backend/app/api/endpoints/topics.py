from fastapi import APIRouter, HTTPException
from typing import List
from backend.app.services.news_service import news_service
from backend.app.schemas.topic import TopicResponse, TopicFollowRequest

router = APIRouter()

@router.get("/topics", response_model=List[TopicResponse], tags=["topics"])
async def get_all_topics():
    """
    Retrieve all knowledge domain topics tracked by Pulse.
    """
    return news_service.get_topics()

@router.post("/topics/{topic_id}/follow", response_model=TopicResponse, tags=["topics"])
async def toggle_topic_follow(topic_id: str, request: TopicFollowRequest):
    """
    Follow or unfollow an intelligence topic.
    """
    updated = news_service.update_topic_follow(topic_id, request.is_followed)
    if not updated:
        raise HTTPException(status_code=404, detail=f"Topic '{topic_id}' not found")
    return updated
