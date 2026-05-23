"""ImporterCostsService — orquesta preview/apply/status/report (US-1A-06-02).

Patrón paralelo a :class:`app.services.importer.importer_service.ImporterService`,
pero específico para Excel de costos (kind='costs'):

- ``preview(file_bytes, filename, actor)`` → parsea, diffea, retorna
  :class:`ImporterCostsRunState` con summary + orphan_report.
- ``apply(run_id, actor, cost_service)`` → invoca CostService.create_cost por
  fila vía :func:`apply_cost_diffs`.
- ``get_status(run_id)`` → estado actual.
- ``report_csv(run_id)`` / ``report_json(run_id)`` → detalle por fila.

Persistencia in-memory (igual que el wizard PIM S2) — el caller del router
puede sustituirlo por un repository sobre ``import_runs`` (kind='costs') si
se desea persistir entre restarts.
"""

from __future__ import annotations

import asyncio
import csv
import io
import logging
import uuid
from collections.abc import Sequence
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, BinaryIO

from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.user import User
from app.services.importer.importer_service import (
    ImportFileTooLargeError,
    ImporterDomainError,
    ImportHeaderMismatchError,
    ImportRunInvalidStateError,
    ImportRunNotFoundError,
    MAX_FILE_SIZE_BYTES,
)
from app.services.importer_costs.applier import (
    ApplyCostsResult,
    CostServiceProtocol,
    apply_cost_diffs,
)
from app.services.importer_costs.differ import (
    CostDiff,
    CostRowAction,
    OrphanReport,
    compute_cost_diff,
)
from app.services.importer_costs.parser import (
    CostsParseResult,
    parse_costs_xlsx_stream,
)

logger = logging.getLogger(__name__)


@dataclass(slots=True)
class ImporterCostsRunState:
    run_id: str
    kind: str  # 'costs'
    filename: str
    status: str  # 'preview_ready' | 'applying' | 'completed' | 'failed'
    created_at: datetime
    created_by: str | None = None
    file_bytes: bytes | None = None
    parse_result: CostsParseResult | None = None
    diffs: list[CostDiff] = field(default_factory=list)
    orphans: OrphanReport = field(default_factory=OrphanReport)
    apply_result: ApplyCostsResult | None = None
    summary: dict[str, Any] = field(default_factory=dict)
    error: str | None = None


_RUN_STORE: dict[str, ImporterCostsRunState] = {}
_RUN_LOCKS: dict[str, asyncio.Lock] = {}


def reset_run_store() -> None:  # pragma: no cover — only used in tests
    _RUN_STORE.clear()
    _RUN_LOCKS.clear()


def _summarize(diffs: Sequence[CostDiff], orphans: OrphanReport) -> dict[str, Any]:
    summary = {
        "total": len(diffs),
        "create": 0,
        "update": 0,
        "no_change": 0,
        "orphan": 0,
        "error": 0,
        "orphans": {
            "sku_not_in_pim": len(orphans.sku_not_in_pim),
            "scheme_unknown": len(orphans.scheme_unknown),
            "supplier_unknown": len(orphans.supplier_unknown),
        },
    }
    for d in diffs:
        summary[d.action.value] = summary.get(d.action.value, 0) + 1
    return summary


