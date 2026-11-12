from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field, model_validator


class Article(BaseModel):
    id: int
    title: str
    url: str
    source_name: str
    tag: Optional[str] = None
    tag_explanation: Optional[str] = None
    published_at: datetime
    content: Optional[str] = None
    summary: Optional[str] = None


class BiasAssessment(BaseModel):
    label: str  # short tag, e.g. "Political"; "None" when no bias was found
    explanation: Optional[str] = None
    # Whether the article is about politics/policy; lean only applies then.
    political: Optional[bool] = None
    # US left-right lean, AllSides' 5 categories:
    # -2 Left, -1 Lean Left, 0 Center, 1 Lean Right, 2 Right.
    lean: Optional[int] = Field(default=None, ge=-2, le=2)

    @model_validator(mode="after")
    def _no_lean_without_politics(self) -> "BiasAssessment":
        if self.political is False:
            self.lean = None
        return self


class ArticleAnalysis(BaseModel):
    """LLM-derived analysis of one article; fields are ``None`` until computed."""

    summary: Optional[str] = None
    bias: Optional[BiasAssessment] = None

    @property
    def is_complete(self) -> bool:
        return self.summary is not None and self.bias is not None


class LLMUsage(BaseModel):
    """LLM consumption of one operation (cache hits cost nothing)."""

    calls: int = 0
    input_tokens: int = 0
    output_tokens: int = 0
    # Estimated from the configured prices; None when no price is set.
    cost: Optional[float] = None
    currency: Optional[str] = None
    model: Optional[str] = None


class TaskFailure(BaseModel):
    """One analysis task that failed; the rest of the work still completes."""

    task: str  # "summarize" | "detect_bias" | "synthesize"
    error: str
    retryable: bool
    article_id: Optional[int] = None  # None for batch-level tasks (synthesize)


class ArticleResult(BaseModel):
    analysis: ArticleAnalysis
    failures: list[TaskFailure] = []
    # Where each produced part came from: "summarize" / "detect_bias".
    from_cache: list[str] = []  # reused from the analysis cache (database)
    computed: list[str] = []  # freshly produced by the LLM in this run
    usage: Optional[LLMUsage] = None  # set by the API for this request


class BatchAnalysis(BaseModel):
    analyses: dict[int, ArticleAnalysis]  # article_id -> analysis
    synthesis: Optional[str] = None
    sources: list[int] = []  # ids of the articles the synthesis was built from
    failed: list[TaskFailure] = []
    skipped: list[int] = []  # ids dropped by the token budget, never attempted
    estimated_tokens: int = 0
    usage: Optional[LLMUsage] = None  # actual consumption, set by the API


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
