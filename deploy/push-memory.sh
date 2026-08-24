#!/bin/bash
# Push this laptop's memory/ (CV, projects, jobs, chroma_db) up to the Mac
# mini, overwriting the mini's copy. Use after a local session (started with
# pull-memory.sh) where you want to keep what you created/changed locally.
#
# DESTRUCTIVE: uses --delete, so anything in the mini's memory/ that isn't
# also in your local memory/ will be removed. Only run this if your local
# copy is the one you want to keep as the new source of truth — e.g. right
# after pull-memory.sh + a local editing session, with nothing else having
# changed the mini's copy in between.
#
# Usage: ./deploy/push-memory.sh

set -euo pipefail

HOST="antoineschmider@Mac-mini-de-antoine.local"
REMOTE_DIR="job-search-agent"
LOCAL_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

read -p "This will OVERWRITE the mini's memory/ with your local copy. Continue? [y/N] " -n 1 -r
echo
if [[ ! $REPLY =~ ^[Yy]$ ]]; then
  echo "Aborted."
  exit 1
fi

echo "==> Pushing memory/ to $HOST:$REMOTE_DIR/memory/ ..."
rsync -avz --delete \
  "$LOCAL_DIR/memory/" "$HOST:$REMOTE_DIR/memory/"

echo "==> Done. Consider restarting the mini's service so it picks up any"
echo "    changed chroma_db/ cleanly: ssh -t $HOST 'sudo launchctl kickstart -k system/com.antoine.jobsearchagent'"
