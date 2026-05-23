"""Tests unitarios para ChannelTransitionService — US-1B-03-02 + US-1B-03-03.

Cubre:
- Transición inválida lanza ChannelTransitionError.
- Transición válida inactive → pre_launch (happy path).
- pre_launch → pilot con SKUs sin precio + override=False lanza
  MissingApprovedPricesError.
- pre_launch → pilot con SKUs sin precio + override=True → pilot_with_warnings=True.
- Transición a paused emite notificaciones a roles comercial + gerente.
- Transición paused → live emite notificaciones de reactivación.

asyncio_mode = "auto" (pyproject.toml), no se necesita @pytest.mark.asyncio.
Sin DB real — usa stubs/mocks.
"""

from __future__ import annotations

import uuid
from typing import Any
from unittest.mock import AsyncMock, MagicMock

import pytest

from app.services.channels.transition_service import (
    VALID_TRANSITIONS,
    ChannelTransitionError,
    ChannelTransitionService,
    MissingApprovedPricesError,
)

pytestmark = pytest.mark.unit

# ---------------------------------------------------------------------------
# Helpers / factories
# ---------------------------------------------------------------------------


def _make_channel(
    state: str = "inactive",
    code: str = "AMAZON_UAE",
) -> MagicMock:
    ch = MagicMock()
    ch.id = uuid.uuid4()
    ch.code = code
    ch.state = state
    ch.pilot_with_warnings = False
    return ch


def _make_user() -> MagicMock:
    u = MagicMock()
    u.id = uuid.uuid4()
    u.email = "actor@example.com"
    return u


def _make_session(
    channel: MagicMock | None = None,
    approved_skus: list[str] | None = None,
    role_users: list[MagicMock] | None = None,
) -> AsyncMock:
    """Construye una AsyncSession stub con comportamiento configurable.

    execute() es async pero devuelve un objeto cuyo .scalars() es sincrónico,
    para evitar errores "coroutine has no attribute 'all'".
    """
    session = AsyncMock()

    # session.get → devuelve el canal
    async def _get(model_cls: Any, pk: Any) -> Any:
        return channel

    session.get = _get

    call_count = {"n": 0}

    async def _execute(stmt: Any) -> Any:
        call_count["n"] += 1
        # Primera llamada a execute: query de precios (approved_skus)
        # Segunda y subsiguientes: query de usuarios por rol (role_users)
        if call_count["n"] == 1 and approved_skus is not None:
            rows = approved_skus
        else:
            rows = role_users or []

        # result.scalars() debe ser SINCRÓNICO — no AsyncMock
        scalars_mock = MagicMock()
        scalars_mock.all.return_value = rows

        result = MagicMock()
        result.scalars.return_value = scalars_mock
        return result

    session.execute = _execute
    session.add = MagicMock()
    session.flush = AsyncMock()

    return session


# ---------------------------------------------------------------------------
# FSM validation tests
# ---------------------------------------------------------------------------


def test_valid_transitions_map_completeness() -> None:
    """Todos los estados tienen una entrada en VALID_TRANSITIONS."""
    states = {"inactive", "pre_launch", "pilot", "live", "paused", "deprecated"}
    assert set(VALID_TRANSITIONS.keys()) == states


def test_deprecated_is_terminal() -> None:
    """deprecated no tiene transiciones salientes."""
    assert VALID_TRANSITIONS["deprecated"] == set()


# ---------------------------------------------------------------------------
# test_invalid_transition_raises
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_invalid_transition_raises() -> None:
    """inactive → live sin pasar por pre_launch → debe fallar."""
    channel = _make_channel(state="inactive")
    session = _make_session(channel=channel)
    service = ChannelTransitionService(session)

    with pytest.raises(ChannelTransitionError, match="inválida"):
        await service.transition(
            channel_id=channel.id,
            target_state="live",
            actor=_make_user(),
        )


@pytest.mark.asyncio
async def test_invalid_transition_deprecated_terminal() -> None:
    """deprecated → cualquier estado → debe fallar."""
    channel = _make_channel(state="deprecated")
    session = _make_session(channel=channel)
    service = ChannelTransitionService(session)

    with pytest.raises(ChannelTransitionError, match="terminal"):
        await service.transition(
            channel_id=channel.id,
            target_state="live",
            actor=_make_user(),
        )


# ---------------------------------------------------------------------------
# test_valid_transition_inactive_to_pre_launch
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_valid_transition_inactive_to_pre_launch() -> None:
    """Transición válida inactive → pre_launch sin validaciones especiales."""
    channel = _make_channel(state="inactive")
    session = _make_session(channel=channel)
    service = ChannelTransitionService(session)

    history, missing_skus = await service.transition(
        channel_id=channel.id,
        target_state="pre_launch",
        actor=_make_user(),
        comment="iniciar pre-lanzamiento",
    )

    assert channel.state == "pre_launch"
    assert channel.pilot_with_warnings is False
    assert missing_skus == []
    assert history.from_state == "inactive"
    assert history.to_state == "pre_launch"
    assert history.pilot_with_warnings is False
    session.add.assert_called()
    session.flush.assert_awaited()


