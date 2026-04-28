from __future__ import annotations

import importlib
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from abris.config.settings import Settings
from abris.environment.detector import EnvironmentDetector
from abris.environment.file_guard import FileGuard
from abris.models.schemas import (
    AcquisitionRequest,
    AnalysisIntent,
    AnalysisReport,
    AutonomyPolicy,
    EnvironmentSnapshot,
    ExecutionResult,
    FileAccessDecision,
    FileReadRequest,
    InputAsset,
    PipelineStep,
)
from abris.orchestrator.opencode_contract import (
    OpenCodeRuntime,
    StructuredSchemaRequest,
)
from abris.runlog.store import RunLedger
from abris.data.sequencing_gateway import SequencingGateway
from abris.pipeline.engine import PipelineEngine
from abris.registry.skills_registry import SkillsRegistry, build_default_registry


class BioAnalysisOrchestrator:
    def __init__(
        self,
        detector: EnvironmentDetector | None = None,
        registry: SkillsRegistry | None = None,
        runtime: OpenCodeRuntime | None = None,
        settings: Settings | None = None,
        autonomy_policy: AutonomyPolicy | None = None,
    ) -> None:
        self.detector = detector or EnvironmentDetector(
            tools=["fastqc", "STAR", "samtools", "bcftools", "docker", "Rscript"],
            python_modules=["scanpy", "pysam", "Bio"],
            r_packages=["DESeq2", "edgeR", "Seurat"],
        )
        self.registry = registry or build_default_registry()
        self.runtime = runtime
        self.settings = settings or Settings.from_root(
            Path(__file__).resolve().parents[3]
        )
        self.autonomy_policy = autonomy_policy or AutonomyPolicy()
        self.gateway = SequencingGateway()
        self.file_guard = FileGuard(self.settings)
        self.run_ledger = RunLedger(self.settings)
        self.template_loader = importlib.import_module(
            "abris.pipeline.template_loader"
        ).PipelineTemplateLoader()
        self.engine = PipelineEngine(self._execute_step)

    def analyze(
        self, request: str, parameters: dict[str, Any] | None = None
    ) -> AnalysisReport:
        parameters = parameters or {}
        run = self.run_ledger.create_run(
            run_type="analysis",
            title=request[:120],
            initial_state="running",
            owner="orchestrator",
            metadata={"request": request, "parameters": parameters},
        )
        assets, access_decisions = self._prepare_inputs(parameters)
        intent = self.understand_intent(request, parameters, run_id=run.run_id)
        environment = self.detector.detect()
        plan = self.plan_pipeline(intent)
        results = self._enforce_autonomy_policy(intent)
        if results:
            self._record_terminal_results(run.run_id, results)
        if not results:
            results = self._validate_environment_for_plan(plan, environment)
            if results:
                self._record_terminal_results(run.run_id, results)
        if not results:
            results = self.engine.run(
                plan,
                initial_context={
                    "run_id": run.run_id,
                    "run_ledger": self.run_ledger,
                    "request": request,
                    "parameters": parameters,
                    "input_assets": [asset.asset_id for asset in assets],
                },
            )
            self._record_terminal_results(run.run_id, results)
        return AnalysisReport(
            run_id=run.run_id,
            intent=intent,
            environment=environment,
            plan=plan,
            results=results,
            autonomy_policy=self.autonomy_policy,
            assets=assets,
            file_access_decisions=access_decisions,
        )

    def _prepare_inputs(
        self, parameters: dict[str, Any]
    ) -> tuple[list[InputAsset], list[FileAccessDecision]]:
        input_files = parameters.get("input_files", [])
        if not input_files:
            return [], []

        assets = self.gateway.inspect_paths(input_files)
        decisions = [
            self.file_guard.evaluate(
                FileReadRequest(
                    path=asset.path,
                    operation="prompt_embed",
                    caller="orchestrator",
                    embed_in_prompt=True,
                ),
                asset,
            )
            for asset in assets
        ]
        return assets, decisions

    def understand_intent(
        self, request: str, parameters: dict[str, Any], run_id: str | None = None
    ) -> AnalysisIntent:
        if self.runtime is not None:
            return self._understand_intent_with_opencode(
                request, parameters, run_id=run_id
            )

        request_flags = self._classify_request_capabilities(request, parameters)
        acquisition_requests = self._normalize_acquisition_requests(
            parameters.get("acquisition_requests", [])
        )
        request_lower = request.lower()
        if parameters.get("counts_file") or any(
            token in request_lower
            for token in (
                "count matrix",
                "counts matrix",
                "counts table",
                "expression matrix",
            )
        ):
            return AnalysisIntent(
                analysis_type="CountMatrix",
                goal="summarize_count_matrix",
                parameters=parameters,
                expected_outputs=[
                    "validation_summary",
                    "sample_count",
                    "feature_count",
                    "top_features",
                    "high_variance_features",
                    "comparison_summary",
                ],
                requires_acquisition=request_flags["requires_acquisition"],
                acquisition_requests=acquisition_requests,
                requests_codegen=request_flags["requests_codegen"],
                requests_optimization=request_flags["requests_optimization"],
            )
        if "rna" in request_lower:
            return AnalysisIntent(
                analysis_type="RNA-seq",
                goal="differential_expression",
                parameters=parameters,
                expected_outputs=[
                    "differential_expression_results",
                    "volcano_plot",
                    "heatmap",
                    "enrichment_report",
                ],
                requires_acquisition=request_flags["requires_acquisition"],
                acquisition_requests=acquisition_requests,
                requests_codegen=request_flags["requests_codegen"],
                requests_optimization=request_flags["requests_optimization"],
            )
        return AnalysisIntent(
            analysis_type="generic",
            goal="exploratory_analysis",
            parameters=parameters,
            expected_outputs=["analysis_report"],
            requires_acquisition=request_flags["requires_acquisition"],
            acquisition_requests=acquisition_requests,
            requests_codegen=request_flags["requests_codegen"],
            requests_optimization=request_flags["requests_optimization"],
        )

    def _understand_intent_with_opencode(
        self, request: str, parameters: dict[str, Any], run_id: str | None = None
    ) -> AnalysisIntent:
        runtime = self.runtime
        if runtime is None:
            return AnalysisIntent(
                analysis_type="generic",
                goal="exploratory_analysis",
                parameters=parameters,
                expected_outputs=["analysis_report"],
            )

        session_id = runtime.create_session("ABRIS Intent Parsing")
        if run_id:
            self.run_ledger.attach_runtime_session(
                run_id,
                step_id="step_intent_parse",
                session_id=session_id,
            )
            self.run_ledger.heartbeat(
                run_id,
                step_id="step_intent_parse",
                reason="intent parsing runtime session attached",
            )
        request_flags = self._classify_request_capabilities(request, parameters)
        acquisition_requests = self._normalize_acquisition_requests(
            parameters.get("acquisition_requests", [])
        )
        governance = self.autonomy_policy.to_runtime_envelope()
        response = runtime.prompt_structured(
            session_id,
            StructuredSchemaRequest(
                prompt=(
                    "Governance envelope: "
                    f"{json.dumps(governance, sort_keys=True)}\n"
                    "Parse the bioinformatics request into structured intent. "
                    "Request: "
                    f"{request}. Parameters: {parameters}."
                ),
                schema={
                    "type": "object",
                    "properties": {
                        "analysis_type": {"type": "string"},
                        "goal": {"type": "string"},
                        "expected_outputs": {
                            "type": "array",
                            "items": {"type": "string"},
                        },
                        "requires_acquisition": {"type": "boolean"},
                        "acquisition_requests": {
                            "type": "array",
                            "items": {
                                "type": "object",
                                "properties": {
                                    "source_class": {"type": "string"},
                                    "locator": {"type": "string"},
                                },
                                "required": ["source_class", "locator"],
                            },
                        },
                        "requests_codegen": {"type": "boolean"},
                        "requests_optimization": {"type": "boolean"},
                    },
                    "required": ["analysis_type", "goal", "expected_outputs"],
                },
            ),
        )
        payload = response.get("structured_output", {})
        if not payload:
            return AnalysisIntent(
                analysis_type="generic",
                goal="exploratory_analysis",
                parameters=parameters,
                expected_outputs=["analysis_report"],
                requires_acquisition=request_flags["requires_acquisition"],
                acquisition_requests=acquisition_requests,
                requests_codegen=request_flags["requests_codegen"],
                requests_optimization=request_flags["requests_optimization"],
            )
        runtime_acquisition_requests = self._normalize_acquisition_requests(
            payload.get("acquisition_requests", acquisition_requests)
        )
        return AnalysisIntent(
            analysis_type=payload.get("analysis_type", "generic"),
            goal=payload.get("goal", "exploratory_analysis"),
            parameters=parameters,
            expected_outputs=payload.get("expected_outputs", ["analysis_report"]),
            requires_acquisition=bool(
                payload.get(
                    "requires_acquisition", request_flags["requires_acquisition"]
                )
            ),
            acquisition_requests=runtime_acquisition_requests,
            requests_codegen=bool(
                payload.get("requests_codegen", request_flags["requests_codegen"])
            ),
            requests_optimization=bool(
                payload.get(
                    "requests_optimization", request_flags["requests_optimization"]
                )
            ),
        )

    def _classify_request_capabilities(
        self, request: str, parameters: dict[str, Any]
    ) -> dict[str, bool]:
        request_lower = request.lower()
        parameter_keys = {str(key).lower() for key in parameters}
        parameter_values = (
            json.dumps(parameters, sort_keys=True).lower() if parameters else ""
        )

        requires_acquisition = (
            any(
                token in request_lower or token in parameter_values
                for token in (
                    "download",
                    "fetch",
                    "acquire",
                    "website",
                    "url",
                    "sra",
                    "geo",
                    "ena",
                )
            )
            or "acquisition_requests" in parameter_keys
        )

        requests_codegen = (
            any(
                token in request_lower or token in parameter_values
                for token in (
                    "write code",
                    "generate code",
                    "implement",
                    "patch",
                    "edit file",
                    "refactor",
                    "codegen",
                )
            )
            or "codegen_scope" in parameter_keys
        )

        requests_optimization = (
            any(
                token in request_lower or token in parameter_values
                for token in (
                    "optimize",
                    "optimization",
                    "benchmark",
                    "improve performance",
                    "tune",
                )
            )
            or "optimization_scope" in parameter_keys
        )

        return {
            "requires_acquisition": requires_acquisition,
            "requests_codegen": requests_codegen,
            "requests_optimization": requests_optimization,
        }

    def _normalize_acquisition_requests(
        self, raw_requests: Any
    ) -> list[AcquisitionRequest]:
        if not isinstance(raw_requests, list):
            return []

        normalized_requests: list[AcquisitionRequest] = []
        for entry in raw_requests:
            if not isinstance(entry, dict):
                continue
            source_class = str(entry.get("source_class", "")).strip().lower()
            locator = str(entry.get("locator", "")).strip()
            normalized_requests.append(
                AcquisitionRequest(source_class=source_class, locator=locator)
            )
        return normalized_requests

    def _enforce_autonomy_policy(self, intent: AnalysisIntent) -> list[ExecutionResult]:
        policy = self.autonomy_policy
        if not policy.allows_execution():
            return [
                self._build_policy_block(
                    "Execution blocked by autonomy policy: plan_only mode only allows planning.",
                    intent,
                )
            ]

        if intent.requires_acquisition:
            if not policy.allows_acquisition():
                return [
                    self._build_policy_block(
                        "Execution blocked by autonomy policy: acquisition requested without acquire_bounded permission.",
                        intent,
                    )
                ]
            if policy.approval_required:
                return [
                    self._build_policy_block(
                        "Execution blocked by autonomy policy: acquisition requires approval.",
                        intent,
                    )
                ]
            if not policy.allowed_source_classes:
                return [
                    self._build_policy_block(
                        "Execution blocked by autonomy policy: no allowed source classes configured for acquisition.",
                        intent,
                    )
                ]
            if not intent.acquisition_requests:
                return [
                    self._build_policy_block(
                        "Execution blocked by autonomy policy: acquisition requires structured acquisition_requests.",
                        intent,
                    )
                ]
            for request in intent.acquisition_requests:
                if not request.source_class or not request.locator:
                    return [
                        self._build_policy_block(
                            "Execution blocked by autonomy policy: acquisition request is missing source_class or locator.",
                            intent,
                        )
                    ]
                if request.source_class not in policy.allowed_source_classes:
                    return [
                        self._build_policy_block(
                            "Execution blocked by autonomy policy: acquisition request uses a disallowed source class.",
                            intent,
                        )
                    ]

        if intent.requests_codegen:
            if not policy.allows_codegen():
                return [
                    self._build_policy_block(
                        "Execution blocked by autonomy policy: code generation requested outside permitted mode.",
                        intent,
                    )
                ]
            if policy.approval_required:
                return [
                    self._build_policy_block(
                        "Execution blocked by autonomy policy: code generation requires approval.",
                        intent,
                    )
                ]
            if not policy.codegen_scope:
                return [
                    self._build_policy_block(
                        "Execution blocked by autonomy policy: code generation scope is empty.",
                        intent,
                    )
                ]

        if intent.requests_optimization:
            if not policy.allows_optimization():
                return [
                    self._build_policy_block(
                        "Execution blocked by autonomy policy: optimization requested outside optimize_proposed mode.",
                        intent,
                    )
                ]
            if policy.approval_required:
                return [
                    self._build_policy_block(
                        "Execution blocked by autonomy policy: optimization requires approval.",
                        intent,
                    )
                ]
            if not policy.optimization_scope:
                return [
                    self._build_policy_block(
                        "Execution blocked by autonomy policy: optimization scope is empty.",
                        intent,
                    )
                ]

        return []

    def _build_policy_block(
        self, message: str, intent: AnalysisIntent
    ) -> ExecutionResult:
        return ExecutionResult(
            step="policy_gate",
            status="blocked",
            outputs={
                "autonomy_mode": self.autonomy_policy.mode,
                "approval_required": self.autonomy_policy.approval_required,
                "allowed_source_classes": self.autonomy_policy.allowed_source_classes,
                "acquisition_requests": [
                    {
                        "source_class": request.source_class,
                        "locator": request.locator,
                    }
                    for request in intent.acquisition_requests
                ],
                "codegen_scope": self.autonomy_policy.codegen_scope,
                "optimization_scope": self.autonomy_policy.optimization_scope,
                "requires_acquisition": intent.requires_acquisition,
                "requests_codegen": intent.requests_codegen,
                "requests_optimization": intent.requests_optimization,
            },
            message=message,
        )

    def plan_pipeline(self, intent: AnalysisIntent) -> list[PipelineStep]:
        pipeline_profile = (
            str(intent.parameters.get("pipeline_profile", "")).strip().lower()
        )
        if (
            pipeline_profile == "prototype_counts"
            or intent.analysis_type == "CountMatrix"
        ):
            template = self.template_loader.load(
                self.settings.pipeline_dir / "count_matrix_prototype.yaml"
            )
            self._validate_pipeline_skills(template.steps)
            return [PipelineStep(skill_id=skill_id) for skill_id in template.steps]
        if intent.analysis_type == "RNA-seq":
            template = self.template_loader.load(
                self.settings.pipeline_dir / "rna_seq_standard.yaml"
            )
            self._validate_pipeline_skills(template.steps)
            return [PipelineStep(skill_id=skill_id) for skill_id in template.steps]
        return [PipelineStep(skill_id="fastqc")]

    def _validate_pipeline_skills(self, skill_ids: list[str]) -> None:
        missing_skills = [
            skill_id for skill_id in skill_ids if not self.registry.has(skill_id)
        ]
        if missing_skills:
            raise ValueError(
                "Pipeline references unknown skills: " + ", ".join(missing_skills)
            )

    def _validate_environment_for_plan(
        self, plan: list[PipelineStep], environment: EnvironmentSnapshot
    ) -> list[ExecutionResult]:
        available_requirements = set(environment.available_tools)
        available_requirements.update(environment.available_python_modules)
        available_requirements.update(environment.available_r_packages)

        blocking_results: list[ExecutionResult] = []
        for step in plan:
            skill = self.registry.get(step.skill_id)
            missing_requirements = [
                requirement
                for requirement in skill.requirements
                if requirement not in available_requirements
            ]
            if not missing_requirements:
                continue

            blocking_results.append(
                ExecutionResult(
                    step=step.skill_id,
                    status="blocked",
                    outputs={
                        "skill_name": skill.name,
                        "missing_requirements": missing_requirements,
                        "environment_notes": environment.notes,
                    },
                    message=(
                        f"Blocked {skill.name}: missing requirements "
                        f"{', '.join(missing_requirements)}."
                    ),
                )
            )

        return blocking_results

    def _execute_step(
        self, step: PipelineStep, context: dict[str, Any]
    ) -> ExecutionResult:
        run_id = str(context.get("run_id") or "")
        run_ledger = context.get("run_ledger")
        step_id = str(context.get("_current_step_id") or step.skill_id)
        if isinstance(run_ledger, RunLedger) and run_id:
            run_ledger.start_step(
                run_id,
                step_id=step_id,
                step_type="pipeline_step",
                title=step.skill_id,
                metadata={"skill_id": step.skill_id},
                owner="orchestrator",
            )
        if step.skill_id == "count_matrix_summary":
            result = self._execute_count_matrix_summary(context)
        else:
            skill = self.registry.get(step.skill_id)
            result = ExecutionResult(
                step=step.skill_id,
                status="success",
                outputs={
                    "skill_name": skill.name,
                    "requirements": skill.requirements,
                    "context_keys": sorted(context.keys()),
                },
                message=f"Prepared execution for {skill.name}.",
            )
        if isinstance(run_ledger, RunLedger) and run_id:
            final_state = self._result_to_run_state(result.status)
            run_ledger.finish_step(
                run_id,
                step_id=step_id,
                final_state=final_state,
                reason=result.message,
                waiting_on="operator_action" if final_state == "blocked_policy" else "",
                failure_reason=result.message
                if final_state in {"failed", "blocked_policy"}
                else "",
                owner="operator" if final_state == "blocked_policy" else "orchestrator",
                metadata={"step": result.step, "status": result.status},
            )
        return result

    def _execute_count_matrix_summary(self, context: dict[str, Any]) -> ExecutionResult:
        parameters = context.get("parameters", {})
        run_id = str(context.get("run_id") or "")
        run_ledger = context.get("run_ledger")
        step_id = str(context.get("_current_step_id") or "count_matrix_summary")
        counts_file = parameters.get("counts_file")
        sample_sheet = parameters.get("sample_sheet")
        if not counts_file:
            return ExecutionResult(
                step="count_matrix_summary",
                status="blocked",
                outputs={
                    "reason": "counts_file is required for prototype count-matrix analysis."
                },
                message="Blocked Count Matrix Summary: missing counts_file.",
            )

        analyzer = importlib.import_module("abris.analysis.count_matrix_summary")
        try:
            summary = analyzer.summarize_count_matrix(counts_file, sample_sheet)
        except ValueError as exc:
            return ExecutionResult(
                step="count_matrix_summary",
                status="blocked",
                outputs={
                    "counts_file": counts_file,
                    "sample_sheet": sample_sheet,
                    "validation_error": str(exc),
                },
                message=f"Blocked Count Matrix Summary: {exc}",
            )

        artifact_paths: list[str] = []
        if run_id and isinstance(run_ledger, RunLedger):
            for candidate in [counts_file, sample_sheet]:
                if candidate:
                    artifact_path = str(candidate)
                    run_ledger.attach_artifact(
                        run_id,
                        step_id=step_id,
                        artifact_path=artifact_path,
                    )
                    artifact_paths.append(artifact_path)

            artifact_dir = self.settings.run_dir / "artifacts" / run_id
            artifact_dir.mkdir(parents=True, exist_ok=True)
            output_path = artifact_dir / f"{step_id}_summary.json"
            output_path.write_text(
                json.dumps(summary, ensure_ascii=False, indent=2),
                encoding="utf-8",
            )
            run_ledger.attach_artifact(
                run_id,
                step_id=step_id,
                artifact_path=str(output_path),
            )
            artifact_paths.append(str(output_path))
            summary = {
                **summary,
                "artifact_paths": artifact_paths,
                "recorded_at": datetime.now(timezone.utc).isoformat(),
            }

        return ExecutionResult(
            step="count_matrix_summary",
            status="success",
            outputs=summary,
            message="Completed lightweight count-matrix summary analysis.",
        )

    def _record_terminal_results(
        self, run_id: str, results: list[ExecutionResult]
    ) -> None:
        if not results:
            return
        last = results[-1]
        if all(result.status == "success" for result in results):
            self.run_ledger.set_run_state(
                run_id,
                new_state="completed",
                owner="orchestrator",
                metadata={"result_count": len(results)},
            )
            return
        state = self._result_to_run_state(last.status)
        self.run_ledger.set_run_state(
            run_id,
            new_state=state,
            reason=last.message,
            waiting_on="operator_action" if state == "blocked_policy" else "",
            failure_reason=last.message,
            owner="operator" if state == "blocked_policy" else "orchestrator",
            metadata={"result_count": len(results), "failed_step": last.step},
        )

    def _result_to_run_state(self, status: str) -> str:
        return {
            "success": "completed",
            "blocked": "blocked_policy",
            "failed": "failed",
            "aborted": "aborted",
        }.get(status, "failed")
