from __future__ import annotations

import importlib.util
import os
import platform
import shutil
from typing import Iterable

from abris.models.schemas import EnvironmentSnapshot


class EnvironmentDetector:
    def __init__(
        self,
        tools: Iterable[str] | None = None,
        python_modules: Iterable[str] | None = None,
        r_packages: Iterable[str] | None = None,
    ) -> None:
        self.tools = list(tools or [])
        self.python_modules = list(python_modules or [])
        self.r_packages = list(r_packages or [])

    def detect(self) -> EnvironmentSnapshot:
        return EnvironmentSnapshot(
            os_name=platform.platform(),
            python_version=platform.python_version(),
            cpu_count=os.cpu_count() or 1,
            available_tools=self._detect_tools(self.tools),
            available_python_modules=self._detect_python_modules(self.python_modules),
            available_r_packages=self._detect_r_packages(self.r_packages),
            notes=self._build_notes(),
        )

    def _detect_tools(self, tools: Iterable[str]) -> list[str]:
        return [tool for tool in tools if shutil.which(tool)]

    def _detect_python_modules(self, modules: Iterable[str]) -> list[str]:
        available = []
        for module in modules:
            if importlib.util.find_spec(module) is not None:
                available.append(module)
        return available

    def _detect_r_packages(self, packages: Iterable[str]) -> list[str]:
        if not shutil.which("Rscript"):
            return []
        return []

    def _build_notes(self) -> list[str]:
        notes = []
        if not shutil.which("Rscript"):
            notes.append("Rscript not found; R package execution is not available yet.")
        else:
            notes.append(
                "R package inspection is not implemented yet; package availability is not verified."
            )
        if not shutil.which("docker"):
            notes.append("Docker not found; container fallback is not available yet.")
        return notes
