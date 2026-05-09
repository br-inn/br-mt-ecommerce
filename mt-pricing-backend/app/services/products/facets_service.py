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

from uuid import UUID

from sqlalchemy import and_, exists, func, or_, select
from sqlalchemy.ext.asyncio import AsyncConnection, AsyncSession

from app.db.engine import get_engine
from app.db.models.product import Product, ProductTranslation
from app.db.models.vocabularies import (
    Division,
    Material,
    ProductDivision,
    Series,
    SeriesTier,
)
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
    # ---- Stage 3 (Wave 11) — division/series/tier/material curated ------
    division_code: str | None = None
    series_id: UUID | None = None
    material_id: UUID | None = None
    tier_code: str | None = None
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
                "division_code", "series_id", "material_id", "tier_code",
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
    # Stage 3 (Wave 11) — division (M:N EXISTS), series_id, material_id, tier.
    if filters.division_code and "division" not in exclude:
        div_sub = (
            select(ProductDivision.product_sku)
            .join(Division, Division.id == ProductDivision.division_id)
            .where(
                ProductDivision.product_sku == Product.sku,
                Division.code == filters.division_code,
            )
        )
        clauses.append(exists(div_sub))
    if filters.series_id and "series" not in exclude:
        clauses.append(Product.series_id == filters.series_id)
    if filters.material_id and "material_curated" not in exclude:
        clauses.append(Product.material_id == filters.material_id)
    if filters.tier_code and "tier_code" not in exclude:
        tier_sub = (
            select(Series.id)
            .join(SeriesTier, SeriesTier.id == Series.tier_id)
            .where(
                Series.id == Product.series_id,
                SeriesTier.code == filters.tier_code,
            )
        )
        clauses.append(exists(tier_sub))
    return clauses


