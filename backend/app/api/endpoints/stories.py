from fastapi import APIRouter, HTTPException, Query, Depends
from typing import List, Optional, Dict, Any, Set
from datetime import datetime, timezone

from backend.app.core.db_repository import db_repository
from backend.app.services.news_service import news_service
from backend.app.services.story_analysis_service import story_analysis_service
from backend.app.services.importance_service import importance_service
from backend.app.services.personal_relevance_service import personal_relevance_service
from backend.app.services.feed_ranking_service import feed_ranking_service
from backend.app.services.behavioral_learning_service import behavioral_learning_service
from backend.app.schemas.preferences import PersonalRelevanceBreakdown
from backend.app.schemas.story import StoryListResponse, StoryResponse
from backend.app.api.deps import get_current_user, get_optional_user

from backend.app.services.story_evolution_service import story_evolution_service

router = APIRouter()



def _to_iso(val: Any) -> str:
    if val is None:
        return ""
    if isinstance(val, datetime):
        return val.isoformat()
    return str(val)


def format_db_story(story: Dict[str, Any], saved_ids: Optional[Set[str]] = None) -> Dict[str, Any]:
    """
    Transforms a database Story cluster with linked articles and AI intelligence into full API StoryResponse.
    """
    raw_articles = story.get("articles") or []
    formatted_articles = [
        {
            "id": a.get("id"),
            "story_id": story.get("id"),
            "title": a.get("title", ""),
            "description": a.get("description", ""),
            "url": a.get("url") or a.get("canonical_url", ""),
            "author": a.get("author"),
            "published_at": _to_iso(a.get("published_at")),
            "source_name": a.get("source_name", "News Source"),
            "source_domain": a.get("source_domain", ""),
            "reliability_score": 0.95
        }
        for a in raw_articles
    ]

    source_names = list(dict.fromkeys(a.get("source_name") for a in raw_articles if a.get("source_name")))
    source_count = max(len(source_names), story.get("source_count", 1))

    # Build timeline of reporting events (use persistent grounded story_events if available)
    db_events = db_repository.get_story_events(story["id"]) if story.get("id") else []
    if db_events:
        timeline = [
            {
                "time": (_to_iso(e.get("occurred_at") or e.get("detected_at")) or "")[:16].replace("T", " "),
                "title": e.get("title", ""),
                "description": e.get("summary", ""),
                "event_type": e.get("event_type", "UPDATE"),
                "article_ids": e.get("article_ids", [])
            }
            for e in db_events
        ]
    elif story.get("timeline"):
        timeline = story["timeline"]
    else:
        timeline = []
        for a in sorted(raw_articles, key=lambda x: _to_iso(x.get("published_at"))):
            pub_str = _to_iso(a.get("published_at"))
            time_label = pub_str[:16].replace("T", " ") if pub_str else "Recent"
            timeline.append({
                "time": time_label,
                "title": f"Reported by {a.get('source_name', 'Wire')}",
                "description": a.get("title", ""),
                "event_type": "UPDATE",
                "article_ids": [str(a.get("id"))] if a.get("id") else []
            })

    # Named entities: use AI structured entities if available, otherwise derive from source/category
    raw_entities = story.get("entities")
    if raw_entities and isinstance(raw_entities, list) and len(raw_entities) > 0:
        entities = [
            {"name": e.get("name", ""), "category": e.get("type", "organization")}
            for e in raw_entities if isinstance(e, dict) and e.get("name")
        ]
    else:
        entities = [{"name": s, "category": "organization"} for s in source_names]
        if story.get("category"):
            entities.append({"name": story["category"].capitalize(), "category": "concept"})
        if story.get("primary_topic"):
            entities.append({"name": story["primary_topic"], "category": "technology"})

    # Tags / Topics: use AI topics if available
    ai_topics = story.get("topics") or []
    if ai_topics and isinstance(ai_topics, list) and len(ai_topics) > 0:
        tags = list(ai_topics)
    else:
        tags = [story.get("category", "Technology").capitalize()]
        if story.get("primary_topic") and story.get("primary_topic") != story.get("category"):
            tags.append(story["primary_topic"])

    importance = int(story.get("importance_score") or 50)
    is_breaking = (
        story.get("breaking_level") == "BREAKING"
        if story.get("breaking_level") is not None
        else importance >= 90
    )
    is_analyzed = bool(story.get("analyzed_at"))
    tier = story.get("importance_tier") or (
        "CRITICAL" if importance >= 85
        else "HIGH" if importance >= 70
        else "MEDIUM" if importance >= 45
        else "LOW"
    )

    breaking_score = int(story.get("breaking_score") if story.get("breaking_score") is not None else (85 if is_breaking else 30))
    breaking_level = story.get("breaking_level") or ("BREAKING" if is_breaking else "STABLE")
    story_status = story.get("story_status") or "ACTIVE"
    latest_dev = story.get("latest_development") or story.get("why_it_matters") or story.get("summary", "")
    latest_up = story.get("latest_updated_at") or story.get("last_published_at") or story.get("updated_at")
    update_cnt = int(story.get("update_count") if story.get("update_count") is not None else max(0, (len(raw_articles) or story.get("article_count", 1)) - 1))
    perspectives = story.get("perspectives") or []

    return {
        "id": story["id"],
        "story_id": story["id"],
        "title": story.get("ai_title") or story.get("title", ""),
        "summary": story.get("ai_summary") or story.get("summary", ""),
        "why_it_matters": story.get("why_it_matters") or f"Synthesized from {source_count} reporting source(s).",
        "category": story.get("category", "Technology"),
        "primary_topic": story.get("primary_topic", "Technology"),
        "importance_score": importance,
        "importance_tier": tier,
        "importance_explanation": story.get("importance_explanation"),
        "importance_version": story.get("importance_version") or "v1",
        "importance_breakdown": story.get("importance_breakdown"),
        "relevance_score": int(story.get("relevance_score") or 60),
        "relevance_reason": story.get("relevance_reason") or f"Synthesized story with {source_count} source perspective(s).",
        "relevance_version": story.get("relevance_version") or "v1",
        "relevance_breakdown": story.get("relevance_breakdown"),
        "final_rank_score": story.get("final_rank_score"),
        "is_global_override": story.get("is_global_override", False),
        "freshness_score": int(story.get("freshness_score") or 95),
        "source_count": source_count,
        "article_count": len(raw_articles) or story.get("article_count", 1),
        "is_breaking": is_breaking,
        "is_saved": (story.get("id") in saved_ids) if saved_ids is not None else bool(story.get("is_saved", False)),
        "analyzed": is_analyzed,
        "ai_title": story.get("ai_title"),
        "ai_summary": story.get("ai_summary"),
        "ai_category": story.get("ai_category"),
        "analysis_confidence": story.get("analysis_confidence"),
        "analyzed_at": story.get("analyzed_at"),
        "analysis_version": story.get("analysis_version"),
        "topics": tags,
        "tags": tags,
        "story_status": story_status,
        "breaking_score": breaking_score,
        "breaking_level": breaking_level,
        "latest_development": latest_dev,
        "latest_updated_at": _to_iso(latest_up) if latest_up else None,
        "update_count": update_cnt,
        "perspectives": perspectives,
        "evolution_version": story.get("evolution_version") or "v1",
        "created_at": _to_iso(story.get("created_at")) or datetime.utcnow().isoformat(),
        "updated_at": _to_iso(story.get("updated_at")) if story.get("updated_at") else None,
        "timeline": timeline,
        "entities": entities,
        "claims": story.get("claims") or [],
        "articles": formatted_articles
    }




