from __future__ import annotations

import argparse
from copy import deepcopy
import json
import importlib
import os
from dataclasses import fields, is_dataclass
from pathlib import Path

from abris.models.schemas import AutonomyPolicy
from abris.orchestrator.bio_orchestrator import BioAnalysisOrchestrator


def _parse_bool_env(name: str, default: bool) -> bool:
    value = os.environ.get(name)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


def _parse_csv_env(name: str) -> list[str]:
    value = os.environ.get(name, "")
    return [item.strip().lower() for item in value.split(",") if item.strip()]


def _build_autonomy_policy_from_env() -> AutonomyPolicy:
    raw_mode = os.environ.get("ABRIS_AUTONOMY_MODE", "plan_only")
    mode = (
        raw_mode
        if raw_mode
        in {"plan_only", "acquire_bounded", "generate_bounded", "optimize_proposed"}
        else "plan_only"
    )
    return AutonomyPolicy(
        mode=mode,
        approval_required=_parse_bool_env("ABRIS_APPROVAL_REQUIRED", True),
        allowed_source_classes=_parse_csv_env("ABRIS_ALLOWED_SOURCE_CLASSES"),
        codegen_scope=_parse_csv_env("ABRIS_CODEGEN_SCOPE"),
        optimization_scope=_parse_csv_env("ABRIS_OPTIMIZATION_SCOPE"),
    )


def _render_runtime_config(value: object, replacements: dict[str, str]) -> object:
    if isinstance(value, str):
        return value.format(**replacements)
    if isinstance(value, list):
        return [_render_runtime_config(item, replacements) for item in value]
    if isinstance(value, dict):
        return {
            str(key): _render_runtime_config(item, replacements)
            for key, item in value.items()
        }
    return value


def _build_opencode_runtime_config(project_root: Path) -> dict[str, object] | None:
    if not _parse_bool_env("ABRIS_ENABLE_PAPER_SEARCH_MCP", False):
        return None

    config_path = Path(
        os.environ.get(
            "ABRIS_OPENCODE_RUNTIME_CONFIG",
            str(project_root / "configs" / "opencode.paper_search.json"),
        )
    )
    raw_config = json.loads(config_path.read_text(encoding="utf-8"))
    if not isinstance(raw_config, dict):
        raise RuntimeError("OpenCode runtime config must be a JSON object.")

    paper_search_dir = Path(
        os.environ.get(
            "ABRIS_PAPER_SEARCH_MCP_DIR",
            str(project_root / "third_party" / "paper-search-mcp"),
        )
    )
    if not paper_search_dir.exists():
        raise RuntimeError(
            "Paper-search MCP is enabled but the repo-local source checkout is missing: "
            f"{paper_search_dir}"
        )

    paper_search_python = paper_search_dir / ".venv" / "bin" / "python"
    if os.name == "nt":
        paper_search_python = paper_search_dir / ".venv" / "Scripts" / "python.exe"
    if not paper_search_python.exists():
        setup_hint = (
            "python deploy/setup_paper_search_mcp.py"
            if os.name == "nt"
            else "bash deploy/setup_paper_search_mcp.sh"
        )
        raise RuntimeError(
            "Paper-search MCP is enabled but the repo-local virtualenv is missing: "
            f"{paper_search_python}. Run {setup_hint} after the checkout is present."
        )

    rendered = _render_runtime_config(
        deepcopy(raw_config),
        {
            "project_root": str(project_root),
            "paper_search_dir": str(paper_search_dir),
            "paper_search_python": str(paper_search_python),
            "paper_search_unpaywall_email": os.environ.get(
                "ABRIS_PAPER_SEARCH_UNPAYWALL_EMAIL", ""
            ),
            "paper_search_semantic_scholar_api_key": os.environ.get(
                "ABRIS_PAPER_SEARCH_SEMANTIC_SCHOLAR_API_KEY", ""
            ),
            "paper_search_core_api_key": os.environ.get(
                "ABRIS_PAPER_SEARCH_CORE_API_KEY", ""
            ),
        },
    )
    if not isinstance(rendered, dict):
        raise RuntimeError("Rendered OpenCode runtime config must stay a JSON object.")

    mcp_config = rendered.get("mcp")
    if isinstance(mcp_config, dict):
        for server_config in mcp_config.values():
            if not isinstance(server_config, dict):
                continue
            environment = server_config.get("environment")
            if isinstance(environment, dict):
                server_config["environment"] = {
                    str(key): str(item)
                    for key, item in environment.items()
                    if isinstance(item, str) and item.strip()
                }

    return rendered


