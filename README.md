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

| Tool | Description |
|------|-------------|
| git | Version control system |
| zsh | Z shell |
| tmux | Terminal multiplexer |
| neovim | Hyperextensible text editor |
| fzf | Fuzzy finder |
| ripgrep | Fast regex search tool |
| fd | Fast file finder |
| navi | Interactive cheatsheet tool |
| chezmoi | Dotfile manager |
| uv | Python package manager |

## Usage

```sh
# Install all tools
devstrap install

# Install a specific tool
devstrap install git

# Preview what would be installed
devstrap install --dry-run

# Interactively select tools to install
devstrap install --interactive

# List tools and their install status
devstrap list

# Use a custom manifest
devstrap install --manifest path/to/tools.yaml
```

## Supported Platforms

- **macOS** -- Homebrew (auto-installs if missing)
- **Linux** -- apt, dnf, pacman (auto-detected)

Tools without a native package (navi, chezmoi, uv) fall back to their official install scripts.

## Custom Manifest

Add or remove tools by editing `src/devstrap/tools.yaml`, or pass your own with `--manifest`:

```yaml
tools:
  - name: jq
    description: JSON processor
    check: jq --version
    install:
      brew: jq
      apt: jq
```

Each tool needs:
- `name` -- tool identifier
- `check` -- command to verify installation
- `install` -- map of package manager to package name, and/or a `script` fallback

## Development

```sh
uv sync
uv run pytest
uv run pre-commit run --all-files
```
