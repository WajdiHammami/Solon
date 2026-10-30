from abc import ABC, abstractmethod

from backend.models import Article


class NewsProvider(ABC):
    """Abstract interface every news source must implement."""

    @abstractmethod
    def fetch_articles(
        self,
        query: str | list[str],
        page_size: int = 5,
        page: int = 1,
    ) -> list[Article]:
        """Fetch article metadata matching ``query``."""

    @abstractmethod
    def extract_content(self, url: str) -> str:
        """Return the full text content of the article at ``url``."""
