"""Differ — compara :class:`ParsedRow` contra estado actual de `products`.

Genera un :class:`RowDiff` por fila con una de las acciones :class:`RowAction`:
- ``CREATE``    : SKU no existe en BD.
- ``UPDATE``    : SKU existe, ≥1 campo difiere y NO está en ``manual_locked_fields``.
- ``NO_CHANGE`` : SKU existe e idéntico.
- ``SKIP_LOCKED``: existe y los únicos campos que diferían están bloqueados manualmente.
- ``ERROR``     : :attr:`ParsedRow.errors` no vacío (cast falló, header roto, etc.).

El differ NO toca BD — sólo lee. Carga los SKUs en lotes con ``WHERE sku = ANY(:lst)``
para evitar N+1.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass, field
from decimal import Decimal
from enum import Enum
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.product import Product
from app.services.importer.parser import ParsedRow

# Campos que comparamos para detectar cambios (whitelist explícita).
# Fase B (mig 065/066): name_en/description_en/marketing_copy_en y active
# removidos — los textos en inglés viven en product_translations(lang='en')
# (su diff es responsabilidad de su propio differ futuro) y active deriva de
# lifecycle_status.
COMPARED_FIELDS: tuple[str, ...] = (
    "family",
    "subfamily",
    "type",
    "material",
    "dn",
    "pn",
    "connection",
    "brand",
    "specs",
    "dimensions",
    "weight",
    "weight_unit",
    "packaging",
    "intrastat_code",
    "erp_name",
    "data_quality",
    "lifecycle_status",
)


class RowAction(str, Enum):
    CREATE = "create"
    UPDATE = "update"
    NO_CHANGE = "no_change"
    SKIP_LOCKED = "skip_locked"
    ERROR = "error"


@dataclass(slots=True)
class RowDiff:
    row_index: int
    sku: str | None
    action: RowAction
    diff: dict[str, dict[str, Any]] = field(default_factory=dict)
    locked_fields_skipped: list[str] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)
    payload: dict[str, Any] = field(default_factory=dict)


def _normalize(v: Any) -> Any:
    """Normaliza valores para comparar — Decimal→str, dicts/lists pasan tal cual."""
    if isinstance(v, Decimal):
        return str(v)
    return v


def _compute_field_diff(payload: dict[str, Any], current: Product) -> dict[str, dict[str, Any]]:
    diff: dict[str, dict[str, Any]] = {}
    for f in COMPARED_FIELDS:
        if f not in payload:
            continue  # Importer no setea ese campo — preservar.
        new = _normalize(payload[f])
        old = _normalize(getattr(current, f, None))
        if new != old:
            diff[f] = {"from": old, "to": new}
    return diff


async def _bulk_load_existing(session: AsyncSession, skus: Sequence[str]) -> dict[str, Product]:
    if not skus:
        return {}
    stmt = select(Product).where(Product.sku.in_(skus))
    result = await session.execute(stmt)
    return {p.sku: p for p in result.scalars().all()}


async def compute_diff(session: AsyncSession, parsed_rows: Sequence[ParsedRow]) -> list[RowDiff]:
    """Genera el diff por fila contra el estado actual de `products`.

    Lee los SKUs existentes en una sola query (``WHERE sku = ANY``) y compara
    campo a campo. Respeta ``manual_locked_fields`` (si todos los campos en
    diff están bloqueados → ``SKIP_LOCKED``; si algunos sí, otros no, los
    locked se reportan en ``locked_fields_skipped`` y la action queda en
    ``UPDATE``).
    """
    # Filtra rows con SKU válido para query.
    skus = [r.sku for r in parsed_rows if r.sku is not None and not r.errors]
    existing_map = await _bulk_load_existing(session, skus)

    diffs: list[RowDiff] = []
    for r in parsed_rows:
        if r.errors:
            diffs.append(
                RowDiff(
                    row_index=r.row_index,
                    sku=r.sku,
                    action=RowAction.ERROR,
                    errors=list(r.errors),
                    payload=r.payload,
                )
            )
            continue
        if r.sku is None:
            diffs.append(
                RowDiff(
                    row_index=r.row_index,
                    sku=None,
                    action=RowAction.ERROR,
                    errors=["sku ausente"],
                    payload=r.payload,
                )
            )
            continue
        current = existing_map.get(r.sku)
        if current is None:
            diffs.append(
                RowDiff(
                    row_index=r.row_index,
                    sku=r.sku,
                    action=RowAction.CREATE,
                    payload=r.payload,
                )
            )
            continue
        field_diff = _compute_field_diff(r.payload, current)
        if not field_diff:
            diffs.append(
                RowDiff(
                    row_index=r.row_index,
                    sku=r.sku,
                    action=RowAction.NO_CHANGE,
                    payload=r.payload,
                )
            )
            continue
        locked = set(current.manual_locked_fields or [])
        # `manual_locked_fields` siempre puede reasignarse; lo excluimos del lock-check.
        locked_in_diff = [f for f in field_diff if f in locked and f != "manual_locked_fields"]
        unlocked = {f: v for f, v in field_diff.items() if f not in locked}
        if not unlocked:
            diffs.append(
                RowDiff(
                    row_index=r.row_index,
                    sku=r.sku,
                    action=RowAction.SKIP_LOCKED,
                    diff=field_diff,
                    locked_fields_skipped=locked_in_diff,
                    payload=r.payload,
                )
            )
        else:
            diffs.append(
                RowDiff(
                    row_index=r.row_index,
                    sku=r.sku,
                    action=RowAction.UPDATE,
                    diff=unlocked,
                    locked_fields_skipped=locked_in_diff,
                    payload=r.payload,
                )
            )
    return diffs
