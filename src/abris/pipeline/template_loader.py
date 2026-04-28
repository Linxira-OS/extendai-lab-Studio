from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


@dataclass(slots=True)
class PipelineTemplate:
    pipeline_id: str
    name: str
    steps: list[str] = field(default_factory=list)
    outputs: list[str] = field(default_factory=list)


class PipelineTemplateLoader:
    def load(self, path: Path) -> PipelineTemplate:
        payload = self._read_yaml_like(path)
        return PipelineTemplate(
            pipeline_id=str(payload.get("id", "unknown-pipeline")),
            name=str(payload.get("name", "Unnamed Pipeline")),
            steps=[str(step["skill"]) for step in payload.get("steps", [])],
            outputs=[str(output) for output in payload.get("outputs", [])],
        )

    def _read_yaml_like(self, path: Path) -> dict[str, Any]:
        text = path.read_text(encoding="utf-8")
        try:
            import yaml  # type: ignore[import-not-found]

            loaded = yaml.safe_load(text)
            return loaded if isinstance(loaded, dict) else {}
        except ImportError:
            return self._fallback_parse(text)

    def _fallback_parse(self, text: str) -> dict[str, Any]:
        payload: dict[str, Any] = {}
        steps: list[dict[str, str]] = []
        outputs: list[str] = []
        section: str | None = None

        for raw_line in text.splitlines():
            line = raw_line.rstrip()
            stripped = line.strip()
            if not stripped or stripped.startswith("#"):
                continue

            if not line.startswith(" ") and stripped.endswith(":"):
                section = stripped[:-1]
                continue

            if not line.startswith(" ") and ":" in stripped:
                key, value = stripped.split(":", 1)
                payload[key.strip()] = value.strip()
                section = None
                continue

            if section == "steps" and stripped.startswith("- skill:"):
                _, value = stripped.split(":", 1)
                steps.append({"skill": value.strip()})
                continue

            if section == "outputs" and stripped.startswith("-"):
                outputs.append(stripped[1:].strip())

        payload["steps"] = steps
        payload["outputs"] = outputs
        return payload
