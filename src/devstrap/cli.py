from __future__ import annotations

import sys
from pathlib import Path
from typing import Optional

import typer
from rich.console import Console
from rich.table import Table

from devstrap import __version__
from devstrap.installer import InstallResult, check_tool, install_all
from devstrap.models import ToolConfig, load_manifest
from devstrap.platform import detect_platform

app = typer.Typer(help="Install dev tools from a YAML manifest.")
console = Console()


def version_callback(value: bool) -> None:
    if value:
        console.print(f"devstrap {__version__}")
        raise typer.Exit()


@app.callback()
def main(
    version: bool = typer.Option(False, "--version", callback=version_callback, is_eager=True, help="Show version."),
) -> None:
    pass


@app.command(name="list")
def list_tools(
    manifest: Optional[Path] = typer.Option(None, "--manifest", help="Path to custom tools.yaml"),
) -> None:
    """List all tools and their install status."""
    tools = load_manifest(manifest)
    platform = detect_platform()

    table = Table(title="Dev Tools")
    table.add_column("Name", style="bold")
    table.add_column("Description")
    table.add_column("Method")
    table.add_column("Status")

    for tool in tools:
        installed = check_tool(tool)
        status = "[green]installed[/green]" if installed else "[red]missing[/red]"
        method = _get_method(tool, platform)
        table.add_row(tool.name, tool.description, method, status)

    console.print(table)


@app.command()
def install(
    name: Optional[str] = typer.Argument(None, help="Tool name to install (all if omitted)"),
    interactive: bool = typer.Option(False, "--interactive", "-i", help="Select tools interactively"),
    dry_run: bool = typer.Option(False, "--dry-run", help="Show what would be installed"),
    manifest: Optional[Path] = typer.Option(None, "--manifest", help="Path to custom tools.yaml"),
) -> None:
    """Install dev tools."""
    tools = load_manifest(manifest)
    platform = detect_platform()

    # Single tool install — name validation before any other logic
    if name:
        matched = [t for t in tools if t.name == name]
        if not matched:
            console.print(f"[red]Error:[/red] Tool '{name}' not found in manifest.")
            raise typer.Exit(code=1)
        tools = matched

    # Interactive selection
    if interactive:
        if not sys.stdin.isatty():
            console.print("[red]Error:[/red] --interactive requires a TTY.")
            raise typer.Exit(code=1)
        tools = _interactive_select(tools)

    results = install_all(tools, platform, dry_run=dry_run)
    _print_results(results, dry_run=dry_run)

    if any(not r.success for r in results):
        raise typer.Exit(code=1)


def _interactive_select(tools: list[ToolConfig]) -> list[ToolConfig]:
    from InquirerPy import inquirer

    checked = []
    for tool in tools:
        installed = check_tool(tool)
        checked.append({"name": f"{tool.name} — {tool.description}", "value": tool.name, "enabled": not installed})

    selected = inquirer.checkbox(
        message="Select tools to install:",
        choices=checked,
    ).execute()

    return [t for t in tools if t.name in selected]


def _get_method(tool: ToolConfig, platform: Platform) -> str:
    if platform.pkg_manager and platform.pkg_manager in tool.install:
        return platform.pkg_manager
    if "script" in tool.install:
        return "script"
    return "[dim]none[/dim]"


def _print_results(results: list[InstallResult], dry_run: bool = False) -> None:
    console.print()
    for r in results:
        if r.status == "skipped":
            console.print(f"  [green]✓[/green] {r.name} — already installed")
        elif r.status == "installed":
            console.print(f"  [green]✓[/green] {r.name} — installed")
        elif r.status == "would_install":
            console.print(f"  [blue]→[/blue] {r.name} — {r.message}")
        elif r.status == "failed":
            console.print(f"  [red]✗[/red] {r.name} — {r.message}")

    console.print()
    installed = sum(1 for r in results if r.status == "installed")
    skipped = sum(1 for r in results if r.status == "skipped")
    failed = sum(1 for r in results if r.status == "failed")
    would = sum(1 for r in results if r.status == "would_install")

    if dry_run:
        console.print(f"Dry run: {would} to install, {skipped} already installed")
    else:
        console.print(f"Done: {installed} installed, {skipped} skipped, {failed} failed")
