"""Dashboard KPIs — endpoint agregado para el panel principal del frontend.

Diseño:
- Una sola query GET `/api/v1/dashboard/stats` agrega contadores de varios
  dominios (catálogo, traducciones, usuarios, jobs, auditoría) para que el
  frontend renderice el panel con un único refetch (TanStack Query, 30s).
- Solo lectura. Auth requerida (`get_current_user`) — no exponemos KPIs a
  usuarios anónimos. No usamos `require_permissions` porque cualquier usuario
  autenticado debería ver el panel resumido (los detalles sí van con permiso).
- Las queries usan `func.count()` con filtros en `WHERE` para evitar cargar rows
  enteros — coste constante O(1) tras los índices existentes.

TODO Sprint 2:
- Cachear la respuesta 15s en Redis (clave `dashboard:stats:v1`) para evitar 5+
  COUNT(*) por refetch en horas pico.
- Sumar KPI de `prices` (proposed/approved/exported últimas 24h) cuando el
  dominio Pricing esté en master.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Annotated

from fastapi import APIRouter, Depends
from sqlalchemy import distinct, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user, get_db_session
from app.db.enums import DataQuality, JobStatus, TranslationStatus
from app.db.models import (
    AuditEvent,
    JobDefinition,
    JobRun,
    Product,
    ProductTranslation,
    User,
)
from app.schemas.dashboard import (
    ActivityStats,
    CatalogStats,
    DashboardStatsResponse,
    JobStats,
    RecentEvent,
    TranslationStats,
    UserStats,
)

router = APIRouter(prefix="/dashboard", tags=["Dashboard"])


def _pct(num: int, denom: int) -> float:
    """Porcentaje 0..100 con guarda contra division-by-zero."""
    if denom <= 0:
        return 0.0
    return round((num / denom) * 100.0, 2)


@router.get(
    "/stats",
    response_model=DashboardStatsResponse,
    summary="KPIs agregados del panel principal",
)
async def get_dashboard_stats(
    # `_user` es necesario sólo para forzar autenticación; el contenido del
    # panel no se filtra por usuario aún (Sprint 1 — todos los autenticados ven
    # los mismos KPIs globales).
    _user: Annotated[User, Depends(get_current_user)],
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> DashboardStatsResponse:
    """Devuelve KPIs de catálogo, traducciones, usuarios, actividad y jobs.

    Frontend refresca cada 30s (`refetchInterval`).
    """
    since_24h = datetime.now(timezone.utc) - timedelta(hours=24)

    # ----------------------------------------------------------------------
    # 1. Catálogo
    # ----------------------------------------------------------------------
    products_total = await session.scalar(
        select(func.count())
        .select_from(Product)
        .where(Product.deleted_at.is_(None))
    )
    products_active = await session.scalar(
        select(func.count())
        .select_from(Product)
        .where(Product.deleted_at.is_(None), Product.active.is_(True))
    )
    products_complete = await session.scalar(
        select(func.count())
        .select_from(Product)
        .where(
            Product.deleted_at.is_(None),
            Product.data_quality == DataQuality.COMPLETE.value,
        )
    )
    products_partial = await session.scalar(
        select(func.count())
        .select_from(Product)
        .where(
            Product.deleted_at.is_(None),
            Product.data_quality == DataQuality.PARTIAL.value,
        )
    )
    total_count = products_total or 0
    complete_count = products_complete or 0
    partial_count = products_partial or 0
    # blocked = todo lo que no es complete ni partial (incluye blocked + migrated_demo).
    blocked_count = max(total_count - complete_count - partial_count, 0)

    catalog = CatalogStats(
        products_total=total_count,
        products_active=products_active or 0,
        products_complete=complete_count,
        products_partial=partial_count,
        products_blocked=blocked_count,
    )

    # ----------------------------------------------------------------------
    # 2. Traducciones — count distinct sku con status='approved' por idioma.
    # ----------------------------------------------------------------------
    products_with_es = await session.scalar(
        select(func.count(distinct(ProductTranslation.sku))).where(
            ProductTranslation.lang == "es",
            ProductTranslation.status == TranslationStatus.APPROVED.value,
        )
    )
    products_with_ar = await session.scalar(
        select(func.count(distinct(ProductTranslation.sku))).where(
            ProductTranslation.lang == "ar",
            ProductTranslation.status == TranslationStatus.APPROVED.value,
        )
    )
    es_count = products_with_es or 0
    ar_count = products_with_ar or 0

    translations = TranslationStats(
        es_approved=es_count,
        ar_approved=ar_count,
        es_coverage_pct=_pct(es_count, total_count),
        ar_coverage_pct=_pct(ar_count, total_count),
    )

    # ----------------------------------------------------------------------
    # 3. Usuarios
    # ----------------------------------------------------------------------
    users_total = await session.scalar(
        select(func.count()).select_from(User).where(User.deleted_at.is_(None))
    )
    users_with_role = await session.scalar(
        select(func.count())
        .select_from(User)
        .where(User.deleted_at.is_(None), User.role_id.is_not(None))
    )
    users_total_count = users_total or 0
    users_with_role_count = users_with_role or 0

    users = UserStats(
        total=users_total_count,
        with_role=users_with_role_count,
        without_role=max(users_total_count - users_with_role_count, 0),
    )

    # ----------------------------------------------------------------------
    # 4. Auditoría — eventos 24h + tail de los 10 más recientes.
    # ----------------------------------------------------------------------
    audit_24h = await session.scalar(
        select(func.count())
        .select_from(AuditEvent)
        .where(AuditEvent.event_at >= since_24h)
    )
    recent_audit_rows = await session.execute(
        select(AuditEvent).order_by(AuditEvent.event_at.desc()).limit(10)
    )
    recent_events = [
        RecentEvent(
            id=str(e.id),
            actor_id=str(e.actor_id) if e.actor_id is not None else None,
            entity_type=e.entity_type,
            action=e.action,
            event_at=e.event_at.isoformat(),
        )
        for e in recent_audit_rows.scalars().all()
    ]

    activity = ActivityStats(
        audit_events_24h=audit_24h or 0,
        recent_events=recent_events,
    )

    # ----------------------------------------------------------------------
    # 5. Jobs / Scheduler
    # ----------------------------------------------------------------------
    jobs_enabled = await session.scalar(
        select(func.count())
        .select_from(JobDefinition)
        .where(JobDefinition.enabled.is_(True))
    )
    job_runs_24h = await session.scalar(
        select(func.count())
        .select_from(JobRun)
        .where(JobRun.started_at >= since_24h)
    )
    job_failures_24h = await session.scalar(
        select(func.count())
        .select_from(JobRun)
        .where(
            JobRun.started_at >= since_24h,
            JobRun.status == JobStatus.FAILURE.value,
        )
    )

    jobs = JobStats(
        enabled=jobs_enabled or 0,
        runs_24h=job_runs_24h or 0,
        failures_24h=job_failures_24h or 0,
    )

    return DashboardStatsResponse(
        catalog=catalog,
        translations=translations,
        users=users,
        activity=activity,
        jobs=jobs,
        as_of=datetime.now(timezone.utc).isoformat(),
    )
