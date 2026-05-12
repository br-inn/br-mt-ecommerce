"""Price state machine — FSM con transiciones legales.

ADR-006 (workflow excepción) + ADR-010 (no aprobado no integra):
- Las transiciones inválidas lanzan `InvalidTransition` / `InvalidTransitionError`.
- `transition()` (función) y `PriceStateMachine.transition()` (clase) mutan el
  Price y devuelven un `PriceApprovalEvent` listo para persistir.
- El caller debe persistir tanto el cambio en `Price.status` como la fila
  `PriceApprovalEvent` en la misma transacción.
- El trigger DB `ck_price_status_transition` actúa como segunda línea de defensa
  (ver migración 20260512_070_price_status_enum).
"""

from __future__ import annotations

from datetime import datetime, timezone
from uuid import UUID

from app.db.models.pricing import Price, PriceApprovalEvent
from app.db.models.user import User


# Transiciones legales — claves son `from_status`, valores son set de `to_status` válidos.
ALLOWED_TRANSITIONS: dict[str, frozenset[str]] = {
    "draft": frozenset({"auto_approved", "pending_review", "rejected"}),
    "auto_approved": frozenset({"approved", "exported", "published", "revised"}),
    "pending_review": frozenset({"approved", "rejected", "revised"}),
    "approved": frozenset({"exported", "published", "revised"}),
    "rejected": frozenset({"draft"}),
    "revised": frozenset({"pending_review", "rejected"}),
    "published": frozenset({"archived"}),
    "archived": frozenset(),   # terminal
    "exported": frozenset({"archived"}),  # legacy alias de published
    "superseded": frozenset(),  # terminal
    "migrated": frozenset({"approved", "rejected"}),  # imported legacy data
}


class InvalidTransition(Exception):
    """Levantada cuando un cambio de estado no es legal."""

    def __init__(self, from_status: str, to_status: str) -> None:
        super().__init__(
            f"Transición inválida: {from_status} → {to_status}. "
            f"Permitidas: {sorted(ALLOWED_TRANSITIONS.get(from_status, []))}"
        )
        self.from_status = from_status
        self.to_status = to_status


# Alias US-1B-02 — mismo error, nombre alineado con la spec de la story
InvalidTransitionError = InvalidTransition


def is_valid_transition(from_status: str, to_status: str) -> bool:
    return to_status in ALLOWED_TRANSITIONS.get(from_status, frozenset())


def transition(
    price: Price,
    to_status: str,
    actor: User,
    reason: str | None = None,
    metadata: dict | None = None,
) -> PriceApprovalEvent:
    """Verifica + aplica transición + devuelve `PriceApprovalEvent` listo para persistir.

    Mutates `price.status`, `price.approved_by`, `price.approved_at`,
    `price.rejection_reason` según corresponda. NO commitea — la session es del
    caller.

    Args:
        price: Price ORM ya cargado en la session.
        to_status: nuevo estado.
        actor: usuario que dispara la transición (validar permisos en service).
        reason: razón opcional (obligatoria para reject/revise — el service la valida).
        metadata: extras JSON-serializables.

    Raises:
        InvalidTransition: si la transición no es legal.
    """
    if not is_valid_transition(price.status, to_status):
        raise InvalidTransition(price.status, to_status)

    from_status = price.status
    now = datetime.now(tz=timezone.utc)
    event = PriceApprovalEvent(
        price_id=price.id,
        actor_id=actor.id,
        from_status=from_status,
        to_status=to_status,
        reason=reason,
        metadata_jsonb=metadata or {},
    )

    price.status = to_status
    if to_status in {"approved", "auto_approved", "published"}:
        price.approved_by = actor.id
        price.approved_at = now
    elif to_status == "rejected":
        price.rejection_reason = reason

    return event


class PriceStateMachine:
    """Clase-servicio FSM para `prices.status` (US-1B-02-01).

    Interfaz de clase estática — sin estado de instancia. Usada por services
    de nivel superior (BulkApproveService, ReviseService, etc.) que ya tienen
    la sesión SQLAlchemy y sólo necesitan validar + mutar.
    """

    @staticmethod
    def transition(
        price: Price,
        target_status: str,
        actor_user_id: UUID,
        reason: str | None = None,
        metadata: dict | None = None,
    ) -> PriceApprovalEvent:
        """Valida la transición, muta `price.status` y devuelve el evento de auditoría.

        Args:
            price: instancia ORM ya cargada en la sesión activa.
            target_status: estado destino (string o PriceState/PriceStatus).
            actor_user_id: UUID del usuario que dispara la transición.
            reason: texto libre; obligatorio para reject/revise (el caller lo valida).
            metadata: JSONB extra para el evento.

        Raises:
            InvalidTransitionError: si la transición no está en ALLOWED_TRANSITIONS.
        """
        target_status = str(target_status)
        if not is_valid_transition(price.status, target_status):
            raise InvalidTransitionError(price.status, target_status)

        from_status = price.status
        now = datetime.now(tz=timezone.utc)

        event = PriceApprovalEvent(
            price_id=price.id,
            actor_id=actor_user_id,
            from_status=from_status,
            to_status=target_status,
            reason=reason,
            metadata_jsonb=metadata or {},
        )

        price.status = target_status
        if target_status in {"approved", "auto_approved", "published"}:
            price.approved_by = actor_user_id
            price.approved_at = now
        elif target_status == "rejected":
            price.rejection_reason = reason

        return event


__all__ = [
    "ALLOWED_TRANSITIONS",
    "InvalidTransition",
    "InvalidTransitionError",
    "PriceStateMachine",
    "is_valid_transition",
    "transition",
]
