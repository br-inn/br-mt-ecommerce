"""Pydantic schemas para Brand Extractor (US-SCR-05-03)."""
from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel


class BrandExtractorRead(BaseModel):
    """Payload de GET /competitor-brands/{id}/extractor."""

    brand_id: UUID
    marketplace: str
    generated_at: datetime | None
    generated_by: str | None
    hit_rate: float  # 0.0 a 1.0
    sample_asins: list[str]
    attribute_count: int  # len(attribute_map)
    last_used_at: datetime | None

    model_config = {"from_attributes": False}


class ExtractorStatRow(BaseModel):
    """Fila del listado GET /scraper/extractor-stats."""

    brand_id: UUID
    brand_name: str
    marketplace: str
    hit_rate: float
    generated_at: datetime | None
    attribute_count: int


class ExtractorCoverageStats(BaseModel):
    """Payload de GET /competitor-brands/{id}/extractor/coverage-stats (US-SCR-05-04)."""

    brand_id: UUID
    marketplace: str
    hit_rate_current: float
    hit_rate_baseline: float  # asumida 0.80 si no hay alerta previa
    delta_pp: float           # (baseline - current) * 100, positivo = degradación
    alert_active: bool
    alert_id: UUID | None = None
