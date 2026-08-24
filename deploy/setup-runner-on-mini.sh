#!/bin/bash
# One-time setup: run this ON THE MAC MINI (SSH in first, or run it there
# directly) to (1) allow the deploy workflow to restart the app service
# without a password, and (2) install a GitHub Actions self-hosted runner
# as an always-on service, so pushes to `main` auto-deploy here.
#
# Needs a runner registration token from:
#   https://github.com/Aschmider24/job-seeker-agents/settings/actions/runners/new
# (choose macOS / x64) — tokens expire after ~1 hour, so grab a fresh one
# right before running this.
#
# Usage: ./setup-runner-on-mini.sh <REGISTRATION_TOKEN>

set -euo pipefail

TOKEN="${1:?Usage: $0 <REGISTRATION_TOKEN> (get one from Settings > Actions > Runners > New self-hosted runner)}"
REPO_URL="https://github.com/Aschmider24/job-seeker-agents"
RUNNER_DIR="$HOME/actions-runner"

echo "==> Adding scoped passwordless-sudo rule for the deploy restart step ..."
# Two services now (backend + frontend, see deploy/*.plist) instead of one.
{
  echo "antoineschmider ALL=(root) NOPASSWD: /bin/launchctl kickstart -k system/com.antoine.jobsearchagent-backend"
  echo "antoineschmider ALL=(root) NOPASSWD: /bin/launchctl kickstart -k system/com.antoine.jobsearchagent-frontend"
} | sudo tee /etc/sudoers.d/jobsearchagent-deploy > /dev/null
sudo chmod 0440 /etc/sudoers.d/jobsearchagent-deploy
sudo visudo -cf /etc/sudoers.d/jobsearchagent-deploy
echo "    OK."

echo "==> Fetching latest GitHub Actions runner release ..."
VER=$(curl -s https://api.github.com/repos/actions/runner/releases/latest \
  | grep '"tag_name"' | sed -E 's/.*"v([0-9.]+)".*/\1/')
echo "    Latest runner version: $VER"

mkdir -p "$RUNNER_DIR"
cd "$RUNNER_DIR"

if [ ! -f ./config.sh ]; then
  echo "==> Downloading runner ..."
  curl -o "actions-runner-osx-x64-${VER}.tar.gz" -L \
    "https://github.com/actions/runner/releases/download/v${VER}/actions-runner-osx-x64-${VER}.tar.gz"
  tar xzf "actions-runner-osx-x64-${VER}.tar.gz"
else
  echo "==> Runner already downloaded, skipping."
fi

echo "==> Registering runner with $REPO_URL ..."
./config.sh --url "$REPO_URL" --token "$TOKEN" \
  --name mac-mini --labels self-hosted,macos,mini --unattended --replace

echo "==> Installing runner as a system service (requires sudo) ..."
sudo ./svc.sh install
sudo ./svc.sh start

echo "==> Checking Node availability for the runner (needed since the deploy"
echo "    workflow now runs 'npm ci && npm run build' for the frontend) ..."
echo "    Requirement: Node MUST be installed system-wide (Homebrew), not"
echo "    via nvm — launchd services (the runner is one) don't source shell"
echo "    rc files, so nvm's PATH changes never reach them even though"
echo "    npm/node work fine over SSH."
if command -v node >/dev/null 2>&1 && [[ "$(command -v node)" != "$HOME"/.nvm/* ]]; then
  echo "    OK: node found at $(command -v node) (not under ~/.nvm)."
else
  echo "    WARNING: node is either missing or only found via nvm"
  echo "    ($(command -v node 2>/dev/null || echo 'not found in this shell'))."
  echo "    Fix: 'brew install node' (uninstall/disable the nvm version"
  echo "    first if both are on PATH, to avoid ambiguity about which one"
  echo "    is actually running). See deploy/README.md."
fi

echo "==> Done. Check status with: sudo $RUNNER_DIR/svc.sh status"
echo "    Push to main on GitHub to trigger a deploy."
