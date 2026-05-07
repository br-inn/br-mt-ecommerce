"""PricingService — orquesta motor + exception evaluator + state machine + audit.

Patrones (alineados con SupplierService):
- Errores de dominio = `PricingDomainError` (4xx en routes).
- Cada mutación emite `audit_events` con before/after/diff.
- No commitea — la session es del caller.
"""

from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal
from typing import Any
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.pricing import Price
from app.db.models.product import Product
from app.db.models.user import User
from app.repositories.audit import AuditRepository
from app.repositories.product import ProductRepository
from app.repositories.pricing import (
    ChannelRepository,
    CostRepository,
    ExceptionRuleRepository,
    FXRateRepository,
    PriceApprovalEventRepository,
    PriceRepository,
)
from app.services.pricing.exception_evaluator import ExceptionEvaluator
from app.services.pricing.rule_engine import (
    EUR_TO_AED_DEFAULT,
    PricingResult,
    PricingRuleEngine,
)
from app.services.pricing.state_machine import (
    InvalidTransition,
    transition,
)


# ---------------------------------------------------------------------------
# Domain errors
# ---------------------------------------------------------------------------
class PricingDomainError(Exception):
    """Errores recoverables del servicio (4xx)."""

    def __init__(self, code: str, message: str, status_code: int = 400) -> None:
        super().__init__(message)
        self.code = code
        self.message = message
        self.status_code = status_code


class ProductNotFound(PricingDomainError):
    def __init__(self, sku: str) -> None:
        super().__init__("product_not_found", f"Producto {sku!r} no existe.", 404)


class ChannelNotFound(PricingDomainError):
    def __init__(self, code: str) -> None:
        super().__init__("channel_not_found", f"Canal {code!r} no existe.", 404)


class SchemeNotFound(PricingDomainError):
    def __init__(self, code: str) -> None:
        super().__init__("scheme_not_found", f"Scheme {code!r} no existe.", 404)


class CostNotFound(PricingDomainError):
    def __init__(self, sku: str, scheme: str) -> None:
        super().__init__(
            "cost_not_found",
            f"No hay coste activo para SKU={sku!r} scheme={scheme!r}.",
            422,
        )


class PriceNotFound(PricingDomainError):
    def __init__(self, price_id: Any) -> None:  # noqa: ANN401
        super().__init__("price_not_found", f"Precio {price_id} no existe.", 404)


class TransitionError(PricingDomainError):
    def __init__(self, from_status: str, to_status: str) -> None:
        super().__init__(
            "invalid_transition",
            f"Transición {from_status} → {to_status} no permitida.",
            409,
        )


# ---------------------------------------------------------------------------
# Helpers — snapshot para audit
# ---------------------------------------------------------------------------
_PRICE_AUDIT_FIELDS = (
    "id",
    "product_sku",
    "channel_id",
    "scheme_code",
    "amount",
    "pvp_min",
    "margin_pct",
    "currency",
    "rule_applied",
    "formula",
    "status",
)


def _snapshot_price(p: Price) -> dict[str, Any]:
    out: dict[str, Any] = {}
    for f in _PRICE_AUDIT_FIELDS:
        v = getattr(p, f, None)
        if v is None:
            out[f] = None
        elif isinstance(v, (UUID, datetime)):
            out[f] = str(v)
        elif isinstance(v, Decimal):
            out[f] = str(v)
        else:
            out[f] = v
    return out


