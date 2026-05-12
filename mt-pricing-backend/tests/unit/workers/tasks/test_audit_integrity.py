"""Tests unitarios para audit.nightly_integrity_check (ADR-076 / R-005).

Estrategia:
- No levanta DB real — toda la lógica de DB se mockea con MagicMock.
- Se prueba la lógica de recomputo de hashes y detección de tamper.
- La función ``_compute_row_hash`` se usa directamente para construir
  fixtures con hashes correctos (garantiza coherencia trigger ↔ Python).
"""

from __future__ import annotations

import hashlib
import json
from datetime import UTC, datetime, timedelta
from typing import Any
from unittest.mock import MagicMock, patch
from uuid import uuid4

import pytest

from app.workers.tasks.audit_integrity import _compute_row_hash, verify_chain_range

pytestmark = pytest.mark.unit

# ---------------------------------------------------------------------------
# Helpers de fixture
# ---------------------------------------------------------------------------

_BASE_TIME = datetime(2026, 5, 11, 0, 0, 0, tzinfo=UTC)


def _make_row(
    row_id: int,
    prev_hash: str,
    actor_id: str | None = None,
    entity_type: str = "price",
    entity_id: str = "sku-001",
    action: str = "update",
    payload_diff: dict | None = None,
    event_at: datetime | None = None,
    tamper: bool = False,
) -> MagicMock:
    """Crea una fila mock con hash correcto (o alterado si tamper=True)."""
    if payload_diff is None:
        payload_diff = {"price": row_id * 10}
    if event_at is None:
        event_at = _BASE_TIME + timedelta(seconds=row_id)

    correct_hash = _compute_row_hash(
        row_id=row_id,
        event_at=event_at,
        actor_id=actor_id,
        entity_type=entity_type,
        entity_id=entity_id,
        action=action,
        payload_diff=payload_diff,
        prev_hash=prev_hash,
    )

    row = MagicMock()
    row.id = row_id
    row.event_at = event_at
    row.actor_id = actor_id
    row.entity_type = entity_type
    row.entity_id = entity_id
    row.action = action
    row.payload_diff = payload_diff
    row.prev_hash = prev_hash
    row.current_hash = "deadbeef" * 8 if tamper else correct_hash  # 64 chars tampered
    return row


def _build_chain(n: int) -> list[MagicMock]:
    """Construye una cadena de n filas con hashes correctamente encadenados."""
    rows = []
    running_hash = ""
    for i in range(1, n + 1):
        row = _make_row(row_id=i, prev_hash=running_hash)
        running_hash = row.current_hash
        rows.append(row)
    return rows


def _mock_conn_with_rows(rows: list[MagicMock]) -> MagicMock:
    """Crea un mock de conexión SQLAlchemy síncrona que retorna las rows dadas."""
    conn = MagicMock()
    result_mock = MagicMock()
    result_mock.fetchall.return_value = rows
    conn.execute.return_value = result_mock
    return conn


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestVerifyChainRange:
    def test_passes_clean_chain(self) -> None:
        """10 filas con hashes correctos → verified=True, tampered_ids=[]."""
        rows = _build_chain(10)
        conn = _mock_conn_with_rows(rows)

        range_start = _BASE_TIME
        range_end = _BASE_TIME + timedelta(days=1)

        result = verify_chain_range(conn, range_start, range_end)

        assert result["verified"] is True
        assert result["rows_checked"] == 10
        assert result["tampered_ids"] == []

    def test_detects_tamper(self) -> None:
        """Una fila con hash alterado → verified=False, tampered_ids=[42]."""
        rows = _build_chain(3)
        # Insertar fila tampered en posición media (id=42 simulado)
        tampered = _make_row(row_id=42, prev_hash=rows[-1].current_hash, tamper=True)
        rows.append(tampered)
        conn = _mock_conn_with_rows(rows)

        range_start = _BASE_TIME
        range_end = _BASE_TIME + timedelta(days=1)

        result = verify_chain_range(conn, range_start, range_end)

        assert result["verified"] is False
        assert 42 in result["tampered_ids"]
        assert result["rows_checked"] == 4

    def test_empty_range(self) -> None:
        """Sin filas en el rango → verified=True, rows_checked=0."""
        conn = _mock_conn_with_rows([])

        range_start = _BASE_TIME
        range_end = _BASE_TIME + timedelta(days=1)

        result = verify_chain_range(conn, range_start, range_end)

        assert result["verified"] is True
        assert result["rows_checked"] == 0
        assert result["tampered_ids"] == []


