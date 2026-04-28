const state = {
  token: null,
  selectedSessionId: null,
  selectedRunId: null,
  pollHandle: null,
};

async function requestJson(path, options = {}) {
  const headers = {
    "Content-Type": "application/json",
    ...(options.headers || {}),
  };
  if (state.token) {
    headers.Authorization = `Bearer ${state.token}`;
  }

  const response = await fetch(path, {
    ...options,
    headers,
  });
  const payload = await response.json();
  if (!response.ok) {
    throw new Error(payload.error || `HTTP ${response.status}`);
  }
  return payload;
}

function renderTotals(totals) {
  const container = document.getElementById("totals");
  container.innerHTML = "";
  const entries = [
    ["活跃会话", totals.session_count ?? 0],
    ["会话停滞", totals.stalled_count ?? 0],
    ["运行数量", totals.run_count ?? 0],
    ["策略阻塞", totals.blocked_run_count ?? 0],
    ["运行停滞", totals.stalled_run_count ?? 0],
  ];
  for (const [label, value] of entries) {
    const card = document.createElement("div");
    card.className = "stat-card";
    card.innerHTML = `<strong>${label}</strong><div>${value}</div>`;
    container.appendChild(card);
  }
}

function renderRuns(runs) {
  const container = document.getElementById("runs");
  if (!container) return;
  container.innerHTML = "";
  if (!runs.length) {
    container.textContent = "暂无运行记录";
    return;
  }

  runs.forEach((run) => {
    const card = document.createElement("div");
    card.className = "session-card";
    card.innerHTML = `
      <strong>${run.title}</strong>
      <div>ID: ${run.run_id}</div>
      <div>状态: ${run.current_state}</div>
      <div>停滞: ${run.stalled ? "是" : "否"}</div>
      <div>停滞原因: ${run.stalled_reason || "-"}</div>
      <div>等待: ${run.waiting_on || "-"}</div>
      <div>心跳: ${run.last_heartbeat || "-"}</div>
      <div>失败原因: ${run.failure_reason || "-"}</div>
      <button type="button">查看运行</button>
    `;
    card.querySelector("button").addEventListener("click", () => {
      state.selectedRunId = run.run_id;
      loadRun(run.run_id);
    });
    container.appendChild(card);
  });
}

function renderSessions(sessions) {
  const container = document.getElementById("sessions");
  container.innerHTML = "";
  if (!sessions.length) {
    container.textContent = "暂无会话";
    return;
  }

  sessions.forEach((session) => {
    const card = document.createElement("div");
    card.className = "session-card";
    card.innerHTML = `
      <strong>${session.title}</strong>
      <div>ID: ${session.session_id}</div>
      <div>状态: ${session.status}</div>
      <div>消息数: ${session.message_count}</div>
      <div>Token: ${session.usage?.total_tokens ?? 0}</div>
      <div>成本: ${session.usage?.cost ?? 0}</div>
      <button type="button">查看用量</button>
    `;
    card.querySelector("button").addEventListener("click", () => {
      state.selectedSessionId = session.session_id;
      loadSessionUsage(session.session_id);
    });
    container.appendChild(card);
  });
}

function renderActivity(events) {
  const container = document.getElementById("activity-feed");
  container.innerHTML = "";
  if (!events.length) {
    container.textContent = "暂无活动";
    return;
  }

  events.forEach((event) => {
    const card = document.createElement("div");
    card.className = "event-card";
    card.innerHTML = `
      <strong>${event.event_type}</strong>
      <div>会话: ${event.session_id || "-"}</div>
      <div>时间: ${event.timestamp || "-"}</div>
      <pre>${JSON.stringify(event.payload || {}, null, 2)}</pre>
    `;
    container.appendChild(card);
  });
}

function renderArtifacts(payload) {
  const container = document.getElementById("artifacts");
  container.innerHTML = `<div class="muted">路径: ${payload.path}</div>`;
  if (!payload.entries.length) {
    container.innerHTML += "<div>目录为空</div>";
    return;
  }
  payload.entries.forEach((entry) => {
    const card = document.createElement("div");
    card.className = "artifact-card";
    card.innerHTML = `
      <strong>${entry.path}</strong>
      <div>类型: ${entry.kind}</div>
      <div>安全动作: ${entry.safe_action}</div>
      <pre>${JSON.stringify(entry.summary || {}, null, 2)}</pre>
    `;
    container.appendChild(card);
  });
}

