from datetime import datetime
from typing import Optional

from pydantic import BaseModel, ValidationError


class Article(BaseModel):
    title: str
    url: str
    source_name: str
    published_at: datetime
    content: Optional[str] = None
    summary: Optional[str] = None


class Source(BaseModel):  # a news/information/articles source
    name: str
    url: str
    enabled: bool


class Profile(BaseModel):
    sources: list[Source]
    topics: list[str]
    newsapi_enabled: Optional[bool]
