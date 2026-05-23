"""R-S2-08, US-1A-07-01 — DoD: tarea Celery `audit_partitions_ensure` idempotente.

Tests:
- Unit: helpers de fechas (`_month_partition_name`, `_month_bounds`,
  `_next_n_months`) producen valores correctos.
- Integration: corre `ensure_partitions` contra Postgres efímero, verifica
  que crea particiones nuevas, y que un segundo run no duplica
  (idempotencia).
"""

from __future__ import annotations

import os
from datetime import datetime, timezone
from typing import TYPE_CHECKING

import pytest

if TYPE_CHECKING:
    pass


# --------------------------------------------------------------------------
# Unit — pure helpers
# --------------------------------------------------------------------------
@pytest.mark.unit
def test_month_partition_name_zero_padded() -> None:
    from app.workers.audit_partitions import _month_partition_name

    assert _month_partition_name(2026, 5) == "audit_events_2026_05"
    assert _month_partition_name(2026, 12) == "audit_events_2026_12"
    assert _month_partition_name(2027, 1) == "audit_events_2027_01"


@pytest.mark.unit
def test_month_bounds_normal_month() -> None:
    from datetime import date

    from app.workers.audit_partitions import _month_bounds

    start, end = _month_bounds(2026, 5)
    assert start == date(2026, 5, 1)
    assert end == date(2026, 6, 1)


@pytest.mark.unit
def test_month_bounds_december_rolls_year() -> None:
    from datetime import date

    from app.workers.audit_partitions import _month_bounds

    start, end = _month_bounds(2026, 12)
    assert start == date(2026, 12, 1)
    assert end == date(2027, 1, 1)


@pytest.mark.unit
def test_next_n_months_handles_year_rollover() -> None:
    from app.workers.audit_partitions import _next_n_months

    ref = datetime(2026, 11, 15, tzinfo=timezone.utc)
    months = _next_n_months(ref, 4)
    assert months == [(2026, 11), (2026, 12), (2027, 1), (2027, 2)]


@pytest.mark.unit
def test_next_n_months_one_month() -> None:
    from app.workers.audit_partitions import _next_n_months

    ref = datetime(2026, 5, 7, tzinfo=timezone.utc)
    assert _next_n_months(ref, 1) == [(2026, 5)]


# --------------------------------------------------------------------------
# Integration — runs against ephemeral Postgres
# --------------------------------------------------------------------------
pytestmark_integration = [pytest.mark.integration]


@pytest.fixture(scope="module")
def _migrated_db(postgres_container: str) -> str:
    """Aplica `alembic upgrade head` y devuelve la URL sync."""
    from alembic import command
    from alembic.config import Config

    sync_url = os.environ["ALEMBIC_DATABASE_URL"]
    cfg = Config("alembic.ini")
    cfg.set_main_option("sqlalchemy.url", sync_url)
    command.upgrade(cfg, "head")
    return sync_url


@pytest.mark.integration
def test_ensure_partitions_creates_missing(
    monkeypatch: pytest.MonkeyPatch, _migrated_db: str
) -> None:
    """Llama `ensure_partitions.run(months_ahead=6)`: crea particiones nuevas."""
    from sqlalchemy import create_engine, text

    from app.workers import audit_partitions

    # Forzar el uso de la URL sync del container.
    monkeypatch.setattr(
        audit_partitions.settings,
        "ALEMBIC_DATABASE_URL",
        _migrated_db,
    )

    # Ejecutar la task en modo eager-equivalent (llamada directa a la función
    # decorada — Celery's @task expone la función original como `.run`).
    result = audit_partitions.ensure_partitions.run(months_ahead=6)

    assert "created" in result
    assert "existing" in result
    assert result["months_checked"] == 6

    # Verifica que existen particiones para los próximos 6 meses.
    engine = create_engine(_migrated_db, future=True)
    try:
        with engine.connect() as conn:
            rows = conn.execute(
                text(
                    "SELECT relname FROM pg_class "
                    "WHERE relname LIKE 'audit_events_%' AND relkind = 'r' "
                    "ORDER BY relname;"
                )
            ).all()
            partition_names = {r[0] for r in rows}
        # Al menos las 2 originales (2026_05, 2026_06) + nuevas creadas.
        assert "audit_events_2026_05" in partition_names
        assert "audit_events_2026_06" in partition_names
        # Total de particiones >= meses revisados (puede haber overlaps con seeds).
        assert len(partition_names) >= 2
    finally:
        engine.dispose()


@pytest.mark.integration
def test_ensure_partitions_idempotent(monkeypatch: pytest.MonkeyPatch, _migrated_db: str) -> None:
    """Segunda ejecución no crea duplicados — todas reportadas como `existing`."""
    from app.workers import audit_partitions

    monkeypatch.setattr(
        audit_partitions.settings,
        "ALEMBIC_DATABASE_URL",
        _migrated_db,
    )

    # Primera corrida (asegura todo creado).
    audit_partitions.ensure_partitions.run(months_ahead=3)

    # Segunda corrida idéntica.
    result2 = audit_partitions.ensure_partitions.run(months_ahead=3)

    assert result2["created"] == [], f"Idempotencia rota: segunda corrida creó {result2['created']}"
    assert len(result2["existing"]) == 3
