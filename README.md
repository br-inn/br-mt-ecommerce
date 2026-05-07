# MT Middle East — Plataforma de Datos Maestros y Pricing

[![ci-backend](https://github.com/br-innovation/br-mt-ecommerce/actions/workflows/ci-backend.yml/badge.svg?branch=main)](./.github/workflows/ci-backend.yml)
[![ci-frontend](https://github.com/br-innovation/br-mt-ecommerce/actions/workflows/ci-frontend.yml/badge.svg?branch=main)](./.github/workflows/ci-frontend.yml)
[![secrets-scan](https://github.com/br-innovation/br-mt-ecommerce/actions/workflows/secrets-scan.yml/badge.svg?branch=main)](./.github/workflows/secrets-scan.yml)
[![commitlint](https://github.com/br-innovation/br-mt-ecommerce/actions/workflows/commitlint.yml/badge.svg?branch=main)](./.github/workflows/commitlint.yml)
[![codeql](https://github.com/br-innovation/br-mt-ecommerce/actions/workflows/codeql.yml/badge.svg?branch=main)](./.github/workflows/codeql.yml)
[![License](https://img.shields.io/badge/license-All%20Rights%20Reserved-red)](./LICENSE)
[![Version](https://img.shields.io/badge/version-0.1.0--alpha-blue)](./CHANGELOG.md)
[![Status](https://img.shields.io/badge/status-fase%201%20en%20desarrollo-yellow)](./_bmad-output/planning-artifacts/sprint0-plan-consolidado.md)

Plataforma single-tenant para **MT Middle East** que centraliza el ciclo de vida de
artículos (MDM), gestiona pricing por canal, monitoriza precios de competidores y
exporta datos curados hacia los canales de venta. Fase 1 cubre el núcleo MDM +
pricing manual + comparador asistido por humanos. Desarrollada por **BR Innovation**
como build-custom 100 % auditable y residente en EAU.

---

## Resumen ejecutivo

- **Producto**: sistema de Master Data + Pricing + comparador competitivo, con
  workflow de aprobación y trazabilidad audit-grade.
- **Cliente**: MT Middle East (single-tenant). Sponsor: Christian. Validador
  técnico: Paula.
- **Operador**: BR Innovation (Pablo Sierra, `psierra@br-innovation.com`).
- **Estado**: Sprint 0 en cierre, Sprint 1 (S1) en ejecución. Ver
  [`sprint0-plan-consolidado.md`](./_bmad-output/planning-artifacts/sprint0-plan-consolidado.md)
  y [`sprint1-backlog-refined.md`](./_bmad-output/planning-artifacts/sprint1-backlog-refined.md).
- **Arquitectura**: monolito modular FastAPI + Postgres (Supabase) + Next.js,
  con Celery/Redis, deploy en Hetzner UAE detrás de Caddy. Documentada en
  [Arquitectura v1.4](./_bmad-output/planning-artifacts/architecture-mt-pricing-mdm-phase1.md).

---

## Estado del proyecto

| Aspecto | Estado | Referencia |
|---|---|---|
| Discovery + brief | Cerrado | [`product-brief-...md`](./_bmad-output/planning-artifacts/product-brief-mt-pricing-mdm-phase1.md) |
| PRD | v1 firmado | [`prd-mt-pricing-mdm-phase1.md`](./_bmad-output/planning-artifacts/prd-mt-pricing-mdm-phase1.md) |
| Arquitectura | v1.4 (54 ADRs) | [`architecture-...md`](./_bmad-output/planning-artifacts/architecture-mt-pricing-mdm-phase1.md) |
| Sprint 0 | En cierre | [`sprint0-plan-consolidado.md`](./_bmad-output/planning-artifacts/sprint0-plan-consolidado.md) |
| Sprint 1 | En ejecución | [`sprint1-backlog-refined.md`](./_bmad-output/planning-artifacts/sprint1-backlog-refined.md) |
| Production readiness | Plan maestro | [`production-readiness-master-plan.md`](./_bmad-output/planning-artifacts/production-readiness-master-plan.md) |

---

## Estructura del monorepo

```
br-mt-ecommerce/
├── mt-pricing-backend/       # FastAPI + SQLAlchemy 2.0 async + Alembic + Celery
│   ├── app/                  # Código de aplicación
│   ├── alembic/              # Migraciones DB (expand-contract)
│   ├── tests/                # Pytest suite
│   ├── pyproject.toml        # uv + dependencias
│   └── Dockerfile
├── mt-pricing-frontend/      # Next.js 16 + React 19 + Tailwind v4 + Shadcn
│   ├── app/                  # App Router
│   ├── components/           # UI Shadcn + componentes propios
│   ├── lib/                  # Cliente API tipado, utilidades
│   ├── messages/             # i18n (es, en)
│   ├── tests/                # Vitest + Playwright
│   ├── package.json
│   └── Dockerfile
├── infra/                    # Terraform (Hetzner + DNS + Doppler refs)
├── supabase/                 # Migraciones Supabase, RLS policies, seeds
├── docs/                     # Documentación de proyecto (este monorepo)
│   ├── architecture/         # Link a arquitectura v1.4 + diagramas
│   ├── adr/                  # Índice de los 54 ADRs
│   ├── runbooks/             # RB-01 a RB-15 (placeholders)
│   ├── onboarding/           # Setup dev en < 15 min
│   └── deployment/           # CI/CD, releases, rollbacks
├── _bmad-output/             # Artefactos BMAD (planning, ADRs, briefs)
│   └── planning-artifacts/
├── docker-compose.dev.yml    # Stack local de desarrollo
├── Caddyfile                 # Reverse proxy (dev/prod)
├── pnpm-workspace.yaml       # Declara frontend como workspace pnpm
└── package.json              # Scripts orquestadores raíz
```

> Las carpetas `_bmad/`, `MT_*` y `Documentos referencia de articulos/` contienen
> material de referencia interno; no son parte del runtime.

---

## Stack tecnológico

| Capa | Tecnología | ADR |
|---|---|---|
| Frontend | Next.js 16 (App Router) + React 19 + TypeScript strict | [ADR-028](./_bmad-output/planning-artifacts/adr/ADR-028-frontend-nextjs-react19.md) |
| UI | Tailwind CSS v4 + Shadcn UI | [ADR-028](./_bmad-output/planning-artifacts/adr/ADR-028-frontend-nextjs-react19.md) |
| Backend API | FastAPI (Python 3.11) | [ADR-029](./_bmad-output/planning-artifacts/adr/ADR-029-backend-fastapi-python.md) |
| ORM | SQLAlchemy 2.0 async + Alembic | [ADR-045](./_bmad-output/planning-artifacts/adr/ADR-045-persistence-hybrid-sqlalchemy-supabase.md) |
| Workers | Celery + Redis (DatabaseScheduler) | [ADR-030](./_bmad-output/planning-artifacts/adr/ADR-030-worker-celery-redis.md), [ADR-046](./_bmad-output/planning-artifacts/adr/ADR-046-celery-beat-database-scheduler.md) |
| DB | Postgres (Supabase managed) | [ADR-031](./_bmad-output/planning-artifacts/adr/ADR-031-db-supabase-postgres.md) |
| Auth | Supabase Auth (JWT + RLS) | [ADR-032](./_bmad-output/planning-artifacts/adr/ADR-032-auth-supabase-auth.md) |
| Storage | Supabase Storage | [ADR-033](./_bmad-output/planning-artifacts/adr/ADR-033-storage-supabase.md) |
| Hosting | Hetzner Cloud (UAE) + Docker Compose | [ADR-020](./_bmad-output/planning-artifacts/adr/ADR-020-cloud-residencia-uae.md), [ADR-034](./_bmad-output/planning-artifacts/adr/ADR-034-deploy-hetzner-docker-compose.md) |
| Reverse proxy | Caddy (TLS + rate limiting) | [ADR-035](./_bmad-output/planning-artifacts/adr/ADR-035-reverse-proxy-caddy.md), [ADR-054](./_bmad-output/planning-artifacts/adr/ADR-054-rate-limiting-waf-strategy.md) |
| IaC | Terraform | [ADR-050](./_bmad-output/planning-artifacts/adr/ADR-050-iac-hetzner-terraform.md) |
| Secretos | Doppler | [ADR-051](./_bmad-output/planning-artifacts/adr/ADR-051-secrets-management-doppler.md) |
| Observabilidad | OpenTelemetry + Loki + Prometheus + Grafana | [ADR-019](./_bmad-output/planning-artifacts/adr/ADR-019-observabilidad.md), [ADR-047](./_bmad-output/planning-artifacts/adr/ADR-047-observability-stack.md) |

Índice completo de los 54 ADRs en [`docs/adr/README.md`](./docs/adr/README.md).

---

## Quickstart (dev local en < 15 minutos)

### Modelo de despliegue local

**Caddy es el único punto de entrada HTTP expuesto al host.** Backend (FastAPI)
y Frontend (Next.js) NO se exponen directamente — solo accesibles vía Caddy a
través de la red interna Docker `mt-internal`. La BD (Postgres) y Auth viven
en **Supabase real** (cloud); Redis se expone en `127.0.0.1` para IDE.

```
                    ┌─────────────────────────────────────┐
   localhost:8080 ──┤ Caddy (único entry point HTTP)      │
                    │  ├── /api/*    → backend:8000       │
                    │  ├── /health/* → backend:8000       │
                    │  ├── /docs     → backend:8000       │
                    │  ├── /_next/*  → frontend:3000      │
                    │  └── /         → frontend:3000      │
                    └──────────────┬──────────────────────┘
                                   │ red interna Docker
                    ┌──────────────┴──────────────────────┐
                    │ backend (8000) · frontend (3000)    │
                    │ worker · beat · redis (6379)         │
                    └──────────────┬──────────────────────┘
                                   │
                                   ▼
                    Supabase Cloud — Postgres + Auth + Storage
                    https://vayatmweveoaskyejzba.supabase.co

   localhost:6379 ──── Redis (solo para redis-cli/RedisInsight)
```

Puertos del host configurables vía `.env.deploy` (defaults razonables que NO
requieren privilegios root: `8080`/`8443` en lugar de `80`/`443`).

### Pre-requisitos

- **Docker Desktop** o Docker Engine 24+ con Docker Compose v2.
- **Node.js 20 LTS** + **pnpm 9+** (recomendado: `corepack enable`) — opcional
  para correr frontend fuera de Docker.
- **Python 3.11** + **uv** (`pipx install uv` o `pip install uv`) — opcional
  para correr migraciones y tests fuera de Docker.
- **Git** 2.40+.

> No necesitás Node ni Python instalados si solo querés arrancar el stack —
> Docker Compose construye y ejecuta todo. Los necesitás para tooling local
> (alembic, pytest, vitest, playwright).

### Pasos

```bash
# 1. Clonar el repo
git clone <repo-url> br-mt-ecommerce
cd br-mt-ecommerce

# 2. Configurar puertos del despliegue local
cp .env.deploy.example .env.deploy
# (Editá .env.deploy si necesitás otros puertos. Verificá disponibilidad:)
./infra/scripts/check-ports.sh         # bash/zsh (Linux/macOS/WSL)
.\infra\scripts\check-ports.ps1        # PowerShell (Windows)

# 3. Configurar .env de backend y frontend
cp mt-pricing-backend/.env.example  mt-pricing-backend/.env
cp mt-pricing-frontend/.env.example mt-pricing-frontend/.env.local
# (Para arrancar local sin Supabase real, los placeholders por defecto sirven.
#  El backend usa Postgres/Redis del compose vía override de DATABASE_URL.)

# 4. Levantar el stack (BD = Supabase real)
./infra/scripts/dev-up.sh                       # bash/zsh/WSL
.\infra\scripts\dev-up.ps1                      # PowerShell

# 5. En otra terminal: aplicar migraciones a Supabase y seed (primera vez)
docker compose -f docker-compose.dev.yml --env-file .env.deploy exec backend \
  alembic upgrade head

docker compose -f docker-compose.dev.yml --env-file .env.deploy exec backend \
  python -m app.scripts.seed_initial   # roles + permisos + admin user

# 6. Hooks locales (recomendado, una sola vez)
pnpm install                                    # instala husky + commitlint
pip install --user pre-commit                   # o: pipx install pre-commit
pnpm run hooks:install                          # pre-commit + commit-msg
pnpm run hooks:run                              # smoke test sobre todo el repo
```

> Detalle completo del setup de hooks (qué hace cada uno, comandos útiles,
> cómo skipear en emergencia) en [`CONTRIBUTING.md` §9](./CONTRIBUTING.md#9-hooks-y-herramientas-locales).

> **Pre-requisito**: completar credenciales Supabase en `mt-pricing-backend/.env`
> antes del paso 4. Ver "Credenciales Supabase requeridas" más abajo.

### Acceso a la aplicación

Asumiendo defaults `.env.deploy` (`CADDY_HTTP_PORT=8080`):

| Recurso | URL |
|---|---|
| **App completa (frontend + backend vía Caddy)** | `http://localhost:8080` |
| API endpoints | `http://localhost:8080/api/v1/*` |
| OpenAPI docs interactivos | `http://localhost:8080/docs` |
| Healthchecks | `http://localhost:8080/health/live` |
| Postgres (IDE) | `localhost:5432` (user `postgres`, pass `devpassword`, db `mt_pricing_dev`) |
| Redis (CLI/RedisInsight) | `localhost:6379` |

Si cambiaste `CADDY_HTTP_PORT` en `.env.deploy`, sustituí 8080 por tu puerto.

### Comandos útiles

```bash
# Logs en vivo
docker compose -f docker-compose.dev.yml --env-file .env.deploy logs -f backend
docker compose -f docker-compose.dev.yml --env-file .env.deploy logs -f frontend
docker compose -f docker-compose.dev.yml --env-file .env.deploy logs -f caddy

# Reiniciar un servicio sin tirar el resto
docker compose -f docker-compose.dev.yml --env-file .env.deploy restart backend

# Rebuild tras cambiar Dockerfile o pyproject.toml
docker compose -f docker-compose.dev.yml --env-file .env.deploy up -d --build backend

# Ejecutar comandos dentro del backend (alembic, tests, scripts)
docker compose -f docker-compose.dev.yml --env-file .env.deploy exec backend \
  alembic revision --autogenerate -m "add new column"

docker compose -f docker-compose.dev.yml --env-file .env.deploy exec backend \
  pytest tests/ -v

# Tirar el stack (preserva volúmenes)
docker compose -f docker-compose.dev.yml --env-file .env.deploy down

# Tirar el stack y BORRAR datos (Postgres + Redis + Caddy data)
docker compose -f docker-compose.dev.yml --env-file .env.deploy down -v
```

### Troubleshooting rápido

| Síntoma | Solución |
|---|---|
| `bind: address already in use` en el puerto Caddy/Postgres/Redis | Editá `.env.deploy` y cambiá el puerto correspondiente. Re-corré `check-ports.sh`. |
| Frontend muestra 502 Bad Gateway | El backend todavía no está `healthy`. Mirá `docker compose logs backend`. |
| Hot-reload no funciona | Verificá que el bind mount esté activo: `docker compose ps` debe mostrar el volumen montado en backend/frontend. |
| Cambiaste `pyproject.toml` y no se ve el nuevo paquete | Rebuild: `docker compose up -d --build backend worker beat`. |
| Postgres data corrupto | `docker compose down -v` + `docker compose up` (RE-EJECUTA migraciones desde cero). |

Más detalles en [`docs/onboarding/README.md`](./docs/onboarding/README.md).

---

## CI / CD y workflows GitHub Actions

Todos los workflows están en [`.github/workflows/`](./.github/workflows/) y se
documentan en detalle en [`mt-cicd-pipeline.md`](./_bmad-output/planning-artifacts/mt-cicd-pipeline.md).

| Workflow | Trigger | Propósito |
|---|---|---|
| `ci-backend.yml` | push/PR a `mt-pricing-backend/**` | ruff, mypy, pytest+cov, pip-audit, build/sign imagen GHCR (en main) |
| `ci-frontend.yml` | push/PR a `mt-pricing-frontend/**` | eslint, tsc, vitest, `next build`, bundle size |
| `ci-infra.yml` | push/PR a `infra/terraform/**` | `terraform fmt/validate`, tflint, tfsec |
| `pr-checks.yml` | PR | commitlint, semantic PR title, template completeness, path-based labels |
| `commitlint.yml` | PR + push main | Validación standalone Conventional Commits |
| `secrets-scan.yml` | PR + push main + weekly | gitleaks (blocking) + trufflehog (advisory) |
| `codeql.yml` | PR + push main + weekly | SAST Python + JS/TS |
| `dependabot-auto-merge.yml` | Dependabot PRs | Auto-aprueba y mergea bumps patch/minor |

### Secrets requeridos en GitHub

> Configurar en **Settings → Secrets and variables → Actions** del repo.

| Secret | Workflow consumidor | Obligatorio |
|---|---|---|
| `GITHUB_TOKEN` | todos | Auto (provisto por GH Actions) |
| `GITLEAKS_LICENSE` | `secrets-scan.yml` | Solo si org > 1 dev y repo privado de organización |
| `SENTRY_AUTH_TOKEN` | (futuro: `deploy-prod.yml`) | Cuando se active release tracking en Sentry |
| `HCLOUD_TOKEN` | (futuro: `ci-infra.yml` plan) | Cuando se habilite `terraform plan` en PRs |
| `DOPPLER_TOKEN_*` | (futuro: deploys) | Por entorno (staging/prod) cuando se conecte Doppler |

### Required status checks recomendados (rama `main`)

- `ci-backend / Lint (ruff)`, `ci-backend / Typecheck (mypy)`, `ci-backend / Tests (pytest)`
- `ci-frontend / Lint`, `ci-frontend / Typecheck`, `ci-frontend / Tests`, `ci-frontend / Build`
- `commitlint / Validate Conventional Commits`
- `pr-checks / Conventional commits`, `pr-checks / Semantic PR title`, `pr-checks / PR template completeness`
- `secrets-scan / gitleaks`
- `codeql / Analyze (python)`, `codeql / Analyze (javascript-typescript)`

> Configurar en **Settings → Branches → Branch protection rules** sobre `main`.

---

## Documentación

Toda la documentación viva del proyecto está en [`docs/`](./docs/) y los
artefactos BMAD (briefs, PRDs, ADRs, sprint plans) en
[`_bmad-output/planning-artifacts/`](./_bmad-output/planning-artifacts/).

| Tema | Documento |
|---|---|
| Brief de producto | [`product-brief-mt-pricing-mdm-phase1.md`](./_bmad-output/planning-artifacts/product-brief-mt-pricing-mdm-phase1.md) |
| PRD Fase 1 | [`prd-mt-pricing-mdm-phase1.md`](./_bmad-output/planning-artifacts/prd-mt-pricing-mdm-phase1.md) |
| Arquitectura v1.4 | [`architecture-mt-pricing-mdm-phase1.md`](./_bmad-output/planning-artifacts/architecture-mt-pricing-mdm-phase1.md) |
| Índice de ADRs (54) | [`docs/adr/README.md`](./docs/adr/README.md) |
| Sprint 0 plan | [`sprint0-plan-consolidado.md`](./_bmad-output/planning-artifacts/sprint0-plan-consolidado.md) |
| Sprint 1 backlog | [`sprint1-backlog-refined.md`](./_bmad-output/planning-artifacts/sprint1-backlog-refined.md) |
| Production readiness | [`production-readiness-master-plan.md`](./_bmad-output/planning-artifacts/production-readiness-master-plan.md) |
| Runbooks DR / SLA | [`mt-dr-runbooks-sla-design.md`](./_bmad-output/planning-artifacts/mt-dr-runbooks-sla-design.md) |
| CI/CD pipeline | [`mt-cicd-pipeline.md`](./_bmad-output/planning-artifacts/mt-cicd-pipeline.md) |
| OpenAPI contract | [`mt-api-contract-openapi.yaml`](./_bmad-output/planning-artifacts/mt-api-contract-openapi.yaml) |
| Onboarding dev | [`docs/onboarding/README.md`](./docs/onboarding/README.md) |
| Deployment | [`docs/deployment/README.md`](./docs/deployment/README.md) |

---

## Equipo y stakeholders

| Rol | Persona | Organización |
|---|---|---|
| Sponsor / decisor | Christian | MT Middle East |
| Validador técnico | Paula | MT Middle East |
| Tech lead / operador | Pablo Sierra (`psierra@br-innovation.com`) | BR Innovation |

Decisiones de arquitectura: cualquier cambio significativo requiere ADR firmado
por al menos el tech lead operador y registro en
[`_bmad-output/planning-artifacts/adr/`](./_bmad-output/planning-artifacts/adr/).

---

## Cómo contribuir

Ver [`CONTRIBUTING.md`](./CONTRIBUTING.md) para:

- Workflow de branches y PRs.
- Conventional Commits.
- Estándares de código (ruff/mypy backend, eslint/tsc frontend).
- Code review checklist.
- Cómo crear migraciones Alembic, endpoints API, componentes Shadcn y ADRs.

Política de calidad y conducta: [`CODE_OF_CONDUCT.md`](./CODE_OF_CONDUCT.md).

---

## Reportar issues

- **Vulnerabilidades de seguridad**: NUNCA en GitHub Issues. Seguir
  [`SECURITY.md`](./SECURITY.md) (email dedicado).
- **Bugs y feature requests**: GitHub Issues con el template correspondiente.
- **Decisiones arquitecturales / discusiones**: ADR draft en
  `_bmad-output/planning-artifacts/adr/` + PR de discusión.

---

## Licencia

Propietario: BR Innovation S.A. para MT Middle East. Ver [`LICENSE`](./LICENSE)
(actualmente *All Rights Reserved* hasta firma de licencia definitiva con MT).