function renderEvidence(bundle) {
  const summary = document.getElementById("evidence-summary");
  const container = document.getElementById("evidence-results");
  container.innerHTML = "";
  summary.textContent = `run=${bundle.run_id || "-"} | query=${bundle.query} | records=${bundle.summary?.record_count ?? 0} | allowed=${bundle.summary?.admissible_count ?? 0} | downgraded=${bundle.summary?.downgraded_count ?? 0} | blocked=${bundle.summary?.blocked_count ?? 0}`;
  const records = bundle.records || [];
  if (!records.length) {
    container.textContent = "没有返回证据记录";
    return;
  }
  records.forEach((record) => {
    const card = document.createElement("div");
    card.className = "artifact-card";
    card.innerHTML = `
      <strong>${record.title}</strong>
      <div>provider: ${record.provider}</div>
      <div>source_class: ${record.source_class}</div>
      <div>admissibility: ${record.admissibility}</div>
      <div>year: ${record.year ?? "-"}</div>
      <div><a href="${record.url || "#"}" target="_blank" rel="noreferrer">${record.url || "无链接"}</a></div>
      <pre>${JSON.stringify({
        authors: record.authors,
        doi: record.doi,
        pmid: record.pmid,
        arxiv_id: record.arxiv_id,
        license: record.license,
        confidence: record.confidence,
        reason: record.admissibility_reason,
        abstract: record.normalized_abstract,
        snippet: record.raw_snippet,
      }, null, 2)}</pre>
    `;
    container.appendChild(card);
  });
}

function renderRunDetail(payload) {
  const panel = document.getElementById("run-panel");
  if (!panel) return;
  const run = payload.run || {};
  const steps = payload.steps || [];
  const timeline = payload.timeline || [];
  const currentStep = payload.current_step || null;
  const linked = payload.linked || {};
  const linkedEvidence = linked.evidence_bundles || [];
  const linkedArtifacts = linked.artifacts || [];

  const stepMarkup = steps.length
    ? steps
        .map(
          (step) => `
            <div class="artifact-card">
              <strong>${step.title}</strong>
              <div>step_id: ${step.step_id}</div>
              <div>state: ${step.state}</div>
              <div>owner: ${step.owner || "-"}</div>
              <div>stalled: ${step.stalled ? "yes" : "no"}</div>
              <div>stalled_reason: ${step.stalled_reason || "-"}</div>
              <div>waiting_on: ${step.waiting_on || "-"}</div>
              <div>checkpoint: ${step.last_checkpoint || "-"}</div>
              <div>heartbeat: ${step.last_heartbeat || "-"}</div>
              <div>failure_reason: ${step.failure_reason || "-"}</div>
            </div>
          `,
        )
        .join("")
    : "<div class=\"muted\">暂无步骤</div>";

  const timelineMarkup = timeline.length
    ? timeline
        .map(
          (entry) => `
            <div class="event-card">
              <strong>${entry.event_type}</strong>
              <div>step: ${entry.step_id || "-"}</div>
              <div>time: ${entry.timestamp || "-"}</div>
              <div>state: ${entry.state_from || "-"} -> ${entry.state_to || "-"}</div>
              <div>reason: ${entry.reason || "-"}</div>
              <div>owner: ${entry.payload?.owner || "-"}</div>
              <div>checkpoint: ${entry.payload?.last_checkpoint || "-"}</div>
            </div>
          `,
        )
        .join("")
    : "<div class=\"muted\">暂无时间线</div>";

  const evidenceMarkup = linkedEvidence.length
    ? linkedEvidence
        .map(
          (bundle) => `
            <div class="artifact-card">
              <strong>${bundle.query || bundle.bundle_id}</strong>
              <div>bundle_id: ${bundle.bundle_id || "-"}</div>
              <div>record_count: ${bundle.summary?.record_count ?? 0}</div>
              <div>allowed: ${bundle.summary?.admissible_count ?? 0}</div>
              <div>downgraded: ${bundle.summary?.downgraded_count ?? 0}</div>
              <div>blocked: ${bundle.summary?.blocked_count ?? 0}</div>
            </div>
          `,
        )
        .join("")
    : '<div class="muted">暂无证据 bundle</div>';

  const artifactMarkup = linkedArtifacts.length
    ? linkedArtifacts
        .map(
          (artifact) => `
            <div class="artifact-card">
              <strong>${artifact.path}</strong>
              <div>kind: ${artifact.kind}</div>
              <div>safe_action: ${artifact.safe_action}</div>
              <pre>${JSON.stringify(artifact.summary || {}, null, 2)}</pre>
            </div>
          `,
        )
        .join("")
    : '<div class="muted">暂无 artifact</div>';

  panel.innerHTML = `
    <div class="artifact-card">
      <strong>${run.title || run.run_id || "Run Detail"}</strong>
      <div>run_id: ${run.run_id || "-"}</div>
      <div>state: ${run.current_state || "-"}</div>
      <div>owner: ${run.owner || "-"}</div>
      <div>waiting_on: ${run.waiting_on || "-"}</div>
      <div>last_heartbeat: ${run.last_heartbeat || "-"}</div>
      <div>last_checkpoint: ${run.last_checkpoint || "-"}</div>
      <div>failure_reason: ${run.failure_reason || "-"}</div>
      <div>current_step: ${currentStep ? `${currentStep.title} (${currentStep.state})` : "-"}</div>
      <pre>${JSON.stringify({
        runtime_session_ids: linked.runtime_session_ids || [],
        evidence_bundle_ids: linked.evidence_bundle_ids || [],
        artifact_paths: linked.artifact_paths || [],
        metadata: run.metadata || {},
      }, null, 2)}</pre>
    </div>
    <div>
      <h3>步骤列表</h3>
      ${stepMarkup}
    </div>
    <div>
      <h3>运行时间线</h3>
      ${timelineMarkup}
    </div>
    <div>
      <h3>证据 Bundles</h3>
      ${evidenceMarkup}
    </div>
    <div>
      <h3>Artifacts</h3>
      ${artifactMarkup}
    </div>
  `;
}

