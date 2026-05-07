---
title: "Diseño del módulo de jobs (Celery + Redis) — MT Pricing/MDM"
status: "draft"
version: "1.1"
created: "2026-05-06"
updated: "2026-05-06"
project_name: "mt-pricing-mdm-phase1"
related: ["architecture-mt-pricing-mdm-phase1.md", "prd-mt-pricing-mdm-phase1.md", "epics-and-stories-mt-pricing-mdm-phase1.md", "reuse-from-hppt-iom.md", "mt-users-module-design.md"]
reference_project: "br-hppt/br-hppt-iom-review_1/Hppt-dashboard"
changelog:
  - "1.0 (2026-05-06): versión inicial — Celery beat puro con schedules estáticos en código."
  - "1.1 (2026-05-06): ADR-046 — pivote a Celery Beat con DatabaseScheduler editable (tabla `job_definitions`). UI admin `/admin/jobs` con CRUD + cron preview + Run now + audit. RLS: ti_integracion full CRUD + gerente_comercial UPDATE limitado. Seeds Alembic con 6 jobs base. Audit trigger automático. Contenedor `beat` separado en docker-compose con healthcheck."
---

# Diseño del módulo de jobs para MT (Task 6)

> **Decisión de arquitectura clave (v1.1, ADR-046).** A diferencia de hppt-iom (que mantiene Celery + APScheduler dual), MT consolida en **Celery + Celery Beat con DatabaseScheduler editable**. Ventajas: (a) simplicidad operativa — todas las tasks son distribuibles via Celery, (b) **schedules editables sin redeploy** — el Gerente Comercial puede ajustar horarios de digest/KPI desde la UI admin sin ticket a TI, (c) audit trail automático de cambios de horario, (d) healthchecks uniformes. Tradeoff: +1 contenedor (beat con replicas=1), +1 tabla, +1 trigger de audit. ROI: cero redeploys por cambios de horario.
>
> **Fuente.** Patrones extraídos de `c:/BR-Github/br-hppt/br-hppt-iom-review_1/Hppt-dashboard/hppt-iom-backend/app/worker.py`, `app/celery_config.py`, `docker-compose.yml`, y mejoras propuestas (queues nombradas, routing, observabilidad estructurada, schedules editables).

---

## 6.1 Configuración Celery

### `mt-pricing-backend/app/celery_config.py`

```python
from __future__ import annotations
import os
from celery.schedules import crontab
from kombu import Queue, Exchange

# ── Queues (definición declarativa) ─────────────────────────────────────────
# Cada queue tiene su propio exchange por nombre y un routing key idéntico al
# nombre. Eso permite escalar workers por queue sin tocar el código de las tasks.
_DEFAULT_EXCHANGE = Exchange("mt", type="direct")

QUEUES = (
    Queue("default",       _DEFAULT_EXCHANGE, routing_key="default"),
    Queue("imports",       _DEFAULT_EXCHANGE, routing_key="imports"),
    Queue("pricing",       _DEFAULT_EXCHANGE, routing_key="pricing"),
    Queue("images",        _DEFAULT_EXCHANGE, routing_key="images"),
    Queue("comparator",    _DEFAULT_EXCHANGE, routing_key="comparator"),
    Queue("notifications", _DEFAULT_EXCHANGE, routing_key="notifications"),
    Queue("audit",         _DEFAULT_EXCHANGE, routing_key="audit"),
)

class CeleryConfig:
    # ── Broker / backend ────────────────────────────────────────────────────
    broker_url = os.environ.get("REDIS_URL", "redis://redis:6379/0")
    result_backend = os.environ.get("REDIS_URL", "redis://redis:6379/0")
    broker_connection_retry_on_startup = True

    # ── Serialización ───────────────────────────────────────────────────────
    task_serializer = "json"
    result_serializer = "json"
    accept_content = ["json"]
    result_expires = 60 * 60 * 6   # 6h (idem hppt usa 1h, aumentado para retros)
    timezone = "Asia/Dubai"        # GST (UAE) — ADR-020 cloud residencia UAE
    enable_utc = True

    # ── Queues + routing ────────────────────────────────────────────────────
    task_queues = QUEUES
    task_default_queue = "default"
    task_default_exchange = "mt"
    task_default_routing_key = "default"

    task_routes = {
        "mt.imports.*":       {"queue": "imports"},
        "mt.pricing.*":       {"queue": "pricing"},
        "mt.images.*":        {"queue": "images"},
        "mt.comparator.*":    {"queue": "comparator"},
        "mt.notifications.*": {"queue": "notifications"},
        "mt.audit.*":         {"queue": "audit"},
        # default cae a queue "default" automáticamente
    }

    # ── Worker hardening ────────────────────────────────────────────────────
    worker_prefetch_multiplier = 1     # tasks largas: una a la vez
    task_acks_late = True              # ack al terminar (no al recibir)
    task_reject_on_worker_lost = True  # re-encolar si worker muere
    task_track_started = True          # estado STARTED visible
    task_send_sent_event = True        # para Flower / observability

    # ── Beat schedule (ADR-046: DatabaseScheduler editable) ─────────────────
    # NOTA (v1.1): el beat schedule NO vive en código. Se persiste en la tabla
    # `public.job_definitions` (Postgres) y es editable desde la UI admin
    # `/admin/jobs` sin redeploy. Ver §6.4 para DDL + seeds + RLS, y §6.10
    # para el scheduler custom o config de `celery-sqlalchemy-scheduler`.
    #
    # beat_scheduler apunta al scheduler custom (decisión Sprint 0):
    #   - Si encaja con SQLAlchemy 2.0 async: "celery_sqlalchemy_scheduler.schedulers:DatabaseScheduler"
    #   - Si no: "app.scheduler.database_scheduler:DatabaseScheduler" (custom ~150 líneas)
    beat_scheduler = "app.scheduler.database_scheduler:DatabaseScheduler"
    # No usamos beat_schedule_filename: el state vive en `public.job_definitions`
    # (last_run_at, next_run_at).

celery_settings = CeleryConfig()
```

