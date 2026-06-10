"""LLM-driven file system agent (Part B).

This module wires the LLM provider together with the tool registry to form
a complete tool-calling agent. The :class:`FileSystemAssistant` owns the
control loop:

    user prompt
        -> provider.send_turn(tools)
            -> if tool_calls: execute each via registry, submit results, loop
            -> else: return final assistant text

The loop is hard-capped by ``AGENT_MAX_ITERATIONS`` to prevent runaway
billing or infinite loops from malformed tool responses.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from time import perf_counter
from typing import Any

from llm_file_assistant import tools_registry
from llm_file_assistant.config import Settings, get_settings
from llm_file_assistant.exceptions import AgentIterationLimitError
from llm_file_assistant.logging_config import get_logger
from llm_file_assistant.providers import LLMProviderClient, build_provider
from llm_file_assistant.providers.base import ProviderToolCall

logger = get_logger(__name__)


DEFAULT_SYSTEM_PROMPT = """\
You are an enterprise file-system assistant operating inside a sandboxed \
directory. You help users explore, summarize, and manage resume files \
through the provided tools.

Operating principles:
1. Always use the provided tools to inspect or modify files; never invent \
file contents.
2. Use list_files first to discover available files when the user gives a \
vague directory reference like "the resumes folder".
3. When a tool returns status="error", read the error_type field and \
recover gracefully — retry with corrected arguments or explain the \
limitation to the user. Never loop blindly on the same failing call.
4. Be concise. Cite filenames you observed in tool results, not invented \
ones. Use markdown for multi-resume summaries.
5. Only call write_file when the user has explicitly asked for a file to \
be created or saved.
"""


@dataclass
class ToolInvocation:
    """A record of a single tool call performed during an agent run."""

    name: str
    arguments: dict[str, Any]
    result: dict[str, Any]


@dataclass
class AgentRunResult:
    """The outcome of a complete agent run."""

    text: str
    iterations: int
    tool_invocations: list[ToolInvocation] = field(default_factory=list)
    elapsed_seconds: float = 0.0
    provider: str = ""
    model: str = ""


class FileSystemAssistant:
    """LLM-driven file system assistant with multi-turn tool calling."""

    def __init__(
        self,
        provider: LLMProviderClient | None = None,
        settings: Settings | None = None,
        system_prompt: str = DEFAULT_SYSTEM_PROMPT,
    ) -> None:
        self._settings = settings or get_settings()
        self._provider = provider or build_provider(self._settings)
        self._system_prompt = system_prompt

    @property
    def provider(self) -> LLMProviderClient:
        return self._provider

    def run(self, user_prompt: str) -> AgentRunResult:
        """Execute one full agent run for the given user prompt.

        Args:
            user_prompt: The user's natural-language request.

        Returns:
            An :class:`AgentRunResult` containing the assistant's final
            text, the list of tool invocations performed, and timing data.

        Raises:
            AgentIterationLimitError: if the loop exceeds
                ``AGENT_MAX_ITERATIONS`` without producing a final answer.
        """
        if not user_prompt or not user_prompt.strip():
            raise ValueError("user_prompt must be a non-empty string")

        logger.info(
            "agent.run.start",
            provider=self._provider.provider_name,
            model=self._provider.model_name,
        )
        started = perf_counter()
        self._provider.start_conversation(self._system_prompt, user_prompt)

        descriptors = tools_registry.all_descriptors()
        invocations: list[ToolInvocation] = []
        max_iter = self._settings.agent_max_iterations

        for iteration in range(1, max_iter + 1):
            logger.debug("agent.iteration.start", iteration=iteration)
            turn = self._provider.send_turn(descriptors)

            if not turn.tool_calls:
                elapsed = perf_counter() - started
                logger.info(
                    "agent.run.end",
                    iterations=iteration,
                    tool_calls=len(invocations),
                    elapsed_seconds=round(elapsed, 3),
                )
                return AgentRunResult(
                    text=turn.text or "",
                    iterations=iteration,
                    tool_invocations=invocations,
                    elapsed_seconds=elapsed,
                    provider=self._provider.provider_name,
                    model=self._provider.model_name,
                )

            results = self._execute_calls(turn.tool_calls, invocations)
            self._provider.submit_tool_results(results)

        raise AgentIterationLimitError(
            f"Agent did not finish within {max_iter} iterations"
        )

    def _execute_calls(
        self,
        calls: list[ProviderToolCall],
        invocations: list[ToolInvocation],
    ) -> list[tuple[ProviderToolCall, dict[str, Any]]]:
        results: list[tuple[ProviderToolCall, dict[str, Any]]] = []
        for call in calls:
            logger.info(
                "agent.tool_call",
                name=call.name,
                argument_keys=sorted(call.arguments.keys()),
            )
            result = tools_registry.execute(call.name, call.arguments)
            invocations.append(
                ToolInvocation(name=call.name, arguments=call.arguments, result=result)
            )
            results.append((call, result))
        return results
