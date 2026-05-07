# ADR-036: Estructura repo (recomendado: repos separados estilo hppt-iom)

- Status: proposed
- Date: 2026-05-06
- Deciders: Pablo Sierra (BR), Christian (MT sponsor), Paula (MT validador), TI MT
- Supersedes: —

## Contexto

Con el pivot a stack heterogéneo (frontend Next.js / TS y backend FastAPI / Python), se debe decidir si el código vive en:

- (A) Un único monorepo con sub-paquetes (`frontend/`, `backend/`, `infra/`).
- (B) Repos separados (`mt-pricing-frontend/`, `mt-pricing-backend/`, `mt-pricing-infra/`).
- (C) Híbrido: monorepo para frontend + backend, repo aparte para infra.

La arquitectura de referencia `hppt-iom` usa la opción **(B)** según información disponible (a verificar contra el repo de referencia).

## Decisión

**Recomendar opción (B): repos separados estilo hppt-iom**, con un repo (o carpeta) de infraestructura que contiene el orquestador `docker-compose.prod.yml`.

| Repo | Contenido |
|------|-----------|
| `mt-pricing-frontend/` | Next.js 16, Shadcn/ui, Tailwind v4, i18n, tests Playwright |
| `mt-pricing-backend/` | FastAPI, Celery, SQLAlchemy 2.0, Alembic, `supabase/migrations/`, tests pytest |
| `mt-pricing-infra/` (o carpeta en repo raíz) | `docker-compose.prod.yml`, `Caddyfile`, `scripts/deploy.sh`, runbook |

CI/CD por repo. Versionado independiente. Comunicación vía contrato OpenAPI publicado por el backend.

**Decisión final a confirmar con TI MT en S0** — si TI MT prefiere un único monorepo (opción A) por razones de gobierno, la estructura interna de carpetas (que ya está definida en §22.1 de la arquitectura) admite ambos modelos sin cambios mayores.

## Alternativas evaluadas

- **(A) Monorepo único** con turborepo/nx: ventaja de un solo PR cross-stack; desventajas: build matrix más complejo, CI más lento, diverge de hppt-iom.
- **(C) Híbrido**: confuso para casos donde infra cambia con código.

## Consecuencias positivas (opción B)

- **Alineamiento con hppt-iom**.
- **Pipelines CI más simples** por repo.
- **Ownership claro**: equipo frontend / equipo backend / TI infra.
- **Versionado independiente**.

## Consecuencias negativas / riesgos

- **Cambios cross-stack** requieren ≥ 2 PRs coordinados → mitigación: contrato OpenAPI estable + scripts de generación de cliente.
- **Tipos no compartidos automáticamente** entre Pydantic y Zod → mitigación: codegen TS desde OpenAPI o convención.

## Cuándo revisar

- **S0**: TI MT confirma preferencia.
- Si los cambios cross-stack se vuelven dolorosos, evaluar monorepo (opción A).
