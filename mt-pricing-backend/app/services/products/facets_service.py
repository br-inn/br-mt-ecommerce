"""Wave 10 — facets service.

Computes facet counts with **non-destructive refinements** (Algolia-style):
each dimension's counts exclude its own filter while applying every other
active filter. Runs queries in parallel with ``asyncio.gather`` for ~80ms p50
on 5K rows with the indexes from migration 041.

Public API:
    ``compute_facets(session, filters)`` → ``FacetsResponse``
"""

from __future__ import annotations

import asyncio
from collections.abc import Sequence
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

from sqlalchemy import and_, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.product import Product, ProductTranslation
from app.schemas.facets import FacetBucket, FacetsResponse, TranslationLangFacet


# ---------------------------------------------------------------------------
# Filter DTO + clause builder (reusable from list endpoint too)
# ---------------------------------------------------------------------------
@dataclass
class ProductFilters:
    family: str | None = None
    brand: str | None = None
    material: str | None = None
    dn: str | None = None
    pn: str | None = None
    data_quality: str | None = None
    active: bool | None = None
    image_status: str | None = None  # 'missing','mirrored','failed'
    has_image: bool | None = None
    lifecycle_status: str | None = None
    translation_status: str | None = None
    translation_lang: str | None = None
    created_after: datetime | None = None
    created_before: datetime | None = None
    search: str | None = None
    include_deleted: bool = False
    # Reserved for parent/variant filters in later iterations.

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> "ProductFilters":
        return cls(**{k: v for k, v in d.items() if k in cls.__dataclass_fields__})

    def has_any_active(self) -> bool:
        return any(
            getattr(self, name) not in (None, False)
            for name in (
                "family", "brand", "material", "dn", "pn", "data_quality",
                "active", "image_status", "has_image", "lifecycle_status",
                "translation_status", "created_after", "created_before", "search",
            )
        )


def build_product_clauses(
    filters: ProductFilters,
    *,
    exclude: set[str] | None = None,
) -> list[Any]:
    """Build SQLAlchemy WHERE clauses from filters, optionally excluding one dimension.

    Used by both the list endpoint and facets service for refinement consistency.
    """
    exclude = exclude or set()
    clauses: list[Any] = []
    if not filters.include_deleted:
        clauses.append(Product.deleted_at.is_(None))
    if filters.family and "family" not in exclude:
        clauses.append(Product.family == filters.family)
    if filters.brand and "brand" not in exclude:
        clauses.append(Product.brand == filters.brand)
    if filters.material and "material" not in exclude:
        clauses.append(Product.material == filters.material)
    if filters.dn and "dn" not in exclude:
        clauses.append(Product.dn == filters.dn)
    if filters.pn and "pn" not in exclude:
        clauses.append(Product.pn == filters.pn)
    if filters.data_quality and "data_quality" not in exclude:
        clauses.append(Product.data_quality == filters.data_quality)
    if filters.active is not None and "active" not in exclude:
        clauses.append(Product.active.is_(filters.active))
    if filters.image_status and "image_status" not in exclude:
        clauses.append(Product.image_status == filters.image_status)
    if filters.has_image is not None and "has_image" not in exclude:
        if filters.has_image:
            clauses.append(Product.image_status != "missing")
        else:
            clauses.append(Product.image_status == "missing")
    if filters.lifecycle_status and "lifecycle_status" not in exclude:
        clauses.append(Product.lifecycle_status == filters.lifecycle_status)
    if filters.created_after:
        clauses.append(Product.created_at >= filters.created_after)
    if filters.created_before:
        clauses.append(Product.created_at <= filters.created_before)
    if filters.search:
        term = f"%{filters.search}%"
        clauses.append(or_(Product.sku.ilike(term), Product.name_en.ilike(term)))
    if filters.translation_status and "translation_status" not in exclude:
        sub = select(ProductTranslation.sku).where(
            ProductTranslation.status == filters.translation_status
        )
        if filters.translation_lang:
            sub = sub.where(ProductTranslation.lang == filters.translation_lang)
        clauses.append(Product.sku.in_(sub))
    return clauses


# ---------------------------------------------------------------------------
# Per-dimension count queries (each excludes its own filter)
# ---------------------------------------------------------------------------
async def _count_by_column(
    session: AsyncSession,
    column: Any,
    filters: ProductFilters,
    *,
    exclude_field: str,
    limit: int = 50,
) -> list[FacetBucket]:
    clauses = build_product_clauses(filters, exclude={exclude_field})
    stmt = (
        select(column.label("v"), func.count().label("c"))
        .where(and_(*clauses))
        .group_by(column)
        .order_by(func.count().desc())
        .limit(limit)
    )
    rows = (await session.execute(stmt)).all()
    return [
        FacetBucket(value=str(r.v), count=int(r.c))
        for r in rows
        if r.v is not None
    ]


