"""Tests for the SQL storage layer.

The contract tests run against every implementation of an interface, in
memory and SQL alike: that is what makes them interchangeable.
"""

import pytest
from sqlalchemy import inspect, select

from backend.article_registry import ArticleRegistry, InMemoryArticleRegistry
from backend.cache.base import AnalysisCache
from backend.cache.memory import InMemoryAnalysisCache
from backend.models import ArticleAnalysis, BiasAssessment
from backend.storage.database import Database, DatabaseConfig
from backend.storage.sql_cache import SqlAnalysisCache
from backend.storage.sql_registry import SqlArticleRegistry
from backend.storage.tables import AnalysisRow, ArticleRow

pytestmark = pytest.mark.anyio


@pytest.fixture
def db_url(tmp_path):
    return f"sqlite+aiosqlite:///{tmp_path / 'solon.db'}"


@pytest.fixture
async def db(db_url):
    database = Database(DatabaseConfig(url=db_url))
    await database.connect()
    yield database
    await database.close()


def _analysis(summary="s", label="Political", explanation="e"):
    bias = BiasAssessment(label=label, explanation=explanation) if label else None
    return ArticleAnalysis(summary=summary, bias=bias)


# --- Database -----------------------------------------------------------------


class TestDatabase:
    async def test_connect_creates_schema_via_migrations(self, db):
        async with db.session() as session:
            tables = await session.run_sync(
                lambda s: inspect(s.connection()).get_table_names()
            )
        assert {"articles", "analyses", "alembic_version"} <= set(tables)

    async def test_connect_is_idempotent(self, db_url):
        for _ in range(2):  # second run finds the schema at head
            database = Database(DatabaseConfig(url=db_url))
            await database.connect()
            assert await database.health()
            await database.close()

    async def test_creates_missing_parent_directory(self, tmp_path):
        url = f"sqlite+aiosqlite:///{tmp_path / 'nested' / 'dir' / 'x.db'}"
        database = Database(DatabaseConfig(url=url))
        await database.connect()
        assert (tmp_path / "nested" / "dir" / "x.db").exists()
        await database.close()

    async def test_session_rolls_back_on_error(self, db, make_article):
        with pytest.raises(RuntimeError):
            async with db.session() as session:
                session.add(AnalysisRow(url="https://example.com/x", summary="s"))
                raise RuntimeError("boom")
        async with db.session() as session:
            assert await session.get(AnalysisRow, "https://example.com/x") is None

    async def test_session_requires_connect(self):
        database = Database(DatabaseConfig(url="sqlite+aiosqlite:///:memory:"))
        with pytest.raises(RuntimeError, match="connect"):
            async with database.session():
                pass

    async def test_config_property(self, db, db_url):
        assert db.config.url == db_url


# --- ArticleRegistry contract -------------------------------------------------


@pytest.fixture(params=["memory", "sql"])
def registry(request, db) -> ArticleRegistry:
    return InMemoryArticleRegistry() if request.param == "memory" else SqlArticleRegistry(db)


class TestArticleRegistryContract:
    async def test_unknown_url(self, registry):
        assert await registry.fingerprint_for("https://nowhere") is None
        assert not await registry.is_issued("https://nowhere")

    async def test_register_then_verify(self, registry, make_article):
        article = make_article(1, content="body")
        await registry.register([article])
        assert await registry.is_issued(article.url)
        assert await registry.verify(article)

    async def test_modified_article_fails(self, registry, make_article):
        article = make_article(1, content="body")
        await registry.register([article])
        assert not await registry.verify(article.model_copy(update={"title": "x"}))

    async def test_reregister_replaces(self, registry, make_article):
        old, new = make_article(1, content="old"), make_article(1, content="new")
        await registry.register([old])
        await registry.register([new])
        assert await registry.verify(new)
        assert not await registry.verify(old)

    async def test_duplicate_urls_in_one_batch(self, registry, make_article):
        first, last = make_article(1, content="first"), make_article(1, content="last")
        await registry.register([first, last])
        assert await registry.verify(last)

    async def test_empty_register(self, registry):
        await registry.register([])


# --- AnalysisCache contract ---------------------------------------------------


@pytest.fixture(params=["memory", "sql"])
def cache(request, db) -> AnalysisCache:
    return InMemoryAnalysisCache() if request.param == "memory" else SqlAnalysisCache(db, model="m")


