"""Application configuration loaded from environment / .env files.

Uses pydantic-settings for validated, typed configuration. All settings can
be overridden via environment variables or a .env file in the project root.
"""

from __future__ import annotations

from enum import Enum
from pathlib import Path

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

from llm_file_assistant.exceptions import ConfigurationError


class LLMProvider(str, Enum):
    """Supported LLM providers."""

    OPENAI = "openai"
    ANTHROPIC = "anthropic"


class LogLevel(str, Enum):
    """Supported logging levels."""

    DEBUG = "DEBUG"
    INFO = "INFO"
    WARNING = "WARNING"
    ERROR = "ERROR"


class Settings(BaseSettings):
    """Application settings loaded from env / .env."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    llm_provider: LLMProvider = Field(default=LLMProvider.OPENAI)

    openai_api_key: str | None = Field(default=None)
    openai_model: str = Field(default="gpt-4o-mini")

    anthropic_api_key: str | None = Field(default=None)
    anthropic_model: str = Field(default="claude-sonnet-4-5")

    fs_root: Path = Field(default=Path("./data"))
    fs_max_file_bytes: int = Field(default=25 * 1024 * 1024, ge=1)

    log_level: LogLevel = Field(default=LogLevel.INFO)

    agent_max_iterations: int = Field(default=10, ge=1, le=50)

    @field_validator("fs_root")
    @classmethod
    def _resolve_fs_root(cls, v: Path) -> Path:
        return v.expanduser().resolve()

    def require_provider_credentials(self) -> None:
        """Validate that credentials exist for the selected provider.

        Raises:
            ConfigurationError: if the API key for the selected provider is missing.
        """
        if self.llm_provider is LLMProvider.OPENAI and not self.openai_api_key:
            raise ConfigurationError(
                "OPENAI_API_KEY is required when LLM_PROVIDER=openai"
            )
        if self.llm_provider is LLMProvider.ANTHROPIC and not self.anthropic_api_key:
            raise ConfigurationError(
                "ANTHROPIC_API_KEY is required when LLM_PROVIDER=anthropic"
            )


_settings: Settings | None = None


def get_settings() -> Settings:
    """Return a process-wide cached Settings instance."""
    global _settings
    if _settings is None:
        _settings = Settings()
    return _settings


def reset_settings_cache() -> None:
    """Clear the cached settings (primarily for tests)."""
    global _settings
    _settings = None
