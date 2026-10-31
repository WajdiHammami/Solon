"""Shared implementation for providers exposing an OpenAI-style chat API.

Groq and Azure OpenAI both speak the ``chat.completions`` protocol, so the
request/response mapping lives here once. Subclasses only build the SDK
clients and declare how their SDK's exceptions map to :mod:`backend.llm.errors`.
"""

import logging
import time
from collections.abc import AsyncIterator, Generator, Iterator
from contextlib import contextmanager
from types import ModuleType
from typing import Any, ClassVar

from backend.llm.base import LLMClient
from backend.llm.errors import (
    LLMAuthenticationError,
    LLMBadRequestError,
    LLMConnectionError,
    LLMError,
    LLMRateLimitError,
    LLMServerError,
    LLMTimeoutError,
)
from backend.llm.models import (
    GenerationRequest,
    GenerationResponse,
    LLMConfig,
    Usage,
)

logger = logging.getLogger(__name__)

ErrorMap = tuple[tuple[type[Exception], type[LLMError]], ...]


def sdk_error_map(sdk: ModuleType) -> ErrorMap:
    """Build the exception mapping for a Stainless-generated SDK (groq, openai).

    Both SDKs share the same exception names. Order matters: the first
    matching ``isinstance`` wins, so subclasses come before their bases.
    """
    return (
        (sdk.APITimeoutError, LLMTimeoutError),
        (sdk.APIConnectionError, LLMConnectionError),
        (sdk.AuthenticationError, LLMAuthenticationError),
        (sdk.PermissionDeniedError, LLMAuthenticationError),
        (sdk.RateLimitError, LLMRateLimitError),
        (sdk.BadRequestError, LLMBadRequestError),
        (sdk.NotFoundError, LLMBadRequestError),
        (sdk.UnprocessableEntityError, LLMBadRequestError),
        (sdk.InternalServerError, LLMServerError),
        (sdk.APIError, LLMError),
    )


class OpenAICompatibleLLM(LLMClient):
    """:class:`LLMClient` over any OpenAI-compatible ``chat.completions`` SDK."""

    #: SDK exception -> LLMError mapping; set by each subclass.
    error_map: ClassVar[ErrorMap] = ()

    def __init__(self, config: LLMConfig, client: Any, async_client: Any):
        self._config = config
        self._client = client
        self._async_client = async_client

    @property
    def config(self) -> LLMConfig:
        return self._config

    def invoke(self, request: GenerationRequest) -> GenerationResponse:
        started = time.perf_counter()
        with self._translate_errors():
            completion = self._client.chat.completions.create(
                **self._params(request)
            )
        return self._log_call(self._to_response(completion), started)

    async def ainvoke(self, request: GenerationRequest) -> GenerationResponse:
        started = time.perf_counter()
        with self._translate_errors():
            completion = await self._async_client.chat.completions.create(
                **self._params(request)
            )
        return self._log_call(self._to_response(completion), started)

    def stream(self, request: GenerationRequest) -> Iterator[str]:
        # Errors can surface mid-stream, so the whole iteration is wrapped.
        with self._translate_errors():
            chunks = self._client.chat.completions.create(
                **self._params(request), stream=True
            )
            for chunk in chunks:
                if text := self._chunk_text(chunk):
                    yield text

    async def astream(self, request: GenerationRequest) -> AsyncIterator[str]:
        with self._translate_errors():
            chunks = await self._async_client.chat.completions.create(
                **self._params(request), stream=True
            )
            async for chunk in chunks:
                if text := self._chunk_text(chunk):
                    yield text

    def _log_call(
        self, response: GenerationResponse, started: float
    ) -> GenerationResponse:
        usage = response.usage
        logger.debug(
            "%s %s: %.0f ms, %s in / %s out tokens, finish=%s",
            type(self).__name__,
            response.model,
            (time.perf_counter() - started) * 1000,
            usage.input_tokens if usage else "?",
            usage.output_tokens if usage else "?",
            response.finish_reason,
        )
        return response

    @contextmanager
    def _translate_errors(self) -> Generator[None, None, None]:
        """Re-raise SDK exceptions as the matching :class:`LLMError`."""
        try:
            yield
        except Exception as e:
            for sdk_error, llm_error in self.error_map:
                if isinstance(e, sdk_error):
                    raise llm_error(str(e)) from e
            raise

    def _params(self, request: GenerationRequest) -> dict[str, Any]:
        """Merge per-request overrides onto the client config."""
        temperature = (
            request.temperature
            if request.temperature is not None
            else self._config.temperature
        )
        max_tokens = (
            request.max_tokens
            if request.max_tokens is not None
            else self._config.max_tokens
        )
        params: dict[str, Any] = {
            "model": self._config.model,
            "messages": [
                {"role": m.role.value, "content": m.content} for m in request.messages
            ],
            "temperature": temperature,
        }
        if max_tokens is not None:
            # ``max_tokens`` is deprecated on both APIs and rejected by
            # reasoning models; ``max_completion_tokens`` works everywhere.
            params["max_completion_tokens"] = max_tokens
        if request.json_output:
            params["response_format"] = {"type": "json_object"}
        return params

    @staticmethod
    def _to_response(completion: Any) -> GenerationResponse:
        choice = completion.choices[0]
        usage = completion.usage
        return GenerationResponse(
            content=choice.message.content or "",
            model=completion.model,
            finish_reason=choice.finish_reason,
            usage=Usage(
                input_tokens=usage.prompt_tokens,
                output_tokens=usage.completion_tokens,
            )
            if usage
            else None,
        )

    @staticmethod
    def _chunk_text(chunk: Any) -> str | None:
        # Azure sends chunks with no choices (e.g. content-filter results).
        if not chunk.choices:
            return None
        return chunk.choices[0].delta.content
