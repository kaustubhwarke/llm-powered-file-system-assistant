"""Central registry mapping tool names to callables and JSON schemas.

The agent loop never calls a Python function directly. It calls a tool
*by name* through this registry, which:

  * validates the registry exists at startup,
  * exposes a single ``execute`` dispatch surface,
  * produces provider-neutral :class:`ToolDescriptor` objects that the
    LLM-provider layer translates into OpenAI or Anthropic tool schemas.

Keeping this layer separate means adding a new tool is a one-line change.
"""

from __future__ import annotations

import json
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from llm_file_assistant import fs_tools
from llm_file_assistant.logging_config import get_logger
from llm_file_assistant.schemas import ToolDescriptor, ToolParameter

logger = get_logger(__name__)

ToolCallable = Callable[..., dict[str, Any]]


@dataclass(frozen=True)
class ToolSpec:
    """Internal record binding a descriptor to its Python callable."""

    descriptor: ToolDescriptor
    handler: ToolCallable


def _build_registry() -> dict[str, ToolSpec]:
    return {
        "read_file": ToolSpec(
            descriptor=ToolDescriptor(
                name="read_file",
                description=(
                    "Read a file from the sandbox and return its full text "
                    "content along with metadata. Supports .txt, .md, .pdf, "
                    "and .docx documents. Use this to inspect resume content."
                ),
                parameters=ToolParameter(
                    properties={
                        "filepath": {
                            "type": "string",
                            "description": (
                                "Path relative to the sandbox root, e.g. "
                                "'resumes/alice.pdf'."
                            ),
                        },
                    },
                    required=["filepath"],
                ),
            ),
            handler=fs_tools.read_file,
        ),
        "list_files": ToolSpec(
            descriptor=ToolDescriptor(
                name="list_files",
                description=(
                    "List files inside a directory in the sandbox, optionally "
                    "filtering by file extension. Returns name, size, and "
                    "modification time for each file."
                ),
                parameters=ToolParameter(
                    properties={
                        "directory": {
                            "type": "string",
                            "description": (
                                "Directory path relative to the sandbox root "
                                "(use '.' for the root itself)."
                            ),
                        },
                        "extension": {
                            "type": ["string", "null"],
                            "description": (
                                "Optional extension filter, with or without "
                                "the leading dot (e.g. 'pdf' or '.pdf'). "
                                "Pass null to list all files."
                            ),
                            "default": None,
                        },
                    },
                    required=["directory"],
                ),
            ),
            handler=fs_tools.list_files,
        ),
        "write_file": ToolSpec(
            descriptor=ToolDescriptor(
                name="write_file",
                description=(
                    "Write UTF-8 text content to a file inside the sandbox. "
                    "Creates parent directories as needed. Overwrites an "
                    "existing file. Use this to create summary or report files."
                ),
                parameters=ToolParameter(
                    properties={
                        "filepath": {
                            "type": "string",
                            "description": (
                                "Path relative to the sandbox root for the "
                                "file to write."
                            ),
                        },
                        "content": {
                            "type": "string",
                            "description": "UTF-8 text content to write.",
                        },
                    },
                    required=["filepath", "content"],
                ),
            ),
            handler=fs_tools.write_file,
        ),
        "search_in_file": ToolSpec(
            descriptor=ToolDescriptor(
                name="search_in_file",
                description=(
                    "Case-insensitive substring search inside a single file. "
                    "Returns each matching line along with surrounding context."
                ),
                parameters=ToolParameter(
                    properties={
                        "filepath": {
                            "type": "string",
                            "description": (
                                "Path relative to the sandbox root for the "
                                "file to search."
                            ),
                        },
                        "keyword": {
                            "type": "string",
                            "description": "Substring to search for (case-insensitive).",
                        },
                        "context_lines": {
                            "type": "integer",
                            "description": (
                                "Number of context lines to include before "
                                "and after each match (0-10)."
                            ),
                            "default": 2,
                            "minimum": 0,
                            "maximum": 10,
                        },
                    },
                    required=["filepath", "keyword"],
                ),
            ),
            handler=fs_tools.search_in_file,
        ),
    }


_REGISTRY: dict[str, ToolSpec] = _build_registry()


def all_descriptors() -> list[ToolDescriptor]:
    """Return all registered tool descriptors."""
    return [spec.descriptor for spec in _REGISTRY.values()]


def execute(name: str, arguments: dict[str, Any] | str) -> dict[str, Any]:
    """Dispatch a tool call by name with the supplied arguments.

    Args:
        name: Registered tool name.
        arguments: Either a dict of kwargs or a JSON string thereof.

    Returns:
        The tool's JSON-serializable result dict. Errors are reported as
        ``{"status": "error", "error": "...", "error_type": "..."}`` rather
        than raised, so the LLM can observe and recover.
    """
    spec = _REGISTRY.get(name)
    if spec is None:
        logger.warning("tool.dispatch.unknown", name=name)
        return {
            "status": "error",
            "error": f"Unknown tool: {name}",
            "error_type": "UnknownToolError",
        }

    if isinstance(arguments, str):
        try:
            arguments = json.loads(arguments) if arguments else {}
        except json.JSONDecodeError as exc:
            logger.warning("tool.dispatch.bad_json", name=name, error=str(exc))
            return {
                "status": "error",
                "error": f"Arguments were not valid JSON: {exc}",
                "error_type": "InvalidArgumentsError",
            }

    if not isinstance(arguments, dict):
        return {
            "status": "error",
            "error": f"Arguments must be an object, got {type(arguments).__name__}",
            "error_type": "InvalidArgumentsError",
        }

    logger.debug("tool.dispatch.start", name=name, arguments=arguments)
    try:
        result = spec.handler(**arguments)
    except TypeError as exc:
        logger.warning("tool.dispatch.bad_args", name=name, error=str(exc))
        return {
            "status": "error",
            "error": f"Bad arguments for tool {name}: {exc}",
            "error_type": "InvalidArgumentsError",
        }
    logger.debug("tool.dispatch.end", name=name, status=result.get("status"))
    return result
