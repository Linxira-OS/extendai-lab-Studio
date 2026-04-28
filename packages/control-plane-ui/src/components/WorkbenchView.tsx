import {
  Alert,
  Button,
  Card,
  Col,
  Descriptions,
  Empty,
  Input,
  InputNumber,
  List,
  Progress,
  Row,
  Space,
  Table,
  Tabs,
  Tag,
  Timeline,
  Tree,
} from "antd"
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
  SessionUsageResponse,
  TimelineEntry,
} from "../api"
import type { ControlPlaneIntegrationArea, ControlPlaneIntegrationStatus } from "../controlPlaneData"
import { buildMessagePreview } from "../opencodeMessagePreview"

type WorkbenchViewProps = {
  runs: RunInfo[]
  sessions: SessionInfo[]
  activity: ActivityEvent[]
  sourceMode: "real" | "demo" | "smoke"
  liveDataEnabled: boolean
  integrationStatus: ControlPlaneIntegrationStatus
  selectedRunId: string | null
  selectedSessionId: string | null
  runDetail?: RunDetailResponse
  sessionUsage?: SessionUsageResponse
  sessionMessages?: SessionMessage[]
  artifacts?: ArtifactsResponse
  evidenceResult?: EvidenceSearchResponse
  evidenceQuery: string
  evidenceLimit: number
  artifactPath: string
  evidenceLoading: boolean
  onSelectRun: (runId: string) => void
  onSelectSession: (sessionId: string) => void
  onArtifactPathChange: (value: string) => void
  onEvidenceQueryChange: (value: string) => void
  onEvidenceLimitChange: (value: number) => void
  onRefreshArtifacts: () => void
  onSearchEvidence: () => void
}

type EmptyStateKind =
  | "runQueue"
  | "sessionQueue"
  | "runDetail"
  | "usage"
  | "messages"
  | "evidence"
  | "artifacts"
  | "activity"

function stateColor(state: string) {
  if (state === "completed") return "green"
  if (state === "blocked_policy") return "orange"
  if (state === "failed") return "red"
  return "blue"
}

function formatTimestamp(value?: string) {
  if (!value) return "-"
  const date = new Date(value)
  if (Number.isNaN(date.getTime())) return value
  return date.toLocaleString("zh-CN", { hour12: false })
}

function compactText(value: string, maxLength: number) {
  return value.length > maxLength ? `${value.slice(0, maxLength - 3)}...` : value
}

function compactLinkLabel(value?: string) {
  if (!value) return "无链接"
  try {
    const url = new URL(value)
    return compactText(`${url.hostname}${url.pathname}`, 52)
  } catch {
    return compactText(value, 52)
  }
}

function limitWithSelection<T>(items: T[], limit: number, getKey: (item: T) => string, selectedKey?: string | null) {
  const visible = items.slice(0, limit)
  if (!selectedKey || visible.some((item) => getKey(item) === selectedKey)) {
    return visible
  }

  const selectedItem = items.find((item) => getKey(item) === selectedKey)
  if (!selectedItem) {
    return visible
  }

  return [...visible.slice(0, Math.max(limit - 1, 0)), selectedItem]
}

function summarizeActivity(event: ActivityEvent) {
  const payload = event.payload ?? {}
  const reason = typeof payload.reason === "string" ? payload.reason : ""
  const state = typeof payload.state_to === "string" ? payload.state_to : typeof payload.state === "string" ? payload.state : ""
  if (reason && state) return compactText(`${state} · ${reason}`, 120)
  if (reason) return compactText(reason, 120)
  if (state) return compactText(state, 120)
  return compactText(`session=${event.session_id || "-"}`, 120)
}

