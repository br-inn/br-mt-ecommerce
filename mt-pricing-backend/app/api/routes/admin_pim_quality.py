"""PIM Data Quality Report — GET /admin/pim/data-quality.

Diagnostica gaps de calidad en el catálogo PIM:
- missing_name_en   : SKUs sin traducción lang='en' con name no vacío.
- missing_specs     : SKUs con specs JSONB vacío o NULL.
- missing_images    : SKUs sin assets de kind='photo' (tabla product_assets).
- missing_brand     : SKUs sin brand TEXT o brand vacío.
- missing_family    : SKUs sin family (NOT NULL en schema — siempre 0).
- specs_below_threshold: SKUs con specs JSONB con menos de 3 claves.

No requiere migración — usa modelos existentes (Product, ProductTranslation,
ProductAsset).

RBAC: ``admin:read`` (admin). Si no existe el permiso en el
token se devuelve 403 via require_permissions.
"""

from __future__ import annotations

import logging
from datetime import UTC, datetime
from typing import Annotated, Any

from fastapi import APIRouter, Depends
from sqlalchemy import func, select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_db_session, require_permissions
from app.db.models.product import Product, ProductAsset, ProductTranslation
from app.db.models.user import User

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/admin/pim", tags=["PIM Quality"])

_SPECS_THRESHOLD = 3
_SAMPLE_LIMIT = 5


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _pct(count: int, total: int) -> float:
    if total == 0:
        return 0.0
    return round(count / total * 100, 1)


async def _sample_skus(session: AsyncSession, stmt: Any, limit: int = _SAMPLE_LIMIT) -> list[str]:
    """Ejecuta stmt.limit(limit) y devuelve lista de SKUs (columna 0)."""
    result = await session.execute(stmt.limit(limit))
    return [row[0] for row in result.fetchall()]


# ---------------------------------------------------------------------------
# Service-level queries
# ---------------------------------------------------------------------------


