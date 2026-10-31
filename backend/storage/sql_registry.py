from datetime import datetime, timezone

from sqlalchemy import select

from backend.article_registry import ArticleRegistry, article_fingerprint
from backend.models import Article
from backend.storage.database import Database
from backend.storage.tables import ArticleRow


class SqlArticleRegistry(ArticleRegistry):
    """Issued articles persisted in SQL, so they stay valid across restarts.

    Keeps everything (no eviction): the rows double as the article archive.
    """

    def __init__(self, db: Database):
        self._db = db

    async def register(self, articles: list[Article]) -> int:
        if not articles:
            return 0
        now = datetime.now(timezone.utc)
        # Last occurrence wins if a URL repeats within one batch.
        by_url = {a.url: a for a in articles}
        async with self._db.session() as session:
            existing = {
                row.url: row
                for row in await session.scalars(
                    select(ArticleRow).where(ArticleRow.url.in_(by_url))
                )
            }
            for url, article in by_url.items():
                row = existing.get(url)
                if row is None:
                    row = ArticleRow(url=url, first_seen_at=now)
                    session.add(row)
                # The source may have edited the article; the latest issue wins.
                row.title = article.title
                row.source_name = article.source_name
                row.published_at = article.published_at
                row.content = article.content
                row.fingerprint = article_fingerprint(article)
                row.last_seen_at = now
        return len(by_url) - len(existing)

    async def fingerprint_for(self, url: str) -> str | None:
        async with self._db.session() as session:
            return await session.scalar(
                select(ArticleRow.fingerprint).where(ArticleRow.url == url)
            )
