import { Card, Col, Row, Space, Tag, Typography } from "antd"
import { Suspense, lazy } from "react"
import type { RunInfo, SessionInfo, Totals } from "../api"
import type { ControlPlaneIntegrationStatus, ResolvedControlPlaneData } from "../controlPlaneData"
import { IntegrationStatusSummary } from "./controlPlaneStatus"

const { Text } = Typography
const ReactECharts = lazy(async () => {
  const module = await import("echarts-for-react")
  return { default: module.default }
})

function ChartFallback() {
  return <div className="chart-loading">Loading chart...</div>
}

function compactText(value: string, maxLength: number) {
  return value.length > maxLength ? `${value.slice(0, maxLength - 3)}...` : value
}

type DashboardOverviewProps = {
  totals: Totals
  runs: RunInfo[]
  sessions: SessionInfo[]
  sourceMode: ResolvedControlPlaneData["mode"]
  integrationStatus: ControlPlaneIntegrationStatus
}

export function DashboardOverview({ totals, runs, sessions, sourceMode, integrationStatus }: DashboardOverviewProps) {
  const activeRuns = runs.filter((item) => !["completed", "failed", "aborted"].includes(item.current_state))
  const activeSessions = sessions.filter((item) => item.status !== "completed")
  const stalledRatio = totals.run_count ? Math.round((totals.stalled_run_count / totals.run_count) * 100) : 0
  const blockedRatio = totals.run_count ? Math.round((totals.blocked_run_count / totals.run_count) * 100) : 0
  const runHealth = Math.max(100 - stalledRatio - Math.round(blockedRatio / 2), 0)

  const kpiOption = {
    backgroundColor: "transparent",
    tooltip: { trigger: "axis" },
    xAxis: { type: "category", data: ["会话", "停滞会话", "运行", "阻塞", "停滞运行"] },
    yAxis: { type: "value" },
    series: [{
      type: "bar",
      data: [totals.session_count, totals.stalled_count, totals.run_count, totals.blocked_run_count, totals.stalled_run_count],
      itemStyle: { borderRadius: [8, 8, 0, 0], color: "#3b82f6" },
    }],
    grid: { left: 32, right: 12, top: 30, bottom: 24 },
  }

  const completed = runs.filter((item) => item.current_state === "completed").length
  const blocked = runs.filter((item) => item.current_state === "blocked_policy").length
  const failed = runs.filter((item) => item.current_state === "failed").length
  const others = Math.max(runs.length - completed - blocked - failed, 0)

  const runStateOption = {
    tooltip: { trigger: "item" },
    series: [{
      type: "pie",
      radius: [46, 86],
      label: { color: "#dbeafe" },
      data: [
        { value: completed, name: "完成" },
        { value: blocked, name: "阻塞" },
        { value: failed, name: "失败" },
        { value: others, name: "其他" },
      ],
    }],
  }

  const highlightRuns = runs.slice(0, 5)
  const hotSessions = sessions.slice(0, 5)
  const blockedRuns = runs.filter((item) => item.current_state === "blocked_policy").slice(0, 3)
  const stalledRuns = runs.filter((item) => item.stalled).slice(0, 3)
  const completedRatio = totals.run_count ? Math.round((completed / totals.run_count) * 100) : 0
  const attentionItems = [
    ...blockedRuns.map((run) => ({
      key: `blocked-${run.run_id}`,
      lane: "阻塞处理",
      title: run.title,
      meta: compactText(run.waiting_on || "等待审批/依赖", 88),
      toneClass: "dashboard-attention-card-danger",
      toneText: run.current_state,
    })),
    ...stalledRuns.map((run) => ({
      key: `stalled-${run.run_id}`,
      lane: "停滞处理",
      title: run.title,
      meta: compactText(run.stalled_reason || "长时间无心跳", 88),
      toneClass: "dashboard-attention-card-warning",
      toneText: "stalled",
    })),
  ].slice(0, 5)
  const hotspotItems = [
    ...highlightRuns.map((run) => ({
      key: `run-${run.run_id}`,
      title: compactText(run.title, 78),
      status: run.current_state,
      color: run.current_state === "completed" ? "green" : run.current_state === "blocked_policy" ? "orange" : run.current_state === "failed" ? "red" : "blue",
      meta: `Run · ${run.run_id}`,
    })),
    ...hotSessions.map((session) => ({
      key: `session-${session.session_id}`,
      title: compactText(session.title, 72),
      status: session.status,
      color: "blue",
      meta: `Session · Token ${session.usage?.total_tokens ?? 0} · 消息 ${session.message_count}`,
    })),
  ].slice(0, 6)
  const metricItems = [
    { label: "运行热度", value: activeRuns.length, helper: "Active runs", toneClass: "" },
    { label: "会话负载", value: activeSessions.length, helper: "Active sessions", toneClass: "" },
    { label: "策略阻塞", value: totals.blocked_run_count, helper: "Policy blocked", toneClass: "dashboard-metric-tile-danger" },
    { label: "运行停滞", value: totals.stalled_run_count, helper: "Stalled runs", toneClass: "dashboard-metric-tile-warning" },
    { label: "完成率", value: `${completedRatio}%`, helper: "Completed", toneClass: "dashboard-metric-tile-success" },
    { label: "系统健康", value: `${runHealth}%`, helper: "Overall health", toneClass: "dashboard-metric-tile-accent" },
  ]

  const matrixSummary = [
    {
      label: "会话总量",
      value: totals.session_count,
      helper: `${activeSessions.length} active`,
    },
    {
      label: "阻塞占比",
      value: `${blockedRatio}%`,
      helper: `${totals.blocked_run_count} blocked`,
    },
    {
      label: "停滞占比",
      value: `${stalledRatio}%`,
      helper: `${totals.stalled_run_count} stalled`,
    },
    {
      label: "完成运行",
      value: completed,
      helper: `${completedRatio}% closed`,
    },
  ]

  return (
    <Space direction="vertical" size={14} style={{ width: "100%" }}>
      <Card className="cp-card cp-card-dense dashboard-metric-strip" bordered={false}>
        <div className="dashboard-metric-grid dashboard-metric-grid-compact">
          {metricItems.map((item) => (
            <div className={`dashboard-metric-tile ${item.toneClass}`.trim()} key={item.label}>
              <span>{item.label}</span>
              <div className="dashboard-metric-value-row">
                <strong>{item.value}</strong>
                <small>{item.helper}</small>
              </div>
            </div>
          ))}
        </div>
      </Card>

      <Row gutter={[10, 10]}>
        <Col xs={24} xl={15}>
          <Card className="cp-card cp-card-dense dashboard-matrix-card" bordered={false}>
            <div className="dashboard-matrix-surface">
              <div className="dashboard-surface-header">
                <div>
                  <Text className="panel-section-title">研究态势矩阵</Text>
                  <div className="dashboard-surface-subtitle">Primary monitoring wall</div>
                </div>
                <Text type="secondary">Wall</Text>
              </div>
              <div className="dashboard-matrix-topline">
                {matrixSummary.map((item) => (
                  <div className="dashboard-matrix-topline-item" key={item.label}>
                    <span>{item.label}</span>
                    <strong>{item.value}</strong>
                    <small>{item.helper}</small>
                  </div>
                ))}
              </div>
              <div className="dashboard-matrix-layout">
              <div className="dashboard-matrix-main">
                <div className="chart-shell chart-shell-large dashboard-chart-shell dashboard-chart-shell-main">
                  <div className="dashboard-chart-title-row">
                    <Text className="panel-section-title">运行 / 会话总体热度</Text>
                    <Text type="secondary">Live balance</Text>
                  </div>
                  <Suspense fallback={<ChartFallback />}>
                    <ReactECharts option={kpiOption} style={{ height: 274 }} />
                  </Suspense>
                </div>
              </div>
              <div className="dashboard-matrix-side">
                <div className="chart-shell chart-shell-large dashboard-chart-shell dashboard-chart-shell-side">
                  <div className="dashboard-chart-title-row">
                    <Text className="panel-section-title">运行状态分布</Text>
                    <Text type="secondary">Outcome mix</Text>
                  </div>
                  <Suspense fallback={<ChartFallback />}>
                    <ReactECharts option={runStateOption} style={{ height: 206 }} />
                  </Suspense>
                </div>
                <div className="dashboard-matrix-summary-grid">
                  {matrixSummary.slice(0, 2).map((item) => (
                    <div className="dashboard-matrix-summary-card" key={item.label}>
                      <span>{item.label}</span>
                      <strong>{item.value}</strong>
                      <small>{item.helper}</small>
                    </div>
                  ))}
                </div>
              </div>
            </div>
            </div>
          </Card>
        </Col>

        <Col xs={24} xl={9}>
          <Space direction="vertical" size={10} style={{ width: "100%" }} className="dashboard-sidebar-stack">
            <Card className="cp-card cp-card-dense dashboard-rail-card" title="控制侧栏">
              <Space direction="vertical" style={{ width: "100%" }} size={12}>
                <div className="dashboard-hotspot-header dashboard-rail-section-header">
                  <Text className="panel-section-title">接入状态</Text>
                  <Text type="secondary">Mode + Coverage</Text>
                </div>
                <div className="dashboard-rail-status-block">
                  <IntegrationStatusSummary sourceMode={sourceMode} integrationStatus={integrationStatus} />
                </div>
                <div className="dashboard-hotspot-header dashboard-rail-section-header">
                  <Text className="panel-section-title">统一热点流</Text>
                  <Text type="secondary">Run + Session</Text>
                </div>
                <div className="compact-feed dashboard-section-feed">
                  {hotspotItems.length ? hotspotItems.map((item) => (
                    <div className="compact-feed-item dashboard-feed-item" key={item.key}>
                      <div className="dashboard-feed-header">
                        <strong className="cp-line-clamp-2">{item.title}</strong>
                        <Tag color={item.color} style={{ margin: 0 }}>{item.status}</Tag>
                      </div>
                      <div className="dashboard-feed-meta">{item.meta}</div>
                    </div>
                  )) : <div className="empty-inline">暂无运行和会话热点</div>}
                </div>
                <div className="dashboard-hotspot-header dashboard-rail-section-header dashboard-rail-divider">
                  <Text className="panel-section-title">优先处理</Text>
                  <Text type="secondary">Blocked + Stalled</Text>
                </div>
                <div className="priority-lane dashboard-attention-lane">
                  {attentionItems.length ? attentionItems.map((item) => (
                    <div className={`priority-card dashboard-attention-card ${item.toneClass}`} key={item.key}>
                      <div className="dashboard-attention-top">
                        <span className="dashboard-attention-lane-label">{item.lane}</span>
                        <span className="dashboard-feed-meta">{item.toneText}</span>
                      </div>
                      <strong className="cp-line-clamp-2">{item.title}</strong>
                      <span className="cp-line-clamp-2">{item.meta}</span>
                    </div>
                  )) : <div className="empty-inline">当前没有需要优先处理的阻塞或停滞 run</div>}
                </div>
              </Space>
            </Card>
          </Space>
        </Col>
      </Row>
    </Space>
  )
}