function emptyStateDescription(kind: EmptyStateKind, options: {
  sourceMode: WorkbenchViewProps["sourceMode"]
  liveDataEnabled: boolean
  selectedRunId: string | null
  selectedSessionId: string | null
}) {
  const { sourceMode, liveDataEnabled, selectedRunId, selectedSessionId } = options

  if (!liveDataEnabled) {
    switch (kind) {
      case "runQueue":
        return `当前 ${sourceMode.toUpperCase()} 场景未提供更多 run。`
      case "sessionQueue":
        return `当前 ${sourceMode.toUpperCase()} 场景未提供更多会话。`
      case "runDetail":
        return "选择场景 run 后显示步骤、时间线和阻塞原因。"
      case "usage":
        return "选择场景会话后显示 token 用量。"
      case "messages":
        return "当前场景暂无更多会话消息。"
      case "evidence":
        return "当前场景暂无更多证据记录。"
      case "artifacts":
        return "当前场景路径下暂无工件。"
      case "activity":
        return "当前场景暂无活动流。"
    }
  }

  switch (kind) {
    case "runQueue":
      return "正式后端尚未返回 run 列表，可先检查 RunLedger 与 /api/runs。"
    case "sessionQueue":
      return "OpenCode 运行时尚未返回会话列表，可先检查 bridge 与 /api/sessions。"
    case "runDetail":
      return selectedRunId
        ? "已选择 run，但详情接口尚未返回步骤和时间线。"
        : "选择真实 run 后显示步骤、时间线和阻塞原因。"
    case "usage":
      return selectedSessionId
        ? "该会话的 token 用量尚未返回。"
        : "选择真实会话后显示 token 用量。"
    case "messages":
      return selectedSessionId
        ? "该会话的消息流尚未返回，可继续检查 OpenCode message 接口。"
        : "选择真实会话后显示消息历史。"
    case "evidence":
      return selectedRunId
        ? "当前 run 尚未生成 evidence bundle，或正式证据检索链路尚未接入。"
        : "选择真实 run 后显示 evidence bundle。"
    case "artifacts":
      return "当前路径暂无工件，或 artifact 浏览接口尚未输出数据。"
    case "activity":
      return "事件订阅尚未返回活动流，可检查 OpenCode event bridge。"
  }
}

const integrationAreaLabels: Record<ControlPlaneIntegrationArea, string> = {
  runList: "run 列表",
  sessionList: "OpenCode 会话",
  activity: "活动事件",
  runDetail: "run 详情",
  sessionUsage: "token 用量",
  sessionMessages: "会话消息",
  artifacts: "工件索引",
  evidence: "证据结果",
}

function renderUsagePanel(sessionUsage?: SessionUsageResponse, emptyDescription = "选择会话后显示用量") {
  if (!sessionUsage) return <Empty description={emptyDescription} image={Empty.PRESENTED_IMAGE_SIMPLE} />
  const tokenPercent = sessionUsage.total_tokens > 0 ? Math.min(Math.round((sessionUsage.output_tokens / sessionUsage.total_tokens) * 100), 100) : 0
  return (
    <div className="usage-panel">
      <div className="usage-grid">
        <div className="usage-metric">
          <span>总 Token</span>
          <strong>{sessionUsage.total_tokens}</strong>
        </div>
        <div className="usage-metric">
          <span>输入</span>
          <strong>{sessionUsage.input_tokens}</strong>
        </div>
        <div className="usage-metric">
          <span>输出</span>
          <strong>{sessionUsage.output_tokens}</strong>
        </div>
        <div className="usage-metric">
          <span>成本</span>
          <strong>{sessionUsage.cost ?? 0}</strong>
        </div>
      </div>
      <Descriptions size="small" column={1} className="cp-descriptions usage-descriptions">
        <Descriptions.Item label="消息数">{sessionUsage.message_count}</Descriptions.Item>
        <Descriptions.Item label="Prompt 数">{sessionUsage.prompt_count}</Descriptions.Item>
        <Descriptions.Item label="输出占比">
          <Progress percent={tokenPercent} size="small" status="active" />
        </Descriptions.Item>
      </Descriptions>
    </div>
  )
}

function renderMessageHistory(messages?: SessionMessage[], emptyDescription = "暂无消息历史") {
  if (!messages?.length) return <Empty description={emptyDescription} image={Empty.PRESENTED_IMAGE_SIMPLE} />
  const visibleMessages = messages.slice(0, 6)
  return (
    <div className="message-history">
      {visibleMessages.map((message, index) => {
        const preview = buildMessagePreview(message)
        return (
          <div className="message-card" key={`${message.createdAt || message.timestamp || "msg"}-${index}`}>
            <div className="message-card-top">
              <Tag color={message.role === "assistant" ? "blue" : message.role === "user" ? "gold" : message.role === "tool" ? "purple" : "default"}>{message.role || "unknown"}</Tag>
              <span className="message-meta">{formatTimestamp(message.createdAt || message.timestamp)}</span>
            </div>
            <div className="message-body">{preview.body}</div>
            {preview.meta ? <div className="message-note">{preview.meta}</div> : null}
          </div>
        )
      })}
      {messages.length > visibleMessages.length ? <div className="cp-overflow-note">另外 {messages.length - visibleMessages.length} 条消息已折叠，避免上下文面板过长。</div> : null}
    </div>
  )
}

