"""ImporterService — orquesta preview/apply/status/report (US-1A-06-01).

S2-scope:
- Persistencia de runs **en memoria por proceso** (suficiente para el wizard
  Pantalla 10 demo y para tests). Cuando llegue la migración ``import_runs``
  (Apéndice B sprint2-backlog → S3 si Agente 1 no la entrega en S2), reemplazar
  el dict ``_RUN_STORE`` por un repository.
- Subida del archivo: el binario crudo se mantiene en memoria asociado al
  ``run_id`` mientras dura el proceso. Por defecto ``MAX_FILE_SIZE = 50 MB``.
- ``apply()`` es serializado por ``run_id`` con ``asyncio.Lock`` (un mismo run
  no se aplica dos veces concurrentemente). Locks cross-tipo (e.g. evitar 2
  PIM applies simultáneos) llegan con ``pg_advisory_lock`` en S3.

Persistencia diff: se guarda la lista completa de :class:`RowDiff` en memoria
para servir luego ``GET /imports/{id}/report``.
"""

from __future__ import annotations

import asyncio
import csv
import io
import logging
import uuid
from collections.abc import Sequence
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.user import User
from app.services.importer.applier import ApplyResult, apply_diffs_chunked
from app.services.importer.differ import RowAction, RowDiff, compute_diff
from app.services.importer.mapping_detector import detect_header_row
from app.services.importer.parser import ParseResult

logger = logging.getLogger(__name__)

MAX_FILE_SIZE_BYTES: int = 50 * 1024 * 1024  # 50 MB (NFR-import-01)


class ImporterDomainError(Exception):
    """Errores de negocio recoverables — 4xx en routes."""

    def __init__(self, code: str, message: str, status_code: int = 400) -> None:
        super().__init__(message)
        self.code = code
        self.message = message
        self.status_code = status_code


class ImportRunNotFoundError(ImporterDomainError):
    def __init__(self, run_id: str) -> None:
        super().__init__(
            code="import_run_not_found",
            message=f"Import run {run_id!r} no existe.",
            status_code=404,
        )


class ImportRunInvalidStateError(ImporterDomainError):
    def __init__(self, run_id: str, current: str, expected: str) -> None:
        super().__init__(
            code="import_run_invalid_state",
            message=(f"Run {run_id!r} en estado {current!r}; se esperaba {expected!r}."),
            status_code=409,
        )


class ImportFileTooLargeError(ImporterDomainError):
    def __init__(self, size: int, max_size: int) -> None:
        super().__init__(
            code="import_file_too_large",
            message=f"Archivo de {size} bytes excede el máximo de {max_size}.",
            status_code=413,
        )


class ImportHeaderMismatchError(ImporterDomainError):
    def __init__(self, header_errors: Sequence[str]) -> None:
        super().__init__(
            code="import_header_mismatch",
            message="Header del archivo no coincide con el mapping esperado.",
            status_code=422,
        )
        self.header_errors = list(header_errors)


@dataclass(slots=True)
class RejectedRow:
    """Fila rechazada durante el parse o el apply."""

    row_number: int
    sku: str | None
    reasons: list[str]


@dataclass(slots=True)
class ImportRunState:
    """Estado en memoria de un run."""

    run_id: str
    type_: str  # 'pim'
    filename: str
    status: str  # 'preview_ready' | 'applying' | 'completed' | 'failed'
    created_at: datetime
    created_by: str | None = None  # email (para audit liviano del run)
    file_bytes: bytes | None = None
    parse_result: ParseResult | None = None
    diffs: list[RowDiff] = field(default_factory=list)
    apply_result: ApplyResult | None = None
    summary: dict[str, Any] = field(default_factory=dict)
    error: str | None = None
    # Additive tracking: filas rechazadas (action=ERROR en el differ).
    # Poblado en preview() — no modifica la lógica de apply.
    rejected_rows: list[RejectedRow] = field(default_factory=list)
    # Reconciliation data from the new pipeline (None if using legacy applier).
    reconciliation: dict[str, Any] | None = None


# Almacenamiento por proceso. En tests se aísla con :func:`reset_run_store`.
# TODO(S3): persistir import_runs en BD (modelo `import_runs` + repository)
#   Hoy el store es in-memory por worker — restart del proceso pierde estado.
#   Aceptable para demo S2 monolítico; no para multi-worker en S3.
_RUN_STORE: dict[str, ImportRunState] = {}
_RUN_LOCKS: dict[str, asyncio.Lock] = {}


