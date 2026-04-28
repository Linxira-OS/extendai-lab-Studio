import type {
  ActivityEvent,
  ArtifactItem,
  ArtifactsResponse,
  EvidenceRecord,
  EvidenceSearchResponse,
  RunDetailResponse,
  RunInfo,
  RunStepInfo,
  SessionInfo,
  SessionMessage,
  SessionMessagesResponse,
  SessionUsageResponse,
  TimelineEntry,
  Totals,
} from "./api"

export type ControlPlaneFixtureScenario = {
  mode: "demo" | "smoke"
  totals: Totals
  runs: RunInfo[]
  sessions: SessionInfo[]
  activity: ActivityEvent[]
  runDetails: Record<string, RunDetailResponse>
  sessionUsage: Record<string, SessionUsageResponse>
  sessionMessages: Record<string, SessionMessagesResponse>
  artifacts: Record<string, ArtifactsResponse>
  evidence: Record<string, EvidenceSearchResponse>
  defaultRunId: string
  defaultSessionId: string
  defaultArtifactPath: string
  defaultEvidenceQuery: string
}

const now = new Date()

const minusMinutes = (minutes: number) =>
  new Date(now.getTime() - minutes * 60_000).toISOString()

const minusHours = (hours: number) =>
  new Date(now.getTime() - hours * 3_600_000).toISOString()

function createEvidenceSummary(records: EvidenceRecord[]) {
  return {
    record_count: records.length,
    allowed_count: records.filter((record) => record.admissibility === "allowed").length,
    downgraded_count: records.filter((record) => record.admissibility === "downgraded").length,
  }
}

function createArtifactsResponse(path: string, items: ArtifactItem[]): ArtifactsResponse {
  return { path, entries: items }
}

function createEvidenceResponse(
  bundleId: string,
  query: string,
  records: EvidenceRecord[],
  runId?: string,
): EvidenceSearchResponse {
  return {
    bundle_id: bundleId,
    query,
    run_id: runId,
    records,
    summary: createEvidenceSummary(records),
    warnings: [],
  }
}

function createMessages(messages: SessionMessage[]): SessionMessagesResponse {
  return { messages }
}

const DEMO_TOTALS: Totals = {
  session_count: 9,
  stalled_count: 1,
  run_count: 6,
  blocked_run_count: 1,
  stalled_run_count: 1,
}

