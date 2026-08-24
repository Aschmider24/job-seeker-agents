#!/bin/bash
# Pull the Mac mini's live memory/ (CV, projects, jobs, chroma_db) down to
# this laptop, so a local `streamlit run app.py` can see real data.
#
# The mini is the source of truth for memory/ (see deploy.sh) — this only
# ever copies mini -> laptop. Don't run this while also running the app on
# the mini against the same job(s) you're about to edit locally: ChromaDB's
# chroma_db/ is SQLite-based and two independently-running copies writing
# to their own chroma_db/ and later being synced can conflict/lose writes.
#
# Usage: ./deploy/pull-memory.sh

set -euo pipefail

HOST="antoineschmider@Mac-mini-de-antoine.local"
REMOTE_DIR="job-search-agent"
LOCAL_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

echo "==> Pulling memory/ from $HOST:$REMOTE_DIR/memory/ ..."
rsync -avz --delete \
  "$HOST:$REMOTE_DIR/memory/" "$LOCAL_DIR/memory/"

echo "==> Done. Local memory/ now matches the mini."
echo "    Remember: avoid running the app on the mini against the same"
echo "    job data while you edit it locally, and run push-memory.sh when"
echo "    you're done if you want your local changes kept."
