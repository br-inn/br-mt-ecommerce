"""Pydantic schemas — Dashboard `/api/v1/dashboard/stats` API contract.

Diseño:
- Endpoint read-only que agrega KPIs de varios dominios (catálogo, traducciones,
  usuarios, jobs, auditoría) en una sola respuesta para que el frontend lo
  consuma con un único refetch cada 30s.
- Mantenemos secciones tipadas (CatalogStats, TranslationStats, …) para que el
  frontend pueda renderizar cards independientes sin reparsear payloads sueltos.
"""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field


class CatalogStats(BaseModel):
    """Conteos del catálogo de productos (excluye soft-deleted)."""

    products_total: int = Field(ge=0, description="Total de SKUs no eliminados.")
    products_active: int = Field(ge=0, description="SKUs con `active=true`.")
    products_complete: int = Field(ge=0, description="SKUs con data_quality='complete'.")
    products_partial: int = Field(ge=0, description="SKUs con data_quality='partial'.")
    products_blocked: int = Field(
        ge=0,
        description="SKUs con data_quality NOT IN ('complete','partial') — bloqueados o demo.",
    )


class TranslationStats(BaseModel):
    """Cobertura de traducciones por idioma (status='approved')."""

    es_approved: int = Field(ge=0)
    ar_approved: int = Field(ge=0)
    es_coverage_pct: float = Field(ge=0.0, le=100.0)
    ar_coverage_pct: float = Field(ge=0.0, le=100.0)


class UserStats(BaseModel):
    """Conteo de usuarios aplicativos (excluye soft-deleted)."""

    total: int = Field(ge=0)
    with_role: int = Field(ge=0)
    without_role: int = Field(ge=0)


class RecentEvent(BaseModel):
    """Item de la actividad reciente (audit_events tail)."""

    model_config = ConfigDict(from_attributes=True)

    id: str
    actor_id: str | None = None
    entity_type: str
    action: str
    event_at: str


class ActivityStats(BaseModel):
    """Actividad de los últimos N segundos + tail de eventos."""

    audit_events_24h: int = Field(ge=0)
    recent_events: list[RecentEvent] = Field(default_factory=list)


class JobStats(BaseModel):
    """Salud del scheduler (Celery beat / DatabaseScheduler)."""

    enabled: int = Field(ge=0, description="JobDefinitions con enabled=true.")
    runs_24h: int = Field(ge=0, description="JobRuns iniciadas en 24h.")
    failures_24h: int = Field(
        ge=0, description="JobRuns con status='failed' iniciadas en 24h."
    )


class DashboardStatsResponse(BaseModel):
    """Respuesta agregada del endpoint `/api/v1/dashboard/stats`.

    `as_of` es ISO-8601 UTC; el frontend lo usa para mostrar "actualizado hace X".
    """

    catalog: CatalogStats
    translations: TranslationStats
    users: UserStats
    activity: ActivityStats
    jobs: JobStats
    as_of: str
