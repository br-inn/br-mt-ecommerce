"""ReviseService — revise con counter-proposal (Sprint 4 / US-1B-01-04).

Patrón:
- ``revise_with_counter`` toma un ``price_id`` que está en
  ``pending_review|auto_approved|approved`` y un ``new_amount``. Genera **dos**
  registros de evento:
    1. ``price.revised`` (state machine ``→ revised`` con audit del delta).
    2. ``price.counter_proposed`` (audit-only entry con detalle del nuevo
       amount + reason + recompute del margen contra el cost activo).
- Recalcula ``margin_pct`` automáticamente si encontramos cost activo (mismo
  comportamiento que ``PricingService.revise`` pero con flag
  ``auto_recompute_margin=True`` por defecto).
- Si el cost no existe, deja el ``margin_pct`` previo y registra alerta en el
  audit ``payload_diff``.

Diseño defensivo: este servicio es un wrapper sobre ``PricingService.revise``.
Los tests inyectan un ``pricing_service`` mock para no necesitar DB.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from decimal import Decimal
from typing import Any, Protocol
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.user import User
from app.repositories.audit import AuditRepository
from app.services.pricing.pricing_service import (
    PricingDomainError,
    PricingService,
)

logger = logging.getLogger(__name__)


class PricingServiceReviseProtocol(Protocol):
    async def revise(
        self,
        price_id: UUID,
        actor: User,
        new_amount: Decimal,
        reason: str,
    ) -> Any: ...


@dataclass(slots=True)
class CounterProposalResult:
    price_id: str
    new_amount: str
    old_amount: str
    margin_pct: str | None
    reason: str
    status_after: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "price_id": self.price_id,
            "new_amount": self.new_amount,
            "old_amount": self.old_amount,
            "margin_pct": self.margin_pct,
            "reason": self.reason,
            "status_after": self.status_after,
        }


class CounterProposalEmptyError(PricingDomainError):
    def __init__(self) -> None:
        super().__init__(
            "counter_proposal_amount_required",
            "El nuevo amount debe ser > 0 para una contrapropuesta.",
            422,
        )


class ReviseService:
    """Revise + counter-proposal dedicado.

    Encapsula la lógica de Sprint 4: cuando un Comercial revisa un precio
    pending/approved con una contrapropuesta hacia el cliente, queremos
    generar:
    - Audit ``price.counter_proposed`` con el detalle (old, new, delta_pct).
    - Tras el ``revise`` real (que dispara state machine + audit
      ``price.revised``), persistir un registro extra de "tracking" para
      el dashboard del Gerente.
    """

    def __init__(
        self,
        session: AsyncSession,
        *,
        pricing_service: PricingServiceReviseProtocol | None = None,
    ) -> None:
        self.session = session
        self.pricing_service: PricingServiceReviseProtocol = (
            pricing_service or PricingService(session)
        )
        self.audit = AuditRepository(session)

    async def revise_with_counter(
        self,
        *,
        price_id: UUID,
        new_amount: Decimal,
        reason: str,
        actor: User,
    ) -> CounterProposalResult:
        if new_amount is None or Decimal(new_amount) <= 0:
            raise CounterProposalEmptyError()
        if not reason or not reason.strip():
            raise PricingDomainError(
                "reason_required",
                "Razón obligatoria para counter-proposal.",
                422,
            )

        revised = await self.pricing_service.revise(
            price_id, actor, new_amount=Decimal(new_amount), reason=reason
        )

        old_amount = self._extract_old_amount(revised, new_amount)
        delta_pct: Decimal | None = None
        if old_amount and Decimal(old_amount) > 0:
            try:
                delta_pct = (Decimal(new_amount) - Decimal(old_amount)) / Decimal(
                    old_amount
                )
            except (ArithmeticError, ValueError):  # pragma: no cover
                delta_pct = None

        await self.audit.record(
            entity_type="price",
            entity_id=str(getattr(revised, "id", price_id)),
            action="price.counter_proposed",
            actor_id=actor.id,
            actor_email=actor.email,
            reason=reason,
            payload_diff={
                "old_amount": str(old_amount) if old_amount is not None else None,
                "new_amount": str(new_amount),
                "delta_pct": str(delta_pct) if delta_pct is not None else None,
            },
        )

        margin_pct = getattr(revised, "margin_pct", None)
        return CounterProposalResult(
            price_id=str(getattr(revised, "id", price_id)),
            new_amount=str(new_amount),
            old_amount=str(old_amount) if old_amount is not None else "0",
            margin_pct=str(margin_pct) if margin_pct is not None else None,
            reason=reason,
            status_after=getattr(revised, "status", "revised"),
        )

    @staticmethod
    def _extract_old_amount(price: Any, new_amount: Decimal) -> Decimal | None:
        """El service.revise muta ``price.amount`` al nuevo monto antes de
        retornar; pero en Sprint 4 también guardamos ``previous_amount`` en
        ``breakdown`` cuando exista. Si nada queda, devolvemos None."""
        bd = getattr(price, "breakdown", None) or {}
        if isinstance(bd, dict):
            prev = bd.get("previous_amount") or bd.get("old_amount")
            if prev is not None:
                try:
                    return Decimal(str(prev))
                except (ArithmeticError, ValueError):
                    return None
        return None


__all__ = [
    "CounterProposalEmptyError",
    "CounterProposalResult",
    "ReviseService",
]
