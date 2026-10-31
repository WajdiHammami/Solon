"""Tests for the FastAPI routes in ``backend.main``.

The ``get_providers`` and ``get_summarizer`` dependencies are overridden with
fakes, so the routes are exercised without real providers, an LLM, or keys.
"""

import pytest
from fastapi.testclient import TestClient

from backend.main import app, get_providers, get_summarizer
from backend.models import Article


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
        return "Scraped full article body. " * 40  # well over the hydration threshold


class FakeSummarizer:
    def __init__(self):
        self.received = None

    def run_batch_summarization(self, articles):
        self.received = articles
        return {
            "summaries": [f"summary {a.id}" for a in articles],
            "synthesis": "synthesis text",
            "tags": {a.id: ("Political", "explanation") for a in articles},
        }

    def run_singular_summarization(self, article, config):
        self.received = [article]
        article.summary = "single summary"
        article.tag = "Neutral"
        return {"article": article}


@pytest.fixture
def fake_provider():
    return FakeProvider()


@pytest.fixture
def fake_summarizer():
    return FakeSummarizer()


@pytest.fixture
def client(fake_provider, fake_summarizer):
    app.dependency_overrides[get_providers] = lambda: [fake_provider]
    app.dependency_overrides[get_summarizer] = lambda: fake_summarizer
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.clear()


def _article_payload(id):
    return {
        "id": id,
        "title": f"t{id}",
        "url": f"https://example.com/{id}",
        "source_name": "S",
        "published_at": "2024-01-01T00:00:00Z",
    }


def test_health(client):
    resp = client.get("/health")
    assert resp.status_code == 200
    assert resp.json() == {"status": "healthy"}


def test_feed_returns_articles(client):
    resp = client.get("/feed", params={"topic": "tech"})
    assert resp.status_code == 200
    body = resp.json()
    assert len(body) == 1
    assert body[0]["title"] == "A"


def test_feed_forwards_paging_params(client, fake_provider):
    client.get("/feed", params={"topic": "tech", "page_size": 5, "page": 2})
    call = fake_provider.fetch_calls[0]
    assert call["query"] == "tech"
    assert call["page_size"] == 5
    assert call["page"] == 2


def test_feed_defaults_topic_when_missing(client, fake_provider):
    client.get("/feed")
    assert fake_provider.fetch_calls[0]["query"] == "Top headlines"


def test_summarize_single_article_returns_article(client):
    resp = client.post("/summarize", json={"articles": [_article_payload(1)]})
    assert resp.status_code == 200
    body = resp.json()
    # a single article returns the summarized Article (bug fix: summary present)
    assert body["id"] == 1
    assert body["summary"] == "single summary"
    assert body["tag"] == "Neutral"


def test_summarize_batch_returns_response(client):
    resp = client.post(
        "/summarize",
        json={"articles": [_article_payload(1), _article_payload(2)]},
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["summaries"] == ["summary 1", "summary 2"]
    assert body["synthesis"] == "synthesis text"
    assert body["tags"]["1"] == ["Political", "explanation"]


def test_summarize_hydrates_missing_content(client, fake_provider, fake_summarizer):
    # Article has no content -> the endpoint should scrape it before summarizing.
    client.post("/summarize", json={"articles": [_article_payload(1)]})
    assert fake_provider.extract_calls == ["https://example.com/1"]
    assert fake_summarizer.received[0].content.startswith("Scraped full article body.")


def test_summarize_skips_scrape_when_content_present(
    client, fake_provider, fake_summarizer
):
    payload = _article_payload(1)
    payload["content"] = "x" * 1000  # already above the hydration threshold
    client.post("/summarize", json={"articles": [payload]})
    assert fake_provider.extract_calls == []  # no scrape needed
    assert fake_summarizer.received[0].content == "x" * 1000


def test_get_content(client):
    resp = client.get("/article/content", params={"url": "https://example.com/x"})
    assert resp.status_code == 200
    assert resp.json() == "Scraped full article body. " * 40
