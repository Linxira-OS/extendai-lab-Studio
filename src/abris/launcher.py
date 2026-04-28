from __future__ import annotations

import os


DEFAULT_CONTROL_PLANE_ENV = {
    "ABRIS_USE_OPENCODE": "1",
    "ABRIS_ENABLE_PAPER_SEARCH_MCP": "1",
    "ABRIS_AUTONOMY_MODE": "acquire_bounded",
    "ABRIS_APPROVAL_REQUIRED": "0",
    "ABRIS_ALLOWED_SOURCE_CLASSES": "public_registry,workspace_local",
    "ABRIS_CONTROL_PLANE_HOST": "127.0.0.1",
    "ABRIS_CONTROL_PLANE_PORT": "18080",
}


def apply_git_bash_defaults() -> None:
    for key, value in DEFAULT_CONTROL_PLANE_ENV.items():
        os.environ.setdefault(key, value)


def main(argv: list[str] | None = None) -> None:
    apply_git_bash_defaults()

    from abris.control_plane.api import main as control_plane_main

    control_plane_main(argv)
