const fs = require('fs');
let code = fs.readFileSync('src/App.tsx', 'utf-8');

const startStr = '<div className="cp-topbar-right"';
const endStr = '        </header>';

const startIndex = code.indexOf(startStr);
const endIndex = code.indexOf(endStr, startIndex) + endStr.length;

const replacement = `<div className="cp-topbar-right" style={{ display: "flex", gap: "24px", alignItems: "center" }}>
            <div className="cp-header-metrics" style={{ display: "flex", gap: "16px", fontSize: "13px" }}>
              <div style={{ display: "flex", gap: "6px" }}><span style={{ color: "var(--text-soft)" }}>Runs</span><strong style={{ color: "var(--text-main)" }}>{totals.run_count}</strong></div>
              <div style={{ display: "flex", gap: "6px" }}><span style={{ color: "var(--text-soft)" }}>Blocked</span><strong style={{ color: "var(--danger)" }}>{totals.blocked_run_count}</strong></div>
              <div style={{ display: "flex", gap: "6px" }}><span style={{ color: "var(--text-soft)" }}>Stalled</span><strong style={{ color: "var(--warning)" }}>{totals.stalled_run_count}</strong></div>
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

            <span className="cp-identity-pill" style={{ color: "var(--text-main)", fontSize: "13px" }}>{identity ? \`\${identity.username} (\${identity.role})\` : "未登录"}</span>
          </div>
        </header>`;

if (startIndex !== -1 && endIndex > startIndex) {
  code = code.substring(0, startIndex) + replacement + code.substring(endIndex);
  fs.writeFileSync('src/App.tsx', code);
  console.log('Fixed');
} else {
  console.log('Not found');
}
