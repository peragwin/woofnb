#!/usr/bin/env bash
set -euo pipefail

# Simple installer for the `woof` CLI using uv's tool installer.
#
# Usage:
#   ./scripts/install_woof.sh            # install from the local checkout
#   ./scripts/install_woof.sh --from-git https://github.com/peragwin/woofnb.git
#   ./scripts/install_woof.sh --from-git git+ssh://git@github.com/peragwin/woofnb.git
#
# Requirements:
#   - A recent Python (3.11+) available on PATH
#   - uv installed (https://docs.astral.sh/uv/). If not found, this script
#     will print guidance to install it and exit.

SRC="."
if [[ "${1:-}" == "--from-git" ]]; then
  if [[ $# -lt 2 ]]; then
    echo "error: --from-git requires a URL argument" >&2
    exit 2
  fi
  SRC="$2"
fi

if ! command -v uv >/dev/null 2>&1; then
  cat >&2 <<'EOF'
uv is not installed.
Install uv first and re-run this script, for example:

  curl -LsSf https://astral.sh/uv/install.sh | sh

Then ensure ~/.local/bin is on your PATH (or follow the installer output),
and re-run: ./scripts/install_woof.sh
EOF
  exit 1
fi

# Ensure we are in the repo root when installing from local checkout
if [[ "$SRC" == "." ]]; then
  if [[ ! -f "pyproject.toml" ]]; then
    echo "error: run this script from the repository root (pyproject.toml not found)" >&2
    exit 2
  fi
fi

echo "Installing woof CLI from: $SRC"
uv tool install --force --upgrade "$SRC"

# Try to locate where uv installed the script and provide PATH hints
BIN_DIR="${HOME}/.local/bin"
if command -v woof >/dev/null 2>&1; then
  echo "\nwoof installed successfully: $(command -v woof)"
else
  echo "\nwoof installed, but not found on PATH. You may need to add ${BIN_DIR} to PATH."
  echo "For example, add this to your shell profile (e.g., ~/.bashrc or ~/.zshrc):"
  echo "\n  export PATH=\"${BIN_DIR}:\$PATH\"\n"
fi

echo "Run: woof --help"

