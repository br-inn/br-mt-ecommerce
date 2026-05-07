"""Unit tests para `CurrencyService` — sin DB (fakes in-memory).

Cobertura:
- list_all devuelve currencies en orden code ASC.
- set_active activate-then-deactivate con audit.
- set_active idempotente si ya está en el target state.
- set_active(false) sobre currency con `is_base=true` lanza
  ``CannotDeactivateBaseCurrencyError`` (422).
- set_active sobre currency inexistente lanza ``CurrencyNotFoundError`` (404).
"""

from __future__ import annotations

from typing import Any
from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest

from app.services.currencies import (
    CannotDeactivateBaseCurrencyError,
    CurrencyNotFoundError,
    CurrencyService,
)

pytestmark = pytest.mark.unit


# ---------------------------------------------------------------------------
# Fakes
# ---------------------------------------------------------------------------
class _FakeCurrency:
    def __init__(
        self,
        code: str,
        name: str,
        symbol: str | None = None,
        decimals: int = 2,
        is_base: bool = False,
        active: bool = True,
    ) -> None:
        self.code = code
        self.name = name
        self.symbol = symbol
        self.decimals = decimals
        self.is_base = is_base
        self.active = active


class _FakeUser:
    def __init__(self) -> None:
        self.id = uuid4()
        self.email = "ti@mt.ae"


def _make_session_with(currencies: dict[str, _FakeCurrency]) -> tuple[Any, list[dict]]:
    """Construye un `AsyncSession` mock que responde a:

    - ``session.get(Currency, code)`` → fake row o None.
    - ``session.execute(select(...))`` → list_all.
    - ``session.flush()`` no-op.

    Devuelve también una lista compartida donde se acumulan los audit events
    creados (vía `AuditRepository.record` parcheado).
    """
    audit_calls: list[dict] = []

    async def _get(_model: Any, code: str) -> _FakeCurrency | None:
        return currencies.get(code)

    async def _execute(stmt: Any) -> Any:
        rows = sorted(currencies.values(), key=lambda c: c.code)
        scalars_obj = MagicMock()
        scalars_obj.all = MagicMock(return_value=rows)
        result = MagicMock()
        result.scalars = MagicMock(return_value=scalars_obj)
        return result

    async def _flush() -> None:
        return None

    async def _record(**kw: Any) -> None:
        audit_calls.append(kw)

    session = MagicMock()
    session.get = AsyncMock(side_effect=_get)
    session.execute = AsyncMock(side_effect=_execute)
    session.flush = AsyncMock(side_effect=_flush)
    return session, audit_calls


def _build_service(
    currencies: dict[str, _FakeCurrency],
) -> tuple[CurrencyService, list[dict]]:
    session, audit_calls = _make_session_with(currencies)
    svc = CurrencyService(session)

    # Reemplazamos audit.record con un fake que captura kwargs.
    async def _record(**kw: Any) -> None:
        audit_calls.append(kw)

    svc.audit.record = AsyncMock(side_effect=_record)  # type: ignore[assignment]
    return svc, audit_calls


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------
async def test_list_all_returns_currencies_sorted() -> None:
    cs = {
        "EUR": _FakeCurrency("EUR", "Euro"),
        "AED": _FakeCurrency("AED", "Dirham", is_base=True),
        "USD": _FakeCurrency("USD", "Dollar", active=False),
    }
    svc, _ = _build_service(cs)
    rows = await svc.list_all()
    assert [r.code for r in rows] == ["AED", "EUR", "USD"]


async def test_set_active_deactivates_non_base_currency_with_audit() -> None:
    cs = {
        "AED": _FakeCurrency("AED", "Dirham", is_base=True),
        "SAR": _FakeCurrency("SAR", "Saudi Riyal", active=True),
    }
    svc, audit = _build_service(cs)
    user = _FakeUser()

    out = await svc.set_active("SAR", active=False, actor=user, reason="not used")

    assert out.active is False
    assert len(audit) == 1
    assert audit[0]["action"] == "currency.deactivated"
    assert audit[0]["entity_type"] == "currency"
    assert audit[0]["entity_id"] == "SAR"
    assert audit[0]["payload_diff"] == {"active": {"from": True, "to": False}}
    assert audit[0]["reason"] == "not used"


async def test_set_active_reactivates_with_audit() -> None:
    cs = {"USD": _FakeCurrency("USD", "Dollar", active=False)}
    svc, audit = _build_service(cs)
    user = _FakeUser()

    out = await svc.set_active("USD", active=True, actor=user)

    assert out.active is True
    assert len(audit) == 1
    assert audit[0]["action"] == "currency.activated"


async def test_set_active_is_idempotent() -> None:
    cs = {"USD": _FakeCurrency("USD", "Dollar", active=True)}
    svc, audit = _build_service(cs)
    user = _FakeUser()

    out = await svc.set_active("USD", active=True, actor=user)

    assert out.active is True
    assert len(audit) == 0  # No audit if no-op.


async def test_set_active_blocks_deactivating_base_currency() -> None:
    cs = {"AED": _FakeCurrency("AED", "Dirham", is_base=True, active=True)}
    svc, _ = _build_service(cs)
    user = _FakeUser()

    with pytest.raises(CannotDeactivateBaseCurrencyError) as exc_info:
        await svc.set_active("AED", active=False, actor=user)

    assert exc_info.value.code == "cannot_deactivate_base_currency"
    assert exc_info.value.status_code == 422


async def test_set_active_unknown_currency_raises_not_found() -> None:
    cs: dict[str, _FakeCurrency] = {}
    svc, _ = _build_service(cs)
    user = _FakeUser()

    with pytest.raises(CurrencyNotFoundError) as exc_info:
        await svc.set_active("XYZ", active=True, actor=user)

    assert exc_info.value.code == "currency_not_found"
    assert exc_info.value.status_code == 404


async def test_get_by_code_normalizes_input() -> None:
    cs = {"EUR": _FakeCurrency("EUR", "Euro")}
    svc, _ = _build_service(cs)
    out = await svc.get_by_code("  eur  ")
    assert out.code == "EUR"
