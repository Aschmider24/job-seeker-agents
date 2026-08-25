# Deploying to the Mac mini

Code lives on GitHub (public repo, showcase). The live app runs on the
author's home Mac mini, kept in sync by a GitHub Actions self-hosted runner
installed on the mini itself (see `setup-runner-on-mini.sh`). Pushing to
`main` (i.e. merging a PR from `dev`) auto-deploys via
`.github/workflows/deploy.yml`.

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

## Manual fallback

`deploy.sh` still works for a manual push if the runner/workflow is ever
down: syncs code over SSH and restarts the service.

`pull-memory.sh` / `push-memory.sh` sync `memory/` (CV, jobs, chroma_db)
between the laptop and the mini for local development against real data —
see the main README for the workflow (mini is the source of truth; avoid
running the app on both against the same job data at once).
