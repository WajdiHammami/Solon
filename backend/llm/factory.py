from backend.config import Settings
from backend.llm.azure_llm import AzureLLM
from backend.llm.base import LLMClient
from backend.llm.groq_llm import GroqLLM
from backend.llm.models import LLMConfig


def create_llm(settings: Settings) -> LLMClient:
    """Build the LLM client selected by ``settings.llm_provider``."""
    if settings.llm_provider == "groq":
        return GroqLLM(
            LLMConfig(model=settings.groq_model), api_key=settings.groq_api_key
        )
    if settings.llm_provider == "azure":
        missing = [
            name
            for name, value in (
                ("AZURE_OPENAI_ENDPOINT", settings.azure_openai_endpoint),
                ("AZURE_OPENAI_API_KEY", settings.azure_openai_api_key),
                ("AZURE_OPENAI_DEPLOYMENT", settings.azure_openai_deployment),
            )
            if not value
        ]
        if missing:
            raise ValueError(f"LLM_PROVIDER=azure requires {', '.join(missing)}")
        return AzureLLM(
            LLMConfig(model=settings.azure_openai_deployment),
            endpoint=settings.azure_openai_endpoint,
            api_key=settings.azure_openai_api_key,
            api_version=settings.azure_openai_api_version,
        )
    raise ValueError(f"Unknown LLM provider: {settings.llm_provider!r}")
