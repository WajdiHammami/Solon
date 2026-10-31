from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field


class Article(BaseModel):
    id: int
    title: str
    url: str
    source_name: str
    tag: Optional[str] = None
    published_at: datetime
    content: Optional[str] = None
    summary: Optional[str] = None


class BiasAssessment(BaseModel):
    label: str  # short tag, e.g. "Political"; "None" when no bias was found
    explanation: Optional[str] = None


class ArticleAnalysis(BaseModel):
    """LLM-derived analysis of one article; fields are ``None`` until computed."""

    summary: Optional[str] = None
    bias: Optional[BiasAssessment] = None

    @property
    def is_complete(self) -> bool:
        return self.summary is not None and self.bias is not None


class TaskFailure(BaseModel):
    """One analysis task that failed; the rest of the work still completes."""

    task: str  # "summarize" | "detect_bias" | "synthesize"
    error: str
    retryable: bool
    article_id: Optional[int] = None  # None for batch-level tasks (synthesize)


class ArticleResult(BaseModel):
    analysis: ArticleAnalysis
    failures: list[TaskFailure] = []


class BatchAnalysis(BaseModel):
    analyses: dict[int, ArticleAnalysis]  # article_id -> analysis
    synthesis: Optional[str] = None
    sources: list[int] = []  # ids of the articles the synthesis was built from
    failed: list[TaskFailure] = []
    skipped: list[int] = []  # ids dropped by the token budget, never attempted
    estimated_tokens: int = 0


class Source(BaseModel):  # a news/information/articles source
    name: str
    url: str
    enabled: bool


class Profile(BaseModel):
    sources: list[Source]
    topics: list[str]
    newsapi_enabled: Optional[bool] = None



class AnalyzeRequest(BaseModel):
    articles: list[Article] = Field(min_length=1)