const DEMO_RUNS: RunInfo[] = [
  {
    run_id: "run-af3-screen",
    run_type: "evidence_synthesis",
    title: "AlphaFold3 binder-screen evidence synthesis",
    current_state: "running",
    created_at: minusHours(3),
    updated_at: minusMinutes(8),
    waiting_on: "Cross-check docking benchmark appendix",
    owner: "paper-evidence-synthesizer",
    last_heartbeat: minusMinutes(2),
    last_checkpoint: "step-4-grade-evidence",
    failure_reason: "",
    stalled: false,
    stalled_reason: "",
    metadata: { study_area: "structure-based drug design", environment: "opencode" },
  },
  {
    run_id: "run-multiomics-qc",
    run_type: "pipeline_orchestration",
    title: "Tumor-normal multi-omics QC and cohort merge",
    current_state: "blocked_policy",
    created_at: minusHours(6),
    updated_at: minusMinutes(36),
    waiting_on: "Approve protected bucket export",
    owner: "bio-orchestrator",
    last_heartbeat: minusMinutes(34),
    last_checkpoint: "step-2-merge-cohorts",
    failure_reason: "",
    stalled: false,
    stalled_reason: "",
    metadata: { study_area: "multi-omics", environment: "backend" },
  },
  {
    run_id: "run-crispr-brief",
    run_type: "technical_brief",
    title: "CRISPR off-target review for executive brief",
    current_state: "completed",
    created_at: minusHours(28),
    updated_at: minusHours(22),
    waiting_on: "",
    owner: "scientific-writer",
    last_heartbeat: minusHours(22),
    last_checkpoint: "step-5-publish-brief",
    failure_reason: "",
    stalled: false,
    stalled_reason: "",
    metadata: { audience: "leadership" },
  },
  {
    run_id: "run-kinase-fold",
    run_type: "structure_prediction",
    title: "Kinase X structure triage and failure analysis",
    current_state: "failed",
    created_at: minusHours(14),
    updated_at: minusHours(13),
    waiting_on: "",
    owner: "bio-pipeline-operator",
    last_heartbeat: minusHours(13),
    last_checkpoint: "step-3-gpu-folding",
    failure_reason: "GPU memory pressure interrupted MSA alignment chunk 7 of 9.",
    stalled: false,
    stalled_reason: "",
    metadata: { cluster: "gpu-a100" },
  },
  {
    run_id: "run-clinvar-smoke",
    run_type: "smoke_validation",
    title: "ClinVar ingestion smoke validation",
    current_state: "running",
    created_at: minusMinutes(42),
    updated_at: minusMinutes(4),
    waiting_on: "",
    owner: "opencode-runtime",
    last_heartbeat: minusMinutes(1),
    last_checkpoint: "step-1-schema-check",
    failure_reason: "",
    stalled: false,
    stalled_reason: "",
    metadata: { mode: "smoke" },
  },
  {
    run_id: "run-proteomics-stall",
    run_type: "pipeline_orchestration",
    title: "Proteomics batch harmonization",
    current_state: "running",
    created_at: minusHours(9),
    updated_at: minusHours(2),
    waiting_on: "Worker heartbeat overdue",
    owner: "bio-orchestrator",
    last_heartbeat: minusHours(2),
    last_checkpoint: "step-3-normalize-intensity",
    failure_reason: "",
    stalled: true,
    stalled_reason: "No worker heartbeat for 121 minutes.",
    metadata: { priority: "high" },
  },
]

const DEMO_SESSION_USAGE: Record<string, SessionUsageResponse> = {
  "ses-af3-01": {
    session_id: "ses-af3-01",
    input_tokens: 126_400,
    output_tokens: 31_200,
    total_tokens: 157_600,
    cost: 2.41,
    message_count: 24,
    prompt_count: 12,
  },
  "ses-qc-02": {
    session_id: "ses-qc-02",
    input_tokens: 42_800,
    output_tokens: 9_300,
    total_tokens: 52_100,
    cost: 0.81,
    message_count: 11,
    prompt_count: 6,
  },
  "ses-brief-03": {
    session_id: "ses-brief-03",
    input_tokens: 211_000,
    output_tokens: 84_300,
    total_tokens: 295_300,
    cost: 5.94,
    message_count: 37,
    prompt_count: 18,
  },
}

const DEMO_SESSIONS: SessionInfo[] = [
  {
    session_id: "ses-af3-01",
    title: "AlphaFold3 benchmark interpretation",
    status: "active",
    message_count: 24,
    last_message_at: minusMinutes(6),
    stalled: false,
    usage: DEMO_SESSION_USAGE["ses-af3-01"],
  },
  {
    session_id: "ses-qc-02",
    title: "Protected cohort merge approval thread",
    status: "blocked",
    message_count: 11,
    last_message_at: minusMinutes(37),
    stalled: true,
    usage: DEMO_SESSION_USAGE["ses-qc-02"],
  },
  {
    session_id: "ses-brief-03",
    title: "CRISPR leadership memo drafting",
    status: "completed",
    message_count: 37,
    last_message_at: minusHours(22),
    stalled: false,
    usage: DEMO_SESSION_USAGE["ses-brief-03"],
  },
]

