"""Tests for the FileSystemAssistant agent loop with a fake provider."""

from __future__ import annotations

from collections.abc import Iterator
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import pytest

from llm_file_assistant.exceptions import AgentIterationLimitError
from llm_file_assistant.llm_file_assistant import FileSystemAssistant
from llm_file_assistant.providers.base import (
    LLMProviderClient,
    ProviderToolCall,
    ProviderTurnResult,
)
from llm_file_assistant.schemas import ToolDescriptor


@dataclass
class FakeProvider(LLMProviderClient):
    """Deterministic provider that replays a scripted list of turns."""

    script: list[ProviderTurnResult]
    _cursor: int = 0
    sent_tool_results: list[list[tuple[ProviderToolCall, dict[str, Any]]]] = field(
        default_factory=list
    )
    tools_seen: list[list[ToolDescriptor]] = field(default_factory=list)
    started: bool = False
    system_prompt: str = ""
    user_prompt: str = ""

    @property
    def provider_name(self) -> str:
        return "fake"

    @property
    def model_name(self) -> str:
        return "fake-1"

    def start_conversation(self, system_prompt: str, user_prompt: str) -> None:
        self.started = True
        self.system_prompt = system_prompt
        self.user_prompt = user_prompt

    def send_turn(self, tools: list[ToolDescriptor]) -> ProviderTurnResult:
        self.tools_seen.append(tools)
        turn = self.script[self._cursor]
        self._cursor += 1
        return turn

    def submit_tool_results(
        self, results: list[tuple[ProviderToolCall, dict[str, Any]]]
    ) -> None:
        self.sent_tool_results.append(results)


class TestAgentLoop:
    def test_returns_immediate_text_response(self, sandbox: Path) -> None:
        provider = FakeProvider(script=[ProviderTurnResult(text="hi there")])
        agent = FileSystemAssistant(provider=provider)
        result = agent.run("ping")
        assert result.text == "hi there"
        assert result.iterations == 1
        assert result.tool_invocations == []
        assert provider.started
        assert provider.user_prompt == "ping"

    def test_single_tool_call_then_answer(self, sandbox: Path) -> None:
        (sandbox / "a.txt").write_text("hello", encoding="utf-8")
        provider = FakeProvider(
            script=[
                ProviderTurnResult(
                    tool_calls=[
                        ProviderToolCall(
                            id="t1",
                            name="read_file",
                            arguments={"filepath": "a.txt"},
                        )
                    ]
                ),
                ProviderTurnResult(text="The file says hello."),
            ]
        )
        agent = FileSystemAssistant(provider=provider)
        result = agent.run("read a.txt")
        assert result.text == "The file says hello."
        assert len(result.tool_invocations) == 1
        assert result.tool_invocations[0].name == "read_file"
        assert result.tool_invocations[0].result["status"] == "success"
        assert provider.sent_tool_results[0][0][1]["status"] == "success"

    def test_multiple_tool_calls_one_turn(self, sandbox: Path) -> None:
        (sandbox / "a.txt").write_text("hello", encoding="utf-8")
        (sandbox / "b.txt").write_text("world", encoding="utf-8")
        provider = FakeProvider(
            script=[
                ProviderTurnResult(
                    tool_calls=[
                        ProviderToolCall("t1", "read_file", {"filepath": "a.txt"}),
                        ProviderToolCall("t2", "read_file", {"filepath": "b.txt"}),
                    ]
                ),
                ProviderTurnResult(text="hello world"),
            ]
        )
        agent = FileSystemAssistant(provider=provider)
        result = agent.run("read both")
        assert len(result.tool_invocations) == 2

    def test_tool_error_passed_through_to_model(self, sandbox: Path) -> None:
        provider = FakeProvider(
            script=[
                ProviderTurnResult(
                    tool_calls=[
                        ProviderToolCall(
                            "t1", "read_file", {"filepath": "missing.txt"}
                        )
                    ]
                ),
                ProviderTurnResult(text="file not found, sorry"),
            ]
        )
        agent = FileSystemAssistant(provider=provider)
        result = agent.run("read it")
        assert result.tool_invocations[0].result["status"] == "error"
        assert result.text == "file not found, sorry"

    def test_iteration_limit_enforced(
        self, sandbox: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        from llm_file_assistant.config import reset_settings_cache

        monkeypatch.setenv("AGENT_MAX_ITERATIONS", "2")
        reset_settings_cache()
        # Three consecutive tool calls; only 2 iterations allowed.
        provider = FakeProvider(
            script=[
                ProviderTurnResult(
                    tool_calls=[ProviderToolCall("t1", "list_files", {"directory": "."})]
                )
            ]
            * 5
        )
        agent = FileSystemAssistant(provider=provider)
        with pytest.raises(AgentIterationLimitError):
            agent.run("loop forever")

    def test_empty_prompt_rejected(self, sandbox: Path) -> None:
        provider = FakeProvider(script=[])
        agent = FileSystemAssistant(provider=provider)
        with pytest.raises(ValueError):
            agent.run("   ")