### `mt-pricing-backend/app/worker.py` (autoload + bootstrap)

```python
from celery import Celery
from celery.signals import task_failure, task_postrun
from app.celery_config import celery_settings, QUEUES
import logging

logger = logging.getLogger(__name__)

celery_app = Celery("mt_worker")
celery_app.config_from_object(celery_settings)

# Autoload de todas las tasks en app.tasks.* (descubrimiento automático)
celery_app.autodiscover_tasks(packages=["app.tasks"])

# ── Hooks globales: idempotency + observability ─────────────────────────────
@task_failure.connect
def on_task_failure(sender=None, task_id=None, exception=None, **kwargs):
    logger.error(f"[TASK FAILURE] task={sender.name if sender else '?'} id={task_id} exc={exception!r}")
    # Sentry, structlog… (sentry_sdk.capture_exception ya engancha por default
    # si SDK inicializado en main.py)

@task_postrun.connect
def on_task_postrun(sender=None, task_id=None, retval=None, state=None, **kwargs):
    # Persistir estado a job_runs si la task lo solicita explícitamente.
    # (las tasks que requieren tracking llaman al svc directamente; este hook
    # es para métricas globales solamente)
    pass
```

### `mt-pricing-backend/app/tasks/__init__.py`

```python
# Auto-import de submódulos para que autodiscover los registre
from . import imports, pricing, images, comparator, notifications, audit  # noqa: F401
```

---

## 6.2 Patrón de tasks (plantilla canónica)

```python
# app/tasks/_helpers.py — utilidades compartidas
from __future__ import annotations
import asyncio
import logging
from typing import Callable, Awaitable, Any
from datetime import datetime, timezone
from app.database import get_supabase_client

logger = logging.getLogger(__name__)

def run_sync(coro_factory: Callable[[], Awaitable[Any]]):
    """Ejecuta una corutina en un loop dedicado (workers Celery son sync)."""
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    try:
        return loop.run_until_complete(coro_factory())
    finally:
        loop.close()

def update_job_run(run_id: str, **fields):
    """Actualiza job_runs (idempotente). UPSERT-like."""
    sb = get_supabase_client()
    fields["updated_at"] = datetime.now(timezone.utc).isoformat()
    sb.table("job_runs").update(fields).eq("run_id", run_id).execute()
```

**Plantilla por task** (`app/tasks/<modulo>/<task_name>.py`):

```python
from celery.exceptions import SoftTimeLimitExceeded
from app.worker import celery_app
from app.tasks._helpers import run_sync, update_job_run
import logging

logger = logging.getLogger(__name__)

@celery_app.task(
    name="mt.<module>.<task_name>",
    bind=True,
    queue="<queue>",
    autoretry_for=(ConnectionError, TimeoutError),
    retry_backoff=True,
    retry_backoff_max=600,           # 10min cap
    retry_jitter=True,
    max_retries=5,
    soft_time_limit=60 * 30,         # 30min alerta
    time_limit=60 * 45,              # 45min hard kill
    acks_late=True,
    reject_on_worker_lost=True,
)
def my_task(self, run_id: str, payload: dict) -> dict:
    """Idempotente; safe para reintento.

    Contrato:
      - run_id existe en `job_runs` con status=PENDING o RUNNING.
      - payload es JSON serializable.
      - Devuelve dict con métricas (items_processed, errors_count).
    """
    logger.info(f"[mt.<module>.<task_name>] start run_id={run_id}")
    update_job_run(run_id, status="RUNNING", started_at_celery=...)
    try:
        result = run_sync(lambda: _run_async(run_id, payload))
        update_job_run(run_id, status="SUCCESS", finished_at=..., result=result)
        return result
    except SoftTimeLimitExceeded:
        logger.error(f"[mt.<module>.<task_name>] soft_time_limit exceeded run_id={run_id}")
        update_job_run(run_id, status="FAILURE", error="soft_time_limit_exceeded")
        raise
    except Exception as e:
        logger.exception(f"[mt.<module>.<task_name>] error run_id={run_id}")
        try:
            raise self.retry(exc=e)
        except self.MaxRetriesExceededError:
            update_job_run(run_id, status="FAILURE", error=str(e)[:500])
            return {"status": "FAILURE", "error": str(e)}
```

**Tabla `job_runs` (Supabase migration):**

```sql
create table public.job_runs (
    run_id           uuid primary key default gen_random_uuid(),
    task_name        text not null,
    queue            text not null,
    status           text not null check (status in ('PENDING','RUNNING','RETRYING','SUCCESS','FAILURE','CANCELLED')),
    payload          jsonb,
    result           jsonb,
    error            text,
    processing_status jsonb default '{}'::jsonb,    -- progreso fase a fase (idem tracker_import hppt)
    items_processed  integer default 0,
    started_at       timestamptz default now(),
    started_at_celery timestamptz,
    finished_at      timestamptz,
    duration_ms      integer,
    triggered_by     uuid references auth.users(id),
    trigger_source   text default 'API',            -- API | BEAT | RETRY | MANUAL
    celery_task_id   text,
    updated_at       timestamptz default now()
);
create index idx_job_runs_status on public.job_runs(status) where status in ('PENDING','RUNNING','RETRYING');
create index idx_job_runs_task_name_started on public.job_runs(task_name, started_at desc);
```

