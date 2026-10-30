"""Shared fixtures and lightweight fakes for the backend test suite.

Nothing here touches the network, a real LLM, or real API keys — external
collaborators are replaced with in-memory fakes so the tests run fast and
deterministically.
"""

from types import SimpleNamespace

import pytest

from backend.models import Article


@pytest.fixture
def make_article():
    """Factory for :class:`Article` instances with sensible defaults."""

    def _make(id: int = 0, **overrides) -> Article:
        data = {
            "id": id,
            "title": f"Title {id}",
            "url": f"https://example.com/{id}",
            "source_name": f"Source {id}",
            "published_at": "2024-01-01T00:00:00Z",
        }
        data.update(overrides)
        return Article(**data)

    return _make


def _default_llm_responder(messages) -> str:
    """Return a canned LLM reply based on the prompt's intent."""
    system = messages[0].content
    if "Detect any potential bias" in system:
        return "Bias Detected: [Political] The piece leans on charged language."
    if "unified analysis" in system:
        return "All sources agree the event occurred; framing differs by outlet."
    return "This is a neutral three-sentence summary of the article."


class FakeLLM:
    """Stand-in for ``ChatGroq``: records calls, returns scripted content."""

    def __init__(self, responder=None):
        self._responder = responder or _default_llm_responder
        self.calls: list = []

    def invoke(self, messages):
        self.calls.append(messages)
        return SimpleNamespace(content=self._responder(messages))


@pytest.fixture
def fake_llm():
    return FakeLLM()


@pytest.fixture
def make_llm():
    """Factory for a :class:`FakeLLM` with a custom response function."""

    def _make(responder=None):
        return FakeLLM(responder)

    return _make
