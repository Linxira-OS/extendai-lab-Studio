import { Suspense, lazy, useEffect, useState } from "react"
import { Dropdown, Select } from "antd"
import { DownOutlined } from "@ant-design/icons"
import { RealModeStatusBanner } from "./components/controlPlaneStatus"
import { useTheme, ThemeMode } from "./components/ThemeProvider"
import { useMutation, useQuery } from "@tanstack/react-query"
import {
  getActivity,
  getArtifacts,
  getRun,
  getRuns,
  getSessionMessages,
  getSessionUsage,
  getSessions,
  login,
  searchEvidence,
  type ActivityResponse,
  type ArtifactsResponse,
  type RunDetailResponse,
  type RunInfo,
  type SessionInfo,
  type SessionMessagesResponse,
  type SessionUsageResponse,
} from "./api"
import {
  getControlPlaneIntegrationStatus,
  type ControlPlaneDataMode,
  resolveControlPlaneData,
  resolveControlPlaneMode,
} from "./controlPlaneData"

const DashboardOverview = lazy(async () => {
  const module = await import("./components/DashboardOverview")
  return { default: module.DashboardOverview }
})

const LoginScreen = lazy(async () => {
  const module = await import("./components/LoginScreen")
  return { default: module.LoginScreen }
})

const WorkbenchView = lazy(async () => {
  const module = await import("./components/WorkbenchView")
  return { default: module.WorkbenchView }
})

function useAuthedQuery<T>(key: unknown[], token: string | null, queryFn: () => Promise<T>, enabled = true) {
  return useQuery({ queryKey: key, queryFn, enabled: Boolean(token) && enabled, refetchInterval: 5000 })
}

type ViewKey = "dashboard" | "workbench"

function ScreenFallback() {
  return (
    <div className="cp-screen-fallback">
      <div className="cp-screen-fallback-bar" />
      <div className="cp-screen-fallback-grid">
        <div className="cp-screen-fallback-card" />
        <div className="cp-screen-fallback-card" />
        <div className="cp-screen-fallback-card" />
      </div>
    </div>
  )
}

type NoticeState = {
  type: "success" | "error"
  text: string
} | null

type AppDataMode = Exclude<ControlPlaneDataMode, "auto">

function getInitialDataMode(): AppDataMode {
  const envMode = resolveControlPlaneMode(import.meta.env.VITE_CONTROL_PLANE_DATA_MODE)
  const normalizedEnvMode = envMode === "auto" ? "real" : envMode
  if (typeof window === "undefined") {
    return normalizedEnvMode
  }

  const savedMode = window.localStorage.getItem("abris-control-plane-data-mode")
  if (savedMode === "real" || savedMode === "demo" || savedMode === "smoke") {
    return savedMode
  }

  return normalizedEnvMode
}

