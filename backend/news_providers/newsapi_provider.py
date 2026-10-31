import logging
from collections.abc import Callable

import requests
from newsapi import NewsApiClient
from newsapi.newsapi_exception import NewsAPIException
from newspaper import Article as NewspaperArticle

from backend.models import Article
from backend.news_providers.base import (
    DEFAULT_PAGE_SIZE,
    NewsProvider,
    NewsProviderError,
)

logger = logging.getLogger(__name__)


class NewsAPIProvider(NewsProvider):
    """News provider backed by NewsAPI (https://newsapi.org).

    :param language: restricts both searches and headlines (ISO 639-1).
    :param country: optional ISO 3166-1 country for top headlines.
    """

    def __init__(self, api_key: str, language: str = "en", country: str | None = None):
        self.newsapi = NewsApiClient(api_key=api_key)
        self.language = language
        self.country = country

    def fetch_articles(
        self,
        query: str | list[str],
        page_size: int = DEFAULT_PAGE_SIZE,
        page: int = 1,
        *,
        sources: list[str] | None = None,
        sort_by: str = "relevancy",
    ) -> list[Article]:
        queries = [query] if isinstance(query, str) else query
        sources_param = ",".join(sources) if sources else ""

        articles: list[Article] = []
        for q in queries:
            response = self._call(
                lambda: self.newsapi.get_everything(
                    q=q,
                    sources=sources_param,
                    language=self.language,
                    sort_by=sort_by,
                    page_size=page_size,
                    page=page,
                )
            )
            articles += self._to_articles(response, first_id=len(articles))
        return articles

    def fetch_top_headlines(
        self,
        page_size: int = DEFAULT_PAGE_SIZE,
        page: int = 1,
    ) -> list[Article]:
        response = self._call(
            lambda: self.newsapi.get_top_headlines(
                language=self.language,
                country=self.country,
                page_size=page_size,
                page=page,
            )
        )
        return self._to_articles(response, first_id=0)

    @staticmethod
    def _call(request: Callable[[], dict]) -> dict:
        """Run a NewsAPI call, raising :class:`NewsProviderError` on any failure."""
        try:
            response = request()
        except NewsAPIException as e:
            raise NewsProviderError(f"NewsAPI error: {e.get_message()}") from e
        except requests.RequestException as e:
            raise NewsProviderError(f"NewsAPI unreachable: {e}") from e
        if response.get("status") != "ok":
            raise NewsProviderError(f"NewsAPI error: {response.get('message')}")
        return response

    def _to_articles(self, response: dict, first_id: int) -> list[Article]:
        return [
            Article(
                # ``id`` must be unique across the whole returned batch so the
                # analysis workflows can key results by article id.
                id=first_id + i,
                title=raw["title"],
                url=raw["url"],
                source_name=raw["source"]["name"],
                published_at=raw["publishedAt"],
                # NewsAPI ships a short description/content snippet; keep
                # it as a baseline so summaries have something to work
                # with even before the full article is scraped.
                content=self._snippet(raw),
            )
            for i, raw in enumerate(response["articles"])
        ]

    @staticmethod
    def _snippet(raw: dict) -> str | None:
        parts = [raw.get("description"), raw.get("content")]
        snippet = "\n\n".join(p for p in parts if p).strip()
        return snippet or None

    def extract_content(self, url: str) -> str:
        try:
            newspaper_article = NewspaperArticle(url)
            newspaper_article.download()
            newspaper_article.parse()
            return newspaper_article.text
        except Exception as e:
            logger.error("Error extracting content from %s: %s", url, e)
            return ""