def reset_run_store() -> None:  # pragma: no cover — sólo para tests
    """Limpia el store; uso únicamente en setup/teardown de tests."""
    _RUN_STORE.clear()
    _RUN_LOCKS.clear()


_ACTION_TO_SUMMARY_KEY: dict[RowAction, str] = {
    RowAction.CREATE: "creates",
    RowAction.UPDATE: "updates",
    RowAction.NO_CHANGE: "no_change",
    RowAction.SKIP_LOCKED: "skipped_locked",
    RowAction.ERROR: "errors",
}


def _summarize(diffs: Sequence[RowDiff]) -> dict[str, Any]:
    """Resumen del preview por action + counts de errores y locks.

    Keys usan nombres plural para coincidir con el tipo ImportSummary del frontend.
    """
    summary: dict[str, Any] = {
        "total": len(diffs),
        "creates": 0,
        "updates": 0,
        "no_change": 0,
        "skipped_locked": 0,
        "errors": 0,
        "orphans": 0,
        "locked_field_skips_total": 0,
    }
    for d in diffs:
        key = _ACTION_TO_SUMMARY_KEY.get(d.action, d.action.value)
        summary[key] = summary.get(key, 0) + 1
        summary["locked_field_skips_total"] += len(d.locked_fields_skipped)
    return summary


