from __future__ import annotations

import importlib
import os
import sys
from pathlib import Path
from types import SimpleNamespace
from unittest import TestCase
from unittest.mock import patch

SRC_ROOT = Path(__file__).resolve().parents[1] / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

launcher_module = importlib.import_module("abris.launcher")


class LauncherTest(TestCase):
    def test_apply_git_bash_defaults_sets_expected_values(self) -> None:
        with patch.dict(os.environ, {}, clear=True):
            launcher_module.apply_git_bash_defaults()

            self.assertEqual(os.environ["ABRIS_USE_OPENCODE"], "1")
            self.assertEqual(os.environ["ABRIS_ENABLE_PAPER_SEARCH_MCP"], "1")
            self.assertEqual(os.environ["ABRIS_AUTONOMY_MODE"], "acquire_bounded")
            self.assertEqual(os.environ["ABRIS_APPROVAL_REQUIRED"], "0")
            self.assertEqual(
                os.environ["ABRIS_ALLOWED_SOURCE_CLASSES"],
                "public_registry,workspace_local",
            )
            self.assertEqual(os.environ["ABRIS_CONTROL_PLANE_HOST"], "127.0.0.1")
            self.assertEqual(os.environ["ABRIS_CONTROL_PLANE_PORT"], "18080")

    def test_apply_git_bash_defaults_preserves_existing_overrides(self) -> None:
        with patch.dict(
            os.environ,
            {
                "ABRIS_ENABLE_PAPER_SEARCH_MCP": "0",
                "ABRIS_CONTROL_PLANE_PORT": "19090",
            },
            clear=True,
        ):
            launcher_module.apply_git_bash_defaults()

            self.assertEqual(os.environ["ABRIS_ENABLE_PAPER_SEARCH_MCP"], "0")
            self.assertEqual(os.environ["ABRIS_CONTROL_PLANE_PORT"], "19090")
            self.assertEqual(os.environ["ABRIS_USE_OPENCODE"], "1")

    def test_main_applies_defaults_then_calls_control_plane_main(self) -> None:
        recorded: dict[str, object] = {}

        def fake_main(argv: list[str] | None = None) -> None:
            recorded["argv"] = argv
            recorded["env"] = {
                "ABRIS_USE_OPENCODE": os.environ.get("ABRIS_USE_OPENCODE"),
                "ABRIS_CONTROL_PLANE_PORT": os.environ.get("ABRIS_CONTROL_PLANE_PORT"),
            }

        with (
            patch.dict(os.environ, {}, clear=True),
            patch.dict(
                sys.modules,
                {"abris.control_plane.api": SimpleNamespace(main=fake_main)},
            ),
        ):
            launcher_module.main(["--port", "18081"])

        self.assertEqual(recorded["argv"], ["--port", "18081"])
        self.assertEqual(
            recorded["env"],
            {
                "ABRIS_USE_OPENCODE": "1",
                "ABRIS_CONTROL_PLANE_PORT": "18080",
            },
        )
