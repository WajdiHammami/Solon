"""Tests for selecting the LLM client from settings."""

import pytest

from backend.config import Settings
from backend.llm.azure_llm import AzureLLM
from backend.llm.factory import create_llm
from backend.llm.groq_llm import GroqLLM


def _settings(**overrides):
    return Settings(_env_file=None, **overrides)


def test_groq_is_the_default():
    llm = create_llm(_settings(groq_api_key="k", groq_model="some-model"))
    assert isinstance(llm, GroqLLM)
    assert llm.config.model == "some-model"


def test_azure_uses_deployment_as_model():
    llm = create_llm(
        _settings(
            llm_provider="azure",
            azure_openai_endpoint="https://example.openai.azure.com",
            azure_openai_api_key="k",
            azure_openai_deployment="my-deployment",
        )
    )
    assert isinstance(llm, AzureLLM)
    assert llm.config.model == "my-deployment"


def test_azure_reports_missing_settings():
    with pytest.raises(ValueError, match="AZURE_OPENAI_ENDPOINT.*AZURE_OPENAI_DEPLOYMENT"):
        create_llm(_settings(llm_provider="azure", azure_openai_api_key="k"))


def test_unknown_provider_rejected_by_settings():
    with pytest.raises(ValueError):
        _settings(llm_provider="anthropic")
