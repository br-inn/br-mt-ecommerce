"""Tarea Celery beat `audit_partitions_ensure` (R-S2-08, US-1A-07-01).

Crea idempotentemente las particiones mensuales de `audit_events` para los
próximos N meses (default 2) si no existen. Migración inicial sólo cubre may/jun
2026 — sin esta task, julio 2026 fallaría todos los inserts a `audit_events`.

Schedule: cron daily 02:00 UTC (`0 2 * * *`). Idempotente — `CREATE TABLE IF
NOT EXISTS` no es válido para particiones, pero `pg_class` check sí.

Nombre de tarea Celery: `mt.audit.ensure_partitions` (alineado con el seed
existente en migration 001 `job_definitions.audit_partitions_ensure`).
"""

from __future__ import annotations

import logging
from datetime import date, datetime, timedelta, timezone
from typing import Any

from sqlalchemy import create_engine, text

from app.core.config import settings
from app.workers.worker import celery_app

logger = logging.getLogger(__name__)


# --------------------------------------------------------------------------
# Helpers
# --------------------------------------------------------------------------
def _month_partition_name(year: int, month: int) -> str:
    """Devuelve `audit_events_YYYY_MM` (zero-padded month)."""
    return f"audit_events_{year:04d}_{month:02d}"


def _month_bounds(year: int, month: int) -> tuple[date, date]:
    """Devuelve (first_day_of_month, first_day_of_next_month) para PARTITION FROM/TO."""
    start = date(year, month, 1)
    if month == 12:
        end = date(year + 1, 1, 1)
    else:
        end = date(year, month + 1, 1)
    return start, end


def _next_n_months(reference: datetime, n: int) -> list[tuple[int, int]]:
    """Devuelve [(year, month), ...] para los próximos N meses incluyendo el actual."""
    out: list[tuple[int, int]] = []
    y, m = reference.year, reference.month
    for _ in range(n):
        out.append((y, m))
        if m == 12:
            y += 1
            m = 1
        else:
            m += 1
    return out


def ensure_partition_exists(conn: Any, year: int, month: int) -> bool:
    """Crea la partición si no existe. Devuelve True si la creó, False si ya estaba.

    Usa `pg_class` para verificar existencia (CREATE TABLE PARTITION OF no
    soporta IF NOT EXISTS).
    """
    name = _month_partition_name(year, month)
    start, end = _month_bounds(year, month)

    exists = conn.execute(
        text("SELECT to_regclass(:name) IS NOT NULL AS exists").bindparams(name=name)
    ).scalar()

    if exists:
        return False

    # CREATE TABLE ... PARTITION OF — DDL no parametrizable, hacemos format
    # con valores ya validados (year/month son ints, name viene de _month_partition_name).
    conn.execute(
        text(
            f"CREATE TABLE {name} PARTITION OF audit_events "
            f"FOR VALUES FROM ('{start.isoformat()}') TO ('{end.isoformat()}');"
        )
    )
    logger.info(
        "audit_partitions.created",
        extra={"partition": name, "from": start.isoformat(), "to": end.isoformat()},
    )
    return True


# --------------------------------------------------------------------------
# Celery task
# --------------------------------------------------------------------------
@celery_app.task(
    bind=True,
    name="mt.audit.ensure_partitions",
    acks_late=True,
    ignore_result=False,
    autoretry_for=(Exception,),
    retry_backoff=True,
    retry_kwargs={"max_retries": 3},
)
def ensure_partitions(self: Any, months_ahead: int = 2) -> dict[str, Any]:
    """Asegura que `audit_events` tiene particiones para los próximos `months_ahead`.

    Args:
        months_ahead: cuántos meses (incluyendo el actual) garantizar. Default 2.

    Returns:
        dict con `created` (lista de nombres creados) y `existing` (los que ya estaban).
    """
    # Engine síncrono ad-hoc — la task corre en proceso Celery, no necesita asyncio.
    sync_url = str(settings.ALEMBIC_DATABASE_URL)
    engine = create_engine(sync_url, future=True)
    now = datetime.now(timezone.utc)

    created: list[str] = []
    existing: list[str] = []

    try:
        with engine.begin() as conn:
            for year, month in _next_n_months(now, months_ahead):
                name = _month_partition_name(year, month)
                was_created = ensure_partition_exists(conn, year, month)
                if was_created:
                    created.append(name)
                else:
                    existing.append(name)
    finally:
        engine.dispose()

    result = {
        "created": created,
        "existing": existing,
        "months_checked": months_ahead,
        "ran_at": now.isoformat(),
    }
    logger.info("audit_partitions.ensure_done", extra=result)
    return result
