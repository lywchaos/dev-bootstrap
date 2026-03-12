# devstrap CLI Implementation Plan

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a cross-platform CLI tool (`devstrap`) that installs a curated set of dev tools from a YAML manifest on macOS and Linux.

**Architecture:** POSIX shell bootstrap installs `uv`, clones the repo, then runs a Python CLI (`typer`) that reads a declarative `tools.yaml`, detects the OS/package manager, and installs each tool sequentially. Tools are checked before install and skipped if already present.

**Tech Stack:** Python 3.11+, uv, Typer, PyYAML, Rich, InquirerPy

**Spec:** `docs/superpowers/specs/2026-03-12-devstrap-cli-design.md`

---

## File Structure

| File | Responsibility |
|------|---------------|
| `pyproject.toml` | Project metadata, dependencies, script entry point |
| `src/devstrap/__init__.py` | Package init, `__version__` |
| `src/devstrap/models.py` | Dataclasses: `ToolConfig`, `Manifest` — parse & validate `tools.yaml` |
| `src/devstrap/platform.py` | `Platform` dataclass — OS detection, pkg manager detection, `install_cmd()` |
| `src/devstrap/installer.py` | `check_tool()`, `install_tool()`, `install_all()` — orchestration logic |
| `src/devstrap/cli.py` | Typer app: `install`, `list` commands, `--interactive`, `--dry-run`, `--manifest` |
| `src/devstrap/tools.yaml` | Bundled tool manifest (10 tools) |
| `bootstrap.sh` | POSIX shell: install uv, clone repo, run devstrap |
| `tests/test_models.py` | Tests for YAML parsing and validation |
| `tests/test_platform.py` | Tests for OS/pkg manager detection |
| `tests/test_installer.py` | Tests for check/install orchestration |
| `tests/test_cli.py` | Tests for CLI commands via Typer test runner |

---

## Chunk 1: Project Scaffolding & Models

### Task 1: Initialize uv project

**Files:**
- Create: `pyproject.toml`
- Create: `src/devstrap/__init__.py`

- [ ] **Step 1: Create the uv project with pyproject.toml**

Run:
```bash
cd /Users/liangyuanwei/workspace/dev-bootstrap
uv init --lib --package --name devstrap
```

This creates `pyproject.toml` and `src/devstrap/__init__.py`.

- [ ] **Step 2: Edit pyproject.toml to add dependencies and script entry point**

`pyproject.toml` should contain:

```toml
[project]
name = "devstrap"
version = "0.1.0"
description = "Cross-platform CLI tool to install dev tools"
requires-python = ">=3.11"
dependencies = [
    "typer>=0.9.0",
    "pyyaml>=6.0",
    "inquirerpy>=0.3.4",
]

[project.scripts]
devstrap = "devstrap.cli:app"

[build-system]
requires = ["hatchling"]
build-backend = "hatchling.backends"
```

- [ ] **Step 3: Set `__version__` in `__init__.py`**

```python
__version__ = "0.1.0"
```

- [ ] **Step 4: Add dev dependency for testing**

Run:
```bash
uv add --dev pytest
```

- [ ] **Step 5: Verify project setup**

Run:
```bash
uv run python -c "import devstrap; print(devstrap.__version__)"
```

Expected: `0.1.0`

- [ ] **Step 6: Commit**

```bash
git add pyproject.toml src/ uv.lock
git commit -m "feat: initialize uv project with dependencies"
```

---

### Task 2: Models — Tool config and manifest parsing

**Files:**
- Create: `src/devstrap/models.py`
- Create: `tests/test_models.py`

- [ ] **Step 1: Write failing tests for ToolConfig and Manifest parsing**

`tests/test_models.py`:

