import groq
from groq import AsyncGroq, Groq

from backend.llm.models import LLMConfig
from backend.llm.openai_compatible import OpenAICompatibleLLM, sdk_error_map


class GroqLLM(OpenAICompatibleLLM):
    """LLM client backed by Groq (https://console.groq.com)."""

    error_map = sdk_error_map(groq)

    def __init__(self, config: LLMConfig, api_key: str):
        super().__init__(
            config,
            client=Groq(api_key=api_key),
            async_client=AsyncGroq(api_key=api_key),
        )
