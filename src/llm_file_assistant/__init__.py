"""LLM-Powered File System Assistant.

Enterprise-grade Python package that exposes file system operations as
LLM-callable tools and orchestrates a tool-use agent loop against
OpenAI or Anthropic providers.
"""

from llm_file_assistant.fs_tools import (
    list_files,
    read_file,
    search_in_file,
    write_file,
)
from llm_file_assistant.llm_file_assistant import FileSystemAssistant

__all__ = [
    "FileSystemAssistant",
    "list_files",
    "read_file",
    "search_in_file",
    "write_file",
]

__version__ = "1.0.0"
