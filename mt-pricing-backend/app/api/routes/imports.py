"""Imports — API v1 routes (US-1A-06-01).

Dos pipelines coexistentes:

**Wizard sincrono** (Pantalla 10, in-memory por proceso):
- ``POST /imports/preview``         — sube xlsx, parsea, devuelve diff por SKU.
- ``POST /imports/{run_id}/apply``  — aplica chunked savepoints cada 1000 rows.
- ``GET  /imports/{run_id}/status`` — estado actual + summary.
- ``GET  /imports/{run_id}/report`` — JSON o CSV (?format=csv).

**Batch async (Celery + ImportRun BD)** — para primer load PIM en dev y
imports recurrentes futuros:
- ``POST /imports/pim/upload``           — sube xlsx + dispara Celery task.
- ``POST /imports/pim/run-from-fixture`` — dev-only: corre desde filesystem.
- ``GET  /imports/runs/{run_id}``        — estado + counters del ImportRun.
- ``GET  /imports/runs``                 — lista runs paginada.

RBAC: ``imports:write`` (TI Integración + admin). Comercial NO puede aplicar.
"""

from __future__ import annotations

import os
from datetime import datetime
from typing import Annotated, Any
from uuid import UUID

from fastapi import (
    APIRouter,
    Depends,
    File,
    Form,
    HTTPException,
    Path,
    Query,
    Response,
    UploadFile,
    status,
)
from sqlalchemy import desc, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_db_session, require_permissions
from app.core.config import settings
from app.db.models.import_run import ImportRun
from app.db.models.user import User
from app.schemas.common import ProblemDetails
from app.schemas.importer import (
    AnalyzeImportResponse,
    ColumnMappingItemSchema,
    ImportApplyRequest,
    ImportPreviewResponse,
    ImportRunStatusResponse,
    ImportRunSummary,
)
from app.services.importer import ImporterService
from app.services.importer.importer_service import (
    ImporterDomainError,
    ImportHeaderMismatchError,
    ImportRunNotFoundError,
    _RUN_STORE,
)

router = APIRouter(prefix="/imports", tags=["imports"])


