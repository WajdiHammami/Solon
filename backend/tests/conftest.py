"""Shared fixtures and lightweight fakes for the backend test suite.

Nothing here touches the network, a real LLM, or real API keys — external
collaborators are replaced with in-memory fakes so the tests run fast and
deterministically.
"""

import json

import pytest
from fastapi.testclient import TestClient

import asyncio

from backend import main
from backend.article_registry import InMemoryArticleRegistry
from backend.cache.memory import InMemoryAnalysisCache
from backend.llm.base import LLMClient
from backend.llm.models import GenerationResponse, LLMConfig
from backend.main import (
    app,
    get_article_workflow,
    get_batch_workflow,
    get_providers,
    get_registry,
)
from backend.models import Article
from backend.news_providers.base import DEFAULT_PAGE_SIZE, NewsProvider
from backend.workflows import prompts
from backend.workflows.article_workflow import ArticleWorkflow
from backend.workflows.batch_workflow import BatchWorkflow

BIAS_JSON = json.dumps({"label": "Political", "explanation": "Charged language."})


@pytest.fixture
def anyio_backend():
    return "asyncio"


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


class ScriptedLLM(LLMClient):
    """Answers by task (recognised from the system prompt) and records calls.

    ``fail`` maps ``(task, article title)`` to an error to raise instead;
    use ``"*"`` as the title to fail that task for every article.
    """

    def __init__(self, bias_reply=BIAS_JSON, fail=None):
        self.bias_reply = bias_reply
        self.fail = fail or {}
        self.requests = []

    @property
    def config(self):
        return LLMConfig(model="scripted")

    def task_calls(self, task):
        return [r for r in self.requests if self.task_of(r) == task]

    @staticmethod
    def task_of(request):
        system = request.messages[0].content
        if system == prompts.BIAS_SYSTEM:
            return "detect_bias"
        if system == prompts.SYNTHESIZE_SYSTEM:
            return "synthesize"
        return "summarize"

    @staticmethod
    def _title(request):
        body = request.messages[1].content
        return body.split("Title: ")[1].split("\n")[0] if "Title: " in body else ""

    def invoke(self, request):
        self.requests.append(request)
        task, title = self.task_of(request), self._title(request)
        error = self.fail.get((task, title)) or self.fail.get((task, "*"))
        if error:
            raise error
        if task == "detect_bias":
            content = self.bias_reply
        elif task == "synthesize":
            content = "synthesis text"
        else:
            content = f"summary of {title}"
        return GenerationResponse(content=content, model="scripted")

    async def ainvoke(self, request):
        return self.invoke(request)

    def stream(self, request):
        yield self.invoke(request).content

    async def astream(self, request):
        yield self.invoke(request).content


@pytest.fixture
def llm():
    return ScriptedLLM()


# --- API fixtures -----------------------------------------------------------

SCRAPED = "Scraped full article body. " * 40  # well over the scrape threshold


class FakeProvider(NewsProvider):
    def __init__(self, title="A"):
        self.title = title
        self.fetch_calls = []
        self.headline_calls = []
        self.extract_calls = []

    def _articles(self):
        return [
            Article(
                id=0,
                title=self.title,
                url=f"https://example.com/{self.title}",
                source_name="S",
                published_at="2024-01-01T00:00:00Z",
            )
        ]

    def fetch_articles(self, query, page_size=DEFAULT_PAGE_SIZE, page=1):
        self.fetch_calls.append({"query": query, "page_size": page_size, "page": page})
        return self._articles()

    def fetch_top_headlines(self, page_size=DEFAULT_PAGE_SIZE, page=1):
        self.headline_calls.append({"page_size": page_size, "page": page})
        return self._articles()

    def extract_content(self, url):
        self.extract_calls.append(url)
        return SCRAPED


@pytest.fixture
def fake_provider():
    return FakeProvider()


@pytest.fixture
def registry():
    return InMemoryArticleRegistry()


@pytest.fixture
def issue(registry):
    """Register article payloads as if ``/feed`` had returned them."""

    def _issue(*payloads: dict) -> list[dict]:
        asyncio.run(registry.register([Article(**p) for p in payloads]))
        return list(payloads)

    return _issue


@pytest.fixture
def make_client(fake_provider, registry, monkeypatch):
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
        app.dependency_overrides[get_registry] = lambda: registry
        client = TestClient(app)
        client.__enter__()
        clients.append(client)
        return client, llm

    yield _make
    for client in clients:
        client.__exit__(None, None, None)
    app.dependency_overrides.clear()