---

## 6.3 Tasks Fase 1 (lista exhaustiva)

> **24 tasks** distribuidas en 6 queues. Cada una con nombre canónico `mt.<module>.<task>`.

### Queue `imports` (6 tasks)

| Nombre | Inputs | Outputs | Retries | Idempotencia | Dependencias |
|--------|--------|---------|---------|--------------|--------------|
| `mt.imports.import_pim` | `run_id`, `file_path` (Storage), `mode=full|delta` | `{rows_processed, rows_failed, sku_added}` | 3, backoff exp | UPSERT por sku, run_id como dedup key | Storage, productos, taxonomía |
| `mt.imports.import_costos` | `run_id`, `file_path`, `effective_date` | `{costs_loaded, prices_invalidated}` | 3 | UPSERT por (sku, currency, effective_date) | Imports, FX |
| `mt.imports.import_compatibilidad` | `run_id`, `file_path` | `{relations_added}` | 3 | UPSERT por (sku_main, sku_compat) | Imports, productos |
| `mt.imports.import_fichas` | `run_id`, `file_path` | `{fichas_added, ocr_pending}` | 3 | UPSERT por sku | Imports, OCR (fichas con imagen) |
| `mt.imports.import_excel_demo` | `run_id`, `file_path` | `{rows_loaded}` | 2 | UPSERT con dedup hash | Imports |
| `mt.imports.validate_cross_references` | `run_id` | `{orphans_found, missing_refs}` | 2 | Read-only, idempotente | Productos, costos, fichas |

### Queue `pricing` (5 tasks)

| Nombre | Inputs | Outputs | Retries | Idempotencia | Dependencias |
|--------|--------|---------|---------|--------------|--------------|
| `mt.pricing.recalculate_sku` | `run_id`, `sku_id` | `{old_price, new_price, margin}` | 5 | UPSERT en `prices` por (sku, channel) | Costos, FX, reglas |
| `mt.pricing.recalculate_catalog_bulk` | `run_id`, `filter` (categoría/canal) | `{skus_processed, prices_changed}` | 3 | Chord/group con `recalculate_sku` por chunk | Pricing engine |
| `mt.pricing.simulate_what_if` | `run_id`, `scenario_payload` | `{simulation_id, summary}` | 2 | Insert en `simulations`, run_id único | Pricing engine |
| `mt.pricing.evaluate_exception_rules` | `run_id`, `sku_id` (opcional) | `{exceptions_triggered, queued_for_approval}` | 3 | UPSERT en `pricing_exceptions` | Reglas, aprobaciones |
| `mt.pricing.refresh_fx_rates` | `provider` | `{rates_updated}` | 5 | UPSERT por (currency, date) | FX provider |

### Queue `images` (4 tasks)

| Nombre | Inputs | Outputs | Retries | Idempotencia | Dependencias |
|--------|--------|---------|---------|--------------|--------------|
| `mt.images.mirror_external_image` | `run_id`, `source_url`, `sku` | `{storage_path, sha256}` | 5 | Skip si sha256 ya existe | Storage |
| `mt.images.generate_thumbnails` | `image_id` | `{thumbs: [200,400,800]}` | 3 | Skip si ya generadas | Sharp/Pillow |
| `mt.images.ocr_image` | `image_id` | `{text, confidence}` | 3 | UPSERT en `image_ocr` por image_id | OCR vendor |
| `mt.images.cleanup_orphan_assets` | (none, beat) | `{orphans_deleted}` | 2 | Borra assets sin FK; idempotente | Storage, productos |

### Queue `comparator` (4 tasks)

| Nombre | Inputs | Outputs | Retries | Idempotencia | Dependencias |
|--------|--------|---------|---------|--------------|--------------|
| `mt.comparator.search_candidates` | `sku_id`, `mode` | `{candidates: [...]}` | 3 | UPSERT en `comparator_candidates` | Search vendor / pgvector |
| `mt.comparator.score_candidates` | `sku_id`, `candidates` | `{scored: [...]}` | 3 | UPSERT por (sku, candidate_url) | Embedding model |
| `mt.comparator.run_vlm_judge` | `pair_id` | `{verdict, confidence}` | 3 | UPSERT en `vlm_verdicts` por pair | VLM API |
| `mt.comparator.calibrate_thresholds` | (none, beat) | `{thresholds_updated}` | 2 | Idempotente; UPSERT en `comparator_config` | Histórico verdicts |

### Queue `notifications` (4 tasks)

| Nombre | Inputs | Outputs | Retries | Idempotencia | Dependencias |
|--------|--------|---------|---------|--------------|--------------|
| `mt.notifications.send_approval_request` | `approval_id` | `{sent: true}` | 5 | Dedup por approval_id+stage | Email service |
| `mt.notifications.send_daily_digest` | (none, beat) | `{recipients, sent}` | 3 | Dedup por fecha+rol | KPI engine |
| `mt.notifications.send_escalation` | `approval_id`, `level` | `{sent}` | 5 | Dedup por (approval_id, level) | Email |
| `mt.notifications.send_import_complete` | `run_id`, `recipients` | `{sent}` | 3 | Dedup por run_id+recipient | Email |
| `mt.notifications.send_weekly_kpi` | (none, beat) | `{recipients, sent}` | 3 | Dedup por iso_week | KPI engine |

