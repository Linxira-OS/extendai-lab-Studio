from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

AutonomyMode = str
EvidenceAdmissibility = str
RunState = str


@dataclass(slots=True)
class AnalysisIntent:
    analysis_type: str
    goal: str
    parameters: dict[str, Any] = field(default_factory=dict)
    expected_outputs: list[str] = field(default_factory=list)
    requires_acquisition: bool = False
    acquisition_requests: list["AcquisitionRequest"] = field(default_factory=list)
    requests_codegen: bool = False
    requests_optimization: bool = False


@dataclass(slots=True)
class AcquisitionRequest:
    source_class: str
    locator: str


@dataclass(slots=True)
class AutonomyPolicy:
    mode: AutonomyMode = "plan_only"
    approval_required: bool = True
    allowed_source_classes: list[str] = field(default_factory=list)
    codegen_scope: list[str] = field(default_factory=list)
    optimization_scope: list[str] = field(default_factory=list)
    policy_version: str = "gov.v1"
    max_steps: int = 4

    def allows_execution(self) -> bool:
        return self.mode != "plan_only"

    def allows_acquisition(self) -> bool:
        return self.mode in {"acquire_bounded", "generate_bounded", "optimize_proposed"}

    def allows_codegen(self) -> bool:
        return self.mode in {"generate_bounded", "optimize_proposed"}

    def allows_optimization(self) -> bool:
        return self.mode == "optimize_proposed"

    def to_runtime_envelope(self) -> dict[str, Any]:
        return {
            "policy_version": self.policy_version,
            "autonomy_mode": self.mode,
            "approval_required": self.approval_required,
            "allowed_source_classes": self.allowed_source_classes,
            "codegen_scope": self.codegen_scope,
            "optimization_scope": self.optimization_scope,
            "max_steps": self.max_steps,
        }


@dataclass(slots=True)
class EnvironmentSnapshot:
    os_name: str
    python_version: str
    cpu_count: int
    available_tools: list[str] = field(default_factory=list)
    available_python_modules: list[str] = field(default_factory=list)
    available_r_packages: list[str] = field(default_factory=list)
    notes: list[str] = field(default_factory=list)


@dataclass(slots=True)
class SkillSpec:
    skill_id: str
    name: str
    layer: str
    category: str
    description: str
    requirements: list[str] = field(default_factory=list)


@dataclass(slots=True)
class PipelineStep:
    skill_id: str
    parameters: dict[str, Any] = field(default_factory=dict)


@dataclass(slots=True)
class InputAsset:
    asset_id: str
    path: Path
    file_type: str
    detected_format: str
    size_bytes: int
    size_class: str
    protected: bool
    metadata_summary: dict[str, Any] = field(default_factory=dict)
    preview_summary: dict[str, Any] = field(default_factory=dict)
    recommended_actions: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)


@dataclass(slots=True)
class FileReadRequest:
    path: Path
    operation: str
    caller: str
    embed_in_prompt: bool = False
    policy_override: dict[str, Any] = field(default_factory=dict)


@dataclass(slots=True)
class FileAccessDecision:
    action: str
    allowed: bool
    reason: str
    warnings: list[str] = field(default_factory=list)
    policy_rule: str = ""
    safe_summary: dict[str, Any] = field(default_factory=dict)
    redirect_tool: str | None = None


@dataclass(slots=True)
class ExecutionResult:
    step: str
    status: str
    outputs: dict[str, Any] = field(default_factory=dict)
    message: str = ""


@dataclass(slots=True)
class TokenUsage:
    session_id: str
    input_tokens: int = 0
    output_tokens: int = 0
    total_tokens: int = 0
    cost: float = 0.0
    message_count: int = 0
    prompt_count: int = 0


@dataclass(slots=True)
class SessionEvent:
    event_id: str
    session_id: str
    event_type: str
    timestamp: str = ""
    payload: dict[str, Any] = field(default_factory=dict)


@dataclass(slots=True)
class ArtifactRef:
    artifact_id: str
    path: str
    kind: str
    safe_action: str
    summary: dict[str, Any] = field(default_factory=dict)


@dataclass(slots=True)
class ControlPlaneSession:
    session_id: str
    title: str
    status: str
    message_count: int = 0
    last_message_at: str = ""
    stalled: bool = False
    usage: TokenUsage | None = None


@dataclass(slots=True)
class AuthorizationContext:
    username: str
    role: str
    session_token: str


@dataclass(slots=True)
class EvidenceRecord:
    evidence_id: str
    query: str
    source_class: str
    provider: str
    title: str
    authors: list[str] = field(default_factory=list)
    year: int | None = None
    url: str = ""
    doi: str = ""
    pmid: str = ""
    arxiv_id: str = ""
    license: str = ""
    retrieved_at: str = ""
    checksum: str = ""
    raw_snippet: str = ""
    normalized_abstract: str = ""
    confidence: float = 0.0
    admissibility: EvidenceAdmissibility = "blocked"
    admissibility_reason: str = ""


@dataclass(slots=True)
class EvidenceBundle:
    bundle_id: str
    query: str
    session_id: str
    retrieved_at: str
    run_id: str = ""
    step_id: str = ""
    records: list[EvidenceRecord] = field(default_factory=list)
    usage: TokenUsage | None = None
    summary: dict[str, Any] = field(default_factory=dict)
    warnings: list[str] = field(default_factory=list)


@dataclass(slots=True)
class RunStepState:
    step_id: str
    step_type: str
    title: str
    state: RunState
    created_at: str
    updated_at: str
    waiting_on: str = ""
    owner: str = ""
    stalled: bool = False
    stalled_reason: str = ""
    last_heartbeat: str = ""
    last_checkpoint: str = ""
    failure_reason: str = ""
    runtime_session_id: str = ""
    evidence_bundle_id: str = ""
    artifact_paths: list[str] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(slots=True)
class RunRecord:
    run_id: str
    run_type: str
    title: str
    current_state: RunState
    created_at: str
    updated_at: str
    waiting_on: str = ""
    owner: str = ""
    stalled: bool = False
    stalled_reason: str = ""
    last_heartbeat: str = ""
    last_checkpoint: str = ""
    failure_reason: str = ""
    runtime_session_ids: list[str] = field(default_factory=list)
    evidence_bundle_ids: list[str] = field(default_factory=list)
    artifact_paths: list[str] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)
    steps: list[RunStepState] = field(default_factory=list)


@dataclass(slots=True)
class RunEvent:
    event_id: str
    run_id: str
    step_id: str = ""
    event_type: str = ""
    state_from: str = ""
    state_to: str = ""
    timestamp: str = ""
    reason: str = ""
    payload: dict[str, Any] = field(default_factory=dict)


@dataclass(slots=True)
class AnalysisReport:
    run_id: str
    intent: AnalysisIntent
    environment: EnvironmentSnapshot
    plan: list[PipelineStep]
    results: list[ExecutionResult]
    autonomy_policy: AutonomyPolicy = field(default_factory=AutonomyPolicy)
    assets: list[InputAsset] = field(default_factory=list)
    file_access_decisions: list[FileAccessDecision] = field(default_factory=list)
