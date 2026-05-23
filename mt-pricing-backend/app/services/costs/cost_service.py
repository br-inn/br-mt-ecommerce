"""CostService — orquesta create/update/list de `costs` con versionado.

Reglas (US-1A-04-03):
- ``create_cost``:
    1. Valida breakdown vía `breakdown_validator`.
    2. Inserta — el trigger DB busca FX as-of y estampa `fx_rate_id`.
       Si no hay rate → IntegrityError mapeado a `fx_rate_not_found_at_effective_at`.
    3. Audit `cost.created`.
- ``update_cost`` (versionado):
    1. Carga la row existente (status='active').
    2. La marca `superseded`, flushea.
    3. Crea row nueva con `version=prev+1`, `status='active'`, breakdown
       merged + cualquier override (effective_at/currency_origin si llegan).
    4. Audit `cost.updated` con diff.
- ``list_for_sku``: alias de CostRepository (con `only_active=True`).
- ``compute_landed_aed``: helper Python para previews UI **sin** persistir.
  La fórmula DB se replica aquí; en BD vive el trigger AFTER (canonical).
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from typing import Any
from uuid import UUID

from sqlalchemy import desc, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.cost import Cost
from app.db.models.pricing import FXRate
from app.repositories.audit import AuditRepository
from app.services.costs.breakdown_validator import (
    BreakdownValidationResult,
    validate_breakdown,
)


# ---------------------------------------------------------------------------
# Errors
# ---------------------------------------------------------------------------
class CostServiceError(Exception):
    code: str = "cost_service_error"
    http_status: int = 422

    def __init__(self, message: str | None = None) -> None:
        super().__init__(message or self.code)


class FXRateNotFoundAtEffectiveAt(CostServiceError):
    code = "fx_rate_not_found_at_effective_at"


class CostNotFound(CostServiceError):
    code = "cost_not_found"
    http_status = 404


class SchemeNotFound(CostServiceError):
    code = "scheme_not_found"
    http_status = 404


# ---------------------------------------------------------------------------
# Result wrapper — used by API layer
# ---------------------------------------------------------------------------
@dataclass
class CreateCostResult:
    cost: Cost
    warnings: list[dict[str, str]]


# ---------------------------------------------------------------------------
# Service
# ---------------------------------------------------------------------------
class CostService:
    """Orquestador de costs. Una instancia por request.

    Args:
        session: AsyncSession ya abierta (el caller commitea).
    """

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    # ------------------------------------------------------------------
    # Reads
    # ------------------------------------------------------------------
    async def get_active(
        self, sku: str, scheme_code: str, supplier_code: str | None = None
    ) -> Cost | None:
        stmt = (
            select(Cost)
            .where(
                Cost.sku == sku,
                Cost.scheme_code == scheme_code,
                Cost.supplier_code == supplier_code,
                Cost.status == "active",
            )
            .order_by(desc(Cost.effective_at))
            .limit(1)
        )
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def list_for_sku(self, sku: str, *, only_active: bool = False) -> Sequence[Cost]:
        stmt = select(Cost).where(Cost.sku == sku)
        if only_active:
            stmt = stmt.where(Cost.status == "active")
        stmt = stmt.order_by(Cost.scheme_code.asc(), desc(Cost.effective_at))
        result = await self.session.execute(stmt)
        return result.scalars().all()

    # ------------------------------------------------------------------
    # Create / Update (versionado)
    # ------------------------------------------------------------------
    async def create_cost(
        self,
        *,
        sku: str,
        scheme_code: str,
        supplier_code: str | None = None,
        currency_origin: str = "AED",
        effective_at: datetime,
        breakdown: dict[str, Any],
        actor_id: UUID | None = None,
        actor_email: str | None = None,
        fx_rate_id: UUID | None = None,
        fx_inferred: bool = False,
        **_extra: Any,  # tolerate extra kwargs from importer (`_import_run_id`, `_actor_id`)
    ) -> CreateCostResult:
        """Crea una row 'active' nueva. Si ya existe una active para el combo,
        ESTE método NO la supersede — usa `update_cost` para versionar.

        Validaciones:
        - Breakdown contra cost_components_template del scheme.
        - El trigger DB se encarga de FX as-of stamping.
        """
        # Importer compat: _actor_id / _import_run_id arrive as named extras.
        if actor_id is None and "_actor_id" in _extra:
            actor_id = _extra.get("_actor_id")  # type: ignore[assignment]

        # 1) Validar breakdown — required missing levanta MissingRequiredField.
        result: BreakdownValidationResult = await validate_breakdown(
            self.session, scheme_code, breakdown
        )
        if not result.valid:
            # Generic error path (scheme not found etc.) — el caller traduce.
            if any(e.get("code") == "scheme_not_found" for e in result.errors):
                raise SchemeNotFound(scheme_code)

        # 2) Insert — trigger BD estampa fx_rate_id, scheme_landed_aed.
        cost = Cost(
            sku=sku,
            scheme_code=scheme_code,
            supplier_code=supplier_code,
            currency_origin=currency_origin,
            effective_at=effective_at,
            breakdown=dict(breakdown),
            status="active",
            version=1,
            fx_inferred=fx_inferred,
            fx_rate_id=fx_rate_id,
            created_by=actor_id,
        )
        self.session.add(cost)
        try:
            await self.session.flush()
        except IntegrityError as exc:
            await self.session.rollback()
            self._maybe_remap_fx_error(exc)
            raise

        # 3) Audit
        audit = AuditRepository(self.session)
        await audit.record(
            entity_type="cost",
            entity_id=str(cost.id),
            action="cost.created",
            actor_id=actor_id,
            actor_email=actor_email,
            after={
                "sku": cost.sku,
                "scheme_code": cost.scheme_code,
                "supplier_code": cost.supplier_code,
                "currency_origin": cost.currency_origin,
                "effective_at": cost.effective_at.isoformat() if cost.effective_at else None,
                "breakdown": cost.breakdown,
                "scheme_landed_aed": str(cost.scheme_landed_aed)
                if cost.scheme_landed_aed is not None
                else None,
                "version": cost.version,
            },
        )
        return CreateCostResult(cost=cost, warnings=result.warnings)

    async def update_cost(
        self,
        cost_id: UUID,
        *,
        actor_id: UUID | None,
        actor_email: str | None = None,
        breakdown: dict[str, Any] | None = None,
        effective_at: datetime | None = None,
        currency_origin: str | None = None,
        fx_rate_id: UUID | None = None,
        fx_inferred: bool | None = None,
    ) -> CreateCostResult:
        """Versionado: NO modifica la row existente in-place. Crea row nueva
        con `version=prev+1, status='active'` y la previa pasa a 'superseded'.
        El UNIQUE parcial (status='active') exige hacerlo en el orden correcto:
        primero el flush del 'superseded' viejo, luego insertar la nueva.
        """
        prev = await self._get(cost_id)
        if prev is None:
            raise CostNotFound(str(cost_id))

        # Snapshot del antes para audit.
        before = _snapshot(prev)

        # 1) supersede la previa.
        prev.status = "superseded"
        prev.updated_by = actor_id
        await self.session.flush()

        # 2) Validar breakdown final (merged si llega parcial).
        new_breakdown = dict(breakdown) if breakdown is not None else dict(prev.breakdown or {})
        validation = await validate_breakdown(self.session, prev.scheme_code, new_breakdown)

        # 3) Insertar nueva row.
        new = Cost(
            sku=prev.sku,
            scheme_code=prev.scheme_code,
            supplier_code=prev.supplier_code,
            currency_origin=currency_origin or prev.currency_origin,
            effective_at=effective_at or prev.effective_at,
            breakdown=new_breakdown,
            status="active",
            version=prev.version + 1,
            fx_inferred=fx_inferred if fx_inferred is not None else False,
            fx_rate_id=fx_rate_id,  # NULL → trigger re-estampará
            created_by=actor_id,
        )
        self.session.add(new)
        try:
            await self.session.flush()
        except IntegrityError as exc:
            await self.session.rollback()
            self._maybe_remap_fx_error(exc)
            raise

        # 4) Audit con diff.
        after = _snapshot(new)
        diff = _compute_diff(before, after)
        audit = AuditRepository(self.session)
        await audit.record(
            entity_type="cost",
            entity_id=str(new.id),
            action="cost.updated",
            actor_id=actor_id,
            actor_email=actor_email,
            before=before,
            after=after,
            payload_diff=diff,
        )
        return CreateCostResult(cost=new, warnings=validation.warnings)

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------
    async def missing_cost_skus(self, scheme_code: str, *, limit: int = 1000) -> Sequence[str]:
        """Devuelve los SKUs sin coste activo para el scheme. Implementación
        en SQL puro — usa NOT EXISTS para evitar un join LEFT con filtro post.
        """
        from sqlalchemy import text as sql_text

        stmt = sql_text(
            """
            SELECT p.sku
            FROM products p
            WHERE p.deleted_at IS NULL
              AND NOT EXISTS (
                SELECT 1 FROM costs c
                WHERE c.sku = p.sku
                  AND c.scheme_code = :scheme
                  AND c.status = 'active'
              )
            ORDER BY p.sku
            LIMIT :lim
            """
        )
        result = await self.session.execute(stmt, {"scheme": scheme_code, "lim": limit})
        return [r[0] for r in result.all()]

    async def _get(self, cost_id: UUID) -> Cost | None:
        return await self.session.get(Cost, cost_id)

    @staticmethod
    def _maybe_remap_fx_error(exc: IntegrityError) -> None:
        """El trigger DB lanza un RAISE EXCEPTION con SQLSTATE 'P0001' y un
        mensaje que incluye `fx_rate_not_found_at_effective_at`. Si lo
        detectamos, levantamos el error de dominio limpio.
        """
        msg = str(getattr(exc, "orig", exc) or exc).lower()
        if "fx_rate_not_found_at_effective_at" in msg:
            raise FXRateNotFoundAtEffectiveAt(
                "No FX rate found for currency_origin → AED at effective_at"
            )

    # ------------------------------------------------------------------
    # Helper Python para preview UI (no persiste — usa misma fórmula que el trigger DB).
    # ------------------------------------------------------------------
    async def compute_landed_aed(
        self,
        breakdown: dict[str, Any],
        currency_origin: str,
        effective_at: datetime,
    ) -> Decimal | None:
        """Calcula el `scheme_landed_aed` esperado.

        Convenciones de claves:
        - ``*_aed`` → no convierten.
        - ``*_<currency_origin>`` (lower) → convierten via fx_rate.
        - ``*_pct`` → porcentaje aplicado sobre subtotal (suma del resto).

        Si necesita FX y no encuentra rate → None (caller decide).
        """
        rate: Decimal | None = None
        if currency_origin.upper() != "AED":
            stmt = (
                select(FXRate)
                .where(
                    FXRate.from_currency == currency_origin.upper(),
                    FXRate.to_currency == "AED",
                    FXRate.effective_from <= effective_at,
                    (FXRate.effective_to.is_(None)) | (FXRate.effective_to > effective_at),
                )
                .order_by(desc(FXRate.effective_from))
                .limit(1)
            )
            result = await self.session.execute(stmt)
            fx = result.scalar_one_or_none()
            if fx is None:
                return None
            rate = fx.rate

        subtotal = Decimal("0")
        pct_components: list[Decimal] = []
        for key, raw in breakdown.items():
            try:
                v = Decimal(str(raw)) if raw is not None else Decimal("0")
            except (ValueError, ArithmeticError):
                continue
            kl = key.lower()
            if kl.endswith("_pct"):
                pct_components.append(v)
                continue
            if kl.endswith("_aed"):
                subtotal += v
                continue
            if rate is not None and kl.endswith("_" + currency_origin.lower()):
                subtotal += v * rate
                continue
            # default: assume same currency as origin
            if rate is not None:
                subtotal += v * rate
            else:
                subtotal += v

        # Apply pct components on top of subtotal (each % independent).
        for pct in pct_components:
            subtotal += subtotal * (pct / Decimal("100"))

        return subtotal.quantize(Decimal("0.0001"))


# ---------------------------------------------------------------------------
# Diff helpers
# ---------------------------------------------------------------------------
def _snapshot(cost: Cost) -> dict[str, Any]:
    return {
        "id": str(cost.id),
        "sku": cost.sku,
        "scheme_code": cost.scheme_code,
        "supplier_code": cost.supplier_code,
        "currency_origin": cost.currency_origin,
        "effective_at": cost.effective_at.isoformat() if cost.effective_at else None,
        "breakdown": cost.breakdown,
        "scheme_landed_aed": str(cost.scheme_landed_aed)
        if cost.scheme_landed_aed is not None
        else None,
        "status": cost.status,
        "version": cost.version,
        "fx_inferred": cost.fx_inferred,
    }


def _compute_diff(before: dict[str, Any], after: dict[str, Any]) -> dict[str, Any]:
    """Helper local — diff per-key. Usa misma estructura que pricing service."""
    out: dict[str, Any] = {}
    keys = set(before.keys()) | set(after.keys())
    for k in keys:
        b = before.get(k)
        a = after.get(k)
        if b != a:
            out[k] = {"before": b, "after": a}
    return out


__all__ = [
    "CostNotFound",
    "CostService",
    "CostServiceError",
    "CreateCostResult",
    "FXRateNotFoundAtEffectiveAt",
    "SchemeNotFound",
]