> Observación: `send_weekly_kpi` cuenta como 5ta task de notifications. Total queue: 5.

### Queue `audit` (2 tasks)

| Nombre | Inputs | Outputs | Retries | Idempotencia | Dependencias |
|--------|--------|---------|---------|--------------|--------------|
| `mt.audit.log_event_async` | `event_payload` | `{event_id}` | 3 | INSERT con `event_id` UUID provisto por caller | `audit_events` |
| `mt.audit.archive_old_events` | (none, beat) | `{archived_count}` | 2 | Idempotente; mueve > 90 días a tabla archive | `audit_events` |

### Resumen totales

- **Total tasks Fase 1:** 26 (mínimo solicitado: 20).
- **Distribución:** imports 6, pricing 5, images 4, comparator 4, notifications 5, audit 2.
- **Beat schedule:** 6 entradas (ver §6.4).

---

## 6.4 Beat schedule editable — DatabaseScheduler (ADR-046)

> **v1.1.** Reemplaza la nota previa "schedules estáticos en código". Decisión: **MT replica el patrón hppt-iom de tabla `job_definitions` editable**, pero sobre Celery Beat (no APScheduler). Razón: el Gerente Comercial debe poder ajustar el horario del digest/KPI/FX recalc sin abrir ticket a TI. Hppt-iom lo justifica para `daily_digest`; MT extiende a más jobs.

### 6.4.1 DDL completo de `job_definitions`

```sql
-- Migración Alembic: alembic/versions/<timestamp>_create_job_definitions.py
-- Schema: public (gestionado por Alembic, ver ADR-045 §8.0.4)

create extension if not exists pgcrypto;

create type schedule_type_t as enum ('cron', 'interval');
create type job_owner_t as enum ('infra', 'business');
create type job_status_t as enum ('idle', 'running', 'success', 'failure', 'cancelled');

create table public.job_definitions (
    id                   uuid primary key default gen_random_uuid(),
    code                 text not null unique,             -- 'daily_digest', 'weekly_kpi', ...
    task_name            text not null,                    -- 'mt.notifications.send_daily_digest'
    description          text,
    owner                job_owner_t not null default 'infra',  -- 'business' = editable por gerente_comercial
    schedule_type        schedule_type_t not null,
    cron_expression      text,                              -- requerido si schedule_type='cron'
    interval_seconds     integer,                           -- requerido si schedule_type='interval'
    timezone             text not null default 'Asia/Dubai',
    queue                text not null default 'default',
    args                 jsonb not null default '[]'::jsonb,
    kwargs               jsonb not null default '{}'::jsonb,
    enabled              boolean not null default true,

    -- Runtime state
    last_run_at          timestamptz,
    next_run_at          timestamptz,
    last_status          job_status_t not null default 'idle',
    last_error           text,
    last_celery_task_id  text,

    -- Audit
    edited_by            uuid references auth.users(id),
    edited_at            timestamptz not null default now(),
    created_at           timestamptz not null default now(),

    constraint chk_schedule_consistency check (
        (schedule_type = 'cron'     and cron_expression is not null and interval_seconds is null) or
        (schedule_type = 'interval' and interval_seconds is not null and cron_expression is null)
    ),
    constraint chk_interval_positive check (interval_seconds is null or interval_seconds > 0)
);

create index idx_job_definitions_enabled_next_run on public.job_definitions(enabled, next_run_at)
    where enabled = true;
create index idx_job_definitions_owner on public.job_definitions(owner);
```

### 6.4.2 Seeds iniciales (Alembic)

```sql
-- Alembic data migration: alembic/versions/<timestamp>_seed_job_definitions.py
-- Inserta los 6 jobs base con timezone Asia/Dubai (GST UAE)

insert into public.job_definitions (code, task_name, description, owner, schedule_type,
                                    cron_expression, timezone, queue, enabled) values
  ('daily_digest',
   'mt.notifications.send_daily_digest',
   'Resumen diario al Gerente Comercial: auto-aprobados + pendientes + escaladas.',
   'business',                       -- editable por gerente_comercial
   'cron', '0 8 * * *', 'Asia/Dubai', 'notifications', true),

  ('weekly_kpi',
   'mt.notifications.send_weekly_kpi',
   'KPI semanal a Gerente + TI los lunes 9:00 GST.',
   'business',
   'cron', '0 9 * * 1', 'Asia/Dubai', 'notifications', true),

  ('nightly_audit_archival',
   'mt.audit.archive_old_events',
   'Archivado nocturno de audit_events > 90 días a tabla cold.',
   'infra',                          -- solo ti_integracion
   'cron', '0 2 * * *', 'Asia/Dubai', 'audit', true),

  ('nightly_image_orphan_cleanup',
   'mt.images.cleanup_orphan_assets',
   'Limpieza nocturna de objetos en bucket product-images sin FK aplicativa.',
   'infra',
   'cron', '0 3 * * *', 'Asia/Dubai', 'images', true),

  ('hourly_fx_recalc',
   'mt.pricing.refresh_fx_rates',
   'Refresh de FX rates desde feed externo cada hora (ajustable por gerente).',
   'business',
   'cron', '10 * * * *', 'Asia/Dubai', 'pricing', true),

  ('daily_pim_diff_audit',
   'mt.imports.audit_pim_diff',
   'Comparación diaria del PIM aplicativo vs último export PIM España (drift detector).',
   'infra',
   'cron', '30 4 * * *', 'Asia/Dubai', 'imports', true)
on conflict (code) do nothing;
```