def get_importer_service(
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> ImporterService:
    return ImporterService(session)


def _raise_domain(err: ImporterDomainError) -> None:
    extra: dict[str, Any] = {"code": err.code, "title": err.message}
    if isinstance(err, ImportHeaderMismatchError):
        extra["header_errors"] = err.header_errors
    raise HTTPException(status_code=err.status_code, detail=extra)


def _state_to_summary_response(state: Any) -> ImportRunSummary:
    return ImportRunSummary(
        run_id=state.run_id,
        type=state.type_,
        filename=state.filename,
        status=state.status,
        created_at=state.created_at,
        created_by=state.created_by,
        summary=state.summary,
        error=state.error,
    )


@router.post(
    "/analyze",
    response_model=AnalyzeImportResponse,
    summary="Detectar estructura del xlsx y proponer mapeo via LLM",
    responses={
        413: {"model": ProblemDetails, "description": "Archivo demasiado grande"},
        422: {"model": ProblemDetails, "description": "No se pudo detectar cabecera"},
    },
)
async def analyze_import(
    file: Annotated[UploadFile, File(description="xlsx PIM (≤ 50 MB)")],
    _user: Annotated[User, Depends(require_permissions("imports:write"))],
) -> AnalyzeImportResponse:
    """Detecta la fila de cabecera real del xlsx y propone el mapeo de columnas
    via Claude. El frontend usa esta respuesta para mostrar el paso 'Mapeo'.
    """
    if file.filename is None:
        raise HTTPException(
            status_code=422,
            detail={"code": "import_missing_filename", "title": "filename requerido"},
        )
    file_bytes = await file.read()
    if len(file_bytes) > 50 * 1024 * 1024:
        raise HTTPException(
            status_code=413,
            detail={"code": "import_file_too_large", "title": "Archivo excede 50 MB"},
        )

    from app.services.importer.mapping_detector import detect_header_row, suggest_mapping

    try:
        header_idx, headers, samples = detect_header_row(file_bytes)
        proposed = suggest_mapping(headers, samples)
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(
            status_code=422,
            detail={"code": "import_header_detection_failed", "title": str(exc)},
        ) from exc
    sample_rows_safe = [
        [str(v) if v is not None else None for v in row]
        for row in samples
    ]

    return AnalyzeImportResponse(
        filename=file.filename,
        detected_header_row=header_idx,
        headers=headers,
        sample_rows=sample_rows_safe,
        proposed_mapping=[
            ColumnMappingItemSchema(
                excel_col=m.excel_col,
                target_field=m.target_field,
                transform=m.transform,
                confidence=m.confidence,
                notes=m.notes,
            )
            for m in proposed
        ],
    )


@router.post(
    "/preview",
    response_model=ImportPreviewResponse,
    summary="Subir xlsx PIM, parsear y devolver diff (preview)",
    responses={
        413: {"model": ProblemDetails, "description": "Archivo demasiado grande"},
        422: {"model": ProblemDetails, "description": "Header mismatch o parse error"},
    },
)
async def preview_import(
    file: Annotated[UploadFile, File(description="xlsx PIM (≤ 50 MB)")],
    user: Annotated[User, Depends(require_permissions("imports:write"))],
    service: Annotated[ImporterService, Depends(get_importer_service)],
    type_: Annotated[str, Query(alias="type", pattern=r"^(pim)$")] = "pim",
    mapping_json: Annotated[str | None, Form()] = None,
) -> ImportPreviewResponse:
    """Acepta un xlsx, lo parsea, computa el diff vs DB y devuelve summary +
    samples agrupados por bucket (create/update/no_change/skip_locked/error).
    """
    if file.filename is None:
        raise HTTPException(
            status_code=422,
            detail={"code": "import_missing_filename", "title": "filename requerido"},
        )
    file_bytes = await file.read()

    # Parsear mapping confirmado (si viene del paso de mapeo LLM).
    custom_mapping = None
    if mapping_json:
        import json as _json
        from app.services.importer.mapping_detector import ColumnMappingItem as _CMI
        try:
            raw_mapping = _json.loads(mapping_json)
            if not isinstance(raw_mapping, list):
                raise HTTPException(
                    status_code=422,
                    detail={"code": "import_invalid_mapping", "title": "mapping_json debe ser un array"},
                )
            custom_mapping = [
                _CMI(
                    excel_col=m["excel_col"],
                    target_field=m["target_field"],
                    transform=m.get("transform", "text"),
                    confidence=float(m.get("confidence", 1.0)),
                    notes=m.get("notes", ""),
                )
                for m in raw_mapping
                if isinstance(m, dict) and "excel_col" in m and "target_field" in m
            ]
            if not custom_mapping:
                raise HTTPException(
                    status_code=422,
                    detail={"code": "import_invalid_mapping", "title": "mapping_json no contiene items válidos"},
                )
        except HTTPException:
            raise
        except Exception:  # noqa: BLE001
            raise HTTPException(
                status_code=422,
                detail={"code": "import_invalid_mapping", "title": "mapping_json inválido"},
            )

    try:
        state = await service.preview(
            file_bytes=file_bytes,
            filename=file.filename,
            actor=user,
            type_=type_,
            custom_mapping=custom_mapping,
        )
    except ImporterDomainError as e:
        _raise_domain(e)
    samples_payload = service.report_json(state.run_id, sample_per_bucket=20)
    return ImportPreviewResponse(
        run_id=state.run_id,
        type=state.type_,
        filename=state.filename,
        status=state.status,
        created_at=state.created_at,
        summary=state.summary,
        samples=samples_payload["samples"],
    )


@router.post(
    "/{run_id}/apply",
    response_model=ImportRunStatusResponse,
    summary="Aplicar diffs del run (chunked savepoints)",
    responses={
        404: {"model": ProblemDetails},
        409: {"model": ProblemDetails, "description": "Run en estado inválido"},
    },
)
async def apply_import(
    run_id: Annotated[str, Path(min_length=1, max_length=64)],
    user: Annotated[User, Depends(require_permissions("imports:write"))],
    service: Annotated[ImporterService, Depends(get_importer_service)],
    body: ImportApplyRequest | None = None,
) -> ImportRunStatusResponse:
    chunk_size = (body.chunk_size if body is not None else 1000) or 1000
    division_codes = body.division_codes if body is not None else None
    try:
        state = await service.apply(
            run_id, user, chunk_size=chunk_size, division_codes=division_codes
        )
    except ImporterDomainError as e:
        _raise_domain(e)
    payload = service.report_json(run_id, sample_per_bucket=0)
    return ImportRunStatusResponse(
        run_id=state.run_id,
        type=state.type_,
        filename=state.filename,
        status=state.status,
        created_at=state.created_at,
        summary=state.summary,
        apply=payload["apply"],
        error=state.error,
    )


@router.get(
    "/{run_id}/status",
    response_model=ImportRunStatusResponse,
    summary="Estado del run + summary",
    responses={404: {"model": ProblemDetails}},
)
async def get_status(
    run_id: Annotated[str, Path(min_length=1, max_length=64)],
    _user: Annotated[User, Depends(require_permissions("imports:read"))],
    service: Annotated[ImporterService, Depends(get_importer_service)],
) -> ImportRunStatusResponse:
    try:
        state = service.get_status(run_id)
    except ImporterDomainError as e:
        _raise_domain(e)
    payload = service.report_json(run_id, sample_per_bucket=0)
    return ImportRunStatusResponse(
        run_id=state.run_id,
        type=state.type_,
        filename=state.filename,
        status=state.status,
        created_at=state.created_at,
        summary=state.summary,
        apply=payload["apply"],
        error=state.error,
    )


@router.get(
    "/{run_id}/report",
    summary="Report del run (JSON detallado o CSV)",
    responses={404: {"model": ProblemDetails}},
)
async def get_report(
    run_id: Annotated[str, Path(min_length=1, max_length=64)],
    _user: Annotated[User, Depends(require_permissions("imports:read"))],
    service: Annotated[ImporterService, Depends(get_importer_service)],
    format: Annotated[str, Query(pattern=r"^(json|csv)$")] = "json",
    sample_per_bucket: Annotated[int, Query(ge=0, le=500)] = 50,
) -> Any:
    try:
        if format == "csv":
            csv_text = service.report_csv(run_id)
            return Response(
                content=csv_text,
                media_type="text/csv",
                headers={
                    "Content-Disposition": (
                        f'attachment; filename="import_{run_id}_report.csv"'
                    )
                },
            )
        return service.report_json(run_id, sample_per_bucket=sample_per_bucket)
    except ImporterDomainError as e:
        _raise_domain(e)


# =============================================================================
# Batch async pipeline (Celery + ImportRun BD) — US-1A-06-01 (M2)
# =============================================================================
# Path donde el worker espera encontrar el PIM montado. Configurable via env
# para facilitar overrides en CI; default coincide con docker-compose.dev.yml.
_PIM_FIXTURE_PATH: str = os.environ.get(
    "PIM_FIXTURE_PATH", "/fixtures/PIM completo.xlsx"
)


def _serialize_import_run(run: ImportRun) -> dict[str, Any]:
    """Convierte ImportRun ORM a dict JSON-friendly para el frontend."""
    return {
        "run_id": str(run.id),
        "import_type": run.import_type,
        "source_filename": run.source_filename,
        "source_storage_path": run.source_storage_path,
        "status": run.status,
        "total_rows": run.total_rows,
        "inserted_rows": run.inserted_rows,
        "updated_rows": run.updated_rows,
        "skipped_rows": run.skipped_rows,
        "error_rows": run.error_rows,
        "errors": run.errors[:20] if run.errors else [],  # cap response
        "errors_total": len(run.errors) if run.errors else 0,
        "summary": run.summary or {},
        "started_at": run.started_at.isoformat() if run.started_at else None,
        "finished_at": run.finished_at.isoformat() if run.finished_at else None,
        "created_at": run.created_at.isoformat() if run.created_at else None,
        "triggered_by": str(run.triggered_by) if run.triggered_by else None,
        "celery_task_id": run.celery_task_id,
    }


@router.post(
    "/pim/upload",
    status_code=status.HTTP_202_ACCEPTED,
    summary="Subir xlsx PIM y disparar import async (Celery)",
    responses={
        413: {"model": ProblemDetails, "description": "Archivo demasiado grande"},
        503: {"model": ProblemDetails, "description": "Storage/Celery no disponible"},
    },
)
async def upload_and_run_pim(
    file: Annotated[UploadFile, File(description="xlsx PIM (≤ 50 MB)")],
    user: Annotated[User, Depends(require_permissions("imports:write"))],
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> dict[str, Any]:
    """Sube el xlsx a Supabase Storage y dispara la Celery task batch.

    Diferencias vs ``/imports/preview``:
    - Persiste ImportRun en BD (sobrevive restarts del backend).
    - Corre en worker (queue ``imports``) — no bloquea la request HTTP.
    - NO hace preview/diff visual — directamente upserta por SKU.
    """
    if file.filename is None:
        raise HTTPException(
            status_code=422,
            detail={
                "code": "import_missing_filename",
                "title": "filename requerido",
            },
        )
    file_bytes = await file.read()
    if len(file_bytes) > 50 * 1024 * 1024:  # 50 MB
        raise HTTPException(
            status_code=413,
            detail={
                "code": "import_file_too_large",
                "title": f"Archivo {len(file_bytes)} bytes excede 50 MB",
            },
        )

    # 1) Subir a Supabase Storage bucket imports-raw.
    storage_path = (
        f"pim/{datetime.utcnow():%Y/%m/%d}/{user.id}/{file.filename}"
    )
    try:
        from app.services.storage import upload_bytes

        upload_bytes(
            storage_path,
            file_bytes,
            content_type=(
                "application/vnd.openxmlformats-officedocument."
                "spreadsheetml.sheet"
            ),
            bucket=settings.SUPABASE_STORAGE_BUCKET_IMPORTS,
            upsert=True,
        )
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(
            status_code=503,
            detail={
                "code": "import_storage_failed",
                "title": f"No se pudo subir a Storage: {exc}",
            },
        ) from exc

    # 2) Persistir ImportRun en estado queued.
    run = ImportRun(
        import_type="pim",
        source_filename=file.filename,
        source_storage_path=(
            f"{settings.SUPABASE_STORAGE_BUCKET_IMPORTS}/{storage_path}"
        ),
        status="queued",
        triggered_by=user.id,
    )
    session.add(run)
    await session.flush()
    await session.commit()
    run_id = run.id

    # 3) Encolar Celery task. NOTE: el worker descarga el blob de Storage a /tmp.
    # En esta primera versión sólo soportamos disparo desde filesystem (fixture);
    # para upload via Storage habría que agregar un step de descarga. TODO Sprint 2.
    try:
        from app.workers.tasks.imports import run_pim_import_task

        async_result = run_pim_import_task.apply_async(
            args=[str(run_id), _PIM_FIXTURE_PATH, str(user.id)],
        )
        run.celery_task_id = async_result.id
        await session.commit()
    except Exception as exc:  # noqa: BLE001
        run.status = "failed"
        run.errors = [{"row": 0, "error": f"Celery dispatch failed: {exc}"}]
        await session.commit()
        raise HTTPException(
            status_code=503,
            detail={
                "code": "import_celery_unavailable",
                "title": "Celery no respondió, run marcado como failed.",
            },
        ) from exc

    return {
        "run_id": str(run_id),
        "status": run.status,
        "celery_task_id": run.celery_task_id,
        "source_storage_path": run.source_storage_path,
    }


@router.post(
    "/pim/run-from-fixture",
    status_code=status.HTTP_202_ACCEPTED,
    summary="DEV-ONLY: corre import del PIM completo.xlsx desde filesystem montado",
    responses={
        403: {"model": ProblemDetails, "description": "No es entorno dev"},
        503: {"model": ProblemDetails, "description": "Celery no disponible"},
    },
)
async def run_pim_from_fixture(
    user: Annotated[User, Depends(require_permissions("imports:write"))],
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> dict[str, Any]:
    """Dispara import del PIM real montado en `/fixtures/PIM completo.xlsx`.

    Sólo disponible en ENV=development. Crea ImportRun + encola Celery task.
    """
    if settings.ENV != "development":
        raise HTTPException(
            status_code=403,
            detail={
                "code": "import_fixture_forbidden",
                "title": "Endpoint solo disponible en development.",
            },
        )

    run = ImportRun(
        import_type="pim",
        source_filename="PIM completo.xlsx",
        source_storage_path=_PIM_FIXTURE_PATH,
        status="queued",
        triggered_by=user.id,
    )
    session.add(run)
    await session.flush()
    await session.commit()
    run_id = run.id

    try:
        from app.workers.tasks.imports import run_pim_import_task

        async_result = run_pim_import_task.apply_async(
            args=[str(run_id), _PIM_FIXTURE_PATH, str(user.id)],
        )
        run.celery_task_id = async_result.id
        await session.commit()
    except Exception as exc:  # noqa: BLE001
        run.status = "failed"
        run.errors = [{"row": 0, "error": f"Celery dispatch failed: {exc}"}]
        await session.commit()
        raise HTTPException(
            status_code=503,
            detail={
                "code": "import_celery_unavailable",
                "title": "Celery no respondió, run marcado como failed.",
            },
        ) from exc

    return {
        "run_id": str(run_id),
        "status": run.status,
        "celery_task_id": run.celery_task_id,
        "source_path": _PIM_FIXTURE_PATH,
    }


@router.get(
    "/runs/{run_id}",
    summary="Estado batch ImportRun (DB-backed)",
    responses={404: {"model": ProblemDetails}},
)
async def get_batch_run(
    run_id: Annotated[UUID, Path()],
    _user: Annotated[User, Depends(require_permissions("imports:read"))],
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> dict[str, Any]:
    """Consulta estado del run batch persistido. NO confundir con
    ``/imports/{run_id}/status`` (wizard in-memory)."""
    run = await session.get(ImportRun, run_id)
    if run is None:
        raise HTTPException(
            status_code=404,
            detail={
                "code": "import_run_not_found",
                "title": f"ImportRun {run_id} no existe.",
            },
        )
    return _serialize_import_run(run)


@router.get(
    "/{run_id}/rejected-rows",
    summary="Filas rechazadas del run wizard (in-memory)",
    responses={404: {"model": ProblemDetails}},
)
async def get_rejected_rows(
    run_id: Annotated[str, Path(min_length=1, max_length=64)],
    _user: Annotated[User, Depends(require_permissions("imports:read"))],
) -> dict[str, Any]:
    """Devuelve la lista de filas rechazadas (action=ERROR) del run wizard.

    Solo aplica a runs creados via ``POST /imports/preview`` (wizard in-memory).
    Para runs batch (Celery + ImportRun BD), consultar ``GET /imports/runs/{id}``.

    Si el run no existe → 404. Si el run existe pero no tiene rechazadas → lista vacía.
    """
    state = _RUN_STORE.get(run_id)
    if state is None:
        raise HTTPException(
            status_code=404,
            detail={
                "code": "import_run_not_found",
                "title": f"Import run {run_id!r} no existe.",
            },
        )
    rejected = state.rejected_rows
    return {
        "run_id": run_id,
        "total_rows": state.summary.get("total", 0),
        "rejected_count": len(rejected),
        "rejected_rows": [
            {
                "row_number": r.row_number,
                "sku": r.sku,
                "reasons": r.reasons,
            }
            for r in rejected
        ],
    }


@router.get(
    "/runs",
    summary="Lista batch ImportRuns paginada",
)
async def list_batch_runs(
    _user: Annotated[User, Depends(require_permissions("imports:read"))],
    session: Annotated[AsyncSession, Depends(get_db_session)],
    import_type: Annotated[str | None, Query(pattern=r"^(pim|costs|datasheets)$")] = None,
    status_filter: Annotated[
        str | None, Query(alias="status", pattern=r"^(queued|running|completed|completed_with_errors|failed)$")
    ] = None,
    limit: Annotated[int, Query(ge=1, le=200)] = 50,
) -> dict[str, Any]:
    stmt = select(ImportRun).order_by(desc(ImportRun.created_at))
    if import_type is not None:
        stmt = stmt.where(ImportRun.import_type == import_type)
    if status_filter is not None:
        stmt = stmt.where(ImportRun.status == status_filter)
    stmt = stmt.limit(limit)
    result = await session.execute(stmt)
    runs = result.scalars().all()
    return {
        "items": [_serialize_import_run(r) for r in runs],
        "count": len(runs),
    }
