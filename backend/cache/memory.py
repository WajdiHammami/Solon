from backend.cache.base import AnalysisCache
from backend.models import ArticleAnalysis


class InMemoryAnalysisCache(AnalysisCache):
    """Process-local cache; lost on restart. Stand-in until the database."""

    def __init__(self):
        self._entries: dict[str, ArticleAnalysis] = {}

    async def get(self, url: str) -> ArticleAnalysis | None:
        entry = self._entries.get(url)
        return entry.model_copy() if entry else None

    async def put(self, url: str, analysis: ArticleAnalysis) -> None:
        self._entries[url] = analysis.model_copy()
