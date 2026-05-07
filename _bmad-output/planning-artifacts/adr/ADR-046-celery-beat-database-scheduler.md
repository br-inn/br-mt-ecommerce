# ADR-046: Celery Beat con DatabaseScheduler — schedules editables sin redeploy

- Status: proposed
- Date: 2026-05-06
- Deciders: Pablo Sierra (BR), Christian (MT sponsor), TI MT, Gerente Comercial
- Supersedes: aclara ADR-030 (Worker async Celery + Redis) sobre el scheduler

## Contexto

Decisión inicial implícita en ADR-030: usar **Celery beat estático en código** (schedules definidos en `app/worker.py` con `beat_schedule = {...}`). Esto requiere **redeploy** para cambiar horarios de digest del Gerente, archival nocturno, etc.

El Gerente Comercial necesita ajustar horarios operativos sin pasar por TI cada vez:
- Cambiar la hora del digest diario (ej. de 8:00 GST a 7:30 GST).
- Pausar temporalmente el archival nocturno durante migración.
- Ajustar frecuencia de KPIs semanales según ciclo del negocio.
- Habilitar/deshabilitar tasks de comparador según sprint del POC.

`hppt-iom-review_1` tiene un **modelo dual** (APScheduler dentro de FastAPI + Celery beat en paralelo) sin consolidación, lo que generó dos fuentes de verdad. MT aprende de eso y consolida.

## Decisión

Adoptar **Celery Beat con DatabaseScheduler custom** sobre Postgres (Supabase), con tabla `job_definitions` editable desde la UI admin.

### Stack concreto

- Librería: **`celery-sqlalchemy-scheduler`** (open-source, mantenido) o **scheduler propio** custom de ~150 líneas si la librería no encaja con SQLAlchemy 2.0 async (a evaluar Sprint 0).
  - Plan B: **`celery-redbeat`** (Redis-backed; menos persistente pero más simple) — descartado en favor de Postgres por durabilidad y trazabilidad.
- Tabla `job_definitions`:
  ```sql
  CREATE TABLE job_definitions (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    code TEXT UNIQUE NOT NULL,                    -- ej. 'daily_digest_gerente'
    description TEXT,
    task_name TEXT NOT NULL,                      -- ej. 'mt.notifications.send_daily_digest'
    schedule_type TEXT NOT NULL CHECK (schedule_type IN ('cron','interval')),
    cron_expression TEXT,                         -- ej. '0 8 * * *'
    interval_seconds INT,                         -- alternativa a cron
    timezone TEXT NOT NULL DEFAULT 'Asia/Dubai',  -- GST
    queue TEXT NOT NULL DEFAULT 'default',
    args JSONB NOT NULL DEFAULT '[]'::jsonb,
    kwargs JSONB NOT NULL DEFAULT '{}'::jsonb,
    enabled BOOLEAN NOT NULL DEFAULT TRUE,
    last_run_at TIMESTAMPTZ,
    next_run_at TIMESTAMPTZ,
    last_status TEXT,                             -- 'success'/'failure'/'skipped'
    last_error TEXT,
    edited_by UUID REFERENCES users(id),
    edited_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
  );
  CREATE INDEX idx_job_definitions_enabled ON job_definitions(enabled, next_run_at)
    WHERE enabled = TRUE;
  ```
- **RLS policies**: solo `ti_integracion` y `gerente_comercial` pueden `UPDATE` las filas. Audit a `audit_events` automático via trigger.
- **Scheduler process**: contenedor `beat` separado en `docker-compose.prod.yml` que lee `job_definitions WHERE enabled=TRUE` cada 30s y dispara tasks via `celery_app.send_task(...)`.
- **Auto-reload**: el scheduler relee la tabla periódicamente; cambios desde la UI surten efecto en < 1 minuto sin redeploy.

### UI admin

- Página `/admin/jobs` (rol `ti_integracion` + `gerente_comercial` para subset).
- Tabla con: `code`, `description`, `cron_expression`, `enabled`, `last_run_at`, `last_status`, acción `Run now`.
- Detalle por job: editor de cron expression con preview ("próximas 5 ejecuciones"), `args/kwargs JSON editor` (TI-only), `enabled` toggle, audit trail de cambios.
- Validación cron expression con preview en tiempo real (cron-parser).

### Seeds iniciales (insertados en migración Alembic)