def article_to_story(art: Dict[str, Any], saved_ids: Optional[Set[str]] = None) -> Dict[str, Any]:
    """
    Transforms a single unclustered article into a story representation.
    """
    category = art.get("category", "technology")
    source_name = art.get("source_name", "News Source")
    title = art.get("title", "")
    summary = art.get("description", "")
    published_at = _to_iso(art.get("published_at")) or datetime.utcnow().isoformat()

    base_importance = 50
    lower_title = title.lower()
    critical_keywords = ["zero-day", "vulnerability", "cve", "breach", "exploit", "outage", "critical"]
    high_keywords = ["breakthrough", "launch", "release", "benchmark", "chip", "quantum", "court", "ai"]

    if any(k in lower_title for k in critical_keywords):
        base_importance = 94
    elif any(k in lower_title for k in high_keywords):
        base_importance = 87

    is_breaking = base_importance >= 90
    relevance_score = 80
    if category in ("technology", "ai", "cybersecurity", "space", "science"):
        relevance_score = 92

    tags = [category.capitalize()]
    if art.get("primary_topic"):
        tags.append(art["primary_topic"])

    tier = (
        "CRITICAL" if base_importance >= 85
        else "HIGH" if base_importance >= 70
        else "MEDIUM" if base_importance >= 45
        else "LOW"
    )

    return {
        "id": art["id"],
        "story_id": art["id"],
        "title": title,
        "summary": summary,
        "why_it_matters": f"Real-time intelligence report ingested from {source_name}. Relevant to your {category} technical stream.",
        "category": category,
        "primary_topic": art.get("primary_topic", category.capitalize()),
        "importance_score": base_importance,
        "importance_tier": tier,
        "importance_explanation": f"Real-time importance signal from {source_name} reporting.",
        "importance_version": "v1",
        "importance_breakdown": None,
        "relevance_score": relevance_score,
        "freshness_score": 95,
        "source_count": 1,
        "article_count": 1,
        "is_breaking": is_breaking,
        "is_saved": (art.get("id") in saved_ids) if saved_ids is not None else bool(art.get("is_saved", False)),
        "story_status": "ACTIVE",
        "breaking_score": 85 if is_breaking else 30,
        "breaking_level": "BREAKING" if is_breaking else "STABLE",
        "latest_development": summary or title,
        "latest_updated_at": published_at,
        "update_count": 0,
        "perspectives": [],
        "evolution_version": "v1",
        "relevance_reason": f"Real-time ingested report from {source_name} matching {category} interests.",
        "tags": tags,
        "created_at": published_at,
        "updated_at": published_at,
        "timeline": [
            {
                "time": published_at[:16].replace("T", " ") if published_at else "Recent",
                "title": "Article Published",
                "description": f"Published by {source_name}."
            }
        ],
        "entities": [
            {"name": source_name, "category": "organization"},
            {"name": category.capitalize(), "category": "concept"}
        ],
        "articles": [
            {
                "id": art["id"],
                "story_id": art.get("story_id"),
                "title": title,
                "description": summary,
                "url": art.get("url", art.get("canonical_url", "")),
                "author": art.get("author"),
                "published_at": published_at,
                "source_name": source_name,
                "source_domain": art.get("source_domain", ""),
                "reliability_score": 0.95
            }
        ]
    }


