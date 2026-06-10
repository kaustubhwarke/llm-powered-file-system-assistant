"""Structured logging configuration using structlog."""

from __future__ import annotations

import logging
import sys

import structlog

from llm_file_assistant.config import LogLevel, get_settings

_configured: bool = False


def configure_logging(level: LogLevel | None = None) -> None:
    """Configure structlog and stdlib logging for the application.

    Idempotent — calling multiple times has no effect after the first.
    """
    global _configured
    if _configured:
        return

    log_level = (level or get_settings().log_level).value
    numeric_level = getattr(logging, log_level)

    logging.basicConfig(
        format="%(message)s",
        stream=sys.stderr,
        level=numeric_level,
    )

    structlog.configure(
        processors=[
            structlog.contextvars.merge_contextvars,
            structlog.processors.add_log_level,
            structlog.processors.TimeStamper(fmt="iso", utc=True),
            structlog.processors.StackInfoRenderer(),
            structlog.dev.set_exc_info,
            structlog.processors.format_exc_info,
            structlog.dev.ConsoleRenderer(colors=sys.stderr.isatty()),
        ],
        wrapper_class=structlog.make_filtering_bound_logger(numeric_level),
        context_class=dict,
        logger_factory=structlog.PrintLoggerFactory(file=sys.stderr),
        cache_logger_on_first_use=True,
    )
    _configured = True


def get_logger(name: str) -> structlog.stdlib.BoundLogger:
    """Return a configured structlog bound logger."""
    if not _configured:
        configure_logging()
    return structlog.get_logger(name)
