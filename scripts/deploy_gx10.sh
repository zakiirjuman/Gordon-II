#!/usr/bin/env bash
set -euo pipefail

HOST="${1:-asus@gx10-49d1}"
REMOTE_DIR="${2:-~/urban-ops-copilot}"

echo "Deploying to ${HOST}:${REMOTE_DIR}"

rsync -avz --delete \
  --exclude '.git' \
  --exclude '__pycache__' \
  --exclude '.venv' \
  ./ "${HOST}:${REMOTE_DIR}/"

ssh -o StrictHostKeyChecking=no "${HOST}" bash -s <<EOF
set -euo pipefail
cd "${REMOTE_DIR}"
python3 -m venv .venv
source .venv/bin/activate
pip install -q -r requirements.txt
pkill -f 'uvicorn app.main:app' || true
nohup .venv/bin/uvicorn app.main:app --host 0.0.0.0 --port 8080 > urban-ops.log 2>&1 &
sleep 2
curl -s http://127.0.0.1:8080/api/health
EOF

echo
echo "App should be live at http://gx10-49d1:8080 (via Tailscale)"
