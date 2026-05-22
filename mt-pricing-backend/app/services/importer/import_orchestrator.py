# app/services/importer/import_orchestrator.py
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession


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
