from __future__ import annotations

import subprocess
from dataclasses import dataclass

from devstrap.models import ToolConfig
from devstrap.platform import Platform


@dataclass
class InstallResult:
    name: str
    status: str  # "installed", "skipped", "failed", "would_install"
    success: bool
    message: str


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


def install_tool(tool: ToolConfig, platform: Platform) -> InstallResult:
    # Try package manager first
    if platform.pkg_manager and platform.pkg_manager in tool.install:
        pkg_name = tool.install[platform.pkg_manager]
        cmd = platform.install_cmd(pkg_name)
        try:
            subprocess.run(cmd, check=True, text=True)
            return InstallResult(
                name=tool.name, status="installed", success=True, message=""
            )
        except subprocess.CalledProcessError as e:
            return InstallResult(
                name=tool.name,
                status="failed",
                success=False,
                message=str(e),
            )

    # Fall back to script
    if "script" in tool.install:
        try:
            subprocess.run(
                tool.install["script"],
                shell=True,
                check=True,
                text=True,
            )
            return InstallResult(
                name=tool.name, status="installed", success=True, message=""
            )
        except subprocess.CalledProcessError as e:
            return InstallResult(
                name=tool.name,
                status="failed",
                success=False,
                message=str(e),
            )

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
    if platform.pkg_manager and platform.pkg_manager in tool.install:
        pkg_name = tool.install[platform.pkg_manager]
        cmd = platform.install_cmd(pkg_name)
        return " ".join(cmd)
    if "script" in tool.install:
        return tool.install["script"]
    return f"No install method for {platform.os_name} ({platform.pkg_manager})"
