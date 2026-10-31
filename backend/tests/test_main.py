"""Tests for the FastAPI routes in ``backend.main``.

Providers and workflows are overridden with fakes built on a scripted LLM, so
the routes are exercised without real providers, an LLM, or keys.
"""

import pytest

from backend.llm.errors import LLMRateLimitError
from backend.main import app, get_providers
from backend.news_providers.base import DEFAULT_PAGE_SIZE
from backend.tests.conftest import SCRAPED, FakeProvider, ScriptedLLM

@pytest.fixture
def client(make_client):
    return make_client()[0]


def _article_payload(id, **overrides):
    return {
        "id": id,
        "title": f"t{id}",
        "url": f"https://example.com/{id}",
        "source_name": "S",
        "published_at": "2024-01-01T00:00:00Z",
        **overrides,
    }


def test_health(client):
    resp = client.get("/health")
    assert resp.status_code == 200
    assert resp.json() == {"status": "healthy"}


class TestFeed:
    def test_returns_articles(self, client):
        resp = client.get("/feed", params={"topic": "tech"})
        assert resp.status_code == 200
        body = resp.json()
        assert len(body) == 1
        assert body[0]["title"] == "A"

    def test_forwards_paging_params(self, client, fake_provider):
        client.get("/feed", params={"topic": "tech", "page_size": 5, "page": 2})
        call = fake_provider.fetch_calls[0]
        assert call["query"] == "tech"
        assert call["page_size"] == 5
        assert call["page"] == 2

    @pytest.mark.parametrize("params", [{}, {"topic": ""}, {"topic": "   "}])
    def test_missing_or_blank_topic_returns_top_headlines(
        self, client, fake_provider, params
    ):
        resp = client.get("/feed", params=params)
        assert resp.status_code == 200
        assert fake_provider.fetch_calls == []
        assert len(fake_provider.headline_calls) == 1

    def test_topic_is_trimmed(self, client, fake_provider):
        client.get("/feed", params={"topic": "  tech  "})
        assert fake_provider.fetch_calls[0]["query"] == "tech"

    def test_default_page_size_matches_client(self, client, fake_provider):
        client.get("/feed", params={"topic": "tech"})
        assert fake_provider.fetch_calls[0]["page_size"] == DEFAULT_PAGE_SIZE == 5

    @pytest.mark.parametrize(
        "params", [{"page_size": 0}, {"page_size": 101}, {"page": 0}]
    )
    def test_rejects_out_of_range_paging(self, client, params):
        assert client.get("/feed", params=params).status_code == 422

    def test_ids_unique_across_providers(self, make_client, fake_provider):
        client, _ = make_client()
        app.dependency_overrides[get_providers] = lambda: [
            fake_provider,
            FakeProvider(title="B"),
        ]
        body = client.get("/feed", params={"topic": "tech"}).json()
        assert [a["id"] for a in body] == [0, 1]
        assert [a["title"] for a in body] == ["A", "B"]


class TestAnalyze:
    def test_returns_batch_analysis(self, client):
        resp = client.post(
            "/analyze", json={"articles": [_article_payload(1), _article_payload(2)]}
        )
        assert resp.status_code == 200
        body = resp.json()
        assert body["analyses"]["1"]["summary"] == "summary of t1"
        assert body["analyses"]["2"]["bias"]["label"] == "Political"
        assert body["synthesis"] == "synthesis text"
        assert body["sources"] == [1, 2]
        assert body["failed"] == []
        assert body["skipped"] == []

    def test_reports_partial_failures(self, make_client):
        llm = ScriptedLLM(fail={("summarize", "t2"): LLMRateLimitError("slow")})
        client, _ = make_client(llm)
        resp = client.post(
            "/analyze", json={"articles": [_article_payload(1), _article_payload(2)]}
        )
        assert resp.status_code == 200
        body = resp.json()
        assert body["sources"] == [1]
        [failure] = body["failed"]
        assert failure["task"] == "summarize"
        assert failure["article_id"] == 2
        assert failure["retryable"] is True

    def test_reports_budget_skips(self, make_client):
        client, _ = make_client(max_tokens=10_000)
        resp = client.post(
            "/analyze", json={"articles": [_article_payload(i) for i in range(3)]}
        )
        assert resp.json()["skipped"] == [1, 2]

    def test_rejects_empty_list(self, client):
        assert client.post("/analyze", json={"articles": []}).status_code == 422

    def test_single_article(self, client):
        resp = client.post("/analyze/article", json=_article_payload(1))
        assert resp.status_code == 200
        body = resp.json()
        assert body["analysis"]["summary"] == "summary of t1"
        assert body["analysis"]["bias"]["explanation"] == "Charged language."
        assert body["failures"] == []

    def test_scrapes_short_content(self, client, fake_provider):
        client.post("/analyze/article", json=_article_payload(1))
        assert fake_provider.extract_calls == ["https://example.com/1"]

    def test_skips_scrape_when_content_present(self, client, fake_provider):
        client.post("/analyze/article", json=_article_payload(1, content="x" * 1000))
        assert fake_provider.extract_calls == []

    def test_repeat_request_served_from_cache(self, make_client, fake_provider):
        client, llm = make_client()
        client.post("/analyze/article", json=_article_payload(1))
        calls = len(llm.requests)
        client.post("/analyze/article", json=_article_payload(1))
        assert len(llm.requests) == calls
        assert fake_provider.extract_calls == ["https://example.com/1"]


def test_get_content(client):
    resp = client.get("/article/content", params={"url": "https://example.com/x"})
    assert resp.status_code == 200
    assert resp.json() == SCRAPED
