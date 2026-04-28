from __future__ import annotations

from collections.abc import Callable
from typing import Any

from abris.models.schemas import ExecutionResult, PipelineStep


StepExecutor = Callable[[PipelineStep, dict[str, Any]], ExecutionResult]


class PipelineEngine:
    def __init__(self, executor: StepExecutor) -> None:
        self.executor = executor

    def run(
        self, plan: list[PipelineStep], initial_context: dict[str, Any] | None = None
    ) -> list[ExecutionResult]:
        context = dict(initial_context or {})
        results: list[ExecutionResult] = []

        for index, step in enumerate(plan, start=1):
            context["_current_step_index"] = index
            context["_current_step_id"] = f"step_{index:03d}_{step.skill_id}"
            result = self.executor(step, context)
            results.append(result)
            context[step.skill_id] = result.outputs
            if result.status != "success":
                break

        return results