export default function App() {
  const { mode, setMode } = useTheme()
  const [dataMode, setDataMode] = useState<AppDataMode>(getInitialDataMode)
  const liveDataEnabled = dataMode === "real"
  const [token, setToken] = useState<string | null>(null)
  const [identity, setIdentity] = useState<{ username: string; role: string } | null>(null)
  const [currentView, setCurrentView] = useState<ViewKey>("dashboard")
  const [selectedRunId, setSelectedRunId] = useState<string | null>(null)
  const [selectedSessionId, setSelectedSessionId] = useState<string | null>(null)
  const [artifactPath, setArtifactPath] = useState(".")
  const [evidenceQuery, setEvidenceQuery] = useState("")
  const [evidenceLimit, setEvidenceLimit] = useState(5)
  const [notice, setNotice] = useState<NoticeState>(null)

  const loginMutation = useMutation({
    mutationFn: ({ username, password }: { username: string; password: string }) => login(username, password),
    onSuccess: (payload) => {
      setToken(payload.session_token)
      setIdentity({ username: payload.username, role: payload.role })
      setNotice({ type: "success", text: "登录成功，已进入研究控制台。" })
    },
    onError: (error) => {
      setNotice({ type: "error", text: (error as Error).message })
    },
  })

  const sessionsQuery = useAuthedQuery<{ sessions: SessionInfo[] }>(["sessions", token], token, () => getSessions(token!), liveDataEnabled)
  const runsQuery = useAuthedQuery<{ runs: RunInfo[] }>(["runs", token], token, () => getRuns(token!), liveDataEnabled)
  const activityQuery = useAuthedQuery<ActivityResponse>(["activity", token], token, () => getActivity(token!), liveDataEnabled)
  const runDetailQuery = useAuthedQuery<RunDetailResponse>(["run", token, selectedRunId], token, () => getRun(token!, selectedRunId!), liveDataEnabled && Boolean(selectedRunId))
  const sessionUsageQuery = useAuthedQuery<SessionUsageResponse>(["sessionUsage", token, selectedSessionId], token, () => getSessionUsage(token!, selectedSessionId!), liveDataEnabled && Boolean(selectedSessionId))
  const sessionMessagesQuery = useAuthedQuery<SessionMessagesResponse>(["sessionMessages", token, selectedSessionId], token, () => getSessionMessages(token!, selectedSessionId!), liveDataEnabled && Boolean(selectedSessionId))
  const artifactsQuery = useAuthedQuery<ArtifactsResponse>(["artifacts", token, artifactPath], token, () => getArtifacts(token!, artifactPath), liveDataEnabled)

  const evidenceMutation = useMutation({
    mutationFn: () => searchEvidence(token!, evidenceQuery, evidenceLimit, selectedRunId),
    onSuccess: (payload) => {
      setNotice({ type: "success", text: "证据检索完成。" })
      if (payload.run_id) {
        setSelectedRunId(payload.run_id)
      }
      if (liveDataEnabled) {
        runsQuery.refetch()
        activityQuery.refetch()
      }
      if (liveDataEnabled && payload.run_id) {
        runDetailQuery.refetch()
      }
    },
    onError: (error) => {
      setNotice({ type: "error", text: (error as Error).message })
    },
  })

  useEffect(() => {
    if (!notice) {
      return undefined
    }
    const timeout = window.setTimeout(() => setNotice(null), 2600)
    return () => window.clearTimeout(timeout)
  }, [notice])

  useEffect(() => {
    window.localStorage.setItem("abris-control-plane-data-mode", dataMode)
  }, [dataMode])

  useEffect(() => {
    setSelectedRunId(null)
    setSelectedSessionId(null)
    setArtifactPath(".")
    setEvidenceQuery("")
  }, [dataMode])

  const controlPlane = resolveControlPlaneData({
    mode: dataMode,
    selectedRunId,
    selectedSessionId,
    artifactPath,
    queryState: {
      runs: runsQuery.data,
      sessions: sessionsQuery.data,
      activity: activityQuery.data,
      runDetail: runDetailQuery.data,
      sessionUsage: sessionUsageQuery.data,
      sessionMessages: sessionMessagesQuery.data,
      artifacts: artifactsQuery.data,
      evidence: evidenceMutation.data,
    },
  })

  const integrationStatus = getControlPlaneIntegrationStatus({
    data: controlPlane,
    selectedRunId,
    selectedSessionId,
  })

  useEffect(() => {
    const runs = controlPlane.runs
    if (!runs.length) {
      if (selectedRunId) {
        setSelectedRunId(null)
      }
      return
    }

    if (!selectedRunId || !runs.some((run) => run.run_id === selectedRunId)) {
      setSelectedRunId(controlPlane.defaultRunId ?? runs[0].run_id)
    }
  }, [controlPlane.defaultRunId, controlPlane.runs, selectedRunId])

  useEffect(() => {
    const sessions = controlPlane.sessions
    if (!sessions.length) {
      if (selectedSessionId) {
        setSelectedSessionId(null)
      }
      return
    }

    if (!selectedSessionId || !sessions.some((session) => session.session_id === selectedSessionId)) {
      setSelectedSessionId(controlPlane.defaultSessionId ?? sessions[0].session_id)
    }
  }, [controlPlane.defaultSessionId, controlPlane.sessions, selectedSessionId])

  useEffect(() => {
    if (!evidenceQuery && controlPlane.defaultEvidenceQuery) {
      setEvidenceQuery(controlPlane.defaultEvidenceQuery)
    }
  }, [controlPlane.defaultEvidenceQuery, evidenceQuery])

  useEffect(() => {
    if (artifactPath === "." && controlPlane.defaultArtifactPath !== ".") {
      setArtifactPath(controlPlane.defaultArtifactPath)
    }
  }, [artifactPath, controlPlane.defaultArtifactPath])

  const liveLoading =
    sessionsQuery.isLoading ||
    runsQuery.isLoading ||
    activityQuery.isLoading ||
    runDetailQuery.isLoading ||
    sessionUsageQuery.isLoading ||
    sessionMessagesQuery.isLoading ||
    artifactsQuery.isLoading

  const liveError =
    sessionsQuery.error ??
    runsQuery.error ??
    activityQuery.error ??
    runDetailQuery.error ??
    sessionUsageQuery.error ??
    sessionMessagesQuery.error ??
    artifactsQuery.error

  if (!token) {
    return (
      <Suspense fallback={<ScreenFallback />}>
        <LoginScreen
          loading={loginMutation.isPending}
          errorMessage={loginMutation.error ? (loginMutation.error as Error).message : undefined}
          onSubmit={(values) => loginMutation.mutate(values)}
        />
      </Suspense>
    )
  }

  return (
    <div className="cp-layout cp-layout-shell">
      <aside className="cp-sider cp-sider-lite">
        <div className="cp-sider-logo">A</div>
        <div className="cp-sider-brand">
          <strong>ABRIS</strong>
          <span style={{ color: "var(--text-soft)" }}>Research OS</span>
        </div>
        <nav className="cp-sider-nav">
          <button className={`cp-nav-button ${currentView === "dashboard" ? "active" : ""}`} onClick={() => setCurrentView("dashboard")}>
            <span className="cp-nav-glyph">◫</span>
            <span>Dashboard</span>
          </button>
          <button className={`cp-nav-button ${currentView === "workbench" ? "active" : ""}`} onClick={() => setCurrentView("workbench")}>
            <span className="cp-nav-glyph">▣</span>
            <span>Workbench</span>
          </button>
        </nav>
      </aside>

      <div className="cp-main-shell">
        <header className="cp-header cp-header-compact cp-topbar">
          <div className="cp-topbar-left">
            <div className="cp-topbar-title-group">
              <span className="cp-topbar-kicker" style={{ color: "var(--text-soft)", fontSize: "12px", textTransform: "uppercase", letterSpacing: "0.05em" }}>Command Center</span>
              <h1 className="cp-title cp-title-compact" style={{ margin: 0, fontSize: "16px", fontWeight: 600 }}>{currentView === "dashboard" ? "Overview" : "Operations Workbench"}</h1>
            </div>
          </div>
          <div className="cp-topbar-right" style={{ display: "flex", gap: "24px", alignItems: "center" }}>
            <div className="cp-header-metrics" style={{ display: "flex", gap: "16px", fontSize: "13px" }}>
              <div style={{ display: "flex", gap: "6px" }}><span style={{ color: "var(--text-soft)" }}>Runs</span><strong style={{ color: "var(--text-main)" }}>{controlPlane.totals.run_count}</strong></div>
              <div style={{ display: "flex", gap: "6px" }}><span style={{ color: "var(--text-soft)" }}>Blocked</span><strong style={{ color: "var(--danger)" }}>{controlPlane.totals.blocked_run_count}</strong></div>
              <div style={{ display: "flex", gap: "6px" }}><span style={{ color: "var(--text-soft)" }}>Stalled</span><strong style={{ color: "var(--warning)" }}>{controlPlane.totals.stalled_run_count}</strong></div>
            </div>
            <div style={{ width: "1px", height: "16px", background: "var(--border-soft)" }}></div>
            
            <Dropdown menu={{
              items: [
                { key: 'system', label: '跟随系统 (System)' },
                { key: 'time', label: '跟随时间 (Time)' },
                { key: 'light', label: '亮色 (Light)' },
                { key: 'dark', label: '暗色 (Dark)' }
              ],
              onClick: (e) => setMode(e.key as ThemeMode)
            }}>
              <a onClick={(e) => e.preventDefault()} style={{ color: 'var(--text-soft)', cursor: 'pointer', fontSize: '13px' }}>
                Theme: {mode} <DownOutlined />
              </a>
            </Dropdown>

            <Select
              size="small"
              value={dataMode}
              onChange={(value) => setDataMode(value)}
              style={{ minWidth: "140px" }}
              options={[
                { value: "real", label: "Data: Real" },
                { value: "demo", label: "Data: Demo" },
                { value: "smoke", label: "Data: Smoke" },
              ]}
            />

            <span className="cp-identity-pill" style={{ color: "var(--text-main)", fontSize: "13px" }}>{identity ? `${identity.username} (${identity.role})` : "未登录"}</span>
          </div>
        </header>

        {notice ? <div className={`cp-notice cp-notice-${notice.type}`}>{notice.text}</div> : null}

        {liveDataEnabled ? (
          <div className="cp-banner-wrap">
            <RealModeStatusBanner
              loading={liveLoading}
              errorMessage={liveError ? (liveError as Error).message : undefined}
              integrationStatus={integrationStatus}
            />
          </div>
        ) : null}

        <main className="cp-content">
          <Suspense fallback={<ScreenFallback />}>
            {currentView === "dashboard" ? (
              <DashboardOverview
                totals={controlPlane.totals}
                runs={controlPlane.runs}
                sessions={controlPlane.sessions}
                sourceMode={controlPlane.mode}
                integrationStatus={integrationStatus}
              />
            ) : (
              <WorkbenchView
                runs={controlPlane.runs}
                sessions={controlPlane.sessions}
                activity={controlPlane.activity}
                sourceMode={controlPlane.mode}
                liveDataEnabled={liveDataEnabled}
                integrationStatus={integrationStatus}
                selectedRunId={selectedRunId}
                selectedSessionId={selectedSessionId}
                runDetail={controlPlane.runDetail}
                sessionUsage={controlPlane.sessionUsage}
                sessionMessages={controlPlane.sessionMessages}
                artifacts={controlPlane.artifacts}
                evidenceResult={controlPlane.evidence}
                evidenceQuery={evidenceQuery}
                evidenceLimit={evidenceLimit}
                artifactPath={artifactPath}
                evidenceLoading={evidenceMutation.isPending}
                onSelectRun={setSelectedRunId}
                onSelectSession={setSelectedSessionId}
                onArtifactPathChange={setArtifactPath}
                onEvidenceQueryChange={setEvidenceQuery}
                onEvidenceLimitChange={setEvidenceLimit}
                onRefreshArtifacts={() => {
                  if (liveDataEnabled) {
                    artifactsQuery.refetch()
                  }
                }}
                onSearchEvidence={() => {
                  if (liveDataEnabled) {
                    evidenceMutation.mutate()
                    return
                  }
                  setNotice({ type: "success", text: `${controlPlane.mode.toUpperCase()} 模式使用固定演示数据。` })
                }}
              />
            )}
          </Suspense>
        </main>
      </div>
    </div>
  )
}