class TestAnalysisCacheContract:
    async def test_miss(self, cache):
        assert await cache.get("https://nowhere") is None

    async def test_put_then_get(self, cache):
        await cache.put("u", _analysis())
        assert await cache.get("u") == _analysis()

    async def test_partial_analysis(self, cache):
        await cache.put("u", ArticleAnalysis(summary="only summary"))
        got = await cache.get("u")
        assert got.summary == "only summary" and got.bias is None

    async def test_get_many_returns_only_stored(self, cache):
        await cache.put("a", _analysis(summary="A"))
        await cache.put("b", ArticleAnalysis(summary="B"))
        found = await cache.get_many(["a", "b", "missing", "a"])
        assert set(found) == {"a", "b"}
        assert found["a"].summary == "A" and found["b"].bias is None
        assert await cache.get_many([]) == {}

    async def test_returned_value_is_a_copy(self, cache):
        await cache.put("u", _analysis())
        got = await cache.get("u")
        got.summary = "mutated"
        assert (await cache.get("u")).summary == "s"


# --- SQL specifics --------------------------------------------------------------


class TestSqlPersistence:
    async def test_survives_restart(self, db_url, make_article):
        article = make_article(1, content="body")
        first = Database(DatabaseConfig(url=db_url))
        await first.connect()
        await SqlArticleRegistry(first).register([article])
        await SqlAnalysisCache(first, model="m").put(article.url, _analysis())
        await first.close()

        second = Database(DatabaseConfig(url=db_url))
        await second.connect()
        assert await SqlArticleRegistry(second).verify(article)
        assert await SqlAnalysisCache(second, model="m").get(article.url) == _analysis()
        await second.close()

    async def test_registry_tracks_first_and_last_seen(self, db, make_article):
        registry = SqlArticleRegistry(db)
        article = make_article(1, content="body")
        await registry.register([article])
        await registry.register([article])
        async with db.session() as session:
            row = await session.get(ArticleRow, article.url)
        assert row.first_seen_at <= row.last_seen_at
        assert row.content == "body" and row.source_name == article.source_name


class TestSqlCacheVersioning:
    async def test_summary_prompt_change_invalidates_only_summary(self, db):
        await SqlAnalysisCache(db, model="m", summary_version="v1", bias_version="b1").put(
            "u", _analysis()
        )
        got = await SqlAnalysisCache(db, model="m", summary_version="v2", bias_version="b1").get("u")
        assert got.summary is None
        assert got.bias.label == "Political"

    async def test_bias_prompt_change_invalidates_only_bias(self, db):
        await SqlAnalysisCache(db, model="m", summary_version="v1", bias_version="b1").put(
            "u", _analysis()
        )
        got = await SqlAnalysisCache(db, model="m", summary_version="v1", bias_version="b2").get("u")
        assert got.summary == "s" and got.bias is None

    async def test_everything_stale_reads_as_miss(self, db):
        await SqlAnalysisCache(db, model="m", summary_version="v1", bias_version="b1").put(
            "u", _analysis()
        )
        stale = SqlAnalysisCache(db, model="m", summary_version="v2", bias_version="b2")
        assert await stale.get("u") is None

    async def test_get_many_applies_versions(self, db):
        old = SqlAnalysisCache(db, model="m", summary_version="v1", bias_version="b1")
        await old.put("fresh-bias", _analysis())
        await old.put("all-stale", ArticleAnalysis(summary="s"))
        current = SqlAnalysisCache(db, model="m", summary_version="v2", bias_version="b1")
        found = await current.get_many(["fresh-bias", "all-stale"])
        assert set(found) == {"fresh-bias"}
        assert found["fresh-bias"].summary is None
        assert found["fresh-bias"].bias.label == "Political"

    async def test_model_change_does_not_invalidate(self, db):
        await SqlAnalysisCache(db, model="groq-model").put("u", _analysis())
        assert await SqlAnalysisCache(db, model="azure-model").get("u") == _analysis()

    async def test_records_model_and_keeps_untouched_part(self, db):
        await SqlAnalysisCache(db, model="first").put("u", _analysis())
        # Recompute only the bias with another model; the summary row stays as it was.
        await SqlAnalysisCache(db, model="second").put(
            "u", ArticleAnalysis(summary="s", bias=BiasAssessment(label="Economic", explanation="x"))
        )
        async with db.session() as session:
            row = await session.get(AnalysisRow, "u")
        assert (row.summary_model, row.bias_model) == ("first", "second")
        assert row.bias_label == "Economic"

    async def test_real_prompt_versions_are_used_by_default(self, db):
        from backend.workflows import prompts

        await SqlAnalysisCache(db, model="m").put("u", _analysis())
        async with db.session() as session:
            row = (await session.scalars(select(AnalysisRow))).one()
        assert (row.summary_version, row.bias_version) == (
            prompts.SUMMARY_VERSION,
            prompts.BIAS_VERSION,
        )


class TestRegisterReportsNewArticles:
    async def test_counts_only_never_issued_urls(self, registry, make_article):
        a, b, c = (make_article(i) for i in range(3))
        assert await registry.register([a, b]) == 2
        assert await registry.register([a, b, c]) == 1  # only c is new
        assert await registry.register([c, c]) == 0  # duplicates count once
        assert await registry.register([]) == 0