class TestNightlyIntegrityCheckTask:
    """Tests de integración mínima del Celery task (mock de DB + settings)."""

    def test_task_passes_clean_chain(self) -> None:
        """Task completa con chain limpia → retorna verified=True."""
        rows = _build_chain(5)

        fake_result = MagicMock()
        fake_result.fetchall.return_value = rows

        fake_conn = MagicMock()
        fake_conn.__enter__ = MagicMock(return_value=fake_conn)
        fake_conn.__exit__ = MagicMock(return_value=False)
        fake_conn.execute.return_value = fake_result

        fake_engine = MagicMock()
        fake_engine.begin.return_value = fake_conn
        fake_engine.dispose = MagicMock()

        with (
            patch(
                "app.workers.tasks.audit_integrity.create_engine",
                return_value=fake_engine,
            ),
            patch(
                "app.workers.tasks.audit_integrity.settings.ALEMBIC_DATABASE_URL",
                "postgresql+psycopg://fake/db",
            ),
            patch(
                "app.workers.tasks.audit_integrity.settings.AUDIT_SIGNING_KEY"
            ) as mock_key,
        ):
            mock_key.get_secret_value.return_value = ""  # sin firma en test

            from app.workers.tasks.audit_integrity import nightly_integrity_check

            result = nightly_integrity_check.run()

        assert result["verified"] is True
        assert result["rows_checked"] == 5
        assert result["tampered_ids"] == []

    def test_task_detects_tamper(self) -> None:
        """Task con fila tampered → retorna verified=False, tampered_ids no vacío."""
        rows = _build_chain(2)
        tampered = _make_row(row_id=99, prev_hash=rows[-1].current_hash, tamper=True)
        rows.append(tampered)

        fake_result = MagicMock()
        fake_result.fetchall.return_value = rows

        fake_conn = MagicMock()
        fake_conn.__enter__ = MagicMock(return_value=fake_conn)
        fake_conn.__exit__ = MagicMock(return_value=False)
        fake_conn.execute.return_value = fake_result

        fake_engine = MagicMock()
        fake_engine.begin.return_value = fake_conn
        fake_engine.dispose = MagicMock()

        with (
            patch(
                "app.workers.tasks.audit_integrity.create_engine",
                return_value=fake_engine,
            ),
            patch(
                "app.workers.tasks.audit_integrity.settings.ALEMBIC_DATABASE_URL",
                "postgresql+psycopg://fake/db",
            ),
            patch(
                "app.workers.tasks.audit_integrity.settings.AUDIT_SIGNING_KEY"
            ) as mock_key,
        ):
            mock_key.get_secret_value.return_value = ""

            from app.workers.tasks.audit_integrity import nightly_integrity_check

            result = nightly_integrity_check.run()

        assert result["verified"] is False
        assert 99 in result["tampered_ids"]

    def test_task_empty_range(self) -> None:
        """Task sin filas en el rango → verified=True, rows_checked=0."""
        fake_result = MagicMock()
        fake_result.fetchall.return_value = []

        fake_conn = MagicMock()
        fake_conn.__enter__ = MagicMock(return_value=fake_conn)
        fake_conn.__exit__ = MagicMock(return_value=False)
        fake_conn.execute.return_value = fake_result

        fake_engine = MagicMock()
        fake_engine.begin.return_value = fake_conn
        fake_engine.dispose = MagicMock()

        with (
            patch(
                "app.workers.tasks.audit_integrity.create_engine",
                return_value=fake_engine,
            ),
            patch(
                "app.workers.tasks.audit_integrity.settings.ALEMBIC_DATABASE_URL",
                "postgresql+psycopg://fake/db",
            ),
            patch(
                "app.workers.tasks.audit_integrity.settings.AUDIT_SIGNING_KEY"
            ) as mock_key,
        ):
            mock_key.get_secret_value.return_value = ""

            from app.workers.tasks.audit_integrity import nightly_integrity_check

            result = nightly_integrity_check.run()

        assert result["verified"] is True
        assert result["rows_checked"] == 0
        assert result["tampered_ids"] == []
