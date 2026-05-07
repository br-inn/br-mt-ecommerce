"""Imports → materials — API v1 routes (US-1A-06-03).

Endpoints:
- ``POST /imports/materials/preview``       — sube xlsx, parsea + summary.
- ``POST /imports/materials/{run_id}/apply`` — TRUNCATE + INSERT (mode='replace')
  o INSERT-only (``mode='append'``).
- ``GET  /imports/materials/{run_id}/status``

NO hay endpoint público de consulta de la tabla en S3 — la consume el matching
pipeline interno (US-1A-09-01-S3). UI tab Compatibilidades es S4.
"""

from __future__ import annotations

import asyncio
import io
import logging
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Annotated, Any

from fastapi import (
    APIRouter,
    Depends,
    File,
    HTTPException,
    Path,
    UploadFile,
)
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_db_session, require_permissions
from app.db.models.user import User
from app.repositories.material_compatibilities import (
    MaterialCompatibilitiesRepository,
)
from app.schemas.common import ProblemDetails
from app.schemas.imports_materials import (
    ImportMaterialsApplyRequest,
    ImportMaterialsApplyResponse,
    ImportMaterialsPreviewResponse,
)
from app.services.importer.importer_service import (
    ImportFileTooLargeError,
    ImporterDomainError,
    ImportHeaderMismatchError,
    ImportRunInvalidStateError,
    ImportRunNotFoundError,
    MAX_FILE_SIZE_BYTES,
)
from app.services.importer_materials import (
    ApplyMaterialsResult,
    MaterialsParseResult,
    apply_material_rows,
    parse_materials_xlsx_stream,
)

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/imports/materials", tags=["imports", "imports:materials"])


# -----------------------------------------------------------------------------
# In-memory run store (mismo patrón que el wizard PIM y el de costs)
# -----------------------------------------------------------------------------
@dataclass(slots=True)
class _MaterialsRunState:
    run_id: str
    kind: str
    filename: str
    status: str
    created_at: datetime
    created_by: str | None = None
    parse_result: MaterialsParseResult | None = None
    apply_result: ApplyMaterialsResult | None = None
    summary: dict[str, Any] = field(default_factory=dict)
    error: str | None = None


_RUN_STORE: dict[str, _MaterialsRunState] = {}
_RUN_LOCKS: dict[str, asyncio.Lock] = {}


def reset_run_store() -> None:  # pragma: no cover — tests-only
    _RUN_STORE.clear()
    _RUN_LOCKS.clear()


def _summarize(parse_result: MaterialsParseResult) -> dict[str, Any]:
    ok_rows = sum(1 for r in parse_result.rows if r.ok)
    err_rows = parse_result.total_data_rows - ok_rows
    return {
        "total": parse_result.total_data_rows,
        "ok": ok_rows,
        "errors": err_rows,
        "materials_columns": len(parse_result.materials_columns),
    }


def _raise_domain(err: ImporterDomainError) -> None:
    extra: dict[str, Any] = {"code": err.code, "title": err.message}
    if isinstance(err, ImportHeaderMismatchError):
        extra["header_errors"] = err.header_errors
    raise HTTPException(status_code=err.status_code, detail=extra)


# -----------------------------------------------------------------------------
# Endpoints
# -----------------------------------------------------------------------------
@router.post(
    "/preview",
    response_model=ImportMaterialsPreviewResponse,
    summary="Preview xlsx compatibilidades materiales",
    description=(
        "Sube un xlsx con compatibilidades material × temperatura, parsea "
        "y devuelve `run_id` + summary + samples. No persiste."
    ),
    operation_id="importMaterialsPreview",
    responses={
        413: {"model": ProblemDetails, "description": "Archivo demasiado grande"},
        422: {"model": ProblemDetails, "description": "Header mismatch o parse error"},
    },
)
async def preview_materials_import(
    file: Annotated[UploadFile, File(description="xlsx materiales (≤ 50 MB)")],
    user: Annotated[User, Depends(require_permissions("imports:write"))],
) -> ImportMaterialsPreviewResponse:
    if file.filename is None:
        raise HTTPException(
            status_code=422,
            detail={
                "code": "import_missing_filename",
                "title": "filename requerido",
            },
        )
    file_bytes = await file.read()
    if len(file_bytes) > MAX_FILE_SIZE_BYTES:
        _raise_domain(ImportFileTooLargeError(len(file_bytes), MAX_FILE_SIZE_BYTES))

    try:
        parse_result = parse_materials_xlsx_stream(io.BytesIO(file_bytes))
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(
            status_code=422,
            detail={
                "code": "import_materials_parse_failed",
                "title": f"Error parseando archivo: {exc}",
            },
        ) from exc
    if not parse_result.header_ok:
        _raise_domain(ImportHeaderMismatchError(parse_result.header_errors))

    run_id = uuid.uuid4().hex
    state = _MaterialsRunState(
        run_id=run_id,
        kind="materials",
        filename=file.filename,
        status="preview_ready",
        created_at=datetime.now(tz=timezone.utc),
        created_by=user.email if user is not None else None,
        parse_result=parse_result,
        summary=_summarize(parse_result),
    )
    _RUN_STORE[run_id] = state
    _RUN_LOCKS[run_id] = asyncio.Lock()

    samples: list[dict[str, Any]] = [
        {
            "row_index": r.row_index,
            "producto_descriptor": r.producto_descriptor,
            "temperatura_c": str(r.temperatura_c) if r.temperatura_c is not None else None,
            "compatibilities": r.compatibilities,
            "errors": r.errors,
        }
        for r in parse_result.rows[:20]
    ]

    return ImportMaterialsPreviewResponse(
        run_id=state.run_id,
        kind=state.kind,
        filename=state.filename,
        status=state.status,
        created_at=state.created_at,
        summary=state.summary,
        materials_columns=parse_result.materials_columns,
        samples=samples,
    )


