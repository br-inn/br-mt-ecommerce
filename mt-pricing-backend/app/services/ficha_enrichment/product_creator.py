# mt-pricing-backend/app/services/ficha_enrichment/product_creator.py
"""Crea un Product nuevo en DB a partir de los datos extraídos de la ficha técnica."""
from __future__ import annotations

import logging
import uuid

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.product import Product
from app.db.models.vocabularies import Brand
from app.schemas.ficha_enrich import FichaExtractionResult, SkuApplyResult

logger = logging.getLogger(__name__)

_PATCHABLE_SCALARS = {
    "family", "subfamily", "type", "material", "dn", "pn",
    "connection", "brand", "weight", "weight_unit",
    "temp_min_c", "temp_max_c", "pressure_max_bar", "size",
}


async def _resolve_brand_id(session: AsyncSession, brand_name: str) -> uuid.UUID | None:
    """Busca brand_id por nombre (case-insensitive). Devuelve None si no existe."""
    result = await session.execute(
        select(Brand).where(func.lower(Brand.name) == brand_name.lower())
    )
    brand = result.scalar_one_or_none()
    return brand.id if brand else None


async def create_product_from_extraction(
    session: AsyncSession,
    sku: str,
    extraction: FichaExtractionResult,
) -> SkuApplyResult:
    """
    Crea un nuevo Product con los datos mínimos requeridos.
    Requiere que 'family' y 'brand' estén en la extracción y que el brand exista en DB.
    """
    scalars = extraction.scalars.model_dump(exclude_none=True)
    family = scalars.get("family")
    if not family:
        return SkuApplyResult(
            sku=sku,
            applied_fields=[],
            skipped_fields=list(scalars.keys()),
            warnings=["No se pudo crear el producto: 'family' no extraído del PDF"],
        )

    brand_name = scalars.get("brand", "")
    brand_id = await _resolve_brand_id(session, brand_name) if brand_name else None

    if brand_id is None:
        return SkuApplyResult(
            sku=sku,
            applied_fields=[],
            skipped_fields=list(scalars.keys()),
            warnings=[
                f"No se pudo crear el producto: brand '{brand_name}' no encontrado en DB. "
                "Crea primero el brand o asigna uno existente."
            ],
        )

    product = Product(
        sku=sku,
        family=family,
        brand_id=brand_id,
    )

    applied: list[str] = ["family"]
    skipped: list[str] = []

    for field, value in scalars.items():
        if field in ("family", "brand"):
            continue
        if field not in _PATCHABLE_SCALARS:
            skipped.append(field)
            continue
        try:
            setattr(product, field, value)
            applied.append(field)
        except Exception as exc:
            skipped.append(field)
            logger.warning("create_product: cannot set %s on new product: %s", field, exc)

    from app.services.ficha_enrichment.differ import _specs_to_dict
    specs_patch = _specs_to_dict(extraction)
    if specs_patch:
        product.specs = specs_patch
        applied.append("specs")

    session.add(product)
    await session.flush()

    return SkuApplyResult(
        sku=sku,
        applied_fields=applied,
        skipped_fields=skipped,
        warnings=[],
    )


__all__ = ["create_product_from_extraction"]
