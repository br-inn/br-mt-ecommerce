"""Exports API — US-1B-04-02 (generate export) + US-1B-04-05 (last-good query).

Endpoints:
- ``POST /exports/{channel_code}`` — genera CSV de precios approved/auto_approved.
- ``GET  /exports/last-good``       — consulta el export completado más reciente
  para una combinación (channel_code, scheme_code).

RBAC: requiere permiso ``channels:read``.
"""

from __future__ import annotations

from datetime import datetime, timezone
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, ConfigDict
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_db_session, require_permissions
from app.db.models.exports import LastGoodExport
from app.db.models.user import User
from app.services.pricing_export.export_service import ADAPTER_REGISTRY, ExportService


# ---------------------------------------------------------------------------
# Pydantic schema — US-1B-04-05
# ---------------------------------------------------------------------------
class LastGoodExportRead(BaseModel):
    """Snapshot del export completado más reciente por canal/scheme."""

    id: UUID
    channel_code: str
    scheme_code: str
    export_manifest_id: UUID | None
    rows_exported: int
    file_ref: str | None
    captured_at: datetime

    model_config = ConfigDict(from_attributes=True)

router = APIRouter(prefix="/exports", tags=["Exports"])


@router.post(
    "/{channel_code}",
    summary="Genera export CSV por canal (solo precios approved/auto_approved)",
    description=(
        "Genera un archivo CSV con todos los precios en estado ``approved`` o "
        "``auto_approved`` para el canal y scheme indicados. "
        "Las filas con otros estados se contabilizan en ``X-Rows-Blocked`` "
        "y quedan archivadas en ``exports_manifest``."
    ),
    responses={
        200: {"content": {"text/csv": {}}, "description": "CSV generado exitosamente."},
        400: {"description": "Payload inválido (errores de validación del adapter)."},
        404: {"description": "Canal o adapter no encontrado."},
    },
    operation_id="exportsGenerateChannelExport",
)
async def generate_channel_export(
    channel_code: str,
    scheme_code: str = Query(default="", description="Código del scheme (FBA, MARKETPLACE, etc.)"),
    session: AsyncSession = Depends(get_db_session),
    user: User = Depends(require_permissions("channels:read")),
) -> StreamingResponse:
    """Genera CSV de precios aprobados para el canal dado."""
    # Validar que el adapter existe para el canal
    adapter = ADAPTER_REGISTRY.get(channel_code.upper())
    if adapter is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=(
                f"No hay adapter registrado para el canal '{channel_code}'. "
                f"Canales soportados: {sorted(ADAPTER_REGISTRY.keys())}"
            ),
        )

    service = ExportService(session)
    try:
        csv_bytes, manifest = await service.generate_export(
            channel_code=channel_code.upper(),
            scheme_code=scheme_code,
            generated_by_user_id=user.id,
            adapter=adapter,
        )
    except LookupError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc

    date_str = datetime.now(tz=timezone.utc).strftime("%Y%m%d")
    filename = f"{channel_code.upper()}_{date_str}.csv"

    headers = {
        "Content-Disposition": f'attachment; filename="{filename}"',
        "X-Rows-Exported": str(manifest.rows_exported),
        "X-Rows-Blocked": str(manifest.rows_blocked),
        "X-Manifest-Id": str(manifest.id),
    }

    return StreamingResponse(
        iter([csv_bytes]),
        media_type="text/csv",
        headers=headers,
    )


@router.get(
    "/last-good",
    response_model=LastGoodExportRead,
    summary="Consulta el export completado más reciente para canal/scheme (US-1B-04-05)",
    responses={
        200: {"description": "Snapshot del último export completado."},
        404: {"description": "Aún no hay ningún export capturado para esta combinación."},
    },
    operation_id="exportsGetLastGood",
)
async def get_last_good_export(
    channel_code: str = Query(..., description="Código del canal (ej. AMAZON_UAE)"),
    scheme_code: str = Query(default="", description="Código del scheme (ej. DEFAULT, FBA)"),
    session: AsyncSession = Depends(get_db_session),
    _user: User = Depends(require_permissions("channels:read")),
) -> LastGoodExportRead:
    """Retorna el último export completado para la combinación canal/scheme dada.

    Responde 404 si el job diario aún no ha corrido o no hay exports completados.
    """
    stmt = select(LastGoodExport).where(
        LastGoodExport.channel_code == channel_code.upper(),
        LastGoodExport.scheme_code == scheme_code,
    )
    result = await session.execute(stmt)
    row = result.scalar_one_or_none()
    if row is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=(
                f"No hay último export conocido para canal='{channel_code.upper()}' "
                f"scheme='{scheme_code}'. "
                "El job diario aún no ha corrido o no existen exports completados."
            ),
        )
    return LastGoodExportRead.model_validate(row)


__all__ = ["router"]