class ImporterCostsService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    # ----------------------------------------------------------------- preview
    async def preview(
        self,
        *,
        file_bytes: bytes,
        filename: str,
        actor: User,
    ) -> ImporterCostsRunState:
        if len(file_bytes) > MAX_FILE_SIZE_BYTES:
            raise ImportFileTooLargeError(len(file_bytes), MAX_FILE_SIZE_BYTES)

        bio: BinaryIO = io.BytesIO(file_bytes)
        try:
            parse_result = parse_costs_xlsx_stream(bio)
        except Exception as exc:  # noqa: BLE001
            raise ImporterDomainError(
                code="import_costs_parse_failed",
                message=f"Error parseando archivo: {exc}",
                status_code=422,
            ) from exc

        if not parse_result.header_ok:
            raise ImportHeaderMismatchError(parse_result.header_errors)

        diffs, orphan_report = await compute_cost_diff(self.session, parse_result.rows)
        summary = _summarize(diffs, orphan_report)

        run_id = uuid.uuid4().hex
        state = ImporterCostsRunState(
            run_id=run_id,
            kind="costs",
            filename=filename,
            status="preview_ready",
            created_at=datetime.now(tz=timezone.utc),
            created_by=actor.email if actor is not None else None,
            file_bytes=file_bytes,
            parse_result=parse_result,
            diffs=diffs,
            orphans=orphan_report,
            summary=summary,
        )
        _RUN_STORE[run_id] = state
        _RUN_LOCKS[run_id] = asyncio.Lock()
        logger.info(
            "Costs importer preview ready run_id=%s rows=%d summary=%s",
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
        cost_service: CostServiceProtocol,
    ) -> ImporterCostsRunState:
        state = _RUN_STORE.get(run_id)
        if state is None:
            raise ImportRunNotFoundError(run_id)
        if state.status != "preview_ready":
            raise ImportRunInvalidStateError(run_id, current=state.status, expected="preview_ready")
        lock = _RUN_LOCKS.setdefault(run_id, asyncio.Lock())
        async with lock:
            state.status = "applying"
            try:
                result = await apply_cost_diffs(
                    state.diffs, actor, cost_service=cost_service, run_id=run_id
                )
                state.apply_result = result
                if result.errors > 0 or result.errors_fx_missing > 0:
                    state.status = "completed_with_errors"
                else:
                    state.status = "completed"
                state.summary["applied_created"] = result.created
                state.summary["applied_updated"] = result.updated
                state.summary["applied_errors"] = result.errors
                state.summary["applied_errors_fx_missing"] = result.errors_fx_missing
            except Exception as exc:  # noqa: BLE001
                logger.exception("Costs importer apply failed run_id=%s", run_id)
                state.status = "failed"
                state.error = f"{type(exc).__name__}: {exc!s}"
                raise
        return state

    # ----------------------------------------------------------------- status
    @staticmethod
    def get_status(run_id: str) -> ImporterCostsRunState:
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
                "scheme_code",
                "supplier_code",
                "action",
                "errors",
                "orphan_reasons",
                "diff_keys",
            ]
        )
        for d in state.diffs:
            writer.writerow(
                [
                    d.row_index,
                    d.sku or "",
                    d.scheme_code or "",
                    d.supplier_code or "",
                    d.action.value,
                    "; ".join(d.errors),
                    "; ".join(d.orphan_reasons),
                    "; ".join(d.diff.keys()),
                ]
            )
        return buf.getvalue()

    @staticmethod
    def report_json(run_id: str, *, sample_per_bucket: int = 50) -> dict[str, Any]:
        state = _RUN_STORE.get(run_id)
        if state is None:
            raise ImportRunNotFoundError(run_id)
        buckets: dict[str, list[dict[str, Any]]] = {a.value: [] for a in CostRowAction}
        for d in state.diffs:
            bucket = buckets[d.action.value]
            if len(bucket) < sample_per_bucket:
                bucket.append(
                    {
                        "row_index": d.row_index,
                        "sku": d.sku,
                        "scheme_code": d.scheme_code,
                        "supplier_code": d.supplier_code,
                        "diff": d.diff,
                        "errors": d.errors,
                        "orphan_reasons": d.orphan_reasons,
                    }
                )
        return {
            "run_id": state.run_id,
            "kind": state.kind,
            "status": state.status,
            "filename": state.filename,
            "created_at": state.created_at.isoformat(),
            "summary": state.summary,
            "orphans": state.orphans.to_dict(),
            "samples": buckets,
            "apply": (state.apply_result.to_dict() if state.apply_result is not None else None),
        }