async def _compute_data_quality(session: AsyncSession) -> dict[str, Any]:
    """Ejecuta todas las queries de calidad y retorna el dict de respuesta."""

    # 1. Total SKUs
    total_result = await session.execute(select(func.count()).select_from(Product))
    total: int = total_result.scalar_one()

    # 2. missing_name_en
    # SKUs donde NO existe una fila en product_translations con lang='en'
    # y name no vacío/NULL.
    missing_name_en_stmt = select(Product.sku).where(
        ~select(ProductTranslation.sku)
        .where(
            ProductTranslation.sku == Product.sku,
            ProductTranslation.lang == "en",
            ProductTranslation.name.isnot(None),
            ProductTranslation.name != "",
        )
        .correlate(Product)
        .exists()
    )
    missing_name_en_count_result = await session.execute(
        select(func.count()).select_from(missing_name_en_stmt.subquery())
    )
    missing_name_en_count: int = missing_name_en_count_result.scalar_one()
    missing_name_en_samples = await _sample_skus(session, missing_name_en_stmt)

    # 3. missing_specs
    # specs = '{}' o NULL
    missing_specs_stmt = select(Product.sku).where((Product.specs == {}) | Product.specs.is_(None))
    missing_specs_count_result = await session.execute(
        select(func.count()).select_from(missing_specs_stmt.subquery())
    )
    missing_specs_count: int = missing_specs_count_result.scalar_one()
    missing_specs_samples = await _sample_skus(session, missing_specs_stmt)

    # 4. missing_images — product_assets tabla existe (ProductAsset).
    # Buscamos SKUs sin ningún asset de kind='photo' con status='active'.
    missing_images_stmt = select(Product.sku).where(
        ~select(ProductAsset.sku)
        .where(
            ProductAsset.sku == Product.sku,
            ProductAsset.kind == "photo",
            ProductAsset.status == "active",
        )
        .correlate(Product)
        .exists()
    )
    missing_images_count_result = await session.execute(
        select(func.count()).select_from(missing_images_stmt.subquery())
    )
    missing_images_count: int = missing_images_count_result.scalar_one()
    missing_images_samples = await _sample_skus(session, missing_images_stmt)

    # 5. missing_brand
    missing_brand_stmt = select(Product.sku).where(
        (Product.brand.is_(None)) | (Product.brand == "")
    )
    missing_brand_count_result = await session.execute(
        select(func.count()).select_from(missing_brand_stmt.subquery())
    )
    missing_brand_count: int = missing_brand_count_result.scalar_one()
    missing_brand_samples = await _sample_skus(session, missing_brand_stmt)

    # 6. missing_family
    # family es NOT NULL en schema → siempre 0, pero lo calculamos defensivamente.
    missing_family_stmt = select(Product.sku).where(
        (Product.family.is_(None)) | (Product.family == "")
    )
    missing_family_count_result = await session.execute(
        select(func.count()).select_from(missing_family_stmt.subquery())
    )
    missing_family_count: int = missing_family_count_result.scalar_one()
    missing_family_samples = await _sample_skus(session, missing_family_stmt)

    # 7. specs_below_threshold
    # jsonb_object_keys devuelve setof text; contamos con subquery.
    # Usamos: jsonb_array_length(ARRAY(SELECT jsonb_object_keys(specs))) < threshold
    # Solo aplica a productos que tienen specs no vacío (excluimos missing_specs).
    specs_below_stmt = text(
        """
        SELECT sku
        FROM products
        WHERE specs IS NOT NULL
          AND specs != '{}'::jsonb
          AND (
              SELECT count(*)
              FROM jsonb_object_keys(specs)
          ) < :threshold
        """
    ).bindparams(threshold=_SPECS_THRESHOLD)
    specs_below_count_result = await session.execute(
        text(
            """
            SELECT count(*)
            FROM products
            WHERE specs IS NOT NULL
              AND specs != '{}'::jsonb
              AND (
                  SELECT count(*)
                  FROM jsonb_object_keys(specs)
              ) < :threshold
            """
        ).bindparams(threshold=_SPECS_THRESHOLD)
    )
    specs_below_count: int = specs_below_count_result.scalar_one()

    specs_below_sample_result = await session.execute(
        text(
            """
            SELECT sku
            FROM products
            WHERE specs IS NOT NULL
              AND specs != '{}'::jsonb
              AND (
                  SELECT count(*)
                  FROM jsonb_object_keys(specs)
              ) < :threshold
            LIMIT :lim
            """
        ).bindparams(threshold=_SPECS_THRESHOLD, lim=_SAMPLE_LIMIT)
    )
    specs_below_samples = [row[0] for row in specs_below_sample_result.fetchall()]

    return {
        "total_skus": total,
        "gaps": {
            "missing_name_en": {
                "count": missing_name_en_count,
                "pct": _pct(missing_name_en_count, total),
                "sample_skus": missing_name_en_samples,
            },
            "missing_specs": {
                "count": missing_specs_count,
                "pct": _pct(missing_specs_count, total),
                "sample_skus": missing_specs_samples,
            },
            "missing_images": {
                "count": missing_images_count,
                "pct": _pct(missing_images_count, total),
                "sample_skus": missing_images_samples,
            },
            "missing_brand": {
                "count": missing_brand_count,
                "pct": _pct(missing_brand_count, total),
                "sample_skus": missing_brand_samples,
            },
            "missing_family": {
                "count": missing_family_count,
                "pct": _pct(missing_family_count, total),
                "sample_skus": missing_family_samples,
            },
            "specs_below_threshold": {
                "count": specs_below_count,
                "pct": _pct(specs_below_count, total),
                "threshold": _SPECS_THRESHOLD,
                "sample_skus": specs_below_samples,
                "description": f"specs JSONB con menos de {_SPECS_THRESHOLD} campos",
            },
        },
        "generated_at": datetime.now(tz=UTC).isoformat(),
    }


# ---------------------------------------------------------------------------
# Endpoint
# ---------------------------------------------------------------------------


@router.get(
    "/data-quality",
    summary="PIM data quality report — gaps por categoría con sample SKUs",
    response_model=None,
)
async def get_pim_data_quality(
    session: Annotated[AsyncSession, Depends(get_db_session)],
    _user: Annotated[User, Depends(require_permissions("admin:read"))],
) -> dict[str, Any]:
    """Analiza el catálogo y devuelve conteos + porcentajes de gaps PIM.

    Queries ejecutadas contra ``products`` + ``product_translations`` +
    ``product_assets``. Sin paginación — es un snapshot diagnóstico.
    """
    return await _compute_data_quality(session)


__all__ = ["router", "_compute_data_quality"]
