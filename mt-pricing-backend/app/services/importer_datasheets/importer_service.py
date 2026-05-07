"""ImporterDatasheetsService — preview/apply/status para el importer de
datasheets PDF (US-1A-06-04).

Contrato análogo a ``ImporterCostsService``:

- ``preview(files, actor)`` recibe una lista de ``(filename, payload)``,
  parsea cada filename → kind + sku_suffixes, extrae texto + specs, resuelve
  cada SKU contra el repo de productos (``ProductRepository`` o un Protocol
  más estrecho — para tests) y construye una lista de
  :class:`DatasheetDiff` por SKU resuelto. Reporta ``orphan_files`` los
  filenames que no resuelven y ``orphan_skus`` los suffixes que no encuentran
  producto.

- ``apply(run_id, actor, product_service)`` llama al applier.

Persistencia in-memory por proceso. Para multi-worker, swap por una capa
sobre ``import_runs`` con ``import_type='datasheets'`` (el modelo ya soporta
ese kind via CHECK constraint reusada — ver migración 023).
"""

from __future__ import annotations

import asyncio
import logging
import uuid
from collections.abc import Iterable, Sequence
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Protocol

from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.user import User
from app.services.importer.importer_service import (
    ImportFileTooLargeError,
    ImporterDomainError,
    ImportRunInvalidStateError,
    ImportRunNotFoundError,
)
from app.services.importer_datasheets.applier import (
    ApplyDatasheetsResult,
    DatasheetDiff,
    ProductServiceProtocol,
    apply_datasheet_diffs,
)
from app.services.importer_datasheets.pdf_extractor import (
    PDFExtractionError,
    extract_text_from_pdf,
)
from app.services.importer_datasheets.spec_parser import (
    DatasheetSpecs,
    parse_datasheet_filename,
    parse_specs_from_text,
)

logger = logging.getLogger(__name__)


# Tope de tamaño por archivo según AC #5 de US-1A-06-04 (10 MB).
MAX_DATASHEET_BYTES = 10 * 1024 * 1024
DATASHEET_KIND_PREFIXES = ("MTFT", "MTCE", "MTMAN")


class ProductLookupProtocol(Protocol):
    async def resolve_skus(self, suffixes: Iterable[str]) -> dict[str, str]:
        """Mapa ``suffix -> product.sku`` (sólo entradas resueltas)."""
        ...


@dataclass(slots=True)
class DatasheetsRunState:
    run_id: str
    kind: str  # 'datasheets'
    status: str
    created_at: datetime
    created_by: str | None = None
    diffs: list[DatasheetDiff] = field(default_factory=list)
    orphan_files: list[dict[str, Any]] = field(default_factory=list)
    orphan_skus: list[str] = field(default_factory=list)
    summary: dict[str, Any] = field(default_factory=dict)
    apply_result: ApplyDatasheetsResult | None = None
    error: str | None = None


_RUN_STORE: dict[str, DatasheetsRunState] = {}
_RUN_LOCKS: dict[str, asyncio.Lock] = {}


def reset_datasheets_run_store() -> None:
    """Helper exclusivo de tests — limpia el almacén in-memory."""
    _RUN_STORE.clear()
    _RUN_LOCKS.clear()