```sql
INSERT INTO job_definitions (code, description, task_name, schedule_type, cron_expression, queue) VALUES
  ('daily_digest_gerente',         'Digest diario al Gerente Comercial', 'mt.notifications.send_daily_digest',     'cron', '0 8 * * *',     'notifications'),
  ('weekly_kpi_report',             'Reporte KPIs semanal',                'mt.notifications.send_kpi_weekly',       'cron', '0 9 * * 1',     'notifications'),
  ('nightly_audit_archival',        'Archivado nocturno de audit_events',   'mt.audit.archive_old_events',            'cron', '0 2 * * *',     'audit'),
  ('nightly_image_orphan_cleanup',  'Limpieza de imágenes huérfanas',       'mt.images.cleanup_orphans',              'cron', '0 3 * * *',     'images'),
  ('hourly_fx_recalc',              'Recálculo FX si hay cambio publicado', 'mt.pricing.evaluate_fx_cascade',         'cron', '0 * * * *',     'pricing'),
  ('daily_pim_diff_audit',          'Diff entre PIM importado y catálogo',  'mt.imports.validate_cross_references',   'cron', '0 6 * * *',     'imports');
```

### Operaciones permitidas

- **TI Integración**: CRUD completo, incluido editar `task_name`, `args`, `kwargs`.
- **Gerente Comercial**: editar `cron_expression`, `enabled`, `timezone` de jobs marcados como "negocio" (digest, KPIs). NO puede tocar tasks de infra (archival, cleanup).
- **Comercial**: read-only.

## Alternativas evaluadas

### Alt 1: Celery beat estático en código (decisión inicial implícita)
- **Pros**: simpler; no DB roundtrip; menos piezas.
- **Contras**: cada cambio requiere PR + redeploy; el negocio depende de TI para cualquier ajuste; experiencia hppt mostró fricción.
- **Veredicto**: rechazada.

### Alt 2: APScheduler en FastAPI (sin Celery beat)
- **Pros**: schedules en proceso de la API; sin contenedor separado.
- **Contras**: tasks corren en el proceso de FastAPI (no Celery worker) → pierde aislamiento, retries, queues, observabilidad de Celery; dual modelo como hppt-iom (aprendido como anti-pattern).
- **Veredicto**: rechazada.

### Alt 3: `celery-redbeat` (Redis-backed)
- **Pros**: minimal; usa Redis ya existente; sincroniza entre múltiples beats si se replica.
- **Contras**: persistencia menos durable que Postgres; RLS no aplicable; audit trail más complejo; queries SQL para reporting son imposibles.
- **Veredicto**: descartada — Postgres gana por trazabilidad + RLS + integración con `audit_events` + reporting.

### Alt 4: `celery-sqlalchemy-scheduler` o scheduler custom Postgres (decisión adoptada)
- **Pros**: editable sin redeploy; auditable; RLS por rol; integrado con `audit_events`; reporting nativo SQL; UI simple; sin dependencia adicional de Redis para state crítico.
- **Contras**: si la librería externa no encaja con SQLAlchemy 2.0 async, hay que escribir un scheduler custom (~150 líneas, riesgo bajo); contenedor `beat` separado.
- **Veredicto**: ADOPTADA.

## Consecuencias positivas

- El Gerente Comercial puede ajustar horarios operativos sin abrir ticket a TI.
- Cambios surten efecto en < 1 minuto sin redeploy.
- Audit trail completo de quién cambió qué schedule y cuándo.
- Reporting nativo (last 30 days de ejecuciones, success rate por job).
- Pausar tasks problemáticas en runtime sin tocar código.
- "Run now" desde UI para casos de testing / disaster recovery.
- Alineación con principio audit-first del proyecto.

## Consecuencias negativas / riesgos

- Una operación maliciosa (rol `ti` comprometido) podría ejecutar tasks arbitrarias. Mitigación: `task_name` validado contra whitelist registrada en código + audit + alertas Sentry en cambios sensibles.
- Si el scheduler `beat` cae, schedules se pausan hasta reinicio. Mitigación: healthcheck propio + auto-restart Docker + alertas Sentry.
- Conflicto de cron mal escrito (ej. `0 0 0 0 0`). Mitigación: validación con cron-parser en backend + preview en UI.
- Schedule editable + task con bug = bug en producción más rápido. Mitigación: `enabled=FALSE` por defecto al crear; explicit "Activate" tras dry-run.
- Drift entre seeds Alembic y tabla en prod (TI editó). Mitigación: migración Alembic usa `ON CONFLICT (code) DO NOTHING` para no pisar ediciones manuales.

## Cuándo revisar

- Si el volumen de tasks supera 50 schedules distintos, evaluar paginación / categorización en UI.
- Si la librería elegida queda discontinuada, migrar a scheduler custom (cost ≈ 1 sprint).
- Si MT pivota a multi-tenant en Fase 3, agregar `tenant_id` a `job_definitions` con RLS.
- Si se implementan workflows complejos (multi-step DAG), evaluar Airflow / Prefect / Temporal en lugar de extender Celery beat.