```python
import pytest
from devstrap.models import ToolConfig, load_manifest


class TestToolConfig:
    def test_from_dict_full(self):
        data = {
            "name": "git",
            "description": "Version control",
            "check": "git --version",
            "install": {"brew": "git", "apt": "git"},
        }
        tool = ToolConfig.from_dict(data)
        assert tool.name == "git"
        assert tool.description == "Version control"
        assert tool.check == "git --version"
        assert tool.install == {"brew": "git", "apt": "git"}

    def test_from_dict_with_script(self):
        data = {
            "name": "navi",
            "description": "Cheatsheet tool",
            "check": "navi --version",
            "install": {"brew": "navi", "script": "curl -sL https://example.com | bash"},
        }
        tool = ToolConfig.from_dict(data)
        assert tool.install["script"] == "curl -sL https://example.com | bash"

    def test_from_dict_missing_name_raises(self):
        with pytest.raises(ValueError, match="name"):
            ToolConfig.from_dict({"description": "x", "check": "x", "install": {}})

    def test_from_dict_missing_install_raises(self):
        with pytest.raises(ValueError, match="install"):
            ToolConfig.from_dict({"name": "x", "description": "x", "check": "x"})


class TestLoadManifest:
    def test_load_from_yaml_string(self, tmp_path):
        yaml_content = """
tools:
  - name: git
    description: Version control
    check: git --version
    install:
      brew: git
      apt: git
  - name: tmux
    description: Terminal multiplexer
    check: tmux -V
    install:
      brew: tmux
"""
        manifest_file = tmp_path / "tools.yaml"
        manifest_file.write_text(yaml_content)
        tools = load_manifest(manifest_file)
        assert len(tools) == 2
        assert tools[0].name == "git"
        assert tools[1].name == "tmux"

    def test_load_invalid_yaml(self, tmp_path):
        manifest_file = tmp_path / "tools.yaml"
        manifest_file.write_text("not: [valid: yaml: {")
        with pytest.raises(Exception):
            load_manifest(manifest_file)

    def test_load_missing_tools_key(self, tmp_path):
        manifest_file = tmp_path / "tools.yaml"
        manifest_file.write_text("something_else: true\n")
        with pytest.raises(ValueError, match="tools"):
            load_manifest(manifest_file)

    def test_load_bundled_manifest(self):
        """The bundled tools.yaml should load without errors."""
        tools = load_manifest()
        assert len(tools) >= 10
        names = [t.name for t in tools]
        assert "git" in names
        assert "neovim" in names
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/test_models.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'devstrap.models'`

- [ ] **Step 3: Implement models.py**

`src/devstrap/models.py`:

```python
from __future__ import annotations

import importlib.resources
from dataclasses import dataclass
from pathlib import Path

import yaml


@dataclass
class ToolConfig:
    name: str
    description: str
    check: str
    install: dict[str, str]

    @classmethod
    def from_dict(cls, data: dict) -> ToolConfig:
        if "name" not in data:
            raise ValueError("Tool entry missing required field: 'name'")
        if "install" not in data:
            raise ValueError(f"Tool '{data.get('name', '?')}' missing required field: 'install'")
        return cls(
            name=data["name"],
            description=data.get("description", ""),
            check=data.get("check", ""),
            install=data["install"],
        )


def load_manifest(path: Path | None = None) -> list[ToolConfig]:
    if path is None:
        ref = importlib.resources.files("devstrap").joinpath("tools.yaml")
        text = ref.read_text(encoding="utf-8")
    else:
        text = Path(path).read_text(encoding="utf-8")

    data = yaml.safe_load(text)
    if not isinstance(data, dict) or "tools" not in data:
        raise ValueError("Manifest must contain a 'tools' key")
    return [ToolConfig.from_dict(entry) for entry in data["tools"]]
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/test_models.py -v`
Expected: all pass (except `test_load_bundled_manifest` — needs `tools.yaml`, created in Task 3)

- [ ] **Step 5: Commit**

```bash
git add src/devstrap/models.py tests/test_models.py
git commit -m "feat: add ToolConfig model and manifest loader with tests"
```

---

### Task 3: Create the bundled tools.yaml

**Files:**
- Create: `src/devstrap/tools.yaml`

- [ ] **Step 1: Write the full tools.yaml manifest**

`src/devstrap/tools.yaml`:

