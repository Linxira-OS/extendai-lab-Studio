import { Alert, Tag } from "antd"
import type { ControlPlaneIntegrationArea, ControlPlaneIntegrationStatus, ResolvedControlPlaneData } from "../controlPlaneData"

export const INTEGRATION_AREA_LABELS: Record<ControlPlaneIntegrationArea, string> = {
  runList: "运行列表",
  sessionList: "OpenCode 会话",
  activity: "活动事件",
  runDetail: "run 详情",
  sessionUsage: "token 用量",
  sessionMessages: "会话消息",
  artifacts: "工件索引",
  evidence: "证据结果",
}

type IntegrationStatusSummaryProps = {
  sourceMode: ResolvedControlPlaneData["mode"]
  integrationStatus: ControlPlaneIntegrationStatus
}

export function IntegrationStatusSummary({ sourceMode, integrationStatus }: IntegrationStatusSummaryProps) {
  const visibleReadyAreas = integrationStatus.readyAreas.slice(0, 4)
  const visibleMissingAreas = integrationStatus.missingAreas.slice(0, 4)
  const totalAreas = integrationStatus.readyAreas.length + integrationStatus.missingAreas.length || 1
  const integrationCompletion = Math.round((integrationStatus.readyAreas.length / totalAreas) * 100)

  return (
    <div className="integration-summary-card">
      <div className="integration-summary-top">
        <div>
          <div className="panel-section-title">当前模式</div>
          <div className="panel-subtitle">前端壳层已经按 {sourceMode.toUpperCase()} 数据源运行。</div>
        </div>
        <Tag color={sourceMode === "real" ? "blue" : sourceMode === "smoke" ? "purple" : "green"}>{sourceMode}</Tag>
      </div>
      <div className="integration-progress-row">
        <strong>{integrationCompletion}%</strong>
        <span>integration coverage</span>
      </div>
      <div className="integration-chip-grid">
        {visibleReadyAreas.map((area) => (
          <span className="integration-chip integration-chip-ready" key={`ready-${area}`}>
            Ready · {INTEGRATION_AREA_LABELS[area]}
          </span>
        ))}
        {visibleMissingAreas.map((area) => (
          <span className="integration-chip integration-chip-missing" key={`missing-${area}`}>
            Gap · {INTEGRATION_AREA_LABELS[area]}
          </span>
        ))}
      </div>
      {integrationStatus.missingAreas.length > visibleMissingAreas.length ? (
        <div className="cp-overflow-note">另外 {integrationStatus.missingAreas.length - visibleMissingAreas.length} 个接入项已折叠到摘要视图。</div>
      ) : null}
    </div>
  )
}

type RealModeBannerProps = {
  loading: boolean
  errorMessage?: string
  integrationStatus: ControlPlaneIntegrationStatus
}

export function RealModeStatusBanner({ loading, errorMessage, integrationStatus }: RealModeBannerProps) {
  if (loading) {
    return (
      <Alert
        type="info"
        showIcon
        message="Real 模式已启用，正在等待正式后端数据。"
        description="当前页面只展示真实接口返回结果，适合联调正式后端与 OpenCode。"
      />
    )
  }

  if (errorMessage) {
    return <Alert type="error" showIcon message="Real 模式请求失败" description={errorMessage} />
  }

  if (integrationStatus.isEmptyShell) {
    return (
      <Alert
        type="warning"
        showIcon
        message="Real 模式当前没有可展示数据"
        description="这通常表示正式后端已连通，但当前还没有 run、session 或 activity。你可以切到 Demo 或 Smoke 继续检查界面布局。"
      />
    )
  }

  if (integrationStatus.isPartialShell) {
    const liveDataGaps = integrationStatus.missingAreas
      .filter((area) => area === "runList" || area === "sessionList" || area === "activity")
      .map((area) => INTEGRATION_AREA_LABELS[area])

    return (
      <Alert
        type="info"
        showIcon
        message="Real 模式为部分接入状态"
        description={`当前已经进入真实联调，但仍缺少 ${liveDataGaps.join("、")}。前端壳层会保留空位，等待正式后端和 OpenCode 补齐。`}
      />
    )
  }

  return null
}
