"""Pydantic models for tool inputs and outputs.

These models give us validated, self-documenting contracts at the
LLM-tool boundary and serve as the source of truth for tool JSON schemas
delivered to the model.
"""

from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field


class ToolStatus(str, Enum):
    """Status of a tool invocation."""

    SUCCESS = "success"
    ERROR = "error"


class BaseToolResult(BaseModel):
    """Common envelope for all tool results."""

    model_config = ConfigDict(extra="forbid")

    status: ToolStatus
    error: str | None = None
    error_type: str | None = None


# ---------- read_file ----------


class FileMetadata(BaseModel):
    """Metadata describing a single file."""

    model_config = ConfigDict(extra="forbid")

    name: str
    path: str
    extension: str
    size_bytes: int = Field(ge=0)
    modified_at: datetime


class ReadFileInput(BaseModel):
    """Input schema for read_file tool."""

    model_config = ConfigDict(extra="forbid")

    filepath: str = Field(
        description="Relative path (from the sandbox root) of the file to read."
    )


class ReadFileResult(BaseToolResult):
    """Result of reading a file."""

    content: str | None = None
    metadata: FileMetadata | None = None
    page_count: int | None = Field(default=None, description="PDFs only.")


# ---------- list_files ----------


class ListFilesInput(BaseModel):
    """Input schema for list_files tool."""

    model_config = ConfigDict(extra="forbid")

    directory: str = Field(
        description="Relative path (from the sandbox root) of the directory to list."
    )
    extension: str | None = Field(
        default=None,
        description="Optional file extension to filter by (with or without leading dot).",
    )


class ListFilesResult(BaseToolResult):
    """Result of listing files in a directory."""

    directory: str | None = None
    count: int = 0
    files: list[FileMetadata] = Field(default_factory=list)


# ---------- write_file ----------


class WriteFileInput(BaseModel):
    """Input schema for write_file tool."""

    model_config = ConfigDict(extra="forbid")

    filepath: str = Field(
        description="Relative path (from the sandbox root) of the file to write."
    )
    content: str = Field(description="UTF-8 text content to write.")
    overwrite: bool = Field(
        default=True,
        description="If false and the target exists, the operation fails.",
    )


class WriteFileResult(BaseToolResult):
    """Result of writing a file."""

    path: str | None = None
    bytes_written: int | None = None
    created_directories: bool = False
    overwritten: bool = False


# ---------- search_in_file ----------


class SearchMatch(BaseModel):
    """A single keyword match with surrounding context."""

    model_config = ConfigDict(extra="forbid")

    line_number: int = Field(ge=1)
    line: str
    context_before: list[str] = Field(default_factory=list)
    context_after: list[str] = Field(default_factory=list)
    char_offset: int = Field(ge=0, description="Offset of the match within the line.")


class SearchInFileInput(BaseModel):
    """Input schema for search_in_file tool."""

    model_config = ConfigDict(extra="forbid")

    filepath: str = Field(
        description="Relative path (from the sandbox root) of the file to search."
    )
    keyword: str = Field(min_length=1, description="Substring to search for.")
    context_lines: int = Field(
        default=2,
        ge=0,
        le=10,
        description="Number of surrounding lines to return as context.",
    )


class SearchInFileResult(BaseToolResult):
    """Result of a keyword search."""

    filepath: str | None = None
    keyword: str | None = None
    match_count: int = 0
    matches: list[SearchMatch] = Field(default_factory=list)


# ---------- LLM tool descriptors ----------


class ToolParameter(BaseModel):
    """JSON-schema-like parameter descriptor for an LLM tool."""

    model_config = ConfigDict(extra="forbid")

    type: Literal["object"] = "object"
    properties: dict[str, Any]
    required: list[str] = Field(default_factory=list)
    additionalProperties: bool = False


class ToolDescriptor(BaseModel):
    """Provider-neutral descriptor of a callable tool."""

    model_config = ConfigDict(extra="forbid")

    name: str
    description: str
    parameters: ToolParameter
