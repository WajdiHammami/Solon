import openai
from openai import AsyncAzureOpenAI, AzureOpenAI

from backend.llm.models import LLMConfig
from backend.llm.openai_compatible import OpenAICompatibleLLM, sdk_error_map


class AzureLLM(OpenAICompatibleLLM):
    """LLM client backed by an Azure OpenAI deployment.

    ``config.model`` is the Azure *deployment name*, not the underlying
    OpenAI model name.
    """

    error_map = sdk_error_map(openai)

    def __init__(
        self, config: LLMConfig, endpoint: str, api_key: str, api_version: str
    ):
        options = {
            "azure_endpoint": endpoint,
            "api_key": api_key,
            "api_version": api_version,
        }
        super().__init__(
            config,
            client=AzureOpenAI(**options),
            async_client=AsyncAzureOpenAI(**options),
        )
