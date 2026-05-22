# tests/unit/importer/test_import_orchestrator.py
"""Tests para ReconciliationResult + OrchestratorResult."""
from __future__ import annotations

import io
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import openpyxl
import pytest

from app.services.importer.import_orchestrator import (
    ImportOrchestrator,
    OrchestratorResult,
    ReconciliationResult,
)
from app.services.importer.mapping_detector import ColumnMappingItem


def test_reconciliation_complete():
    r = ReconciliationResult(
        total_excel_rows=100,
        inserted=10,
        updated=80,
        no_change=10,
        error_rows=0,
        locked_rows=0,
        missing_skus=[],
    )
    assert r.accounted_total == 100
    assert r.gap == 0
    assert r.is_complete is True


def test_reconciliation_incomplete():
    r = ReconciliationResult(
        total_excel_rows=100,
        inserted=10,
        updated=80,
        no_change=7,
        error_rows=0,
        locked_rows=0,
        missing_skus=["MT-X1", "MT-X2", "MT-X3"],
    )
    assert r.gap == 3
    assert r.is_complete is False
    assert len(r.missing_skus) == 3


def test_reconciliation_with_errors():
    r = ReconciliationResult(
        total_excel_rows=50,
        inserted=20,
        updated=25,
        no_change=3,
        error_rows=2,
        locked_rows=0,
        missing_skus=[],
    )
    assert r.accounted_total == 50
    assert r.gap == 0
    assert r.is_complete is True


def test_orchestrator_result_defaults():
    r = OrchestratorResult()
    assert r.inserted == 0
    assert r.updated == 0
    assert r.errors == []
    assert r.reconciliation is None


def _make_xlsx_bytes(rows: list[list]) -> bytes:
    wb = openpyxl.Workbook()
    ws = wb.active
    for row in rows:
        ws.append(row)
    buf = io.BytesIO()
    wb.save(buf)
    return buf.getvalue()


def _mapping(*items):
    return [ColumnMappingItem(excel_col=e, target_field=t, transform=tr) for e, t, tr in items]


@pytest.mark.asyncio
async def test_run_sync_counts_inserted():
    """Products that don't exist yet should be counted as inserted."""
    session = AsyncMock()

    with patch("app.services.importer.import_orchestrator.select") as mock_select, \
         patch("app.services.importer.import_orchestrator.Product") as MockProduct, \
         patch("app.services.importer.import_orchestrator.RowWriter") as MockRW:

        # Simulate: no existing product found (scalar returns None)
        mock_exec_result = MagicMock()
        mock_exec_result.scalar_one_or_none.return_value = None
        session.execute = AsyncMock(return_value=mock_exec_result)
        session.flush = AsyncMock()

        # Mock RowWriter to return "updated" (new product set to inserted by orchestrator)
        mock_rw = MagicMock()
        mock_rw.apply = AsyncMock(return_value=MagicMock(bucket="updated", errors=[]))
        MockRW.return_value = mock_rw

        xlsx = _make_xlsx_bytes([["sku", "Peso"], ["MT-001", 1.5]])
        mapping = _mapping(("sku", "sku", "text"), ("Peso", "weight", "decimal"))

        orch = ImportOrchestrator(session=session, actor_id=uuid4())
        result = await orch.run_sync(xlsx, mapping)

    assert result.reconciliation.total_excel_rows == 1
    assert result.reconciliation.is_complete is True


@pytest.mark.asyncio
async def test_run_sync_error_row_counted_in_reconciliation():
    """Rows with empty SKU should be counted as error_rows in reconciliation."""
    session = AsyncMock()

    xlsx = _make_xlsx_bytes([["sku", "Peso"], [None, 1.5]])
    mapping = _mapping(("sku", "sku", "text"), ("Peso", "weight", "decimal"))

    orch = ImportOrchestrator(session=session, actor_id=uuid4())
    result = await orch.run_sync(xlsx, mapping)

    assert result.error_rows == 1
    assert result.reconciliation.total_excel_rows == 1
    assert result.reconciliation.error_rows == 1
    assert result.reconciliation.is_complete is True


@pytest.mark.asyncio
async def test_run_sync_no_rows_gives_complete_reconciliation():
    """Empty xlsx should give complete reconciliation with all zeroes."""
    session = AsyncMock()

    xlsx = _make_xlsx_bytes([["sku"]])  # header only, no data rows
    mapping = _mapping(("sku", "sku", "text"))

    orch = ImportOrchestrator(session=session, actor_id=uuid4())
    result = await orch.run_sync(xlsx, mapping)

    assert result.reconciliation.total_excel_rows == 0
    assert result.reconciliation.is_complete is True
