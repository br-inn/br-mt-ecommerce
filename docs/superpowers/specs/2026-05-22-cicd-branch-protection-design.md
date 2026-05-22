# CI/CD — Branch Protection + Workflow Optimization

**Date:** 2026-05-22  
**Status:** Approved  
**Scope:** Enforce PR-based workflow on `main`; eliminate redundant CI runs post-merge.

---

## Problem

The team pushes code directly to `main`, which acts as the primary development environment. CI runs on `push: main`, meaning tests execute after the code has already landed. Broken code reaches `main` before being caught.

## Goal

Standardize the workflow so that every code change must go through a feature branch + PR + CI green before touching `main`. No approvals required (small team); CI is the sole gate.

---

## Architecture

### 1. Branch Protection on `main`

Configured in GitHub → Settings → Branches → Rule for `main`:

| Rule | Value |
|------|-------|
| Require a pull request before merging | ✅ (0 approvals required) |
| Require status checks to pass before merging | ✅ (see list below) |
| Require branches to be up to date before merging | ✅ |
| Do not allow bypassing the above settings (incl. admins) | ✅ |
| Allow force pushes | ❌ |
| Allow deletions | ❌ |

**Required status checks:**

From `ci-backend`:
- `Lint (ruff)`
- `Typecheck (mypy)`
- `Tests (pytest)`
- `Security (pip-audit)`

From `ci-frontend`:
- `Lint`
- `Typecheck`
- `Tests`

From `pr-checks`:
- `Conventional commits`
- `Semantic PR title`

### 2. `ci-backend.yml` — workflow changes

Add `if: github.event_name == 'pull_request'` to jobs: `lint`, `typecheck`, `test`, `security`.  
The `build` job already has `if: github.event_name == 'push' && github.ref == 'refs/heads/main'` — no change needed.

Behavior after change:
- **PR** → lint + typecheck + test + security run (CI gate)
- **push to main** (merge) → only Docker build + push to GHCR runs

### 3. `ci-frontend.yml` — workflow changes

Remove `push: branches: [main]` from the `on:` trigger entirely.  
Frontend Docker build lives in `release-and-deploy.yml` (tag-triggered); re-running tests on main adds no value.

Behavior after change:
- **PR** → lint + typecheck + test + build run
- **push to main** → nothing runs

---

## Developer Flow

```
feature/<name>  →  git push origin feature/<name>
                →  open PR on GitHub
                →  CI runs: lint · typecheck · test · security (backend)
                             lint · typecheck · test · build (frontend)
                →  all checks green → merge button enabled
                →  merge to main
                →  ci-backend: Docker build → pushed to GHCR (automatic)
```

Direct pushes to `main` are blocked by branch protection for all team members including admins.

---

## Files Changed

| File | Change |
|------|--------|
| `.github/workflows/ci-backend.yml` | Add `if: github.event_name == 'pull_request'` to `lint`, `typecheck`, `test`, `security` jobs |
| `.github/workflows/ci-frontend.yml` | Remove `push: branches: [main]` from `on:` trigger |
| GitHub Settings → Branches | Add branch protection rule for `main` (manual step) |

---

## Out of Scope

- CODEOWNERS file (can be added later as team grows)
- PR template (already enforced by `pr-checks.yml` which validates `## Summary` and `## Test plan` sections)
- Staging / production environment split (future phase)
- Auto-deploy on merge to main (deferred until a staging environment exists)
