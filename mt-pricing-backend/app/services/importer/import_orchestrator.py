# app/services/importer/import_orchestrator.py
from __future__ import annotations

import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.product import Product
from app.services.importer.mapping_detector import ColumnMappingItem
from app.services.importer.row_writer import RowWriter
from app.services.importer.xlsx_parser import XlsxParser

logger = logging.getLogger(__name__)

_MAX_ERRORS_LOGGED = 100


@dataclass
class ReconciliationResult:
    total_excel_rows: int
    inserted: int
    updated: int
    no_change: int
    error_rows: int
    locked_rows: int
    missing_skus: list[str] = field(default_factory=list)

    @property
    def accounted_total(self) -> int:
        return self.inserted + self.updated + self.no_change + self.error_rows + self.locked_rows

    @property
    def gap(self) -> int:
        return self.total_excel_rows - self.accounted_total

    @property
    def is_complete(self) -> bool:
        return self.gap == 0


@dataclass
class OrchestratorResult:
    inserted: int = 0
    updated: int = 0
    no_change: int = 0
    error_rows: int = 0
    locked_rows: int = 0
    errors: list[dict[str, Any]] = field(default_factory=list)
    reconciliation: ReconciliationResult | None = None


class ImportOrchestrator:
    """Unified orchestrator for wizard sync + Celery batch imports."""

    def __init__(
        self,
        session: AsyncSession,
        actor_id: UUID,
        run_id: UUID | None = None,
    ) -> None:
        self._session = session
        self._actor_id = actor_id
        self._run_id = run_id

    async def run_sync(
        self,
        xlsx_bytes: bytes,
        mapping: list[ColumnMappingItem],
        header_row_index: int = 0,
        preview_only: bool = False,
    ) -> OrchestratorResult:
        parser = XlsxParser(xlsx_bytes, mapping, header_row_index)
        writer = RowWriter()
        result = OrchestratorResult()

        inserted_skus: set[str] = set()
        updated_skus: set[str] = set()
        no_change_skus: set[str] = set()
        error_skus: set[str] = set()
        locked_skus: set[str] = set()
        all_skus_in_excel: set[str] = set()

        for parsed in parser.parse():
            if parsed.sku:
                all_skus_in_excel.add(parsed.sku)

            if parsed.is_error_row:
                result.error_rows += 1
                if parsed.sku:
                    error_skus.add(parsed.sku)
                if len(result.errors) < _MAX_ERRORS_LOGGED:
                    result.errors.append({"sku": parsed.sku or "", "errors": parsed.errors})
                continue

            try:
                existing_result = await self._session.execute(
                    select(Product).where(Product.sku == parsed.sku)
                )
                existing = existing_result.scalar_one_or_none()
                locked: set[str] = set(getattr(existing, "manual_locked_fields", None) or [])

                was_new = existing is None

                if preview_only:
                    if was_new:
                        result.inserted += 1
                        inserted_skus.add(parsed.sku)
                    else:
                        result.updated += 1
                        updated_skus.add(parsed.sku)
                    continue

                if was_new:
                    existing = Product(
                        sku=parsed.sku,
                        family="unclassified",
                        brand="MT",
                        data_quality="partial",
                        manual_locked_fields=[],
                    )
                    self._session.add(existing)
                    await self._session.flush()

                write_result = await writer.apply(
                    self._session, parsed, existing, locked, self._actor_id
                )

                if was_new:
                    result.inserted += 1
                    inserted_skus.add(parsed.sku)
                elif write_result.bucket == "updated":
                    result.updated += 1
                    updated_skus.add(parsed.sku)
                elif write_result.bucket == "no_change":
                    result.no_change += 1
                    no_change_skus.add(parsed.sku)
                elif write_result.bucket == "locked":
                    result.locked_rows += 1
                    locked_skus.add(parsed.sku)
                elif write_result.bucket == "error":
                    result.error_rows += 1
                    error_skus.add(parsed.sku)

            except Exception as exc:
                logger.warning("Error on row sku=%s: %s", parsed.sku, exc)
                result.error_rows += 1
                error_skus.add(parsed.sku)
                if len(result.errors) < _MAX_ERRORS_LOGGED:
                    result.errors.append({"sku": parsed.sku, "errors": [str(exc)]})

        # Reconciliation pass
        accounted = inserted_skus | updated_skus | no_change_skus | error_skus | locked_skus
        missing = list(all_skus_in_excel - accounted)
        result.reconciliation = ReconciliationResult(
            total_excel_rows=parser.rows_yielded,
            inserted=result.inserted,
            updated=result.updated,
            no_change=result.no_change,
            error_rows=result.error_rows,
            locked_rows=result.locked_rows,
            missing_skus=missing,
        )
        return result

    async def run_batch(
        self,
        source_path: Path,
        mapping: list[ColumnMappingItem] | None = None,
        header_row_index: int = 0,
    ) -> OrchestratorResult:
        from app.services.importer.mapping_detector import detect_header_row, suggest_mapping

        xlsx_bytes = source_path.read_bytes()
        if mapping is None:
            detected_idx, headers, samples = detect_header_row(xlsx_bytes)
            header_row_index = detected_idx
            mapping = suggest_mapping(headers, samples)

        result = await self.run_sync(xlsx_bytes, mapping, header_row_index=header_row_index)
        await self._session.commit()
        return result
