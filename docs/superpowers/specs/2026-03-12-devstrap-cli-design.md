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

```
curl bootstrap.sh | sh
  → installs uv (if missing)
  → uv run devstrap install
    → reads tools.yaml
    → detects platform & package manager
    → installs each tool
```

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
│       └── models.py        # Dataclass models for tool config
├── tools.yaml               # Tool manifest
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
- **`check`** — shell command to verify installation (exit 0 = installed)
- **`install.<manager>`** — package name for that manager (runs `<manager> install <name>`)
- **`install.script`** — fallback shell command when no native package exists

Resolution order: detect package manager → use matching key → fall back to `script` → warn if nothing matches.

### CLI Commands

| Command | Description |
|---------|-------------|
| `devstrap install` | Install all tools (skips already-installed) |
| `devstrap install <name>` | Install a specific tool by name |
| `devstrap install -i / --interactive` | Checkbox selector to pick tools |
| `devstrap list` | Show all tools and their install status |
| `devstrap check` | Verify which tools are installed vs missing |

### Platform Detection (`platform.py`)

1. `platform.system()` → `Darwin` or `Linux`
2. macOS: check for `brew` via `shutil.which`; prompt to install Homebrew if missing
3. Linux: check for `apt`, `dnf`, `pacman` (first found wins)
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

When `--interactive` is passed, use `InquirerPy` (or `rich` prompts) to present a checkbox list of all tools. Pre-check tools that are not yet installed. User selects which to install, then the normal install flow runs on the selected subset.

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
