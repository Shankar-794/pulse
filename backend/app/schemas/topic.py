from pydantic import BaseModel, Field

class TopicBase(BaseModel):
    name: str
    slug: str
    description: str
    category: str
    follower_count: int = Field(default=0)

class TopicResponse(TopicBase):
    id: str
    is_followed: bool = False

    class Config:
        from_attributes = True

class TopicFollowRequest(BaseModel):
    is_followed: bool
