---
adr: "ADR-049"
title: "Migration Discipline — Alembic + Supabase CLI + Expand-Contract"
status: "proposed"
date: "2026-05-06"
deciders: ["Pablo BR", "TI integración MT"]
related: ["ADR-031", "ADR-045", "ADR-046"]
supersedes: []
project: "mt-pricing-mdm-phase1"
---

# ADR-049 — Migration Discipline

## Contexto

`hppt-iom-review_1` (proyecto referencia) tiene solo **21 migraciones versionadas** en `supabase/migrations/`. El resto del schema de producción se gestionó vía **Supabase Studio UI** sin commit a Git. Esto genera:

- Schema drift entre devs y entornos.
- Imposibilidad de re-crear DB desde cero de forma reproducible.
- Rollbacks ad-hoc, sin garantías.
- Onboarding lento (devs no entienden el modelo real).
- Data migrations mezcladas con schema migrations sin trazabilidad.

MT Middle East **no puede repetir este anti-pattern**. Es un proyecto facturado a cliente externo con compromiso de calidad enterprise.

Decisiones de stack ya tomadas:
- ORM: SQLAlchemy 2.0 async (ADR-029, ADR-045).
- Migrator core: Alembic.
- DB: Supabase Postgres (ADR-031).
- Hybrid persistence: SQLAlchemy en backend Python; Supabase auth/storage/RLS via supabase-js en frontend (ADR-045).

Necesitamos política unificada que respete ambos mundos.

## Decisión

Adoptamos **migration discipline obligatoria** con tres pilares:

### 1. Split de responsabilidades

- **Alembic** gestiona `public.*` (tablas, funciones, triggers, índices, constraints, RLS no-auth).
- **Supabase CLI** (`supabase/migrations/<timestamp>_*.sql`) gestiona `auth.*`, `storage.*`, y RLS de `public.*` que invoca `auth.uid()` / `auth.jwt()`.
- Convención naming pareada: prefijo timestamp + número de orden compartido cuando ambas migran la misma feature.

### 2. Workflow de cambio obligatorio

1. Dev edita modelo SQLAlchemy.
2. `alembic revision --autogenerate -m "..."`.
3. Dev revisa diff (autogenerate no es perfecto).
4. Si toca auth/storage/RLS-auth → escribe SQL Supabase complementario.
5. Tests locales: `upgrade head → downgrade base → upgrade head`.
6. PR incluye ambas migraciones + tests pgTAP para RLS.
7. CI gate `migrate-check` corre roundtrip en Postgres limpio.
8. CI weekly `drift-detect` compara prod schema vs. expected.
9. Deploy: Supabase migrations primero, luego Alembic.

### 3. Reglas no-negociables

- **Expand-Contract pattern** obligatorio para drops/renames/NOT NULL en tablas con datos.
- Prohibido `DROP TABLE`, `DROP COLUMN`, `RENAME COLUMN` en una sola migración con código vivo.
- Prohibido `ALTER COLUMN ... NOT NULL` sin backfill previo.
- Migraciones de **schema** y de **datos** siempre separadas.
- Data migrations en `app/db/data_migrations/` ejecutadas por Celery con audit log.
- Cada migración Alembic con `downgrade()` real (no `pass`).
- Pre-deploy prod: dump schema + datos críticos.
- Migraciones idempotentes cuando posible (`IF NOT EXISTS`, `ON CONFLICT DO NOTHING`).
- Rollback runbook documentado y probado.

### 4. Testing y CI

- Suite CI Postgres limpio + Supabase migrations + Alembic + roundtrip downgrade.
- pgTAP para tests de RLS policies.
- Drift detector weekly en Slack.

## Alternativas consideradas

### A. Solo Alembic, RLS escrita en migraciones Alembic
- ✅ Una sola tool.
- ❌ Pierdes Supabase Studio managed RLS preview.
- ❌ Discrepancia con resto de proyectos BR Innovation que usan Supabase migrations.
- ❌ `supabase db push` en pipelines requiere migrations en `supabase/migrations/`.
- **Rechazado**: incompatible con tooling Supabase recommended.

### B. Solo Supabase CLI, sin Alembic
- ✅ Un solo formato SQL.
- ❌ Pierdes autogenerate de Alembic vs. modelo SQLAlchemy → schema drift entre Python y DB casi garantizado.
- ❌ Sin downgrade real (Supabase migration repair es manual).
- **Rechazado**: regresión grave en velocidad de dev.

### C. Schema-as-code con tools tipo Atlas / Skeema
- ✅ Declarativo, diff automático.
- ❌ Inmaduro en ecosistema Supabase, no soporta políticas RLS bien.
- ❌ Curva de aprendizaje alta para el equipo.
- **Rechazado**: stack ya decidido.

### D. Status quo (Supabase Studio + commits parciales)
- ❌ Anti-pattern observado en hppt-iom-review_1, fuente de bugs y outages.
- **Rechazado**: explícitamente lo que queremos evitar.

## Consecuencias

### Positivas
- Schema 100 % reproducible desde commit.
- Rollbacks confiables.
- Onboarding más rápido (devs leen migraciones para entender modelo).
- DR drills posibles en < 30 min.
- Compliance audit-ready (auditoría puede ver historia completa).

### Negativas
- **Velocity inicial**: workflow más estricto, prohibición de cambios en Studio prod requiere disciplina.
- **Aprendizaje**: devs deben aprender expand-contract.
- **Doble tooling**: Alembic + Supabase CLI requiere split mental.
- **CI más lento**: roundtrip + pgTAP añade ~3-5 min al pipeline.

### Mitigaciones
- Capacitación en S0 (workshop 2h sobre expand-contract).
- Templates de migration con boilerplate idempotente.
- Studio en prod con role read-only enforced via Supabase project settings.
- Drift detector como red de seguridad.

## Definition of Done

- [ ] Alembic configurado en `apps/backend/alembic/`.
- [ ] Supabase CLI configurado en repo root con `supabase/config.toml`.
- [ ] 1ª migration pareada mergeada y aplicada en staging.
- [ ] CI workflow `migrate-check` passing.
- [ ] CI workflow `drift-detect` schedule activo.
- [ ] pgTAP suite con ≥5 tests RLS.
- [ ] Runbook `runbooks/rollback-migration.md` probado en staging.
- [ ] Documentación expand-contract en `docs/migrations.md`.

## Referencias

- ADR-031: DB Supabase Postgres.
- ADR-045: Persistence hybrid SQLAlchemy + Supabase.
- Documento: `_bmad-output/planning-artifacts/mt-migrations-iac-secrets-design.md` §1.
- Alembic: https://alembic.sqlalchemy.org/
- Supabase migrations: https://supabase.com/docs/guides/cli/local-development#database-migrations
- pgTAP: https://pgtap.org/
- Expand-Contract pattern: https://martinfowler.com/bliki/ParallelChange.html
