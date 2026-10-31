"""Every NewsProvider must keep the interface's signatures.

Provider-specific options are allowed only after the shared parameters, and
only as keyword-only arguments with defaults, so callers written against
:class:`NewsProvider` work with any provider.
"""

import inspect

import pytest

from backend.news_providers.base import NewsProvider
from backend.news_providers.newsapi_provider import NewsAPIProvider

PROVIDERS = [NewsAPIProvider]
METHODS = ["fetch_articles", "fetch_top_headlines", "extract_content"]


@pytest.mark.parametrize("provider_cls", PROVIDERS)
@pytest.mark.parametrize("method", METHODS)
def test_signature_matches_interface(provider_cls, method):
    base = list(inspect.signature(getattr(NewsProvider, method)).parameters.values())
    impl = list(inspect.signature(getattr(provider_cls, method)).parameters.values())

    shared = [(p.name, p.kind, p.default) for p in base]
    assert [(p.name, p.kind, p.default) for p in impl[: len(base)]] == shared

    for extra in impl[len(base) :]:
        assert extra.kind is inspect.Parameter.KEYWORD_ONLY, extra.name
        assert extra.default is not inspect.Parameter.empty, extra.name
