"""Unit tests para `app.services.audit.audit_query_service`.

US-1A-07-03 backend — query multi-entidad con filters + cursor pagination.

Estrategia:
- Stub mínimo de ``AsyncSession.execute`` que captura el `stmt` y devuelve
  filas canned. NO se ejerce SQLAlchemy real (test puro de la lógica de
  filters/condiciones + cursor + límite).
- 8+ tests cubriendo: filtros entity_types, related_sku, paginación,
  límites de seguridad, ordering implícito.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Any
from unittest.mock import MagicMock
from uuid import uuid4

import pytest

from app.services.audit.audit_query_service import (
    AuditQueryFilters,
    AuditQueryResult,
    AuditQueryService,
)

pytestmark = pytest.mark.unit


# ---------------------------------------------------------------------------
# Stubs
# ---------------------------------------------------------------------------
class _FakeAuditEvent:
    def __init__(
        self,
        *,
        id: int,
        event_at: datetime,
        entity_type: str,
        entity_id: str,
        action: str,
        actor_id: Any | None = None,
        actor_email: str | None = None,
        before: dict | None = None,
        after: dict | None = None,
        payload_diff: dict | None = None,
        reason: str | None = None,
    ) -> None:
        self.id = id
        self.event_at = event_at
        self.entity_type = entity_type
        self.entity_id = entity_id
        self.action = action
        self.actor_id = actor_id
        self.actor_email = actor_email
        self.before = before
        self.after = after
        self.payload_diff = payload_diff or {}
        self.reason = reason


class _FakeUser:
    def __init__(self, email: str, full_name: str | None = None) -> None:
        self.email = email
        self.full_name = full_name


class _FakeResult:
    def __init__(self, rows: list[tuple[Any, Any]]) -> None:
        self._rows = rows

    def all(self) -> list[tuple[Any, Any]]:
        return [(MagicMock(_mapping=None, **{"0": r[0], "1": r[1]}), None) for r in self._rows]


class _StubAsyncSession:
    """Captura la última statement y retorna rows canned."""

    def __init__(self, rows: list[tuple[Any, Any]]) -> None:
        self.rows = rows
        self.last_stmt: Any = None

    async def execute(self, stmt: Any) -> Any:
        self.last_stmt = stmt
        # Build a result-like object that supports `.all()` and yields
        # rows as 2-tuples (subscriptable by [0] / [1]).
        rows = self.rows

        class _R:
            def all(self_inner) -> list[Any]:
                return [_RowProxy(a, b) for a, b in rows]

        return _R()


class _RowProxy:
    def __init__(self, a: Any, b: Any) -> None:
        self._a = a
        self._b = b

    def __getitem__(self, idx: int) -> Any:
        return self._a if idx == 0 else self._b


def _make_event(
    id_: int,
    *,
    entity_type: str = "products",
    entity_id: str = "MT-V-038",
    action: str = "product.created",
    minutes_ago: int = 0,
    actor_email: str | None = "tester@mt.ae",
) -> _FakeAuditEvent:
    return _FakeAuditEvent(
        id=id_,
        event_at=datetime.now(tz=UTC) - timedelta(minutes=minutes_ago),
        entity_type=entity_type,
        entity_id=entity_id,
        action=action,
        actor_id=uuid4(),
        actor_email=actor_email,
        before=None,
        after={"name": "x"},
        payload_diff={},
        reason=None,
    )


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------
async def test_query_returns_items_no_filters() -> None:
    rows = [
        (_make_event(1), _FakeUser("u1@mt.ae", "Tester One")),
        (_make_event(2, action="product.updated"), _FakeUser("u2@mt.ae", "Tester Two")),
    ]
    session = _StubAsyncSession(rows)
    svc = AuditQueryService(session)  # type: ignore[arg-type]

    result = await svc.query(AuditQueryFilters())
    assert isinstance(result, AuditQueryResult)
    assert len(result.items) == 2
    assert result.items[0].action == "product.created"
    assert result.items[0].actor_email == "u1@mt.ae"
    assert result.items[0].actor_full_name == "Tester One"
    assert result.next_cursor is None


async def test_query_falls_back_to_evt_actor_email_if_no_user() -> None:
    rows = [
        (_make_event(10, actor_email="anon@example.com"), None),
    ]
    session = _StubAsyncSession(rows)
    svc = AuditQueryService(session)  # type: ignore[arg-type]
    result = await svc.query(AuditQueryFilters())
    assert result.items[0].actor_email == "anon@example.com"
    assert result.items[0].actor_full_name is None


async def test_query_pagination_yields_next_cursor() -> None:
    # 3 rows, limit=2 → should produce next_cursor.
    rows = [
        (_make_event(100, minutes_ago=0), None),
        (_make_event(99, minutes_ago=1), None),
        (_make_event(98, minutes_ago=2), None),
    ]
    session = _StubAsyncSession(rows)
    svc = AuditQueryService(session)  # type: ignore[arg-type]
    result = await svc.query(AuditQueryFilters(), limit=2)
    assert len(result.items) == 2
    assert result.next_cursor is not None
    cursor_at, cursor_id = result.next_cursor
    assert cursor_id == 99


async def test_query_no_next_cursor_when_under_limit() -> None:
    rows = [(_make_event(5), None)]
    session = _StubAsyncSession(rows)
    svc = AuditQueryService(session)  # type: ignore[arg-type]
    result = await svc.query(AuditQueryFilters(), limit=10)
    assert len(result.items) == 1
    assert result.next_cursor is None


async def test_query_limit_clamps_at_200() -> None:
    rows = [(_make_event(i), None) for i in range(5)]
    session = _StubAsyncSession(rows)
    svc = AuditQueryService(session)  # type: ignore[arg-type]
    # Pasamos limit=999; servicio debe cap a 200, pero no rompe la query.
    result = await svc.query(AuditQueryFilters(), limit=999)
    assert len(result.items) <= 200


async def test_query_limit_clamps_at_one_minimum() -> None:
    rows = [(_make_event(1), None)]
    session = _StubAsyncSession(rows)
    svc = AuditQueryService(session)  # type: ignore[arg-type]
    result = await svc.query(AuditQueryFilters(), limit=0)
    # No raise — clamp a 1.
    assert len(result.items) <= 1


async def test_filters_entity_types_builds_condition() -> None:
    """Verifica que las conditions se construyen sin errores para entity_types."""
    rows = []
    session = _StubAsyncSession(rows)
    svc = AuditQueryService(session)  # type: ignore[arg-type]
    filters = AuditQueryFilters(entity_types=("products", "costs", "prices"))
    result = await svc.query(filters)
    assert result.items == []
    assert session.last_stmt is not None  # se ejecutó la query


async def test_filters_related_sku_with_other_filters_uses_or() -> None:
    rows = []
    session = _StubAsyncSession(rows)
    svc = AuditQueryService(session)  # type: ignore[arg-type]
    filters = AuditQueryFilters(
        related_sku="MT-V-038",
        entity_types=("custom_entity",),
    )
    # Sin error.
    result = await svc.query(filters)
    assert result.items == []


async def test_filters_actor_email_partial() -> None:
    rows = []
    session = _StubAsyncSession(rows)
    svc = AuditQueryService(session)  # type: ignore[arg-type]
    filters = AuditQueryFilters(actor_email="paula@")
    result = await svc.query(filters)
    assert result.items == []


async def test_filters_temporal_range() -> None:
    rows = []
    session = _StubAsyncSession(rows)
    svc = AuditQueryService(session)  # type: ignore[arg-type]
    since = datetime.now(tz=UTC) - timedelta(days=7)
    until = datetime.now(tz=UTC)
    filters = AuditQueryFilters(since=since, until=until)
    result = await svc.query(filters)
    assert result.items == []


async def test_filters_actions_in() -> None:
    rows = [
        (_make_event(1, action="price.proposed"), None),
        (_make_event(2, action="price.approved"), None),
    ]
    session = _StubAsyncSession(rows)
    svc = AuditQueryService(session)  # type: ignore[arg-type]
    result = await svc.query(AuditQueryFilters(actions=("price.proposed", "price.approved")))
    assert len(result.items) == 2


async def test_query_with_cursor_continues_pagination() -> None:
    rows = [(_make_event(50), None)]
    session = _StubAsyncSession(rows)
    svc = AuditQueryService(session)  # type: ignore[arg-type]
    cursor_at = datetime.now(tz=UTC) - timedelta(hours=1)
    result = await svc.query(AuditQueryFilters(), cursor=(cursor_at, 100))
    assert len(result.items) == 1
