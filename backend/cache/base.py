from abc import ABC, abstractmethod

from backend.models import ArticleAnalysis


class AnalysisCache(ABC):
    """Store of previously computed article analyses, keyed by article URL.

    The URL is used rather than ``Article.id`` because ids are only unique
    within a single fetch, while a URL identifies the article across fetches.
    """

    @abstractmethod
    async def get(self, url: str) -> ArticleAnalysis | None:
        """Return the stored analysis for ``url``, or ``None``."""

    async def get_many(self, urls: list[str]) -> dict[str, ArticleAnalysis]:
        """Stored analyses for ``urls``; URLs without one are left out.

        Override when the backend can fetch many at once (one SQL query).
        """
        found = {}
        for url in dict.fromkeys(urls):
            analysis = await self.get(url)
            if analysis is not None:
                found[url] = analysis
        return found

    @abstractmethod
    async def put(self, url: str, analysis: ArticleAnalysis) -> None:
        """Store ``analysis`` for ``url``, replacing any previous entry."""