async function loadRun(runId) {
  const payload = await requestJson(`/api/runs/${runId}`);
  renderRunDetail(payload);
}

async function loadDashboard() {
  const [sessionsPayload, runsPayload, activityPayload] = await Promise.all([
    requestJson("/api/sessions"),
    requestJson("/api/runs"),
    requestJson("/api/dashboard/activity?limit=10&timeout_ms=200"),
  ]);
  renderSessions(sessionsPayload.sessions || []);
  renderRuns(runsPayload.runs || activityPayload.runs || []);
  renderTotals(activityPayload.totals || {});
  renderActivity(activityPayload.events || []);
  if (!state.selectedSessionId && sessionsPayload.sessions?.length) {
    state.selectedSessionId = sessionsPayload.sessions[0].session_id;
    loadSessionUsage(state.selectedSessionId).catch(showMessage);
  }
}

async function loadSessionUsage(sessionId) {
  const payload = await requestJson(`/api/sessions/${sessionId}/usage`);
  document.getElementById("usage-panel").textContent = JSON.stringify(payload, null, 2);
}

async function loadArtifacts(pathValue = ".") {
  const payload = await requestJson(`/api/artifacts?path=${encodeURIComponent(pathValue)}`);
  renderArtifacts(payload);
}

function showMessage(message) {
  document.getElementById("login-message").textContent = String(message);
}

function startPolling() {
  if (state.pollHandle) {
    clearInterval(state.pollHandle);
  }
  state.pollHandle = setInterval(() => {
    if (!state.token) return;
    loadDashboard().catch(showMessage);
  }, 5000);
}

document.getElementById("login-form").addEventListener("submit", async (event) => {
  event.preventDefault();
  const username = document.getElementById("username").value;
  const password = document.getElementById("password").value;
  try {
    const payload = await requestJson("/api/auth/login", {
      method: "POST",
      body: JSON.stringify({ username, password }),
    });
    state.token = payload.session_token;
    document.getElementById("connection-status").textContent = `${payload.username} (${payload.role})`;
    showMessage("登录成功");
    await loadDashboard();
    await loadArtifacts(document.getElementById("artifact-path").value || ".");
    startPolling();
  } catch (error) {
    showMessage(error.message || error);
  }
});

document.getElementById("artifacts-form").addEventListener("submit", async (event) => {
  event.preventDefault();
  try {
    await loadArtifacts(document.getElementById("artifact-path").value || ".");
  } catch (error) {
    showMessage(error.message || error);
  }
});

document.getElementById("evidence-form").addEventListener("submit", async (event) => {
  event.preventDefault();
  try {
    const query = document.getElementById("evidence-query").value.trim();
    const limit = Number(document.getElementById("evidence-limit").value || 5);
    const payload = await requestJson("/api/evidence/search", {
      method: "POST",
      body: JSON.stringify({ query, limit, run_id: state.selectedRunId || null }),
    });
    renderEvidence(payload);
    if (payload.run_id) {
      state.selectedRunId = payload.run_id;
      await loadRun(payload.run_id);
      await loadDashboard();
    }
  } catch (error) {
    showMessage(error.message || error);
  }
});
