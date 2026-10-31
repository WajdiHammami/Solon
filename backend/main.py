"""FastAPI application exposing the Solon news aggregation and analysis API."""

import logging
from functools import lru_cache

from fastapi import Depends, FastAPI
from langchain_groq import ChatGroq

from backend.config import get_settings
from backend.models import Article, SummarizeRequest, SummarizeResponse
from backend.news_providers.newsapi_provider import NewsAPIProvider
from backend.summarization.pipeline import SummarizationPipeline

logger = logging.getLogger(__name__)

app = FastAPI(title="Solon", version="0.1.0")


@lru_cache
def get_providers() -> list[NewsAPIProvider]:
    """Return the configured news providers (built once, then cached)."""
    settings = get_settings()
    return [NewsAPIProvider(api_key=settings.newsapi_key)]


@lru_cache
def get_summarizer() -> SummarizationPipeline:
    """Return the summarization pipeline (built once, then cached)."""
    settings = get_settings()
    llm = ChatGroq(model=settings.groq_model, api_key=settings.groq_api_key)
    return SummarizationPipeline(llm=llm)


@app.get("/health")
def health_check() -> dict[str, str]:
    return {"status": "healthy"}


@app.get("/feed")
def get_feed(
    topic: str | None = None,
    page_size: int = 40,
    page: int = 1,
    providers: list[NewsAPIProvider] = Depends(get_providers),
) -> list[Article]:
    articles: list[Article] = []
    for provider in providers:
        articles += provider.fetch_articles(
            topic or "Top headlines", page_size=page_size, page=page
        )
    return articles


# Articles with less text than this are scraped for their full content before
# summarization (NewsAPI only returns a short snippet).
_MIN_CONTENT_CHARS = 600


def _hydrate_content(
    articles: list[Article], providers: list[NewsAPIProvider]
) -> list[Article]:
    """Scrape full article text for any article lacking substantial content.

    Falls back to whatever content the article already had (the NewsAPI
    snippet) when scraping yields nothing, so summarization always has input.
    """
    for article in articles:
        if article.content and len(article.content) >= _MIN_CONTENT_CHARS:
            continue
        scraped = providers[0].extract_content(article.url)
        if scraped:
            article.content = scraped
    return articles


@app.post("/summarize")
def summarize(
    request: SummarizeRequest,
    summarizer: SummarizationPipeline = Depends(get_summarizer),
    providers: list[NewsAPIProvider] = Depends(get_providers),
) -> SummarizeResponse | Article:
    articles = _hydrate_content(request.articles, providers)

    if len(articles) > 1:
        result = summarizer.run_batch_summarization(articles)
        return SummarizeResponse(
            summaries=result["summaries"],
            synthesis=result["synthesis"],
            tags=result["tags"],
        )

    result = summarizer.run_singular_summarization(
        articles[0], config={"enable_bias": True}
    )
    return result["article"]


@app.get("/article/content")
def get_content(
    url: str,
    providers: list[NewsAPIProvider] = Depends(get_providers),
) -> str:
    content = providers[0].extract_content(url)
    logger.info("Extracted %d characters from %s", len(content), url)
    return content
