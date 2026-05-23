"""Unit tests para `FXRateService` — sin DB (mocks).

Cobertura sin trigger (los AC del trigger van en `tests/data/test_fx_rates_trigger.py`):

- ``rate_at`` con identidad (from==to) devuelve rate=1 sin tocar DB.
- ``rate_at`` con par no existente lanza ``FXRateNotFoundError``.
- ``rate_at`` con par existente devuelve la fila vigente.
- ``create_rate`` con `rate <= 0` lanza ``FXRatePositiveError`` (pre-flight).
- ``create_rate`` con identidad fuerza rate=1 antes de flush.
- ``create_rate`` con currency inactiva lanza ``InvalidFXCurrencyError``.
- ``create_rate`` con `allow_retroactive=true` y sin reason lanza error.
- ``create_rate`` traduce `IntegrityError` con mensaje
  ``fx_retroactive_not_allowed`` a ``FXRateRetroactiveBlockedError``.
"""

from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal
from typing import Any
from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest
from sqlalchemy.exc import IntegrityError

from app.db.models.pricing import FXRate
from app.services.fx import (
    FXRateDomainError,
    FXRateNotFoundError,
    FXRateRetroactiveBlockedError,
    FXRateService,
    InvalidFXCurrencyError,
)
from app.services.fx.fx_rate_service import FXRatePositiveError

pytestmark = pytest.mark.unit


# ---------------------------------------------------------------------------
# Fakes
# ---------------------------------------------------------------------------
class _FakeCurrency:
    def __init__(self, code: str, *, active: bool = True) -> None:
        self.code = code
        self.active = active


class _FakeUser:
    def __init__(self) -> None:
        self.id = uuid4()
        self.email = "ti@mt.ae"


def _make_fx_row(
    *,
    from_c: str,
    to_c: str,
    rate: Decimal | float = 4.18,
    effective_from: datetime | None = None,
    effective_to: datetime | None = None,
) -> FXRate:
    """Crea una instancia ORM no-persisted para tests."""
    row = FXRate(
        from_currency=from_c,
        to_currency=to_c,
        rate=Decimal(str(rate)),
        effective_from=effective_from or datetime(2026, 4, 1, tzinfo=UTC),
        effective_to=effective_to,
        source="manual",
    )
    row.id = uuid4()  # type: ignore[assignment]
    return row


def _make_session(
    *,
    currencies: dict[str, _FakeCurrency] | None = None,
    rate_row: FXRate | None = None,
    flush_raises: Exception | None = None,
) -> Any:
    """Mock de AsyncSession para FXRateService.

    - ``session.get(Currency, code)`` → resuelve desde dict.
    - ``session.execute(select(FXRate)…)`` → devuelve `rate_row` si se pasó.
    - ``session.flush()`` → opcional raise.
    - ``session.add()``, ``session.rollback()`` → no-op AsyncMock.
    """
    currencies = currencies or {}

    async def _get(model: Any, key: Any) -> Any:
        # Distinguimos por nombre de modelo (Currency vs FXRate).
        name = getattr(model, "__name__", "")
        if name == "Currency":
            return currencies.get(key)
        return None

    async def _execute(stmt: Any) -> Any:
        result = MagicMock()
        if rate_row is not None:
            result.scalar_one_or_none = MagicMock(return_value=rate_row)
            scalars_obj = MagicMock()
            scalars_obj.all = MagicMock(return_value=[rate_row])
            result.scalars = MagicMock(return_value=scalars_obj)
        else:
            result.scalar_one_or_none = MagicMock(return_value=None)
            scalars_obj = MagicMock()
            scalars_obj.all = MagicMock(return_value=[])
            result.scalars = MagicMock(return_value=scalars_obj)
        return result

    async def _flush() -> None:
        if flush_raises is not None:
            raise flush_raises

    session = MagicMock()
    session.get = AsyncMock(side_effect=_get)
    session.execute = AsyncMock(side_effect=_execute)
    session.flush = AsyncMock(side_effect=_flush)
    session.add = MagicMock()
    session.rollback = AsyncMock()
    return session


def _build_service(
    *,
    currencies: dict[str, _FakeCurrency] | None = None,
    rate_row: FXRate | None = None,
    flush_raises: Exception | None = None,
) -> tuple[FXRateService, list[dict]]:
    session = _make_session(currencies=currencies, rate_row=rate_row, flush_raises=flush_raises)
    svc = FXRateService(session)
    audit_calls: list[dict] = []

    async def _record(**kw: Any) -> None:
        audit_calls.append(kw)

    svc.audit.record = AsyncMock(side_effect=_record)  # type: ignore[assignment]
    return svc, audit_calls


# ---------------------------------------------------------------------------
# rate_at
# ---------------------------------------------------------------------------
async def test_rate_at_identity_returns_one_without_db_hit() -> None:
    svc, _ = _build_service()
    result = await svc.rate_at("AED", "AED", datetime.now(UTC))
    assert result.rate == Decimal("1")
    assert result.from_currency == "AED"
    assert result.to_currency == "AED"
    assert result.effective_to is None
    # No execute call needed for identity.
    assert svc.session.execute.await_count == 0  # type: ignore[union-attr]


async def test_rate_at_returns_existing_row() -> None:
    row = _make_fx_row(from_c="EUR", to_c="AED", rate=4.29)
    svc, _ = _build_service(rate_row=row)
    out = await svc.rate_at("EUR", "AED", datetime.now(UTC))
    assert out is row


