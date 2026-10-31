"""Provider-agnostic request/response models for LLM calls."""

from enum import Enum

from pydantic import BaseModel, Field


class Role(str, Enum):
    SYSTEM = "system"
    USER = "user"
    ASSISTANT = "assistant"


class Message(BaseModel):
    role: Role
    content: str


class LLMConfig(BaseModel):
    """Static configuration an LLM client is built with."""

    model: str
    temperature: float = Field(default=0.0, ge=0.0, le=2.0)
    max_tokens: int | None = Field(default=None, gt=0)


class GenerationRequest(BaseModel):
    """Input to an LLM call.

    ``temperature`` and ``max_tokens`` override the client's
    :class:`LLMConfig` for this request only; ``None`` means use the default.

    ``json_output`` asks the provider to return a single JSON object. The
    prompt must still describe the expected shape (and, for OpenAI-style
    APIs, mention the word "JSON").
    """

    messages: list[Message] = Field(min_length=1)
    temperature: float | None = Field(default=None, ge=0.0, le=2.0)
    max_tokens: int | None = Field(default=None, gt=0)
    json_output: bool = False


class Usage(BaseModel):
    input_tokens: int = 0
    output_tokens: int = 0


class GenerationResponse(BaseModel):
    """Output of a (non-streaming) LLM call."""

    content: str
    model: str
    finish_reason: str | None = None
    usage: Usage | None = None
