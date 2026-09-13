from datetime import datetime
from typing import Optional
from pydantic import BaseModel, Field

class SourceBase(BaseModel):
    id: str
    name: str
    domain: str
    reliability_score: float = Field(default=1.0, ge=0.0, le=1.0)
    is_active: bool = True

class SourceCreate(SourceBase):
    pass

class SourceResponse(SourceBase):
    created_at: Optional[datetime] = None

    class Config:
        from_attributes = True

class ArticleBase(BaseModel):
    title: str
    description: Optional[str] = None
    url: str
    author: Optional[str] = None
    published_at: datetime
    source_name: str
    source_domain: str

class ArticleCreate(ArticleBase):
    story_id: Optional[str] = None
    raw_content_hash: Optional[str] = None

class ArticleResponse(ArticleBase):
    id: str
    story_id: Optional[str] = None
    created_at: Optional[datetime] = None

    class Config:
        from_attributes = True
