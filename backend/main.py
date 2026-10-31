"""FastAPI application exposing the Solon news aggregation and analysis API."""

import asyncio
import logging
import time
from contextlib import asynccontextmanager
from functools import lru_cache

from fastapi import Depends, FastAPI, HTTPException, Query, Request
from fastapi.responses import JSONResponse

from backend.article_registry import ArticleRegistry
from backend.cache.base import AnalysisCache
from backend.config import get_settings
from backend.llm.base import LLMClient
from backend.llm.factory import create_llm
from backend.logging_config import configure_logging
from backend.models import (
    AnalyzeRequest,
    Article,
    ArticleAnalysis,
    ArticleResult,
    BatchAnalysis,
)
from backend.news_providers.base import (
    DEFAULT_PAGE_SIZE,
    NewsProvider,
    NewsProviderError,
)
from backend.news_providers.newsapi_provider import NewsAPIProvider
from backend.request_context import (
    REQUEST_ID_HEADER,
    reset_request_id,
    resolve_request_id,
    set_request_id,
)
from backend.storage.database import Database, DatabaseConfig
from backend.storage.sql_cache import SqlAnalysisCache
from backend.storage.sql_registry import SqlArticleRegistry
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
    database = get_database()
    await database.connect()  # also applies pending migrations
    try:
        yield
    finally:
        await database.close()


app = FastAPI(title="Solon", version="0.2.0", lifespan=lifespan)


@app.middleware("http")
async def request_id_middleware(request: Request, call_next):
    """Tag the request's log lines with an id and echo it in the response."""
    request_id = resolve_request_id(request.headers.get(REQUEST_ID_HEADER))
    token = set_request_id(request_id)
    started = time.perf_counter()
    try:
        response = await call_next(request)
        logger.info(
            "%s %s -> %d (%.0f ms)",
            request.method,
            request.url.path,
            response.status_code,
            (time.perf_counter() - started) * 1000,
        )
        response.headers[REQUEST_ID_HEADER] = request_id
        return response
    except Exception:
        # Unhandled errors still get a JSON body (and the id) the client can show.
        logger.exception("%s %s failed", request.method, request.url.path)
        return JSONResponse(
            status_code=500,
            content={"detail": {"message": "Internal server error", "request_id": request_id}},
            headers={REQUEST_ID_HEADER: request_id},
        )
    finally:
        reset_request_id(token)


# --- Dependencies (each built once, then cached) ---------------------------


@lru_cache
def get_providers() -> list[NewsProvider]:
    """Return the configured news providers."""
    settings = get_settings()
    return [
        NewsAPIProvider(
            api_key=settings.newsapi_key,
            language=settings.news_language,
            country=settings.news_country or None,
        )
    ]


@lru_cache
def get_llm() -> LLMClient:
    return create_llm(get_settings())


@lru_cache
def get_database() -> Database:
    return Database(DatabaseConfig(url=get_settings().resolved_database_url))


@lru_cache
def get_cache() -> AnalysisCache:
    return SqlAnalysisCache(get_database(), model=get_llm().config.model)


@lru_cache
def get_registry() -> ArticleRegistry:
    return SqlArticleRegistry(get_database())


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
async def health_check() -> dict[str, str]:
    database_ok = await get_database().health()
    return {
        "status": "healthy" if database_ok else "degraded",
        "database": "ok" if database_ok else "unavailable",
    }


@app.get("/feed")
async def get_feed(
    topic: str | None = None,
    page_size: int = Query(DEFAULT_PAGE_SIZE, ge=1, le=100),
    page: int = Query(1, ge=1),
    providers: list[NewsProvider] = Depends(get_providers),
    registry: ArticleRegistry = Depends(get_registry),
    cache: AnalysisCache = Depends(get_cache),
) -> list[Article]:
    """Articles matching ``topic``; top headlines when it is missing or blank.

    Every returned article is registered, so it can be analyzed later, and
    comes with its summary/bias when a current analysis is already stored.
    """
    topic = (topic or "").strip()
    articles: list[Article] = []
    try:
        for provider in providers:
            # Provider SDKs are blocking; keep them off the event loop.
            if topic:
                articles += await asyncio.to_thread(
                    provider.fetch_articles, topic, page_size=page_size, page=page
                )
            else:
                articles += await asyncio.to_thread(
                    provider.fetch_top_headlines, page_size=page_size, page=page
                )
    except NewsProviderError as e:
        logger.warning("Feed failed: %s", e)
        raise HTTPException(status_code=502, detail={"message": str(e)}) from e
    # Each provider numbers from 0; renumber so ids are unique across providers.
    articles = [a.model_copy(update={"id": i}) for i, a in enumerate(articles)]
    # Register the articles as issued (fingerprints cover only what the
    # provider returned, so attaching analysis below doesn't affect them).
    new = await registry.register(articles)
    known = await cache.get_many([a.url for a in articles])
    articles = [_with_analysis(a, known.get(a.url)) for a in articles]
    distinct = len({a.url for a in articles})
    logger.info(
        "Feed %s: %d new, %d already in the database (%d total), %d with stored analysis",
        f'"{topic}"' if topic else "top headlines",
        new,
        distinct - new,
        distinct,
        len(known),
    )
    return articles


def _with_analysis(article: Article, analysis: ArticleAnalysis | None) -> Article:
    if analysis is None:
        return article
    update: dict = {"summary": analysis.summary}
    if analysis.bias is not None:
        update["tag"] = analysis.bias.label
        update["tag_explanation"] = analysis.bias.explanation
    return article.model_copy(update=update)


async def _require_issued(articles: list[Article], registry: ArticleRegistry) -> None:
    """Reject the request unless every article is exactly as ``/feed`` issued it."""
    rejected = [a.id for a in articles if not await registry.verify(a)]
    if rejected:
        logger.warning("Rejected unknown or modified articles: ids %s", rejected)
        raise HTTPException(
            status_code=403,
            detail={
                "message": "Unknown or modified article — search again to refresh the feed",
                "article_ids": rejected,
            },
        )


@app.post("/analyze")
async def analyze(
    request: AnalyzeRequest,
    workflow: BatchWorkflow = Depends(get_batch_workflow),
    registry: ArticleRegistry = Depends(get_registry),
) -> BatchAnalysis:
    """Analyze articles and synthesize them; partial failures are reported."""
    await _require_issued(request.articles, registry)
    return await workflow.run(request.articles)


@app.post("/analyze/article")
async def analyze_article(
    article: Article,
    workflow: ArticleWorkflow = Depends(get_article_workflow),
    registry: ArticleRegistry = Depends(get_registry),
) -> ArticleResult:
    """Summarize and bias-tag one article; partial failures are reported."""
    await _require_issued([article], registry)
    result = await workflow.run(article)
    logger.info(
        "Article analysis %s: from database %s, new %s, failed %s",
        article.url,
        ", ".join(result.from_cache) or "nothing",
        ", ".join(result.computed) or "nothing",
        ", ".join(f.task for f in result.failures) or "nothing",
    )
    return result


@app.get("/article/content")
async def get_content(
    url: str,
    providers: list[NewsProvider] = Depends(get_providers),
    registry: ArticleRegistry = Depends(get_registry),
) -> str:
    """Full text of an article previously returned by ``/feed``."""
    if not await registry.is_issued(url):
        logger.warning("Rejected content request for unknown URL %s", url)
        raise HTTPException(
            status_code=403,
            detail={"message": "Unknown article URL — search again to refresh the feed"},
        )
    content = await asyncio.to_thread(providers[0].extract_content, url)
    logger.info("Extracted %d characters from %s", len(content), url)
    return content
