# devstrap CLI — Design Spec

## Overview

A cross-platform (macOS/Linux) CLI tool that installs a curated set of development tools in one command. Built with Python (managed by `uv`), bootstrapped via a POSIX shell script.

## Goals

- Install 10+ dev tools with a single command on a fresh machine
- Support macOS (Homebrew) and Linux (apt/dnf/pacman)
- Easy to extend: add a tool by editing a YAML file
- Skip already-installed tools
- Interactive mode for selective installs

## Non-Goals

- Windows support (for now)
- Configuration management (chezmoi handles that separately)
- Version pinning of installed tools

## Architecture

### Bootstrap Flow

Usage: `curl -fsSL https://raw.githubusercontent.com/<user>/dev-bootstrap/main/bootstrap.sh | sh`

`bootstrap.sh` does the following:

1. Check if `uv` is installed (`command -v uv`); if not, install via `curl -LsSf https://astral.sh/uv/install.sh | sh`, then source `$HOME/.local/bin/env` (or add `$HOME/.local/bin` to `PATH`) so `uv` is available in the current shell session
2. Clone the `dev-bootstrap` repo to `~/.local/share/devstrap/` (if no existing clone). If a clone already exists, attempt `git -C ~/.local/share/devstrap pull --ff-only`; if that fails (local changes or diverged history), warn the user and continue with the existing checkout as-is
3. `cd` into the repo and run `uv run devstrap install`

This means the project is always run from a local clone. `uv run` handles venv creation and dependency installation automatically via `pyproject.toml`.

### Project Structure

```
dev-bootstrap/
├── bootstrap.sh            # POSIX shell: installs uv, then runs devstrap
├── pyproject.toml           # uv project: typer, pyyaml, rich deps
├── src/
│   └── devstrap/
│       ├── __init__.py
│       ├── cli.py           # Typer app: install, list, check commands
│       ├── installer.py     # Install orchestration per tool
│       ├── platform.py      # OS & package manager detection
│       ├── models.py        # Dataclass models for tool config
│       └── tools.yaml       # Tool manifest (bundled via importlib.resources)
└── tests/
    ├── test_platform.py
    ├── test_installer.py
    └── test_models.py
```

### Tool Manifest (`tools.yaml`)

Each tool is defined declaratively:

```yaml
tools:
  - name: git
    description: Version control
    check: git --version
    install:
      brew: git
      apt: git
      dnf: git
      pacman: git

  - name: neovim
    description: Hyperextensible text editor
    check: nvim --version
    install:
      brew: neovim
      apt: neovim
      dnf: neovim
      pacman: neovim

  - name: navi
    description: Interactive cheatsheet tool
    check: navi --version
    install:
      brew: navi
      script: "curl -sL https://raw.githubusercontent.com/denisidoro/navi/master/scripts/install | bash"

  - name: uv
    description: Python package manager
    check: uv --version
    install:
      brew: uv
      script: "curl -LsSf https://astral.sh/uv/install.sh | sh"
```

Fields:

- **`name`** — tool identifier
- **`description`** — human-readable summary
- **`check`** — shell command to verify installation (exit code 0 = installed, non-zero = missing; 5-second timeout via `subprocess.run(timeout=5)` — a timeout is treated as "missing" with a warning noting the timeout, so the tool will be offered for install)
- **`install.<manager>`** — package name for that manager. The key (`brew`, `apt`, `dnf`, `pacman`) maps to the actual command shown in the Platform Detection table (e.g., `apt` key → `sudo apt-get install -y <pkg>`)
- **`install.script`** — fallback shell command when no native package exists. Used when the detected package manager has no entry for this tool.

Resolution order: detect package manager → use matching key → fall back to `script` → warn if nothing matches. Partial platform coverage in the manifest is expected — not every tool needs an entry for every package manager.

**Trust model:** The `tools.yaml` manifest lives in the user's own repo. `script` entries can run arbitrary shell commands, which is acceptable because the user controls the manifest content. No additional trust prompt is needed beyond what `bootstrap.sh` already implies (running code from the user's own repo).

