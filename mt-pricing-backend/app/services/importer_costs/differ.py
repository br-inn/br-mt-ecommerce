"""Differ — compara :class:`CostRow` contra el estado de `costs` y master data.

Genera un :class:`CostDiff` por fila con una de las acciones :class:`CostRowAction`:
- ``CREATE``        : (sku, scheme, supplier?) sin costo activo → crea uno nuevo.
- ``UPDATE``        : existe costo activo y los valores difieren (total/breakdown/currency).
- ``NO_CHANGE``     : existe e idéntico (no toca BD).
- ``ORPHAN``        : el SKU/scheme/supplier no existe en master data — reportable.
- ``ERROR``         : la fila tiene errores de parse/cast.

Adicionalmente computa un :class:`OrphanReport` agregado para el preview JSON.

NO toca BD si se pasa un session mock (los unit tests mockean
``_load_active_costs`` y los lookups de master data).
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass, field
from datetime import date
from decimal import Decimal
from enum import Enum
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.cost import Cost
from app.db.models.cost_scheme import CostScheme
from app.db.models.product import Product
from app.db.models.supplier import Supplier
from app.services.importer_costs.parser import CostRow


class CostRowAction(str, Enum):
    CREATE = "create"
    UPDATE = "update"
    NO_CHANGE = "no_change"
    ORPHAN = "orphan"
    ERROR = "error"


@dataclass(slots=True)
class CostDiff:
    row_index: int
    sku: str | None
    scheme_code: str | None
    supplier_code: str | None
    action: CostRowAction
    diff: dict[str, dict[str, Any]] = field(default_factory=dict)
    errors: list[str] = field(default_factory=list)
    orphan_reasons: list[str] = field(default_factory=list)
    payload: dict[str, Any] = field(default_factory=dict)


@dataclass(slots=True)
class OrphanReport:
    """Agregado para summary preview."""

    sku_not_in_pim: list[str] = field(default_factory=list)
    scheme_unknown: list[str] = field(default_factory=list)
    supplier_unknown: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, list[str]]:
        return {
            "sku_not_in_pim": self.sku_not_in_pim,
            "scheme_unknown": self.scheme_unknown,
            "supplier_unknown": self.supplier_unknown,
        }


def _normalize_decimal(v: Any) -> str | None:
    if v is None:
        return None
    if isinstance(v, Decimal):
        return str(v)
    return str(v)


def _build_payload(row: CostRow) -> dict[str, Any]:
    """Convierte CostRow → kwargs para ``CostService.create_cost``.

    Las claves coinciden con la firma actual del service (vigencia por rangos):
    ``sku`` / ``scheme_code`` / ``supplier_code`` / ``currency_origin`` /
    ``breakdown`` / ``valid_from``. ``valid_from`` default a hoy si la fila no
    lo trae (el parser ya lo resuelve, pero reforzamos por seguridad).
    """
    return {
        "sku": row.sku,
        "scheme_code": row.scheme_code,
        "supplier_code": row.supplier_code,
        "currency_origin": row.currency or "AED",
        "breakdown": dict(row.breakdown),
        "valid_from": row.valid_from or date.today(),
    }


def _compute_field_diff(payload: dict[str, Any], current: Cost) -> dict[str, dict[str, Any]]:
    """Diff entre el payload de import y el coste vigente a su ``valid_from``.

    Compara sólo lo que el importer realmente fija: ``currency_origin``,
    ``supplier_code`` y ``breakdown``. El ``scheme_landed_aed`` lo deriva el
    trigger DB a partir del breakdown, por lo que comparar breakdown ya cubre
    cambios de coste sin depender de un total preexistente.
    """
    diff: dict[str, dict[str, Any]] = {}
    fields_to_compare = {
        "currency_origin": ("currency_origin", lambda v: v),
        "supplier_code": ("supplier_code", lambda v: v),
    }
    for payload_key, (col, norm) in fields_to_compare.items():
        new_v = norm(payload.get(payload_key))
        old_v = norm(getattr(current, col, None))
        if new_v != old_v:
            diff[payload_key] = {"from": old_v, "to": new_v}
    new_bd = payload.get("breakdown") or {}
    old_bd = current.breakdown or {}
    if new_bd != old_bd:
        diff["breakdown"] = {"from": old_bd, "to": new_bd}
    return diff


async def _load_master_sets(
    session: AsyncSession, skus: Sequence[str], schemes: Sequence[str], suppliers: Sequence[str]
) -> tuple[set[str], set[str], set[str]]:
    """Carga sets de PKs existentes — usado para detectar huérfanos."""
    skus = list({s for s in skus if s})
    schemes = list({s for s in schemes if s})
    suppliers = list({s for s in suppliers if s})
    sku_set: set[str] = set()
    scheme_set: set[str] = set()
    supplier_set: set[str] = set()

    if skus:
        result = await session.execute(select(Product.sku).where(Product.sku.in_(skus)))
        sku_set = {row[0] for row in result.all()}
    if schemes:
        result = await session.execute(select(CostScheme.code).where(CostScheme.code.in_(schemes)))
        scheme_set = {row[0] for row in result.all()}
    if suppliers:
        result = await session.execute(select(Supplier.code).where(Supplier.code.in_(suppliers)))
        supplier_set = {row[0] for row in result.all()}

    return sku_set, scheme_set, supplier_set


def _norm_key(sku: str, scheme: str, supplier: str | None) -> tuple[str, str, str]:
    """Clave normalizada (supplier NULL == '') — coincide con la exclusión GiST."""
    return (sku, scheme, supplier or "")


async def _load_costs_for_keys(
    session: AsyncSession, keys: Sequence[tuple[str, str, str | None]]
) -> dict[tuple[str, str, str], list[Cost]]:
    """Carga TODAS las filas de coste (cualquier rango de vigencia) para los
    triples ``(sku, scheme, supplier?)`` presentes en el import.

    A diferencia de la versión anterior (sólo ``valid_to IS NULL``), traemos la
    cadena completa para poder resolver, por fila, el coste vigente al
    ``valid_from`` de esa fila — necesario para soportar filas con fecha futura.
    """
    if not keys:
        return {}
    skus = list({k[0] for k in keys})
    schemes = list({k[1] for k in keys})
    stmt = select(Cost).where(Cost.sku.in_(skus)).where(Cost.scheme_code.in_(schemes))
    result = await session.execute(stmt)
    out: dict[tuple[str, str, str], list[Cost]] = {}
    for c in result.scalars().all():
        out.setdefault(_norm_key(c.sku, c.scheme_code, c.supplier_code), []).append(c)
    return out


def _cost_as_of(
    by_key: dict[tuple[str, str, str], list[Cost]],
    key: tuple[str, str, str],
    on: date,
) -> Cost | None:
    """Devuelve la fila vigente a la fecha ``on`` para ``key``, o None.

    Vigente := ``valid_from <= on AND (valid_to IS NULL OR valid_to >= on)``.
    La exclusión GiST garantiza ≤1 fila; ante empates, gana el ``valid_from``
    más reciente (consistente con ``CostService.cost_as_of``).
    """
    candidates = [
        c
        for c in by_key.get(key, [])
        if c.valid_from <= on and (c.valid_to is None or c.valid_to >= on)
    ]
    if not candidates:
        return None
    return max(candidates, key=lambda c: c.valid_from)


async def compute_cost_diff(
    session: AsyncSession,
    parsed_rows: Sequence[CostRow],
) -> tuple[list[CostDiff], OrphanReport]:
    """Genera diffs por fila + reporte agregado de huérfanos."""
    valid_rows = [r for r in parsed_rows if not r.errors and r.sku and r.scheme_code]
    skus = [r.sku for r in valid_rows if r.sku]
    schemes = [r.scheme_code for r in valid_rows if r.scheme_code]
    suppliers = [r.supplier_code for r in valid_rows if r.supplier_code]

    sku_set, scheme_set, supplier_set = await _load_master_sets(session, skus, schemes, suppliers)
    costs_by_key = await _load_costs_for_keys(
        session,
        [(r.sku, r.scheme_code, r.supplier_code) for r in valid_rows],  # type: ignore[misc]
    )

    orphan_report = OrphanReport()
    diffs: list[CostDiff] = []

    for r in parsed_rows:
        if r.errors:
            diffs.append(
                CostDiff(
                    row_index=r.row_index,
                    sku=r.sku,
                    scheme_code=r.scheme_code,
                    supplier_code=r.supplier_code,
                    action=CostRowAction.ERROR,
                    errors=list(r.errors),
                    payload=_build_payload(r),
                )
            )
            continue

        orphan_reasons: list[str] = []
        if r.sku and r.sku not in sku_set:
            orphan_reasons.append("sku_not_in_pim")
            if r.sku not in orphan_report.sku_not_in_pim:
                orphan_report.sku_not_in_pim.append(r.sku)
        if r.scheme_code and r.scheme_code not in scheme_set:
            orphan_reasons.append("scheme_unknown")
            if r.scheme_code not in orphan_report.scheme_unknown:
                orphan_report.scheme_unknown.append(r.scheme_code)
        if r.supplier_code and r.supplier_code not in supplier_set:
            orphan_reasons.append("supplier_unknown")
            if r.supplier_code not in orphan_report.supplier_unknown:
                orphan_report.supplier_unknown.append(r.supplier_code)

        if orphan_reasons:
            diffs.append(
                CostDiff(
                    row_index=r.row_index,
                    sku=r.sku,
                    scheme_code=r.scheme_code,
                    supplier_code=r.supplier_code,
                    action=CostRowAction.ORPHAN,
                    orphan_reasons=orphan_reasons,
                    payload=_build_payload(r),
                )
            )
            continue

        payload = _build_payload(r)
        # Compara contra el coste vigente AL valid_from de la fila (no sólo el
        # rango abierto). Así una fila futura crea un rango nuevo aunque exista
        # un coste vigente hoy.
        on = r.valid_from or date.today()
        key = _norm_key(r.sku, r.scheme_code, r.supplier_code)  # type: ignore[arg-type]
        current = _cost_as_of(costs_by_key, key, on)
        if current is None:
            diffs.append(
                CostDiff(
                    row_index=r.row_index,
                    sku=r.sku,
                    scheme_code=r.scheme_code,
                    supplier_code=r.supplier_code,
                    action=CostRowAction.CREATE,
                    payload=payload,
                )
            )
            continue
        field_diff = _compute_field_diff(payload, current)
        if not field_diff:
            diffs.append(
                CostDiff(
                    row_index=r.row_index,
                    sku=r.sku,
                    scheme_code=r.scheme_code,
                    supplier_code=r.supplier_code,
                    action=CostRowAction.NO_CHANGE,
                    payload=payload,
                )
            )
        else:
            diffs.append(
                CostDiff(
                    row_index=r.row_index,
                    sku=r.sku,
                    scheme_code=r.scheme_code,
                    supplier_code=r.supplier_code,
                    action=CostRowAction.UPDATE,
                    diff=field_diff,
                    payload=payload,
                )
            )

    return diffs, orphan_report
