"""Celery beat schedule estático — fallback para entornos sin DatabaseScheduler.

En producción usamos `app.scheduler.database_scheduler:DatabaseScheduler` (ADR-046)
que lee `job_definitions` desde Postgres. Sin embargo, mantenemos este registro
estático por dos razones:

1. **Documentación**: única fuente de verdad legible en código de qué tasks
   periódicas existen, su cadencia y argumentos. Cualquier nuevo job se debe
   registrar AQUÍ además de seedar `job_definitions`.
2. **Fallback**: en dev sin DB inicializada, o si DatabaseScheduler falla, el
   admin puede arrancar Beat con `--scheduler celery.beat:PersistentScheduler`
   y `app.conf.beat_schedule = BEAT_SCHEDULE` para no perder housekeeping.

Para activar: importar y aplicar en `make_celery()` (no se hace por default —
el DatabaseScheduler tiene precedencia).
"""

from __future__ import annotations

from celery.schedules import crontab

#: Schedule estático de tasks periódicas (espejo de `job_definitions` seeds).
#: Las claves son nombres lógicos (no necesariamente == task name).
BEAT_SCHEDULE: dict[str, dict] = {
    # ----- Audit partitions (R-S2-08, US-1A-07-01) -----
    # Crea particiones del mes siguiente si no existen. Idempotente.
    # Cron: diario 02:00 UTC (madrugada baja-tráfico Asia/Dubai = 06:00 local).
    "audit_partitions_ensure": {
        "task": "mt.audit.ensure_partitions",
        "schedule": crontab(hour="2", minute="0"),
        "args": (),
        "kwargs": {"months_ahead": 2},
        "options": {"queue": "audit"},
    },
    # ----- Pricing bulk recalc nocturno (US-1B-01-07, Sprint 5) -----
    # Recalcula precios de todo el catálogo activo. Idempotente — el batch
    # graba un audit_event ('nightly_recalc_batch') con el summary del run.
    # Cron: diario 02:00 Asia/Dubai (TIMEZONE settings.TIMEZONE) — el seed
    # de `job_definitions` (DatabaseScheduler) usa la misma cron expression
    # con timezone='Asia/Dubai'. Acá el crontab es UTC (Celery default), por
    # lo que se mantiene 02:00 como estándar fijo del fallback.
    "pricing_bulk_recalc_nightly": {
        "task": "mt.pricing.bulk_recalc",
        "schedule": crontab(hour="2", minute="0"),
        "args": (),
        "kwargs": {"source": "nightly_beat"},
        "options": {"queue": "pricing"},
    },
}


__all__ = ["BEAT_SCHEDULE"]
