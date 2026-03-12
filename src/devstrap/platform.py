from __future__ import annotations

import platform as _platform
import shutil
from dataclasses import dataclass

# Wrapped for easy mocking in tests
platform_system = _platform.system

_PKG_MANAGER_CMDS: dict[str, list[str]] = {
    "brew": ["brew", "install"],
    "apt": ["sudo", "apt-get", "install", "-y"],
    "dnf": ["sudo", "dnf", "install", "-y"],
    "pacman": ["sudo", "pacman", "-S", "--noconfirm"],
}

_LINUX_MANAGERS = ["apt-get", "dnf", "pacman"]
_LINUX_MANAGER_KEY = {"apt-get": "apt", "dnf": "dnf", "pacman": "pacman"}


@dataclass
class Platform:
    os_name: str
    pkg_manager: str | None

    def install_cmd(self, package: str) -> list[str]:
        if self.pkg_manager is None:
            raise RuntimeError("No package manager detected")
        return [*_PKG_MANAGER_CMDS[self.pkg_manager], package]


def detect_platform() -> Platform:
    os_name = platform_system()
    pkg_manager: str | None = None

    if os_name == "Darwin":
        if shutil.which("brew"):
            pkg_manager = "brew"
        else:
            pkg_manager = _handle_missing_homebrew()
    elif os_name == "Linux":
        for binary in _LINUX_MANAGERS:
            if shutil.which(binary):
                pkg_manager = _LINUX_MANAGER_KEY[binary]
                break

    return Platform(os_name=os_name, pkg_manager=pkg_manager)


def _handle_missing_homebrew() -> str | None:
    """Prompt to install Homebrew on macOS. Auto-install if not a TTY."""
    import subprocess
    import sys

    homebrew_cmd = '/bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"'

    if not sys.stdin.isatty():
        # Non-interactive: auto-install
        _console_print("Homebrew not found. Installing automatically...")
        try:
            subprocess.run(homebrew_cmd, shell=True, check=True)
            return "brew"
        except subprocess.CalledProcessError:
            _console_print(
                "Warning: Failed to install Homebrew. Falling back to script-only installs."
            )
            return None

    # Interactive: ask user
    from rich.prompt import Confirm

    if Confirm.ask("Homebrew not found. Install it?", default=True):
        try:
            subprocess.run(homebrew_cmd, shell=True, check=True)
            return "brew"
        except subprocess.CalledProcessError:
            _console_print(
                "Warning: Failed to install Homebrew. Falling back to script-only installs."
            )
            return None
    else:
        _console_print(
            "Skipping Homebrew. Only tools with 'script' fallback will be installed."
        )
        return None


def _console_print(msg: str) -> None:
    from rich.console import Console

    Console(stderr=True).print(msg)
