from fastapi import APIRouter
from backend.app.api.endpoints import health, news, stories, topics, preferences, ingestion, clustering, pipeline

api_router = APIRouter()

api_router.include_router(health.router)
api_router.include_router(pipeline.router)
api_router.include_router(ingestion.router)
api_router.include_router(clustering.router)
api_router.include_router(news.router)
api_router.include_router(stories.router)
api_router.include_router(topics.router)
api_router.include_router(preferences.router)