### 6.4.3 RLS policies para `job_definitions`

> **Defense in depth.** El backend valida permisos via `require_permissions(["jobs:manage"])`, pero RLS Postgres es el segundo cordón. Tres niveles de acceso:

```sql
-- supabase/migrations/<timestamp>_job_definitions_rls.sql

alter table public.job_definitions enable row level security;

-- 1. ti_integracion: full CRUD sobre todos los jobs
create policy "job_def_ti_full_crud" on public.job_definitions
    for all
    using ((auth.jwt() -> 'app_metadata' ->> 'role') = 'ti_integracion')
    with check ((auth.jwt() -> 'app_metadata' ->> 'role') = 'ti_integracion');

-- 2. gerente_comercial: SELECT all + UPDATE limitado a campos {cron_expression, enabled, timezone}
--    SOLO en jobs con owner='business'
create policy "job_def_gerente_read" on public.job_definitions
    for select
    using ((auth.jwt() -> 'app_metadata' ->> 'role') in ('gerente_comercial', 'comercial'));

create policy "job_def_gerente_update_business" on public.job_definitions
    for update
    using (
        (auth.jwt() -> 'app_metadata' ->> 'role') = 'gerente_comercial'
        and owner = 'business'
    )
    with check (
        (auth.jwt() -> 'app_metadata' ->> 'role') = 'gerente_comercial'
        and owner = 'business'
    );

-- NOTA: la restricción de campos editables (solo cron_expression, enabled, timezone)
-- se enforce en el backend (`/admin/jobs PATCH` valida payload). Postgres RLS no
-- tiene granularidad por columna en UPDATE; queda como segundo cordón a nivel fila
-- (gerente solo toca jobs business). Si TI quiere granularidad columna, se usa
-- trigger BEFORE UPDATE que rechaza cambios fuera del whitelist.

-- 3. comercial: read-only (para visualizar próximos digests sin poder editar)
-- ya cubierto por policy "job_def_gerente_read" (incluye 'comercial')
```

### 6.4.4 Audit trail automático (trigger)

```sql
create or replace function public.audit_job_definitions_changes()
returns trigger language plpgsql security definer as $$
declare v_actor uuid;
begin
    v_actor := nullif(current_setting('request.jwt.claim.sub', true), '')::uuid;
    if tg_op = 'UPDATE' then
        insert into public.audit_events (entity, entity_id, action, payload_before, payload_after, actor_id)
        values ('job_definitions', NEW.id::text, 'update',
                to_jsonb(OLD), to_jsonb(NEW), v_actor);
        NEW.edited_by := coalesce(v_actor, NEW.edited_by);
        NEW.edited_at := now();
    elsif tg_op = 'INSERT' then
        insert into public.audit_events (entity, entity_id, action, payload_before, payload_after, actor_id)
        values ('job_definitions', NEW.id::text, 'create', null, to_jsonb(NEW), v_actor);
    elsif tg_op = 'DELETE' then
        insert into public.audit_events (entity, entity_id, action, payload_before, payload_after, actor_id)
        values ('job_definitions', OLD.id::text, 'delete', to_jsonb(OLD), null, v_actor);
    end if;
    return coalesce(NEW, OLD);
end;
$$;

create trigger trg_audit_job_definitions
    before insert or update or delete on public.job_definitions
    for each row execute function public.audit_job_definitions_changes();
```

### 6.4.5 Tasks "owner" — negocio vs infra

| Task | Owner | Razón |
|------|-------|-------|
| `mt.notifications.send_daily_digest` | **business** | Gerente decide hora/cadencia; afecta su rutina diaria. |
| `mt.notifications.send_weekly_kpi` | **business** | Decisión de comunicación interna del Gerente. |
| `mt.pricing.refresh_fx_rates` | **business** | Frecuencia depende de volatilidad FX; Gerente puede subir/bajar. |
| `mt.audit.archive_old_events` | infra | Compliance + storage; ti_integracion lo gestiona. |
| `mt.images.cleanup_orphan_assets` | infra | Higiene técnica del bucket. |
| `mt.imports.audit_pim_diff` | infra | Detección de drift técnico vs export España. |
| `mt.comparator.calibrate_thresholds` (Fase 1.5+) | infra | Pipeline R&D — ti_integracion + champion. |

### 6.4.6 UI admin `/admin/jobs`

> **Pantalla** dentro del dashboard, ruta `/admin/jobs`, gated por `RbacGuard role="ti_integracion"` (o `permission="jobs:manage"`).

**Componentes:**

- **Lista** (TanStack Table): columnas `code`, `task_name`, `owner` (badge), `schedule_type`, `cron_expression`, `timezone`, `enabled` (toggle inline), `last_run_at`, `next_run_at`, `last_status` (badge color), acciones.
- **Filtros**: por `owner` (business/infra), `enabled`, `last_status`.
- **Edit dialog** (`<JobDefinitionDialog>`): formulario controlado por react-hook-form + Zod. Campos editables según rol:
  - `ti_integracion`: todos.
  - `gerente_comercial`: solo `cron_expression`, `timezone`, `enabled` (campos restantes en read-only).
