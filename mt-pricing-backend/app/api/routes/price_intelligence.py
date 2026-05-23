"""Price Intelligence API — KPI dashboard, listings por marca, quality monitor (US-SCR-04-06/07).

Endpoints:
- GET  /api/v1/price-intelligence/dashboard   — Price Gap, Price Index, Price Position
- GET  /api/v1/price-intelligence/listings/{brand_id} — productos con precios actuales
- GET  /api/v1/price-intelligence/quality     — histograma confidence scores 7d

RBAC: products:read en todos.
"""

from __future__ import annotations

import logging
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Query
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_db_session, require_permissions
from app.db.models.user import User

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/price-intelligence", tags=["price-intelligence"])

RequireRead = Annotated[User, Depends(require_permissions("products:read"))]


# ---------------------------------------------------------------------------
# GET /dashboard
# ---------------------------------------------------------------------------


@router.get("/dashboard")
async def get_price_intelligence_dashboard(
    current_user: RequireRead,
    session: Annotated[AsyncSession, Depends(get_db_session)],
    brand_id: UUID | None = Query(None, description="Filtrar por brand UUID"),
    marketplace: str | None = Query(None, description="amazon_uae | noon_uae"),
    date_from: datetime | None = Query(None, description="Inicio rango (ISO8601)"),
    date_to: datetime | None = Query(None, description="Fin rango (ISO8601)"),
    mt_price_aed: float | None = Query(None, description="Precio MT en AED para calcular KPIs"),
) -> dict:
    """Retorna KPIs de precio: Price Gap, Price Index, Price Position.

    Calcula desde price_daily_stats para el rango de fechas dado.
    Si no se especifica rango → últimos 30 días.
    """
    now = datetime.now(tz=UTC)
    date_to = date_to or now
    date_from = date_from or (now - timedelta(days=30))

    # ── Calcular estadísticas desde price_daily_stats ──────────────────────
    # Nota: price_daily_stats es una vista materializada; filtramos por stat_date
    # y, si hay brand_id, unimos con match_candidates → products → brands.

    params: dict = {
        "date_from": date_from.date(),
        "date_to": date_to.date(),
    }

    marketplace_clause = ""
    if marketplace:
        marketplace_clause = "AND pds.marketplace = :marketplace"
        params["marketplace"] = marketplace

    brand_clause = ""
    brand_join = ""
    if brand_id:
        brand_join = """
            INNER JOIN match_candidates mc ON pds.match_id = mc.id
            INNER JOIN products p ON mc.product_sku = p.sku
        """
        brand_clause = "AND p.brand_id = :brand_id"
        params["brand_id"] = brand_id

    sql = text(f"""
        SELECT
            COUNT(*)                        AS total_records,
            ROUND(AVG(pds.price_avg), 4)    AS mkt_avg_price,
            ROUND(MIN(pds.price_min), 4)    AS mkt_min_price,
            ROUND(MAX(pds.price_max), 4)    AS mkt_max_price,
            AVG(pds.sample_count)           AS avg_daily_samples
        FROM price_daily_stats pds
        {brand_join}
        WHERE pds.stat_date BETWEEN :date_from AND :date_to
          {marketplace_clause}
          {brand_clause}
    """)

    try:
        result = await session.execute(sql, params)
        row = result.mappings().first()
    except Exception as exc:
        # Matview no populada aún (ObjectNotInPrerequisiteStateError) u otro error DB
        logger.warning("price_intelligence.dashboard.query_failed", extra={"error": str(exc)[:200]})
        row = None

    mkt_avg = float(row["mkt_avg_price"]) if row and row["mkt_avg_price"] else None
    mkt_min = float(row["mkt_min_price"]) if row and row["mkt_min_price"] else None
    mkt_max = float(row["mkt_max_price"]) if row and row["mkt_max_price"] else None
    total_records = int(row["total_records"]) if row and row["total_records"] else 0

    # ── Price Gap: (MT price - mkt_avg) / mkt_avg × 100 ──────────────────
    # ── Price Index: MT price / mkt_avg × 100 ─────────────────────────────
    # ── Price Position: rank of MT price among competitor prices ──────────
    price_gap_pct = None
    price_index = None
    price_position_rank = None
    if mt_price_aed and mkt_avg and mkt_avg > 0:
        mt_dec = Decimal(str(mt_price_aed))
        price_gap_pct = round(
            float((mt_dec - Decimal(str(mkt_avg))) / Decimal(str(mkt_avg)) * 100), 2
        )
        price_index = round(float(mt_dec / Decimal(str(mkt_avg)) * 100), 2)
    if mt_price_aed and mkt_min and mkt_avg and mkt_avg > 0:
        price_position_rank = round(float(Decimal(str(mkt_min)) / Decimal(str(mkt_avg)) * 100), 1)

    return {
        "date_from": date_from.isoformat(),
        "date_to": date_to.isoformat(),
        "marketplace": marketplace,
        "brand_id": str(brand_id) if brand_id else None,
        "total_records": total_records,
        "market_stats": {
            "avg_price_aed": mkt_avg,
            "min_price_aed": mkt_min,
            "max_price_aed": mkt_max,
        },
        "kpis": {
            "price_gap_pct": price_gap_pct,
            "price_index": price_index,
            "price_position_rank": price_position_rank,
        },
        "note": "price_gap, price_index and price_position_rank require mt_price_aed query param",
    }


