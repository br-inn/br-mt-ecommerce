"""Unit tests para `app.services.importer_materials.applier` con repo mockeado."""

from __future__ import annotations

from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock

import pytest

from app.services.importer_materials.applier import apply_material_rows
from app.services.importer_materials.parser import MaterialRow

pytestmark = pytest.mark.unit


def _row(*, errors=None, descriptor="A", temp=10):
    return MaterialRow(
        row_index=1,
        producto_descriptor=descriptor,
        temperatura_c=Decimal(temp) if temp is not None else None,
        compatibilities={"pvc": "ok"},
        errors=list(errors or []),
    )


async def test_apply_replace_calls_replace_all_and_truncates() -> None:
    repo = MagicMock()
    repo.replace_all = AsyncMock(return_value=2)
    repo.insert_many = AsyncMock()
    rows = [_row(descriptor="A"), _row(descriptor="B", temp=20)]
    res = await apply_material_rows(rows, repo=repo, mode="replace")
    assert res.inserted == 2
    assert res.truncated is True
    assert res.errors == 0
    repo.replace_all.assert_awaited_once()
    repo.insert_many.assert_not_awaited()


async def test_apply_append_does_not_truncate() -> None:
    repo = MagicMock()
    repo.replace_all = AsyncMock()
    repo.insert_many = AsyncMock(return_value=1)
    rows = [_row()]
    res = await apply_material_rows(rows, repo=repo, mode="append")
    assert res.inserted == 1
    assert res.truncated is False
    repo.insert_many.assert_awaited_once()
    repo.replace_all.assert_not_awaited()


async def test_apply_skips_rows_with_errors() -> None:
    repo = MagicMock()
    repo.replace_all = AsyncMock(return_value=1)
    rows = [_row(descriptor="A"), _row(errors=["broken"], descriptor="B")]
    res = await apply_material_rows(rows, repo=repo, mode="replace")
    assert res.inserted == 1
    assert res.errors == 1
    assert len(res.failure_details) == 1
    args = repo.replace_all.await_args.args[0]
    assert len(args) == 1
    assert args[0]["producto_descriptor"] == "A"


async def test_apply_invalid_mode_raises() -> None:
    repo = MagicMock()
    with pytest.raises(ValueError):
        await apply_material_rows([_row()], repo=repo, mode="bogus")


async def test_apply_to_dict_serializable() -> None:
    repo = MagicMock()
    repo.replace_all = AsyncMock(return_value=0)
    res = await apply_material_rows([], repo=repo, mode="replace")
    d = res.to_dict()
    assert d["inserted"] == 0
    assert d["truncated"] is True
    assert isinstance(d["started_at"], str)
