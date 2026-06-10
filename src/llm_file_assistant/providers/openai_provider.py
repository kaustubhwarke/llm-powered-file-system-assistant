"""OpenAI Chat Completions provider implementation with tool-calling."""

from __future__ import annotations

import json
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


class OpenAIProvider(LLMProviderClient):
    """OpenAI provider using the chat.completions tools API."""

    def __init__(self, api_key: str, model: str) -> None:
        if not api_key:
            raise ConfigurationError("OpenAI API key is required")
        try:
            from openai import OpenAI
        except ImportError as exc:  # pragma: no cover
            raise ConfigurationError("openai package is not installed") from exc
        self._client = OpenAI(api_key=api_key)
        self._model = model
        self._messages: list[dict[str, Any]] = []

    @property
    def provider_name(self) -> str:
        return "openai"

    @property
    def model_name(self) -> str:
        return self._model

    def start_conversation(self, system_prompt: str, user_prompt: str) -> None:
        self._messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ]

    def send_turn(self, tools: list[ToolDescriptor]) -> ProviderTurnResult:
        openai_tools = [self._to_openai_tool(t) for t in tools]
        logger.debug(
            "provider.openai.send_turn",
            model=self._model,
            message_count=len(self._messages),
        )
        response = self._client.chat.completions.create(
            model=self._model,
            messages=self._messages,
            tools=openai_tools,
            tool_choice="auto",
            temperature=0.2,
        )
        if not response.choices:
            raise LLMResponseError("OpenAI returned no choices")
        choice = response.choices[0]
        message = choice.message

        assistant_msg: dict[str, Any] = {"role": "assistant"}
        if message.content is not None:
            assistant_msg["content"] = message.content
        if message.tool_calls:
            assistant_msg["tool_calls"] = [
                {
                    "id": tc.id,
                    "type": "function",
                    "function": {
                        "name": tc.function.name,
                        "arguments": tc.function.arguments,
                    },
                }
                for tc in message.tool_calls
            ]
        self._messages.append(assistant_msg)

        if message.tool_calls:
            calls = [
                ProviderToolCall(
                    id=tc.id,
                    name=tc.function.name,
                    arguments=self._parse_args(tc.function.arguments, tc.id),
                )
                for tc in message.tool_calls
            ]
            return ProviderTurnResult(tool_calls=calls, raw_response=response)
        return ProviderTurnResult(text=message.content or "", raw_response=response)

    def submit_tool_results(
        self, results: list[tuple[ProviderToolCall, dict[str, Any]]]
    ) -> None:
        for call, result in results:
            self._messages.append(
                {
                    "role": "tool",
                    "tool_call_id": call.id,
                    "content": json.dumps(result, default=str),
                }
            )

    # ------------------------------------------------------------------
    # internals
    # ------------------------------------------------------------------

    @staticmethod
    def _to_openai_tool(descriptor: ToolDescriptor) -> dict[str, Any]:
        return {
            "type": "function",
            "function": {
                "name": descriptor.name,
                "description": descriptor.description,
                "parameters": {
                    "type": descriptor.parameters.type,
                    "properties": descriptor.parameters.properties,
                    "required": descriptor.parameters.required,
                    "additionalProperties": descriptor.parameters.additionalProperties,
                },
            },
        }

    @staticmethod
    def _parse_args(raw: str | None, call_id: str) -> dict[str, Any]:
        if not raw:
            return {}
        try:
            parsed = json.loads(raw)
        except json.JSONDecodeError as exc:
            raise LLMResponseError(
                f"OpenAI tool_call {call_id} arguments were not valid JSON: {exc}"
            ) from exc
        if not isinstance(parsed, dict):
            raise LLMResponseError(
                f"OpenAI tool_call {call_id} arguments must be an object"
            )
        return parsed
