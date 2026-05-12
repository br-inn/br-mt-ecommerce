"""Parallel run report API — app vs Excel diff (US-1B-05-01).

Endpoint:
- GET /parallel-run/report?date=YYYY-MM-DD
  Devuelve el reporte de diff generado por la task ``mt.pricing.parallel_run_diff``.
  Si no existe reporte para la fecha, genera uno on-demand (puede ser lento).
"""

from __future__ import annotations

from datetime import date
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_db_session, require_permissions
from app.db.models.user import User
from app.services.pricing.parallel_run_service import ParallelRunService

router = APIRouter(prefix="/parallel-run", tags=["parallel-run"])


@router.get(
    "/report",
    summary="Reporte diff app vs Excel (parallel run)",
    response_model=dict,
    responses={
        404: {
            "description": "No hay reporte para la fecha indicada y no se pudo generar",
        }
    },
)
async def get_parallel_run_report(
    report_date: Annotated[
        date,
        Query(
            alias="date",
            description="Fecha del reporte en formato YYYY-MM-DD",
            examples=["2026-05-12"],
        ),
    ],
    _user: Annotated[User, Depends(require_permissions("prices:read"))],
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> dict:
    """Devuelve el último reporte de parallel run para la fecha dada.

    Intenta recuperar desde caché Redis. Si no hay caché, genera el reporte
    on-demand consultando ``prices`` y ``price_reference_excel``.

    Query params:
        date: Fecha en formato YYYY-MM-DD (requerido).

    Returns:
        {
            "date": "YYYY-MM-DD",
            "generated_at": "<ISO datetime>",
            "total_skus": int,
            "flagged": int,
            "items": [
                {
                    "sku": str,
                    "channel": str,
                    "app_price_aed": str | null,
                    "excel_price_aed": str | null,
                    "deviation_pct": str | null,
                    "flagged": bool,
                },
                ...
            ]
        }
    """
    svc = ParallelRunService(session)

    # Intentar desde caché primero
    report = await svc.get_latest_report(report_date)
    if report is not None:
        return report

    # Generar on-demand si no hay caché
    try:
        report = await svc.generate_report(report_date)
    except Exception as exc:
        raise HTTPException(
            status_code=500,
            detail={
                "code": "parallel_run_error",
                "title": f"Error generando reporte: {exc}",
            },
        ) from exc

    if report is None:
        raise HTTPException(
            status_code=404,
            detail={
                "code": "report_not_found",
                "title": f"No hay reporte de parallel run para la fecha {report_date.isoformat()}",
            },
        )

    return report
