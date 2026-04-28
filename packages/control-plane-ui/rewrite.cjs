const fs = require('fs');
const content = fs.readFileSync('src/styles.css', 'utf-8');

const themeCss = `:root {
  --bg-base: #f8fafc;
  --bg-shell: #f8fafc;
  --bg-panel: #ffffff;
  --bg-panel-2: #f1f5f9;
  --border-soft: rgba(0, 0, 0, 0.08);
  --border-strong: rgba(0, 0, 0, 0.15);
  --text-main: #1e293b;
  --text-soft: rgba(0, 0, 0, 0.65);
  --text-dim: rgba(0, 0, 0, 0.45);
  --accent: #2563eb;
  --accent-strong: #1d4ed8;
  --accent-deep: #1e40af;
  --success: #16a34a;
  --warning: #d97706;
  --danger: #dc2626;
  --shadow-lg: 0 8px 24px rgba(0, 0, 0, 0.08);
  --shadow-md: 0 4px 12px rgba(0, 0, 0, 0.05);
}

[data-theme='dark'] {
  --bg-base: #0f172a;
  --bg-shell: #0f172a;
  --bg-panel: #1e293b;
  --bg-panel-2: #334155;
  --border-soft: rgba(255, 255, 255, 0.1);
  --border-strong: rgba(255, 255, 255, 0.15);
  --text-main: #f8fafc;
  --text-soft: rgba(255, 255, 255, 0.7);
  --text-dim: rgba(255, 255, 255, 0.4);
  --accent: #3b82f6;
  --accent-strong: #60a5fa;
  --accent-deep: #2563eb;
  --success: #22c55e;
  --warning: #f59e0b;
  --danger: #ef4444;
  --shadow-lg: 0 8px 24px rgba(0, 0, 0, 0.25);
  --shadow-md: 0 4px 12px rgba(0, 0, 0, 0.18);
}`;

let newContent = content.replace(/:root \{[\s\S]*?\}/, themeCss);

newContent = newContent.replace(/rgba\(12,\s*22,\s*31,\s*0\.\d+\)/g, 'var(--bg-panel)');
newContent = newContent.replace(/rgba\(14,\s*26,\s*36,\s*0\.\d+\)/g, 'var(--bg-panel)');
newContent = newContent.replace(/rgba\(15,\s*26,\s*36,\s*0\.\d+\)/g, 'var(--bg-panel)');
newContent = newContent.replace(/rgba\(16,\s*28,\s*39,\s*0\.\d+\)/g, 'var(--bg-panel)');
newContent = newContent.replace(/rgba\(24,\s*39,\s*52,\s*0\.\d+\)/g, 'var(--bg-panel-2)');
newContent = newContent.replace(/rgba\(18,\s*30,\s*41,\s*0\.\d+\)/g, 'var(--bg-panel-2)');
newContent = newContent.replace(/rgba\(8,\s*16,\s*24,\s*0\.\d+\)/g, 'var(--bg-panel)');
newContent = newContent.replace(/#1c1c1e/g, 'var(--bg-base)');
newContent = newContent.replace(/#242424/g, 'var(--bg-panel)');
newContent = newContent.replace(/#ffffff/g, 'var(--text-main)');
newContent = newContent.replace(/#fff/g, 'var(--text-main)');
newContent = newContent.replace(/linear-gradient\(180deg,\s*rgba\(12,\s*24,\s*34,\s*0\.96\),\s*rgba\(13,\s*26,\s*37,\s*0\.9\)\)/g, 'var(--bg-panel)');
newContent = newContent.replace(/linear-gradient\(180deg,\s*rgba\(16,\s*28,\s*39,\s*0\.94\),\s*rgba\(13,\s*23,\s*32,\s*0\.92\)\)/g, 'var(--bg-panel)');
newContent = newContent.replace(/rgba\(255,\s*255,\s*255,\s*0\.55\)/g, 'var(--text-soft)');
newContent = newContent.replace(/rgba\(255,\s*255,\s*255,\s*0\.3\)/g, 'var(--text-dim)');

fs.writeFileSync('src/styles.css', newContent);
console.log("Done");