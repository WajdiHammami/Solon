"""Shared fixtures and lightweight fakes for the backend test suite.

Nothing here touches the network, a real LLM, or real API keys — external
collaborators are replaced with in-memory fakes so the tests run fast and
deterministically.
"""

import json

import pytest

from backend.llm.base import LLMClient
from backend.llm.models import GenerationResponse, LLMConfig
from backend.models import Article
from backend.workflows import prompts

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