@router.get("/stories/saved", tags=["stories", "saved"])
async def get_saved_stories(
    user: Optional[Dict[str, Any]] = Depends(get_optional_user)
):
    """
    Retrieve all stories saved by the authenticated user.
    Returns empty list if unauthenticated or no stories saved.
    """
    if not user:
        return {
            "total": 0,
            "items": []
        }
    saved_stories = db_repository.get_saved_stories(user["id"])
    saved_ids = set(db_repository.get_saved_story_ids(user["id"]))
    formatted = [format_db_story(s, saved_ids=saved_ids) for s in saved_stories]
    return {
        "total": len(formatted),
        "items": formatted
    }


@router.post("/stories/{story_id}/save", tags=["stories", "saved"])
async def save_story(
    story_id: str,
    user: Dict[str, Any] = Depends(get_current_user)
):
    """
    Saves a story for the authenticated user and records a behavioral interaction.
    """
    user_id = user["id"]
    db_repository.save_story(user_id, story_id)
    behavioral_learning_service.process_interaction(
        user_id=user_id,
        story_id=story_id,
        interaction_type="save",
        metadata={"timestamp": datetime.now(timezone.utc).isoformat()}
    )
    return {
        "status": "success",
        "story_id": story_id,
        "is_saved": True,
        "user_id": user_id
    }


@router.delete("/stories/{story_id}/save", tags=["stories", "saved"])
async def unsave_story(
    story_id: str,
    user: Dict[str, Any] = Depends(get_current_user)
):
    """
    Removes a story from the authenticated user's saved stories list.
    """
    user_id = user["id"]
    db_repository.unsave_story(user_id, story_id)
    return {
        "status": "success",
        "story_id": story_id,
        "is_saved": False,
        "user_id": user_id
    }


