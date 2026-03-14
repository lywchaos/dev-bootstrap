from __future__ import annotations

import sys
from pathlib import Path
from typing import Optional

import typer
from rich.console import Console
from rich.table import Table

from devstrap import __version__
from devstrap.installer import (
    InstallResult,
    check_tool,
    install_tool,
    resolve_install_order,
)
from devstrap.models import ToolConfig, load_manifest
from devstrap.platform import Platform, detect_platform

app = typer.Typer(help="Install dev tools from a YAML manifest.")
console = Console()


def version_callback(value: bool) -> None:
    if value:
        console.print(f"devstrap {__version__}")
        raise typer.Exit()


@app.callback()
def main(
    version: bool = typer.Option(
        False,
        "--version",
        callback=version_callback,
        is_eager=True,
        help="Show version.",
    ),
) -> None:
    pass


@app.command(name="list")
def list_tools(
    manifest: Optional[Path] = typer.Option(
        None, "--manifest", help="Path to custom tools.yaml"
    ),
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
    name: Optional[str] = typer.Argument(
        None, help="Tool name to install (all if omitted)"
    ),
    interactive: bool = typer.Option(
        False, "--interactive", "-i", help="Select tools interactively"
    ),
    dry_run: bool = typer.Option(
        False, "--dry-run", help="Show what would be installed"
    ),
    manifest: Optional[Path] = typer.Option(
        None, "--manifest", help="Path to custom tools.yaml"
    ),
) -> None:
    """Install dev tools."""
    tools = load_manifest(manifest)
    platform = detect_platform()

    # Single tool install — resolve with transitive deps
    if name:
        matched = [t for t in tools if t.name == name]
        if not matched:
            console.print(f"[red]Error:[/red] Tool '{name}' not found in manifest.")
            raise typer.Exit(code=1)
        tools = _collect_with_deps(matched[0], {t.name: t for t in tools})

    # Interactive selection
    if interactive:
        if not sys.stdin.isatty():
            console.print("[red]Error:[/red] --interactive requires a TTY.")
            raise typer.Exit(code=1)
        tools = _interactive_select(tools)

    # Resolve dependency order
    tools = resolve_install_order(tools)

    results = _install_tools(tools, platform, dry_run=dry_run)
    _print_summary(results, dry_run=dry_run)

    if any(not r.success for r in results):
        raise typer.Exit(code=1)


def _collect_with_deps(
    tool: ToolConfig, lookup: dict[str, ToolConfig]
) -> list[ToolConfig]:
    """Collect a tool and all its transitive deps."""
    collected: dict[str, ToolConfig] = {}

    def _walk(t: ToolConfig) -> None:
        if t.name in collected:
            return
        for dep_name in t.deps:
            _walk(lookup[dep_name])
        collected[t.name] = t

    _walk(tool)
    return list(collected.values())


def _install_tools(
    tools: list[ToolConfig], platform: Platform, dry_run: bool = False
) -> list[InstallResult]:
    results: list[InstallResult] = []
    failed: set[str] = set()
    for tool in tools:
        failed_deps = [d for d in tool.deps if d in failed]
        if failed_deps:
            result = InstallResult(
                name=tool.name,
                status="dep_failed",
                success=False,
                message=f"Skipped (dep {failed_deps[0]} failed)",
            )
            failed.add(tool.name)
        else:
            result = _process_tool(tool, platform, dry_run=dry_run)
            if not result.success:
                failed.add(tool.name)
        results.append(result)
        _print_result(result)
    return results


def _process_tool(
    tool: ToolConfig, platform: Platform, dry_run: bool = False
) -> InstallResult:
    console.print(f"  [dim]Checking {tool.name}...[/dim]", end="\r")
    if check_tool(tool):
        return InstallResult(
            name=tool.name,
            status="skipped",
            success=True,
            message="Already installed",
        )
    if dry_run:
        return InstallResult(
            name=tool.name,
            status="would_install",
            success=True,
            message=_describe_install(tool, platform),
        )
    console.print(f"  [bold]Installing {tool.name}...[/bold]")
    return install_tool(tool, platform)


def _print_result(result: InstallResult) -> None:
    icon, label = _STATUS_FORMAT.get(result.status, ("?", result.status))
    text = label if label else result.message
    console.print(f"  {icon} {result.name} — {text}")


def _interactive_select(tools: list[ToolConfig]) -> list[ToolConfig]:
    from InquirerPy import inquirer

    checked = []
    for tool in tools:
        installed = check_tool(tool)
        checked.append(
            {
                "name": f"{tool.name} — {tool.description}",
                "value": tool.name,
                "enabled": not installed,
            }
        )

    selected = inquirer.checkbox(
        message="Select tools to install:",
        choices=checked,
    ).execute()

    return [t for t in tools if t.name in selected]


def _get_method(tool: ToolConfig, platform: Platform) -> str:
    if platform.pkg_manager and platform.pkg_manager in tool.install:
        return platform.pkg_manager
    if "scripts" in tool.install:
        return "script"
    return "[dim]none[/dim]"


_STATUS_FORMAT = {
    "skipped": ("[green]✓[/green]", "already installed"),
    "installed": ("[green]✓[/green]", "installed"),
    "would_install": ("[blue]→[/blue]", None),  # uses message
    "failed": ("[red]✗[/red]", None),  # uses message
    "dep_failed": ("[yellow]⊘[/yellow]", None),  # uses message
}


def _describe_install(tool: ToolConfig, platform: Platform) -> str:
    if platform.pkg_manager and platform.pkg_manager in tool.install:
        pkg_name = tool.install[platform.pkg_manager]
        assert isinstance(pkg_name, str)
        cmd = platform.install_cmd(pkg_name)
        return " ".join(cmd)
    if "scripts" in tool.install:
        scripts = tool.install["scripts"]
        return " || ".join(scripts)
    return f"No install method for {platform.os_name} ({platform.pkg_manager})"


def _print_summary(results: list[InstallResult], dry_run: bool = False) -> None:
    console.print()
    counts = {s: sum(1 for r in results if r.status == s) for s in _STATUS_FORMAT}

    if dry_run:
        console.print(
            f"Dry run: {counts['would_install']} to install, {counts['skipped']} already installed"
        )
    else:
        parts = [
            f"{counts['installed']} installed",
            f"{counts['skipped']} skipped",
            f"{counts['failed']} failed",
        ]
        if counts["dep_failed"]:
            parts.append(f"{counts['dep_failed']} dep-skipped")
        console.print(f"Done: {', '.join(parts)}")
