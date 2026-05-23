"""Schemas Pydantic para el scraper Amazon UAE (EP-SCR-01)."""

from __future__ import annotations

from pydantic import BaseModel, Field


class ScrapeRunRequest(BaseModel):
    """Payload para disparar un batch de scraping."""

    skus: list[str] | None = Field(
        default=None,
        description="Lista de SKUs a scrapear. None = todos los productos activos.",
    )
    force: bool = Field(
        default=False,
        description="Re-scrapear aunque ya tengan candidatos recientes.",
    )


class ScrapeRunResponse(BaseModel):
    """Respuesta inmediata al encolar un batch de scraping."""

    job_id: str = Field(description="ID del grupo Celery encolado.")
    total_skus: int = Field(description="Número de SKUs encolados.")
    status: str = Field(default="queued", description="Estado inicial del job.")


class ScrapeJobStatus(BaseModel):
    """Estado de un job de scraping en curso o finalizado."""

    job_id: str = Field(description="ID del job o grupo Celery.")
    completed: int = Field(default=0, description="Tasks completadas con éxito.")
    total: int = Field(default=0, description="Total de tasks en el grupo.")
    failed: int = Field(default=0, description="Tasks fallidas.")
    status: str = Field(description="Estado general: pending | running | completed | failed.")
