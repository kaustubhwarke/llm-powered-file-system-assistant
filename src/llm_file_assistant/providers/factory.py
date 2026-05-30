"""Provider factory keyed on the configured LLM_PROVIDER setting."""

from __future__ import annotations

from llm_file_assistant.config import LLMProvider, Settings, get_settings
from llm_file_assistant.exceptions import ConfigurationError
from llm_file_assistant.providers.base import LLMProviderClient


def build_provider(settings: Settings | None = None) -> LLMProviderClient:
    """Construct the configured LLM provider client.

    Raises:
        ConfigurationError: if credentials for the selected provider are missing.
    """
    settings = settings or get_settings()
    settings.require_provider_credentials()

    if settings.llm_provider is LLMProvider.OPENAI:
        from llm_file_assistant.providers.openai_provider import OpenAIProvider

        assert settings.openai_api_key is not None  # narrowed by require_provider_credentials
        return OpenAIProvider(
            api_key=settings.openai_api_key, model=settings.openai_model
        )
    if settings.llm_provider is LLMProvider.ANTHROPIC:
        from llm_file_assistant.providers.anthropic_provider import AnthropicProvider

        assert settings.anthropic_api_key is not None
        return AnthropicProvider(
            api_key=settings.anthropic_api_key, model=settings.anthropic_model
        )
    raise ConfigurationError(f"Unsupported LLM_PROVIDER: {settings.llm_provider!r}")
