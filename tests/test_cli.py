import importlib
import os
import sys
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

SRC_DIR = Path(__file__).resolve().parents[1] / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

cli_module = importlib.import_module("abris.cli")
BioAnalysisOrchestrator = importlib.import_module(
    "abris.orchestrator.bio_orchestrator"
).BioAnalysisOrchestrator
AutonomyPolicy = importlib.import_module("abris.models.schemas").AutonomyPolicy


class CliTest(unittest.TestCase):
    @staticmethod
    def _runtime_only_import(fake_builder):
        real_import = cli_module.importlib.import_module

        def loader(name, package=None):
            if name == "abris.orchestrator.opencode_runtime":
                return SimpleNamespace(build_node_bridge_runtime=fake_builder)
            return real_import(name, package)

        return loader

    def test_build_orchestrator_from_env_defaults_to_local_mode(self) -> None:
        with patch.dict(os.environ, {}, clear=True):
            orchestrator = cli_module.build_orchestrator_from_env()

        self.assertIsInstance(orchestrator, BioAnalysisOrchestrator)
        self.assertIsNone(orchestrator.runtime)
        self.assertEqual(orchestrator.autonomy_policy.mode, "plan_only")
        self.assertTrue(orchestrator.autonomy_policy.approval_required)

    def test_build_orchestrator_from_env_parses_bounded_policy(self) -> None:
        with patch.dict(
            os.environ,
            {
                "ABRIS_AUTONOMY_MODE": "generate_bounded",
                "ABRIS_APPROVAL_REQUIRED": "0",
                "ABRIS_ALLOWED_SOURCE_CLASSES": "Public_Registry, workspace_local ",
                "ABRIS_CODEGEN_SCOPE": "src/abris,tests",
                "ABRIS_OPTIMIZATION_SCOPE": "skill:fastqc-v2",
            },
            clear=True,
        ):
            orchestrator = cli_module.build_orchestrator_from_env()

        self.assertIsInstance(orchestrator.autonomy_policy, AutonomyPolicy)
        self.assertEqual(orchestrator.autonomy_policy.mode, "generate_bounded")
        self.assertFalse(orchestrator.autonomy_policy.approval_required)
        self.assertEqual(
            orchestrator.autonomy_policy.allowed_source_classes,
            ["public_registry", "workspace_local"],
        )
        self.assertEqual(
            orchestrator.autonomy_policy.codegen_scope, ["src/abris", "tests"]
        )
        self.assertEqual(
            orchestrator.autonomy_policy.optimization_scope,
            ["skill:fastqc-v2"],
        )

    def test_remote_base_url_disables_local_server_start_by_default(self) -> None:
        captured: dict[str, object] = {}

        def fake_builder(*args, **kwargs):
            captured.update(kwargs)
            return object()

        with (
            patch.dict(
                os.environ,
                {
                    "ABRIS_USE_OPENCODE": "1",
                    "ABRIS_OPENCODE_BASE_URL": "https://example.invalid",
                    "ABRIS_AUTONOMY_MODE": "acquire_bounded",
                    "ABRIS_APPROVAL_REQUIRED": "0",
                },
                clear=True,
            ),
            patch.object(
                cli_module.importlib,
                "import_module",
                side_effect=self._runtime_only_import(fake_builder),
            ),
        ):
            orchestrator = cli_module.build_orchestrator_from_env()

        self.assertIsInstance(orchestrator, BioAnalysisOrchestrator)
        self.assertFalse(captured["start_server"])
        self.assertEqual(captured["base_url"], "https://example.invalid")

    def test_build_parameters_from_args_defaults_to_prototype_counts(self) -> None:
        parser = cli_module._build_argument_parser()
        args = parser.parse_args(["--counts-file", "examples/prototype/counts.tsv"])

        parameters = cli_module._build_parameters_from_args(args)

        self.assertEqual(parameters["pipeline_profile"], "prototype_counts")
        self.assertEqual(parameters["counts_file"], "examples/prototype/counts.tsv")
        self.assertIn("examples/prototype/counts.tsv", parameters["input_files"])

    def test_explicit_start_server_override_is_honored_with_remote_base_url(
        self,
    ) -> None:
        captured: dict[str, object] = {}

        def fake_builder(*args, **kwargs):
            captured.update(kwargs)
            return object()

        with (
            patch.dict(
                os.environ,
                {
                    "ABRIS_USE_OPENCODE": "1",
                    "ABRIS_OPENCODE_BASE_URL": "https://example.invalid",
                    "ABRIS_OPENCODE_START_SERVER": "1",
                    "ABRIS_AUTONOMY_MODE": "acquire_bounded",
                    "ABRIS_APPROVAL_REQUIRED": "0",
                },
                clear=True,
            ),
            patch.object(
                cli_module.importlib,
                "import_module",
                side_effect=self._runtime_only_import(fake_builder),
            ),
        ):
            cli_module.build_orchestrator_from_env()

        self.assertTrue(captured["start_server"])

    def test_build_runtime_config_uses_repo_local_paper_search_defaults(self) -> None:
        source_config = (
            Path(__file__).resolve().parents[1]
            / "configs"
            / "opencode.paper_search.json"
        ).read_text(encoding="utf-8")
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            paper_search_dir = root / "third_party" / "paper-search-mcp"
            paper_search_dir.mkdir(parents=True, exist_ok=True)
            venv_python = (
                paper_search_dir / ".venv" / "Scripts" / "python.exe"
                if os.name == "nt"
                else paper_search_dir / ".venv" / "bin" / "python"
            )
            venv_python.parent.mkdir(parents=True, exist_ok=True)
            venv_python.write_text("#!/usr/bin/env python3\n", encoding="utf-8")
            configs_dir = root / "configs"
            configs_dir.mkdir(parents=True, exist_ok=True)
            (configs_dir / "opencode.paper_search.json").write_text(
                source_config,
                encoding="utf-8",
            )

            with patch.dict(
                os.environ,
                {
                    "ABRIS_ENABLE_PAPER_SEARCH_MCP": "1",
                    "ABRIS_PAPER_SEARCH_UNPAYWALL_EMAIL": "research@example.org",
                    "ABRIS_PAPER_SEARCH_MCP_DIR": str(paper_search_dir),
                },
                clear=True,
            ):
                config = cli_module._build_opencode_runtime_config(root)

        self.assertIsInstance(config, dict)
        mcp_config = config["mcp"]["paper-search"]
        self.assertEqual(mcp_config["type"], "local")
        self.assertEqual(mcp_config["command"][0], str(venv_python))
        self.assertEqual(mcp_config["command"][1:], ["-m", "paper_search_mcp.server"])
        self.assertEqual(
            mcp_config["environment"]["PAPER_SEARCH_MCP_UNPAYWALL_EMAIL"],
            "research@example.org",
        )
        self.assertEqual(
            mcp_config["environment"]["PAPER_SEARCH_MCP_ENABLE_SCIHUB"],
            "0",
        )

    def test_build_runtime_config_requires_repo_local_checkout_when_enabled(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            configs_dir = root / "configs"
            configs_dir.mkdir(parents=True, exist_ok=True)
            (configs_dir / "opencode.paper_search.json").write_text(
                '{"mcp": {"paper-search": {"type": "local", "command": ["{paper_search_python}", "-m", "paper_search_mcp.server"]}}}',
                encoding="utf-8",
            )
            with patch.dict(
                os.environ,
                {"ABRIS_ENABLE_PAPER_SEARCH_MCP": "1"},
                clear=True,
            ):
                with self.assertRaises(RuntimeError):
                    cli_module._build_opencode_runtime_config(root)

    def test_build_runtime_config_requires_repo_local_virtualenv_when_enabled(
        self,
    ) -> None:
        source_config = (
            Path(__file__).resolve().parents[1]
            / "configs"
            / "opencode.paper_search.json"
        ).read_text(encoding="utf-8")
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            paper_search_dir = root / "third_party" / "paper-search-mcp"
            paper_search_dir.mkdir(parents=True, exist_ok=True)
            configs_dir = root / "configs"
            configs_dir.mkdir(parents=True, exist_ok=True)
            (configs_dir / "opencode.paper_search.json").write_text(
                source_config,
                encoding="utf-8",
            )

            with patch.dict(
                os.environ,
                {
                    "ABRIS_ENABLE_PAPER_SEARCH_MCP": "1",
                    "ABRIS_PAPER_SEARCH_MCP_DIR": str(paper_search_dir),
                },
                clear=True,
            ):
                with self.assertRaises(RuntimeError):
                    cli_module._build_opencode_runtime_config(root)


if __name__ == "__main__":
    unittest.main()