const DEMO_ACTIVITY: ActivityEvent[] = [
  {
    event_id: "evt-af3-1",
    session_id: "ses-af3-01",
    event_type: "agent_action",
    timestamp: minusMinutes(3),
    payload: { state: "Extracted benchmark caveats from supplementary appendix" },
  },
  {
    event_id: "evt-af3-2",
    session_id: "ses-af3-01",
    event_type: "state_change",
    timestamp: minusMinutes(9),
    payload: { state_to: "running", reason: "Continuing evidence grading after new DOI match" },
  },
  {
    event_id: "evt-qc-1",
    session_id: "ses-qc-02",
    event_type: "policy_block",
    timestamp: minusMinutes(36),
    payload: { state: "blocked_policy", reason: "Export target contains protected subject identifiers" },
  },
  {
    event_id: "evt-stall-1",
    session_id: "ses-qc-02",
    event_type: "system_alert",
    timestamp: minusHours(2),
    payload: { state: "stalled", reason: "Worker heartbeat dropped below threshold" },
  },
  {
    event_id: "evt-brief-1",
    session_id: "ses-brief-03",
    event_type: "state_change",
    timestamp: minusHours(22),
    payload: { state_to: "completed", reason: "Leadership brief exported to review bundle" },
  },
]

const DEMO_MESSAGES_AF3: SessionMessage[] = [
  {
    role: "user",
    createdAt: minusHours(3),
    content: "Summarize whether AlphaFold3 materially improves binder-screen decision quality over docking-only baselines.",
  },
  {
    role: "assistant",
    createdAt: minusHours(3),
    content: "I started a synthesis run across Nature, bioRxiv, and supporting benchmark datasets. I will separate peer-reviewed findings from exploratory preprints.",
  },
  {
    role: "assistant",
    createdAt: minusMinutes(42),
    parts: [
      {
        type: "text",
        text: "The strongest signal is improved complex-level structural plausibility, but screening throughput and calibration still depend on downstream docking and assay context.",
      },
      {
        type: "tool_call",
        toolName: "paper_search_mcp_search_pubmed",
      },
      {
        type: "evidence_bundle",
        summary: "24 records graded, 6 prioritized for the final brief.",
      },
    ],
    usage: {
      input_tokens: 6420,
      output_tokens: 1480,
      total_tokens: 7900,
    },
  },
  {
    role: "user",
    createdAt: minusMinutes(18),
    content: "Keep the conclusion conservative and call out where evidence is still preclinical.",
  },
  {
    role: "assistant",
    createdAt: minusMinutes(6),
    parts: [
      {
        type: "text",
        text: "Done. The draft now separates peer-reviewed claims, preprint-only claims, and operational risks for screening teams.",
      },
      {
        type: "artifact_update",
        content: "Updated workspace/reports/alphafold3_binder_screen_brief.md with a conservative recommendation section.",
      },
    ],
  },
]

const DEMO_MESSAGES_QC: SessionMessage[] = [
  {
    role: "user",
    createdAt: minusHours(6),
    content: "Can we merge the tumor-normal cohort and export the harmonized matrix for downstream modeling?",
  },
  {
    role: "assistant",
    createdAt: minusHours(6),
    parts: [
      {
        type: "text",
        text: "The merge is ready, but the target bucket contains protected identifiers. Approval is required before the export step can continue.",
      },
      {
        type: "policy_block",
        tool_name: "secure_export_guard",
        content: "Protected export target requires user approval before any artifact leaves the workspace.",
      },
    ],
  },
  {
    role: "assistant",
    createdAt: minusMinutes(37),
    content: "I left the pipeline at the policy boundary so no protected data was moved automatically.",
  },
]

const DEMO_MESSAGES_BRIEF: SessionMessage[] = [
  {
    role: "user",
    createdAt: minusHours(27),
    content: "Create a short executive brief on off-target editing risk for the current CRISPR program review.",
  },
  {
    role: "assistant",
    createdAt: minusHours(26),
    content: "I prepared a three-part memo covering detection methods, program risk, and mitigation options with citations.",
  },
]