```yaml
tools:
  - name: git
    description: Version control system
    check: git --version
    install:
      brew: git
      apt: git
      dnf: git
      pacman: git

  - name: zsh
    description: Z shell
    check: zsh --version
    install:
      brew: zsh
      apt: zsh
      dnf: zsh
      pacman: zsh

  - name: tmux
    description: Terminal multiplexer
    check: tmux -V
    install:
      brew: tmux
      apt: tmux
      dnf: tmux
      pacman: tmux

  - name: neovim
    description: Hyperextensible text editor
    check: nvim --version
    install:
      brew: neovim
      apt: neovim
      dnf: neovim
      pacman: neovim

  - name: fzf
    description: Fuzzy finder
    check: fzf --version
    install:
      brew: fzf
      apt: fzf
      dnf: fzf
      pacman: fzf

  - name: ripgrep
    description: Fast regex search tool
    check: rg --version
    install:
      brew: ripgrep
      apt: ripgrep
      dnf: ripgrep
      pacman: ripgrep

  - name: fd
    description: Fast file finder
    check: fd --version
    install:
      brew: fd
      apt: fd-find
      dnf: fd-find
      pacman: fd

  - name: navi
    description: Interactive cheatsheet tool
    check: navi --version
    install:
      brew: navi
      script: "curl -sL https://raw.githubusercontent.com/denisidoro/navi/master/scripts/install | bash"

  - name: chezmoi
    description: Dotfile manager
    check: chezmoi --version
    install:
      brew: chezmoi
      script: "sh -c \"$(curl -fsLS get.chezmoi.io)\""

  - name: uv
    description: Python package manager
    check: uv --version
    install:
      brew: uv
      script: "curl -LsSf https://astral.sh/uv/install.sh | sh"
```

- [ ] **Step 2: Verify bundled manifest loads**

Run: `uv run pytest tests/test_models.py::TestLoadManifest::test_load_bundled_manifest -v`
Expected: PASS

- [ ] **Step 3: Commit**

```bash
git add src/devstrap/tools.yaml
git commit -m "feat: add bundled tools.yaml with 10 tools"
```

---

## Chunk 2: Platform Detection

### Task 4: Platform detection module

**Files:**
- Create: `src/devstrap/platform.py`
- Create: `tests/test_platform.py`

- [ ] **Step 1: Write failing tests for platform detection**

`tests/test_platform.py`:

