"""Registry of the articles this server has issued, for verifying client input.

``/feed`` registers a fingerprint (SHA-256) of every article it returns. When
the client later asks for work on an article, the server recomputes the
fingerprint and only proceeds if it matches what was issued for that URL. A
client therefore can't make the server analyze, cache, or fetch anything it
didn't hand out: no forged content planted under a real URL, and no fetching
of arbitrary (e.g. internal) URLs.
"""

import hashlib
import json
from abc import ABC, abstractmethod
from collections import OrderedDict

from backend.models import Article

#: Hashed fields: what reaches the LLM and the cache. The URL is not hashed but
#: is still bound: it is the registry key, so the hash must match the one issued
#: for that exact URL. ``id`` (renumbered per fetch), ``published_at`` (never
#: used in analysis) and analysis fields (never trusted) are left out.
FINGERPRINT_FIELDS = ("title", "content", "source_name")


def article_fingerprint(article: Article) -> str:
    data = article.model_dump(mode="json", include=set(FINGERPRINT_FIELDS))
    data["content"] = data["content"] or ""  # clients send "" for null
    payload = json.dumps(data, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


class ArticleRegistry(ABC):
    @abstractmethod
    async def register(self, articles: list[Article]) -> None:
        """Record ``articles`` as issued; re-registering a URL replaces it."""

    @abstractmethod
    async def fingerprint_for(self, url: str) -> str | None:
        """The fingerprint issued for ``url``, or ``None`` if never issued."""

    async def is_issued(self, url: str) -> bool:
        return await self.fingerprint_for(url) is not None

    async def verify(self, article: Article) -> bool:
        """Whether ``article`` is exactly as this server issued it."""
        issued = await self.fingerprint_for(article.url)
        return issued is not None and issued == article_fingerprint(article)


class InMemoryArticleRegistry(ArticleRegistry):
    """Process-local registry, oldest entries evicted past ``max_entries``.

    Lost on restart: articles fetched before a restart must be fetched again.
    """

    def __init__(self, max_entries: int = 10_000):
        self._max_entries = max_entries
        self._fingerprints: OrderedDict[str, str] = OrderedDict()

    async def register(self, articles: list[Article]) -> None:
        for article in articles:
            self._fingerprints[article.url] = article_fingerprint(article)
            self._fingerprints.move_to_end(article.url)
        while len(self._fingerprints) > self._max_entries:
            self._fingerprints.popitem(last=False)

    async def fingerprint_for(self, url: str) -> str | None:
        return self._fingerprints.get(url)
