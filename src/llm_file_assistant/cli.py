"""Command-line interface for the LLM file system assistant.

Usage:
  llm-fs ask "Find resumes mentioning Python"      # one-shot
  llm-fs chat                                       # interactive REPL
  llm-fs tools                                      # list tools / sandbox info
"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Annotated

import typer
from rich.console import Console
from rich.markdown import Markdown
from rich.panel import Panel
from rich.table import Table

from llm_file_assistant import __version__, tools_registry
from llm_file_assistant.config import get_settings, reset_settings_cache
from llm_file_assistant.exceptions import (
    AgentIterationLimitError,
    ConfigurationError,
    FileAssistantError,
)
from llm_file_assistant.llm_file_assistant import (
    AgentRunResult,
    FileSystemAssistant,
)
from llm_file_assistant.logging_config import configure_logging

app = typer.Typer(
    name="llm-fs",
    help="Enterprise LLM-powered file system assistant.",
    no_args_is_help=True,
    add_completion=False,
)
console = Console()
err_console = Console(stderr=True)


def _version_callback(value: bool) -> None:
    if value:
        console.print(f"llm-fs {__version__}")
        raise typer.Exit()


@app.callback()
def main(
    version: Annotated[
        bool,
        typer.Option(
            "--version",
            "-V",
            callback=_version_callback,
            is_eager=True,
            help="Show version and exit.",
        ),
    ] = False,
) -> None:
    """LLM File Assistant — root callback."""
    configure_logging()


def _render_run(result: AgentRunResult, show_trace: bool) -> None:
    if show_trace and result.tool_invocations:
        table = Table(
            title=f"Tool calls ({len(result.tool_invocations)})",
            show_lines=True,
            header_style="bold",
        )
        table.add_column("#", justify="right")
        table.add_column("tool")
        table.add_column("arguments")
        table.add_column("status")
        for i, inv in enumerate(result.tool_invocations, 1):
            table.add_row(
                str(i),
                inv.name,
                json.dumps(inv.arguments, default=str),
                str(inv.result.get("status", "?")),
            )
        console.print(table)
    console.print(
        Panel(
            Markdown(result.text or "_(empty response)_"),
            title=(
                f"Assistant ({result.provider}/{result.model}) "
                f"— {result.iterations} iter · "
                f"{result.elapsed_seconds:.2f}s"
            ),
            border_style="cyan",
        )
    )


@app.command("ask")
def ask(
    prompt: Annotated[str, typer.Argument(help="Your question for the assistant.")],
    show_trace: Annotated[
        bool, typer.Option("--trace/--no-trace", help="Show tool-call trace.")
    ] = False,
    fs_root: Annotated[
        Path | None,
        typer.Option(
            "--root",
            help="Override the sandbox root for this invocation.",
            exists=False,
        ),
    ] = None,
) -> None:
    """Send a single question to the assistant and print the answer."""
    try:
        if fs_root is not None:
            import os

            os.environ["FS_ROOT"] = str(fs_root)
            reset_settings_cache()
        assistant = FileSystemAssistant()
        result = assistant.run(prompt)
        _render_run(result, show_trace=show_trace)
    except ConfigurationError as exc:
        err_console.print(f"[red]Configuration error:[/red] {exc}")
        raise typer.Exit(code=2) from exc
    except AgentIterationLimitError as exc:
        err_console.print(f"[red]Agent limit reached:[/red] {exc}")
        raise typer.Exit(code=3) from exc
    except FileAssistantError as exc:
        err_console.print(f"[red]Error:[/red] {exc}")
        raise typer.Exit(code=1) from exc


@app.command("chat")
def chat(
    show_trace: Annotated[
        bool, typer.Option("--trace/--no-trace", help="Show tool-call trace each turn.")
    ] = False,
) -> None:
    """Start an interactive multi-turn chat session.

    Each prompt is a fresh agent run against the LLM. Type 'exit' or
    Ctrl-D / Ctrl-C to quit.
    """
    try:
        assistant = FileSystemAssistant()
    except ConfigurationError as exc:
        err_console.print(f"[red]Configuration error:[/red] {exc}")
        raise typer.Exit(code=2) from exc

    settings = get_settings()
    console.print(
        Panel.fit(
            f"[bold]LLM File Assistant[/bold] "
            f"({assistant.provider.provider_name} / "
            f"{assistant.provider.model_name})\n"
            f"Sandbox: [cyan]{settings.fs_root}[/cyan]\n"
            "Type your request, or 'exit' to quit.",
            border_style="cyan",
        )
    )
    while True:
        try:
            prompt = console.input("[bold green]you[/bold green] » ").strip()
        except (EOFError, KeyboardInterrupt):
            console.print("\n[dim]bye[/dim]")
            return
        if not prompt:
            continue
        if prompt.lower() in {"exit", "quit", ":q"}:
            console.print("[dim]bye[/dim]")
            return
        try:
            result = assistant.run(prompt)
            _render_run(result, show_trace=show_trace)
        except FileAssistantError as exc:
            err_console.print(f"[red]Error:[/red] {exc}")


@app.command("tools")
def tools() -> None:
    """List registered tools and current sandbox configuration."""
    settings = get_settings()
    console.print(
        Panel.fit(
            f"Sandbox root: [cyan]{settings.fs_root}[/cyan]\n"
            f"Provider:     [cyan]{settings.llm_provider.value}[/cyan]\n"
            f"Max file:     [cyan]{settings.fs_max_file_bytes:,} bytes[/cyan]\n"
            f"Max iter:     [cyan]{settings.agent_max_iterations}[/cyan]",
            title="Configuration",
            border_style="cyan",
        )
    )
    table = Table(title="Registered tools", show_lines=True, header_style="bold")
    table.add_column("name")
    table.add_column("required")
    table.add_column("description")
    for desc in tools_registry.all_descriptors():
        table.add_row(
            desc.name,
            ", ".join(desc.parameters.required),
            desc.description,
        )
    console.print(table)


if __name__ == "__main__":  # pragma: no cover
    app()
