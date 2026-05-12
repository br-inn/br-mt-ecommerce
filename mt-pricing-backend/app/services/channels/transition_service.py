"""ChannelTransitionService — US-1B-03-02 + US-1B-03-03 (Sprint 8).

Responsabilidades:
- Valida máquina de estados de canal.
- Valida precios aprobados para pre_launch → pilot.
- Registra ChannelStateHistory.
- Emite notificaciones in-app al pausar / reactivar canal.

Sin commit — el caller (route) hace await session.commit().
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.channels import Channel, ChannelStateHistory
from app.db.models.pricing import Price
from app.db.models.user import Role, User
from app.repositories.notifications import NotificationsRepository

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Máquina de estados válida
# ---------------------------------------------------------------------------
VALID_TRANSITIONS: dict[str, set[str]] = {
    "inactive":    {"pre_launch"},
    "pre_launch":  {"pilot", "inactive"},
    "pilot":       {"live", "pre_launch"},
    "live":        {"paused", "deprecated"},
    "paused":      {"live", "deprecated"},
    "deprecated":  set(),  # estado terminal
}

# Roles a notificar en eventos de pause/resume
_NOTIFY_ROLES = ("comercial", "gerente")

NOTIFICATION_KIND_PAUSED = "channel.paused"
NOTIFICATION_KIND_RESUMED = "channel.resumed"


class ChannelTransitionError(ValueError):
    """Transición de canal inválida."""


class MissingApprovedPricesError(ValueError):
    """SKUs sin precio aprobado al intentar piloto."""

    def __init__(self, missing: list[str]) -> None:
        self.missing_skus = missing
        super().__init__(
            f"SKUs sin precio aprobado para piloto: {', '.join(missing)}"
        )


class ChannelTransitionService:
    """Orquesta transición de estado de canal con validaciones y efectos laterales.

    Sin commit — el caller decide el commit.
    """

    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.notifications = NotificationsRepository(session)

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    async def transition(
        self,
        channel_id: UUID,
        target_state: str,
        actor: User,
        subset_skus: list[str] | None = None,
        comment: str = "",
        override_warnings: bool = False,
    ) -> tuple[ChannelStateHistory, list[str]]:
        """Ejecuta transición de estado.

        Returns:
            (ChannelStateHistory, missing_skus) — fila de auditoría y lista de
            SKUs sin precio aprobado (vacía si validación pasó o no aplica).

        Raises:
            ChannelTransitionError: transición no válida en la FSM.
            MissingApprovedPricesError: pre_launch→pilot con SKUs sin precio
                aprobado y override_warnings=False.
        """
        channel = await self.session.get(Channel, channel_id)
        if channel is None:
            raise ChannelTransitionError(f"Canal {channel_id} no existe.")

        from_state = channel.state

        # -- FSM validation ------------------------------------------------
        allowed = VALID_TRANSITIONS.get(from_state, set())
        if target_state not in allowed:
            raise ChannelTransitionError(
                f"Transición inválida: {from_state!r} → {target_state!r}. "
                f"Permitidas desde {from_state!r}: {sorted(allowed) or 'ninguna (estado terminal)'}"
            )

        # -- Validación especial pre_launch → pilot -------------------------
        pilot_with_warnings = False
        missing_skus: list[str] = []

        if from_state == "pre_launch" and target_state == "pilot":
            skus = list(subset_skus or [])
            if skus:
                missing_skus = await self._check_approved_prices(
                    channel_code=channel.code,
                    skus=skus,
                )
                if missing_skus and not override_warnings:
                    raise MissingApprovedPricesError(missing_skus)
                if missing_skus and override_warnings:
                    pilot_with_warnings = True

        # -- Aplicar transición --------------------------------------------
        channel.state = target_state
        channel.pilot_with_warnings = pilot_with_warnings
        await self.session.flush()

        # -- Registro de auditoría -----------------------------------------
        history = ChannelStateHistory(
            channel_id=channel.id,
            from_state=from_state,
            to_state=target_state,
            actor_user_id=actor.id,
            comment=comment,
            pilot_with_warnings=pilot_with_warnings,
        )
        self.session.add(history)
        await self.session.flush()

        # -- Efectos laterales US-1B-03-03 ----------------------------------
        await self._handle_side_effects(
            channel=channel,
            from_state=from_state,
            to_state=target_state,
            history=history,
        )

        return history, missing_skus

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    async def _check_approved_prices(
        self,
        channel_code: str,
        skus: list[str],
    ) -> list[str]:
        """Devuelve SKUs que NO tienen ningún precio aprobado en el canal."""
        stmt = (
            select(Price.product_sku)
            .join(Channel, Channel.id == Price.channel_id)
            .where(Channel.code == channel_code)
            .where(Price.product_sku.in_(skus))
            .where(Price.status.in_(["approved", "auto_approved"]))
            .distinct()
        )
        result = await self.session.execute(stmt)
        skus_with_price = set(result.scalars().all())
        return [sku for sku in skus if sku not in skus_with_price]

    async def _fetch_users_by_roles(self, role_codes: tuple[str, ...]) -> list[User]:
        """Devuelve usuarios activos de los roles especificados."""
        stmt = (
            select(User)
            .join(Role, Role.id == User.role_id)
            .where(Role.code.in_(role_codes))
            .where(User.is_active.is_(True))
            .where(User.deleted_at.is_(None))
        )
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def _notify_roles(
        self,
        role_codes: tuple[str, ...],
        kind: str,
        payload: dict,
    ) -> int:
        """Crea notificaciones para todos los usuarios de los roles dados.

        Returns:
            Número de notificaciones creadas.
        """
        recipients = await self._fetch_users_by_roles(role_codes)
        if not recipients:
            logger.warning(
                "_notify_roles: no active users found for roles %s — skipping notifications",
                role_codes,
            )
            return 0

        count = 0
        for user in recipients:
            await self.notifications.create(
                recipient_user_id=user.id,
                kind=kind,
                payload=payload,
            )
            count += 1

        return count

    async def _handle_side_effects(
        self,
        channel: Channel,
        from_state: str,
        to_state: str,
        history: ChannelStateHistory,
    ) -> None:
        """Efectos laterales según transición (US-1B-03-03)."""
        now = datetime.now(tz=timezone.utc).isoformat()

        if to_state == "paused":
            # Canal pausado — notificar comercial + gerente
            payload = {
                "channel_id": str(channel.id),
                "channel_code": channel.code,
                "from_state": from_state,
                "to_state": to_state,
                "history_id": str(history.id),
                "message": f"Canal {channel.code} pausado. Exports bloqueados temporalmente.",
                "paused_at": now,
            }
            count = await self._notify_roles(
                _NOTIFY_ROLES,
                kind=NOTIFICATION_KIND_PAUSED,
                payload=payload,
            )
            logger.info(
                "channel.paused: %s — %d notificaciones emitidas",
                channel.code,
                count,
            )

        elif from_state == "paused" and to_state == "live":
            # Canal reactivado desde pausa — notificar comercial + gerente
            payload = {
                "channel_id": str(channel.id),
                "channel_code": channel.code,
                "from_state": from_state,
                "to_state": to_state,
                "history_id": str(history.id),
                "message": f"Canal {channel.code} reactivado. Exports disponibles.",
                "resumed_at": now,
            }
            count = await self._notify_roles(
                _NOTIFY_ROLES,
                kind=NOTIFICATION_KIND_RESUMED,
                payload=payload,
            )
            logger.info(
                "channel.resumed: %s — %d notificaciones emitidas",
                channel.code,
                count,
            )


__all__ = [
    "ChannelTransitionService",
    "ChannelTransitionError",
    "MissingApprovedPricesError",
    "VALID_TRANSITIONS",
]
