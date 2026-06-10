"""Turnkey end-to-end demo of the LLM-Powered File System Assistant.

Run this with a recorder running (OBS, Windows Game Bar Win+G, ShareX, Loom)
and you have your submission video. The script:

    Section 1 — Part A: calls each of the four file system tools directly
                so you can show the raw contracts and outputs.
    Section 2 — Part B: drives the FileSystemAssistant agent with the
                three example queries from the assignment brief.

By default the script pauses between sections so you can narrate. Pass
``--auto`` to run end-to-end without pauses.

Usage:
    python scripts/demo.py                 # narrated mode (pauses)
    python scripts/demo.py --auto          # no pauses, for re-runs
    python scripts/demo.py --no-trace      # hide tool-call traces
"""

from __future__ import annotations

import argparse
import os
import shutil
import sys
import time
from pathlib import Path
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT / "src"))

# Force UTF-8 on Windows consoles so rich's box-drawing renders.
for _stream in (sys.stdout, sys.stderr):
    reconfigure = getattr(_stream, "reconfigure", None)
    if reconfigure is not None:
        try:
            reconfigure(encoding="utf-8", errors="replace")
        except (ValueError, OSError):
            pass

# Force the sandbox to point at this repo's data/ before any settings load.
os.environ.setdefault("FS_ROOT", str(PROJECT_ROOT / "data"))

import json  # noqa: E402

from rich.console import Console  # noqa: E402
from rich.markdown import Markdown  # noqa: E402
from rich.panel import Panel  # noqa: E402
from rich.rule import Rule  # noqa: E402
from rich.syntax import Syntax  # noqa: E402
from rich.table import Table  # noqa: E402

from llm_file_assistant import (  # noqa: E402
    __version__,
    fs_tools,
)
from llm_file_assistant.config import LLMProvider, get_settings  # noqa: E402
from llm_file_assistant.exceptions import ConfigurationError  # noqa: E402
from llm_file_assistant.llm_file_assistant import (  # noqa: E402
    AgentRunResult,
    FileSystemAssistant,
)

console = Console()


# ----------------------------------------------------------------------
# helpers
# ----------------------------------------------------------------------


def banner(title: str, subtitle: str | None = None) -> None:
    console.print()
    console.print(Rule(style="cyan"))
    body = f"[bold cyan]{title}[/bold cyan]"
    if subtitle:
        body += f"\n[dim]{subtitle}[/dim]"
    console.print(Panel.fit(body, border_style="cyan"))
    console.print(Rule(style="cyan"))


def pause(auto: bool, prompt: str = "press Enter to continue") -> None:
    if auto:
        time.sleep(1.0)
        return
    try:
        console.input(f"[dim]({prompt})[/dim] ")
    except (EOFError, KeyboardInterrupt):
        console.print("\n[dim]aborted[/dim]")
        sys.exit(0)


def show_command(label: str, code: str) -> None:
    console.print(f"[bold yellow]>> {label}[/bold yellow]")
    console.print(Syntax(code, "python", theme="monokai", background_color="default"))


def show_result(result: dict[str, Any], *, truncate: int = 600) -> None:
    pretty = json.dumps(result, indent=2, default=str)
    if len(pretty) > truncate:
        pretty = pretty[:truncate] + f"\n... (+{len(pretty) - truncate} more chars)"
    console.print(
        Syntax(pretty, "json", theme="monokai", background_color="default")
    )


def render_agent_run(result: AgentRunResult, *, show_trace: bool) -> None:
    if show_trace and result.tool_invocations:
        table = Table(
            title=f"Tool calls ({len(result.tool_invocations)})",
            show_lines=True,
            header_style="bold",
        )
        table.add_column("#", justify="right")
        table.add_column("tool")
        table.add_column("arguments", overflow="fold")
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
                f"Assistant — {result.provider}/{result.model} "
                f"· {result.iterations} iter · {result.elapsed_seconds:.2f}s"
            ),
            border_style="green",
        )
    )


def cleanup_demo_artifacts() -> None:
    """Remove anything the demo wrote so it can be re-run cleanly."""
    target = PROJECT_ROOT / "data" / "summaries"
    if target.exists():
        shutil.rmtree(target)


# ----------------------------------------------------------------------
# Sections
# ----------------------------------------------------------------------


def section_intro(auto: bool) -> None:
    settings = get_settings()
    banner(
        f"LLM-Powered File System Assistant — Demo v{__version__}",
        f"Provider: {settings.llm_provider.value} | "
        f"Sandbox: {settings.fs_root}",
    )
    console.print(
        "This demo walks the marker through both halves of the assignment:\n"
        "  • Part A — the four core file system tools, called directly\n"
        "  • Part B — the LLM agent driving those tools via tool-calling\n"
    )
    pause(auto, "press Enter to begin Part A")