```python
from unittest.mock import patch
import pytest
from devstrap.platform import detect_platform, Platform


class TestDetectPlatform:
    @patch("devstrap.platform.shutil.which", side_effect=lambda cmd: "/opt/homebrew/bin/brew" if cmd == "brew" else None)
    @patch("devstrap.platform.platform_system", return_value="Darwin")
    def test_macos_with_brew(self, mock_sys, mock_which):
        p = detect_platform()
        assert p.os_name == "Darwin"
        assert p.pkg_manager == "brew"

    @patch("devstrap.platform.shutil.which", side_effect=lambda cmd: "/usr/bin/apt-get" if cmd == "apt-get" else None)
    @patch("devstrap.platform.platform_system", return_value="Linux")
    def test_linux_with_apt(self, mock_sys, mock_which):
        p = detect_platform()
        assert p.os_name == "Linux"
        assert p.pkg_manager == "apt"

    @patch("devstrap.platform.shutil.which", side_effect=lambda cmd: "/usr/bin/dnf" if cmd == "dnf" else None)
    @patch("devstrap.platform.platform_system", return_value="Linux")
    def test_linux_with_dnf(self, mock_sys, mock_which):
        p = detect_platform()
        assert p.os_name == "Linux"
        assert p.pkg_manager == "dnf"

    @patch("devstrap.platform.shutil.which", side_effect=lambda cmd: "/usr/bin/pacman" if cmd == "pacman" else None)
    @patch("devstrap.platform.platform_system", return_value="Linux")
    def test_linux_with_pacman(self, mock_sys, mock_which):
        p = detect_platform()
        assert p.os_name == "Linux"
        assert p.pkg_manager == "pacman"

    @patch("devstrap.platform.shutil.which", return_value=None)
    @patch("devstrap.platform.platform_system", return_value="Linux")
    def test_linux_no_pkg_manager(self, mock_sys, mock_which):
        p = detect_platform()
        assert p.os_name == "Linux"
        assert p.pkg_manager is None

    @patch("devstrap.platform._handle_missing_homebrew", return_value="brew")
    @patch("devstrap.platform.shutil.which", return_value=None)
    @patch("devstrap.platform.platform_system", return_value="Darwin")
    def test_macos_no_brew_installs_homebrew(self, mock_sys, mock_which, mock_handle):
        p = detect_platform()
        assert p.pkg_manager == "brew"
        mock_handle.assert_called_once()

    @patch("devstrap.platform._handle_missing_homebrew", return_value=None)
    @patch("devstrap.platform.shutil.which", return_value=None)
    @patch("devstrap.platform.platform_system", return_value="Darwin")
    def test_macos_no_brew_declined(self, mock_sys, mock_which, mock_handle):
        p = detect_platform()
        assert p.pkg_manager is None


class TestPlatformInstallCmd:
    def test_brew_install_cmd(self):
        p = Platform(os_name="Darwin", pkg_manager="brew")
        assert p.install_cmd("git") == ["brew", "install", "git"]

    def test_apt_install_cmd(self):
        p = Platform(os_name="Linux", pkg_manager="apt")
        assert p.install_cmd("git") == ["sudo", "apt-get", "install", "-y", "git"]

    def test_dnf_install_cmd(self):
        p = Platform(os_name="Linux", pkg_manager="dnf")
        assert p.install_cmd("git") == ["sudo", "dnf", "install", "-y", "git"]

    def test_pacman_install_cmd(self):
        p = Platform(os_name="Linux", pkg_manager="pacman")
        assert p.install_cmd("git") == ["sudo", "pacman", "-S", "--noconfirm", "git"]

    def test_no_pkg_manager_raises(self):
        p = Platform(os_name="Linux", pkg_manager=None)
        with pytest.raises(RuntimeError, match="No package manager"):
            p.install_cmd("git")
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/test_platform.py -v`
Expected: FAIL — `ModuleNotFoundError`

- [ ] **Step 3: Implement platform.py**

`src/devstrap/platform.py`:

```python
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

    if os_name == "Darwin":
        if shutil.which("brew"):
            pkg_manager = "brew"
        else:
            pkg_manager = _handle_missing_homebrew()
    elif os_name == "Linux":
        pkg_manager = None
        for binary in _LINUX_MANAGERS:
            if shutil.which(binary):
                pkg_manager = _LINUX_MANAGER_KEY[binary]
                break
    else:
        pkg_manager = None

    return Platform(os_name=os_name, pkg_manager=pkg_manager)


def _handle_missing_homebrew() -> str | None:
    """Prompt to install Homebrew on macOS. Auto-install if not a TTY."""
    import subprocess
    import sys

    if not sys.stdin.isatty():
        # Non-interactive: auto-install
        console_print("Homebrew not found. Installing automatically...")
        try:
            subprocess.run(
                '/bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"',
                shell=True,
                check=True,
            )
            return "brew"
        except subprocess.CalledProcessError:
            console_print("Warning: Failed to install Homebrew. Falling back to script-only installs.")
            return None

    # Interactive: ask user
    from rich.prompt import Confirm

    if Confirm.ask("Homebrew not found. Install it?", default=True):
        try:
            subprocess.run(
                '/bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"',
                shell=True,
                check=True,
            )
            return "brew"
        except subprocess.CalledProcessError:
            console_print("Warning: Failed to install Homebrew. Falling back to script-only installs.")
            return None
    else:
        console_print("Skipping Homebrew. Only tools with 'script' fallback will be installed.")
        return None


def console_print(msg: str) -> None:
    from rich.console import Console
    Console(stderr=True).print(msg)
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/test_platform.py -v`
Expected: all PASS

- [ ] **Step 5: Commit**

