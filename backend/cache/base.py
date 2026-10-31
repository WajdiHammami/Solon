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

    @abstractmethod
    async def put(self, url: str, analysis: ArticleAnalysis) -> None:
        """Store ``analysis`` for ``url``, replacing any previous entry."""
