"""Admin price calibration routes — US-F15-02-04.

Endpoints:
- ``GET   /admin/price-calibration``              — lista todos los rangos (paginado).
- ``POST  /admin/price-calibration/recalibrate``  — dispara Celery task recalibrate_price_ranges.
- ``GET   /admin/price-calibration/template``     — descarga CSV template (StreamingResponse).
- ``POST  /admin/price-calibration/import-csv``   — sube CSV (UploadFile) y hace UPSERT.

RBAC: usa ``calibrator:train`` (mismo permiso que el calibrador ML — admin + ti_integracion).
"""

from __future__ import annotations

import csv
import io
from datetime import UTC, datetime
from decimal import Decimal, InvalidOperation
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, UploadFile, status
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_db_session, require_permissions
from app.db.models.comparator import PriceCalibrationRange
from app.db.models.user import User

router = APIRouter(prefix="/admin/price-calibration", tags=["Price Calibration Admin"])

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------
_ALLOWED_CURRENCIES = {"AED", "USD", "EUR"}
_MAX_UPLOAD_BYTES = 5 * 1024 * 1024  # 5 MB


# ---------------------------------------------------------------------------
# Schemas
# ---------------------------------------------------------------------------
class PriceCalibrationRangeItem(BaseModel):
    """Fila de rango de calibración serializada para la API."""

    id: str
    category_id: str
    expected_min_p10: str  # Decimal serializado como string para evitar pérdida de precisión
    expected_max_p90: str
    currency: str
    updated_at: datetime

    model_config = {"from_attributes": True}


class PriceCalibrationListResponse(BaseModel):
    items: list[PriceCalibrationRangeItem]
    total: int
    page: int
    page_size: int


class ImportResult(BaseModel):
    inserted: int
    updated: int
    errors: list[str]


class RecalibrateResponse(BaseModel):
    task_id: str
    status: str


# ---------------------------------------------------------------------------
# Validation helpers
# ---------------------------------------------------------------------------
class _ValidationError(Exception):
    pass


class _RowError:
    def __init__(self, line: int, field: str, msg: str) -> None:
        self.line = line
        self.field = field
        self.msg = msg

    def __str__(self) -> str:
        return f"Línea {self.line} [{self.field}]: {self.msg}"


def _validate_row(
    row: dict[str, str],
    *,
    line: int,
    default_currency: str = "AED",
) -> tuple[str, Decimal, Decimal, str] | _RowError:
    """Valida una fila CSV y devuelve (category_id, min_p10, max_p90, currency) o un error."""
    category_id = (row.get("category_id") or "").strip()
    if not category_id:
        return _RowError(line, "category_id", "vacío")

    currency = (row.get("currency") or default_currency).strip().upper()
    if currency not in _ALLOWED_CURRENCIES:
        return _RowError(
            line,
            "currency",
            f"'{currency}' no permitido. Válidos: {sorted(_ALLOWED_CURRENCIES)}",
        )

    raw_min = (row.get("expected_min_p10") or "").strip()
    raw_max = (row.get("expected_max_p90") or "").strip()

    try:
        min_p10 = Decimal(raw_min)
    except InvalidOperation:
        return _RowError(line, "expected_min_p10", f"'{raw_min}' no es un decimal válido")

    try:
        max_p90 = Decimal(raw_max)
    except InvalidOperation:
        return _RowError(line, "expected_max_p90", f"'{raw_max}' no es un decimal válido")

    if min_p10 <= 0:
        return _RowError(line, "expected_min_p10", f"{min_p10} debe ser > 0")

    if min_p10 >= max_p90:
        return _RowError(
            line,
            "expected_max_p90",
            f"{max_p90} debe ser > expected_min_p10 ({min_p10})",
        )

    return (category_id, min_p10, max_p90, currency)


def _parse_csv_bytes(
    content: bytes,
    *,
    default_currency: str = "AED",
) -> tuple[list[tuple[str, Decimal, Decimal, str]], list[str]]:
    """Parsea CSV en bytes, valida filas y retorna (valid_rows, error_messages)."""
    try:
        text = content.decode("utf-8-sig")  # utf-8-sig maneja BOM de Excel
    except UnicodeDecodeError:
        text = content.decode("latin-1")

    reader = csv.DictReader(io.StringIO(text))
    valid: list[tuple[str, Decimal, Decimal, str]] = []
    errors: list[str] = []

    for line_num, row in enumerate(reader, start=2):  # start=2: fila 1 es header
        result = _validate_row(row, line=line_num, default_currency=default_currency)
        if isinstance(result, _RowError):
            errors.append(str(result))
        else:
            valid.append(result)

    return valid, errors


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------
@router.get(
    "",
    response_model=PriceCalibrationListResponse,
    summary="Lista rangos de calibración de precios (admin only — calibrator:train)",
)
async def list_price_calibration_ranges(
    session: Annotated[AsyncSession, Depends(get_db_session)],
    _user: User = Depends(require_permissions("calibrator:train")),
    page: int = Query(1, ge=1, description="Página (1-indexada)"),
    page_size: int = Query(50, ge=1, le=200, description="Filas por página"),
) -> PriceCalibrationListResponse:
    offset = (page - 1) * page_size

    total_result = await session.execute(
        select(func.count()).select_from(PriceCalibrationRange)
    )
    total = total_result.scalar_one()

    rows_result = await session.execute(
        select(PriceCalibrationRange)
        .order_by(PriceCalibrationRange.category_id, PriceCalibrationRange.currency)
        .offset(offset)
        .limit(page_size)
    )
    rows = rows_result.scalars().all()

    items = [
        PriceCalibrationRangeItem(
            id=str(row.id),
            category_id=row.category_id,
            expected_min_p10=str(row.expected_min_p10),
            expected_max_p90=str(row.expected_max_p90),
            currency=row.currency,
            updated_at=row.updated_at,
        )
        for row in rows
    ]

    return PriceCalibrationListResponse(
        items=items,
        total=total,
        page=page,
        page_size=page_size,
    )