def section_part_a(auto: bool) -> None:
    banner(
        "Part A — Core file system tools",
        "Direct calls into fs_tools.py — no LLM in the loop",
    )

    # 1. list_files
    console.print(Rule("[bold]1/4 list_files[/bold]", style="white"))
    show_command(
        "fs_tools.list_files('resumes')",
        "from llm_file_assistant import list_files\nlist_files('resumes')",
    )
    result = fs_tools.list_files("resumes")
    show_result(result, truncate=1200)
    pause(auto)

    # 2. list_files with extension filter
    console.print(Rule("[bold]list_files with extension filter[/bold]", style="white"))
    show_command(
        "fs_tools.list_files('resumes', extension='pdf')",
        "list_files('resumes', extension='pdf')",
    )
    result = fs_tools.list_files("resumes", extension="pdf")
    show_result(result, truncate=800)
    pause(auto)

    # 3. read_file across all three formats
    console.print(Rule("[bold]2/4 read_file (TXT, DOCX, PDF)[/bold]", style="white"))
    for sample in (
        "resumes/alice_johnson.txt",
        "resumes/elena_petrov.docx",
        "resumes/henry_anderson.pdf",
    ):
        show_command(f"read_file({sample!r})", f"read_file({sample!r})")
        result = fs_tools.read_file(sample)
        show_result(result, truncate=500)
        console.print()
    pause(auto)

    # 4. search_in_file
    console.print(Rule("[bold]3/4 search_in_file[/bold]", style="white"))
    show_command(
        "search_in_file('resumes/alice_johnson.txt', 'Python')",
        "search_in_file('resumes/alice_johnson.txt', 'Python')",
    )
    result = fs_tools.search_in_file("resumes/alice_johnson.txt", "Python")
    show_result(result, truncate=900)
    pause(auto)

    # 5. write_file
    console.print(Rule("[bold]4/4 write_file (with auto-mkdir)[/bold]", style="white"))
    show_command(
        "write_file('demo_output/note.txt', '...')",
        "write_file('demo_output/note.txt', "
        "'Hello from the demo at ' + time.ctime())",
    )
    result = fs_tools.write_file(
        "demo_output/note.txt",
        f"Hello from the demo at {time.ctime()}",
    )
    show_result(result)
    pause(auto)

    # 6. Security: traversal blocked
    console.print(Rule("[bold]Security — path traversal blocked[/bold]", style="red"))
    show_command(
        "read_file('../../etc/passwd')   # must be rejected",
        "read_file('../../etc/passwd')",
    )
    result = fs_tools.read_file("../../etc/passwd")
    show_result(result, truncate=400)
    pause(auto, "press Enter to start Part B")


def section_part_b(auto: bool, show_trace: bool) -> None:
    banner(
        "Part B — LLM agent with tool calling",
        "FileSystemAssistant.run() drives the LLM through a tool-use loop",
    )

    try:
        assistant = FileSystemAssistant()
    except ConfigurationError as exc:
        console.print(
            Panel(
                f"[red]Cannot run Part B — {exc}[/red]\n\n"
                "Set OPENAI_API_KEY (or ANTHROPIC_API_KEY + "
                "LLM_PROVIDER=anthropic) in .env or your shell, "
                "then re-run the demo.",
                title="API key missing",
                border_style="red",
            )
        )
        return

    queries = [
        (
            "Read all resumes in the resumes folder",
            "List the files in the resumes folder and give me a one-line "
            "summary of each candidate.",
        ),
        (
            "Find resumes mentioning Python experience",
            "Which candidates in the resumes folder mention Python "
            "experience? For each match, name the file and quote the "
            "relevant line.",
        ),
        (
            "Create a summary file",
            "Read resumes/alice_johnson.txt and write a concise markdown "
            "summary of Alice's experience to summaries/alice_johnson.md.",
        ),
    ]

    for i, (label, prompt) in enumerate(queries, 1):
        console.print(
            Rule(f"[bold]Query {i}/{len(queries)} — {label}[/bold]", style="white")
        )
        console.print(Panel(prompt, title="User prompt", border_style="yellow"))
        result = assistant.run(prompt)
        render_agent_run(result, show_trace=show_trace)
        pause(auto)


def section_outro(auto: bool) -> None:  # noqa: ARG001
    banner(
        "Demo complete",
        "tests: `pytest`  ·  source: src/llm_file_assistant/  ·  "
        "docs: README.md",
    )
    summary_path = PROJECT_ROOT / "data" / "summaries" / "alice_johnson.md"
    if summary_path.exists():
        console.print(
            f"[green]✓[/green] Agent wrote: "
            f"[cyan]{summary_path.relative_to(PROJECT_ROOT)}[/cyan]"
        )
    else:
        console.print(
            "[dim]No summary file was written this run "
            "(model may have chosen a different filename).[/dim]"
        )


# ----------------------------------------------------------------------
# Entry point
# ----------------------------------------------------------------------


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--auto",
        action="store_true",
        help="Run without pausing between sections (for re-runs).",
    )
    parser.add_argument(
        "--no-trace",
        action="store_true",
        help="Hide the per-turn tool-call trace in Part B.",
    )
    parser.add_argument(
        "--skip-part-a",
        action="store_true",
        help="Skip Part A (useful if you only want to record the agent).",
    )
    parser.add_argument(
        "--skip-part-b",
        action="store_true",
        help="Skip Part B (useful if you have no API key configured).",
    )
    args = parser.parse_args()

    cleanup_demo_artifacts()
    # warn loudly if Part B will be skipped due to missing creds
    settings = get_settings()
    if not args.skip_part_b:
        try:
            settings.require_provider_credentials()
        except ConfigurationError:
            provider = settings.llm_provider.value
            console.print(
                Panel(
                    f"[yellow]Heads up:[/yellow] no API key found for "
                    f"provider [bold]{provider}[/bold]. Part B will display "
                    f"an error panel instead of running the LLM. Set "
                    f"{'OPENAI_API_KEY' if settings.llm_provider is LLMProvider.OPENAI else 'ANTHROPIC_API_KEY'} "
                    "in .env to enable it.",
                    border_style="yellow",
                )
            )

    section_intro(args.auto)
    if not args.skip_part_a:
        section_part_a(args.auto)
    if not args.skip_part_b:
        section_part_b(args.auto, show_trace=not args.no_trace)
    section_outro(args.auto)
    return 0


if __name__ == "__main__":
    sys.exit(main())
