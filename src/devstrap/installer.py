from __future__ import annotations

import subprocess
from collections import deque
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path

from devstrap.models import ToolConfig
from devstrap.platform import Platform


@dataclass
class InstallResult:
    name: str
    status: str  # "installed", "skipped", "failed", "would_install"
    success: bool
    message: str


def _prepare_script(script: str) -> str:
    """Prepend set -e to multiline scripts that don't already handle errors."""
    if "\n" not in script:
        return script
    if script.startswith("#!") or script.startswith("set -"):
        return script
    return f"set -e\n{script}"


def _run_script(script: str) -> None:
    """Execute a script string with shell=True."""
    prepared = _prepare_script(script)
    subprocess.run(prepared, shell=True, check=True, text=True)


def _run_script_file(script_file: str) -> None:
    """Read and execute an external script file."""
    content = Path(script_file).read_text(encoding="utf-8")
    subprocess.run(content, shell=True, check=True, text=True)


def check_tool(tool: ToolConfig) -> bool:
    if not tool.check:
        return False
    try:
        result = subprocess.run(
            tool.check,
            shell=True,
            capture_output=True,
            timeout=5,
        )
        return result.returncode == 0
    except FileNotFoundError:
        return False
    except subprocess.TimeoutExpired:
        from rich.console import Console

        Console(stderr=True).print(
            f"[yellow]Warning:[/yellow] Check for '{tool.name}' timed out"
        )
        return False


def _validate_deps(tools: list[ToolConfig], lookup: dict[str, ToolConfig]) -> None:
    """Raise ValueError if any tool references an unknown dependency."""
    for tool in tools:
        for dep in tool.deps:
            if dep not in lookup:
                raise ValueError(f"Tool '{tool.name}' depends on unknown tool '{dep}'")


def _build_graph(
    tools: list[ToolConfig],
) -> tuple[dict[str, int], dict[str, list[str]]]:
    """Build in-degree map and adjacency list from tool deps."""
    in_degree: dict[str, int] = {t.name: 0 for t in tools}
    dependents: dict[str, list[str]] = {t.name: [] for t in tools}
    for tool in tools:
        for dep in tool.deps:
            in_degree[tool.name] += 1
            dependents[dep].append(tool.name)
    return in_degree, dependents


def _topo_sort(
    tools: list[ToolConfig],
    in_degree: dict[str, int],
    dependents: dict[str, list[str]],
) -> list[str]:
    """BFS topological sort. Returns sorted names or raises on cycle."""
    queue: deque[str] = deque(t.name for t in tools if in_degree[t.name] == 0)
    sorted_names: list[str] = []
    while queue:
        name = queue.popleft()
        sorted_names.append(name)
        for dep in dependents[name]:
            in_degree[dep] -= 1
            if in_degree[dep] == 0:
                queue.append(dep)
    if len(sorted_names) != len(tools):
        remaining = [n for n in in_degree if n not in sorted_names]
        raise ValueError(f"Dependency cycle detected among: {', '.join(remaining)}")
    return sorted_names


def resolve_install_order(tools: list[ToolConfig]) -> list[ToolConfig]:
    """Topologically sort tools by deps using Kahn's algorithm."""
    lookup = {t.name: t for t in tools}
    _validate_deps(tools, lookup)
    in_degree, dependents = _build_graph(tools)
    sorted_names = _topo_sort(tools, in_degree, dependents)
    return [lookup[name] for name in sorted_names]


def _try_install(
    name: str, func: Callable, *args: object, **kwargs: object
) -> InstallResult:
    """Run *func* and return an InstallResult (installed or failed)."""
    try:
        func(*args, **kwargs)
        return InstallResult(name=name, status="installed", success=True, message="")
    except subprocess.CalledProcessError as e:
        return InstallResult(name=name, status="failed", success=False, message=str(e))


def _install_via_alternatives(tool: ToolConfig, spec) -> InstallResult:
    """Try each alternative in order; return on first success."""
    last_error = ""
    for i, entry in enumerate(spec.alternatives):
        try:
            if entry.script:
                _run_script(entry.script)
            elif entry.script_file:
                _run_script_file(entry.script_file)
            return InstallResult(
                name=tool.name, status="installed", success=True, message=""
            )
        except subprocess.CalledProcessError as e:
            last_error = str(e)
            if i < len(spec.alternatives) - 1:
                from rich.console import Console

                Console(stderr=True).print(
                    f"[yellow]Warning:[/yellow] Script failed for '{tool.name}': {e}, trying next..."
                )
    return InstallResult(
        name=tool.name, status="failed", success=False, message=last_error
    )


def install_tool(tool: ToolConfig, platform: Platform) -> InstallResult:
    spec = tool.install

    # Try package manager first
    if platform.pkg_manager and platform.pkg_manager in spec.package_managers:
        pkg_name = spec.package_managers[platform.pkg_manager]
        cmd = platform.install_cmd(pkg_name)
        return _try_install(tool.name, subprocess.run, cmd, check=True, text=True)

    # Try single script
    if spec.script:
        return _try_install(tool.name, _run_script, spec.script)

    # Try script file
    if spec.script_file:
        return _try_install(tool.name, _run_script_file, spec.script_file)

    # Try alternatives (fallback chain)
    if spec.alternatives:
        return _install_via_alternatives(tool, spec)

    return InstallResult(
        name=tool.name,
        status="failed",
        success=False,
        message=f"No install method for '{tool.name}' on {platform.os_name} ({platform.pkg_manager})",
    )


def install_all(
    tools: list[ToolConfig],
    platform: Platform,
    dry_run: bool = False,
) -> list[InstallResult]:
    results: list[InstallResult] = []
    for tool in tools:
        if check_tool(tool):
            results.append(
                InstallResult(
                    name=tool.name,
                    status="skipped",
                    success=True,
                    message="Already installed",
                )
            )
            continue
        if dry_run:
            results.append(
                InstallResult(
                    name=tool.name,
                    status="would_install",
                    success=True,
                    message=_describe_install(tool, platform),
                )
            )
            continue
        result = install_tool(tool, platform)
        results.append(result)
    return results


def _describe_install(tool: ToolConfig, platform: Platform) -> str:
    spec = tool.install
    if platform.pkg_manager and platform.pkg_manager in spec.package_managers:
        pkg_name = spec.package_managers[platform.pkg_manager]
        cmd = platform.install_cmd(pkg_name)
        return " ".join(cmd)
    if spec.script:
        return spec.script.split("\n")[0] + ("..." if "\n" in spec.script else "")
    if spec.script_file:
        return f"run {spec.script_file}"
    if spec.alternatives:
        parts = []
        for entry in spec.alternatives:
            if entry.script:
                parts.append(entry.script)
            elif entry.script_file:
                parts.append(f"run {entry.script_file}")
        return " || ".join(parts)
    return f"No install method for {platform.os_name} ({platform.pkg_manager})"
