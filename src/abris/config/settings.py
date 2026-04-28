from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


@dataclass(slots=True)
class Settings:
    project_root: Path
    config_dir: Path
    pipeline_dir: Path
    runtime_dir: Path
    run_dir: Path
    max_direct_read_bytes: int = 1_000_000
    max_preview_lines: int = 100
    metadata_only_mode: bool = True
    stall_timeout_seconds: int = 30

    @classmethod
    def from_root(cls, project_root: Path) -> "Settings":
        return cls(
            project_root=project_root,
            config_dir=project_root / "configs",
            pipeline_dir=project_root / "configs" / "pipelines",
            runtime_dir=project_root / ".abris-runtime",
            run_dir=project_root / ".abris-runtime" / "runs",
        )
