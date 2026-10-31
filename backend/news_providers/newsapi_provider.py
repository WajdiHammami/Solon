import logging

from newsapi import NewsApiClient
from newspaper import Article as NewspaperArticle

from backend.models import Article
from backend.news_providers.base import NewsProvider

logger = logging.getLogger(__name__)


class NewsAPIProvider(NewsProvider):
    """News provider backed by NewsAPI (https://newsapi.org)."""

    def __init__(self, api_key: str):
        self.newsapi = NewsApiClient(api_key=api_key)

    def fetch_articles(
        self,
        query: str | list[str],
        sources: list[str] | None = None,
        language: str = "en",
        sort_by: str = "relevancy",
        page_size: int = 5,
        page: int = 1,
    ) -> list[Article]:
        queries = [query] if isinstance(query, str) else query
        sources_param = ",".join(sources) if sources else ""

        articles: list[Article] = []
        for q in queries:
            response = self.newsapi.get_everything(
                q=q,
                sources=sources_param,
                language=language,
                sort_by=sort_by,
                page_size=page_size,
                page=page,
            )
            if response["status"] != "ok":
                logger.error("Error fetching articles: %s", response.get("message"))
                continue

            for raw in response["articles"]:
                # ``id`` must be unique across the whole returned batch so the
                # analysis workflows can key results by article id.
                articles.append(
                    Article(
                        id=len(articles),
                        title=raw["title"],
                        url=raw["url"],
                        source_name=raw["source"]["name"],
                        published_at=raw["publishedAt"],
                        # NewsAPI ships a short description/content snippet; keep
                        # it as a baseline so summaries have something to work
                        # with even before the full article is scraped.
                        content=self._snippet(raw),
                    )
                )
        return articles

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
