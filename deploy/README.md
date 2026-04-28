# ABRIS deployment helpers

This directory holds repo-local deployment helpers.

## SSH key placement

Put temporary deployment SSH material under `deploy/ssh/`.

Ignored by Git:
- `deploy/ssh/id_*`
- `deploy/ssh/*.pub`
- `deploy/ssh/known_hosts`
- `deploy/ssh/config.local`

Recommended private key path:
- `deploy/ssh/id_abris_linux`

Recommended public key path:
- `deploy/ssh/id_abris_linux.pub`

## Linux smoke test script

Use `deploy/linux_smoke_test.sh` on the target Linux machine after copying the repo.

## Paper-search MCP local bootstrap

- Linux/macOS:
  - `bash deploy/setup_paper_search_mcp.sh`
- Windows / MINGW / local Python:
  - `python deploy/setup_paper_search_mcp.py`

Both helpers create a repo-local virtualenv under:
- `third_party/paper-search-mcp/.venv`

ABRIS will fail closed if `ABRIS_ENABLE_PAPER_SEARCH_MCP=1` and that repo-local interpreter is missing.

## Any-directory Git Bash usage

From the repo root, do a one-time editable install:

- `python -m pip install -e .`

After that, you can start the local UI from any Git Bash directory with:

- `abris-ui`

This launcher applies the usual local defaults automatically:
- `ABRIS_USE_OPENCODE=1`
- `ABRIS_ENABLE_PAPER_SEARCH_MCP=1`
- `ABRIS_AUTONOMY_MODE=acquire_bounded`
- `ABRIS_APPROVAL_REQUIRED=0`
- `ABRIS_ALLOWED_SOURCE_CLASSES=public_registry,workspace_local`
- `ABRIS_CONTROL_PLANE_HOST=127.0.0.1`
- `ABRIS_CONTROL_PLANE_PORT=18080`

Use `abris-control-plane` directly only if you want to manage all env vars yourself.
