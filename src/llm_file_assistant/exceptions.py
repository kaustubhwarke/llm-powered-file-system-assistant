"""Custom exception hierarchy for the file system assistant."""

from __future__ import annotations


class FileAssistantError(Exception):
    """Base class for all package errors."""


class ConfigurationError(FileAssistantError):
    """Raised when configuration is invalid or missing."""


class FileSystemError(FileAssistantError):
    """Base class for filesystem-related errors."""


class PathSecurityError(FileSystemError):
    """Raised when a requested path escapes the configured sandbox root."""


class FileNotFoundInSandboxError(FileSystemError):
    """Raised when a target file does not exist within the sandbox."""


class FileTooLargeError(FileSystemError):
    """Raised when a file exceeds the configured maximum read size."""


class UnsupportedFileTypeError(FileSystemError):
    """Raised when a file extension is not supported for reading."""


class FileParseError(FileSystemError):
    """Raised when document parsing fails (corrupt PDF, malformed DOCX, etc)."""


class LLMProviderError(FileAssistantError):
    """Base class for LLM provider errors."""


class LLMResponseError(LLMProviderError):
    """Raised when the LLM returns malformed or unexpected output."""


class AgentIterationLimitError(LLMProviderError):
    """Raised when the agent loop exceeds the configured max iterations."""
