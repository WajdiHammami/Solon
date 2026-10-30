"""Tests for the Pydantic models in ``backend.models``."""

from datetime import datetime

import pytest
from pydantic import ValidationError

from backend.models import Article, Profile, Source, SummarizeRequest, SummarizeResponse


class TestArticle:
    def test_minimal_valid_article(self):
        article = Article(
            id=1,
            title="Headline",
            url="https://example.com/a",
            source_name="Example",
            published_at="2024-01-01T12:00:00Z",
        )
        assert article.id == 1
        assert isinstance(article.published_at, datetime)
        # optional fields default to None
        assert article.tag is None
        assert article.content is None
        assert article.summary is None

    def test_missing_required_field_raises(self):
        with pytest.raises(ValidationError):
            Article(id=1, title="x", url="https://e.com", source_name="E")  # no published_at

    def test_invalid_date_raises(self):
        with pytest.raises(ValidationError):
            Article(
                id=1,
                title="x",
                url="https://e.com",
                source_name="E",
                published_at="not-a-date",
            )


class TestProfile:
    def test_profile_with_sources(self):
        profile = Profile(
            sources=[Source(name="BBC", url="https://bbc.co.uk", enabled=True)],
            topics=["tech"],
            newsapi_enabled=True,
        )
        assert profile.sources[0].name == "BBC"
        assert profile.topics == ["tech"]

    def test_source_requires_enabled_flag(self):
        with pytest.raises(ValidationError):
            Source(name="BBC", url="https://bbc.co.uk")


class TestSummarizeSchemas:
    def test_summarize_request_wraps_articles(self):
        req = SummarizeRequest(
            articles=[
                {
                    "id": 1,
                    "title": "t",
                    "url": "https://e.com",
                    "source_name": "E",
                    "published_at": "2024-01-01T00:00:00Z",
                }
            ]
        )
        assert len(req.articles) == 1
        assert isinstance(req.articles[0], Article)

    def test_summarize_response_defaults(self):
        resp = SummarizeResponse(summaries=["a", "b"])
        assert resp.summaries == ["a", "b"]
        assert resp.synthesis is None
        assert resp.tags is None

    def test_summarize_response_tags_shape(self):
        resp = SummarizeResponse(
            summaries=["a"],
            synthesis="synth",
            tags={1: ("Political", "leans left")},
        )
        assert resp.tags[1] == ("Political", "leans left")
