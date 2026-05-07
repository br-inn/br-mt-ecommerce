"""Applier — asocia un :class:`DatasheetDiff` (filename + sku_suffix + specs)
a productos vía un ``ProductService`` mockeable.

El service real (:class:`app.services.products.product_service.ProductService`)
expone ``attach_datasheet(product_sku, kind, storage_path, specs, actor)`` —
si aún no aterrizó, los unit tests inyectan un mock con la misma firma.

NO toca Storage (subida del PDF al bucket Supabase) — eso queda en el
``ImporterDatasheetsService.apply`` que llama a este applier después de
delegar la persistencia del binario al storage layer (ya cubierto por
``app.services.storage`` desde S2).
"""

from __future__ import annotations

import logging
from collections.abc import Sequence
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Protocol

from app.db.models.user import User
from app.services.importer_datasheets.spec_parser import DatasheetSpecs

logger = logging.getLogger(__name__)


class ProductServiceProtocol(Protocol):
    """Contrato mínimo invocado por el applier."""

    async def attach_datasheet(
        self,
        *,
        product_sku: str,
        kind: str,
        storage_path: str,
        original_filename: str,
        specs: dict[str, Any],
        actor: User,
        _import_run_id: str | None = None,
    ) -> Any: ...


@dataclass(slots=True)
class DatasheetDiff:
    """Describe la asociación a aplicar."""

    row_index: int
    filename: str
    kind: str  # 'ficha_tecnica' | 'compliance' | 'manual'
    product_sku: str
    storage_path: str
    specs: DatasheetSpecs = field(default_factory=DatasheetSpecs)
    file_size_bytes: int = 0


@dataclass(slots=True)
class ApplyDatasheetsResult:
    total_rows: int
    attached: int = 0
    skipped: int = 0
    errors: int = 0
    errors_details: list[dict[str, Any]] = field(default_factory=list)
    started_at: datetime | None = None
    finished_at: datetime | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "total_rows": self.total_rows,
            "attached": self.attached,
            "skipped": self.skipped,
            "errors": self.errors,
            "errors_details": self.errors_details[:50],
            "started_at": self.started_at.isoformat() if self.started_at else None,
            "finished_at": self.finished_at.isoformat() if self.finished_at else None,
        }


async def apply_datasheet_diffs(
    diffs: Sequence[DatasheetDiff],
    actor: User,
    *,
    product_service: ProductServiceProtocol,
    run_id: str | None = None,
) -> ApplyDatasheetsResult:
    """Itera diffs y llama a ``product_service.attach_datasheet`` por cada uno.

    No aborta el batch entero por un fallo individual: contabiliza en
    ``errors`` con detalle (`failure_details`) y sigue.
    """
    started = datetime.now(tz=timezone.utc)
    res = ApplyDatasheetsResult(total_rows=len(diffs), started_at=started)
    for d in diffs:
        try:
            await product_service.attach_datasheet(
                product_sku=d.product_sku,
                kind=d.kind,
                storage_path=d.storage_path,
                original_filename=d.filename,
                specs=d.specs.to_dict(),
                actor=actor,
                _import_run_id=run_id,
            )
            res.attached += 1
        except Exception as exc:  # noqa: BLE001
            logger.exception(
                "datasheets applier failed row=%s sku=%s",
                d.row_index,
                d.product_sku,
            )
            res.errors += 1
            res.errors_details.append(
                {
                    "row_index": d.row_index,
                    "filename": d.filename,
                    "sku": d.product_sku,
                    "code": "internal_error",
                    "message": f"{type(exc).__name__}: {exc!s}",
                }
            )
    res.finished_at = datetime.now(tz=timezone.utc)
    return res


class DatasheetApplier:
    """Wrapper instanciable (paralelo a ``CostsApplier``)."""

    def __init__(self, product_service: ProductServiceProtocol) -> None:
        self.product_service = product_service

    async def apply(
        self,
        diffs: Sequence[DatasheetDiff],
        actor: User,
        *,
        run_id: str | None = None,
    ) -> ApplyDatasheetsResult:
        return await apply_datasheet_diffs(
            diffs, actor, product_service=self.product_service, run_id=run_id
        )


__all__ = [
    "ApplyDatasheetsResult",
    "DatasheetApplier",
    "DatasheetDiff",
    "ProductServiceProtocol",
    "apply_datasheet_diffs",
]
