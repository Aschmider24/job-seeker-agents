#!/bin/bash
# Push local code changes to the Mac mini and restart the backend + frontend
# services.
#
# NOTE: only syncs *code* (backend/, frontend/, README.md) — excludes
# backend/.venv, backend/__pycache__, frontend/node_modules, frontend/dist
# (all rebuilt on the mini). frontend/.env.production IS synced (it's build
# config, not a secret — VITE_API_BASE_URL must match the mini's real
# address, see that file's comment). It deliberately does NOT touch memory/
# or backend/.env — memory/ is the mini's own live data now (the backend
# writes to memory/jobs/... there), so pushing from your laptop would blow
# away anything created since the initial copy. Root .env (ANTHROPIC_API_KEY)
# also isn't in the include list, so it's untouched too.
#
# Usage: ./deploy/deploy.sh

set -euo pipefail

HOST="antoineschmider@Mac-mini-de-antoine.local"
REMOTE_DIR="job-search-agent"
LOCAL_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

echo "==> Syncing code to $HOST:$REMOTE_DIR ..."
# rsync filter rules are first-match-wins, so excludes for paths *nested
# inside* an included tree must be listed before that include rule.
rsync -avz \
  --exclude='backend/.venv/' --exclude='__pycache__/' \
  --include='backend/***' \
  --exclude='frontend/node_modules/' --exclude='frontend/dist/' \
  --include='frontend/***' \
  --include='README.md' \
  --exclude='*' \
  "$LOCAL_DIR"/ "$HOST:$REMOTE_DIR/"

echo "==> Reinstalling backend dependencies (in case requirements.txt changed) ..."
ssh "$HOST" "cd $REMOTE_DIR/backend && source .venv/bin/activate && pip install -q -r requirements.txt"

echo "==> Installing frontend dependencies and rebuilding ..."
# Requires Node installed system-wide (Homebrew) on the mini, not via nvm —
# see deploy/README.md.
ssh "$HOST" "cd $REMOTE_DIR/frontend && npm ci --silent && npm run build --silent"

echo "==> Restarting the backend + frontend services (requires sudo on the mini) ..."
ssh -t "$HOST" "sudo launchctl kickstart -k system/com.antoine.jobsearchagent-backend"
ssh -t "$HOST" "sudo launchctl kickstart -k system/com.antoine.jobsearchagent-frontend"

echo "==> Done. Check http://100.114.228.0:4173 (or your Tailscale hostname) in a minute."