```bash
git add src/devstrap/platform.py tests/test_platform.py
git commit -m "feat: add platform detection with OS and package manager support"
```

---

## Chunk 3: Installer Logic

### Task 5: Installer — check and install orchestration

**Files:**
- Create: `src/devstrap/installer.py`
- Create: `tests/test_installer.py`

- [ ] **Step 1: Write failing tests for check_tool**

`tests/test_installer.py`:

```python
from unittest.mock import patch, MagicMock
import subprocess
import pytest
from devstrap.models import ToolConfig
from devstrap.platform import Platform
from devstrap.installer import check_tool, install_tool, install_all, InstallResult


@pytest.fixture
def git_tool():
    return ToolConfig(
        name="git",
        description="Version control",
        check="git --version",
        install={"brew": "git", "apt": "git"},
    )


@pytest.fixture
def navi_tool():
    return ToolConfig(
        name="navi",
        description="Cheatsheet tool",
        check="navi --version",
        install={"brew": "navi", "script": "curl -sL https://example.com | bash"},
    )


@pytest.fixture
def mac_platform():
    return Platform(os_name="Darwin", pkg_manager="brew")


class TestCheckTool:
    @patch("devstrap.installer.subprocess.run")
    def test_tool_installed(self, mock_run, git_tool):
        mock_run.return_value = MagicMock(returncode=0)
        assert check_tool(git_tool) is True

    @patch("devstrap.installer.subprocess.run")
    def test_tool_not_installed(self, mock_run, git_tool):
        mock_run.side_effect = FileNotFoundError()
        assert check_tool(git_tool) is False

    @patch("devstrap.installer.subprocess.run")
    def test_tool_check_timeout(self, mock_run, git_tool):
        mock_run.side_effect = subprocess.TimeoutExpired(cmd="git --version", timeout=5)
        assert check_tool(git_tool) is False

    @patch("devstrap.installer.subprocess.run")
    def test_tool_nonzero_exit(self, mock_run, git_tool):
        mock_run.return_value = MagicMock(returncode=1)
        assert check_tool(git_tool) is False

    def test_tool_no_check_command(self):
        tool = ToolConfig(name="x", description="", check="", install={"brew": "x"})
        assert check_tool(tool) is False


class TestInstallTool:
    @patch("devstrap.installer.subprocess.run")
    def test_install_via_pkg_manager(self, mock_run, git_tool, mac_platform):
        mock_run.return_value = MagicMock(returncode=0)
        result = install_tool(git_tool, mac_platform)
        assert result.success is True
        mock_run.assert_called_once_with(
            ["brew", "install", "git"],
            check=True,
            capture_output=True,
            text=True,
        )

    @patch("devstrap.installer.subprocess.run")
    def test_install_via_script_fallback(self, mock_run, navi_tool):
        platform = Platform(os_name="Linux", pkg_manager="apt")
        mock_run.return_value = MagicMock(returncode=0)
        result = install_tool(navi_tool, platform)
        assert result.success is True
        mock_run.assert_called_once_with(
            "curl -sL https://example.com | bash",
            shell=True,
            check=True,
            capture_output=True,
            text=True,
        )

    def test_install_no_method(self, mac_platform):
        tool = ToolConfig(name="x", description="", check="", install={"dnf": "x"})
        result = install_tool(tool, mac_platform)
        assert result.success is False
        assert "no install method" in result.message.lower()

    @patch("devstrap.installer.subprocess.run")
    def test_install_failure(self, mock_run, git_tool, mac_platform):
        mock_run.side_effect = subprocess.CalledProcessError(
            1, "brew install git", stderr="Error: something went wrong"
        )
        result = install_tool(git_tool, mac_platform)
        assert result.success is False


class TestInstallAll:
    @patch("devstrap.installer.install_tool")
    @patch("devstrap.installer.check_tool")
    def test_skips_installed_tools(self, mock_check, mock_install, git_tool, mac_platform):
        mock_check.return_value = True
        results = install_all([git_tool], mac_platform)
        assert len(results) == 1
        assert results[0].status == "skipped"
        mock_install.assert_not_called()

    @patch("devstrap.installer.install_tool")
    @patch("devstrap.installer.check_tool")
    def test_installs_missing_tools(self, mock_check, mock_install, git_tool, mac_platform):
        mock_check.return_value = False
        mock_install.return_value = InstallResult(name="git", status="installed", success=True, message="")
        results = install_all([git_tool], mac_platform)
        assert len(results) == 1
        assert results[0].status == "installed"

    @patch("devstrap.installer.install_tool")
    @patch("devstrap.installer.check_tool")
    def test_continues_after_failure(self, mock_check, mock_install, mac_platform):
        tools = [
            ToolConfig(name="a", description="", check="a", install={"brew": "a"}),
            ToolConfig(name="b", description="", check="b", install={"brew": "b"}),
        ]
        mock_check.return_value = False
        mock_install.side_effect = [
            InstallResult(name="a", status="failed", success=False, message="error"),
            InstallResult(name="b", status="installed", success=True, message=""),
        ]
        results = install_all(tools, mac_platform)
        assert len(results) == 2
        assert results[0].status == "failed"
        assert results[1].status == "installed"
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/test_installer.py -v`
Expected: FAIL — `ModuleNotFoundError`

