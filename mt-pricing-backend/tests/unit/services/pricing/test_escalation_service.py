"""Unit tests para EscalationService (US-1B-02-08).

Idempotencia + delegate routing + audit/notification persistence.
Pure unit — usa fakes para session + repositorios para evitar dependencia
de Postgres real.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from typing import Any
from uuid import UUID, uuid4

import pytest

from app.services.pricing.escalation_service import (
    AUDIT_ACTION,
    DEFAULT_ESCALATION_HOURS,
    NOTIFICATION_KIND,
    EscalationService,
)


@dataclass
class _FakePrice:
    id: UUID = field(default_factory=uuid4)
    product_sku: str = "MT-FT-87-01"
    channel_id: UUID = field(default_factory=uuid4)
    scheme_code: str = "B2B-AED"
    amount: Any = "100.00"
    status: str = "pending_review"
    proposed_by: UUID | None = None
    escalated: bool = False
    escalated_at: datetime | None = None
    updated_at: datetime = field(default_factory=lambda: datetime.now(tz=UTC) - timedelta(hours=72))


@dataclass
class _FakeUser:
    id: UUID
    is_active: bool = True
    delegate_user_id: UUID | None = None
    role_id: UUID | None = None


@dataclass
class _AuditCall:
    entity_type: str
    entity_id: str
    action: str
    after: dict


@dataclass
class _NotifCall:
    recipient_user_id: UUID
    kind: str
    payload: dict


class _FakeAudit:
    def __init__(self) -> None:
        self.calls: list[_AuditCall] = []

    async def record(
        self,
        *,
        entity_type: str,
        entity_id: str,
        action: str,
        actor_id=None,
        actor_email=None,
        actor_role=None,
        before=None,
        after=None,
        payload_diff=None,
        reason=None,
        request_id=None,
        ip_address=None,
        user_agent=None,
    ):
        self.calls.append(
            _AuditCall(
                entity_type=entity_type, entity_id=entity_id, action=action, after=after or {}
            )
        )


class _FakeNotifs:
    def __init__(self) -> None:
        self.calls: list[_NotifCall] = []
        self._counter = 0

    async def create(self, *, recipient_user_id, kind, payload):
        self._counter += 1
        self.calls.append(
            _NotifCall(recipient_user_id=recipient_user_id, kind=kind, payload=payload)
        )

        @dataclass
        class _N:
            id: UUID

        return _N(id=uuid4())


class _FakeSession:
    def __init__(
        self,
        *,
        overdue: list[_FakePrice],
        users: dict[UUID, _FakeUser],
        fallback_user: _FakeUser | None,
    ) -> None:
        self._overdue = overdue
        self._users = users
        self._fallback_user = fallback_user
        self.flush_count = 0

    async def execute(self, stmt):
        text = str(stmt).lower()
        if "from prices" in text:
            return _FakeResult(self._overdue)
        if "from users" in text and "join roles" in text:
            return _FakeResult([self._fallback_user] if self._fallback_user else [])
        return _FakeResult([])

    async def get(self, model, key):
        return self._users.get(key)

    async def flush(self) -> None:
        self.flush_count += 1


class _FakeResult:
    def __init__(self, items: list) -> None:
        self._items = items

    def scalars(self):
        return iter(self._items)

    def scalar_one_or_none(self):
        return self._items[0] if self._items else None


def _make_service(
    *,
    overdue: list[_FakePrice],
    users: dict[UUID, _FakeUser] | None = None,
    fallback: _FakeUser | None = None,
) -> tuple[EscalationService, _FakeSession, _FakeAudit, _FakeNotifs]:
    session = _FakeSession(overdue=overdue, users=users or {}, fallback_user=fallback)
    service = EscalationService(session)  # type: ignore[arg-type]
    audit = _FakeAudit()
    notifs = _FakeNotifs()
    service.audit = audit  # type: ignore[assignment]
    service.notifications = notifs  # type: ignore[assignment]
    return service, session, audit, notifs


def test_default_window_is_48h() -> None:
    assert DEFAULT_ESCALATION_HOURS == 48


async def test_escalate_with_delegate_routes_notification() -> None:
    proposer_id = uuid4()
    delegate_id = uuid4()
    proposer = _FakeUser(id=proposer_id, delegate_user_id=delegate_id)
    delegate = _FakeUser(id=delegate_id)
    price = _FakePrice(proposed_by=proposer_id)
    service, session, audit, notifs = _make_service(
        overdue=[price],
        users={proposer_id: proposer, delegate_id: delegate},
    )

    summary = await service.run_sweep()

    assert summary["checked"] == 1
    assert summary["escalated"] == 1
    assert price.escalated is True
    assert price.escalated_at is not None
    assert len(notifs.calls) == 1
    assert notifs.calls[0].recipient_user_id == delegate_id
    assert notifs.calls[0].kind == NOTIFICATION_KIND
    assert notifs.calls[0].payload["no_delegate"] is False
    assert audit.calls[0].action == AUDIT_ACTION
    assert audit.calls[0].after["recipient_reason"] == "delegate"


async def test_escalate_no_delegate_uses_fallback_role() -> None:
    proposer_id = uuid4()
    proposer = _FakeUser(id=proposer_id, delegate_user_id=None)
    fallback = _FakeUser(id=uuid4())
    price = _FakePrice(proposed_by=proposer_id)
    service, _, audit, notifs = _make_service(
        overdue=[price],
        users={proposer_id: proposer},
        fallback=fallback,
    )

    summary = await service.run_sweep()

    assert summary["escalated"] == 1
    assert notifs.calls[0].recipient_user_id == fallback.id
    assert notifs.calls[0].payload["no_delegate"] is True
    assert audit.calls[0].after["recipient_reason"] == "fallback"


async def test_escalate_inactive_delegate_falls_back() -> None:
    proposer_id = uuid4()
    delegate_id = uuid4()
    proposer = _FakeUser(id=proposer_id, delegate_user_id=delegate_id)
    inactive_delegate = _FakeUser(id=delegate_id, is_active=False)
    fallback = _FakeUser(id=uuid4())
    price = _FakePrice(proposed_by=proposer_id)
    service, _, _, notifs = _make_service(
        overdue=[price],
        users={proposer_id: proposer, delegate_id: inactive_delegate},
        fallback=fallback,
    )

    await service.run_sweep()
    assert notifs.calls[0].recipient_user_id == fallback.id


async def test_escalate_already_escalated_is_idempotent() -> None:
    price = _FakePrice(escalated=True)
    service, _, audit, notifs = _make_service(overdue=[price])

    summary = await service.run_sweep()

    assert summary["details"][0]["skipped"] is True
    assert summary["details"][0]["reason"] == "already_escalated"
    assert summary["escalated"] == 0
    assert notifs.calls == []
    assert audit.calls == []


async def test_escalate_no_proposer_no_recipient_still_audits() -> None:
    price = _FakePrice(proposed_by=None)
    service, _, audit, notifs = _make_service(overdue=[price], fallback=None)

    summary = await service.run_sweep()

    assert summary["escalated"] == 1
    assert price.escalated is True
    assert notifs.calls == []
    assert audit.calls[0].after["recipient_reason"] == "none"
    assert audit.calls[0].after["notification_id"] is None


async def test_run_sweep_processes_multiple_prices() -> None:
    proposer_id = uuid4()
    fallback = _FakeUser(id=uuid4())
    proposer = _FakeUser(id=proposer_id, delegate_user_id=None)
    overdue = [_FakePrice(proposed_by=proposer_id) for _ in range(3)]
    service, _, audit, notifs = _make_service(
        overdue=overdue,
        users={proposer_id: proposer},
        fallback=fallback,
    )

    summary = await service.run_sweep()

    assert summary["checked"] == 3
    assert summary["escalated"] == 3
    assert all(p.escalated for p in overdue)
    assert len(notifs.calls) == 3
    assert len(audit.calls) == 3


@pytest.mark.parametrize("window", [24, 72, 96])
async def test_window_hours_propagates_to_summary(window: int) -> None:
    service, _, _, _ = _make_service(overdue=[])
    service.window_hours = window
    summary = await service.run_sweep()
    assert summary["window_hours"] == window
