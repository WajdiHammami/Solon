"""Provider-agnostic LLM errors.

Every :class:`~backend.llm.base.LLMClient` raises these instead of its SDK's
own exceptions, so callers can handle failures without knowing which
provider is behind the client. The original SDK exception is kept as
``__cause__``.
"""


class LLMError(Exception):
    """Base class for all LLM failures."""

    #: Whether retrying the same request later may succeed.
    retryable: bool = False


class LLMAuthenticationError(LLMError):
    """Missing, invalid, or unauthorized credentials."""


class LLMBadRequestError(LLMError):
    """The request was rejected (invalid params, unknown model/deployment,
    context too long, content filtered)."""


class LLMInvalidOutputError(LLMError):
    """The model answered, but not in the shape the caller asked for."""

    retryable = True


class LLMRateLimitError(LLMError):
    retryable = True


class LLMTimeoutError(LLMError):
    retryable = True


class LLMConnectionError(LLMError):
    retryable = True


class LLMServerError(LLMError):
    """The provider failed (5xx)."""

    retryable = True
