# devstrap

Cross-platform CLI tool to install dev tools on a fresh machine. One command to get everything back.

## Quick Start

```sh
curl -fsSL https://raw.githubusercontent.com/lywchaos/dev-bootstrap/main/bootstrap.sh | sh
```

This will:
1. Install [uv](https://github.com/astral-sh/uv) if not present
2. Clone this repo to `~/.local/share/devstrap`
3. Run `devstrap install` to install all tools

## Included Tools

| Tool | Description | Dependencies |
|------|-------------|--------------|
| git | Version control system | -- |
| go | Go programming language | -- |
| lazygit | Terminal UI for git | go |
| zsh | Z shell | -- |
| oh-my-zsh | Framework for managing zsh configuration | -- |
| zsh-autosuggestions | Fish-like autosuggestions for zsh | oh-my-zsh |
| zsh-syntax-highlighting | Fish-like syntax highlighting for zsh | oh-my-zsh |
| powerlevel10k | A fast and flexible Zsh theme | oh-my-zsh |
| tmux | Terminal multiplexer | -- |
| neovim | Hyperextensible text editor | -- |
| nvim-config | Custom Neovim configuration | neovim |
| fzf | Fuzzy finder | -- |
| ripgrep | Fast regex search tool | -- |
| fd | Fast file finder | -- |
| navi | Interactive cheatsheet tool | -- |
| chezmoi | Dotfile manager | -- |
| uv | Python package manager | -- |
| zoxide | Smarter cd command | -- |
| rust | Systems programming language (installed via rustup) | -- |
| just | Command runner for project-specific tasks | rust |
| claude-code | Anthropic's CLI for Claude | -- |

Tools with dependencies are automatically installed in the correct order. When installing a single tool, its transitive dependencies are pulled in automatically.

## Usage

### Check version

```sh
devstrap --version
```

### List tools

Show all tools and their current install status:

```sh
devstrap list
```

Prints a table with columns: **Name**, **Description**, **Method** (e.g. brew, script), and **Status** (installed or not installed).

Use `--manifest` to list tools from a custom manifest instead of the bundled one:

```sh
devstrap list --manifest path/to/tools.yaml
```

### Install tools

Install all tools:

```sh
devstrap install
```

Install a specific tool (dependencies are resolved and installed automatically):

```sh
devstrap install neovim        # installs just neovim
devstrap install nvim-config   # installs neovim first (dependency), then nvim-config
```

Preview what would be installed without making changes:

```sh
devstrap install --dry-run
devstrap install lazygit --dry-run
```

Interactively select which tools to install (requires a TTY):

```sh
devstrap install --interactive
# or
devstrap install -i
```

Use a custom manifest file:

```sh
devstrap install --manifest path/to/tools.yaml
```

### How installation works

1. **Already installed?** Each tool has a `check` command (e.g. `git --version`). If it succeeds, the tool is skipped.
2. **Package manager first.** If your platform has a supported package manager and the tool declares a package for it, that's used.
3. **Script fallback.** If no package is available, the tool's `script`, `script_file`, or `alternatives` (tried in order) are used.
4. **Dependency ordering.** Tools are topologically sorted so dependencies install before dependents. If a dependency fails, all tools that depend on it are skipped.

The exit code is 1 if any tool fails to install.

## Supported Platforms

- **macOS** -- Homebrew (auto-installs if missing)
- **Linux** -- apt

Tools without a native package fall back to scripts.

## Custom Manifest

Add or remove tools by editing `src/devstrap/tools.yaml`, or pass your own with `--manifest`.

### Manifest format

```yaml
tools:
  - name: jq
    description: JSON processor
    check: jq --version
    deps: []                    # optional list of tool names this depends on
    install:
      brew: jq
      apt: jq
```

### Install specification

Each tool's `install` block supports several methods (mutually exclusive where noted):

**Package managers** -- map a manager name to a package name:

```yaml
install:
  brew: ripgrep
  apt: ripgrep
```

Recognized package managers: `brew`, `apt`.

**Inline script** -- a shell command to run as fallback:

```yaml
install:
  script: curl -fsSL https://example.com/install.sh | sh
```

Multiline scripts automatically get `set -e` prepended for safety (unless they start with a shebang or `set -`).

**Script file** -- reference an external script:

```yaml
install:
  script_file: scripts/install-tool.sh
```

**Alternatives** -- an ordered list of scripts tried in sequence (useful when a tool offers multiple install methods, e.g. curl vs wget):

```yaml
install:
  alternatives:
    - script: curl -fsSL https://example.com/install.sh | sh
    - script: wget -qO- https://example.com/install.sh | sh
```

`script`, `script_file`, and `alternatives` are mutually exclusive -- use only one per tool.

## Development

```sh
uv sync
uv run pytest
uv run pre-commit run --all-files
```

Pre-commit hooks: ruff (lint), black (format), isort (imports), mypy (types), xenon (complexity), gitleaks (secrets).
