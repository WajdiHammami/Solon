from abc import ABC, abstractmethod

from backend.models import Article

#: Articles per page when the caller doesn't say; matches what the client asks for.
DEFAULT_PAGE_SIZE = 5


class NewsProvider(ABC):
    """Abstract interface every news source must implement.

    Implementations keep these signatures; provider-specific options go
    after them as keyword-only arguments or into the constructor.
    """

    @abstractmethod
    def fetch_articles(
        self,
        query: str | list[str],
        page_size: int = DEFAULT_PAGE_SIZE,
        page: int = 1,
    ) -> list[Article]:
        """Fetch article metadata matching ``query``."""

    @abstractmethod
    def fetch_top_headlines(
        self,
        page_size: int = DEFAULT_PAGE_SIZE,
        page: int = 1,
    ) -> list[Article]:
        """Fetch the current top headlines (no query)."""

    @abstractmethod
    def extract_content(self, url: str) -> str:
        """Return the full text content of the article at ``url``, or ``""``."""
