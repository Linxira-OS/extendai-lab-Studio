from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path


def _venv_python_path(venv_dir: Path) -> Path:
    if os.name == "nt":
        return venv_dir / "Scripts" / "python.exe"
    return venv_dir / "bin" / "python"


def _run(command: list[str], env: dict[str, str] | None = None) -> None:
    subprocess.run(command, check=True, env=env)


def main() -> None:
    root_dir = Path(__file__).resolve().parents[1]
    paper_search_dir = Path(
        os.environ.get(
            "ABRIS_PAPER_SEARCH_MCP_DIR",
            str(root_dir / "third_party" / "paper-search-mcp"),
        )
    )
    if not paper_search_dir.exists():
        print(f"SKIP: paper-search checkout not present at {paper_search_dir}")
        return

    python_bin = os.environ.get("ABRIS_PAPER_SEARCH_PYTHON", sys.executable)
    venv_dir = paper_search_dir / ".venv"
    bootstrap_dir = root_dir / ".abris-runtime" / "bootstrap"
    virtualenv_bootstrap = bootstrap_dir / "virtualenv"

    print(f"Preparing paper-search MCP virtualenv at {venv_dir}")
    try:
        _run([python_bin, "-m", "venv", str(venv_dir)])
    except subprocess.CalledProcessError:
        print("python -m venv unavailable; bootstrapping repo-local virtualenv package")
        virtualenv_bootstrap.mkdir(parents=True, exist_ok=True)
        _run(
            [
                python_bin,
                "-m",
                "pip",
                "install",
                "--upgrade",
                "--target",
                str(virtualenv_bootstrap),
                "virtualenv",
            ]
        )
        env = os.environ.copy()
        existing = env.get("PYTHONPATH", "")
        env["PYTHONPATH"] = (
            str(virtualenv_bootstrap)
            if not existing
            else str(virtualenv_bootstrap) + os.pathsep + existing
        )
        _run([python_bin, "-m", "virtualenv", str(venv_dir)], env=env)

    venv_python = _venv_python_path(venv_dir)
    _run([str(venv_python), "-m", "pip", "install", "--upgrade", "pip"])
    _run([str(venv_python), "-m", "pip", "install", "-e", str(paper_search_dir)])
    print("paper-search MCP virtualenv ready")


if __name__ == "__main__":
    main()