- **Cron preview**: al editar `cron_expression`, llama `GET /admin/jobs/{id}/cron-preview?expr=...&tz=...&n=5` que devuelve las próximas 5 ejecuciones en formato humano. Útil para validar antes de guardar.
- **Run now**: botón que llama `POST /admin/jobs/{id}/run-now` → backend encola `celery_app.send_task(task_name, args=..., kwargs=..., queue=...)` y crea fila `job_runs` con `trigger_source='MANUAL'`. Toast "Encolado, run_id=…".
- **Audit drawer**: panel lateral que muestra últimas 20 entradas de `audit_events` para el job (`entity='job_definitions', entity_id=...`), con diff entre `payload_before` / `payload_after`.

**Endpoints backend** (`mt-pricing-backend/app/routers/admin_jobs.py`):

```python
@router.get("/admin/jobs", response_model=list[JobDefinitionResponse])
async def list_jobs(_user = Depends(require_permissions(["jobs:read"])),
                    session: AsyncSession = Depends(get_session)): ...

@router.patch("/admin/jobs/{job_id}", response_model=JobDefinitionResponse)
async def update_job(job_id: UUID, payload: JobDefinitionUpdate,
                     actor = Depends(require_permissions(["jobs:manage"])),
                     session: AsyncSession = Depends(get_session)): ...

@router.post("/admin/jobs/{job_id}/run-now", status_code=202)
async def run_now(job_id: UUID,
                  actor = Depends(require_permissions(["jobs:manage"])),
                  session: AsyncSession = Depends(get_session)): ...

@router.get("/admin/jobs/{job_id}/cron-preview")
async def cron_preview(job_id: UUID, expr: str, tz: str = "Asia/Dubai", n: int = 5,
                       _user = Depends(require_permissions(["jobs:read"]))): ...

@router.get("/admin/jobs/{job_id}/audit")
async def job_audit(job_id: UUID, limit: int = 20,
                    _user = Depends(require_permissions(["jobs:read"])),
                    session: AsyncSession = Depends(get_session)): ...
```

### 6.4.7 Resumen vista calendario (con seeds defaults)

| Cron seed | Task | Queue | Owner | Editable por |
|-----------|------|-------|-------|--------------|
| `0 8 * * *` (diario 8:00 GST) | `mt.notifications.send_daily_digest` | notifications | business | gerente + ti |
| `0 9 * * 1` (lunes 9:00 GST) | `mt.notifications.send_weekly_kpi` | notifications | business | gerente + ti |
| `0 2 * * *` (diario 2:00 GST) | `mt.audit.archive_old_events` | audit | infra | ti |
| `0 3 * * *` (diario 3:00 GST) | `mt.images.cleanup_orphan_assets` | images | infra | ti |
| `10 * * * *` (cada hora +10min) | `mt.pricing.refresh_fx_rates` | pricing | business | gerente + ti |
| `30 4 * * *` (diario 4:30 GST) | `mt.imports.audit_pim_diff` | imports | infra | ti |

> **Nota.** El cron `comparator-calibration` (semanal domingo 4:00) se introduce en Fase 1.5+ junto con la activación del comparador production-grade.

---

## 6.5 Healthchecks y observabilidad

### Endpoint `/health/celery` (FastAPI)

```python
# app/routers/health.py
from fastapi import APIRouter
from app.worker import celery_app
import asyncio

router = APIRouter()

@router.get("/health/celery")
async def celery_health():
    """Ping a workers con timeout estricto. Returns 200 si al menos 1 worker responde."""
    try:
        # inspect ping en thread (kombu es sync)
        from concurrent.futures import ThreadPoolExecutor
        loop = asyncio.get_event_loop()
        with ThreadPoolExecutor(max_workers=1) as ex:
            replies = await asyncio.wait_for(
                loop.run_in_executor(ex, lambda: celery_app.control.ping(timeout=2.0)),
                timeout=3.0,
            )
        if not replies:
            return {"status": "degraded", "workers": 0}
        return {"status": "healthy", "workers": len(replies), "replies": replies}
    except asyncio.TimeoutError:
        return {"status": "degraded", "workers": 0, "reason": "timeout"}
    except Exception as e:
        return {"status": "degraded", "workers": 0, "reason": str(e)[:200]}
```

> **Mejora vs hppt:** hppt deshabilitó el healthcheck nativo en prod por cuelgues de `inspect ping`. MT lo reemplaza con un endpoint propio que tiene timeout estricto y nunca bloquea más de 3 s.

### Logging estructurado

```python
# app/core/logger.py — MT
import structlog
import logging
import sentry_sdk
from sentry_sdk.integrations.logging import LoggingIntegration
from sentry_sdk.integrations.celery import CeleryIntegration

def setup_logging(env: str, sentry_dsn: str | None):
    logging.basicConfig(format="%(message)s", level=logging.INFO)
    structlog.configure(
        processors=[
            structlog.processors.TimeStamper(fmt="iso"),
            structlog.contextvars.merge_contextvars,
            structlog.processors.add_log_level,
            structlog.processors.JSONRenderer(),
        ],
        wrapper_class=structlog.make_filtering_bound_logger(logging.INFO),
    )
    if sentry_dsn:
        sentry_sdk.init(
            dsn=sentry_dsn,
            environment=env,
            integrations=[CeleryIntegration(), LoggingIntegration(level=logging.INFO, event_level=logging.ERROR)],
            traces_sample_rate=0.1,
            profiles_sample_rate=0.05,
            send_default_pii=False,
        )
```

> **Mejora vs hppt:** hppt usa `logging` stdlib + tabla `system_logs`. MT añade structlog (JSON output) + Sentry (CeleryIntegration captura task failures automáticamente). ADR-019 ya lo prevé.

### Métricas Prometheus (opcional Fase 1.5)