const DEMO_EVIDENCE_AF3: EvidenceRecord[] = [
  {
    evidence_id: "ev-af3-001",
    title: "Accurate structure prediction of biomolecular interactions with AlphaFold 3",
    provider: "Nature",
    source_class: "Journal Article",
    admissibility: "allowed",
    admissibility_reason: "Peer-reviewed primary source",
    year: 2024,
    doi: "10.1038/s41586-024-07487-w",
    url: "https://doi.org/10.1038/s41586-024-07487-w",
    confidence: 0.98,
    normalized_abstract: "AlphaFold 3 expands joint structure prediction to proteins, nucleic acids, small molecules, ions, and modified residues, improving complex-level structural reasoning for discovery workflows.",
  },
  {
    evidence_id: "ev-af3-002",
    title: "Benchmarking AlphaFold3 on kinase-inhibitor complexes with docking baselines",
    provider: "bioRxiv",
    source_class: "Preprint",
    admissibility: "downgraded",
    admissibility_reason: "Preprint awaiting peer review",
    year: 2024,
    confidence: 0.76,
    normalized_abstract: "The preprint reports stronger pose plausibility than docking-only baselines on difficult kinase complexes, but notes calibration drift for weak binders and throughput tradeoffs in screening-scale use.",
  },
  {
    evidence_id: "ev-af3-003",
    title: "Generative AI in structure-based drug design",
    provider: "PubMed",
    source_class: "Review",
    admissibility: "allowed",
    admissibility_reason: "Established review source",
    year: 2023,
    pmid: "37700123",
    confidence: 0.88,
    normalized_abstract: "A review of generative and structure-aware models in drug discovery that contextualizes where AlphaFold-style models help and where wet-lab validation remains the limiting step.",
  },
]

const DEMO_EVIDENCE_QC: EvidenceRecord[] = [
  {
    evidence_id: "ev-qc-001",
    title: "Best practices for multi-omics cohort harmonization in translational studies",
    provider: "Nature Methods",
    source_class: "Methods Article",
    admissibility: "allowed",
    admissibility_reason: "Peer-reviewed workflow guidance",
    year: 2023,
    confidence: 0.91,
    normalized_abstract: "Describes sample identity resolution, batch handling, and metadata controls required before cross-platform cohort merging in translational studies.",
  },
]

const DEMO_ARTIFACTS_MAIN: ArtifactItem[] = [
  {
    artifact_id: "art-af3-brief",
    path: "workspace/reports/alphafold3_binder_screen_brief.md",
    kind: "file",
    safe_action: "read",
    summary: {
      file_name: "alphafold3_binder_screen_brief.md",
      size_class: "18KB",
      detected_format: "markdown",
      protected: false,
    },
  },
  {
    artifact_id: "art-af3-matrix",
    path: "workspace/data/benchmark_pose_matrix.csv",
    kind: "file",
    safe_action: "read",
    summary: {
      file_name: "benchmark_pose_matrix.csv",
      size_class: "146KB",
      detected_format: "csv",
      protected: false,
    },
  },
  {
    artifact_id: "art-af3-note",
    path: "workspace/notes/policy_block_review.txt",
    kind: "file",
    safe_action: "read",
    summary: {
      file_name: "policy_block_review.txt",
      size_class: "4KB",
      detected_format: "text",
      protected: true,
    },
  },
]

const DEMO_TIMELINE_AF3: TimelineEntry[] = [
  {
    index: 1,
    event_id: "af3-t1",
    step_id: "step-1-query",
    event_type: "step_started",
    state_from: "pending",
    state_to: "running",
    timestamp: minusHours(3),
    reason: "Starting literature collection",
    payload: {},
  },
  {
    index: 2,
    event_id: "af3-t2",
    step_id: "step-1-query",
    event_type: "step_completed",
    state_from: "running",
    state_to: "completed",
    timestamp: minusHours(2.4),
    reason: "DOI and PubMed retrieval complete",
    payload: {},
  },
  {
    index: 3,
    event_id: "af3-t3",
    step_id: "step-3-grade",
    event_type: "step_started",
    state_from: "pending",
    state_to: "running",
    timestamp: minusMinutes(58),
    reason: "Evaluating peer-review and assay alignment",
    payload: {},
  },
  {
    index: 4,
    event_id: "af3-t4",
    step_id: "step-4-brief",
    event_type: "state_change",
    state_from: "pending",
    state_to: "running",
    timestamp: minusMinutes(8),
    reason: "Drafting conservative conclusions for screening team",
    payload: {},
  },
]

