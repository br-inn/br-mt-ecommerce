"""Unit tests for app.schemas.documents — Fase 4."""

from __future__ import annotations

from datetime import date
from uuid import uuid4

import pytest
from pydantic import ValidationError

from app.schemas.documents import (
    DocumentCreate,
    DocumentPatch,
    DocumentResponse,
    DocumentType,
)

pytestmark = pytest.mark.unit


# ---------------------------------------------------------------------------
# Enum
# ---------------------------------------------------------------------------
def test_document_type_values() -> None:
    expected = {
        "ficha_tecnica",
        "manual",
        "declaracion_ce",
        "certificado",
        "catalogo",
    }
    assert {v.value for v in DocumentType} == expected


# ---------------------------------------------------------------------------
# DocumentCreate
# ---------------------------------------------------------------------------
def test_create_minimal_valid() -> None:
    asset_id = uuid4()
    doc = DocumentCreate(
        type=DocumentType.FICHA_TECNICA,
        code="MTFT-038",
        version="rev-2",
        language="es",
        asset_id=asset_id,
    )
    assert doc.code == "MTFT-038"
    assert doc.language == "es"
    assert doc.asset_id == asset_id
    assert doc.issued_at is None


def test_create_normalizes_language_lowercase() -> None:
    doc = DocumentCreate(
        type=DocumentType.MANUAL,
        code="MTMAN-1",
        version="1",
        language="EN",
        asset_id=uuid4(),
    )
    assert doc.language == "en"


def test_create_with_issued_at() -> None:
    doc = DocumentCreate(
        type=DocumentType.DECLARACION_CE,
        code="MTCE-2024",
        version="1.0",
        language="es",
        asset_id=uuid4(),
        issued_at=date(2024, 6, 1),
    )
    assert doc.issued_at == date(2024, 6, 1)


def test_create_rejects_bad_type() -> None:
    with pytest.raises(ValidationError):
        DocumentCreate(
            type="bad_type",  # type: ignore[arg-type]
            code="X",
            version="1",
            language="es",
            asset_id=uuid4(),
        )


def test_create_rejects_bad_language_length() -> None:
    with pytest.raises(ValidationError):
        DocumentCreate(
            type=DocumentType.MANUAL,
            code="X",
            version="1",
            language="esp",  # 3 chars
            asset_id=uuid4(),
        )


def test_create_rejects_empty_code() -> None:
    with pytest.raises(ValidationError):
        DocumentCreate(
            type=DocumentType.MANUAL,
            code="",
            version="1",
            language="es",
            asset_id=uuid4(),
        )


def test_create_extra_forbid() -> None:
    with pytest.raises(ValidationError):
        DocumentCreate(
            type=DocumentType.MANUAL,
            code="X",
            version="1",
            language="es",
            asset_id=uuid4(),
            unexpected="hi",  # type: ignore[call-arg]
        )


# ---------------------------------------------------------------------------
# DocumentPatch
# ---------------------------------------------------------------------------
def test_patch_empty_rejected() -> None:
    with pytest.raises(ValidationError):
        DocumentPatch()


def test_patch_single_field_ok() -> None:
    patch = DocumentPatch(version="rev-3")
    payload = patch.model_dump(exclude_unset=True)
    assert payload == {"version": "rev-3"}


def test_patch_language_normalizes() -> None:
    patch = DocumentPatch(language="AR")
    assert patch.language == "ar"


def test_patch_extra_forbid() -> None:
    with pytest.raises(ValidationError):
        DocumentPatch(unknown_field="x")  # type: ignore[call-arg]


# ---------------------------------------------------------------------------
# DocumentResponse
# ---------------------------------------------------------------------------
def test_response_from_attrs() -> None:
    from datetime import UTC, datetime

    class _Row:
        def __init__(self) -> None:
            self.id = uuid4()
            self.type = "ficha_tecnica"
            self.code = "MTFT-1"
            self.version = "rev-1"
            self.language = "es"
            self.asset_id = uuid4()
            self.issued_at = date(2024, 1, 1)
            self.created_at = datetime.now(tz=UTC)

    resp = DocumentResponse.model_validate(_Row())
    assert resp.type == "ficha_tecnica"
    assert resp.code == "MTFT-1"
    assert resp.language == "es"
