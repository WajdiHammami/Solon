"""Alembic environment.

Two ways in:
- From the app, ``Database.connect()`` passes its own connection through
  ``config.attributes["connection"]``; we migrate on it and leave logging alone.
- From the CLI (``alembic upgrade head`` / ``alembic revision --autogenerate``),
  we build an engine from ``DATABASE_URL`` (backend settings).
"""

import asyncio
from logging.config import fileConfig

from alembic import context
from sqlalchemy.ext.asyncio import create_async_engine

from backend.config import get_settings
from backend.storage.tables import Base

config = context.config
target_metadata = Base.metadata


def _configure(**kwargs) -> None:
    # Batch mode lets SQLite (no ALTER COLUMN) apply column changes.
    context.configure(target_metadata=target_metadata, render_as_batch=True, **kwargs)


def run_migrations_offline() -> None:
    _configure(url=get_settings().resolved_database_url, literal_binds=True)
    with context.begin_transaction():
        context.run_migrations()


def _run_on(connection) -> None:
    _configure(connection=connection)
    with context.begin_transaction():
        context.run_migrations()


async def _run_from_cli() -> None:
    engine = create_async_engine(get_settings().resolved_database_url)
    async with engine.connect() as connection:
        await connection.run_sync(_run_on)
        await connection.commit()
    await engine.dispose()


def run_migrations_online() -> None:
    connection = config.attributes.get("connection")
    if connection is not None:
        _run_on(connection)
        return
    if config.config_file_name is not None:
        fileConfig(config.config_file_name)
    asyncio.run(_run_from_cli())


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
