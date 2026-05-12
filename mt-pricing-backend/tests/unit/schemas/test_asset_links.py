"""Unit tests for app.schemas.asset_links — Fase 4."""

from __future__ import annotations

from uuid import uuid4

import pytest
from pydantic import ValidationError

from app.schemas.asset_links import (
    AssetLinkCreate,
    AssetLinkOwnerType,
    AssetLinkResponse,
    AssetLinkRole,
)

pytestmark = pytest.mark.unit


# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------
def test_owner_type_values() -> None:
    expected = {"product", "variant", "series", "family", "spare_part"}
    assert {v.value for v in AssetLinkOwnerType} == expected


def test_role_values() -> None:
    expected = {
        "image_padre",
        "banner",
        "ficha_pdf",
        "manual_pdf",
        "ce_pdf",
        "catalogo_pdf",
        "exploded_3d",
        "section_drawing",
        "dimensions_drawing",
        "video",
        "web_image",
        "main_image",
    }
    assert {v.value for v in AssetLinkRole} == expected


# ---------------------------------------------------------------------------
# AssetLinkCreate
# ---------------------------------------------------------------------------
def test_create_minimal_valid() -> None:
    asset_id = uuid4()
    link = AssetLinkCreate(
        asset_id=asset_id,
        owner_type=AssetLinkOwnerType.PRODUCT,
        owner_id="MT-V-038",
        role=AssetLinkRole.WEB_IMAGE,
    )
    assert link.asset_id == asset_id
    assert link.owner_type == AssetLinkOwnerType.PRODUCT
    assert link.role == AssetLinkRole.WEB_IMAGE
    assert link.order_index == 0


def test_create_with_order_index() -> None:
    link = AssetLinkCreate(
        asset_id=uuid4(),
        owner_type="series",
        owner_id="series-001",
        role="banner",
        order_index=5,
    )
    assert link.order_index == 5


def test_create_rejects_bad_owner_type() -> None:
    with pytest.raises(ValidationError):
        AssetLinkCreate(
            asset_id=uuid4(),
            owner_type="invalid_owner",
            owner_id="X",
            role=AssetLinkRole.WEB_IMAGE,
        )


def test_create_rejects_bad_role() -> None:
    with pytest.raises(ValidationError):
        AssetLinkCreate(
            asset_id=uuid4(),
            owner_type=AssetLinkOwnerType.PRODUCT,
            owner_id="X",
            role="not_a_role",
        )


def test_create_rejects_empty_owner_id() -> None:
    with pytest.raises(ValidationError):
        AssetLinkCreate(
            asset_id=uuid4(),
            owner_type=AssetLinkOwnerType.PRODUCT,
            owner_id="",
            role=AssetLinkRole.WEB_IMAGE,
        )


def test_create_rejects_negative_order_index() -> None:
    with pytest.raises(ValidationError):
        AssetLinkCreate(
            asset_id=uuid4(),
            owner_type=AssetLinkOwnerType.PRODUCT,
            owner_id="MT-V-038",
            role=AssetLinkRole.WEB_IMAGE,
            order_index=-1,
        )


def test_create_extra_forbid() -> None:
    with pytest.raises(ValidationError):
        AssetLinkCreate(
            asset_id=uuid4(),
            owner_type=AssetLinkOwnerType.PRODUCT,
            owner_id="MT-V-038",
            role=AssetLinkRole.WEB_IMAGE,
            extra_field="x",  # type: ignore[call-arg]
        )


# ---------------------------------------------------------------------------
# AssetLinkResponse
# ---------------------------------------------------------------------------
def test_response_from_attrs_object() -> None:
    from datetime import UTC, datetime

    class _Row:
        def __init__(self) -> None:
            self.id = uuid4()
            self.asset_id = uuid4()
            self.owner_type = "product"
            self.owner_id = "MT-V-038"
            self.role = "ficha_pdf"
            self.order_index = 2
            self.created_at = datetime.now(tz=UTC)

    row = _Row()
    resp = AssetLinkResponse.model_validate(row)
    assert resp.owner_type == "product"
    assert resp.role == "ficha_pdf"
    assert resp.order_index == 2