# ---------------------------------------------------------------------------
# Per-dimension count queries (each excludes its own filter)
# ---------------------------------------------------------------------------
async def _count_by_column(
    session: AsyncSession | AsyncConnection,
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
    session: AsyncSession | AsyncConnection,
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
    session: AsyncSession | AsyncConnection, filters: ProductFilters
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
    session: AsyncSession | AsyncConnection, filters: ProductFilters, lang: str
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


async def _count_division(
    session: AsyncSession | AsyncConnection,
    filters: ProductFilters,
    *,
    limit: int = 50,
) -> list[FacetBucket]:
    """Counts por division.code (M:N) — refinement no destructivo."""
    clauses = build_product_clauses(filters, exclude={"division"})
    stmt = (
        select(Division.code.label("v"), func.count(ProductDivision.product_sku.distinct()).label("c"))
        .select_from(Product)
        .join(ProductDivision, ProductDivision.product_sku == Product.sku)
        .join(Division, Division.id == ProductDivision.division_id)
        .where(and_(*clauses))
        .group_by(Division.code)
        .order_by(func.count().desc())
        .limit(limit)
    )
    rows = (await session.execute(stmt)).all()
    return [
        FacetBucket(value=str(r.v), count=int(r.c)) for r in rows if r.v is not None
    ]


async def _count_series(
    session: AsyncSession | AsyncConnection,
    filters: ProductFilters,
    *,
    limit: int = 50,
) -> list[FacetBucket]:
    """Counts por series.code — joins products → series."""
    clauses = build_product_clauses(filters, exclude={"series"})
    stmt = (
        select(Series.code.label("v"), func.count().label("c"))
        .select_from(Product)
        .join(Series, Series.id == Product.series_id)
        .where(and_(*clauses))
        .group_by(Series.code)
        .order_by(func.count().desc())
        .limit(limit)
    )
    rows = (await session.execute(stmt)).all()
    return [
        FacetBucket(value=str(r.v), count=int(r.c)) for r in rows if r.v is not None
    ]


async def _count_tier(
    session: AsyncSession | AsyncConnection,
    filters: ProductFilters,
    *,
    limit: int = 20,
) -> list[FacetBucket]:
    """Counts por series_tiers.code (vía series.tier_id)."""
    clauses = build_product_clauses(filters, exclude={"tier_code"})
    stmt = (
        select(SeriesTier.code.label("v"), func.count().label("c"))
        .select_from(Product)
        .join(Series, Series.id == Product.series_id)
        .join(SeriesTier, SeriesTier.id == Series.tier_id)
        .where(and_(*clauses))
        .group_by(SeriesTier.code)
        .order_by(func.count().desc())
        .limit(limit)
    )
    rows = (await session.execute(stmt)).all()
    return [
        FacetBucket(value=str(r.v), count=int(r.c)) for r in rows if r.v is not None
    ]


async def _count_material_curated(
    session: AsyncSession | AsyncConnection,
    filters: ProductFilters,
    *,
    limit: int = 50,
) -> list[FacetBucket]:
    """Counts por material.code (vocab curado, vía material_id)."""
    clauses = build_product_clauses(filters, exclude={"material_curated"})
    stmt = (
        select(Material.code.label("v"), func.count().label("c"))
        .select_from(Product)
        .join(Material, Material.id == Product.material_id)
        .where(and_(*clauses))
        .group_by(Material.code)
        .order_by(func.count().desc())
        .limit(limit)
    )
    rows = (await session.execute(stmt)).all()
    return [
        FacetBucket(value=str(r.v), count=int(r.c)) for r in rows if r.v is not None
    ]


async def _total(session: AsyncSession | AsyncConnection, filters: ProductFilters) -> int:
    clauses = build_product_clauses(filters)
    stmt = select(func.count()).where(and_(*clauses))
    return int((await session.execute(stmt)).scalar_one() or 0)


async def _total_unfiltered(session: AsyncSession | AsyncConnection) -> int:
    stmt = select(func.count()).where(Product.deleted_at.is_(None))
    return int((await session.execute(stmt)).scalar_one() or 0)


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------
async def compute_facets(
    session: AsyncSession, filters: ProductFilters
) -> FacetsResponse:
    """Compute all dimensions in parallel with non-destructive refinements.

    Cada dimensión corre en una **conexión propia** del pool (``engine.connect``)
    para sortear la limitación de ``AsyncSession`` de 1 conexión simultánea.
    El ``session`` argumento queda como API estable; sólo se usa el engine.
    Para 5K-50K rows con los índices migration 041 esto reduce el wall clock
    de ~12×RTT secuencial a ~max(RTT) paralelo.

    Si el connection pool del backend está saturado (concurrencia muy alta),
    el ``async with engine.connect()`` espera al pool y degrada a serial sin
    romper.
    """
    engine = get_engine()

    async def _on_conn(coro_factory: Any) -> Any:
        async with engine.connect() as conn:
            return await coro_factory(conn)

    (
        family,
        material,
        dn,
        pn,
        data_quality,
        active,
        image_status,
        has_image,
        tr_es,
        tr_ar,
        total,
        total_unfiltered,
        division,
        series,
        tier_code,
        material_curated,
    ) = await asyncio.gather(
        _on_conn(lambda c: _count_by_column(c, Product.family, filters, exclude_field="family", limit=50)),
        _on_conn(lambda c: _count_by_column(c, Product.material, filters, exclude_field="material", limit=50)),
        _on_conn(lambda c: _count_by_column(c, Product.dn, filters, exclude_field="dn", limit=50)),
        _on_conn(lambda c: _count_by_column(c, Product.pn, filters, exclude_field="pn", limit=20)),
        _on_conn(lambda c: _enum_counts(c, Product.data_quality, filters, exclude_field="data_quality")),
        _on_conn(lambda c: _enum_counts(c, Product.active, filters, exclude_field="active")),
        _on_conn(lambda c: _enum_counts(c, Product.image_status, filters, exclude_field="image_status")),
        _on_conn(lambda c: _has_image_counts(c, filters)),
        _on_conn(lambda c: _translation_status_counts(c, filters, "es")),
        _on_conn(lambda c: _translation_status_counts(c, filters, "ar")),
        _on_conn(lambda c: _total(c, filters)),
        _on_conn(lambda c: _total_unfiltered(c)),
        # Stage 3 (Wave 11) — division/series/tier/material curated.
        _on_conn(lambda c: _count_division(c, filters)),
        _on_conn(lambda c: _count_series(c, filters)),
        _on_conn(lambda c: _count_tier(c, filters)),
        _on_conn(lambda c: _count_material_curated(c, filters)),
    )

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
        division=division,
        series=series,
        tier_code=tier_code,
        material_curated=material_curated,
    )
