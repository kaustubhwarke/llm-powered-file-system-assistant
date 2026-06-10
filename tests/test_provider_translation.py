"""Tests for provider-specific tool-schema translation.

These tests don't hit the network — they validate that our ToolDescriptor
objects translate correctly into each provider's wire format and that
provider responses parse correctly into ProviderToolCall objects.
"""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from llm_file_assistant.providers.anthropic_provider import AnthropicProvider
from llm_file_assistant.providers.openai_provider import OpenAIProvider
from llm_file_assistant.schemas import ToolDescriptor, ToolParameter


@pytest.fixture
def sample_descriptor() -> ToolDescriptor:
    return ToolDescriptor(
        name="read_file",
        description="Read a file.",
        parameters=ToolParameter(
            properties={
                "filepath": {"type": "string", "description": "path"},
            },
            required=["filepath"],
        ),
    )


class TestOpenAITranslation:
    def test_tool_descriptor_to_openai_format(
        self, sample_descriptor: ToolDescriptor, sandbox: Path
    ) -> None:
        wire = OpenAIProvider._to_openai_tool(sample_descriptor)
        assert wire["type"] == "function"
        assert wire["function"]["name"] == "read_file"
        assert wire["function"]["parameters"]["required"] == ["filepath"]
        assert wire["function"]["parameters"]["additionalProperties"] is False

    def test_parse_args_valid_json(self, sandbox: Path) -> None:
        result = OpenAIProvider._parse_args('{"filepath": "a.txt"}', "id1")
        assert result == {"filepath": "a.txt"}

    def test_parse_args_empty(self, sandbox: Path) -> None:
        assert OpenAIProvider._parse_args(None, "id1") == {}
        assert OpenAIProvider._parse_args("", "id1") == {}

    def test_parse_args_invalid_json(self, sandbox: Path) -> None:
        from llm_file_assistant.exceptions import LLMResponseError

        with pytest.raises(LLMResponseError):
            OpenAIProvider._parse_args("{not json}", "id1")

    def test_parse_args_non_object(self, sandbox: Path) -> None:
        from llm_file_assistant.exceptions import LLMResponseError

        with pytest.raises(LLMResponseError):
            OpenAIProvider._parse_args("[1, 2, 3]", "id1")

    def test_send_turn_with_mocked_client(
        self, sample_descriptor: ToolDescriptor, sandbox: Path
    ) -> None:
        provider = OpenAIProvider(api_key="sk-test", model="gpt-4o-mini")
        mock_message = MagicMock()
        mock_message.content = None
        mock_call = MagicMock()
        mock_call.id = "call-1"
        mock_call.function.name = "read_file"
        mock_call.function.arguments = '{"filepath": "a.txt"}'
        mock_message.tool_calls = [mock_call]
        mock_choice = MagicMock()
        mock_choice.message = mock_message
        mock_response = MagicMock()
        mock_response.choices = [mock_choice]

        with patch.object(
            provider._client.chat.completions, "create", return_value=mock_response
        ):
            provider.start_conversation("sys", "user")
            turn = provider.send_turn([sample_descriptor])

        assert len(turn.tool_calls) == 1
        assert turn.tool_calls[0].name == "read_file"
        assert turn.tool_calls[0].arguments == {"filepath": "a.txt"}


class TestAnthropicTranslation:
    def test_tool_descriptor_to_anthropic_format(
        self, sample_descriptor: ToolDescriptor, sandbox: Path
    ) -> None:
        wire = AnthropicProvider._to_anthropic_tool(sample_descriptor)
        assert wire["name"] == "read_file"
        assert wire["input_schema"]["required"] == ["filepath"]
        assert wire["input_schema"]["additionalProperties"] is False

    def test_send_turn_with_mocked_client(
        self, sample_descriptor: ToolDescriptor, sandbox: Path
    ) -> None:
        provider = AnthropicProvider(api_key="sk-ant-test", model="claude-sonnet-4-5")

        tool_block = MagicMock()
        tool_block.type = "tool_use"
        tool_block.id = "tu-1"
        tool_block.name = "read_file"
        tool_block.input = {"filepath": "a.txt"}
        mock_response = MagicMock()
        mock_response.content = [tool_block]

        with patch.object(
            provider._client.messages, "create", return_value=mock_response
        ):
            provider.start_conversation("sys", "user")
            turn = provider.send_turn([sample_descriptor])

        assert len(turn.tool_calls) == 1
        assert turn.tool_calls[0].name == "read_file"
        assert turn.tool_calls[0].arguments == {"filepath": "a.txt"}
