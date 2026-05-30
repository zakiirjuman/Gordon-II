#!/usr/bin/env bash
# Deploy urban-ops-copilot to ASUS GX10 (Tailscale: gx10-49d1).
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

export DEPLOY_HOST="${DEPLOY_HOST:-asus@gx10-49d1}"
export REMOTE_DIR="${REMOTE_DIR:-~/urban-ops-copilot}"
export PORT="${PORT:-8080}"
export NVSYNC_KEY="${NVSYNC_KEY:-$HOME/Library/Application Support/NVIDIA/Sync/config/nvsync.key}"

echo "=== GX10 deploy ==="
echo "  host:       $DEPLOY_HOST"
echo "  remote dir: $REMOTE_DIR"
echo "  port:       $PORT"
if [[ -f "$NVSYNC_KEY" ]]; then
  echo "  ssh key:    $NVSYNC_KEY"
else
  echo "  ssh key:    (not found — set NVSYNC_KEY or use ~/.ssh/config)"
fi

python3 scripts/deploy_remote.py
status=$?
if [[ $status -eq 0 ]]; then
  echo ""
  echo "Verify locally:"
  echo "  curl -s http://gx10-49d1:${PORT}/api/health"
  echo "  curl -s http://gx10-49d1:${PORT}/api/snapshot | python3 -c \"import sys,json; print(json.load(sys.stdin)['counts'])\""
fi
exit "$status"
