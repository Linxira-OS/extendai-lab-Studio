import type { FormEvent } from "react"

type LoginScreenProps = {
  loading: boolean
  errorMessage?: string
  onSubmit: (values: { username: string; password: string }) => void
}

export function LoginScreen({ loading, errorMessage, onSubmit }: LoginScreenProps) {
  function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    const formData = new FormData(event.currentTarget)
    onSubmit({
      username: String(formData.get("username") ?? ""),
      password: String(formData.get("password") ?? ""),
    })
  }

  return (
    <div className="login-screen">
      <div className="login-shell">
        <div className="login-hero">
          <span className="screen-eyebrow">ABRIS · RESEARCH OPERATIONS SYSTEM</span>
          <h1 className="login-title">研究控制台</h1>
          <p className="login-subtitle">面向真实研究闭环的控制入口。</p>
          <div className="login-signal-strip">
            <span>Run Ledger</span>
            <span>Evidence Plane</span>
            <span>Research Workbench</span>
          </div>
          <div className="login-feature-grid">
            <div className="login-feature-card">
              <strong>主屏</strong>
              <span>态势 / 风险 / 热点</span>
            </div>
            <div className="login-feature-card">
              <strong>工作台</strong>
              <span>任务 / 对话 / 证据 / 工件</span>
            </div>
            <div className="login-feature-card">
              <strong>可信研究</strong>
              <span>Run Ledger / Evidence / Artifact</span>
            </div>
          </div>
        </div>

        <section className="login-card-pro login-card-native">
          <h2 className="login-card-title">登录系统</h2>
          <p className="login-card-note">先看主屏，再进入工作台处理 run、证据与工件。</p>
          <form className="login-form" onSubmit={handleSubmit}>
            <label className="login-field">
              <span className="login-label">用户名</span>
              <input className="login-input" name="username" defaultValue="admin" placeholder="输入用户名" required />
            </label>
            <label className="login-field">
              <span className="login-label">密码</span>
              <input className="login-input" type="password" name="password" defaultValue="abris-admin" placeholder="输入密码" required />
            </label>
            <button className="login-submit" type="submit" disabled={loading}>
              {loading ? "进入中..." : "进入控制台"}
            </button>
          </form>
          {errorMessage ? <div className="login-error">{errorMessage}</div> : null}
        </section>
      </div>
    </div>
  )
}
