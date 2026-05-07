"""Unit tests para `app.services.importer.differ` (sin DB real).

Usa un session mock (compatible con el query stub que necesitamos).
"""

from __future__ import annotations

from typing import Any
from unittest.mock import AsyncMock, MagicMock

import pytest

from app.db.models.product import Product
from app.services.importer.differ import RowAction, _compute_field_diff, compute_diff
from app.services.importer.parser import ParsedRow


def _mk_product(sku: str, **fields: Any) -> Product:
    """Construye un Product en memoria, sin pasar por DB."""
    p = Product(sku=sku, name_en=fields.get("name_en", "n"), family=fields.get("family", "f"))
    for k, v in fields.items():
        setattr(p, k, v)
    return p


def test_compute_field_diff_detects_changes() -> None:
    p = _mk_product("X1", dn="DN15", material="brass")
    diff = _compute_field_diff(
        {"dn": "DN50", "material": "brass", "name_en": "n"}, p
    )
    assert "dn" in diff
    assert diff["dn"] == {"from": "DN15", "to": "DN50"}
    # material no cambió.
    assert "material" not in diff


def test_compute_field_diff_normalizes_decimals() -> None:
    from decimal import Decimal

    p = _mk_product("X2", weight=Decimal("1.5"))
    diff = _compute_field_diff({"weight": Decimal("1.5"), "name_en": "n"}, p)
    assert "weight" not in diff


@pytest.mark.asyncio
async def test_compute_diff_marks_create_when_sku_unknown() -> None:
    session = MagicMock()
    # Simula execute().scalars().all() vacío.
    result = MagicMock()
    result.scalars.return_value.all.return_value = []
    session.execute = AsyncMock(return_value=result)

    rows = [
        ParsedRow(row_index=1, sku="NEW-001", payload={"name_en": "n", "family": "f"}),
        ParsedRow(row_index=2, sku="NEW-002", payload={"name_en": "n", "family": "f"}),
    ]
    diffs = await compute_diff(session, rows)
    assert len(diffs) == 2
    assert all(d.action == RowAction.CREATE for d in diffs)


@pytest.mark.asyncio
async def test_compute_diff_marks_update_when_field_changed() -> None:
    existing = _mk_product("EXIST-001", dn="DN15", material="brass", manual_locked_fields=[])
    session = MagicMock()
    result = MagicMock()
    result.scalars.return_value.all.return_value = [existing]
    session.execute = AsyncMock(return_value=result)

    rows = [
        ParsedRow(
            row_index=1,
            sku="EXIST-001",
            payload={"dn": "DN50", "material": "brass", "name_en": "n", "family": "f"},
        )
    ]
    diffs = await compute_diff(session, rows)
    assert len(diffs) == 1
    assert diffs[0].action == RowAction.UPDATE
    assert "dn" in diffs[0].diff


@pytest.mark.asyncio
async def test_compute_diff_skip_locked_when_only_locked_field_changed() -> None:
    existing = _mk_product(
        "LOCK-001", dn="DN15", material="brass", manual_locked_fields=["dn"]
    )
    session = MagicMock()
    result = MagicMock()
    result.scalars.return_value.all.return_value = [existing]
    session.execute = AsyncMock(return_value=result)

    rows = [
        ParsedRow(
            row_index=1,
            sku="LOCK-001",
            payload={"dn": "DN50", "material": "brass", "name_en": "n", "family": "f"},
        )
    ]
    diffs = await compute_diff(session, rows)
    assert diffs[0].action == RowAction.SKIP_LOCKED
    assert "dn" in diffs[0].locked_fields_skipped


@pytest.mark.asyncio
async def test_compute_diff_update_when_some_locked_others_not() -> None:
    existing = _mk_product(
        "MIX-001",
        dn="DN15",
        material="brass",
        manual_locked_fields=["dn"],
    )
    session = MagicMock()
    result = MagicMock()
    result.scalars.return_value.all.return_value = [existing]
    session.execute = AsyncMock(return_value=result)

    rows = [
        ParsedRow(
            row_index=1,
            sku="MIX-001",
            payload={
                "dn": "DN50",          # locked → skip
                "material": "ss316",   # unlocked → update
                "name_en": "n",
                "family": "f",
            },
        )
    ]
    diffs = await compute_diff(session, rows)
    assert diffs[0].action == RowAction.UPDATE
    assert "material" in diffs[0].diff
    assert "dn" not in diffs[0].diff  # locked excluido
    assert "dn" in diffs[0].locked_fields_skipped


@pytest.mark.asyncio
async def test_compute_diff_no_change_when_identical() -> None:
    existing = _mk_product(
        "SAME-001", dn="DN15", material="brass", manual_locked_fields=[]
    )
    session = MagicMock()
    result = MagicMock()
    result.scalars.return_value.all.return_value = [existing]
    session.execute = AsyncMock(return_value=result)

    rows = [
        ParsedRow(
            row_index=1,
            sku="SAME-001",
            payload={"dn": "DN15", "material": "brass", "name_en": "n", "family": "f"},
        )
    ]
    diffs = await compute_diff(session, rows)
    assert diffs[0].action == RowAction.NO_CHANGE


@pytest.mark.asyncio
async def test_compute_diff_propagates_parse_errors() -> None:
    session = MagicMock()
    result = MagicMock()
    result.scalars.return_value.all.return_value = []
    session.execute = AsyncMock(return_value=result)

    rows = [
        ParsedRow(row_index=1, sku=None, payload={}, errors=["sku missing"]),
    ]
    diffs = await compute_diff(session, rows)
    assert diffs[0].action == RowAction.ERROR
    assert "sku missing" in diffs[0].errors[0]
