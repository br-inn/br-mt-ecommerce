"""Unit tests for app.services.documents.document_service — Fase 4.

Sin DB real — AsyncSession mock + fake rows in-memory.
"""

from __future__ import annotations

from datetime import date
from typing import Any
from unittest.mock import AsyncMock, MagicMock
from uuid import UUID, uuid4

import pytest

from app.services.documents.document_service import (
    DocumentDomainError,
    DocumentService,
)

pytestmark = pytest.mark.unit


# ---------------------------------------------------------------------------
# Fakes
# ---------------------------------------------------------------------------
class _FakeDocument:
    def __init__(
        self,
        *,
        id: UUID | None = None,
        type: str = "ficha_tecnica",
        code: str = "MTFT-1",
        version: str = "rev-1",
        language: str = "es",
        asset_id: UUID | None = None,
        issued_at: date | None = None,
    ) -> None:
        self.id = id or uuid4()
        self.type = type
        self.code = code
        self.version = version
        self.language = language
        self.asset_id = asset_id or uuid4()
        self.issued_at = issued_at


# ---------------------------------------------------------------------------
# Session builder
# ---------------------------------------------------------------------------
def _make_session(
    scalar_one_or_none_seq: list[Any] | None = None,
    scalars_all_seq: list[list[Any]] | None = None,
) -> Any:
    session = MagicMock()
    session.add = MagicMock()
    session.delete = AsyncMock()
    session.flush = AsyncMock()

    one_q = list(scalar_one_or_none_seq or [])
    all_q = list(scalars_all_seq or [])

    async def _execute(_stmt: Any) -> Any:
        result = MagicMock()
        result.scalar_one_or_none.return_value = one_q.pop(0) if one_q else None
        scalars = MagicMock()
        scalars.all.return_value = all_q.pop(0) if all_q else []
        result.scalars.return_value = scalars
        return result

    session.execute = _execute
    return session


# ---------------------------------------------------------------------------
# list_documents
# ---------------------------------------------------------------------------
async def test_list_documents_no_filter() -> None:
    docs = [_FakeDocument(), _FakeDocument(type="manual")]
    session = _make_session(scalars_all_seq=[docs])
    svc = DocumentService(session)
    result = await svc.list_documents()
    assert result == docs


async def test_list_documents_with_filters() -> None:
    docs = [_FakeDocument(type="manual", language="en")]
    session = _make_session(scalars_all_seq=[docs])
    svc = DocumentService(session)
    result = await svc.list_documents(type_="manual", language="en")
    assert result == docs


# ---------------------------------------------------------------------------
# get_document
# ---------------------------------------------------------------------------
async def test_get_document_found() -> None:
    doc = _FakeDocument()
    session = _make_session(scalar_one_or_none_seq=[doc])
    svc = DocumentService(session)
    result = await svc.get_document(doc.id)
    assert result is doc


async def test_get_document_not_found_raises() -> None:
    session = _make_session(scalar_one_or_none_seq=[None])
    svc = DocumentService(session)
    with pytest.raises(DocumentDomainError) as exc:
        await svc.get_document(uuid4())
    assert exc.value.status_code == 404
    assert exc.value.code == "document_not_found"


# ---------------------------------------------------------------------------
# create
# ---------------------------------------------------------------------------
async def test_create_ok() -> None:
    asset_id = uuid4()
    # Execute calls expected in order:
    # 1) _assert_asset_exists → returns asset_id (truthy via scalar_one_or_none)
    # 2) _assert_unique → returns None (no conflict)
    session = _make_session(scalar_one_or_none_seq=[asset_id, None])
    added: list[Any] = []
    session.add = lambda obj: added.append(obj)

    svc = DocumentService(session)
    data = {
        "type": "ficha_tecnica",
        "code": "MTFT-99",
        "version": "rev-1",
        "language": "es",
        "asset_id": asset_id,
        "issued_at": None,
    }
    doc = await svc.create(data)
    assert len(added) == 1
    assert doc.code == "MTFT-99"
    assert doc.asset_id == asset_id


async def test_create_asset_missing_404() -> None:
    # _assert_asset_exists returns None → 404
    session = _make_session(scalar_one_or_none_seq=[None])
    svc = DocumentService(session)
    with pytest.raises(DocumentDomainError) as exc:
        await svc.create(
            {
                "type": "manual",
                "code": "M-1",
                "version": "1",
                "language": "es",
                "asset_id": uuid4(),
            }
        )
    assert exc.value.status_code == 404
    assert exc.value.code == "asset_not_found"


async def test_create_unique_conflict_409() -> None:
    asset_id = uuid4()
    existing = _FakeDocument(code="DUP", version="1", language="es")
    # 1) asset exists ; 2) unique check returns existing → conflict
    session = _make_session(scalar_one_or_none_seq=[asset_id, existing])
    svc = DocumentService(session)
    with pytest.raises(DocumentDomainError) as exc:
        await svc.create(
            {
                "type": "manual",
                "code": "DUP",
                "version": "1",
                "language": "es",
                "asset_id": asset_id,
            }
        )
    assert exc.value.status_code == 409
    assert exc.value.code == "document_conflict"


# ---------------------------------------------------------------------------
# patch
# ---------------------------------------------------------------------------
async def test_patch_single_field_ok() -> None:
    doc = _FakeDocument()
    # 1) get_document → doc; tuplas (code,version,language) no cambian → no unique check.
    session = _make_session(scalar_one_or_none_seq=[doc])
    svc = DocumentService(session)
    updated = await svc.patch(doc.id, {"version": "rev-2"})
    assert updated.version == "rev-2"


async def test_patch_not_found() -> None:
    session = _make_session(scalar_one_or_none_seq=[None])
    svc = DocumentService(session)
    with pytest.raises(DocumentDomainError) as exc:
        await svc.patch(uuid4(), {"version": "x"})
    assert exc.value.status_code == 404


async def test_patch_change_triplet_uniqueness_conflict() -> None:
    doc = _FakeDocument(code="A", version="1", language="es")
    conflict = _FakeDocument(code="A", version="2", language="es")
    # 1) get_document → doc ; 2) unique check encuentra conflicto
    session = _make_session(scalar_one_or_none_seq=[doc, conflict])
    svc = DocumentService(session)
    with pytest.raises(DocumentDomainError) as exc:
        await svc.patch(doc.id, {"version": "2"})
    assert exc.value.status_code == 409


# ---------------------------------------------------------------------------
# delete
# ---------------------------------------------------------------------------
async def test_delete_ok() -> None:
    doc = _FakeDocument()
    session = _make_session(scalar_one_or_none_seq=[doc])
    svc = DocumentService(session)
    await svc.delete(doc.id)
    session.delete.assert_awaited_once_with(doc)


async def test_delete_not_found() -> None:
    session = _make_session(scalar_one_or_none_seq=[None])
    svc = DocumentService(session)
    with pytest.raises(DocumentDomainError) as exc:
        await svc.delete(uuid4())
    assert exc.value.status_code == 404