# ---------------------------------------------------------------------------
# test_pilot_transition_missing_skus_without_override_raises
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_pilot_transition_missing_skus_without_override_raises() -> None:
    """pre_launch → pilot con SKUs sin precio aprobado + override=False → MissingApprovedPricesError."""
    channel = _make_channel(state="pre_launch", code="NOON_UAE")
    # approved_skus vacío → todos los SKUs faltan
    session = _make_session(channel=channel, approved_skus=[])
    service = ChannelTransitionService(session)

    with pytest.raises(MissingApprovedPricesError) as exc_info:
        await service.transition(
            channel_id=channel.id,
            target_state="pilot",
            actor=_make_user(),
            subset_skus=["MTV-1001", "MTV-1002"],
            override_warnings=False,
        )

    assert "MTV-1001" in exc_info.value.missing_skus
    assert "MTV-1002" in exc_info.value.missing_skus
    # Canal no debe haber sido mutado
    assert channel.state == "pre_launch"


@pytest.mark.asyncio
async def test_pilot_transition_missing_skus_with_override_succeeds() -> None:
    """pre_launch → pilot con SKUs faltantes + override=True → pilot_with_warnings=True."""
    channel = _make_channel(state="pre_launch", code="NOON_UAE")
    # Solo MTV-1001 tiene precio aprobado; MTV-1002 falta
    session = _make_session(channel=channel, approved_skus=["MTV-1001"])
    service = ChannelTransitionService(session)

    history, missing_skus = await service.transition(
        channel_id=channel.id,
        target_state="pilot",
        actor=_make_user(),
        subset_skus=["MTV-1001", "MTV-1002"],
        override_warnings=True,
    )

    assert channel.state == "pilot"
    assert channel.pilot_with_warnings is True
    assert missing_skus == ["MTV-1002"]
    assert history.pilot_with_warnings is True


@pytest.mark.asyncio
async def test_pilot_transition_all_skus_approved_no_warnings() -> None:
    """pre_launch → pilot con todos los SKUs aprobados → sin warnings."""
    channel = _make_channel(state="pre_launch", code="AMAZON_UAE")
    session = _make_session(channel=channel, approved_skus=["MTV-1001", "MTV-1002"])
    service = ChannelTransitionService(session)

    history, missing_skus = await service.transition(
        channel_id=channel.id,
        target_state="pilot",
        actor=_make_user(),
        subset_skus=["MTV-1001", "MTV-1002"],
        override_warnings=False,
    )

    assert channel.state == "pilot"
    assert channel.pilot_with_warnings is False
    assert missing_skus == []
    assert history.pilot_with_warnings is False


# ---------------------------------------------------------------------------
# US-1B-03-03 — Notificaciones pause/resume
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_pause_emits_notifications() -> None:
    """live → paused emite notificaciones a roles comercial + gerente."""
    channel = _make_channel(state="live", code="AMAZON_UAE")

    # Dos usuarios: uno comercial, uno gerente
    user1 = MagicMock()
    user1.id = uuid.uuid4()
    user2 = MagicMock()
    user2.id = uuid.uuid4()

    session = _make_session(channel=channel, role_users=[user1, user2])
    service = ChannelTransitionService(session)

    # Spy en notifications.create
    notif_calls: list[dict] = []

    async def _notif_create(*, recipient_user_id, kind, payload):
        notif_calls.append({"recipient": recipient_user_id, "kind": kind, "payload": payload})
        n = MagicMock()
        n.id = uuid.uuid4()
        return n

    service.notifications.create = _notif_create

    history, _ = await service.transition(
        channel_id=channel.id,
        target_state="paused",
        actor=_make_user(),
        comment="mantenimiento",
    )

    assert channel.state == "paused"
    assert len(notif_calls) == 2
    assert all(c["kind"] == "channel.paused" for c in notif_calls)
    assert all("bloqueados" in c["payload"]["message"] for c in notif_calls)


@pytest.mark.asyncio
async def test_resume_from_pause_emits_notifications() -> None:
    """paused → live emite notificaciones de reactivación."""
    channel = _make_channel(state="paused", code="NOON_UAE")

    user1 = MagicMock()
    user1.id = uuid.uuid4()

    session = _make_session(channel=channel, role_users=[user1])
    service = ChannelTransitionService(session)

    notif_calls: list[dict] = []

    async def _notif_create(*, recipient_user_id, kind, payload):
        notif_calls.append({"recipient": recipient_user_id, "kind": kind, "payload": payload})
        n = MagicMock()
        n.id = uuid.uuid4()
        return n

    service.notifications.create = _notif_create

    history, _ = await service.transition(
        channel_id=channel.id,
        target_state="live",
        actor=_make_user(),
        comment="reactivación tras mantenimiento",
    )

    assert channel.state == "live"
    assert len(notif_calls) == 1
    assert notif_calls[0]["kind"] == "channel.resumed"
    assert "disponibles" in notif_calls[0]["payload"]["message"]


# ---------------------------------------------------------------------------
# US-1B-03-03 — Canal deprecated rechaza nuevas propuestas
# ---------------------------------------------------------------------------


def test_channel_deprecated_error_in_pricing_service() -> None:
    """ChannelDeprecated se importa correctamente desde pricing_service."""
    from app.services.pricing.pricing_service import ChannelDeprecated

    err = ChannelDeprecated("AMAZON_UAE")
    assert err.status_code == 422
    assert "deprecated" in err.message
    assert "AMAZON_UAE" in err.message
