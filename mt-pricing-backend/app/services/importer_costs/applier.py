"""Applier — aplica :class:`CostDiff` invocando ``CostService.create_cost``.

Diseño:
- Acepta un ``cost_service`` inyectado (Protocol) — facilita mocking en unit
  tests sin necesidad de DB ni de la API real ``POST /costs`` que la entrega
  Agent F (US-1A-04-03).
- Sólo aplica acciones ``CREATE`` y ``UPDATE``. Las ``ORPHAN`` se cuentan pero
  NO se aplican (Champion las resuelve manualmente).
- Estampe FX as-of: si la fila trae ``effective_at`` lo respeta; si no, default
  ``now()``. Si el FX no resuelve para la divisa origen → row contabilizada en
  ``errors_fx_missing`` y sigue.
- Audit por fila + summary por chunk (consistente con :mod:`importer.applier`).

Mocks en tests: pasar un dummy con el método ``create_cost(**kwargs) -> Any``;
el applier sólo llama ese método (no más).
"""

from __future__ import annotations

import logging
from collections.abc import Sequence
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any, Protocol

from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.user import User
from app.services.importer_costs.differ import CostDiff, CostRowAction

logger = logging.getLogger(__name__)


class FxMissingError(Exception):
    """Levantado por la cost service real cuando no hay FX para la divisa."""


class CostServiceProtocol(Protocol):
    """Contrato mínimo del CostService que necesitamos al aplicar."""

    async def create_cost(self, **kwargs: Any) -> Any: ...


@dataclass(slots=True)
class ApplyCostsResult:
    total_rows: int
    created: int = 0
    updated: int = 0
    no_change: int = 0
    orphans: int = 0
    errors: int = 0
    errors_fx_missing: int = 0
    started_at: datetime | None = None
    finished_at: datetime | None = None
    failure_details: list[dict[str, Any]] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "total_rows": self.total_rows,
            "created": self.created,
            "updated": self.updated,
            "no_change": self.no_change,
            "orphans": self.orphans,
            "errors": self.errors,
            "errors_fx_missing": self.errors_fx_missing,
            "started_at": self.started_at.isoformat() if self.started_at else None,
            "finished_at": self.finished_at.isoformat() if self.finished_at else None,
            "failure_details": self.failure_details[:50],
        }


class CostsApplier:
    """Wrapper instanciable; útil cuando la session/auditoría son inyectadas."""

    def __init__(
        self,
        session: AsyncSession,
        cost_service: CostServiceProtocol,
    ) -> None:
        self.session = session
        self.cost_service = cost_service

    async def apply(
        self,
        diffs: Sequence[CostDiff],
        actor: User,
        *,
        run_id: str,
    ) -> ApplyCostsResult:
        return await apply_cost_diffs(diffs, actor, cost_service=self.cost_service, run_id=run_id)


async def apply_cost_diffs(
    diffs: Sequence[CostDiff],
    actor: User,
    *,
    cost_service: CostServiceProtocol,
    run_id: str,
) -> ApplyCostsResult:
    """Aplica los diffs invocando ``cost_service.create_cost`` por fila.

    NO maneja chunks/savepoints como :mod:`importer.applier` porque cada
    ``create_cost`` ya es una transacción autoseleccionada (ADR-045 — costs
    persistencia híbrida con audit emit). Si una fila falla, la siguiente
    continúa y el caller registra summary.
    """
    result = ApplyCostsResult(
        total_rows=len(diffs),
        started_at=datetime.now(tz=UTC),
    )

    for d in diffs:
        if d.action == CostRowAction.NO_CHANGE:
            result.no_change += 1
            continue
        if d.action == CostRowAction.ORPHAN:
            result.orphans += 1
            continue
        if d.action == CostRowAction.ERROR:
            result.errors += 1
            continue
        if d.action not in (CostRowAction.CREATE, CostRowAction.UPDATE):
            continue

        kwargs = dict(d.payload)
        kwargs["_import_run_id"] = run_id
        kwargs["_actor_id"] = getattr(actor, "id", None)

        try:
            await cost_service.create_cost(**kwargs)
        except FxMissingError as exc:
            result.errors_fx_missing += 1
            result.failure_details.append(
                {
                    "row_index": d.row_index,
                    "sku": d.sku,
                    "code": "fx_missing",
                    "message": str(exc),
                }
            )
            logger.warning(
                "Costs apply: fx_missing row=%s sku=%s scheme=%s",
                d.row_index,
                d.sku,
                d.scheme_code,
            )
            continue
        except Exception as exc:
            result.errors += 1
            result.failure_details.append(
                {
                    "row_index": d.row_index,
                    "sku": d.sku,
                    "code": type(exc).__name__,
                    "message": str(exc),
                }
            )
            logger.exception("Costs apply: row %s sku=%s failed", d.row_index, d.sku)
            continue

        if d.action == CostRowAction.CREATE:
            result.created += 1
        elif d.action == CostRowAction.UPDATE:
            result.updated += 1

    result.finished_at = datetime.now(tz=UTC)
    return result