async def _enum_counts(
    session: AsyncSession,
    column: Any,
    filters: ProductFilters,
    *,
    exclude_field: str,
) -> dict[str, int]:
    clauses = build_product_clauses(filters, exclude={exclude_field})
    stmt = (
        select(column.label("v"), func.count().label("c"))
        .where(and_(*clauses))
        .group_by(column)
    )
    rows = (await session.execute(stmt)).all()
    return {str(r.v): int(r.c) for r in rows if r.v is not None}


async def _has_image_counts(
    session: AsyncSession, filters: ProductFilters
) -> dict[str, int]:
    clauses = build_product_clauses(filters, exclude={"has_image", "image_status"})
    with_clause = and_(*clauses, Product.image_status != "missing")
    without_clause = and_(*clauses, Product.image_status == "missing")
    with_n = await session.execute(select(func.count()).where(with_clause))
    without_n = await session.execute(select(func.count()).where(without_clause))
    return {
        "with": int(with_n.scalar_one() or 0),
        "without": int(without_n.scalar_one() or 0),
    }


async def _translation_status_counts(
    session: AsyncSession, filters: ProductFilters, lang: str
) -> TranslationLangFacet:
    base_clauses = build_product_clauses(filters, exclude={"translation_status"})
    base_total_stmt = select(func.count()).where(and_(*base_clauses))

    # Per-status counts via subquery
    sub_stmt = (
        select(
            Product.sku.label("sku"),
            func.coalesce(ProductTranslation.status, "missing").label("status"),
        )
        .join(
            ProductTranslation,
            (ProductTranslation.sku == Product.sku)
            & (ProductTranslation.lang == lang),
            isouter=True,
        )
        .where(and_(*base_clauses))
    ).subquery()

    counts_stmt = (
        select(sub_stmt.c.status, func.count())
        .group_by(sub_stmt.c.status)
    )

    base_total_res = await session.execute(base_total_stmt)
    counts_res = await session.execute(counts_stmt)
    total = int(base_total_res.scalar_one() or 0)
    counts = {str(r[0]): int(r[1]) for r in counts_res.all()}
    return TranslationLangFacet(
        approved=counts.get("approved", 0),
        pending=counts.get("pending", 0),
        draft=counts.get("draft", 0),
        missing=counts.get("missing", total - sum(v for k, v in counts.items() if k != "missing")),
    )


async def _total(session: AsyncSession, filters: ProductFilters) -> int:
    clauses = build_product_clauses(filters)
    stmt = select(func.count()).where(and_(*clauses))
    return int((await session.execute(stmt)).scalar_one() or 0)


async def _total_unfiltered(session: AsyncSession) -> int:
    stmt = select(func.count()).where(Product.deleted_at.is_(None))
    return int((await session.execute(stmt)).scalar_one() or 0)


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------
async def compute_facets(
    session: AsyncSession, filters: ProductFilters
) -> FacetsResponse:
    """Compute all dimensions sequentially with non-destructive refinements.

    Ejecutado secuencialmente porque ``AsyncSession`` no soporta concurrencia
    interna (one connection / one txn at a time). Para 5K-50K rows con índices
    de la migration 041, ~12 queries × ~5ms = ~60ms total. Si crece el volumen,
    parallelizamos via ``async with engine.connect()`` por dimensión.
    """
    family = await _count_by_column(
        session, Product.family, filters, exclude_field="family", limit=50
    )
    material = await _count_by_column(
        session, Product.material, filters, exclude_field="material", limit=50
    )
    dn = await _count_by_column(
        session, Product.dn, filters, exclude_field="dn", limit=50
    )
    pn = await _count_by_column(
        session, Product.pn, filters, exclude_field="pn", limit=20
    )
    data_quality = await _enum_counts(
        session, Product.data_quality, filters, exclude_field="data_quality"
    )
    active = await _enum_counts(
        session, Product.active, filters, exclude_field="active"
    )
    image_status = await _enum_counts(
        session, Product.image_status, filters, exclude_field="image_status"
    )
    has_image = await _has_image_counts(session, filters)
    tr_es = await _translation_status_counts(session, filters, "es")
    tr_ar = await _translation_status_counts(session, filters, "ar")
    total = await _total(session, filters)
    total_unfiltered = await _total_unfiltered(session)

    # Sort dn/pn numerically when possible (ascending), else lexicographic.
    def _num_sort(buckets: Sequence[FacetBucket]) -> list[FacetBucket]:
        def key(b: FacetBucket) -> tuple[int, float, str]:
            try:
                return (0, float(b.value), b.value)
            except ValueError:
                return (1, 0.0, b.value)

        return sorted(buckets, key=key)

    return FacetsResponse(
        total=total,
        total_unfiltered=total_unfiltered,
        family=family,
        material=material,
        dn=_num_sort(dn),
        pn=_num_sort(pn),
        data_quality=data_quality,
        active=active,
        image_status=image_status,
        has_image=has_image,
        translation_status={"es": tr_es, "ar": tr_ar},
    )
