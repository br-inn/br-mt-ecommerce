---
name: git-pr-workflow
description: Use when making any code change in br-mt-ecommerce — creating files, editing workflows, fixing bugs, updating config, or any modification that will be committed to git. Use before writing a single line of code or running any git command.
---

# Git PR Workflow — br-mt-ecommerce

## Core Rule

**Every change goes through a branch and a PR. No exceptions.**

`main` is protected. Direct pushes are blocked at the platform level. The only path into `main` is: feature branch → PR → CI green → merge.

---

## The Workflow (follow in order)

```
1. git checkout main && git pull origin main
2. git checkout -b <type>/<short-description>
3. Make changes
4. git add <files> && git commit -m "<conventional commit>"
5. git push origin <branch>
6. gh pr create --title "<title>" --body "..."
7. Wait for CI — fix any failures
8. Merge via GitHub (or gh pr merge)
```

**Branch naming:** `feat/`, `fix/`, `ci/`, `chore/`, `docs/` + kebab-case description.  
**Commit messages:** conventional commits (`feat:`, `fix:`, `ci:`, `chore:`).

---

## CI Gate — Required Checks Before Merge

All 9 must be green before the merge button activates:

| Check | Workflow |
|-------|----------|
| `Lint (ruff)` | ci-backend |
| `Typecheck (mypy)` | ci-backend |
| `Tests (pytest)` | ci-backend |
| `Security (pip-audit)` | ci-backend |
| `Lint` | ci-frontend |
| `Typecheck` | ci-frontend |
| `Tests` | ci-frontend |
| `Conventional commits` | pr-checks |
| `Semantic PR title` | pr-checks |

**When a check fails:** Read the failure log → fix the root cause on the same branch → push → wait again. Never merge with red checks.

---

## Diagnosing CI Failures

```bash
# View PR status
gh pr checks <PR-number>

# View failed job logs
gh run view <run-id> --log-failed

# List recent runs
gh run list --branch <branch-name>
```

Common failures and fixes:

| Error | Fix |
|-------|-----|
| `ruff: E501 line too long` | Shorten lines or add `# noqa: E501` |
| `mypy: error: ...` | Fix type annotation or add `# type: ignore` with comment |
| `pytest: FAILED` | Read traceback → fix root cause → re-run locally first |
| `pip-audit: vulnerability found` | Update the vulnerable package |
| `pnpm audit: vulnerability` | Add override in root `package.json` → `pnpm install` |
| `Conventional commits: title` | PR title must start with `feat:`, `fix:`, `ci:`, etc. |

---

## Red Flags — You Are About to Violate This Workflow

| Thought | Reality |
|---------|---------|
| "It's a one-line change, no need for a PR" | Every line goes through a PR. Branch protection enforces this. |
| "I'll push to main directly and open a PR later" | Impossible — branch protection blocks all direct pushes. |
| "This is urgent, I'll skip the branch" | Urgency doesn't change the process. The PR takes 2 minutes. |
| "I'll commit to the existing feature branch" | Every task gets its own branch. Don't stack unrelated changes. |
| "CI is probably going to pass, I'll merge now" | Wait for CI. Green checks are the merge condition, not optimism. |
| "The tests are slow, I'll skip waiting" | CI must finish. Never merge with pending or failed checks. |

---

## Iron Law

**No commit reaches `main` without passing through a PR with green CI.**

This is not a guideline. `main` is protected at the platform level. The workflow above is the only path.
