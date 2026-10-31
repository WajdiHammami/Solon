"""SQL table definitions (SQLAlchemy ORM).

Schema changes go through Alembic: edit these classes, then generate a
migration (see ``backend/README.md``). Never edit an applied migration.
"""

from datetime import datetime

from sqlalchemy import DateTime, String, Text
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    pass


class ArticleRow(Base):
    """An article this server issued via ``/feed`` (backs the ArticleRegistry)."""

    __tablename__ = "articles"

    url: Mapped[str] = mapped_column(String(2048), primary_key=True)
    title: Mapped[str] = mapped_column(Text)
    source_name: Mapped[str] = mapped_column(String(255))
    published_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    content: Mapped[str | None] = mapped_column(Text)
    fingerprint: Mapped[str] = mapped_column(String(64))
    first_seen_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    last_seen_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class AnalysisRow(Base):
    """Cached LLM analysis of an article (backs the AnalysisCache).

    Summary and bias are versioned independently: a result is only reused
    while its ``*_version`` matches the current prompt version, so changing
    one prompt recomputes just that part. ``*_model`` records which model
    produced it, for reference only (switching models doesn't invalidate).

    Not a foreign key to ``articles``: the cache is keyed by URL on its own
    and must not depend on the registry.
    """

    __tablename__ = "analyses"

    url: Mapped[str] = mapped_column(String(2048), primary_key=True)

    summary: Mapped[str | None] = mapped_column(Text)
    summary_version: Mapped[str | None] = mapped_column(String(32))
    summary_model: Mapped[str | None] = mapped_column(String(255))
    summary_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    bias_label: Mapped[str | None] = mapped_column(String(255))
    bias_explanation: Mapped[str | None] = mapped_column(Text)
    bias_version: Mapped[str | None] = mapped_column(String(32))
    bias_model: Mapped[str | None] = mapped_column(String(255))
    bias_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