const DEMO_RUN_STEPS_AF3: RunStepInfo[] = [
  {
    step_id: "step-1-query",
    title: "Collect literature and benchmark references",
    state: "completed",
    last_checkpoint: minusHours(2.4),
  },
  {
    step_id: "step-2-filter",
    title: "Filter non-comparable assay evidence",
    state: "completed",
    last_checkpoint: minusHours(1.6),
  },
  {
    step_id: "step-3-grade",
    title: "Grade evidence by review status and assay fit",
    state: "completed",
    last_checkpoint: minusMinutes(42),
  },
  {
    step_id: "step-4-brief",
    title: "Draft screening recommendation memo",
    state: "running",
    waiting_on: "Benchmark appendix review",
    last_checkpoint: minusMinutes(8),
  },
]

const DEMO_RUN_DETAIL_AF3: RunDetailResponse = {
  run: DEMO_RUNS[0],
  steps: DEMO_RUN_STEPS_AF3,
  timeline: DEMO_TIMELINE_AF3,
  current_step: { step_id: "step-4-brief", title: "Draft screening recommendation memo" },
  linked: {
    runtime_session_ids: ["ses-af3-01"],
    evidence_bundle_ids: ["bundle-af3-main"],
    artifact_paths: ["workspace/reports/alphafold3_binder_screen_brief.md"],
    evidence_bundles: [createEvidenceResponse("bundle-af3-main", "AlphaFold3 binder screening evidence", DEMO_EVIDENCE_AF3, DEMO_RUNS[0].run_id)],
    artifacts: DEMO_ARTIFACTS_MAIN,
  },
  events: [],
}

const DEMO_RUN_DETAIL_QC: RunDetailResponse = {
  run: DEMO_RUNS[1],
  steps: [
    {
      step_id: "step-1-identity",
      title: "Resolve sample identity map",
      state: "completed",
      last_checkpoint: minusHours(5.4),
    },
    {
      step_id: "step-2-merge-cohorts",
      title: "Merge tumor-normal cohort tables",
      state: "blocked_policy",
      waiting_on: "Approve protected bucket export",
      last_checkpoint: minusMinutes(36),
    },
  ],
  timeline: [
    {
      index: 1,
      event_id: "qc-t1",
      step_id: "step-2-merge-cohorts",
      event_type: "policy_block",
      state_from: "running",
      state_to: "blocked_policy",
      timestamp: minusMinutes(36),
      reason: "Protected export target requires user approval",
      payload: {},
    },
  ],
  current_step: { step_id: "step-2-merge-cohorts", title: "Merge tumor-normal cohort tables" },
  linked: {
    runtime_session_ids: ["ses-qc-02"],
    evidence_bundles: [createEvidenceResponse("bundle-qc-main", "multi-omics cohort harmonization", DEMO_EVIDENCE_QC, DEMO_RUNS[1].run_id)],
    artifacts: [],
  },
  events: [],
}

const DEMO_RUN_DETAILS: Record<string, RunDetailResponse> = {
  [DEMO_RUNS[0].run_id]: DEMO_RUN_DETAIL_AF3,
  [DEMO_RUNS[1].run_id]: DEMO_RUN_DETAIL_QC,
  [DEMO_RUNS[2].run_id]: {
    run: DEMO_RUNS[2],
    steps: [],
    timeline: [],
    current_step: null,
    linked: {},
    events: [],
  },
  [DEMO_RUNS[3].run_id]: {
    run: DEMO_RUNS[3],
    steps: [],
    timeline: [],
    current_step: null,
    linked: {},
    events: [],
  },
  [DEMO_RUNS[4].run_id]: {
    run: DEMO_RUNS[4],
    steps: [],
    timeline: [],
    current_step: null,
    linked: {},
    events: [],
  },
  [DEMO_RUNS[5].run_id]: {
    run: DEMO_RUNS[5],
    steps: [],
    timeline: [],
    current_step: null,
    linked: {},
    events: [],
  },
}