- [ ] **Step 3: Implement installer.py**

`src/devstrap/installer.py`:

```python
from __future__ import annotations

import subprocess
from dataclasses import dataclass

from devstrap.models import ToolConfig
from devstrap.platform import Platform


@dataclass
class InstallResult:
    name: str
    status: str  # "installed", "skipped", "failed"
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
        Console(stderr=True).print(f"[yellow]Warning:[/yellow] Check for '{tool.name}' timed out")
        return False


def install_tool(tool: ToolConfig, platform: Platform) -> InstallResult:
    # Try package manager first
    if platform.pkg_manager and platform.pkg_manager in tool.install:
        pkg_name = tool.install[platform.pkg_manager]
        cmd = platform.install_cmd(pkg_name)
        try:
            subprocess.run(cmd, check=True, capture_output=True, text=True)
            return InstallResult(name=tool.name, status="installed", success=True, message="")
        except subprocess.CalledProcessError as e:
            return InstallResult(
                name=tool.name, status="failed", success=False,
                message=e.stderr or str(e),
            )

    # Fall back to script
    if "script" in tool.install:
        try:
            subprocess.run(
                tool.install["script"],
                shell=True,
                check=True,
                capture_output=True,
                text=True,
            )
            return InstallResult(name=tool.name, status="installed", success=True, message="")
        except subprocess.CalledProcessError as e:
            return InstallResult(
                name=tool.name, status="failed", success=False,
                message=e.stderr or str(e),
            )

    return InstallResult(
        name=tool.name, status="failed", success=False,
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
            results.append(InstallResult(name=tool.name, status="skipped", success=True, message="Already installed"))
            continue
        if dry_run:
            results.append(InstallResult(name=tool.name, status="would_install", success=True, message=_describe_install(tool, platform)))
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
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/test_installer.py -v`
Expected: all PASS

- [ ] **Step 5: Commit**

```bash
git add src/devstrap/installer.py tests/test_installer.py
git commit -m "feat: add installer with check, install, and dry-run support"
```

---

## Chunk 4: CLI Layer

### Task 6: CLI — Typer app with install, list, and version commands

**Files:**
- Create: `src/devstrap/cli.py`
- Create: `tests/test_cli.py`

- [ ] **Step 1: Write failing tests for CLI commands**

`tests/test_cli.py`:

