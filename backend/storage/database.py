"""Connection and lifecycle for the SQL database.

:class:`Database` is the only place that knows about engines, connection
pools and migrations. Stores (``SqlArticleRegistry``, ``SqlAnalysisCache``)
receive it and run their own typed queries through :meth:`Database.session`.
SQLAlchemy handles dialect differences, so moving from SQLite to Postgres is
a URL change (plus the matching async driver).
"""

import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from dataclasses import dataclass
from pathlib import Path

from alembic import command
from alembic.config import Config as AlembicConfig
from sqlalchemy import event, text
from sqlalchemy.engine import make_url
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

logger = logging.getLogger(__name__)

ALEMBIC_INI = Path(__file__).resolve().parent.parent / "alembic.ini"


@dataclass(frozen=True)
class DatabaseConfig:
    url: str  # e.g. "sqlite+aiosqlite:////abs/path/solon.db"
    echo: bool = False  # log every SQL statement (debugging only)


class Database:
    def __init__(self, config: DatabaseConfig):
        self._config = config
        self._engine: AsyncEngine | None = None
        self._sessions: async_sessionmaker[AsyncSession] | None = None

    @property
    def config(self) -> DatabaseConfig:
        return self._config

    async def connect(self) -> None:
        """Open the engine and bring the schema up to date (Alembic ``head``)."""
        url = make_url(self._config.url)
        if url.get_backend_name() == "sqlite" and url.database not in (None, "", ":memory:"):
            Path(url.database).parent.mkdir(parents=True, exist_ok=True)

        self._engine = create_async_engine(self._config.url, echo=self._config.echo)
        if url.get_backend_name() == "sqlite":
            event.listen(self._engine.sync_engine, "connect", _sqlite_pragmas)
        self._sessions = async_sessionmaker(self._engine, expire_on_commit=False)

        async with self._engine.begin() as connection:
            await connection.run_sync(_upgrade_to_head)
        logger.info("Database ready (%s)", url.render_as_string(hide_password=True))

    async def close(self) -> None:
        if self._engine is not None:
            await self._engine.dispose()
            self._engine = None
            self._sessions = None

    @asynccontextmanager
    async def session(self) -> AsyncIterator[AsyncSession]:
        """One unit of work: commits on success, rolls back on any error."""
        if self._sessions is None:
            raise RuntimeError("Database.connect() must be awaited before use")
        async with self._sessions() as session, session.begin():
            yield session

    async def health(self) -> bool:
        try:
            async with self.session() as session:
                await session.execute(text("SELECT 1"))
            return True
        except Exception:
            logger.exception("Database health check failed")
            return False


def _upgrade_to_head(connection) -> None:
    config = AlembicConfig(str(ALEMBIC_INI))
    config.attributes["connection"] = connection  # reuse ours; see migrations/env.py
    command.upgrade(config, "head")


def _sqlite_pragmas(dbapi_connection, _record) -> None:
    cursor = dbapi_connection.cursor()
    # WAL lets readers proceed while a write is in progress.
    cursor.execute("PRAGMA journal_mode=WAL")
    cursor.execute("PRAGMA foreign_keys=ON")
    cursor.close()