`celery-prometheus-exporter` o equivalente, expuesto en `:9540`. No bloqueante para Fase 1; se añade cuando haya volumen.

### Flower (opcional, dashboard Celery)

```yaml
flower:
  image: mher/flower:latest
  command: celery --broker=redis://redis:6379/0 flower --port=5555 --basic_auth=${FLOWER_USER}:${FLOWER_PASS}
  ports: ["5555:5555"]
  depends_on: [redis]
```

Recomendación Fase 1: incluir Flower solo en compose dev; en prod queda detrás de Caddy con auth básico opcional.

---

## 6.6 Docker Compose

### `docker-compose.yml` (dev)

```yaml
services:
  redis:
    image: redis:7-alpine
    container_name: mt-redis
    healthcheck:
      test: ["CMD", "redis-cli", "ping"]
      interval: 15s
      timeout: 5s
      retries: 3

  backend:
    build: ./mt-pricing-backend
    container_name: mt-backend
    ports: ["8000:8000"]
    depends_on:
      redis:
        condition: service_healthy
    env_file: [.env]
    environment:
      - REDIS_URL=redis://redis:6379/0
    healthcheck:
      test: ["CMD", "python", "-c", "import httpx; httpx.get('http://localhost:8000/health', timeout=5).raise_for_status()"]
      interval: 30s
      timeout: 10s
      retries: 3
      start_period: 15s

  celery-worker-default:
    build: ./mt-pricing-backend
    container_name: mt-celery-default
    command: celery -A app.worker.celery_app worker --loglevel=info -Q default,audit -n default@%h --concurrency=2
    depends_on:
      redis: { condition: service_healthy }
      backend: { condition: service_healthy }
    env_file: [.env]
    environment:
      - REDIS_URL=redis://redis:6379/0

  celery-worker-imports:
    build: ./mt-pricing-backend
    container_name: mt-celery-imports
    # Imports son largos — concurrency 1 + prefetch 1 para evitar acaparar memoria
    command: celery -A app.worker.celery_app worker --loglevel=info -Q imports -n imports@%h --concurrency=1 --prefetch-multiplier=1
    depends_on: { redis: { condition: service_healthy }, backend: { condition: service_healthy } }
    env_file: [.env]
    environment: { REDIS_URL: "redis://redis:6379/0" }

  celery-worker-pricing:
    build: ./mt-pricing-backend
    container_name: mt-celery-pricing
    command: celery -A app.worker.celery_app worker --loglevel=info -Q pricing,comparator,images -n pricingmix@%h --concurrency=4
    depends_on: { redis: { condition: service_healthy }, backend: { condition: service_healthy } }
    env_file: [.env]
    environment: { REDIS_URL: "redis://redis:6379/0" }

  celery-worker-notifications:
    build: ./mt-pricing-backend
    container_name: mt-celery-notif
    command: celery -A app.worker.celery_app worker --loglevel=info -Q notifications -n notif@%h --concurrency=2
    depends_on: { redis: { condition: service_healthy }, backend: { condition: service_healthy } }
    env_file: [.env]
    environment: { REDIS_URL: "redis://redis:6379/0" }

  celery-beat:
    # ADR-046: DatabaseScheduler editable. State vive en public.job_definitions
    # (Postgres), no en archivo. Por eso no hay volumen celerybeat_data.
    build: ./mt-pricing-backend
    container_name: mt-celery-beat
    command: celery -A app.worker.celery_app beat --loglevel=info --scheduler app.scheduler.database_scheduler:DatabaseScheduler
    depends_on:
      redis: { condition: service_healthy }
      backend: { condition: service_healthy }    # garantiza que Alembic ya aplicó job_definitions
    env_file: [.env]
    environment:
      - REDIS_URL=redis://redis:6379/0
      - DATABASE_URL=${DATABASE_URL}             # Postgres (Supabase) — para leer job_definitions
    healthcheck:
      # Verifica que el scheduler esté leyendo la tabla. El scheduler escribe un
      # heartbeat en public.job_scheduler_heartbeat cada 30s; el healthcheck mira
      # que el último heartbeat sea < 90s.
      test: ["CMD", "python", "-c", "from app.scheduler.database_scheduler import check_heartbeat; check_heartbeat(max_age_seconds=90)"]
      interval: 60s
      timeout: 10s
      retries: 3
      start_period: 30s

  flower:
    image: mher/flower:latest
    container_name: mt-flower
    command: celery --broker=redis://redis:6379/0 flower --port=5555
    ports: ["5555:5555"]
    depends_on: [redis]
    profiles: ["debug"]

  # NOTA (v1.1): el volumen celerybeat_data fue removido. DatabaseScheduler persiste
  # state en public.job_definitions (last_run_at, next_run_at) — no en archivo local.
```

### `docker-compose.prod.yml` (override)

```yaml
services:
  celery-beat:
    deploy: { replicas: 1 }    # crítico: solo UNA instancia
    restart: unless-stopped
  celery-worker-default:        { restart: unless-stopped }
  celery-worker-imports:        { restart: unless-stopped }
  celery-worker-pricing:        { restart: unless-stopped }
  celery-worker-notifications:  { restart: unless-stopped }
```

> **Diferencia clave vs hppt:** hppt corre **un solo** `celery-worker` que escucha todas las queues. MT lo separa en 4 workers por dominio para que un import lento no bloquee notifications, y para escalar independiente.

### Caddyfile (extracto)

```
mt.br-innovation.com {
    handle /api/* { reverse_proxy backend:8000 }
    handle /flower/* { reverse_proxy flower:5555 }   # opcional
    handle { reverse_proxy frontend:3000 }
}
```