```python
import pytest
from unittest.mock import patch, MagicMock
from typer.testing import CliRunner
from devstrap.cli import app
from devstrap.models import ToolConfig
from devstrap.platform import Platform
from devstrap.installer import InstallResult

runner = CliRunner()


@pytest.fixture
def mock_tools():
    return [
        ToolConfig(name="git", description="Version control", check="git --version", install={"brew": "git"}),
        ToolConfig(name="navi", description="Cheatsheet", check="navi --version", install={"brew": "navi"}),
    ]


@pytest.fixture
def mock_platform():
    return Platform(os_name="Darwin", pkg_manager="brew")


class TestVersion:
    def test_version_flag(self):
        result = runner.invoke(app, ["--version"])
        assert result.exit_code == 0
        assert "0.1.0" in result.output


class TestList:
    @patch("devstrap.cli.check_tool")
    @patch("devstrap.cli.detect_platform")
    @patch("devstrap.cli.load_manifest")
    def test_list_shows_tools(self, mock_load, mock_detect, mock_check, mock_tools, mock_platform):
        mock_load.return_value = mock_tools
        mock_detect.return_value = mock_platform
        mock_check.side_effect = [True, False]
        result = runner.invoke(app, ["list"])
        assert result.exit_code == 0
        assert "git" in result.output
        assert "navi" in result.output

    @patch("devstrap.cli.check_tool")
    @patch("devstrap.cli.detect_platform")
    @patch("devstrap.cli.load_manifest")
    def test_list_shows_install_method(self, mock_load, mock_detect, mock_check, mock_tools, mock_platform):
        mock_load.return_value = mock_tools
        mock_detect.return_value = mock_platform
        mock_check.side_effect = [True, False]
        result = runner.invoke(app, ["list"])
        assert "brew" in result.output


class TestInstall:
    @patch("devstrap.cli.install_all")
    @patch("devstrap.cli.detect_platform")
    @patch("devstrap.cli.load_manifest")
    def test_install_all(self, mock_load, mock_detect, mock_install, mock_tools, mock_platform):
        mock_load.return_value = mock_tools
        mock_detect.return_value = mock_platform
        mock_install.return_value = [
            InstallResult(name="git", status="skipped", success=True, message="Already installed"),
            InstallResult(name="navi", status="installed", success=True, message=""),
        ]
        result = runner.invoke(app, ["install"])
        assert result.exit_code == 0

    @patch("devstrap.cli.install_all")
    @patch("devstrap.cli.detect_platform")
    @patch("devstrap.cli.load_manifest")
    def test_install_single_tool(self, mock_load, mock_detect, mock_install, mock_tools, mock_platform):
        mock_load.return_value = mock_tools
        mock_detect.return_value = mock_platform
        mock_install.return_value = [
            InstallResult(name="git", status="installed", success=True, message=""),
        ]
        result = runner.invoke(app, ["install", "git"])
        assert result.exit_code == 0

    @patch("devstrap.cli.detect_platform")
    @patch("devstrap.cli.load_manifest")
    def test_install_unknown_tool(self, mock_load, mock_detect, mock_tools, mock_platform):
        mock_load.return_value = mock_tools
        mock_detect.return_value = mock_platform
        result = runner.invoke(app, ["install", "nonexistent"])
        assert result.exit_code != 0
        assert "not found" in result.output.lower()

    @patch("devstrap.cli.install_all")
    @patch("devstrap.cli.detect_platform")
    @patch("devstrap.cli.load_manifest")
    def test_install_dry_run(self, mock_load, mock_detect, mock_install, mock_tools, mock_platform):
        mock_load.return_value = mock_tools
        mock_detect.return_value = mock_platform
        mock_install.return_value = [
            InstallResult(name="git", status="skipped", success=True, message="Already installed"),
            InstallResult(name="navi", status="would_install", success=True, message="brew install navi"),
        ]
        result = runner.invoke(app, ["install", "--dry-run"])
        assert result.exit_code == 0

    @patch("devstrap.cli.install_all")
    @patch("devstrap.cli.detect_platform")
    @patch("devstrap.cli.load_manifest")
    def test_install_exits_nonzero_on_failure(self, mock_load, mock_detect, mock_install, mock_tools, mock_platform):
        mock_load.return_value = mock_tools
        mock_detect.return_value = mock_platform
        mock_install.return_value = [
            InstallResult(name="git", status="failed", success=False, message="error"),
        ]
        result = runner.invoke(app, ["install"])
        assert result.exit_code != 0

    @patch("devstrap.cli.detect_platform")
    @patch("devstrap.cli.load_manifest")
    def test_install_unknown_tool_with_dry_run(self, mock_load, mock_detect, mock_tools, mock_platform):
        """Name validation fires before dry-run."""
        mock_load.return_value = mock_tools
        mock_detect.return_value = mock_platform
        result = runner.invoke(app, ["install", "nonexistent", "--dry-run"])
        assert result.exit_code != 0
        assert "not found" in result.output.lower()

    @patch("devstrap.cli.detect_platform")
    @patch("devstrap.cli.load_manifest")
    def test_interactive_requires_tty(self, mock_load, mock_detect, mock_tools, mock_platform):
        """--interactive should error when stdin is not a TTY."""
        mock_load.return_value = mock_tools
        mock_detect.return_value = mock_platform
        # CliRunner does not provide a real TTY
        result = runner.invoke(app, ["install", "--interactive"])
        assert result.exit_code != 0
        assert "tty" in result.output.lower()
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/test_cli.py -v`
Expected: FAIL — `ModuleNotFoundError`

