from fastapi import APIRouter, HTTPException, Query
from typing import List, Optional
from backend.app.core.db_repository import db_repository
from backend.app.schemas.article import ArticleResponse

router = APIRouter()

@router.get("/news", tags=["news"])
async def get_all_articles(
    category: Optional[str] = Query(None, description="Filter by category e.g. 'technology', 'cybersecurity'"),
    source: Optional[str] = Query(None, description="Filter by source ID or domain name"),
    search: Optional[str] = Query(None, description="Search term in headline or description"),
    limit: int = Query(50, ge=1, le=200, description="Max number of articles to return"),
    offset: int = Query(0, ge=0, description="Pagination offset")
):
    """
    Retrieve real stored articles from the database, ordered by publication date (newest first).
    """
    items = db_repository.get_articles(
        category=category,
        source_id=source,
        search=search,
        limit=limit,
        offset=offset
    )
    total = db_repository.get_total_count(category=category)
    return {
        "total": total,
        "count": len(items),
        "items": items
    }

@router.get("/news/{article_id}", tags=["news"])
async def get_article_by_id(article_id: str):
    """
    Retrieve single stored article by its unique ID.
    """
    article = db_repository.get_article_by_id(article_id)
    if not article:
        raise HTTPException(status_code=404, detail=f"Article {article_id} not found")
    return article
