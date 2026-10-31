"""Tests for the OpenAI-compatible LLM clients (Groq, Azure OpenAI).

The SDK clients are replaced with in-memory fakes; nothing hits the network.
"""

from types import SimpleNamespace

import groq
import httpx
import httpx2
import openai
import pytest

from backend.llm.azure_llm import AzureLLM
from backend.llm.errors import (
    LLMAuthenticationError,
    LLMBadRequestError,
    LLMConnectionError,
    LLMError,
    LLMRateLimitError,
    LLMServerError,
    LLMTimeoutError,
)
from backend.llm.groq_llm import GroqLLM
from backend.llm.models import GenerationRequest, LLMConfig, Message, Role
from backend.llm.openai_compatible import OpenAICompatibleLLM


@pytest.fixture
def anyio_backend():
    return "asyncio"


def _completion(content="hi", finish_reason="stop", usage=(3, 5)):
    return SimpleNamespace(
        model="served-model",
        choices=[
            SimpleNamespace(
                message=SimpleNamespace(content=content),
                finish_reason=finish_reason,
            )
        ],
        usage=SimpleNamespace(prompt_tokens=usage[0], completion_tokens=usage[1])
        if usage
        else None,
    )


def _chunks(*texts):
    # A leading empty-choices chunk mimics Azure's content-filter preamble.
    yield SimpleNamespace(choices=[])
    for text in texts:
        yield SimpleNamespace(
            choices=[SimpleNamespace(delta=SimpleNamespace(content=text))]
        )


class _FakeCompletions:
    """Fake ``chat.completions``; ``error`` is raised on the call, or
    mid-stream (after the first chunk) when ``stream_error`` is set."""

    def __init__(self, completion=None, chunks=(), error=None, stream_error=None):
        self.completion = completion or _completion()
        self.chunks = chunks
        self.error = error
        self.stream_error = stream_error
        self.calls: list[dict] = []

    def _stream(self):
        for i, chunk in enumerate(_chunks(*self.chunks)):
            if i == 1 and self.stream_error:
                raise self.stream_error
            yield chunk

    def create(self, **params):
        self.calls.append(params)
        if self.error:
            raise self.error
        return self._stream() if params.get("stream") else self.completion


class _FakeAsyncCompletions(_FakeCompletions):
    async def create(self, **params):
        result = super().create(**params)
        if not params.get("stream"):
            return result

        async def agen():
            for chunk in result:
                yield chunk

        return agen()


def _client(completions):
    return SimpleNamespace(chat=SimpleNamespace(completions=completions))


class _GroqErrorsLLM(OpenAICompatibleLLM):
    error_map = GroqLLM.error_map


def _llm(config=None, **fake_kwargs):
    sync, async_ = _FakeCompletions(**fake_kwargs), _FakeAsyncCompletions(**fake_kwargs)
    llm = _GroqErrorsLLM(
        config or LLMConfig(model="m", temperature=0.3, max_tokens=100),
        client=_client(sync),
        async_client=_client(async_),
    )
    return llm, sync, async_


def _request(**overrides):
    return GenerationRequest(
        messages=[
            Message(role=Role.SYSTEM, content="be brief"),
            Message(role=Role.USER, content="hello"),
        ],
        **overrides,
    )


class TestInvoke:
    def test_maps_completion_to_response(self):
        llm, _, _ = _llm()
        response = llm.invoke(_request())
        assert response.content == "hi"
        assert response.model == "served-model"
        assert response.finish_reason == "stop"
        assert response.usage.input_tokens == 3
        assert response.usage.output_tokens == 5

    def test_missing_usage_and_content(self):
        llm, _, _ = _llm(completion=_completion(content=None, usage=None))
        response = llm.invoke(_request())
        assert response.content == ""
        assert response.usage is None

    def test_sends_messages_and_config_defaults(self):
        llm, sync, _ = _llm()
        llm.invoke(_request())
        params = sync.calls[0]
        assert params["model"] == "m"
        assert params["messages"] == [
            {"role": "system", "content": "be brief"},
            {"role": "user", "content": "hello"},
        ]
        assert params["temperature"] == 0.3
        assert params["max_completion_tokens"] == 100
        assert "max_tokens" not in params

    def test_request_overrides_config(self):
        llm, sync, _ = _llm()
        llm.invoke(_request(temperature=0.0, max_tokens=10))
        assert sync.calls[0]["temperature"] == 0.0
        assert sync.calls[0]["max_completion_tokens"] == 10

    def test_json_output_sets_response_format(self):
        llm, sync, _ = _llm()
        llm.invoke(_request())
        assert "response_format" not in sync.calls[0]
        llm.invoke(_request(json_output=True))
        assert sync.calls[1]["response_format"] == {"type": "json_object"}

    def test_omits_token_limit_when_unset(self):
        llm, sync, _ = _llm(config=LLMConfig(model="m"))
        llm.invoke(_request())
        assert "max_completion_tokens" not in sync.calls[0]


