"""Tests for the NewsAPI provider.

The unit tests replace the NewsAPI HTTP client and newspaper3k scraper with
fakes, so they run offline. The integration test at the bottom hits the live
NewsAPI and is skipped unless a key is configured.
"""

import pytest

from backend.config import get_settings
from backend.models import Article
from backend.news_providers import newsapi_provider as provider_module
from backend.news_providers.newsapi_provider import NewsAPIProvider


def _ok_response(*titles, description=None, content=None):
    return {
        "status": "ok",
        "articles": [
            {
                "title": t,
                "url": f"https://example.com/{t}",
                "source": {"name": f"Source {t}"},
                "publishedAt": "2024-01-01T00:00:00Z",
                "description": description,
                "content": content,
            }
            for t in titles
        ],
    }


class FakeNewsApiClient:
    """Captures calls and returns scripted ``get_everything`` responses."""

    def __init__(self, responses):
        self._responses = list(responses)
        self.calls = []

    def get_everything(self, **kwargs):
        self.calls.append(kwargs)
        return self._responses.pop(0)


@pytest.fixture
def provider():
    # api_key is never used because we swap the client out below.
    p = NewsAPIProvider(api_key="dummy")
    return p


class TestFetchArticles:
    def test_maps_response_to_articles(self, provider):
        provider.newsapi = FakeNewsApiClient([_ok_response("A", "B")])
        articles = provider.fetch_articles("tech")
        assert len(articles) == 2
        assert all(isinstance(a, Article) for a in articles)
        assert articles[0].title == "A"
        assert articles[0].source_name == "Source A"

    def test_ids_are_unique_across_multiple_queries(self, provider):
        provider.newsapi = FakeNewsApiClient([_ok_response("A"), _ok_response("B", "C")])
        articles = provider.fetch_articles(["q1", "q2"])
        ids = [a.id for a in articles]
        assert ids == [0, 1, 2]
        assert len(set(ids)) == len(ids)

    def test_error_status_is_skipped(self, provider):
        provider.newsapi = FakeNewsApiClient(
            [{"status": "error", "message": "rate limited"}]
        )
        assert provider.fetch_articles("tech") == []

    def test_passes_paging_params_to_client(self, provider):
        client = FakeNewsApiClient([_ok_response("A")])
        provider.newsapi = client
        provider.fetch_articles("tech", page_size=7, page=3)
        assert client.calls[0]["page_size"] == 7
        assert client.calls[0]["page"] == 3

    def test_captures_snippet_as_baseline_content(self, provider):
        provider.newsapi = FakeNewsApiClient(
            [_ok_response("A", description="A short blurb.", content="Truncated body…")]
        )
        article = provider.fetch_articles("tech")[0]
        assert "A short blurb." in article.content
        assert "Truncated body…" in article.content

    def test_content_is_none_when_snippet_absent(self, provider):
        provider.newsapi = FakeNewsApiClient([_ok_response("A")])
        assert provider.fetch_articles("tech")[0].content is None


class TestExtractContent:
    def test_returns_parsed_text(self, provider, monkeypatch):
        class FakeNewspaperArticle:
            def __init__(self, url):
                self.url = url
                self.text = ""

            def download(self):
                pass

            def parse(self):
                self.text = "Full article body."

        monkeypatch.setattr(provider_module, "NewspaperArticle", FakeNewspaperArticle)
        assert provider.extract_content("https://example.com/a") == "Full article body."

    def test_returns_empty_string_on_error(self, provider, monkeypatch):
        def boom(url):
            raise RuntimeError("network down")

        monkeypatch.setattr(provider_module, "NewspaperArticle", boom)
        assert provider.extract_content("https://example.com/a") == ""


@pytest.mark.integration
def test_news_api_provider_live():
    api_key = get_settings().newsapi_key
    if not api_key:
        pytest.skip("NEWSAPI_KEY not configured")

    provider = NewsAPIProvider(api_key=api_key)
    articles = provider.fetch_articles(query="technology")
    assert isinstance(articles, list)
    assert len(articles) > 0
    assert len({a.id for a in articles}) == len(articles)
