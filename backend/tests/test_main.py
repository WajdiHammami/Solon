"""Tests for the FastAPI routes in ``backend.main``.

Providers and workflows are overridden with fakes built on a scripted LLM, so
the routes are exercised without real providers, an LLM, or keys.
"""

import pytest
from fastapi.testclient import TestClient

from backend import main
from backend.cache.memory import InMemoryAnalysisCache
from backend.llm.errors import LLMAuthenticationError, LLMRateLimitError
from backend.main import app, get_article_workflow, get_batch_workflow, get_providers
from backend.models import Article
from backend.tests.conftest import ScriptedLLM
from backend.workflows.article_workflow import ArticleWorkflow
from backend.workflows.batch_workflow import BatchWorkflow

SCRAPED = "Scraped full article body. " * 40  # well over the scrape threshold


class FakeProvider:
    def __init__(self):
        self.fetch_calls = []
        self.extract_calls = []

    def fetch_articles(self, query, page_size=40, page=1):
        self.fetch_calls.append({"query": query, "page_size": page_size, "page": page})
        return [
            Article(
                id=0,
                title="A",
                url="https://example.com/a",
                source_name="S",
                published_at="2024-01-01T00:00:00Z",
            )
        ]

    def extract_content(self, url):
        self.extract_calls.append(url)
        return SCRAPED


@pytest.fixture
def fake_provider():
    return FakeProvider()


@pytest.fixture
def make_client(fake_provider, monkeypatch):
    """Build a TestClient whose workflows run on the given scripted LLM."""
    # Startup would otherwise configure logging to write into backend/logs.
    monkeypatch.setattr(main, "configure_logging", lambda *a, **k: None)
    clients = []

    def _make(llm=None, max_tokens=None):
        llm = llm or ScriptedLLM()

        async def load_content(url):
            return fake_provider.extract_content(url)

        article_workflow = ArticleWorkflow(
            llm, InMemoryAnalysisCache(), content_loader=load_content
        )
        batch_workflow = BatchWorkflow(llm, article_workflow, max_tokens=max_tokens)
        app.dependency_overrides[get_providers] = lambda: [fake_provider]
        app.dependency_overrides[get_article_workflow] = lambda: article_workflow
        app.dependency_overrides[get_batch_workflow] = lambda: batch_workflow
        client = TestClient(app)
        client.__enter__()
        clients.append(client)
        return client, llm

    yield _make
    for client in clients:
        client.__exit__(None, None, None)
    app.dependency_overrides.clear()


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

    def test_defaults_topic_when_missing(self, client, fake_provider):
        client.get("/feed")
        assert fake_provider.fetch_calls[0]["query"] == "Top headlines"


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


class TestLegacySummarize:
    def test_single_article_returns_article(self, client):
        resp = client.post("/summarize", json={"articles": [_article_payload(1)]})
        assert resp.status_code == 200
        body = resp.json()
        assert body["id"] == 1
        assert body["summary"] == "summary of t1"
        assert body["tag"] == "Political"

    def test_batch_returns_summaries_in_request_order(self, client):
        resp = client.post(
            "/summarize",
            json={"articles": [_article_payload(2), _article_payload(1)]},
        )
        assert resp.status_code == 200
        body = resp.json()
        assert body["summaries"] == ["summary of t2", "summary of t1"]
        assert body["synthesis"] == "synthesis text"
        assert body["tags"]["1"] == ["Political", "Charged language."]

    def test_batch_pads_missing_summaries(self, make_client):
        llm = ScriptedLLM(fail={("summarize", "t1"): LLMRateLimitError("slow")})
        client, _ = make_client(llm)
        resp = client.post(
            "/summarize",
            json={"articles": [_article_payload(1), _article_payload(2)]},
        )
        assert resp.json()["summaries"] == ["", "summary of t2"]

    def test_502_when_nothing_produced(self, make_client):
        error = LLMAuthenticationError("bad key")
        llm = ScriptedLLM(fail={("summarize", "*"): error, ("detect_bias", "*"): error})
        client, _ = make_client(llm)
        resp = client.post("/summarize", json={"articles": [_article_payload(1)]})
        assert resp.status_code == 502
        failures = resp.json()["detail"]["failures"]
        assert {f["task"] for f in failures} == {"summarize", "detect_bias"}

    def test_rejects_empty_list(self, client):
        assert client.post("/summarize", json={"articles": []}).status_code == 422

    def test_marked_deprecated(self, client):
        schema = client.get("/openapi.json").json()
        assert schema["paths"]["/summarize"]["post"]["deprecated"] is True


def test_get_content(client):
    resp = client.get("/article/content", params={"url": "https://example.com/x"})
    assert resp.status_code == 200
    assert resp.json() == SCRAPED