# ---------------------------------------------------------------------------
# Service
# ---------------------------------------------------------------------------
class PricingService:
    """CRUD + motor + workflow. Stateless por request."""

    def __init__(
        self,
        session: AsyncSession,
        engine: PricingRuleEngine | None = None,
    ) -> None:
        self.session = session
        self.engine = engine or PricingRuleEngine()
        self.products = ProductRepository(session)
        self.channels = ChannelRepository(session)
        self.costs = CostRepository(session)
        self.prices = PriceRepository(session)
        self.fx_rates = FXRateRepository(session)
        self.exceptions = ExceptionRuleRepository(session)
        self.events = PriceApprovalEventRepository(session)
        self.audit = AuditRepository(session)

    # --------------------------------------------------------------- helpers
    async def _resolve_inputs(
        self, product_sku: str, channel_code: str, scheme_code: str
    ) -> tuple[Any, Any, str]:
        product = await self.products.get_by_sku(product_sku)
        if product is None:
            raise ProductNotFound(product_sku)
        channel = await self.channels.get_by_code(channel_code)
        if channel is None:
            raise ChannelNotFound(channel_code)
        # Scheme code se referencia directamente (es la PK de schemes)
        # Validamos via cost lookup más adelante; permitimos cualquier scheme_code
        # registrado (FBA/FBM/DIRECT_B2C/DIRECT_B2B/MARKETPLACE).
        return product, channel, scheme_code

    async def _resolve_fx(self) -> Decimal:
        fx = await self.fx_rates.get_active("EUR", "AED")
        if fx is None:
            return EUR_TO_AED_DEFAULT
        return Decimal(str(fx.rate))

    # ---------------------------------------------------------- public read
    async def get_price(self, price_id: UUID) -> Price:
        p = await self.prices.get(price_id)
        if p is None:
            raise PriceNotFound(price_id)
        return p

    async def list_prices(
        self,
        *,
        product_sku: str | None = None,
        channel_code: str | None = None,
        scheme_code: str | None = None,
        status: str | None = None,
        cursor: UUID | None = None,
        limit: int = 50,
        include_total: bool = False,
    ) -> tuple[Any, UUID | None, int | None]:
        channel_id: UUID | None = None
        if channel_code:
            channel = await self.channels.get_by_code(channel_code)
            if channel is None:
                raise ChannelNotFound(channel_code)
            channel_id = channel.id
        return await self.prices.list_paginated(
            product_sku=product_sku,
            channel_id=channel_id,
            scheme_code=scheme_code,
            status=status,
            cursor=cursor,
            limit=limit,
            include_total=include_total,
        )

    # -------------------------------------------------------- public mutate
    async def propose_price(
        self,
        product_sku: str,
        channel_code: str,
        scheme_code: str,
        actor: User,
        market: dict[str, Any] | None = None,
        master_data: dict[str, Any] | None = None,
    ) -> Price:
        """Calcula + crea Price con status según ExceptionEvaluator + emite audit."""
        product, channel, scheme_code = await self._resolve_inputs(
            product_sku, channel_code, scheme_code
        )

        # Cost lookup activo
        cost = await self.costs.get_active_for(product_sku, scheme_code)
        if cost is None:
            raise CostNotFound(product_sku, scheme_code)

        fx_rate = await self._resolve_fx()

        prev_price = await self.prices.get_active_for(
            product.sku, channel.id, scheme_code
        )

        active_rules = list(await self.exceptions.list_active())

        # Min margin del scheme (extraído de exception rules para inyectar al motor)
        scheme_min_margin: Decimal | None = None
        for r in active_rules:
            if r.active and r.scheme_code == scheme_code and r.min_margin_pct:
                scheme_min_margin = Decimal(str(r.min_margin_pct))
                break

        result: PricingResult = self.engine.calculate(
            product=product,
            channel=channel,
            scheme={"code": scheme_code},
            cost=cost,
            fx_rate=fx_rate,
            prev_price=prev_price,
            market=market,
            master_data=master_data,
            scheme_min_margin=scheme_min_margin,
        )

        # Decide status (auto_approved | pending_review)
        next_status, reasons = ExceptionEvaluator.evaluate(
            new_price=result,
            prev_price=prev_price,
            channel_id=channel.id,
            scheme_code=scheme_code,
            active_rules=active_rules,
            current_fx_rate=fx_rate,
            prev_fx_rate=None,  # TODO Sprint 3: stamping FX as-of por línea de precio
        )

        # Persist Price (status = draft inicialmente, luego transition)
        new_price = Price(
            product_sku=product.sku,
            channel_id=channel.id,
            scheme_code=scheme_code,
            amount=result.amount,
            pvp_min=result.pvp_min,
            margin_pct=result.margin_pct,
            currency="AED",
            rule_applied=result.rule_applied,
            formula=result.formula,
            breakdown=result.to_jsonable_breakdown(),
            alerts=result.to_jsonable_alerts(),
            fx_at=result.fx_at,
            status="draft",
            proposed_by=actor.id,
            created_by=actor.id,
            updated_by=actor.id,
        )
        self.session.add(new_price)
        await self.session.flush()  # asigna id

        # Marcar precios anteriores como expirados
        await self.prices.supersede_previous(
            product.sku, channel.id, scheme_code, new_price.id
        )

        # Aplicar transición draft → next_status
        try:
            event = transition(
                price=new_price,
                to_status=next_status,
                actor=actor,
                reason="propose",
                metadata={"evaluator_reasons": reasons},
            )
        except InvalidTransition as exc:
            raise TransitionError("draft", next_status) from exc
        self.session.add(event)

        await self.audit.record(
            entity_type="price",
            entity_id=str(new_price.id),
            action="price.proposed",
            actor_id=actor.id,
            actor_email=actor.email,
            after=_snapshot_price(new_price),
            payload_diff={"reasons": reasons},
        )
        await self.session.flush()
        return new_price

    async def approve(
        self, price_id: UUID, actor: User, reason: str | None = None
    ) -> Price:
        price = await self.get_price(price_id)
        before = _snapshot_price(price)
        try:
            event = transition(price, "approved", actor, reason=reason)
        except InvalidTransition as exc:
            raise TransitionError(price.status, "approved") from exc
        self.session.add(event)
        await self.audit.record(
            entity_type="price",
            entity_id=str(price.id),
            action="price.approved",
            actor_id=actor.id,
            actor_email=actor.email,
            before=before,
            after=_snapshot_price(price),
            reason=reason,
        )
        await self.session.flush()
        return price

    async def reject(self, price_id: UUID, actor: User, reason: str) -> Price:
        if not reason:
            raise PricingDomainError(
                "reason_required", "Razón obligatoria para rechazar precio.", 422
            )
        price = await self.get_price(price_id)
        before = _snapshot_price(price)
        try:
            event = transition(price, "rejected", actor, reason=reason)
        except InvalidTransition as exc:
            raise TransitionError(price.status, "rejected") from exc
        self.session.add(event)
        await self.audit.record(
            entity_type="price",
            entity_id=str(price.id),
            action="price.rejected",
            actor_id=actor.id,
            actor_email=actor.email,
            before=before,
            after=_snapshot_price(price),
            reason=reason,
        )
        await self.session.flush()
        return price

    async def revise(
        self, price_id: UUID, actor: User, new_amount: Decimal, reason: str
    ) -> Price:
        if not reason:
            raise PricingDomainError(
                "reason_required", "Razón obligatoria para revisar precio.", 422
            )
        price = await self.get_price(price_id)
        before = _snapshot_price(price)
        # Aceptamos revise desde {auto_approved, pending_review, approved}.
        # State machine valida.
        old_amount = price.amount
        price.amount = new_amount
        # Recalcular margen si tenemos cost breakdown
        cost = await self.costs.get_active_for(price.product_sku, price.scheme_code)
        if cost is not None and cost.total > 0:
            price.margin_pct = (new_amount - cost.total) / new_amount if new_amount > 0 else Decimal("0")
        try:
            event = transition(
                price,
                "revised",
                actor,
                reason=reason,
                metadata={"old_amount": str(old_amount), "new_amount": str(new_amount)},
            )
        except InvalidTransition as exc:
            raise TransitionError(price.status, "revised") from exc
        self.session.add(event)
        await self.audit.record(
            entity_type="price",
            entity_id=str(price.id),
            action="price.revised",
            actor_id=actor.id,
            actor_email=actor.email,
            before=before,
            after=_snapshot_price(price),
            reason=reason,
            payload_diff={"amount": {"from": str(old_amount), "to": str(new_amount)}},
        )
        await self.session.flush()
        return price

    async def export(self, price_id: UUID, actor: User) -> Price:
        price = await self.get_price(price_id)
        before = _snapshot_price(price)
        try:
            event = transition(price, "exported", actor, reason="export")
        except InvalidTransition as exc:
            raise TransitionError(price.status, "exported") from exc
        self.session.add(event)
        await self.audit.record(
            entity_type="price",
            entity_id=str(price.id),
            action="price.exported",
            actor_id=actor.id,
            actor_email=actor.email,
            before=before,
            after=_snapshot_price(price),
        )
        await self.session.flush()
        return price

    async def bulk_approve(
        self, price_ids: list[UUID], actor: User
    ) -> dict[str, Any]:
        """Aprobación masiva — falla soft (devuelve mapa éxitos/errores)."""
        results = {"approved": [], "errors": []}
        for pid in price_ids:
            try:
                p = await self.approve(pid, actor)
                results["approved"].append(str(p.id))
            except PricingDomainError as exc:
                results["errors"].append(
                    {"price_id": str(pid), "code": exc.code, "message": exc.message}
                )
        return results

    async def recalculate_for_product(
        self, product_id: UUID | str, actor: User
    ) -> list[Price]:
        """Re-propone precios para todas las (channel × scheme) activas del SKU."""
        # product_id puede ser sku o internal_id UUID
        product: Product | None
        if isinstance(product_id, UUID):
            stmt = select(Product).where(Product.internal_id == product_id)
            result = await self.session.execute(stmt)
            product = result.scalar_one_or_none()
        else:
            product = await self.products.get_by_sku(str(product_id))
        if product is None:
            raise ProductNotFound(str(product_id))

        new_prices: list[Price] = []
        channels = await self.channels.list_all(state="live")
        # Para cada channel × scheme soportado
        for ch in channels:
            schemes = ch.schemes_supported or []
            for scheme_code in schemes:
                cost = await self.costs.get_active_for(product.sku, scheme_code)
                if cost is None:
                    continue  # skip silently
                p = await self.propose_price(
                    product_sku=product.sku,
                    channel_code=ch.code,
                    scheme_code=scheme_code,
                    actor=actor,
                )
                new_prices.append(p)
        return new_prices

    async def recalculate_catalog_bulk(self, actor: User) -> dict[str, Any]:
        """Trigger fan-out via Celery — devuelve task_id."""
        # Import diferido para evitar ciclo
        from app.workers.tasks.pricing import recalculate_catalog_task

        async_result = recalculate_catalog_task.delay(str(actor.id))
        return {"task_id": async_result.id, "status": "queued"}

    async def simulate_what_if(
        self,
        product_sku: str,
        channel_code: str,
        scheme_code: str,
        scenario_overrides: dict[str, Any] | None = None,
    ) -> PricingResult:
        """Sin persist — sólo preview."""
        product, channel, scheme_code = await self._resolve_inputs(
            product_sku, channel_code, scheme_code
        )
        cost = await self.costs.get_active_for(product_sku, scheme_code)
        if cost is None and not (scenario_overrides and scenario_overrides.get("cost_total")):
            raise CostNotFound(product_sku, scheme_code)
        fx_rate = await self._resolve_fx()
        if scenario_overrides and scenario_overrides.get("fx_rate"):
            fx_rate = Decimal(str(scenario_overrides["fx_rate"]))

        result = self.engine.calculate(
            product=product,
            channel=channel,
            scheme={"code": scheme_code},
            cost=cost or {"total": 0, "breakdown": {}},
            fx_rate=fx_rate,
            scenario_overrides=scenario_overrides,
        )
        return result


__all__ = [
    "PricingDomainError",
    "PricingService",
    "ProductNotFound",
    "ChannelNotFound",
    "SchemeNotFound",
    "CostNotFound",
    "PriceNotFound",
    "TransitionError",
]
