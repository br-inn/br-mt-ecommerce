"""MAPService — MAP Engine (US-INV-01-02).

Implementa el cálculo de Coste Medio Ponderado (WAC/MAP) al procesar
un Goods Receipt. Sigue el modelo SAP MM Moving Average Price.

Flujo principal: `process_gr(gr_id)` →
  1. Carga GR + PO line
  2. Idempotencia
  3. Calcula unit_cost_aed
  4. Calcula MAP
  5. Upsert InventoryPosition + INSERT CostLot
  6. Actualiza Cost via CostService.update_cost()
  7. Marca GR processed
"""

from __future__ import annotations

import logging
import traceback
from datetime import datetime, timezone
from decimal import ROUND_HALF_UP, Decimal
from typing import Any
from uuid import UUID

from sqlalchemy import select, text
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.inventory import (
    CostLot,
    GoodsReceipt,
    InventoryPosition,
    PurchaseOrderLine,
)
from app.services.costs.cost_service import CostService

logger = logging.getLogger(__name__)

_FOUR = Decimal("0.0001")


class MAPService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self._cost_svc = CostService(session)

    # ------------------------------------------------------------------
    # Pure calculation — no IO
    # ------------------------------------------------------------------

    def calculate_map(
        self,
        qty_existing: Decimal,
        value_existing_aed: Decimal,
        qty_new: Decimal,
        unit_cost_aed_new: Decimal,
    ) -> Decimal:
        if qty_existing == Decimal("0"):
            return unit_cost_aed_new.quantize(_FOUR, rounding=ROUND_HALF_UP)
        total_value = value_existing_aed + qty_new * unit_cost_aed_new
        total_qty = qty_existing + qty_new
        return (total_value / total_qty).quantize(_FOUR, rounding=ROUND_HALF_UP)

    # ------------------------------------------------------------------
    # Main orchestrator
    # ------------------------------------------------------------------

    async def process_gr(self, gr_id: UUID) -> InventoryPosition:
        gr = await self._load_gr(gr_id)
        if gr.status == "processed":
            pos = await self._get_position(
                sku=gr._pol_sku,
                supplier_code=gr._pol_supplier_code,
                scheme_code=gr._pol_scheme_code,
            )
            return pos  # type: ignore[return-value]

        pol = gr._po_line

        qty_new = Decimal(str(gr.qty_received))

        unit_cost_aed = await self._resolve_unit_cost_aed(gr, pol)

        pos = await self._get_position(
            sku=pol.sku,
            supplier_code=pol._po_supplier_code,
            scheme_code=pol.scheme_code,
        )

        qty_existing = Decimal(str(pos.qty_on_hand)) if pos else Decimal("0")
        value_existing = (
            Decimal(str(pos.total_stock_value_aed))
            if pos and pos.total_stock_value_aed is not None
            else Decimal("0")
        )

        map_before = pos.map_aed if pos else None
        map_after = self.calculate_map(
            qty_existing=qty_existing,
            value_existing_aed=value_existing,
            qty_new=qty_new,
            unit_cost_aed_new=unit_cost_aed,
        )

        gr.map_before = map_before
        gr.map_after = map_after
        await self.session.flush()

        pos = await self._upsert_inventory_position(
            sku=pol.sku,
            supplier_code=pol._po_supplier_code,
            scheme_code=pol.scheme_code,
            qty_delta=qty_new,
            new_map=map_after,
            last_gr_id=gr_id,
        )

        await self._insert_cost_lot(
            sku=pol.sku,
            supplier_code=pol._po_supplier_code,
            scheme_code=pol.scheme_code,
            gr_id=gr_id,
            qty=qty_new,
            unit_cost_aed=unit_cost_aed,
        )

        await self._update_cost(
            sku=pol.sku,
            supplier_code=pol._po_supplier_code,
            scheme_code=pol.scheme_code,
            map_aed=map_after,
            fx_rate_id=gr.fx_rate_id,
            effective_at=gr.received_at,
        )

        gr.status = "processed"
        gr.processed_at = datetime.now(tz=timezone.utc)
        await self.session.flush()

        return pos

    # ------------------------------------------------------------------
    # Internals
    # ------------------------------------------------------------------

    async def _load_gr(self, gr_id: UUID) -> Any:
        """Carga GR + po_line + po (para supplier_code). Adjunta atributos helper."""
        from app.db.models.inventory import PurchaseOrder

        stmt = (
            select(GoodsReceipt)
            .where(GoodsReceipt.id == gr_id)
        )
        result = await self.session.execute(stmt)
        gr = result.scalar_one_or_none()
        if gr is None:
            raise ValueError(f"GoodsReceipt {gr_id} not found")

        pol_stmt = select(PurchaseOrderLine).where(
            PurchaseOrderLine.id == gr.po_line_id
        )
        pol = (await self.session.execute(pol_stmt)).scalar_one()

        po_stmt = select(PurchaseOrder).where(PurchaseOrder.id == pol.po_id)
        po = (await self.session.execute(po_stmt)).scalar_one()

        pol._po_supplier_code = po.supplier_code or ""
        gr._po_line = pol
        gr._pol_sku = pol.sku
        gr._pol_supplier_code = po.supplier_code or ""
        gr._pol_scheme_code = pol.scheme_code

        return gr

    async def _get_position(
        self,
        *,
        sku: str,
        supplier_code: str,
        scheme_code: str,
    ) -> InventoryPosition | None:
        stmt = select(InventoryPosition).where(
            InventoryPosition.sku == sku,
            InventoryPosition.supplier_code == supplier_code,
            InventoryPosition.scheme_code == scheme_code,
        )
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def _resolve_unit_cost_aed(
        self,
        gr: Any,
        pol: Any,
    ) -> Decimal:
        """Determina el unit_cost_aed del GR usando prioridad definida en story."""
        received_at = gr.received_at or datetime.now(tz=timezone.utc)

        actual_breakdown: dict = gr.actual_breakdown or {}
        if actual_breakdown:
            # Reutiliza la misma lógica de compute_landed_aed del CostService.
            # currency_origin se infiere: si hay claves _aed asumimos AED,
            # si no, usamos la moneda del PO (fallback AED).
            currency = _infer_currency(actual_breakdown)
            result = await self._cost_svc.compute_landed_aed(
                breakdown=actual_breakdown,
                currency_origin=currency,
                effective_at=received_at,
            )
            if result is not None and result > Decimal("0"):
                return result

        if gr.actual_unit_price is not None:
            price = Decimal(str(gr.actual_unit_price))
            if price > Decimal("0"):
                fx_rate = await self._get_fx_rate(gr.fx_rate_id)
                return (price * fx_rate).quantize(_FOUR, rounding=ROUND_HALF_UP)

        landed_breakdown: dict = pol.landed_cost_breakdown or {}
        if landed_breakdown:
            currency = _infer_currency(landed_breakdown)
            result = await self._cost_svc.compute_landed_aed(
                breakdown=landed_breakdown,
                currency_origin=currency,
                effective_at=received_at,
            )
            if result is not None and result > Decimal("0"):
                return result

        unit_price = Decimal(str(pol.unit_price))
        fx_rate = await self._get_fx_rate(gr.fx_rate_id)
        return (unit_price * fx_rate).quantize(_FOUR, rounding=ROUND_HALF_UP)

    async def _get_fx_rate(self, fx_rate_id: UUID | None) -> Decimal:
        if fx_rate_id is None:
            return Decimal("1")
        from app.db.models.pricing import FXRate

        fx = await self.session.get(FXRate, fx_rate_id)
        if fx is None:
            return Decimal("1")
        return Decimal(str(fx.rate))

    async def _upsert_inventory_position(
        self,
        *,
        sku: str,
        supplier_code: str,
        scheme_code: str,
        qty_delta: Decimal,
        new_map: Decimal,
        last_gr_id: UUID,
    ) -> InventoryPosition:
        now = datetime.now(tz=timezone.utc)

        # Fetch current to compute new qty_on_hand.
        existing = await self._get_position(
            sku=sku, supplier_code=supplier_code, scheme_code=scheme_code
        )
        new_qty = (
            Decimal(str(existing.qty_on_hand)) + qty_delta
            if existing
            else qty_delta
        )

        stmt = (
            pg_insert(InventoryPosition)
            .values(
                sku=sku,
                supplier_code=supplier_code,
                scheme_code=scheme_code,
                qty_on_hand=new_qty,
                map_aed=new_map,
                last_gr_id=last_gr_id,
                last_updated_at=now,
            )
            .on_conflict_do_update(
                constraint="uq_inventory_positions",
                set_={
                    "qty_on_hand": new_qty,
                    "map_aed": new_map,
                    "last_gr_id": last_gr_id,
                    "last_updated_at": now,
                },
            )
            .returning(InventoryPosition)
        )
        result = await self.session.execute(stmt)
        await self.session.flush()

        pos = result.scalar_one_or_none()
        if pos is None:
            pos = await self._get_position(
                sku=sku, supplier_code=supplier_code, scheme_code=scheme_code
            )
        return pos  # type: ignore[return-value]

    async def _insert_cost_lot(
        self,
        *,
        sku: str,
        supplier_code: str,
        scheme_code: str,
        gr_id: UUID,
        qty: Decimal,
        unit_cost_aed: Decimal,
    ) -> None:
        lot = CostLot(
            sku=sku,
            supplier_code=supplier_code,
            scheme_code=scheme_code,
            gr_id=gr_id,
            qty_original=qty,
            qty_remaining=qty,
            unit_cost_aed=unit_cost_aed,
        )
        self.session.add(lot)
        await self.session.flush()

    async def _update_cost(
        self,
        *,
        sku: str,
        supplier_code: str,
        scheme_code: str,
        map_aed: Decimal,
        fx_rate_id: UUID | None,
        effective_at: datetime,
    ) -> None:
        """Actualiza o crea el Cost activo para el SKU con el nuevo MAP.

        Estrategia para CostService.update_cost() + trigger DB:
        El trigger `costs_compute_landed_aed_trg` recalcula `scheme_landed_aed`
        sumando el breakdown × FX. Para que `scheme_landed_aed == map_aed`,
        pasamos el MAP directamente en `map_override_aed` (clave sufijo `_aed`).
        El trigger lo suma directamente sin conversión FX, produciendo
        `scheme_landed_aed = map_aed`. Todas las claves originales del breakdown
        anterior se preservan si el Cost ya existe — el MAP override las
        reemplaza completamente porque es el único componente del nuevo breakdown.
        Esto es intencional: el MAP Engine establece el landed cost definitivo.

        Si no existe Cost activo, lo crea con currency_origin='AED' y
        fx_rate_id=None para que el trigger `costs_stamp_fx_trg` no intente
        buscar FX (AED → no necesita FX).
        """
        existing = await self._cost_svc.get_active(
            sku=sku,
            scheme_code=scheme_code,
            supplier_code=supplier_code or None,
        )

        breakdown = {"map_override_aed": str(map_aed)}

        if existing is None:
            try:
                await self._cost_svc.create_cost(
                    sku=sku,
                    scheme_code=scheme_code,
                    supplier_code=supplier_code or None,
                    currency_origin="AED",
                    effective_at=effective_at,
                    breakdown=breakdown,
                    fx_rate_id=None,
                )
            except Exception:
                logger.warning(
                    "map_service.create_cost_failed sku=%s scheme=%s — "
                    "updating scheme_landed_aed directly",
                    sku,
                    scheme_code,
                )
                # Fallback: UPDATE directo si el scheme requiere campos que no
                # tenemos (e.g. fob_eur required). No bloquea el MAP Engine.
                await self._direct_update_landed_aed(
                    sku=sku,
                    supplier_code=supplier_code,
                    scheme_code=scheme_code,
                    map_aed=map_aed,
                )
        else:
            try:
                await self._cost_svc.update_cost(
                    existing.id,
                    actor_id=None,
                    breakdown=breakdown,
                    fx_rate_id=None,
                    fx_inferred=False,
                )
            except Exception:
                logger.warning(
                    "map_service.update_cost_failed cost_id=%s — "
                    "updating scheme_landed_aed directly",
                    existing.id,
                )
                await self._direct_update_landed_aed(
                    sku=sku,
                    supplier_code=supplier_code,
                    scheme_code=scheme_code,
                    map_aed=map_aed,
                )

    async def _direct_update_landed_aed(
        self,
        *,
        sku: str,
        supplier_code: str,
        scheme_code: str,
        map_aed: Decimal,
    ) -> None:
        """UPDATE SQL directo sobre costs — fallback cuando update_cost falla
        por validación de breakdown (e.g. scheme con campos requeridos).
        Bypassa el trigger de cálculo escribiendo scheme_landed_aed directamente.
        """
        stmt = text(
            """
            UPDATE costs
               SET scheme_landed_aed = :map_aed,
                   updated_at = now()
             WHERE sku = :sku
               AND scheme_code = :scheme_code
               AND COALESCE(supplier_code, '') = :supplier_code
               AND status = 'active'
            """
        )
        await self.session.execute(
            stmt,
            {
                "map_aed": float(map_aed),
                "sku": sku,
                "scheme_code": scheme_code,
                "supplier_code": supplier_code or "",
            },
        )


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _infer_currency(breakdown: dict) -> str:
    """Infiere la moneda de origen del breakdown por sus sufijos de clave.

    Si todas las claves son `_aed` o `_pct`, no hay conversión → AED.
    Si hay alguna clave `_eur`, la moneda origen es EUR.
    Otros sufijos se infieren de la primera clave no-AED-no-pct encontrada.
    Fallback: AED.
    """
    for key in breakdown:
        kl = key.lower()
        if kl.endswith("_aed") or kl.endswith("_pct"):
            continue
        if kl.endswith("_eur"):
            return "EUR"
        # Intenta extraer sufijo genérico (_xxx donde xxx = 3 chars = currency)
        parts = kl.rsplit("_", 1)
        if len(parts) == 2 and len(parts[1]) == 3:
            return parts[1].upper()
    return "AED"
