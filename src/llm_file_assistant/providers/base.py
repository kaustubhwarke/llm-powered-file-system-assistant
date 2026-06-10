"""Provider-neutral interfaces for LLM tool-calling.

The agent loop talks only to :class:`LLMProviderClient`. Concrete provider
implementations translate their wire format into these dataclasses.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any

from llm_file_assistant.schemas import ToolDescriptor


@dataclass(frozen=True)
class ProviderToolCall:
    """A normalized representation of a tool-call request from the LLM."""

    id: str
    name: str
    arguments: dict[str, Any]


@dataclass
class ProviderTurnResult:
    """The outcome of one LLM turn.

    Exactly one of:
      * ``tool_calls`` is non-empty (the model wants us to run tools), OR
      * ``text`` contains the final assistant answer.
    """

    tool_calls: list[ProviderToolCall] = field(default_factory=list)
    text: str | None = None
    raw_response: Any = None


class LLMProviderClient(ABC):
    """Abstract LLM client used by the agent loop."""

    @abstractmethod
    def start_conversation(self, system_prompt: str, user_prompt: str) -> None:
        """Initialize provider-side conversation state."""

    @abstractmethod
    def send_turn(self, tools: list[ToolDescriptor]) -> ProviderTurnResult:
        """Send the current conversation and return the model's response."""

    @abstractmethod
    def submit_tool_results(
        self, results: list[tuple[ProviderToolCall, dict[str, Any]]]
    ) -> None:
        """Append tool results so the next ``send_turn`` includes them."""

    @property
    @abstractmethod
    def provider_name(self) -> str:
        """Human-readable provider identifier."""

    @property
    @abstractmethod
    def model_name(self) -> str:
        """Model identifier in use."""