const DEMO_SESSION_MESSAGES: Record<string, SessionMessagesResponse> = {
  "ses-af3-01": createMessages(DEMO_MESSAGES_AF3),
  "ses-qc-02": createMessages(DEMO_MESSAGES_QC),
  "ses-brief-03": createMessages(DEMO_MESSAGES_BRIEF),
}

const DEMO_ARTIFACTS: Record<string, ArtifactsResponse> = {
  ".": createArtifactsResponse(".", DEMO_ARTIFACTS_MAIN),
  workspace: createArtifactsResponse("workspace", DEMO_ARTIFACTS_MAIN),
}

const DEMO_EVIDENCE: Record<string, EvidenceSearchResponse> = {
  [DEMO_RUNS[0].run_id]: createEvidenceResponse(
    "bundle-af3-main",
    "AlphaFold3 binder screening evidence",
    DEMO_EVIDENCE_AF3,
    DEMO_RUNS[0].run_id,
  ),
  [DEMO_RUNS[1].run_id]: createEvidenceResponse(
    "bundle-qc-main",
    "multi-omics cohort harmonization",
    DEMO_EVIDENCE_QC,
    DEMO_RUNS[1].run_id,
  ),
}

export const DEMO_SCENARIO: ControlPlaneFixtureScenario = {
  mode: "demo",
  totals: DEMO_TOTALS,
  runs: DEMO_RUNS,
  sessions: DEMO_SESSIONS,
  activity: DEMO_ACTIVITY,
  runDetails: DEMO_RUN_DETAILS,
  sessionUsage: DEMO_SESSION_USAGE,
  sessionMessages: DEMO_SESSION_MESSAGES,
  artifacts: DEMO_ARTIFACTS,
  evidence: DEMO_EVIDENCE,
  defaultRunId: DEMO_RUNS[0].run_id,
  defaultSessionId: DEMO_SESSIONS[0].session_id,
  defaultArtifactPath: "workspace",
  defaultEvidenceQuery: "AlphaFold3 binder screening evidence",
}

const SMOKE_TOTALS: Totals = {
  session_count: 1,
  stalled_count: 0,
  run_count: 1,
  blocked_run_count: 0,
  stalled_run_count: 0,
}

const SMOKE_RUNS: RunInfo[] = [
  {
    run_id: "run-smoke-001",
    run_type: "smoke_validation",
    title: "Smoke mode shell validation",
    current_state: "running",
    created_at: minusMinutes(22),
    updated_at: minusMinutes(1),
    waiting_on: "",
    owner: "opencode-runtime",
    last_heartbeat: minusMinutes(1),
    last_checkpoint: "step-1-render-shell",
    failure_reason: "",
    stalled: false,
    stalled_reason: "",
    metadata: { mode: "smoke" },
  },
]

const SMOKE_SESSION_USAGE: SessionUsageResponse = {
  session_id: "ses-smoke-001",
  input_tokens: 1_200,
  output_tokens: 340,
  total_tokens: 1_540,
  cost: 0.03,
  message_count: 3,
  prompt_count: 2,
}

const SMOKE_SESSIONS: SessionInfo[] = [
  {
    session_id: "ses-smoke-001",
    title: "Smoke mode session",
    status: "active",
    message_count: 3,
    last_message_at: minusMinutes(2),
    stalled: false,
    usage: SMOKE_SESSION_USAGE,
  },
]

const SMOKE_MESSAGES: SessionMessage[] = [
  {
    role: "user",
    createdAt: minusMinutes(22),
    content: "Run the control-plane smoke scenario.",
  },
  {
    role: "assistant",
    createdAt: minusMinutes(21),
    parts: [
      {
        type: "text",
        text: "Smoke mode is active. Shell layout, tabs, and fallback bindings are available for quick validation.",
      },
      {
        type: "tool_result",
        toolName: "smoke_fixture_loader",
        summary: "Loaded 1 run, 1 session, 1 artifact path, and 1 evidence bundle.",
      },
    ],
    usage: {
      input_tokens: 120,
      output_tokens: 84,
      total_tokens: 204,
    },
  },
]

