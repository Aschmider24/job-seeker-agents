#!/bin/bash
# Push local code changes to the Mac mini and restart the Streamlit service.
#
# NOTE: only syncs *code* (app.py, agents/, prompts.py, rag.py,
# shared_context.py, requirements.txt, README.md). It deliberately does NOT
# touch memory/, jobs/, output/, or .env on the mini — those are the mini's
# own live data now (the app writes to memory/jobs/... there), so pushing
# from your laptop would blow away anything created since the initial copy.
#
# Usage: ./deploy/deploy.sh

set -euo pipefail

HOST="antoineschmider@Mac-mini-de-antoine.local"
REMOTE_DIR="job-search-agent"
LOCAL_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

echo "==> Syncing code to $HOST:$REMOTE_DIR ..."
rsync -avz \
  --include='agents/***' \
  --include='app.py' --include='agent.py' --include='prompts.py' \
  --include='rag.py' --include='shared_context.py' \
  --include='requirements.txt' --include='README.md' \
  --exclude='*' \
  "$LOCAL_DIR"/ "$HOST:$REMOTE_DIR/"

echo "==> Reinstalling dependencies (in case requirements.txt changed) ..."
ssh "$HOST" "cd $REMOTE_DIR && source .venv/bin/activate && pip install -q -r requirements.txt"

echo "==> Restarting the jobsearchagent service (requires sudo on the mini) ..."
ssh -t "$HOST" "sudo launchctl kickstart -k system/com.antoine.jobsearchagent"

echo "==> Done. Check https://100.114.228.0:8501 (or your Tailscale hostname) in a minute."
