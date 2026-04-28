export type LoginResponse = {
  username: string
  role: string
  session_token: string
}

export type Totals = {
  session_count: number
  stalled_count: number
  run_count: number
  blocked_run_count: number
  stalled_run_count: number
}

export type SessionUsage = {
  session_id: string
  input_tokens: number
  output_tokens: number
  total_tokens: number
  cost: number
  message_count: number
  prompt_count: number
}

export type SessionInfo = {
  session_id: string
  title: string
  status: string
  message_count: number
  last_message_at: string
  stalled: boolean
  usage: SessionUsage
}

export type RunInfo = {
  run_id: string
  run_type: string
  title: string
  current_state: string
  created_at: string
  updated_at: string
  waiting_on: string
  owner: string
  last_heartbeat: string
  last_checkpoint: string
  failure_reason: string
  stalled: boolean
  stalled_reason: string
  metadata: Record<string, unknown>
}

export type ActivityEvent = {
  event_id: string
  session_id: string
  event_type: string
  timestamp: string
  payload: Record<string, unknown>
}

export type SessionMessagePart = {
  type?: string
  kind?: string
  event_type?: string
  eventType?: string
  tool_name?: string
  toolName?: string
  name?: string
  text?: string
  content?: string
  summary?: string
  reasoning?: string
  description?: string
  title?: string
  query?: string
  result?: string
  output?: string
  payload?: unknown
  arguments?: unknown
  input?: unknown
  parts?: SessionMessagePart[]
  [key: string]: unknown
}

export type SessionMessageUsage = {
  total_tokens?: number
  totalTokens?: number
  input_tokens?: number
  inputTokens?: number
  prompt_tokens?: number
  promptTokens?: number
  output_tokens?: number
  outputTokens?: number
  completion_tokens?: number
  completionTokens?: number
  [key: string]: unknown
}

export type SessionMessage = {
  role?: string
  createdAt?: string
  timestamp?: string
  parts?: SessionMessagePart[]
  content?: unknown
  text?: string
  usage?: SessionMessageUsage
  [key: string]: unknown
}

export type SessionMessagesResponse = {
  messages: SessionMessage[]
}

export type SessionUsageResponse = SessionUsage

export type RunDetailResponse = {
  run: RunInfo
  steps: RunStepInfo[]
  timeline: TimelineEntry[]
  current_step: Record<string, unknown> | null
  linked: RunLinkedPayload
  events: Array<Record<string, unknown>>
}

export type RunStepInfo = {
  step_id: string
  title: string
  state: string
  waiting_on?: string
  owner?: string
  last_checkpoint?: string
  last_heartbeat?: string
  failure_reason?: string
  stalled?: boolean
  stalled_reason?: string
}

export type TimelineEntry = {
  index: number
  event_id: string
  step_id: string
  event_type: string
  state_from: string
  state_to: string
  timestamp: string
  reason: string
  payload: Record<string, unknown>
}

export type ArtifactItem = {
  artifact_id: string
  path: string
  kind: string
  safe_action: string
  summary: Record<string, unknown>
}

export type LinkedEvidenceBundle = {
  bundle_id: string
  query: string
  run_id?: string
  step_id?: string
  records: EvidenceRecord[]
  summary?: Record<string, number>
  warnings?: string[]
}

export type RunLinkedPayload = {
  runtime_session_ids?: string[]
  evidence_bundle_ids?: string[]
  artifact_paths?: string[]
  evidence_bundles?: LinkedEvidenceBundle[]
  artifacts?: ArtifactItem[]
}

export type ActivityResponse = {
  sessions: SessionInfo[]
  runs: RunInfo[]
  events: ActivityEvent[]
  totals: Totals
}

export type ArtifactsResponse = {
  path: string
  entries: Array<Record<string, unknown>>
}

export type EvidenceRecord = {
  evidence_id: string
  title: string
  provider: string
  source_class: string
  admissibility: string
  admissibility_reason: string
  year?: number
  url?: string
  authors?: string[]
  doi?: string
  pmid?: string
  arxiv_id?: string
  license?: string
  confidence?: number
  normalized_abstract?: string
  raw_snippet?: string
}

export type EvidenceSearchResponse = {
  bundle_id: string
  query: string
  run_id?: string
  records: EvidenceRecord[]
  summary?: Record<string, number>
  warnings?: string[]
}

export async function requestJson<T>(path: string, token?: string, init?: RequestInit): Promise<T> {
  const headers = new Headers(init?.headers ?? {})
  if (!headers.has("Content-Type") && init?.body) {
    headers.set("Content-Type", "application/json")
  }
  if (token) {
    headers.set("Authorization", `Bearer ${token}`)
  }

  const response = await fetch(path, { ...init, headers })
  const payload = await response.json()
  if (!response.ok) {
    throw new Error(payload.error || `HTTP ${response.status}`)
  }
  return payload as T
}

export function login(username: string, password: string) {
  return requestJson<LoginResponse>("/api/auth/login", undefined, {
    method: "POST",
    body: JSON.stringify({ username, password }),
  })
}

export const getSessions = (token: string) => requestJson<{ sessions: SessionInfo[] }>("/api/sessions", token)
export const getRuns = (token: string) => requestJson<{ runs: RunInfo[] }>("/api/runs", token)
export const getActivity = (token: string) => requestJson<ActivityResponse>("/api/dashboard/activity?limit=10&timeout_ms=200", token)
export const getRun = (token: string, runId: string) => requestJson<RunDetailResponse>(`/api/runs/${runId}`, token)
export const getSessionUsage = (token: string, sessionId: string) => requestJson<SessionUsageResponse>(`/api/sessions/${sessionId}/usage`, token)
export const getSessionMessages = (token: string, sessionId: string) => requestJson<SessionMessagesResponse>(`/api/sessions/${sessionId}/messages`, token)
export const getArtifacts = (token: string, pathValue: string) => requestJson<ArtifactsResponse>(`/api/artifacts?path=${encodeURIComponent(pathValue)}`, token)
export const searchEvidence = (token: string, query: string, limit: number, runId?: string | null) =>
  requestJson<EvidenceSearchResponse>("/api/evidence/search", token, {
    method: "POST",
    body: JSON.stringify({ query, limit, run_id: runId ?? null }),
  })
