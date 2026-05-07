"""Price state machine — FSM con transiciones legales.

ADR-006 (workflow excepción) + ADR-010 (no aprobado no integra):
- Las transiciones inválidas lanzan `InvalidTransition`.
- `transition()` deja la mutación al caller (PricingService) — sólo valida y
  devuelve el nuevo estado + crea registro `PriceApprovalEvent` para audit.
- El caller debe persistir tanto el cambio en `Price.status` como la fila
  `PriceApprovalEvent` en la misma transacción.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import TYPE_CHECKING

from app.db.models.pricing import Price, PriceApprovalEvent
from app.db.models.user import User

if TYPE_CHECKING:  # pragma: no cover
    pass


# Transiciones legales — claves son `from_status`, valores son set de `to_status` válidos.
ALLOWED_TRANSITIONS: dict[str, frozenset[str]] = {
    "draft": frozenset({"auto_approved", "pending_review", "rejected"}),
    "auto_approved": frozenset({"approved", "exported", "revised"}),
    "pending_review": frozenset({"approved", "rejected", "revised"}),
    "approved": frozenset({"exported", "revised"}),
    "rejected": frozenset({"draft"}),
    "revised": frozenset({"pending_review", "rejected"}),
    "exported": frozenset(),  # terminal
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
    if to_status in {"approved", "auto_approved"}:
        price.approved_by = actor.id
        price.approved_at = now
    elif to_status == "rejected":
        price.rejection_reason = reason

    return event


__all__ = [
    "ALLOWED_TRANSITIONS",
    "InvalidTransition",
    "is_valid_transition",
    "transition",
]
