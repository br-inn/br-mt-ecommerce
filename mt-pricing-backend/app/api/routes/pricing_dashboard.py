"""Pricing Observability Dashboard — endpoint agregado `/api/v1/dashboard/pricing-stats`.

Expone KPIs del workflow de aprobación de precios para el panel de observabilidad:
- Conteos de estado actual (pending_review, auto_approved, approved_today, escalated)
- Lag promedio de aprobación (pending_review → approved) en horas — últimos 7 días
- Top 3 exception rules más disparadas — últimos 7 días
- Tendencia diaria de 7 días (auto_approved / manual_approved por día)

Notas de diseño:
- Solo lectura. `get_current_user` garantiza auth sin filtrar por usuario.
- Todas las queries usan `func.count()` / `func.avg()` con índices existentes.
- TODO Cache 30s en Redis (clave `dashboard:pricing-stats:v1`) para reducir
  carga en horas pico (≥ 5 COUNT/refetch cada 60s desde el frontend).
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Annotated

from fastapi import APIRouter, Depends
from sqlalchemy import case, func, select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user, get_db_session
from app.db.models.pricing import ExceptionRule, Price, PriceApprovalEvent
from app.db.models.user import User
from app.schemas.pricing_dashboard import (
    DailyPricingTrend,
    ExceptionRuleHit,
    PricingDashboardStats,
)

router = APIRouter(prefix="/dashboard", tags=["Pricing Dashboard"])


@router.get(
    "/pricing-stats",
    response_model=PricingDashboardStats,
    summary="KPIs de observabilidad del workflow de aprobación de precios",
)
async def get_pricing_dashboard_stats(
    _user: Annotated[User, Depends(get_current_user)],
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> PricingDashboardStats:
    """Devuelve métricas de observabilidad del workflow de aprobación.

    Frontend refresca cada 60s (`refetchInterval: 60_000`).
    """
    now = datetime.now(timezone.utc)
    since_7d = now - timedelta(days=7)
    today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)

    # ------------------------------------------------------------------
    # 1. Conteos de estado actual (snapshot)
    # ------------------------------------------------------------------
    pending_review_count = await session.scalar(
        select(func.count()).select_from(Price).where(Price.status == "pending_review")
    )

    auto_approved_count = await session.scalar(
        select(func.count()).select_from(Price).where(Price.status == "auto_approved")
    )

    approved_today_count = await session.scalar(
        select(func.count())
        .select_from(Price)
        .where(
            Price.status.in_(["approved", "auto_approved"]),
            Price.approved_at >= today_start,
        )
    )

    escalated_count = await session.scalar(
        select(func.count()).select_from(Price).where(Price.escalated.is_(True))
    )

    # ------------------------------------------------------------------
    # 2. Lag promedio de aprobación (últimos 7 días)
    #
    # Estrategia: para cada precio aprobado en los últimos 7 días, buscar
    # el primer PriceApprovalEvent con to_status='pending_review' y el
    # primer PriceApprovalEvent con to_status IN ('approved','auto_approved').
    # El lag = approved_event.created_at - pending_event.created_at.
    #
    # Implementamos con dos subqueries correlacionadas (min created_at por
    # price_id + to_status) y un JOIN en Python sobre los resultados
    # escalares, para evitar SQL complejo en dialecto genérico.
    #
    # TODO Sprint N: migrar a CTE con LATERAL para reducir round-trips
    # cuando el volumen de precios aprobados supere ~10K/semana.
    # ------------------------------------------------------------------
    pending_events_q = (
        select(
            PriceApprovalEvent.price_id,
            func.min(PriceApprovalEvent.created_at).label("pending_at"),
        )
        .where(
            PriceApprovalEvent.to_status == "pending_review",
            PriceApprovalEvent.created_at >= since_7d,
        )
        .group_by(PriceApprovalEvent.price_id)
        .subquery()
    )

    approved_events_q = (
        select(
            PriceApprovalEvent.price_id,
            func.min(PriceApprovalEvent.created_at).label("approved_at"),
        )
        .where(
            PriceApprovalEvent.to_status.in_(["approved", "auto_approved"]),
            PriceApprovalEvent.created_at >= since_7d,
        )
        .group_by(PriceApprovalEvent.price_id)
        .subquery()
    )

    lag_result = await session.execute(
        select(
            pending_events_q.c.price_id,
            pending_events_q.c.pending_at,
            approved_events_q.c.approved_at,
        )
        .join(
            approved_events_q,
            pending_events_q.c.price_id == approved_events_q.c.price_id,
        )
        .where(approved_events_q.c.approved_at > pending_events_q.c.pending_at)
    )
    lag_rows = lag_result.all()

    if lag_rows:
        total_lag_hours = sum(
            (row.approved_at - row.pending_at).total_seconds() / 3600.0 for row in lag_rows
        )
        avg_approval_lag_hours = round(total_lag_hours / len(lag_rows), 2)
    else:
        avg_approval_lag_hours = 0.0

    # ------------------------------------------------------------------
    # 3. Top 3 exception rules más disparadas (últimos 7 días)
    #
    # `Price.rule_applied` almacena el código de la ExceptionRule que
    # disparó el estado pending_review. Agrupamos por rule_applied y
    # hacemos LEFT JOIN con exception_rules para obtener channel_id y
    # scheme_code.
    #
    # TODO: si rule_applied contiene valores no normalizados (texto libre),
    # revisar con el engine service para asegurar que siempre coincide
    # con ExceptionRule.code antes de confiar en este join.
    # ------------------------------------------------------------------
    top_rules_result = await session.execute(
        select(
            Price.rule_applied,
            ExceptionRule.channel_id,
            ExceptionRule.scheme_code,
            func.count(Price.id).label("hit_count"),
        )
        .outerjoin(ExceptionRule, Price.rule_applied == ExceptionRule.code)
        .where(
            Price.status == "pending_review",
            Price.rule_applied.is_not(None),
            Price.updated_at >= since_7d,
        )
        .group_by(Price.rule_applied, ExceptionRule.channel_id, ExceptionRule.scheme_code)
        .order_by(text("hit_count DESC"))
        .limit(3)
    )
    top_exception_rules = [
        ExceptionRuleHit(
            rule_code=row.rule_applied,
            channel_id=str(row.channel_id) if row.channel_id is not None else None,
            scheme_code=row.scheme_code,
            count=row.hit_count,
        )
        for row in top_rules_result.all()
    ]

    # ------------------------------------------------------------------
    # 4. Tendencia 7 días — conteo de eventos de aprobación por día
    #
    # Agrupa PriceApprovalEvent por fecha (UTC) y to_status para obtener
    # cuántos precios fueron auto-aprobados o aprobados manualmente por día.
    #
    # `pending` en DailyPricingTrend es el snapshot del conteo pending al
    # cierre del día — dato histórico no disponible sin tabla de snapshots.
    # TODO: añadir tabla `pricing_daily_snapshots` o un job nocturno que
    # persista el conteo pending_review de cada día para reportes históricos.
    # Por ahora se retorna 0 en el campo `pending`.
    # ------------------------------------------------------------------
    trend_result = await session.execute(
        select(
            func.date_trunc("day", PriceApprovalEvent.created_at).label("day"),
            func.count(
                case(
                    (PriceApprovalEvent.to_status == "auto_approved", 1),
                    else_=None,
                )
            ).label("auto_approved"),
            func.count(
                case(
                    (PriceApprovalEvent.to_status == "approved", 1),
                    else_=None,
                )
            ).label("manual_approved"),
        )
        .where(
            PriceApprovalEvent.to_status.in_(["approved", "auto_approved"]),
            PriceApprovalEvent.created_at >= since_7d,
        )
        .group_by(text("day"))
        .order_by(text("day ASC"))
    )
    daily_trend = [
        DailyPricingTrend(
            date=row.day.date().isoformat(),
            auto_approved=row.auto_approved,
            manual_approved=row.manual_approved,
            pending=0,
        )
        for row in trend_result.all()
    ]

    return PricingDashboardStats(
        pending_review_count=pending_review_count or 0,
        auto_approved_count=auto_approved_count or 0,
        approved_today_count=approved_today_count or 0,
        escalated_count=escalated_count or 0,
        avg_approval_lag_hours=avg_approval_lag_hours,
        top_exception_rules=top_exception_rules,
        daily_trend=daily_trend,
        as_of=now.isoformat(),
    )