- [ ] **Step 3: Implement cli.py**

`src/devstrap/cli.py`:

```python
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

    # Single tool install
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


def _get_method(tool: ToolConfig, platform) -> str:
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
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/test_cli.py -v`
Expected: all PASS

- [ ] **Step 5: Verify CLI works end-to-end**

Run: `uv run devstrap --version`
Expected: `devstrap 0.1.0`

Run: `uv run devstrap list`
Expected: table showing all 10 tools with status

- [ ] **Step 6: Commit**

```bash
git add src/devstrap/cli.py tests/test_cli.py
git commit -m "feat: add CLI with install, list, and version commands"
```

---

## Chunk 5: Bootstrap Script & Final Polish

### Task 7: Bootstrap shell script

**Files:**
- Create: `bootstrap.sh`

- [ ] **Step 1: Write bootstrap.sh**

`bootstrap.sh`:

```bash
#!/bin/sh
set -e

REPO_URL="https://github.com/<user>/dev-bootstrap.git"  # TODO: replace <user> with actual GitHub username
INSTALL_DIR="$HOME/.local/share/devstrap"

echo "==> devstrap bootstrap"

# Step 1: Ensure uv is installed
if ! command -v uv >/dev/null 2>&1; then
    echo "==> Installing uv..."
    curl -LsSf https://astral.sh/uv/install.sh | sh
    # Make uv available in current session
    if [ -f "$HOME/.local/bin/env" ]; then
        . "$HOME/.local/bin/env"
    else
        export PATH="$HOME/.local/bin:$PATH"
    fi
fi

# Step 2: Clone or update repo
if [ -d "$INSTALL_DIR/.git" ]; then
    echo "==> Updating devstrap..."
    if ! git -C "$INSTALL_DIR" pull --ff-only 2>/dev/null; then
        echo "    Warning: Could not update (local changes or diverged). Using existing checkout."
    fi
else
    echo "==> Cloning devstrap..."
    git clone "$REPO_URL" "$INSTALL_DIR"
fi

# Step 3: Run devstrap
echo "==> Running devstrap install..."
cd "$INSTALL_DIR"
uv run devstrap install
```

- [ ] **Step 2: Make it executable**

Run: `chmod +x bootstrap.sh`

- [ ] **Step 3: Verify script syntax**

Run: `sh -n bootstrap.sh`
Expected: no output (no syntax errors)

- [ ] **Step 4: Commit**

```bash
git add bootstrap.sh
git commit -m "feat: add POSIX bootstrap script"
```

---

### Task 8: Run full test suite and final verification

- [ ] **Step 1: Run all tests**

Run: `uv run pytest tests/ -v`
Expected: all PASS

- [ ] **Step 2: Verify CLI commands**

Run:
```bash
uv run devstrap --version
uv run devstrap list
uv run devstrap install --dry-run
```

Expected: version prints, list shows table, dry-run shows planned actions

- [ ] **Step 3: Final commit if any adjustments needed**

```bash
git add -A
git commit -m "chore: final adjustments after full test run"
```