async def test_rate_at_missing_raises() -> None:
    svc, _ = _build_service(rate_row=None)
    with pytest.raises(FXRateNotFoundError) as ei:
        await svc.rate_at("EUR", "AED", datetime.now(UTC))
    assert ei.value.code == "fx_rate_not_found_at_effective_at"


# ---------------------------------------------------------------------------
# create_rate
# ---------------------------------------------------------------------------
async def test_create_rate_rejects_non_positive_rate() -> None:
    svc, _ = _build_service(
        currencies={
            "EUR": _FakeCurrency("EUR"),
            "AED": _FakeCurrency("AED"),
        }
    )
    with pytest.raises(FXRatePositiveError):
        await svc.create_rate(
            from_code="EUR",
            to_code="AED",
            rate=Decimal("0"),
            effective_from=datetime(2026, 6, 12, tzinfo=UTC),
            actor=_FakeUser(),
        )


async def test_create_rate_rejects_inactive_currency() -> None:
    svc, _ = _build_service(
        currencies={
            "EUR": _FakeCurrency("EUR", active=False),
            "AED": _FakeCurrency("AED"),
        }
    )
    with pytest.raises(InvalidFXCurrencyError) as ei:
        await svc.create_rate(
            from_code="EUR",
            to_code="AED",
            rate=Decimal("4.18"),
            effective_from=datetime(2026, 6, 12, tzinfo=UTC),
            actor=_FakeUser(),
        )
    assert ei.value.code == "fx_invalid_currency"


async def test_create_rate_unknown_currency_rejected() -> None:
    svc, _ = _build_service(currencies={"AED": _FakeCurrency("AED")})
    with pytest.raises(InvalidFXCurrencyError):
        await svc.create_rate(
            from_code="ZZZ",
            to_code="AED",
            rate=Decimal("1.5"),
            effective_from=datetime(2026, 6, 12, tzinfo=UTC),
            actor=_FakeUser(),
        )


async def test_create_rate_identity_forces_rate_one() -> None:
    """from==to → rate forzado a 1 antes de flush (defensa en servicio)."""
    svc, audit = _build_service(currencies={"AED": _FakeCurrency("AED")})

    captured: dict[str, FXRate] = {}

    def _capture(obj: Any) -> None:
        if isinstance(obj, FXRate):
            captured["row"] = obj

    svc.session.add = MagicMock(side_effect=_capture)  # type: ignore[union-attr]

    await svc.create_rate(
        from_code="AED",
        to_code="AED",
        rate=Decimal("999"),
        effective_from=datetime(2026, 4, 1, tzinfo=UTC),
        actor=_FakeUser(),
    )

    assert captured["row"].rate == Decimal("1")
    assert len(audit) == 1
    assert audit[0]["action"] == "fx_rate.created"


async def test_create_rate_allow_retroactive_requires_reason() -> None:
    svc, _ = _build_service(currencies={"EUR": _FakeCurrency("EUR"), "AED": _FakeCurrency("AED")})
    with pytest.raises(FXRateDomainError) as ei:
        await svc.create_rate(
            from_code="EUR",
            to_code="AED",
            rate=Decimal("4.18"),
            effective_from=datetime(2026, 6, 12, tzinfo=UTC),
            actor=_FakeUser(),
            allow_retroactive=True,
            reason=None,
        )
    assert ei.value.code == "fx_retroactive_requires_reason"


async def test_create_rate_translates_trigger_retroactive_error() -> None:
    """Si el trigger lanza P0001 con `fx_retroactive_not_allowed`, el servicio
    debe rollback y traducir a ``FXRateRetroactiveBlockedError``."""
    err = IntegrityError(
        statement="INSERT INTO fx_rates",
        params=None,
        orig=Exception("fx_retroactive_not_allowed: blocked by trigger"),
    )
    svc, _ = _build_service(
        currencies={"EUR": _FakeCurrency("EUR"), "AED": _FakeCurrency("AED")},
        flush_raises=err,
    )
    with pytest.raises(FXRateRetroactiveBlockedError) as ei:
        await svc.create_rate(
            from_code="EUR",
            to_code="AED",
            rate=Decimal("4.18"),
            effective_from=datetime(2026, 1, 1, tzinfo=UTC),
            actor=_FakeUser(),
        )
    assert ei.value.code == "fx_retroactive_not_allowed"
    svc.session.rollback.assert_awaited()  # type: ignore[union-attr]


async def test_create_rate_happy_path_emits_audit() -> None:
    svc, audit = _build_service(
        currencies={"EUR": _FakeCurrency("EUR"), "AED": _FakeCurrency("AED")}
    )
    user = _FakeUser()
    out = await svc.create_rate(
        from_code="eur",
        to_code="aed",
        rate=Decimal("4.18"),
        effective_from=datetime(2026, 6, 12, tzinfo=UTC),
        source="manual",
        actor=user,
    )
    assert out.from_currency == "EUR"
    assert out.to_currency == "AED"
    assert out.rate == Decimal("4.18")
    assert out.created_by == user.id
    assert len(audit) == 1
    assert audit[0]["action"] == "fx_rate.created"
    assert audit[0]["entity_type"] == "fx_rate"


async def test_list_rates_filters() -> None:
    row = _make_fx_row(from_c="EUR", to_c="AED")
    svc, _ = _build_service(rate_row=row)
    rows = await svc.list_rates(from_code="EUR", to_code="AED", only_active=True)
    assert list(rows) == [row]