# ---------------------------------------------------------------------------
# GET /listings/{brand_id}
# ---------------------------------------------------------------------------


@router.get("/listings/{brand_id}")
async def get_brand_listings(
    brand_id: UUID,
    current_user: RequireRead,
    session: Annotated[AsyncSession, Depends(get_db_session)],
    marketplace: str | None = Query(None),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
) -> dict:
    """Lista productos de una marca con sus precios actuales en marketplace.

    Retorna match_candidates del marketplace, agrupados por SKU MT,
    con el último precio scrapeado.
    """
    marketplace_clause = ""
    params: dict = {"brand_id": brand_id, "limit": limit, "offset": offset}

    if marketplace:
        marketplace_clause = "AND mc.channel = :marketplace"
        params["marketplace"] = marketplace

    sql = text(f"""
        SELECT
            mc.id            AS candidate_id,
            mc.product_sku   AS sku,
            mc.channel       AS marketplace,
            mc.title         AS competitor_title,
            mc.price_aed     AS competitor_price_aed,
            mc.score,
            mc.status,
            mc.calibrated_confidence,
            p.brand_id,
            p.description    AS product_description
        FROM match_candidates mc
        INNER JOIN products p ON mc.product_sku = p.sku
        WHERE p.brand_id = :brand_id
          {marketplace_clause}
          AND mc.status != 'discarded'
        ORDER BY mc.score DESC, mc.product_sku
        LIMIT :limit OFFSET :offset
    """)

    result = await session.execute(sql, params)
    rows = result.mappings().all()

    # Count total
    count_sql = text(f"""
        SELECT COUNT(*) FROM match_candidates mc
        INNER JOIN products p ON mc.product_sku = p.sku
        WHERE p.brand_id = :brand_id
          {marketplace_clause}
          AND mc.status != 'discarded'
    """)
    count_result = await session.execute(
        count_sql, {k: v for k, v in params.items() if k not in ("limit", "offset")}
    )
    total = count_result.scalar() or 0

    listings = [
        {
            "candidate_id": str(row["candidate_id"]),
            "sku": row["sku"],
            "marketplace": row["marketplace"],
            "competitor_title": row["competitor_title"],
            "competitor_price_aed": float(row["competitor_price_aed"])
            if row["competitor_price_aed"]
            else None,
            "score": row["score"],
            "status": row["status"],
            "calibrated_confidence": float(row["calibrated_confidence"])
            if row["calibrated_confidence"]
            else None,
        }
        for row in rows
    ]

    return {
        "brand_id": str(brand_id),
        "total": total,
        "limit": limit,
        "offset": offset,
        "listings": listings,
    }


# ---------------------------------------------------------------------------
# GET /quality
# ---------------------------------------------------------------------------


@router.get("/quality")
async def get_matching_quality(
    current_user: RequireRead,
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> dict:
    """Histograma de confidence_score en últimos 7 días + mediana + pct > 0.8.

    Bins: [0-0.2, 0.2-0.4, 0.4-0.6, 0.6-0.8, 0.8-1.0].
    Solo incluye match_candidates con updated_at >= 7 días atrás.
    """
    seven_days_ago = datetime.now(tz=UTC) - timedelta(days=7)

    histogram_sql = text("""
        SELECT
            SUM(CASE WHEN calibrated_confidence < 0.5  THEN 1 ELSE 0 END) AS bin_0_50,
            SUM(CASE WHEN calibrated_confidence >= 0.5  AND calibrated_confidence < 0.7  THEN 1 ELSE 0 END) AS bin_50_70,
            SUM(CASE WHEN calibrated_confidence >= 0.7  AND calibrated_confidence < 0.85 THEN 1 ELSE 0 END) AS bin_70_85,
            SUM(CASE WHEN calibrated_confidence >= 0.85 THEN 1 ELSE 0 END) AS bin_85_100,
            PERCENTILE_CONT(0.5) WITHIN GROUP (ORDER BY calibrated_confidence) AS median_confidence,
            AVG(CASE WHEN calibrated_confidence >= 0.8 THEN 1.0 ELSE 0.0 END) AS pct_above_08
        FROM competitor_prices
        WHERE updated_at >= :cutoff
          AND calibrated_confidence IS NOT NULL
    """)

    result = await session.execute(histogram_sql, {"cutoff": seven_days_ago})
    row = result.mappings().first()

    if not row:
        return {
            "period_days": 7,
            "histogram": [],
            "median_confidence": None,
            "pct_above_80": None,
            "total": 0,
        }

    histogram = [
        {"bin": "0.0-0.5", "count": int(row["bin_0_50"] or 0)},
        {"bin": "0.5-0.7", "count": int(row["bin_50_70"] or 0)},
        {"bin": "0.7-0.85", "count": int(row["bin_70_85"] or 0)},
        {"bin": "0.85-1.0", "count": int(row["bin_85_100"] or 0)},
    ]

    return {
        "period_days": 7,
        "histogram": histogram,
        "median_confidence": float(row["median_confidence"]) if row["median_confidence"] else None,
        "pct_above_80": float(row["pct_above_08"]) if row["pct_above_08"] else None,
    }
