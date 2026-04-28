#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
PAPER_SEARCH_DIR="${ABRIS_PAPER_SEARCH_MCP_DIR:-$ROOT_DIR/third_party/paper-search-mcp}"

if [ ! -d "$PAPER_SEARCH_DIR" ]; then
  echo "SKIP: paper-search checkout not present at $PAPER_SEARCH_DIR"
  exit 0
fi

PYTHON_BIN="${ABRIS_PAPER_SEARCH_PYTHON:-python3}"
VENV_DIR="$PAPER_SEARCH_DIR/.venv"
BOOTSTRAP_DIR="$ROOT_DIR/.abris-runtime/bootstrap"
VIRTUALENV_BOOTSTRAP="$BOOTSTRAP_DIR/virtualenv"

echo "Preparing paper-search MCP virtualenv at $VENV_DIR"
if ! "$PYTHON_BIN" -m venv "$VENV_DIR"; then
  echo "python -m venv unavailable; bootstrapping repo-local virtualenv package"
  mkdir -p "$VIRTUALENV_BOOTSTRAP"
  "$PYTHON_BIN" -m pip install --upgrade --target "$VIRTUALENV_BOOTSTRAP" virtualenv
  PYTHONPATH="$VIRTUALENV_BOOTSTRAP${PYTHONPATH:+:$PYTHONPATH}" \
    "$PYTHON_BIN" -m virtualenv "$VENV_DIR"
fi
"$VENV_DIR/bin/python" -m pip install --upgrade pip
"$VENV_DIR/bin/python" -m pip install -e "$PAPER_SEARCH_DIR"

echo "paper-search MCP virtualenv ready"