---

## 6.7 Tests

### Configuración eager para pytest

`mt-pricing-backend/conftest.py`:

```python
import pytest
from app.worker import celery_app

@pytest.fixture(autouse=True)
def celery_eager(monkeypatch):
    """Ejecuta tasks sincrónicamente en tests; evita Redis."""
    monkeypatch.setattr(celery_app.conf, "task_always_eager", True)
    monkeypatch.setattr(celery_app.conf, "task_eager_propagates", True)
    monkeypatch.setattr(celery_app.conf, "task_store_eager_result", True)
```

### Test ejemplo

```python
# tests/tasks/test_imports.py
def test_import_pim_creates_run_and_processes(supabase_test_db, sample_pim_csv):
    from app.tasks.imports.import_pim import import_pim

    run_id = "test-run-1"
    supabase_test_db.table("job_runs").insert({"run_id": run_id, "task_name": "mt.imports.import_pim",
                                                "queue": "imports", "status": "PENDING"}).execute()
    result = import_pim.apply(args=[run_id, sample_pim_csv]).get()
    assert result["rows_processed"] > 0
    final = supabase_test_db.table("job_runs").select("status").eq("run_id", run_id).single().execute().data
    assert final["status"] == "SUCCESS"

def test_import_pim_idempotent_on_retry(supabase_test_db, sample_pim_csv):
    from app.tasks.imports.import_pim import import_pim
    run_id = "test-run-2"
    # Primer run
    import_pim.apply(args=[run_id, sample_pim_csv]).get()
    count1 = supabase_test_db.table("products").select("count", count="exact").execute().count
    # Segunda corrida con el mismo input → no duplica
    import_pim.apply(args=[run_id, sample_pim_csv]).get()
    count2 = supabase_test_db.table("products").select("count", count="exact").execute().count
    assert count1 == count2
```

### Patrón mock Redis (cuando no eager)

Para tests de integración con broker real, usar `pytest-redis` o `fakeredis`:

```python
@pytest.fixture
def redis_broker(redis_proc):
    return f"redis://{redis_proc.host}:{redis_proc.port}/0"
```

---

## 6.8 Resumen de mejoras propuestas vs hppt

| # | Mejora | Justificación |
|---|--------|---------------|
| M1 | Queues nombradas + routing | hppt usa solo `default`. MT necesita aislar imports largos de notifications cortos. |
| M2 | Workers separados por queue (4 contenedores) | Evita head-of-line blocking entre dominios. |
| M3 | Beat schedule en código (Celery beat puro) | hppt tiene dual APScheduler+Celery; MT consolida. |
| M4 | Endpoint `/health/celery` con timeout estricto | hppt deshabilitó healthcheck nativo. |
| M5 | structlog + Sentry desde día 1 | hppt usa `logging` stdlib y carece de Sentry. |
| M6 | Tabla `job_runs` con `processing_status` JSONB | Inspirado en `job_run_history.processing_status` de hppt; mantiene polling-friendly. |
| M7 | `task_always_eager` en pytest fixtures | hppt no tiene tests Celery; MT instituye desde Sprint 1. |
| M8 | Convención de nombre `mt.<module>.<task>` | Permite routing por glob `mt.imports.*` → queue. |
| M9 | `acks_late + reject_on_worker_lost` global | hppt lo aplica solo en algunas tasks; MT lo deja como default. |
| M10 | Flower opcional vía `profiles: [debug]` | Inspección visual sin sumar al runtime productivo Fase 1. |

---

## 6.9 Checklist implementación Sprint 1

- [ ] Crear `mt-pricing-backend/app/celery_config.py` (queues + beat).
- [ ] Crear `mt-pricing-backend/app/worker.py` con `autodiscover_tasks`.
- [ ] Crear estructura `app/tasks/{imports,pricing,images,comparator,notifications,audit}/__init__.py`.
- [ ] Crear `app/tasks/_helpers.py` (`run_sync`, `update_job_run`).
- [ ] Migración Supabase `job_runs`.
- [ ] Endpoint `/health/celery` en `app/routers/health.py`.
- [ ] `docker-compose.yml` con 4 workers + beat + redis healthcheck.
- [ ] Config Sentry + structlog en `app/core/logger.py`.
- [ ] `conftest.py` con `task_always_eager` fixture.
- [ ] Sprint 1: implementar 1 task por queue (smoke test): `mt.imports.import_excel_demo`, `mt.pricing.recalculate_sku`, `mt.notifications.send_daily_digest`, `mt.audit.log_event_async`.
- [ ] Sprint 2-4: completar las 26 tasks listadas en §6.3.

## TODOs / dudas pendientes

1. ~~**¿Beat scheduler debe ser editable vía UI?**~~ **Resuelto (v1.1, ADR-046)**: SÍ, DatabaseScheduler editable con tabla `job_definitions`. Ver §6.4.
2. **¿Redis Cluster o single?** Fase 1: single con persistencia AOF. Si volumen crece, Sentinel.
3. **`mirror_external_image` y derecho de uso de imágenes.** Verificar con legal antes de implementar — ADR-013 menciona storage pero no derecho de imagen.
4. **Decisión Sprint 0 (ADR-046).** Validar si `celery-sqlalchemy-scheduler` (librería existente) encaja con SQLAlchemy 2.0 async; si no, implementar scheduler custom de ~150 líneas en `app/scheduler/database_scheduler.py`. Owner: TI MT + Pablo.
