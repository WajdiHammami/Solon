"""Token-usage accounting for LLM calls.

- :class:`UsageRecordingLLM` totals the usage of every call through one
  wrapper instance (used by offline scripts such as the evaluation).
- :class:`MeteredLLM` + :func:`track_usage` total the usage of the calls made
  *within the current context* — e.g. one API request — even when the same
  client is shared by concurrent requests. The tally lives in a ContextVar,
  which LangGraph tasks and worker threads inherit, so every call made on
  behalf of the request is counted once.
"""

from collections.abc import AsyncIterator, Iterator
from contextlib import contextmanager
from contextvars import ContextVar
from dataclasses import dataclass

from backend.llm.base import LLMClient
from backend.llm.models import GenerationRequest, GenerationResponse, LLMConfig


@dataclass
class UsageTotals:
    calls: int = 0
    input_tokens: int = 0
    output_tokens: int = 0
    calls_without_usage: int = 0  # provider returned no usage numbers

    @property
    def total_tokens(self) -> int:
        return self.input_tokens + self.output_tokens

    def add(self, response: GenerationResponse) -> None:
        self.calls += 1
        if response.usage is None:
            self.calls_without_usage += 1
        else:
            self.input_tokens += response.usage.input_tokens
            self.output_tokens += response.usage.output_tokens


class UsageRecordingLLM(LLMClient):
    """Wraps any :class:`LLMClient` and totals token usage of its calls.

    Only ``invoke``/``ainvoke`` are counted: streams carry no usage numbers,
    so they pass through untouched.
    """

    def __init__(self, inner: LLMClient):
        self._inner = inner
        self.totals = UsageTotals()

    @property
    def config(self) -> LLMConfig:
        return self._inner.config

    def invoke(self, request: GenerationRequest) -> GenerationResponse:
        return self._record(self._inner.invoke(request))

    async def ainvoke(self, request: GenerationRequest) -> GenerationResponse:
        return self._record(await self._inner.ainvoke(request))

    def stream(self, request: GenerationRequest) -> Iterator[str]:
        return self._inner.stream(request)

    def astream(self, request: GenerationRequest) -> AsyncIterator[str]:
        return self._inner.astream(request)

    def reset(self) -> UsageTotals:
        """Return the totals so far and start counting from zero."""
        totals, self.totals = self.totals, UsageTotals()
        return totals

    def _record(self, response: GenerationResponse) -> GenerationResponse:
        self.totals.add(response)
        return response


_current_usage: ContextVar[UsageTotals | None] = ContextVar("llm_usage", default=None)


@contextmanager
def track_usage() -> Iterator[UsageTotals]:
    """Count the usage of every :class:`MeteredLLM` call made inside the block."""
    totals = UsageTotals()
    token = _current_usage.set(totals)
    try:
        yield totals
    finally:
        _current_usage.reset(token)


class MeteredLLM(LLMClient):
    """Wraps a shared client; adds each call's usage to the current
    :func:`track_usage` tally, if any (calls outside one aren't counted)."""

    def __init__(self, inner: LLMClient):
        self._inner = inner

    @property
    def config(self) -> LLMConfig:
        return self._inner.config

    def invoke(self, request: GenerationRequest) -> GenerationResponse:
        return self._record(self._inner.invoke(request))

    async def ainvoke(self, request: GenerationRequest) -> GenerationResponse:
        return self._record(await self._inner.ainvoke(request))

    def stream(self, request: GenerationRequest) -> Iterator[str]:
        return self._inner.stream(request)

    def astream(self, request: GenerationRequest) -> AsyncIterator[str]:
        return self._inner.astream(request)

    @staticmethod
    def _record(response: GenerationResponse) -> GenerationResponse:
        totals = _current_usage.get()
        if totals is not None:
            totals.add(response)
        return response
