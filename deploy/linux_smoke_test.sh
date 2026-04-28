#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT_DIR"

echo "[1/8] Python version"
python3 --version

echo "[2/8] Node/npm version"
node --version
npm --version

echo "[3/8] Build local OpenCode bridge"
npm install --prefix packages/opencode-bridge
npm run check --prefix packages/opencode-bridge
npm run build --prefix packages/opencode-bridge

echo "[4/8] Run Python unit tests"
PYTHONPATH=src python3 -m unittest discover -s tests -v

echo "[5/8] Prototype local analysis smoke test"
PYTHONPATH=src python3 -m abris.cli \
  --request "Analyze this local count matrix" \
  --counts-file examples/prototype/counts.tsv \
  --sample-sheet examples/prototype/samples.csv \
  --json-output

echo "[6/8] Embedded OpenCode runtime self-check"
test -f packages/opencode-bridge/dist/cli.js
test -x packages/opencode-bridge/node_modules/.bin/opencode || test -f packages/opencode-bridge/node_modules/.bin/opencode

echo "[7/8] Optional paper-search MCP readiness"
if [ -d third_party/paper-search-mcp ]; then
  echo "paper-search checkout detected"
  bash deploy/setup_paper_search_mcp.sh
  if [ -z "${ABRIS_PAPER_SEARCH_UNPAYWALL_EMAIL:-}" ]; then
    echo "WARN: ABRIS_PAPER_SEARCH_UNPAYWALL_EMAIL is unset"
  fi
  ABRIS_USE_OPENCODE=1 \
  ABRIS_ENABLE_PAPER_SEARCH_MCP=1 \
  ABRIS_AUTONOMY_MODE=acquire_bounded \
  ABRIS_APPROVAL_REQUIRED=0 \
  ABRIS_ALLOWED_SOURCE_CLASSES=public_registry,workspace_local \
  PYTHONPATH=src python3 - <<'PY'
from pathlib import Path
import sys
sys.path.insert(0, str(Path('src').resolve()))
from abris.cli import build_orchestrator_from_env

orchestrator = build_orchestrator_from_env()
runtime = orchestrator.runtime
assert runtime is not None, 'OpenCode runtime did not initialize'
session_id = runtime.create_session('ABRIS paper-search smoke test')
result = runtime.prompt_text(
    session_id,
    'Use the configured paper-search MCP if available. Find 3 recent papers on single-cell RNA-seq batch correction and summarize them with source names.'
)
print({'session_id': session_id, 'result_keys': sorted(result.keys())})
events = runtime.subscribe_events(limit=10, timeout_ms=1500)
print({'event_count': len(events.get('events', []))})
PY
else
  echo "SKIP: third_party/paper-search-mcp not present"
fi

echo "[8/8] Environment notes"
echo "Conda: $(command -v conda || true)"
echo "Rscript: $(command -v Rscript || true)"

echo "Smoke test completed"