function buildRunTree(runDetail?: RunDetailResponse) {
  if (!runDetail) return []
  return [
    {
      key: runDetail.run.run_id,
      title: `${runDetail.run.title} · ${runDetail.run.current_state}`,
      children: (runDetail.steps ?? []).map((step) => ({
        key: step.step_id,
        title: `${step.title} · ${step.state}`,
      })),
    },
  ]
}

function renderEvidenceCards(records: EvidenceRecord[], emptyDescription = "暂无证据") {
  if (!records.length) return <Empty description={emptyDescription} image={Empty.PRESENTED_IMAGE_SIMPLE} />
  const visibleRecords = records.slice(0, 4)
  return (
    <div className="evidence-card-grid">
      {visibleRecords.map((record) => (
        <div className="evidence-card" key={record.evidence_id}>
          <div className="evidence-card-top">
            <Tag color={record.admissibility === "allowed" ? "green" : record.admissibility === "downgraded" ? "orange" : "red"}>{record.admissibility}</Tag>
            <span className="evidence-provider">{record.provider}</span>
          </div>
          <div className="evidence-title">{record.title}</div>
          <div className="evidence-meta">
            <span>{record.year ?? "-"}</span>
            <span>{record.source_class}</span>
            <span>conf {record.confidence ?? 0}</span>
          </div>
          <div className="evidence-abstract">{compactText(record.normalized_abstract || record.raw_snippet || "无摘要", 240)}</div>
          <div className="evidence-link">{compactLinkLabel(record.url || record.doi)}</div>
        </div>
      ))}
      {records.length > visibleRecords.length ? <div className="cp-overflow-note">另外 {records.length - visibleRecords.length} 条证据已折叠到摘要视图。</div> : null}
    </div>
  )
}

function renderArtifactTable(items: ArtifactItem[], emptyDescription = "暂无工件") {
  return (
    <Table<ArtifactItem>
      rowKey="artifact_id"
      pagination={false}
      size="small"
      scroll={{ y: 400 }}
      dataSource={items}
      locale={{ emptyText: emptyDescription }}
      columns={[
        { title: "路径", dataIndex: "path", key: "path", ellipsis: true },
        { title: "类型", dataIndex: "kind", key: "kind", width: 120 },
        { title: "动作", dataIndex: "safe_action", key: "safe_action", width: 160 },
        {
          title: "摘要",
          key: "summary",
          render: (_, item) => {
            const summary = item.summary ?? {}
            const fileName = typeof summary.file_name === "string" ? summary.file_name : ""
            const sizeClass = typeof summary.size_class === "string" ? summary.size_class : ""
            const detected = typeof summary.detected_format === "string" ? summary.detected_format : ""
            const protectedFlag = typeof summary.protected === "boolean" ? (summary.protected ? "protected" : "safe") : ""
            return (
              <div className="artifact-summary-cell">
                {[fileName, sizeClass, detected, protectedFlag].filter(Boolean).map((value) => (
                  <span className="artifact-chip" key={value}>{value}</span>
                ))}
              </div>
            )
          },
        },
      ]}
    />
  )
}

function renderTimeline(items: TimelineEntry[]) {
  if (!items.length) return <Empty description="暂无时间线" image={Empty.PRESENTED_IMAGE_SIMPLE} />
  return (
    <Timeline
      items={items.map((item) => ({
        color: item.state_to === "completed" ? "green" : item.state_to === "failed" ? "red" : item.state_to === "blocked_policy" ? "orange" : "blue",
        children: (
          <div className="timeline-card">
            <div className="timeline-title-row">
              <strong>{item.event_type}</strong>
              <Tag>{item.state_to || item.step_id || "event"}</Tag>
            </div>
            <div className="timeline-meta">{item.timestamp || "-"}</div>
            {item.reason ? <div className="timeline-reason">{item.reason}</div> : null}
          </div>
        ),
      }))}
    />
  )
}

