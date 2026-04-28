import type {
  ActivityResponse,
  ArtifactsResponse,
  EvidenceSearchResponse,
  RunDetailResponse,
  RunInfo,
  SessionInfo,
  SessionMessagesResponse,
  SessionUsageResponse,
  Totals,
} from "./api"
import {
  DEMO_SCENARIO,
  SMOKE_SCENARIO,
  type ControlPlaneFixtureScenario,
} from "./mockData"

export type ControlPlaneDataMode = "auto" | "real" | "demo" | "smoke"

type ControlPlaneQueryState = {
  runs?: { runs: RunInfo[] }
  sessions?: { sessions: SessionInfo[] }
  activity?: ActivityResponse
  runDetail?: RunDetailResponse
  sessionUsage?: SessionUsageResponse
  sessionMessages?: SessionMessagesResponse
  artifacts?: ArtifactsResponse
  evidence?: EvidenceSearchResponse
}

export type ResolvedControlPlaneData = {
  mode: Exclude<ControlPlaneDataMode, "auto">
  totals: Totals
  runs: RunInfo[]
  sessions: SessionInfo[]
  activity: ActivityResponse["events"]
  runDetail?: RunDetailResponse
  sessionUsage?: SessionUsageResponse
  sessionMessages?: SessionMessagesResponse["messages"]
  artifacts?: ArtifactsResponse
  evidence?: EvidenceSearchResponse
  defaultRunId?: string
  defaultSessionId?: string
  defaultArtifactPath: string
  defaultEvidenceQuery: string
}

export type ControlPlaneIntegrationArea =
  | "runList"
  | "sessionList"
  | "activity"
  | "runDetail"
  | "sessionUsage"
  | "sessionMessages"
  | "artifacts"
  | "evidence"

export type ControlPlaneIntegrationStatus = {
  mode: ResolvedControlPlaneData["mode"]
  readyAreas: ControlPlaneIntegrationArea[]
  missingAreas: ControlPlaneIntegrationArea[]
  isEmptyShell: boolean
  isPartialShell: boolean
}

const EMPTY_TOTALS: Totals = {
  session_count: 0,
  stalled_count: 0,
  run_count: 0,
  blocked_run_count: 0,
  stalled_run_count: 0,
}

function getFixtureScenario(mode: Exclude<ControlPlaneDataMode, "auto" | "real">): ControlPlaneFixtureScenario {
  return mode === "smoke" ? SMOKE_SCENARIO : DEMO_SCENARIO
}

export function resolveControlPlaneMode(rawMode?: string): ControlPlaneDataMode {
  if (rawMode === "real" || rawMode === "demo" || rawMode === "smoke" || rawMode === "auto") {
    return rawMode
  }
  return "demo"
}

export function resolveControlPlaneData(args: {
  mode: ControlPlaneDataMode
  selectedRunId: string | null
  selectedSessionId: string | null
  artifactPath: string
  queryState: ControlPlaneQueryState
}): ResolvedControlPlaneData {
  const { mode, selectedRunId, selectedSessionId, artifactPath, queryState } = args
  const resolvedMode: Exclude<ControlPlaneDataMode, "auto"> =
    mode === "auto" ? "real" : mode

  if (resolvedMode === "real") {
    const runs = queryState.runs?.runs ?? []
    const sessions = queryState.sessions?.sessions ?? []
    const effectiveRunId = selectedRunId ?? runs[0]?.run_id
    const effectiveSessionId = selectedSessionId ?? sessions[0]?.session_id

    return {
      mode: "real",
      totals: queryState.activity?.totals ?? EMPTY_TOTALS,
      runs,
      sessions,
      activity: queryState.activity?.events ?? [],
      runDetail: queryState.runDetail,
      sessionUsage: queryState.sessionUsage,
      sessionMessages: queryState.sessionMessages?.messages,
      artifacts: queryState.artifacts,
      evidence: queryState.evidence,
      defaultRunId: effectiveRunId,
      defaultSessionId: effectiveSessionId,
      defaultArtifactPath: artifactPath || ".",
      defaultEvidenceQuery: "",
    }
  }

  const fixture = getFixtureScenario(resolvedMode)
  const runs = fixture.runs
  const sessions = fixture.sessions
  const activity = fixture.activity
  const totals = fixture.totals
  const effectiveRunId = selectedRunId ?? runs[0]?.run_id ?? fixture.defaultRunId
  const effectiveSessionId = selectedSessionId ?? sessions[0]?.session_id ?? fixture.defaultSessionId
  const effectiveArtifactPath = artifactPath || fixture.defaultArtifactPath

  return {
    mode: resolvedMode,
    totals,
    runs,
    sessions,
    activity,
    runDetail: effectiveRunId ? fixture.runDetails[effectiveRunId] : undefined,
    sessionUsage: effectiveSessionId ? fixture.sessionUsage[effectiveSessionId] : undefined,
    sessionMessages: effectiveSessionId ? fixture.sessionMessages[effectiveSessionId]?.messages : undefined,
    artifacts: fixture.artifacts[effectiveArtifactPath] ?? fixture.artifacts[fixture.defaultArtifactPath],
    evidence: effectiveRunId ? fixture.evidence[effectiveRunId] : undefined,
    defaultRunId: fixture.defaultRunId,
    defaultSessionId: fixture.defaultSessionId,
    defaultArtifactPath: fixture.defaultArtifactPath,
    defaultEvidenceQuery: fixture.defaultEvidenceQuery,
  }
}

export function getControlPlaneIntegrationStatus(args: {
  data: ResolvedControlPlaneData
  selectedRunId: string | null
  selectedSessionId: string | null
}) : ControlPlaneIntegrationStatus {
  const { data, selectedRunId, selectedSessionId } = args
  const readyAreas: ControlPlaneIntegrationArea[] = []
  const missingAreas: ControlPlaneIntegrationArea[] = []

  const markArea = (area: ControlPlaneIntegrationArea, ready: boolean) => {
    if (ready) {
      readyAreas.push(area)
      return
    }
    missingAreas.push(area)
  }

  markArea("runList", data.runs.length > 0)
  markArea("sessionList", data.sessions.length > 0)
  markArea("activity", data.activity.length > 0)
  markArea("runDetail", !selectedRunId || Boolean(data.runDetail))
  markArea("sessionUsage", !selectedSessionId || Boolean(data.sessionUsage))
  markArea("sessionMessages", !selectedSessionId || Boolean(data.sessionMessages?.length))
  markArea("artifacts", Boolean(data.artifacts?.entries?.length))
  markArea("evidence", Boolean(data.evidence?.records?.length || data.runDetail?.linked?.evidence_bundles?.length))

  const baseMissing = missingAreas.filter((area) =>
    area === "runList" || area === "sessionList" || area === "activity",
  )

  return {
    mode: data.mode,
    readyAreas,
    missingAreas,
    isEmptyShell: data.mode === "real" && baseMissing.length === 3,
    isPartialShell: data.mode === "real" && baseMissing.length > 0 && baseMissing.length < 3,
  }
}
