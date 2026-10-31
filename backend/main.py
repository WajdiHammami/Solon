"""FastAPI application exposing the Solon news aggregation and analysis API."""

import asyncio
import logging
from contextlib import asynccontextmanager
from functools import lru_cache

from fastapi import Depends, FastAPI, HTTPException

from backend.cache.base import AnalysisCache
from backend.cache.memory import InMemoryAnalysisCache
from backend.config import get_settings
from backend.llm.base import LLMClient
from backend.llm.factory import create_llm
from backend.logging_config import configure_logging
from backend.models import (
    AnalyzeRequest,
    Article,
    ArticleResult,
    BatchAnalysis,
    SummarizeRequest,
    SummarizeResponse,
    TaskFailure,
)
from backend.news_providers.base import NewsProvider
from backend.news_providers.newsapi_provider import NewsAPIProvider
from backend.workflows.article_workflow import ArticleWorkflow
from backend.workflows.batch_workflow import BatchWorkflow

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    settings = get_settings()
    configure_logging(
        settings.log_level,
        settings.log_file_path,
        settings.log_max_bytes,
        settings.log_backup_count,
    )
    logger.info("Solon backend starting (LLM provider: %s)", settings.llm_provider)
    yield


app = FastAPI(title="Solon", version="0.2.0", lifespan=lifespan)


# --- Dependencies (each built once, then cached) ---------------------------


@lru_cache
def get_providers() -> list[NewsProvider]:
    """Return the configured news providers."""
    settings = get_settings()
    return [NewsAPIProvider(api_key=settings.newsapi_key)]


@lru_cache
def get_llm() -> LLMClient:
    return create_llm(get_settings())


@lru_cache
def get_cache() -> AnalysisCache:
    return InMemoryAnalysisCache()


@lru_cache
def get_article_workflow() -> ArticleWorkflow:
    provider = get_providers()[0]

    async def load_content(url: str) -> str:
        # newspaper3k is blocking; keep it off the event loop.
        return await asyncio.to_thread(provider.extract_content, url)

    return ArticleWorkflow(
        get_llm(),
        get_cache(),
        content_loader=load_content,
        min_content_chars=get_settings().min_content_chars,
    )


@lru_cache
def get_batch_workflow() -> BatchWorkflow:
    settings = get_settings()
    return BatchWorkflow(
        get_llm(),
        get_article_workflow(),
        max_tokens=settings.batch_max_tokens,
        max_concurrency=settings.batch_max_concurrency,
    )


# --- Routes -----------------------------------------------------------------


@app.get("/health")
def health_check() -> dict[str, str]:
    return {"status": "healthy"}


@app.get("/feed")
def get_feed(
    topic: str | None = None,
    page_size: int = 40,
    page: int = 1,
    providers: list[NewsProvider] = Depends(get_providers),
) -> list[Article]:
    articles: list[Article] = []
    for provider in providers:
        articles += provider.fetch_articles(
            topic or "Top headlines", page_size=page_size, page=page
        )
    return articles


@app.post("/analyze")
async def analyze(
    request: AnalyzeRequest,
    workflow: BatchWorkflow = Depends(get_batch_workflow),
) -> BatchAnalysis:
    """Analyze articles and synthesize them; partial failures are reported."""
    return await workflow.run(request.articles)


@app.post("/analyze/article")
async def analyze_article(
    article: Article,
    workflow: ArticleWorkflow = Depends(get_article_workflow),
) -> ArticleResult:
    """Summarize and bias-tag one article; partial failures are reported."""
    return await workflow.run(article)


@app.post("/summarize", deprecated=True)
async def summarize(
    request: SummarizeRequest,
    article_workflow: ArticleWorkflow = Depends(get_article_workflow),
    batch_workflow: BatchWorkflow = Depends(get_batch_workflow),
) -> SummarizeResponse | Article:
    """Legacy shape kept for the current client; use ``/analyze`` instead.

    One article returns the :class:`Article` with ``summary``/``tag`` set;
    several return a :class:`SummarizeResponse` with summaries in request
    order (``""`` where unavailable). Responds 502 when nothing was produced.
    """
    if len(request.articles) == 1:
        article = request.articles[0]
        result = await article_workflow.run(article)
        analysis = result.analysis
        if analysis.summary is None and analysis.bias is None:
            raise _all_failed(result.failures)
        return article.model_copy(
            update={
                "summary": analysis.summary,
                "tag": analysis.bias.label if analysis.bias else article.tag,
            }
        )

    batch = await batch_workflow.run(request.articles)
    if not batch.analyses and batch.failed:
        raise _all_failed(batch.failed)
    summaries = []
    tags = {}
    for article in request.articles:
        analysis = batch.analyses.get(article.id)
        summaries.append((analysis.summary or "") if analysis else "")
        if analysis and analysis.bias:
            tags[article.id] = (analysis.bias.label, analysis.bias.explanation or "")
    return SummarizeResponse(summaries=summaries, synthesis=batch.synthesis, tags=tags)


def _all_failed(failures: list[TaskFailure]) -> HTTPException:
    return HTTPException(
        status_code=502,
        detail={
            "message": "Analysis failed",
            "failures": [f.model_dump() for f in failures],
        },
    )


@app.get("/article/content")
def get_content(
    url: str,
    providers: list[NewsProvider] = Depends(get_providers),
) -> str:
    content = providers[0].extract_content(url)
    logger.info("Extracted %d characters from %s", len(content), url)
    return content
