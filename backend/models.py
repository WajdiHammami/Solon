from datetime import datetime
from typing import Optional

from pydantic import BaseModel


class Article(BaseModel):
    id: int
    title: str
    url: str
    source_name: str
    tag: Optional[str] = None
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
    newsapi_enabled: Optional[bool] = None



class SummarizeRequest(BaseModel):
    articles: list[Article]

class SummarizeResponse(BaseModel):
    summaries: list[str]
    synthesis: Optional[str] = None
    tags: Optional[dict[int, tuple[str, str]]] = None  # article_id -> (tag, explanation)