"""Tests for article fingerprinting and issued-article verification."""

import pytest

from backend.article_registry import InMemoryArticleRegistry, article_fingerprint
from backend.news_providers.base import NewsProviderError
from backend.request_context import REQUEST_ID_HEADER

pytestmark = pytest.mark.anyio


class TestFingerprint:
    def test_covers_title_content_and_source(self, make_article):
        base = make_article(1, content="body")
        for field, value in [("title", "x"), ("content", "x"), ("source_name", "x")]:
            changed = base.model_copy(update={field: value})
            assert article_fingerprint(changed) != article_fingerprint(base), field

    def test_ignores_id_date_and_analysis_fields(self, make_article):
        base = make_article(1, content="body")
        changed = base.model_copy(
            update={
                "id": 99,
                "published_at": "2030-01-01T00:00:00Z",
                "summary": "s",
                "tag": "t",
            }
        )
        assert article_fingerprint(changed) == article_fingerprint(base)

    def test_null_and_empty_content_match(self, make_article):
        assert article_fingerprint(make_article(1, content=None)) == article_fingerprint(
            make_article(1, content="")
        )


class TestInMemoryRegistry:
    async def test_verifies_issued_article(self, make_article):
        registry = InMemoryArticleRegistry()
        article = make_article(1, content="body")
        await registry.register([article])
        assert await registry.is_issued(article.url)
        assert await registry.verify(article)

    async def test_rejects_unknown_url(self, make_article):
        registry = InMemoryArticleRegistry()
        await registry.register([make_article(1)])
        assert not await registry.verify(make_article(1, url="https://evil.example/x"))
        assert not await registry.is_issued("https://evil.example/x")

    async def test_rejects_other_articles_text_under_issued_url(self, make_article):
        registry = InMemoryArticleRegistry()
        a, b = make_article(1, content="real"), make_article(2, content="other")
        await registry.register([a, b])
        assert not await registry.verify(b.model_copy(update={"url": a.url}))

    async def test_reregistering_replaces_fingerprint(self, make_article):
        registry = InMemoryArticleRegistry()
        old = make_article(1, content="old")
        new = make_article(1, content="updated by the source")
        await registry.register([old])
        await registry.register([new])
        assert await registry.verify(new)
        assert not await registry.verify(old)

    async def test_evicts_oldest_past_capacity(self, make_article):
        registry = InMemoryArticleRegistry(max_entries=2)
        articles = [make_article(i) for i in range(3)]
        await registry.register(articles)
        assert not await registry.is_issued(articles[0].url)
        assert await registry.is_issued(articles[2].url)


# --- API ----------------------------------------------------------------------


@pytest.fixture
def client(make_client):
    return make_client()[0]


def _fetch_feed(client):
    resp = client.get("/feed", params={"topic": "tech"})
    assert resp.status_code == 200
    return resp.json()


def test_feed_articles_can_be_analyzed_as_returned(client):
    articles = _fetch_feed(client)
    assert client.post("/analyze", json={"articles": articles}).status_code == 200
    assert client.post("/analyze/article", json=articles[0]).status_code == 200


@pytest.mark.parametrize(
    "field, value",
    [("title", "Forged"), ("content", "planted text"), ("source_name", "Fake")],
)
def test_modified_article_is_rejected(client, field, value):
    article = _fetch_feed(client)[0]
    article[field] = value
    resp = client.post("/analyze/article", json=article)
    assert resp.status_code == 403
    assert "search again" in resp.json()["detail"]["message"]
    assert resp.json()["detail"]["article_ids"] == [article["id"]]


def test_unknown_url_is_rejected(client):
    article = _fetch_feed(client)[0]
    article["url"] = "http://169.254.169.254/latest/meta-data"
    assert client.post("/analyze/article", json=article).status_code == 403


def test_one_bad_article_rejects_the_batch(client, fake_provider):
    articles = _fetch_feed(client)
    forged = dict(articles[0], url="https://evil.example/x", id=5)
    resp = client.post("/analyze", json={"articles": articles + [forged]})
    assert resp.status_code == 403
    assert resp.json()["detail"]["article_ids"] == [5]


def test_client_side_changes_to_ignored_fields_are_allowed(client):
    article = _fetch_feed(client)[0]
    article.update(id=42, summary="client summary", tag="client tag")
    assert client.post("/analyze/article", json=article).status_code == 200


def test_content_requires_an_issued_url(client, fake_provider):
    resp = client.get("/article/content", params={"url": "http://localhost:22/"})
    assert resp.status_code == 403
    assert fake_provider.extract_calls == []  # never fetched

    url = _fetch_feed(client)[0]["url"]
    assert client.get("/article/content", params={"url": url}).status_code == 200


def test_feed_provider_failure_is_a_502_with_message(client, fake_provider):
    def failing(*args, **kwargs):
        raise NewsProviderError("NewsAPI error: rate limited")

    fake_provider.fetch_articles = failing
    resp = client.get("/feed", params={"topic": "tech"})
    assert resp.status_code == 502
    assert resp.json()["detail"]["message"] == "NewsAPI error: rate limited"


def test_unhandled_error_is_a_json_500_with_request_id(client, fake_provider):
    def broken(*args, **kwargs):
        raise RuntimeError("bug")

    fake_provider.fetch_top_headlines = broken
    resp = client.get("/feed", headers={REQUEST_ID_HEADER: "req-500"})
    assert resp.status_code == 500
    assert resp.json()["detail"] == {
        "message": "Internal server error",
        "request_id": "req-500",
    }
    assert resp.headers[REQUEST_ID_HEADER] == "req-500"
