"""Shared pytest fixtures."""

from __future__ import annotations

import os
from pathlib import Path
from typing import Iterator

import pytest

from llm_file_assistant.config import reset_settings_cache


@pytest.fixture
def sandbox(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Iterator[Path]:
    """Point the assistant's sandbox at an isolated tmp_path."""
    monkeypatch.setenv("FS_ROOT", str(tmp_path))
    monkeypatch.setenv("FS_MAX_FILE_BYTES", str(10 * 1024 * 1024))
    monkeypatch.setenv("LLM_PROVIDER", "openai")
    monkeypatch.setenv("OPENAI_API_KEY", "sk-test-not-real")
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-ant-test-not-real")
    reset_settings_cache()
    yield tmp_path
    reset_settings_cache()
