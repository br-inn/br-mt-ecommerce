# tests/unit/importer/test_import_orchestrator.py
"""Tests para ReconciliationResult + OrchestratorResult."""
from __future__ import annotations
from app.services.importer.import_orchestrator import ReconciliationResult, OrchestratorResult


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