class ImporterDatasheetsService:
    """Servicio orquestador (Sprint 4 / US-1A-06-04)."""

    def __init__(
        self,
        session: AsyncSession,
        *,
        sku_resolver: ProductLookupProtocol | None = None,
        storage_path_factory: Any | None = None,
    ) -> None:
        self.session = session
        self._sku_resolver = sku_resolver
        # ``storage_path_factory(filename) -> str`` permite a los tests
        # construir paths sin tocar Supabase.
        self._storage_factory = storage_path_factory or (
            lambda filename: f"product-datasheets/{filename}"
        )

    # ----------------------------------------------------------------- preview
    async def preview(
        self,
        *,
        files: Sequence[tuple[str, bytes]],
        actor: User,
    ) -> DatasheetsRunState:
        diffs: list[DatasheetDiff] = []
        orphan_files: list[dict[str, Any]] = []
        all_suffixes: set[str] = set()
        per_file_meta: list[
            tuple[str, bytes, str, list[str], DatasheetSpecs]
        ] = []  # filename, payload, kind, suffixes, specs

        for idx, (filename, payload) in enumerate(files):
            if len(payload) > MAX_DATASHEET_BYTES:
                raise ImportFileTooLargeError(len(payload), MAX_DATASHEET_BYTES)
            parsed = parse_datasheet_filename(filename)
            if not parsed.ok:
                orphan_files.append(
                    {
                        "filename": filename,
                        "reason": parsed.error or "filename_invalid",
                        "row_index": idx,
                    }
                )
                continue

            try:
                text = extract_text_from_pdf(payload)
            except PDFExtractionError as exc:
                orphan_files.append(
                    {
                        "filename": filename,
                        "reason": exc.code,
                        "row_index": idx,
                        "detail": exc.message,
                    }
                )
                continue

            specs = parse_specs_from_text(text)
            assert parsed.kind is not None  # noqa: S101  for mypy
            per_file_meta.append((filename, payload, parsed.kind, parsed.sku_suffixes, specs))
            all_suffixes.update(parsed.sku_suffixes)

        sku_map = await self._resolve_skus(all_suffixes)
        orphan_suffixes = sorted(s for s in all_suffixes if s not in sku_map)

        for idx, (filename, payload, kind, suffixes, specs) in enumerate(per_file_meta):
            resolved = [(s, sku_map[s]) for s in suffixes if s in sku_map]
            if not resolved:
                orphan_files.append(
                    {
                        "filename": filename,
                        "reason": "no_sku_resolved",
                        "row_index": idx,
                    }
                )
                continue
            for suffix, sku in resolved:
                diffs.append(
                    DatasheetDiff(
                        row_index=idx,
                        filename=filename,
                        kind=kind,
                        product_sku=sku,
                        storage_path=self._storage_factory(filename),
                        specs=specs,
                        file_size_bytes=len(payload),
                    )
                )

        run_id = uuid.uuid4().hex
        summary = {
            "total_files": len(files),
            "matched_files": len({d.filename for d in diffs}),
            "matched_diffs": len(diffs),
            "orphan_files": len(orphan_files),
            "orphan_skus": len(orphan_suffixes),
        }
        state = DatasheetsRunState(
            run_id=run_id,
            kind="datasheets",
            status="preview_ready",
            created_at=datetime.now(tz=timezone.utc),
            created_by=getattr(actor, "email", None),
            diffs=diffs,
            orphan_files=orphan_files,
            orphan_skus=orphan_suffixes,
            summary=summary,
        )
        _RUN_STORE[run_id] = state
        _RUN_LOCKS[run_id] = asyncio.Lock()
        logger.info(
            "Datasheets preview ready run_id=%s summary=%s",
            run_id,
            summary,
        )
        return state

    # ------------------------------------------------------------------ apply
    async def apply(
        self,
        run_id: str,
        actor: User,
        *,
        product_service: ProductServiceProtocol,
    ) -> DatasheetsRunState:
        state = _RUN_STORE.get(run_id)
        if state is None:
            raise ImportRunNotFoundError(run_id)
        if state.status != "preview_ready":
            raise ImportRunInvalidStateError(
                run_id, current=state.status, expected="preview_ready"
            )
        lock = _RUN_LOCKS.setdefault(run_id, asyncio.Lock())
        async with lock:
            state.status = "applying"
            try:
                result = await apply_datasheet_diffs(
                    state.diffs,
                    actor,
                    product_service=product_service,
                    run_id=run_id,
                )
                state.apply_result = result
                state.status = "completed_with_errors" if result.errors > 0 else "completed"
                state.summary["applied_attached"] = result.attached
                state.summary["applied_errors"] = result.errors
            except Exception as exc:  # noqa: BLE001
                logger.exception("datasheets apply failed run_id=%s", run_id)
                state.status = "failed"
                state.error = f"{type(exc).__name__}: {exc!s}"
                raise
        return state

    # ----------------------------------------------------------------- status
    @staticmethod
    def get_status(run_id: str) -> DatasheetsRunState:
        state = _RUN_STORE.get(run_id)
        if state is None:
            raise ImportRunNotFoundError(run_id)
        return state

    # ----------------------------------------------------------------- helpers
    async def _resolve_skus(self, suffixes: set[str]) -> dict[str, str]:
        if not suffixes:
            return {}
        if self._sku_resolver is not None:
            try:
                return await self._sku_resolver.resolve_skus(suffixes)
            except Exception:  # noqa: BLE001
                logger.exception("sku_resolver failed; fallback to repo")
        # Fallback: usa repository de productos
        try:
            from app.repositories.product import ProductRepository
        except Exception:  # pragma: no cover  # noqa: BLE001
            return {}
        repo = ProductRepository(self.session)
        result: dict[str, str] = {}
        for suffix in suffixes:
            sku_candidate = f"MT-V-{suffix}"
            try:
                product = await repo.get_by_sku(sku_candidate)
            except Exception:  # noqa: BLE001
                product = None
            if product is not None:
                result[suffix] = sku_candidate
        return result


__all__ = [
    "DATASHEET_KIND_PREFIXES",
    "DatasheetsRunState",
    "ImporterDatasheetsService",
    "MAX_DATASHEET_BYTES",
    "ProductLookupProtocol",
    "reset_datasheets_run_store",
]
