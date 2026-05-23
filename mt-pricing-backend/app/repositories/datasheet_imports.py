"""DatasheetImportRepository — CRUD sobre ``import_runs`` (kind='datasheets')
+ ``product_datasheets``.

Patrón paralelo a :class:`MatchCandidateRepository` y
:class:`PriceRepository` (estilo S3). NO commit-ea — la session pertenece al
caller.

Métodos principales:
- ``create_run`` — inserta ``import_runs`` con ``import_type='datasheets'``.
- ``mark_status`` — actualiza estado / contadores.
- ``upsert_datasheet`` — inserta o actualiza fila ``product_datasheets``
  (idempotencia por ``storage_path``).
- ``list_for_sku`` — devuelve datasheets activos de un SKU (consultando
  ``sku_list`` JSONB con operador ``?``).
"""

from __future__ import annotations

from collections.abc import Sequence
from datetime import datetime, timezone
from typing import Any
from uuid import UUID

from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.datasheet_import_run import ProductDatasheet
from app.db.models.import_run import ImportRun
from app.repositories.base import BaseRepository


class ProductDatasheetRepository(BaseRepository[ProductDatasheet]):
    model = ProductDatasheet
    pk_field = "id"
    soft_delete_field = None

    async def find_by_storage_path(self, storage_path: str) -> ProductDatasheet | None:
        stmt = select(ProductDatasheet).where(ProductDatasheet.storage_path == storage_path)
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def upsert_datasheet(
        self,
        *,
        kind: str,
        storage_path: str,
        original_filename: str,
        sku_list: Sequence[str],
        specs_extracted: dict[str, Any],
        file_size_bytes: int = 0,
        import_run_id: UUID | None = None,
        uploaded_by: UUID | None = None,
    ) -> ProductDatasheet:
        existing = await self.find_by_storage_path(storage_path)
        if existing is not None:
            existing.kind = kind
            existing.original_filename = original_filename
            existing.sku_list = list(sku_list)
            existing.specs_extracted = dict(specs_extracted)
            existing.file_size_bytes = file_size_bytes
            existing.import_run_id = import_run_id
            existing.uploaded_by = uploaded_by
            existing.uploaded_at = datetime.now(tz=timezone.utc)
            await self.session.flush()
            return existing

        row = ProductDatasheet(
            kind=kind,
            storage_path=storage_path,
            original_filename=original_filename,
            sku_list=list(sku_list),
            specs_extracted=dict(specs_extracted),
            file_size_bytes=file_size_bytes,
            import_run_id=import_run_id,
            uploaded_by=uploaded_by,
            uploaded_at=datetime.now(tz=timezone.utc),
        )
        self.session.add(row)
        await self.session.flush()
        return row

    async def list_for_sku(self, sku: str) -> Sequence[ProductDatasheet]:
        # JSONB containment: sku_list @> '["MT-V-..."]'::jsonb
        stmt = select(ProductDatasheet).where(
            text("product_datasheets.sku_list @> CAST(:sku_array AS jsonb)")
        )
        result = await self.session.execute(stmt, {"sku_array": f'["{sku}"]'})
        return result.scalars().all()


class DatasheetImportRunRepository(BaseRepository[ImportRun]):
    """Wrapper sobre ``import_runs`` filtrando por ``import_type='datasheets'``."""

    model = ImportRun
    pk_field = "id"
    soft_delete_field = None

    async def create_run(
        self,
        *,
        source_filename: str,
        source_storage_path: str | None = None,
        triggered_by: UUID | None = None,
        celery_task_id: str | None = None,
    ) -> ImportRun:
        row = ImportRun(
            import_type="datasheets",
            source_filename=source_filename,
            source_storage_path=source_storage_path,
            status="queued",
            triggered_by=triggered_by,
            celery_task_id=celery_task_id,
        )
        self.session.add(row)
        await self.session.flush()
        return row

    async def mark_status(
        self,
        run_id: UUID,
        *,
        status: str,
        summary: dict[str, Any] | None = None,
        errors: list[dict[str, Any]] | None = None,
        finished: bool = False,
    ) -> ImportRun | None:
        run = await self.get(run_id)
        if run is None:
            return None
        run.status = status
        if summary is not None:
            run.summary = summary
        if errors is not None:
            run.errors = errors
        if finished:
            run.finished_at = datetime.now(tz=timezone.utc)
        await self.session.flush()
        return run

    async def list_recent(self, *, limit: int = 50) -> Sequence[ImportRun]:
        stmt = (
            select(ImportRun)
            .where(ImportRun.import_type == "datasheets")
            .order_by(ImportRun.created_at.desc())
            .limit(limit)
        )
        result = await self.session.execute(stmt)
        return result.scalars().all()


__all__ = [
    "DatasheetImportRunRepository",
    "ProductDatasheetRepository",
]