**Note on `uv`:** `uv` appears in the manifest so `devstrap check` reports it, but `bootstrap.sh` already ensures it is installed before devstrap runs. The check command will always succeed; this is intentional for completeness.

### CLI Commands

| Command | Description |
|---------|-------------|
| `devstrap install` | Install all tools (skips already-installed) |
| `devstrap install <name>` | Install a specific tool by name |
| `devstrap install -i / --interactive` | Checkbox selector to pick tools (requires TTY; errors early if stdin is not a terminal) |
| `devstrap list` | Table of all tools with name, description, install method for current platform, and installed/missing status (runs each tool's `check` command with same timeout semantics as `install`) |
| `devstrap install --dry-run` | Show tool names and the exact commands that would run, without executing |
| `devstrap --version` | Show devstrap version |

Global option: `--manifest <path>` overrides the bundled `tools.yaml`.

`devstrap install <name>` exits with error and message if `<name>` is not found in the manifest. Name validation occurs before any other logic (including `--dry-run` evaluation).

All install operations run **sequentially** (no parallel installs) to avoid package manager lock conflicts.

### Platform Detection (`platform.py`)

1. `platform.system()` → `Darwin` or `Linux`
2. macOS: check for `brew` via `shutil.which`; if missing and stdin is a TTY, ask user whether to install Homebrew. If not a TTY (e.g., piped bootstrap), auto-install Homebrew. If user declines interactively, continue with `script`-only tools (tools without a `script` fallback will be skipped with a warning).
3. Linux: check for `apt-get`, `dnf`, `pacman` in that priority order (first found wins). This order is intentional: Debian/Ubuntu (apt) is most common, then Fedora (dnf), then Arch (pacman).
4. Returns a `Platform` dataclass with `os_name`, `pkg_manager_name`, and `install_cmd(package)` method

Package manager install commands:

| Manager | Command |
|---------|---------|
| brew | `brew install <pkg>` |
| apt | `sudo apt-get install -y <pkg>` |
| dnf | `sudo dnf install -y <pkg>` |
| pacman | `sudo pacman -S --noconfirm <pkg>` |

### Install Flow (`installer.py`)

```
for each tool in manifest:
    run check command
    if exit 0 → skip (already installed), log green checkmark
    else:
        find install method for current platform
        if pkg manager entry exists → run pkg install
        elif script entry exists → run script via subprocess
        else → warn "no install method", log red X
    capture stdout/stderr for failures
```

### Interactive Mode

When `--interactive` is passed, use `InquirerPy` to present a checkbox list of all tools. Pre-check tools that are not yet installed. User selects which to install, then the normal install flow runs on the selected subset.

### Sudo Handling

Linux install commands use `sudo`. The CLI lets each `subprocess.run` call prompt for the password naturally (sudo's own credential caching handles subsequent calls). No upfront sudo prompt.

### Manifest Location

`tools.yaml` is bundled in the Python package using `importlib.resources` (referenced from `src/devstrap/`). This means the manifest ships with the package and is always findable regardless of working directory. Users who want to customize can pass `--manifest <path>` to override.

### Error Handling

- Each tool install is independent — failure on one does not stop others
- Summary at the end: counts of installed, skipped, and failed tools
- Failed tools show the error output
- CLI exits with non-zero code if any tool failed

### Dependencies

- **typer** — CLI framework
- **rich** — colored output (comes with typer)
- **pyyaml** — YAML manifest parsing
- **inquirerpy** — interactive checkbox selection

### Testing Strategy

- Unit tests for platform detection: mock `shutil.which` and `platform.system()`
- Unit tests for manifest parsing: valid YAML, invalid YAML, missing fields
- Unit tests for install logic: mock `subprocess.run`, verify correct commands
- No integration tests that actually install packages

## Initial Tool List

1. git
2. zsh
3. navi
4. chezmoi
5. uv
6. neovim
7. tmux
8. fzf
9. ripgrep
10. fd