const SMOKE_EVIDENCE_RECORDS: EvidenceRecord[] = [
  {
    evidence_id: "ev-smoke-001",
    title: "Smoke fixture evidence record",
    provider: "fixture",
    source_class: "Fixture",
    admissibility: "allowed",
    admissibility_reason: "Deterministic smoke data",
    confidence: 1,
    normalized_abstract: "A compact fixture used to validate the control-plane shell without long narrative content.",
  },
]

const SMOKE_ARTIFACTS_LIST: ArtifactItem[] = [
  {
    artifact_id: "art-smoke-001",
    path: "workspace/smoke/status.json",
    kind: "file",
    safe_action: "read",
    summary: {
      file_name: "status.json",
      size_class: "1KB",
      detected_format: "json",
      protected: false,
    },
  },
]

export const SMOKE_SCENARIO: ControlPlaneFixtureScenario = {
  mode: "smoke",
  totals: SMOKE_TOTALS,
  runs: SMOKE_RUNS,
  sessions: SMOKE_SESSIONS,
  activity: [
    {
      event_id: "evt-smoke-001",
      session_id: "ses-smoke-001",
      event_type: "state_change",
      timestamp: minusMinutes(2),
      payload: { state_to: "running", reason: "Smoke shell validated" },
    },
  ],
  runDetails: {
    "run-smoke-001": {
      run: SMOKE_RUNS[0],
      steps: [
        {
          step_id: "step-1-render-shell",
          title: "Render shell",
          state: "completed",
          last_checkpoint: minusMinutes(12),
        },
        {
          step_id: "step-2-bind-fallback",
          title: "Bind fallback data",
          state: "running",
          last_checkpoint: minusMinutes(1),
        },
      ],
      timeline: [
        {
          index: 1,
          event_id: "smoke-t1",
          step_id: "step-2-bind-fallback",
          event_type: "state_change",
          state_from: "pending",
          state_to: "running",
          timestamp: minusMinutes(1),
          reason: "Validating fallback bindings",
          payload: {},
        },
      ],
      current_step: { step_id: "step-2-bind-fallback", title: "Bind fallback data" },
      linked: {
        runtime_session_ids: ["ses-smoke-001"],
        evidence_bundles: [
          createEvidenceResponse(
            "bundle-smoke-001",
            "control-plane smoke validation",
            SMOKE_EVIDENCE_RECORDS,
            "run-smoke-001",
          ),
        ],
        artifacts: SMOKE_ARTIFACTS_LIST,
      },
      events: [],
    },
  },
  sessionUsage: { "ses-smoke-001": SMOKE_SESSION_USAGE },
  sessionMessages: { "ses-smoke-001": createMessages(SMOKE_MESSAGES) },
  artifacts: { workspace: createArtifactsResponse("workspace", SMOKE_ARTIFACTS_LIST) },
  evidence: {
    "run-smoke-001": createEvidenceResponse(
      "bundle-smoke-001",
      "control-plane smoke validation",
      SMOKE_EVIDENCE_RECORDS,
      "run-smoke-001",
    ),
  },
  defaultRunId: "run-smoke-001",
  defaultSessionId: "ses-smoke-001",
  defaultArtifactPath: "workspace",
  defaultEvidenceQuery: "control-plane smoke validation",
}

export const MOCK_TOTALS = DEMO_SCENARIO.totals
export const MOCK_RUNS = DEMO_SCENARIO.runs
export const MOCK_SESSIONS = DEMO_SCENARIO.sessions
export const MOCK_ACTIVITY = DEMO_SCENARIO.activity
export const MOCK_MESSAGES = DEMO_MESSAGES_AF3
export const MOCK_EVIDENCE = DEMO_EVIDENCE_AF3
export const MOCK_ARTIFACTS = DEMO_ARTIFACTS_MAIN
export const MOCK_TIMELINE = DEMO_TIMELINE_AF3
export const MOCK_RUN_STEPS = DEMO_RUN_STEPS_AF3
export const MOCK_RUN_DETAIL = DEMO_RUN_DETAIL_AF3
