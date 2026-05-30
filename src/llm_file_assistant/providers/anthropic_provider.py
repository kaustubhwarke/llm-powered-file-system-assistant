"""Anthropic Messages API provider implementation with tool-calling."""

from __future__ import annotations

from typing import Any

from llm_file_assistant.exceptions import ConfigurationError, LLMResponseError
from llm_file_assistant.logging_config import get_logger
from llm_file_assistant.providers.base import (
    LLMProviderClient,
    ProviderToolCall,
    ProviderTurnResult,
)
from llm_file_assistant.schemas import ToolDescriptor

logger = get_logger(__name__)


class AnthropicProvider(LLMProviderClient):
    """Anthropic provider using the messages API with tool_use blocks."""

    def __init__(self, api_key: str, model: str) -> None:
        if not api_key:
            raise ConfigurationError("Anthropic API key is required")
        try:
            from anthropic import Anthropic
        except ImportError as exc:  # pragma: no cover
            raise ConfigurationError("anthropic package is not installed") from exc
        self._client = Anthropic(api_key=api_key)
        self._model = model
        self._system_prompt: str = ""
        self._messages: list[dict[str, Any]] = []

    @property
    def provider_name(self) -> str:
        return "anthropic"

    @property
    def model_name(self) -> str:
        return self._model

    def start_conversation(self, system_prompt: str, user_prompt: str) -> None:
        self._system_prompt = system_prompt
        self._messages = [{"role": "user", "content": user_prompt}]

    def send_turn(self, tools: list[ToolDescriptor]) -> ProviderTurnResult:
        anthropic_tools = [self._to_anthropic_tool(t) for t in tools]
        logger.debug(
            "provider.anthropic.send_turn",
            model=self._model,
            message_count=len(self._messages),
        )
        response = self._client.messages.create(
            model=self._model,
            system=self._system_prompt,
            messages=self._messages,
            tools=anthropic_tools,
            max_tokens=4096,
            temperature=0.2,
        )

        assistant_blocks: list[dict[str, Any]] = []
        tool_calls: list[ProviderToolCall] = []
        text_parts: list[str] = []

        for block in response.content:
            if block.type == "text":
                text_parts.append(block.text)
                assistant_blocks.append({"type": "text", "text": block.text})
            elif block.type == "tool_use":
                if not isinstance(block.input, dict):
                    raise LLMResponseError(
                        f"Anthropic tool_use {block.id} input must be an object"
                    )
                tool_calls.append(
                    ProviderToolCall(
                        id=block.id, name=block.name, arguments=block.input
                    )
                )
                assistant_blocks.append(
                    {
                        "type": "tool_use",
                        "id": block.id,
                        "name": block.name,
                        "input": block.input,
                    }
                )

        self._messages.append({"role": "assistant", "content": assistant_blocks})

        if tool_calls:
            return ProviderTurnResult(tool_calls=tool_calls, raw_response=response)
        return ProviderTurnResult(text="".join(text_parts), raw_response=response)

    def submit_tool_results(
        self, results: list[tuple[ProviderToolCall, dict[str, Any]]]
    ) -> None:
        content_blocks: list[dict[str, Any]] = []
        for call, result in results:
            is_error = result.get("status") == "error"
            content_blocks.append(
                {
                    "type": "tool_result",
                    "tool_use_id": call.id,
                    "content": _stringify(result),
                    "is_error": is_error,
                }
            )
        self._messages.append({"role": "user", "content": content_blocks})

    # ------------------------------------------------------------------
    # internals
    # ------------------------------------------------------------------

    @staticmethod
    def _to_anthropic_tool(descriptor: ToolDescriptor) -> dict[str, Any]:
        return {
            "name": descriptor.name,
            "description": descriptor.description,
            "input_schema": {
                "type": descriptor.parameters.type,
                "properties": descriptor.parameters.properties,
                "required": descriptor.parameters.required,
                "additionalProperties": descriptor.parameters.additionalProperties,
            },
        }


def _stringify(payload: dict[str, Any]) -> str:
    import json

    return json.dumps(payload, default=str)
