# CI/CD Branch Protection Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Enforce PR-based workflow — no direct pushes to `main`; CI is the sole merge gate.

**Architecture:** Two workflow files are edited so that test/lint/typecheck jobs only run on `pull_request` events, while the Docker build job continues running on push to `main`. Branch protection is then activated in GitHub Settings to enforce the constraint at the platform level.

**Tech Stack:** GitHub Actions YAML, GitHub branch protection rules.

---

## Files to Modify

| File | Change |
|------|--------|
| `.github/workflows/ci-backend.yml` | Add `if: github.event_name == 'pull_request'` to `lint`, `typecheck`, `test`, `security` jobs |
| `.github/workflows/ci-frontend.yml` | Remove `push: branches: [main]` block from `on:` trigger |

---

### Task 1: ci-backend.yml — gate test jobs to PR events only

**Files:**
- Modify: `.github/workflows/ci-backend.yml`

The `build` job already has `if: github.event_name == 'push' && github.ref == 'refs/heads/main'`.
The other four jobs need the inverse condition so they only run on PRs.

- [ ] **Step 1: Add `if` condition to the `lint` job**

In `.github/workflows/ci-backend.yml`, find the `lint` job definition (line ~40) and add one line:

```yaml
  lint:
    name: Lint (ruff)
    if: github.event_name == 'pull_request'
    runs-on: ubuntu-latest
    timeout-minutes: 10
```

- [ ] **Step 2: Add `if` condition to the `typecheck` job**

Find the `typecheck` job (line ~71):

```yaml
  typecheck:
    name: Typecheck (mypy)
    if: github.event_name == 'pull_request'
    runs-on: ubuntu-latest
    timeout-minutes: 15
```

- [ ] **Step 3: Add `if` condition to the `test` job**

Find the `test` job (line ~100):

```yaml
  test:
    name: Tests (pytest)
    if: github.event_name == 'pull_request'
    runs-on: ubuntu-latest
    timeout-minutes: 20
```

- [ ] **Step 4: Add `if` condition to the `security` job**

Find the `security` job (line ~180):

```yaml
  security:
    name: Security (pip-audit)
    if: github.event_name == 'pull_request'
    runs-on: ubuntu-latest
    timeout-minutes: 10
```

- [ ] **Step 5: Verify YAML syntax**

```bash
python3 -c "import yaml; yaml.safe_load(open('.github/workflows/ci-backend.yml'))" && echo "OK"
```

Expected output: `OK`

- [ ] **Step 6: Commit**

```bash
git add .github/workflows/ci-backend.yml
git commit -m "ci(backend): gate lint/typecheck/test/security to PR events only"
```

---

### Task 2: ci-frontend.yml — remove push-to-main trigger

**Files:**
- Modify: `.github/workflows/ci-frontend.yml`

The frontend has no Docker build in this workflow, so re-running tests on push to `main` is purely redundant.

- [ ] **Step 1: Replace the `on:` block**

In `.github/workflows/ci-frontend.yml`, replace the entire `on:` section (lines 9–18):

**Before:**
```yaml
on:
  push:
    branches: [main]
    paths:
      - "mt-pricing-frontend/**"
      - ".github/workflows/ci-frontend.yml"
  pull_request:
    paths:
      - "mt-pricing-frontend/**"
      - ".github/workflows/ci-frontend.yml"
```

**After:**
```yaml
on:
  pull_request:
    paths:
      - "mt-pricing-frontend/**"
      - ".github/workflows/ci-frontend.yml"
```

- [ ] **Step 2: Verify YAML syntax**

```bash
python3 -c "import yaml; yaml.safe_load(open('.github/workflows/ci-frontend.yml'))" && echo "OK"
```

Expected output: `OK`

- [ ] **Step 3: Commit**

```bash
git add .github/workflows/ci-frontend.yml
git commit -m "ci(frontend): run CI on pull_request only — remove redundant push-to-main trigger"
```

---

### Task 3: Push changes to main

- [ ] **Step 1: Push both commits**

```bash
git push origin main
```

Verify in GitHub → Actions that no spurious CI run is triggered (no PR open = no jobs should run).

---

### Task 4: Configure branch protection on GitHub (manual)

This step is done in the GitHub web UI. Cannot be automated without admin token.

- [ ] **Step 1: Open branch protection settings**

Go to: `https://github.com/br-inn/br-mt-ecommerce/settings/branches`

Click **"Add branch protection rule"**.

- [ ] **Step 2: Set branch name pattern**

Branch name pattern: `main`

- [ ] **Step 3: Enable required status checks**

Check **"Require a pull request before merging"**.  
Leave approvals at **0** (no review required).

Check **"Require status checks to pass before merging"**.  
Check **"Require branches to be up to date before merging"**.

Search and add each of the following required checks:

**From `ci-backend`:**
- `Lint (ruff)`
- `Typecheck (mypy)`
- `Tests (pytest)`
- `Security (pip-audit)`

**From `ci-frontend`:**
- `Lint`
- `Typecheck`
- `Tests`

**From `pr-checks`:**
- `Conventional commits`
- `Semantic PR title`

> **Note:** Status checks only appear in the search box after they have run at least once on a PR. If a check doesn't appear yet, open a test PR with a small change to trigger the workflows, then come back and add the checks.

- [ ] **Step 4: Lock down direct pushes**

Check **"Do not allow bypassing the above settings"** (this includes admins).

Leave **"Allow force pushes"** unchecked.  
Leave **"Allow deletions"** unchecked.

- [ ] **Step 5: Save**

Click **"Create"** (or "Save changes" if editing an existing rule).

- [ ] **Step 6: Verify protection is active**

Try to push a commit directly to `main`:

```bash
git commit --allow-empty -m "test: verify branch protection"
git push origin main
```

Expected output:
```
remote: error: GH006: Protected branch update failed for refs/heads/main.
remote: error: Required status checks have not succeeded: ...
```

If you see this error, protection is working correctly. Reset the test commit:

```bash
git reset HEAD~1
```

---

## Done — Expected Final State

| What | Result |
|------|--------|
| Direct push to `main` | ❌ Blocked by GitHub |
| PR with failing CI | ❌ Merge button disabled |
| PR with green CI | ✅ Merge button enabled |
| Merge to `main` | ✅ Triggers Docker build only (ci-backend) |
| Push to feature branch | ✅ CI runs lint + typecheck + test + security |