export function WorkbenchView(props: WorkbenchViewProps) {
  const {
    runs,
    sessions,
    activity,
    sourceMode,
    liveDataEnabled,
    integrationStatus,
    selectedRunId,
    selectedSessionId,
    runDetail,
    sessionUsage,
    sessionMessages,
    artifacts,
    evidenceResult,
    evidenceQuery,
    evidenceLimit,
    artifactPath,
    evidenceLoading,
    onSelectRun,
    onSelectSession,
    onArtifactPathChange,
    onEvidenceQueryChange,
    onEvidenceLimitChange,
    onRefreshArtifacts,
    onSearchEvidence,
  } = props

  const linkedEvidence = (runDetail?.linked?.evidence_bundles as EvidenceSearchResponse[] | undefined)?.flatMap((bundle) => bundle.records ?? []) ?? []
  const linkedArtifacts = (runDetail?.linked?.artifacts as ArtifactItem[] | undefined) ?? []
  const runSteps = (runDetail?.steps as RunStepInfo[] | undefined) ?? []
  const runTimeline = (runDetail?.timeline as TimelineEntry[] | undefined) ?? []
  const activityItems = activity.slice(0, 8)
  const currentRun = runDetail?.run
  const completedSteps = runSteps.filter((step) => ["completed", "failed", "blocked_policy", "aborted"].includes(step.state)).length
  const stepProgress = runSteps.length ? Math.round((completedSteps / runSteps.length) * 100) : 0
  const visibleRuns = limitWithSelection(runs, 5, (run) => run.run_id, selectedRunId)
  const visibleSessions = limitWithSelection(sessions, 4, (session) => session.session_id, selectedSessionId)
  const integrationGaps = liveDataEnabled
    ? integrationStatus.missingAreas
        .filter((area) => {
          if (area === "runDetail") {
            return Boolean(selectedRunId)
          }
          if (area === "sessionUsage" || area === "sessionMessages") {
            return Boolean(selectedSessionId)
          }
          return area !== "evidence" && area !== "artifacts"
        })
        .map((area) => integrationAreaLabels[area])
    : []

  return (
    <Space direction="vertical" size={16} style={{ width: "100%" }}>
      {integrationGaps.length ? (
        <Alert
          type="info"
          showIcon
          message="Workbench 正在等待部分真实数据"
          description={`当前仍缺少 ${integrationGaps.join("、")}。前端结构已经稳定，正式后端和 OpenCode 接入后会自动填充这些区域。`}
        />
      ) : null}

      <div className="workbench-command-strip">
        <div className="workbench-command-card">
          <span>当前 Run</span>
          <strong className="cp-line-clamp-2">{currentRun?.title || "未选择"}</strong>
          <small>{currentRun?.run_id || "-"}</small>
        </div>
        <div className="workbench-command-card">
          <span>当前状态</span>
          <strong>{currentRun?.current_state || "-"}</strong>
          <small className="cp-line-clamp-2">{currentRun?.waiting_on || "无等待项"}</small>
        </div>
        <div className="workbench-command-card">
          <span>证据记录</span>
          <strong>{(evidenceResult?.records ?? linkedEvidence).length}</strong>
          <small>linked evidence</small>
        </div>
        <div className="workbench-command-card">
          <span>工件数量</span>
          <strong>{(artifacts?.entries as ArtifactItem[] | undefined)?.length ?? linkedArtifacts.length}</strong>
          <small>artifacts visible</small>
        </div>
      </div>

      <Row gutter={[16, 16]}>
        <Col xs={24} xxl={6} xl={7}>
          <Card className="cp-card cp-card-dense" title="任务树与队列">
            {runDetail ? (
              <Tree className="cp-tree" defaultExpandAll treeData={buildRunTree(runDetail)} />
            ) : (
              <Empty description="选择 run 后显示任务树" image={Empty.PRESENTED_IMAGE_SIMPLE} />
            )}
            <div className="divider-note">当前选中 run：{selectedRunId || "-"}</div>
            {runs.length ? (
              <div className="queue-stack">
                {visibleRuns.map((run) => (
                  <div className={`queue-card ${selectedRunId === run.run_id ? "queue-card-active" : ""}`} key={run.run_id} onClick={() => onSelectRun(run.run_id)}>
                    <div className="queue-card-top">
                      <strong className="cp-line-clamp-2">{run.title}</strong>
                      <Tag color={stateColor(run.current_state)}>{run.current_state}</Tag>
                    </div>
                    <div className="queue-meta">ID: {run.run_id}</div>
                    <div className="queue-meta cp-line-clamp-2">等待: {run.waiting_on || "无等待项"}</div>
                    <div className="queue-kpis">
                      <span>{run.owner || "system"}</span>
                      <span>{formatTimestamp(run.updated_at)}</span>
                    </div>
                  </div>
                ))}
                {runs.length > visibleRuns.length ? <div className="cp-overflow-note">其余 {runs.length - visibleRuns.length} 个 run 已折叠到摘要视图。</div> : null}
              </div>
            ) : (
              <Empty description={emptyStateDescription("runQueue", { sourceMode, liveDataEnabled, selectedRunId, selectedSessionId })} image={Empty.PRESENTED_IMAGE_SIMPLE} />
            )}
            <div className="divider-note">会话入口</div>
            {sessions.length ? (
              <div className="queue-stack">
                {visibleSessions.map((session) => (
                  <div className={`queue-card ${selectedSessionId === session.session_id ? "queue-card-active" : ""}`} key={session.session_id} onClick={() => onSelectSession(session.session_id)}>
                    <div className="queue-card-top">
                      <strong className="cp-line-clamp-2">{session.title}</strong>
                      <Tag color="blue">{session.status}</Tag>
                    </div>
                    <div className="queue-meta">ID: {session.session_id}</div>
                    <div className="queue-meta">Token: {session.usage?.total_tokens ?? 0}</div>
                    <div className="queue-kpis">
                      <span>消息 {session.message_count}</span>
                      <span>{formatTimestamp(session.last_message_at)}</span>
                    </div>
                  </div>
                ))}
                {sessions.length > visibleSessions.length ? <div className="cp-overflow-note">其余 {sessions.length - visibleSessions.length} 个会话已折叠到摘要视图。</div> : null}
              </div>
            ) : (
              <Empty description={emptyStateDescription("sessionQueue", { sourceMode, liveDataEnabled, selectedRunId, selectedSessionId })} image={Empty.PRESENTED_IMAGE_SIMPLE} />
            )}
          </Card>
        </Col>

        <Col xs={24} xxl={9} xl={8}>
          <Space direction="vertical" size={16} style={{ width: "100%" }}>
            <Card className="cp-card cp-card-dense" title="运行驾驶台" bodyStyle={{ paddingBottom: 0 }}>
              {runDetail ? (
                <Space direction="vertical" size={16} style={{ width: "100%" }}>
                  <div className="run-driver-top">
                    <div>
                      <div className="run-driver-label">当前研究运行</div>
                      <div className="run-driver-title">{runDetail.run.title}</div>
                    </div>
                    <Tag color={stateColor(runDetail.run.current_state)}>{runDetail.run.current_state}</Tag>
                  </div>

                  <div className="run-driver-progress">
                    <div className="run-driver-progress-row">
                      <span>步骤推进</span>
                      <strong>{stepProgress}%</strong>
                    </div>
                    <Progress percent={stepProgress} size="small" status={runDetail.run.current_state === "failed" ? "exception" : "active"} />
                  </div>

                  {runDetail.run.current_state === "blocked_policy" || runDetail.run.stalled ? (
                    <Alert
                      type={runDetail.run.current_state === "blocked_policy" ? "warning" : "error"}
                      showIcon
                      message={runDetail.run.current_state === "blocked_policy" ? "当前运行受阻" : "当前运行停滞"}
                      description={compactText(runDetail.run.failure_reason || runDetail.run.stalled_reason || runDetail.run.waiting_on || "需要在工作台继续处理", 160)}
                    />
                  ) : null}

                  <Descriptions size="small" column={1} className="cp-descriptions" style={{ paddingBottom: 16 }}>
                    <Descriptions.Item label="标题">{runDetail.run.title}</Descriptions.Item>
                    <Descriptions.Item label="状态"><Tag color={stateColor(runDetail.run.current_state)}>{runDetail.run.current_state}</Tag></Descriptions.Item>
                    <Descriptions.Item label="等待">{runDetail.run.waiting_on || "-"}</Descriptions.Item>
                    <Descriptions.Item label="负责人">{runDetail.run.owner || "-"}</Descriptions.Item>
                    <Descriptions.Item label="检查点">{runDetail.run.last_checkpoint || "-"}</Descriptions.Item>
                    <Descriptions.Item label="心跳">{formatTimestamp(runDetail.run.last_heartbeat)}</Descriptions.Item>
                    <Descriptions.Item label="失败原因">{compactText(runDetail.run.failure_reason || "-", 120)}</Descriptions.Item>
                  </Descriptions>

                  <Tabs
                    defaultActiveKey="steps"
                    items={[
                      {
                        key: "steps",
                        label: "步骤状态",
                        children: (
                          <div className="cp-scroll-panel">
                            <List
                              dataSource={runSteps}
                              locale={{ emptyText: "暂无步骤" }}
                              renderItem={(step) => (
                                <List.Item>
                                  <List.Item.Meta
                                    title={<div className="step-title-row"><strong>{step.title}</strong><Tag color={stateColor(step.state)}>{step.state}</Tag></div>}
                                    description={<>
                                      <div>ID: {step.step_id}</div>
                                      <div>等待: {step.waiting_on || "-"}</div>
                                      <div>Checkpoint: {step.last_checkpoint || "-"}</div>
                                    </>}
                                  />
                                </List.Item>
                              )}
                            />
                          </div>
                        ),
                      },
                      {
                        key: "timeline",
                        label: "时间轴",
                        children: <div className="cp-scroll-panel" style={{ paddingTop: 12 }}>{renderTimeline(runTimeline)}</div>,
                      },
                    ]}
                  />
                </Space>
              ) : (
                <Empty description={emptyStateDescription("runDetail", { sourceMode, liveDataEnabled, selectedRunId, selectedSessionId })} image={Empty.PRESENTED_IMAGE_SIMPLE} style={{ paddingBottom: 24 }} />
              )}
            </Card>
          </Space>
        </Col>

        <Col xs={24} xxl={9} xl={9}>
          <Space direction="vertical" size={16} style={{ width: "100%" }}>
            <Card className="cp-card cp-card-dense cp-tabs-card" bordered={false} bodyStyle={{ padding: 0 }}>
              <Tabs
                defaultActiveKey="brief"
                style={{ padding: '0 16px 16px' }}
                items={[
                  {
                    key: "brief",
                    label: "研究简报",
                    children: (
                       <div className="brief-grid" style={{ marginTop: 8 }}>
                        <div className="brief-card">
                          <span>证据总数</span>
                          <strong>{(evidenceResult?.records ?? linkedEvidence).length}</strong>
                          <small>当前 run 可见 evidence</small>
                        </div>
                        <div className="brief-card">
                          <span>工件总数</span>
                          <strong>{(artifacts?.entries as ArtifactItem[] | undefined)?.length ?? linkedArtifacts.length}</strong>
                          <small>当前路径或 linked artifacts</small>
                        </div>
                        <div className="brief-card">
                          <span>活动摘要</span>
                          <strong>{activityItems.length}</strong>
                          <small>最近可见活动事件</small>
                        </div>
                      </div>
                    )
                  },
                  {
                    key: "session",
                    label: "会话上下文",
                    children: (
                      <Space direction="vertical" size={16} style={{ width: "100%", paddingTop: 8 }}>
                        {renderUsagePanel(sessionUsage, emptyStateDescription("usage", { sourceMode, liveDataEnabled, selectedRunId, selectedSessionId }))}
                        <div>
                          <div className="panel-section-title">历史消息</div>
                          <div className="panel-subtitle">保留最近会话上下文，避免把工作台做成开发日志窗口。</div>
                        </div>
                        {renderMessageHistory(sessionMessages, emptyStateDescription("messages", { sourceMode, liveDataEnabled, selectedRunId, selectedSessionId }))}
                      </Space>
                    )
                  },
                  {
                    key: "evidence",
                    label: "证据检索",
                    children: (
                      <Space direction="vertical" style={{ width: "100%", paddingTop: 8 }} size={12}>
                        <div>
                          <div className="panel-subtitle">统一把新的研究问题、证据回收和当前 run 绑定起来。</div>
                          {!liveDataEnabled ? <div className="panel-subtitle">当前为 {sourceMode.toUpperCase()} 模式，检索结果使用固定场景数据。</div> : null}
                        </div>
                        <Space.Compact style={{ width: "100%" }}>
                          <Input value={evidenceQuery} onChange={(event) => onEvidenceQueryChange(event.target.value)} placeholder="输入研究问题或关键词" />
                          <InputNumber min={1} max={20} value={evidenceLimit} onChange={(value) => onEvidenceLimitChange(Number(value || 5))} />
                          <Button type="primary" onClick={onSearchEvidence} loading={evidenceLoading} disabled={!liveDataEnabled}>检索</Button>
                        </Space.Compact>
                        {evidenceResult ? (
                          <Alert type="success" showIcon message={`run=${evidenceResult.run_id || "-"} · records=${evidenceResult.summary?.record_count ?? 0}`} description={`query=${evidenceResult.query}`} />
                        ) : null}
                        {renderEvidenceCards(evidenceResult?.records ?? linkedEvidence, emptyStateDescription("evidence", { sourceMode, liveDataEnabled, selectedRunId, selectedSessionId }))}
                        {liveDataEnabled && !evidenceResult?.records?.length && !linkedEvidence.length ? (
                          <div className="cp-overflow-note">真实模式下这里会优先展示正式 evidence bundle；当前仍可先用 Demo / Smoke 检查版式是否稳定。</div>
                        ) : null}
                      </Space>
                    )
                  },
                  {
                    key: "artifacts",
                    label: "工件产物",
                    children: (
                      <Space direction="vertical" style={{ width: "100%", paddingTop: 8 }} size={12}>
                        <div>
                          <div className="panel-subtitle">把路径、工件摘要和安全动作集中显示。</div>
                          {!liveDataEnabled ? <div className="panel-subtitle">当前为 {sourceMode.toUpperCase()} 模式，工件列表来自预置场景。</div> : null}
                        </div>
                        <Space.Compact style={{ width: "100%" }}>
                          <Input value={artifactPath} onChange={(event) => onArtifactPathChange(event.target.value)} placeholder="输入路径" />
                          <Button onClick={onRefreshArtifacts} disabled={!liveDataEnabled}>刷新</Button>
                        </Space.Compact>
                        {renderArtifactTable(artifacts?.entries as ArtifactItem[] ?? linkedArtifacts, emptyStateDescription("artifacts", { sourceMode, liveDataEnabled, selectedRunId, selectedSessionId }))}
                        {liveDataEnabled && !(artifacts?.entries as ArtifactItem[] | undefined)?.length && !linkedArtifacts.length ? (
                          <div className="cp-overflow-note">工件面板已准备好接正式 artifact browser；当前路径为空时会保持紧凑，不再把整列撑高。</div>
                        ) : null}
                      </Space>
                    )
                  },
                  {
                    key: "activity",
                    label: "活动流",
                    children: (
                       <div className="cp-scroll-panel cp-scroll-panel-tall" style={{ paddingTop: 8 }}>
                        <div className="panel-subtitle panel-subtitle-spaced">系统底层活动摘要。</div>
                        <List
                          dataSource={activityItems}
                          locale={{ emptyText: emptyStateDescription("activity", { sourceMode, liveDataEnabled, selectedRunId, selectedSessionId }) }}
                          renderItem={(event) => (
                            <List.Item>
                              <List.Item.Meta
                                title={<div className="timeline-title-row"><strong>{event.event_type}</strong><Tag>{event.session_id || "session"}</Tag></div>}
                                description={<>
                                  <div className="timeline-meta">{formatTimestamp(event.timestamp)}</div>
                                  <div className="timeline-reason">{summarizeActivity(event)}</div>
                                </>}
                              />
                            </List.Item>
                          )}
                        />
                      </div>
                    )
                  }
                ]}
              />
            </Card>
          </Space>
        </Col>
      </Row>
    </Space>
  )
}
