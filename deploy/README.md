# Deploying to the Mac mini

Code lives on GitHub (public repo, showcase). The live app runs on the
author's home Mac mini as **two separate services** — a FastAPI backend
(`com.antoine.jobsearchagent-backend`, port 8000) and a static-served React
frontend (`com.antoine.jobsearchagent-frontend`, port 4173) — kept in sync by
a GitHub Actions self-hosted runner installed on the mini itself (see
`setup-runner-on-mini.sh`). Pushing to `main` (i.e. merging a PR from `dev`)
auto-deploys via `.github/workflows/deploy.yml`.

## Security model — READ BEFORE TOUCHING WORKFLOWS

This repo is **public** with a **self-hosted runner** attached (the Mac
mini). GitHub explicitly warns against this combination, because a workflow
triggered by `pull_request` (or `pull_request_target`) lets anyone fork the
repo, open a PR that edits the workflow to run arbitrary shell, and have it
execute on the runner — no merge, no review, nothing but opening the PR.
For a self-hosted runner that's someone's home Mac mini, that's remote code
execution on a home network.

The mitigation in place:

- `deploy.yml` triggers **only** on `push` to `main`. Pushing to `main`
  requires write access to the repo, which forks don't have — so the runner
  only ever executes code the repo owner personally pushed or merged. This
  is the same trust boundary as running `deploy.sh`/`deploy/setup-runner-on-mini.sh`
  by hand.
- Branch protection on `main` requires PRs (no direct pushes) — see repo
  Settings → Branches.
- Repo Settings → Actions → General → **Fork pull request workflows from
  outside collaborators** is set to "Require approval for all outside
  collaborators" (the strictest option).

**Hard rule: never add a `pull_request` or `pull_request_target` trigger to
any workflow in this repo while the runner is attached.** If CI-on-PR
(tests, linting, etc.) is ever wanted, either point it at GitHub-hosted
runners (`runs-on: ubuntu-latest`) instead of `self-hosted`, or first detach
the mini's runner. Don't mix "runs on the mini" with "triggers on PR from
forks" — that's the exact combination GitHub's warning is about.

## One-time runner setup

See `setup-runner-on-mini.sh` — run it on the mini with a fresh runner
registration token from the repo's Settings → Actions → Runners → New
self-hosted runner.

## Migrating from the old single-service (Streamlit) setup

If the mini is still running the old `com.antoine.jobsearchagent` Streamlit
service, it needs a one-time manual switch-over — none of this was run from
this session, so walk through it yourself on the mini:

1. **Stop and remove the old service:**
   ```
   sudo launchctl bootout system/com.antoine.jobsearchagent
   sudo rm /Library/LaunchDaemons/com.antoine.jobsearchagent.plist
   ```
2. **Node must be installed system-wide (Homebrew), not via nvm.** Check
   with `which node`; if it only resolves under `~/.nvm`, run
   `brew install node`. This isn't optional: launchd services (both the
   frontend's `serve` process and the runner itself) don't source shell rc
   files, so nvm's PATH additions never reach them even though `npm`/`node`
   work fine over plain SSH. The frontend plist's `PATH` env var already
   points at both Homebrew prefixes (`/opt/homebrew/bin`, `/usr/local/bin`)
   so it'll pick up whichever one `brew install` used — see the comments in
   `com.antoine.jobsearchagent-frontend.plist` and `deploy.yml`.
3. **First build, by hand** (the plists only *serve* what's already built,
   they don't build it):
   ```
   cd ~/job-search-agent/backend && python3 -m venv .venv && source .venv/bin/activate && pip install -r requirements.txt
   cd ~/job-search-agent/frontend && npm ci && npm run build
   ```
4. **Verify `VITE_API_BASE_URL`** in `frontend/.env.production` and
   `ALLOWED_ORIGINS` in `com.antoine.jobsearchagent-backend.plist` actually
   match the mini's real Tailscale hostname/IP and ports — both currently
   hold a best guess (`100.114.228.0`), not a verified value.
5. **Install and start the two new services:**
   ```
   sudo cp deploy/com.antoine.jobsearchagent-backend.plist deploy/com.antoine.jobsearchagent-frontend.plist /Library/LaunchDaemons/
   sudo launchctl bootstrap system /Library/LaunchDaemons/com.antoine.jobsearchagent-backend.plist
   sudo launchctl bootstrap system /Library/LaunchDaemons/com.antoine.jobsearchagent-frontend.plist
   ```
6. **Re-run `setup-runner-on-mini.sh`** (or hand-edit
   `/etc/sudoers.d/jobsearchagent-deploy`) — the passwordless-sudo rule was
   scoped to the old single service label and needs both new ones. The
   script also now checks Node's PATH situation for you.

Steps 2 and 6 are the two things most likely to silently break the *next*
push-to-main deploy even after the switch-over above succeeds — see
`setup-runner-on-mini.sh`'s Node check and the comments in `deploy.yml`.

## Manual fallback

`deploy.sh` still works for a manual push if the runner/workflow is ever
down: syncs `backend/` + `frontend/` over SSH, reinstalls deps, rebuilds the
frontend, and restarts both services.

`pull-memory.sh` / `push-memory.sh` sync `memory/` (CV, jobs, chroma_db)
between the laptop and the mini for local development against real data —
unaffected by the backend/frontend split, `memory/` still lives at the repo
root on both ends. See the main README for the workflow (mini is the source
of truth; avoid running the backend on both against the same job data at
once).