@router.get("/feed", response_model=StoryListResponse, tags=["feed", "stories"])
async def get_personalized_feed(
    limit: int = Query(50, ge=1, le=100, description="Max stories to return"),
    offset: int = Query(0, ge=0, description="Stories offset for pagination"),
    user_id: Optional[str] = Query(None, description="Target user identifier"),
    user: Optional[Dict[str, Any]] = Depends(get_optional_user)
):
    """
    Returns personalized ranked feed balancing personal relevance, global importance,
    freshness, urgency, and category diversity interleaving.
    """
    effective_user_id = user["id"] if user else (user_id or "default_user")
    ranked_stories = feed_ranking_service.rank_feed(user_id=effective_user_id, limit=limit, offset=offset)
    saved_ids = set(db_repository.get_saved_story_ids(effective_user_id)) if user else set()
    for s in ranked_stories:
        if isinstance(s, dict):
            s["is_saved"] = s.get("id") in saved_ids
        elif hasattr(s, "is_saved"):
            s.is_saved = s.id in saved_ids
    return {
        "total": len(ranked_stories),
        "items": ranked_stories
    }


@router.get("/stories", tags=["stories"])
async def get_stories(
    category: Optional[str] = Query(None, description="Filter by category e.g. 'ai', 'technology', 'world', 'business', 'economy'"),
    topic: Optional[str] = Query(None, description="Filter by topic"),
    section: Optional[str] = Query(None, description="Filter by feed section: 'breaking', 'important'"),
    search: Optional[str] = Query(None, description="Search keyword"),
    min_sources: Optional[int] = Query(1, ge=1, description="Minimum number of unique sources"),
    min_importance: Optional[int] = Query(None, ge=0, le=100),
    use_demo_fallback: bool = Query(False, description="Explicitly use mock fallback if DB empty"),
    user: Optional[Dict[str, Any]] = Depends(get_optional_user)
):
    """
    Retrieve news stories.
    Surfaces real clustered stories from the database.
    Falls back gracefully to individual articles or mock service if not yet clustered.
    """
    total_articles = db_repository.get_total_count()
    total_stories = db_repository.get_total_story_count()

    effective_user_id = user["id"] if user else "default_user"
    saved_ids = set(db_repository.get_saved_story_ids(effective_user_id)) if user else set()

    # 1. If DB is completely empty (no articles and no stories)
    if total_articles == 0 and total_stories == 0 and not use_demo_fallback:
        return {
            "total": 0,
            "items": [],
            "is_empty": True,
            "message": "No news articles ingested yet. Trigger an ingestion cycle via POST /api/ingestion/run or the UI 'Sync Sources' button."
        }

    if total_articles == 0 and total_stories == 0 and use_demo_fallback:
        items = news_service.get_all_stories(
            category=category,
            topic=topic,
            section=section,
            search=search,
            min_importance=min_importance
        )
        for it in items:
            it["is_saved"] = it.get("id") in saved_ids
        return {
            "total": len(items),
            "items": items,
            "is_demo_fallback": True
        }

    # 2. If stories table has clustered stories, serve them!
    if total_stories > 0:
        raw_stories = db_repository.get_stories(
            category=category,
            min_sources=min_sources or 1,
            limit=100
        )
        stories = [format_db_story(s, saved_ids=saved_ids) for s in raw_stories]
    else:
        # Fallback to unclustered articles
        real_articles = db_repository.get_articles(
            category=category,
            search=search,
            limit=100
        )
        stories = [article_to_story(art, saved_ids=saved_ids) for art in real_articles]

    # Apply search filter if provided
    if search:
        search_lower = search.lower()
        stories = [
            s for s in stories
            if search_lower in s["title"].lower() or search_lower in s["summary"].lower()
        ]

    # Apply section filters
    if section == "breaking":
        stories = [s for s in stories if s["is_breaking"]]
    elif section == "important":
        stories = [s for s in stories if s["importance_score"] >= 85]

    if min_importance is not None:
        stories = [s for s in stories if s["importance_score"] >= min_importance]

    return {
        "total": len(stories),
        "items": stories,
        "is_clustered": total_stories > 0,
        "is_real_data": True
    }


@router.get("/stories/{story_id}/relevance", response_model=PersonalRelevanceBreakdown, tags=["stories", "personalization"])
async def get_story_relevance_breakdown(
    story_id: str,
    user_id: Optional[str] = Query(None, description="Target user identifier"),
    user: Optional[Dict[str, Any]] = Depends(get_optional_user)
):
    """
    Provides grounded, deterministic breakdown and explanation of why this story
    was scored and ranked for the user.
    """
    story = db_repository.get_story(story_id)
    if not story:
        story = news_service.get_story_by_id(story_id)
    if not story:
        raise HTTPException(status_code=404, detail=f"Story with ID '{story_id}' not found")

    effective_user_id = user["id"] if user else (user_id or "default_user")
    profile = db_repository.get_user_preferences(effective_user_id)
    breakdown = personal_relevance_service.compute_relevance(story, profile)
    return breakdown