@router.post(
    "/recalibrate",
    response_model=RecalibrateResponse,
    status_code=status.HTTP_202_ACCEPTED,
    summary="Dispara Celery task recalibrate_price_ranges (perm calibrator:train)",
)
async def trigger_recalibrate(
    _user: User = Depends(require_permissions("calibrator:train")),
) -> RecalibrateResponse:
    from app.workers.tasks.price_sanity import recalibrate_price_ranges

    result = recalibrate_price_ranges.delay()
    return RecalibrateResponse(task_id=result.id, status="queued")


@router.get(
    "/template",
    summary="Descarga CSV template con headers y fila de ejemplo (perm calibrator:train)",
)
async def download_template(
    session: Annotated[AsyncSession, Depends(get_db_session)],
    _user: User = Depends(require_permissions("calibrator:train")),
) -> StreamingResponse:
    rows_result = await session.execute(
        select(PriceCalibrationRange).order_by(
            PriceCalibrationRange.category_id, PriceCalibrationRange.currency
        )
    )
    existing = rows_result.scalars().all()

    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(["category_id", "expected_min_p10", "expected_max_p90", "currency"])

    if existing:
        # Exporta rangos existentes (modo backup)
        for row in existing:
            writer.writerow(
                [
                    row.category_id,
                    str(row.expected_min_p10),
                    str(row.expected_max_p90),
                    row.currency,
                ]
            )
    else:
        # Fila de ejemplo comentada (CSV no soporta '#', usamos campo prefijado)
        writer.writerow(["valve_family", "15.00", "850.00", "AED"])
        writer.writerow(["fitting_family", "2.50", "320.00", "AED"])
        writer.writerow(["default", "5.00", "500.00", "AED"])

    csv_content = output.getvalue()

    return StreamingResponse(
        iter([csv_content.encode("utf-8")]),
        media_type="text/csv",
        headers={
            "Content-Disposition": "attachment; filename=price_calibration_template.csv"
        },
    )


@router.post(
    "/import-csv",
    response_model=ImportResult,
    summary="Importa CSV con rangos de calibración (perm calibrator:train). Límite 5 MB.",
)
async def import_csv(
    file: UploadFile,
    session: Annotated[AsyncSession, Depends(get_db_session)],
    _user: User = Depends(require_permissions("calibrator:train")),
) -> ImportResult:
    # Verificar tamaño
    content = await file.read()
    if len(content) > _MAX_UPLOAD_BYTES:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail={
                "type": "https://mtme.ae/errors/payload-too-large",
                "title": "CSV demasiado grande",
                "status": 413,
                "detail": f"El archivo supera el límite de {_MAX_UPLOAD_BYTES // 1024 // 1024} MB.",
            },
        )

    valid_rows, errors = _parse_csv_bytes(content)

    if errors:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={
                "type": "https://mtme.ae/errors/csv-validation-failed",
                "title": "CSV inválido",
                "status": 422,
                "detail": f"{len(errors)} error(es) de validación en el CSV.",
                "errors": errors,
            },
        )

    if not valid_rows:
        return ImportResult(inserted=0, updated=0, errors=[])

    inserted = 0
    updated = 0
    now = datetime.now(tz=UTC)

    async with session.begin():
        for category_id, min_p10, max_p90, currency in valid_rows:
            existing_result = await session.execute(
                select(PriceCalibrationRange).where(
                    PriceCalibrationRange.category_id == category_id,
                    PriceCalibrationRange.currency == currency,
                )
            )
            existing = existing_result.scalar_one_or_none()

            if existing is not None:
                existing.expected_min_p10 = min_p10
                existing.expected_max_p90 = max_p90
                existing.updated_at = now
                updated += 1
            else:
                session.add(
                    PriceCalibrationRange(
                        category_id=category_id,
                        expected_min_p10=min_p10,
                        expected_max_p90=max_p90,
                        currency=currency,
                        updated_at=now,
                    )
                )
                inserted += 1

    return ImportResult(inserted=inserted, updated=updated, errors=[])


__all__ = ["router"]