@router.post(
    "/{run_id}/apply",
    response_model=ImportMaterialsApplyResponse,
    summary="Aplicar import (replace TRUNCATE+INSERT o append)",
    description=(
        "Confirma y aplica el run en modo `replace` (TRUNCATE + INSERT) o "
        "`append` (INSERT-only). Idempotente — un run sólo se aplica una vez."
    ),
    operation_id="importMaterialsApply",
    responses={
        404: {"model": ProblemDetails},
        409: {"model": ProblemDetails, "description": "Run en estado inválido"},
    },
)
async def apply_materials_import(
    run_id: Annotated[str, Path(min_length=1, max_length=64)],
    _user: Annotated[User, Depends(require_permissions("imports:write"))],
    session: Annotated[AsyncSession, Depends(get_db_session)],
    body: ImportMaterialsApplyRequest | None = None,
) -> ImportMaterialsApplyResponse:
    state = _RUN_STORE.get(run_id)
    if state is None:
        _raise_domain(ImportRunNotFoundError(run_id))
    if state.status != "preview_ready":
        _raise_domain(
            ImportRunInvalidStateError(
                run_id, current=state.status, expected="preview_ready"
            )
        )

    mode = body.mode if body is not None else "replace"
    repo = MaterialCompatibilitiesRepository(session)
    lock = _RUN_LOCKS.setdefault(run_id, asyncio.Lock())
    async with lock:
        state.status = "applying"
        try:
            assert state.parse_result is not None
            result = await apply_material_rows(
                state.parse_result.rows, repo=repo, mode=mode
            )
            state.apply_result = result
            state.status = "completed_with_errors" if result.errors > 0 else "completed"
            state.summary["applied_inserted"] = result.inserted
            state.summary["applied_truncated"] = result.truncated
            state.summary["applied_errors"] = result.errors
        except Exception as exc:  # noqa: BLE001
            logger.exception("Materials importer apply failed run_id=%s", run_id)
            state.status = "failed"
            state.error = f"{type(exc).__name__}: {exc!s}"
            raise HTTPException(
                status_code=500,
                detail={
                    "code": "import_materials_apply_failed",
                    "title": state.error,
                },
            ) from exc

    return ImportMaterialsApplyResponse(
        run_id=state.run_id,
        kind=state.kind,
        status=state.status,
        summary=state.summary,
        apply=state.apply_result.to_dict() if state.apply_result is not None else None,
        error=state.error,
    )


@router.get(
    "/{run_id}/status",
    response_model=ImportMaterialsApplyResponse,
    summary="Estado actual del run de materiales",
    description=(
        "Devuelve el estado in-memory del run de materiales (preview_ready, "
        "applying, completed, completed_with_errors, failed)."
    ),
    operation_id="importMaterialsGetStatus",
    responses={404: {"model": ProblemDetails}},
)
async def get_status(
    run_id: Annotated[str, Path(min_length=1, max_length=64)],
    _user: Annotated[User, Depends(require_permissions("imports:read"))],
) -> ImportMaterialsApplyResponse:
    state = _RUN_STORE.get(run_id)
    if state is None:
        _raise_domain(ImportRunNotFoundError(run_id))
    return ImportMaterialsApplyResponse(
        run_id=state.run_id,
        kind=state.kind,
        status=state.status,
        summary=state.summary,
        apply=state.apply_result.to_dict() if state.apply_result is not None else None,
        error=state.error,
    )
