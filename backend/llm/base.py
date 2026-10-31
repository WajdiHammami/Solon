from abc import ABC, abstractmethod
from collections.abc import AsyncIterator, Iterator

from backend.llm.models import GenerationRequest, GenerationResponse, LLMConfig


class LLMClient(ABC):
    """Abstract interface every LLM provider must implement.

    Implementations raise :class:`~backend.llm.errors.LLMError` subclasses,
    never their SDK's own exceptions.
    """

    @property
    @abstractmethod
    def config(self) -> LLMConfig:
        """The configuration this client was built with."""

    @abstractmethod
    def invoke(self, request: GenerationRequest) -> GenerationResponse:
        """Run ``request`` and return the complete response."""

    @abstractmethod
    async def ainvoke(self, request: GenerationRequest) -> GenerationResponse:
        """Async variant of :meth:`invoke`."""

    @abstractmethod
    def stream(self, request: GenerationRequest) -> Iterator[str]:
        """Run ``request`` and yield the response text as it is generated."""

    @abstractmethod
    def astream(self, request: GenerationRequest) -> AsyncIterator[str]:
        """Async variant of :meth:`stream`; implement as an ``async def`` generator."""
