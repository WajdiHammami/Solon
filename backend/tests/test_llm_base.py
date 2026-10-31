"""Tests for the provider-agnostic LLM interface and its models."""

import pytest
from pydantic import ValidationError

from backend.llm.base import LLMClient
from backend.llm.models import (
    GenerationRequest,
    GenerationResponse,
    LLMConfig,
    Message,
    Role,
)


class EchoLLM(LLMClient):
    """Minimal concrete client: echoes the last message back."""

    def __init__(self, config: LLMConfig):
        self._config = config

    @property
    def config(self) -> LLMConfig:
        return self._config

    def invoke(self, request):
        return GenerationResponse(
            content=request.messages[-1].content, model=self._config.model
        )

    async def ainvoke(self, request):
        return self.invoke(request)

    def stream(self, request):
        yield from request.messages[-1].content.split()

    async def astream(self, request):
        for word in request.messages[-1].content.split():
            yield word


def _request(text="hello world"):
    return GenerationRequest(messages=[Message(role=Role.USER, content=text)])


def test_cannot_instantiate_abstract_client():
    with pytest.raises(TypeError):
        LLMClient()


def test_concrete_client_invoke_and_stream():
    llm = EchoLLM(LLMConfig(model="echo"))
    assert llm.config.model == "echo"
    assert llm.invoke(_request()).content == "hello world"
    assert list(llm.stream(_request())) == ["hello", "world"]


def test_request_requires_at_least_one_message():
    with pytest.raises(ValidationError):
        GenerationRequest(messages=[])


def test_request_overrides_default_to_none():
    request = _request()
    assert request.temperature is None
    assert request.max_tokens is None


@pytest.mark.parametrize("temperature", [-0.1, 2.1])
def test_temperature_out_of_range_rejected(temperature):
    with pytest.raises(ValidationError):
        LLMConfig(model="m", temperature=temperature)


def test_role_accepts_plain_strings():
    assert Message(role="system", content="x").role is Role.SYSTEM