class ImporterService:
    """Wizard PIM: preview → apply → status → report."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    # ----------------------------------------------------------------- preview
    async def preview(
        self,
        *,
        file_bytes: bytes,
        filename: str,
        actor: User,
        type_: str = "pim",
        custom_mapping: list[Any] | None = None,
    ) -> ImportRunState:
        """Sube + parsea + diffea. Devuelve un run en estado ``preview_ready``."""
        if len(file_bytes) > MAX_FILE_SIZE_BYTES:
            raise ImportFileTooLargeError(len(file_bytes), MAX_FILE_SIZE_BYTES)

        # Parse según formato (xlsx o xml de la plantilla).
        from app.services.importer.source_dispatch import is_xml_filename, parse_source

        try:
            if is_xml_filename(filename):
                parse_result = parse_source(file_bytes, filename)
            elif custom_mapping is not None:
                header_idx, _headers, _samples = detect_header_row(file_bytes)
                parse_result = parse_source(
                    file_bytes, filename,
                    custom_mapping=custom_mapping, header_row_index=header_idx,
                )
            else:
                parse_result = parse_source(file_bytes, filename)
        except Exception as exc:
            raise ImporterDomainError(
                code="import_parse_failed",
                message=f"Error parseando archivo: {exc}",
                status_code=422,
            ) from exc

        if not parse_result.header_ok:
            raise ImportHeaderMismatchError(parse_result.header_errors)

        diffs = await compute_diff(self.session, parse_result.rows)
        summary = _summarize(diffs)

        # Tracking additive: recolectar filas con action=ERROR para el
        # endpoint GET /imports/{run_id}/rejected-rows.
        rejected: list[RejectedRow] = [
            RejectedRow(
                row_number=d.row_index,
                sku=d.sku,
                reasons=list(d.errors) if d.errors else ["parse_error"],
            )
            for d in diffs
            if d.action == RowAction.ERROR
        ]

        run_id = uuid.uuid4().hex
        state = ImportRunState(
            run_id=run_id,
            type_=type_,
            filename=filename,
            status="preview_ready",
            created_at=datetime.now(tz=UTC),
            created_by=actor.email,
            file_bytes=file_bytes,
            parse_result=parse_result,
            diffs=diffs,
            summary=summary,
            rejected_rows=rejected,
        )
        _RUN_STORE[run_id] = state
        _RUN_LOCKS[run_id] = asyncio.Lock()

        logger.info(
            "Importer preview ready run_id=%s rows=%d summary=%s",
            run_id,
            summary["total"],
            summary,
        )
        return state

    # ------------------------------------------------------------------ apply
    async def apply(
        self,
        run_id: str,
        actor: User,
        *,
        chunk_size: int = 1000,
        division_codes: list[str] | None = None,
    ) -> ImportRunState:
        state = _RUN_STORE.get(run_id)
        if state is None:
            raise ImportRunNotFoundError(run_id)
        if state.status != "preview_ready":
            raise ImportRunInvalidStateError(run_id, current=state.status, expected="preview_ready")

        lock = _RUN_LOCKS.setdefault(run_id, asyncio.Lock())
        async with lock:
            state.status = "applying"
            try:
                apply_result = await apply_diffs_chunked(
                    self.session,
                    [d for d in state.diffs if d.action in (RowAction.CREATE, RowAction.UPDATE)],
                    actor,
                    run_id=run_id,
                    chunk_size=chunk_size,
                    division_codes=division_codes,
                )
                state.apply_result = apply_result
                state.status = (
                    "completed" if apply_result.failed_chunks == 0 else "completed_with_failures"
                )
                # Refresca summary con resultados reales del apply.
                state.summary["applied_created"] = apply_result.created
                state.summary["applied_updated"] = apply_result.updated
                state.summary["applied_failed_chunks"] = apply_result.failed_chunks
                # Wire reconciliation from ImportOrchestrator result when available.
                # The legacy applier (apply_diffs_chunked) does not produce this yet;
                # state.reconciliation remains None in that path.
                if (
                    hasattr(apply_result, "reconciliation")
                    and apply_result.reconciliation is not None
                ):
                    rec = apply_result.reconciliation
                    state.reconciliation = {
                        "total_excel_rows": rec.total_excel_rows,
                        "inserted": rec.inserted,
                        "updated": rec.updated,
                        "no_change": rec.no_change,
                        "error_rows": rec.error_rows,
                        "locked_rows": rec.locked_rows,
                        "accounted_total": rec.accounted_total,
                        "gap": rec.gap,
                        "is_complete": rec.is_complete,
                        "missing_skus": rec.missing_skus,
                    }
            except Exception as exc:
                logger.exception("Importer apply failed run_id=%s", run_id)
                state.status = "failed"
                state.error = f"{type(exc).__name__}: {exc!s}"
                raise
        return state

    # ----------------------------------------------------------------- status
    @staticmethod
    def get_status(run_id: str) -> ImportRunState:
        state = _RUN_STORE.get(run_id)
        if state is None:
            raise ImportRunNotFoundError(run_id)
        return state

    # ----------------------------------------------------------------- report
    @staticmethod
    def report_csv(run_id: str) -> str:
        state = _RUN_STORE.get(run_id)
        if state is None:
            raise ImportRunNotFoundError(run_id)
        buf = io.StringIO()
        writer = csv.writer(buf)
        writer.writerow(
            [
                "row_index",
                "sku",
                "action",
                "errors",
                "locked_fields_skipped",
                "diff_keys",
            ]
        )
        for d in state.diffs:
            writer.writerow(
                [
                    d.row_index,
                    d.sku or "",
                    d.action.value,
                    "; ".join(d.errors),
                    "; ".join(d.locked_fields_skipped),
                    "; ".join(d.diff.keys()),
                ]
            )
        return buf.getvalue()

    @staticmethod
    def report_json(run_id: str, *, sample_per_bucket: int = 50) -> dict[str, Any]:
        state = _RUN_STORE.get(run_id)
        if state is None:
            raise ImportRunNotFoundError(run_id)

        buckets: dict[str, list[dict[str, Any]]] = {a.value: [] for a in RowAction}

        for d in state.diffs:
            # Transform diff: {field: {from, to}} → [{field, before, after}]
            diff_list: list[dict[str, Any]] | None = None
            if d.diff:
                diff_list = [
                    {"field": k, "before": v.get("from"), "after": v.get("to")}
                    for k, v in d.diff.items()
                ]

            row_data: dict[str, Any] = {
                "row_index": d.row_index,
                "sku": d.sku,
                "action": d.action.value,
                "diff": diff_list,
                "error_code": d.errors[0] if d.errors else None,
                "error_message": "; ".join(d.errors) if d.errors else None,
                "locked_fields_skipped": d.locked_fields_skipped,
            }
            bucket = buckets[d.action.value]
            if len(bucket) < sample_per_bucket:
                bucket.append(row_data)

        # Flatten buckets into a single list (ya capeada por sample_per_bucket).
        rows: list[dict[str, Any]] = [row for bucket in buckets.values() for row in bucket]

        return {
            "run_id": state.run_id,
            "status": state.status,
            "filename": state.filename,
            "created_at": state.created_at.isoformat(),
            "summary": state.summary,
            "samples": buckets,
            "rows": rows,
            "apply": (
                {
                    "created": state.apply_result.created,
                    "updated": state.apply_result.updated,
                    "skipped_locked": state.apply_result.skipped_locked,
                    "no_change": state.apply_result.no_change,
                    "errors": state.apply_result.errors,
                    "failed_chunks": state.apply_result.failed_chunks,
                    "started_at": state.apply_result.started_at.isoformat()
                    if state.apply_result.started_at
                    else None,
                    "finished_at": state.apply_result.finished_at.isoformat()
                    if state.apply_result.finished_at
                    else None,
                }
                if state.apply_result is not None
                else None
            ),
        }