@router.get("/stories/{story_id}", tags=["stories"])
async def get_story(
    story_id: str,
    user: Optional[Dict[str, Any]] = Depends(get_optional_user)
):
    """
    Retrieve single story details (either from real clustered stories or fallback).
    """
    saved_ids = set(db_repository.get_saved_story_ids(user["id"])) if user else set()

    # 1. Check clustered stories table
    story = db_repository.get_story_by_id(story_id)
    if story:
        return format_db_story(story, saved_ids=saved_ids)

    # 2. Check individual articles table
    article = db_repository.get_article_by_id(story_id)
    if article:
        return article_to_story(article, saved_ids=saved_ids)

    # 3. Check mock service if it's a foundation story ID
    mock_story = news_service.get_story_by_id(story_id)
    if mock_story:
        mock_copy = dict(mock_story)
        mock_copy["is_saved"] = mock_story.get("id") in saved_ids
        return mock_copy

    raise HTTPException(status_code=404, detail=f"Story with ID '{story_id}' not found")



@router.post("/stories/{story_id}/analyze", tags=["stories"])
async def analyze_single_story(story_id: str):
    """
    Analyzes a specific story using AI story understanding.
    Generates synthesized summary, why it matters, structured entities, and topic tags.
    """
    analysis = story_analysis_service.analyze_story_by_id(story_id)
    if not analysis:
        raise HTTPException(status_code=404, detail=f"Story with ID '{story_id}' not found")

    updated_story = db_repository.get_story_by_id(story_id)
    return format_db_story(updated_story)


@router.post("/stories/analyze", tags=["stories"])
async def analyze_batch_stories(
    limit: int = Query(10, ge=1, le=50, description="Max unanalyzed stories to process")
):
    """
    Batch analyzes unanalyzed stories up to the specified limit.
    """
    result = story_analysis_service.analyze_batch(limit=limit)
    return result


@router.post("/stories/{story_id}/importance", tags=["stories"])
async def calculate_story_importance(story_id: str):
    """
    Calculates deterministic Global Importance for a specific story.
    Computes signals, evaluates weights, assigns tier, and stores grounded explanation.
    """
    breakdown = importance_service.calculate_story_importance(story_id)
    if not breakdown:
        raise HTTPException(status_code=404, detail=f"Story with ID '{story_id}' not found")

    updated_story = db_repository.get_story_by_id(story_id)
    return format_db_story(updated_story)


@router.post("/stories/importance", tags=["stories"])
async def calculate_batch_importance(
    limit: int = Query(20, ge=1, le=100, description="Max stories to calculate importance for")
):
    """
    Calculates deterministic Global Importance for a batch of stories.
    """
    result = importance_service.calculate_batch_importance(limit=limit)
    return result


@router.post("/stories/{story_id}/evolve", tags=["stories", "evolution"])
async def evolve_single_story(story_id: str):
    """
    Triggers deterministic story evolution, lifecycle state assessment,
    breaking score calculation, and timeline event synthesis for a single story.
    """
    updated_story = story_evolution_service.evolve_story(story_id)
    if not updated_story:
        raise HTTPException(status_code=404, detail=f"Story with ID '{story_id}' not found")
    return format_db_story(updated_story)


@router.post("/stories/evolve", tags=["stories", "evolution"])
async def evolve_batch_stories(
    limit: int = Query(50, ge=1, le=200, description="Max stories to evaluate evolution for")
):
    """
    Batch evaluates story evolution, lifecycle, and breaking news scores across stories.
    """
    result = story_evolution_service.evolve_all_stories(limit=limit)
    return result


@router.get("/stories/{story_id}/timeline", tags=["stories", "evolution"])
async def get_story_timeline_events(story_id: str):
    """
    Retrieves full persistent chronological timeline events for a story.
    """
    story = db_repository.get_story_by_id(story_id)
    if not story:
        raise HTTPException(status_code=404, detail=f"Story with ID '{story_id}' not found")

    events = db_repository.get_story_events(story_id)
    if not events:
        articles = db_repository.get_articles_for_story(story_id)
        events = story_evolution_service.generate_timeline_events(story, articles)

    return {
        "story_id": story_id,
        "total_events": len(events),
        "events": events
    }