def build_orchestrator_from_env() -> BioAnalysisOrchestrator:
    project_root = Path(__file__).resolve().parents[2]
    autonomy_policy = _build_autonomy_policy_from_env()
    use_opencode = os.environ.get("ABRIS_USE_OPENCODE", "0") == "1"
    if not use_opencode:
        return BioAnalysisOrchestrator(autonomy_policy=autonomy_policy)

    build_node_bridge_runtime = importlib.import_module(
        "abris.orchestrator.opencode_runtime"
    ).build_node_bridge_runtime
    base_url = os.environ.get("ABRIS_OPENCODE_BASE_URL")
    raw_start_server = os.environ.get("ABRIS_OPENCODE_START_SERVER")
    start_server = (
        _parse_bool_env("ABRIS_OPENCODE_START_SERVER", True)
        if raw_start_server is not None
        else base_url is None
    )
    runtime = build_node_bridge_runtime(
        project_root,
        base_url=base_url,
        runtime_config=_build_opencode_runtime_config(project_root),
        start_server=start_server,
        directory=project_root,
        workspace_id=os.environ.get("ABRIS_OPENCODE_WORKSPACE_ID"),
        node_binary=os.environ.get("ABRIS_NODE_BINARY", "node"),
    )
    return BioAnalysisOrchestrator(runtime=runtime, autonomy_policy=autonomy_policy)


def _build_argument_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Run ABRIS prototype analyses.")
    parser.add_argument(
        "--request",
        default="Analyze this local count matrix",
        help="Natural-language analysis request.",
    )
    parser.add_argument("--counts-file", help="Local TSV/CSV count matrix path.")
    parser.add_argument("--sample-sheet", help="Optional sample sheet path.")
    parser.add_argument(
        "--pipeline-profile",
        help="Pipeline profile to run, e.g. prototype_counts or standard_rna.",
    )
    parser.add_argument(
        "--input-file",
        action="append",
        dest="input_files",
        default=[],
        help="Additional input files to inspect through the file gateway.",
    )
    parser.add_argument(
        "--json-output",
        action="store_true",
        help="Emit structured JSON instead of a Python repr.",
    )
    return parser


def _build_parameters_from_args(args: argparse.Namespace) -> dict[str, object]:
    input_files = list(args.input_files)
    if args.counts_file:
        input_files.append(args.counts_file)
    if args.sample_sheet:
        input_files.append(args.sample_sheet)

    pipeline_profile = args.pipeline_profile
    if not pipeline_profile and args.counts_file:
        pipeline_profile = "prototype_counts"

    parameters: dict[str, object] = {"input_files": input_files}
    if args.counts_file:
        parameters["counts_file"] = args.counts_file
    if args.sample_sheet:
        parameters["sample_sheet"] = args.sample_sheet
    if pipeline_profile:
        parameters["pipeline_profile"] = pipeline_profile
    return parameters


def _to_jsonable(value: object) -> object:
    if is_dataclass(value) and not isinstance(value, type):
        return {
            field.name: _to_jsonable(getattr(value, field.name))
            for field in fields(value)
        }
    if isinstance(value, Path):
        return str(value)
    if isinstance(value, dict):
        return {str(key): _to_jsonable(item) for key, item in value.items()}
    if isinstance(value, list):
        return [_to_jsonable(item) for item in value]
    return value


def main(argv: list[str] | None = None) -> None:
    parser = _build_argument_parser()
    args = parser.parse_args(argv)
    orchestrator = build_orchestrator_from_env()
    report = orchestrator.analyze(args.request, _build_parameters_from_args(args))
    if args.json_output:
        print(json.dumps(_to_jsonable(report), ensure_ascii=False, indent=2))
        return
    print(report)


if __name__ == "__main__":
    main()
