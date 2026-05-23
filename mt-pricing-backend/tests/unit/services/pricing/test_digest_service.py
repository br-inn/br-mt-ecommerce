"""Tests unitarios para DigestService (US-1B-02-07).

3 escenarios:
  1. Sin prices el día → todos los conteos en 0.
  2. Con prices pending_review → conteo correcto.
  3. Con prices escalados → conteo escalados correcto.

Usa mocks de AsyncSession — sin DB real.
"""

from __future__ import annotations

from datetime import date
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.services.pricing.digest_service import DigestService


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_session(status_rows: list[tuple[str, int]], escalated_count: int) -> AsyncMock:
    """Construye un AsyncSession mock con resultados configurados.

    status_rows: lista de (status_str, count) que simula el GROUP BY.
    escalated_count: escalar para el count de escalados.
    """
    session = AsyncMock()

    # Primera llamada → result del GROUP BY status
    mock_result_status = MagicMock()
    mock_result_status.__iter__ = MagicMock(
        return_value=iter([MagicMock(status=s, cnt=c) for s, c in status_rows])
    )

    # Segunda llamada → result del count escalados
    mock_result_esc = MagicMock()
    mock_result_esc.scalar_one_or_none = MagicMock(return_value=escalated_count)

    session.execute = AsyncMock(side_effect=[mock_result_status, mock_result_esc])
    return session


# ---------------------------------------------------------------------------
# Escenario 1: sin prices el día
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_get_daily_summary_empty_day() -> None:
    """Sin ningún price creado el día → todos los conteos son 0."""
    session = _make_session(status_rows=[], escalated_count=0)
    svc = DigestService(session)

    summary = await svc.get_daily_summary(date(2026, 5, 12))

    assert summary["date"] == "2026-05-12"
    assert summary["pending_review"] == 0
    assert summary["auto_approved"] == 0
    assert summary["approved"] == 0
    assert summary["escalated"] == 0
    assert summary["total"] == 0


# ---------------------------------------------------------------------------
# Escenario 2: con prices pending_review
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_get_daily_summary_with_pending_review() -> None:
    """Con prices en pending_review → conteo correcto, otros en 0."""
    session = _make_session(
        status_rows=[
            ("pending_review", 5),
            ("auto_approved", 3),
        ],
        escalated_count=0,
    )
    svc = DigestService(session)

    summary = await svc.get_daily_summary(date(2026, 5, 12))

    assert summary["pending_review"] == 5
    assert summary["auto_approved"] == 3
    assert summary["approved"] == 0
    assert summary["escalated"] == 0
    assert summary["total"] == 8  # 5 + 3


# ---------------------------------------------------------------------------
# Escenario 3: con prices escalados
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_get_daily_summary_with_escalated() -> None:
    """Con prices escalados → conteo escalados refleja el valor correcto."""
    session = _make_session(
        status_rows=[
            ("pending_review", 2),
            ("auto_approved", 10),
            ("approved", 4),
        ],
        escalated_count=3,
    )
    svc = DigestService(session)

    summary = await svc.get_daily_summary(date(2026, 5, 12))

    assert summary["pending_review"] == 2
    assert summary["auto_approved"] == 10
    assert summary["approved"] == 4
    assert summary["escalated"] == 3
    assert summary["total"] == 16  # 2 + 10 + 4


# ---------------------------------------------------------------------------
# Escenario bonus: fecha correctamente formateada
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_get_daily_summary_date_format() -> None:
    """La clave `date` del summary siempre retorna formato ISO-8601."""
    session = _make_session(status_rows=[], escalated_count=0)
    svc = DigestService(session)

    summary = await svc.get_daily_summary(date(2026, 1, 5))

    assert summary["date"] == "2026-01-05"
