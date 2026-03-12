#!/bin/sh
set -e

REPO_URL="git@github.com:lywchaos/dev-bootstrap.git"
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
