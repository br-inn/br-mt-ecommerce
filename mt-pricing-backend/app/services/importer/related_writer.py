"""Upsert idempotente de bloques relacionales de un artículo.

Consumido por el applier del wizard y por PimImporter (async). Lee las claves
reservadas `_translations`/`_releases`/`_uom_conversions`/`_bore_dimensions` y
hace upsert por su clave natural.
"""

from __future__ import annotations

from decimal import Decimal
from typing import Any
from uuid import UUID

from sqlalchemy import select, text
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.product import (
    ProductBoreDimension,
    ProductRelease,
    ProductTranslation,
    ProductUomConversion,
)

_TR_FIELDS = (
    "name",
    "description",
    "marketing_copy",
    "meta_title",
    "meta_description",
    "applications_text",
    "technical_limits",
    "notes",
    "marketing_features",
)
_REL_FIELDS = (
    "local_name",
    "local_description",
    "local_sku",
    "local_uom",
    "list_price",
    "price_currency",
    "tax_class",
)
_BORE_FIELDS = (
    "dn_nominal_ref",
    "pressure_class",
    "bore_mm",
    "face_to_face_mm",
    "end_to_end_mm",
    "flange_od_mm",
    "bolt_circle_mm",
    "bolt_count",
    "bolt_size",
    "notes",
)
_BORE_DECIMAL = {"bore_mm", "face_to_face_mm", "end_to_end_mm", "flange_od_mm", "bolt_circle_mm"}
_VALID_TR_STATUSES = frozenset(("pending", "draft", "approved"))


def _dec(v: Any) -> Decimal | None:
    return Decimal(str(v)) if v not in (None, "") else None


async def _upsert_translations(session: AsyncSession, sku: str, items: list[dict]) -> None:
    for it in items:
        lang = it.get("lang")
        if lang not in ("en", "es", "ar"):
            continue
        status = it.get("status")
        values: dict[str, Any] = {
            "sku": sku,
            "lang": lang,
            "status": status if status in _VALID_TR_STATUSES else "draft",
        }
        for f in _TR_FIELDS:
            if it.get(f) is not None:
                values[f] = it[f]
        update_set = {k: v for k, v in values.items() if k not in ("sku", "lang")}
        update_set["updated_at"] = text("now()")
        stmt = (
            pg_insert(ProductTranslation)
            .values(**values)
            .on_conflict_do_update(
                index_elements=["sku", "lang"],
                set_=update_set,
            )
        )
        await session.execute(stmt)


async def _upsert_releases(session: AsyncSession, sku: str, items: list[dict]) -> None:
    for it in items:
        if not it.get("market_code"):
            continue
        values: dict[str, Any] = {
            "product_sku": sku,
            "market_code": it["market_code"],
        }
        for f in _REL_FIELDS:
            if it.get(f) is not None:
                values[f] = _dec(it[f]) if f == "list_price" else it[f]
        update_set = {k: v for k, v in values.items() if k not in ("product_sku", "market_code")}
        update_set["updated_at"] = text("now()")
        stmt = (
            pg_insert(ProductRelease)
            .values(**values)
            .on_conflict_do_update(
                index_elements=["product_sku", "market_code"],
                set_=update_set,
            )
        )
        await session.execute(stmt)


async def _upsert_uom(session: AsyncSession, sku: str, items: list[dict]) -> None:
    for it in items:
        if not (it.get("uom_from") and it.get("uom_to") and it.get("factor")):
            continue
        values: dict[str, Any] = {
            "product_sku": sku,
            "uom_from": it["uom_from"],
            "uom_to": it["uom_to"],
            "factor": _dec(it["factor"]),
        }
        stmt = (
            pg_insert(ProductUomConversion)
            .values(**values)
            .on_conflict_do_update(
                index_elements=["product_sku", "uom_from", "uom_to"],
                set_={"factor": values["factor"]},
            )
        )
        await session.execute(stmt)


async def _upsert_bore(session: AsyncSession, sku: str, items: list[dict]) -> None:
    """Upsert bore dimensions using select-or-insert/update.

    The unique constraint (product_sku, standard_code, pressure_class) treats
    NULL pressure_class as distinct from every other NULL in PostgreSQL, so
    ON CONFLICT cannot be used when pressure_class IS NULL. We fall back to a
    manual SELECT + INSERT/UPDATE pattern that works in both cases.
    """
    for it in items:
        system = it.get("standard_system")
        code = it.get("standard_code")
        if not (system and code):
            continue
        pressure_class: str | None = it.get("pressure_class") or None

        # Build the field values to set/update
        fields: dict[str, Any] = {
            "standard_system": system,
            "is_primary": bool(it.get("is_primary", False)),
        }
        for f in _BORE_FIELDS:
            if f == "pressure_class":
                # handled as the lookup key separately
                continue
            if it.get(f) is None:
                continue
            if f in _BORE_DECIMAL:
                fields[f] = _dec(it[f])
            elif f == "bolt_count":
                try:
                    fields[f] = int(it[f])
                except (ValueError, TypeError):
                    # tolerant parsing — skip a non-integer bolt_count
                    continue
            else:
                fields[f] = it[f]

        # Look up existing row by natural key
        q = select(ProductBoreDimension).where(
            ProductBoreDimension.product_sku == sku,
            ProductBoreDimension.standard_code == code,
        )
        if pressure_class is None:
            q = q.where(ProductBoreDimension.pressure_class.is_(None))
        else:
            q = q.where(ProductBoreDimension.pressure_class == pressure_class)

        existing = (await session.execute(q)).scalar_one_or_none()
        if existing is None:
            session.add(
                ProductBoreDimension(
                    product_sku=sku,
                    standard_code=code,
                    pressure_class=pressure_class,
                    **fields,
                )
            )
            # Flush immediately so a subsequent iteration / re-apply sees this row
            # via the SELECT above. Production uses autoflush=False, so without
            # this the pending insert is invisible and we'd add a duplicate.
            await session.flush()
        else:
            for k, v in fields.items():
                setattr(existing, k, v)


async def apply_related_entities(
    session: AsyncSession,
    sku: str,
    payload: dict[str, Any],
    *,
    actor_id: UUID | None,
) -> None:
    """Upsert de todos los bloques relacionales presentes en `payload`."""
    if payload.get("_translations"):
        await _upsert_translations(session, sku, payload["_translations"])
    if payload.get("_releases"):
        await _upsert_releases(session, sku, payload["_releases"])
    if payload.get("_uom_conversions"):
        await _upsert_uom(session, sku, payload["_uom_conversions"])
    if payload.get("_bore_dimensions"):
        await _upsert_bore(session, sku, payload["_bore_dimensions"])


def pop_related_keys(payload: dict[str, Any]) -> dict[str, Any]:
    """Extrae (mutando) las claves reservadas del payload y las devuelve."""
    return {
        k: payload.pop(k)
        for k in ("_translations", "_releases", "_uom_conversions", "_bore_dimensions")
        if k in payload
    }