@pytest.mark.anyio
async def test_ainvoke_maps_completion_to_response():
    llm, _, async_ = _llm()
    response = await llm.ainvoke(_request())
    assert response.content == "hi"
    assert response.usage.output_tokens == 5
    assert "stream" not in async_.calls[0]


def test_stream_yields_text_and_skips_empty_chunks():
    llm, sync, _ = _llm(chunks=("Hel", None, "lo"))
    assert list(llm.stream(_request())) == ["Hel", "lo"]
    assert sync.calls[0]["stream"] is True


@pytest.mark.anyio
async def test_astream_yields_text_and_skips_empty_chunks():
    llm, _, async_ = _llm(chunks=("Hel", None, "lo"))
    assert [t async for t in llm.astream(_request())] == ["Hel", "lo"]
    assert async_.calls[0]["stream"] is True


def _sdk_error(sdk, name, status=None):
    """Build a real SDK exception (each SDK pins its own httpx module)."""
    hx = httpx2 if sdk is openai else httpx
    request = hx.Request("POST", "https://api.example.com")
    cls = getattr(sdk, name)
    if status is None:
        return cls(request=request)
    return cls("boom", response=hx.Response(status, request=request), body=None)


ERROR_CASES = [
    ("APITimeoutError", None, LLMTimeoutError, True),
    ("APIConnectionError", None, LLMConnectionError, True),
    ("AuthenticationError", 401, LLMAuthenticationError, False),
    ("PermissionDeniedError", 403, LLMAuthenticationError, False),
    ("RateLimitError", 429, LLMRateLimitError, True),
    ("BadRequestError", 400, LLMBadRequestError, False),
    ("NotFoundError", 404, LLMBadRequestError, False),
    ("UnprocessableEntityError", 422, LLMBadRequestError, False),
    ("InternalServerError", 500, LLMServerError, True),
    ("ConflictError", 409, LLMError, False),  # unmapped status -> base class
]


class TestErrorTranslation:
    @pytest.mark.parametrize("llm_cls", [GroqLLM, AzureLLM])
    @pytest.mark.parametrize("name, status, expected, retryable", ERROR_CASES)
    def test_sdk_errors_map_to_llm_errors(
        self, llm_cls, name, status, expected, retryable
    ):
        sdk = groq if llm_cls is GroqLLM else openai
        error = _sdk_error(sdk, name, status)
        llm = llm_cls.__new__(llm_cls)
        OpenAICompatibleLLM.__init__(
            llm,
            LLMConfig(model="m"),
            client=_client(_FakeCompletions(error=error)),
            async_client=None,
        )
        with pytest.raises(expected) as exc_info:
            llm.invoke(_request())
        assert type(exc_info.value) is expected
        assert exc_info.value.retryable is retryable
        assert exc_info.value.__cause__ is error

    def test_mid_stream_error_is_translated(self):
        error = _sdk_error(groq, "APIConnectionError")
        llm, _, _ = _llm(chunks=("a", "b"), stream_error=error)
        with pytest.raises(LLMConnectionError):
            list(llm.stream(_request()))

    @pytest.mark.anyio
    async def test_async_errors_are_translated(self):
        llm, _, _ = _llm(error=_sdk_error(groq, "RateLimitError", 429))
        with pytest.raises(LLMRateLimitError):
            await llm.ainvoke(_request())
        with pytest.raises(LLMRateLimitError):
            [t async for t in llm.astream(_request())]

    def test_non_sdk_errors_pass_through(self):
        llm, _, _ = _llm(error=ValueError("bug"))
        with pytest.raises(ValueError):
            llm.invoke(_request())


def test_groq_llm_builds_sdk_clients():
    llm = GroqLLM(LLMConfig(model="g"), api_key="key")
    assert llm.config.model == "g"
    assert type(llm._client).__name__ == "Groq"
    assert type(llm._async_client).__name__ == "AsyncGroq"


def test_azure_llm_builds_sdk_clients():
    llm = AzureLLM(
        LLMConfig(model="deployment"),
        endpoint="https://example.openai.azure.com",
        api_key="key",
        api_version="2024-10-21",
    )
    assert llm.config.model == "deployment"
    assert type(llm._client).__name__ == "AzureOpenAI"
    assert type(llm._async_client).__name__ == "AsyncAzureOpenAI"
