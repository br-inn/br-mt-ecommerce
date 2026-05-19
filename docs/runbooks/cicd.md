# Runbook — CI/CD pipeline (US-1A-CICD-01)

**Story**: US-1A-CICD-01 · **ADR**: ADR-051 (supply chain) · **Última actualización**: 2026-05-07

---

## 1. Pipeline overview

```
PR opened
  ├── ci-backend.yml          (ruff + mypy + pytest --cov + pip-audit)         [existente]
  ├── ci-frontend.yml         (eslint + tsc + vitest + build + bundle size)   [existente]
  ├── ci-backend-full.yml     (pytest unit + integration + alembic check)    [NUEVO S5]
  ├── ci-frontend-full.yml    (tsc + eslint + vitest + playwright opt)       [NUEVO S5]
  ├── ci-infra.yml            (terraform fmt/validate)                       [existente]
  ├── codeql.yml + secrets-scan.yml + pr-checks.yml                          [existente]
  └── pr-checks.yml           (commitlint, branch protection summary)         [existente]

push tag v*
  └── release-images.yml      (build + push GHCR backend/frontend)            [NUEVO S5]
       └── on workflow_run "release-images" success
            └── deploy-staging.yml (SSH AWS EC2 staging + docker compose)    [NUEVO S5]
```

## 2. Workflows nuevos S5

### 2.1 `ci-backend-full.yml`

- Sigue `ci-backend.yml` como source-of-truth para lint/mypy.
- Añade job `integration-tests` con services Postgres+Redis y `pgvector` extension
  habilitada (US-1A-INFRA-01).
- Job `alembic-check` corre `alembic upgrade head` en DB efímera y verifica `--check`.

### 2.2 `ci-frontend-full.yml`

- TSC strict + ESLint + Vitest (existentes).
- Playwright e2e behind env flag `RUN_PLAYWRIGHT=true` — en S5 default off; activar
  por job una vez Playwright spec set estabilice (Sprint 6).

### 2.3 `release-images.yml`

- Trigger: push de tag `v*` (e.g. `v0.5.0`).
- Build multi-stage backend + frontend images.
- Tag matrix: `${tag}` + `latest`.
- Push a GHCR `ghcr.io/${owner}/mt-pricing-backend:${tag}`.
- Trivy scan + cosign keyless signing (sigstore OIDC, sin secrets).

### 2.4 `deploy-staging.yml`

- Trigger: `workflow_run` de `release-images.yml` en estado `success`.
- Steps:
  1. SSH al AWS EC2 staging app server (key en GH Encrypted Secret `STAGING_SSH_KEY`).
  2. `docker compose pull` (pulls tag `latest` o tag específico via input).
  3. `docker compose up -d --remove-orphans`.
  4. Healthcheck `/health/ready` con timeout 90s, retry 3x.
  5. Si healthcheck falla → rollback automático al tag previo (variable
     `PREVIOUS_TAG` mantenida en server-side `~/mt-deploy/state.json`).
  6. Slack notify `#mt-alerts` con summary (tag deployed, duration, healthcheck status).

## 3. Secrets requeridos en GitHub Actions

| Secret | Uso | Owner |
|--------|-----|-------|
| `GHCR_TOKEN` (auto via `GITHUB_TOKEN`) | push images | GitHub |
| `STAGING_SSH_KEY` | SSH a AWS EC2 staging (clave privada Ed25519 del key pair EC2) | TI MT |
| `STAGING_SSH_HOST` | IP pública del servidor EC2 | TI MT |
| `STAGING_SSH_USER` | usuario EC2, típicamente `ubuntu` | TI MT |
| `DOPPLER_STAGING_TOKEN` | service token Doppler config staging | TI MT |
| `SLACK_WEBHOOK_URL` | notifications | DevOps |

## 4. Rollback runbook

### Rollback automático (deploy fail)

`deploy-staging.yml` rollback step se dispara si healthcheck falla:

```bash
ssh ubuntu@$STAGING_HOST "cd ~/mt-deploy && \
  PREVIOUS_TAG=\$(jq -r .previous_tag state.json) && \
  TAG=\$PREVIOUS_TAG docker compose up -d"
```

### Rollback manual (incidente post-deploy)

1. Identificar tag previo en GHCR (`gh release list`).
2. Trigger `deploy-staging.yml` con `workflow_dispatch` + input `tag=v0.4.x`.
3. Validar healthcheck + Better Stack dashboard.
4. Abrir RCA en Slack thread.

## 5. Performance targets (DoD)

- PR triggers tests en < 8 min p95.
- Main merge → release pipeline en < 15 min wall-clock.
- Rollback automático en < 2 min desde detección.

## 6. Bloqueos conocidos

- **`STAGING_SSH_KEY` debe coincidir con el key pair EC2** — verificar en AWS Console que
  la clave pública del par esté asociada a la instancia. Usuario típico: `ubuntu`.
- **`ENV_STAGING`** — contenido del `.env.staging` inyectado por el deploy step.
  Gestionar vía GitHub Encrypted Secrets (no Doppler en staging).
- **Cosign keyless** requiere OIDC habilitado en GH org — verificar pre-merge.
- **Trivy scan** puede bloquear en CVEs HIGH no patcheables — usar `.trivyignore` con
  justificación firmada.
