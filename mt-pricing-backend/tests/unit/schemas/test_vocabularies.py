"""Unit tests for vocabulary Pydantic schemas (Wave 4)."""

from __future__ import annotations

from datetime import date, datetime, UTC
from uuid import uuid4

import pytest

from app.schemas.vocabularies import (
    ApplicationCreate,
    ApplicationPatch,
    ApplicationResponse,
    CertificationCreate,
    CertificationOwnerType,
    CertificationPatch,
    CertificationResponse,
    ProductApplicationLink,
    ProductApplicationResponse,
    ProductCertificationLink,
    ProductCertificationResponse,
)

pytestmark = pytest.mark.unit


class TestCertificationSchemas:
    def test_certification_create_valid(self) -> None:
        data = CertificationCreate(code="CE", name="CE Marking", issued_by="EU", active=True)
        assert data.code == "CE"
        assert data.active is True

    def test_certification_create_strips_whitespace(self) -> None:
        data = CertificationCreate(code="  CE  ", name="  CE Marking  ")
        assert data.code == "CE"
        assert data.name == "CE Marking"

    def test_certification_create_rejects_extra_fields(self) -> None:
        with pytest.raises(Exception):
            CertificationCreate(code="CE", name="CE Marking", unknown_field="x")

    def test_certification_patch_all_optional(self) -> None:
        patch = CertificationPatch()
        assert patch.name is None
        assert patch.active is None

    def test_certification_patch_partial(self) -> None:
        patch = CertificationPatch(active=False)
        assert patch.active is False
        assert patch.name is None

    def test_certification_response_from_attributes(self) -> None:
        now = datetime.now(tz=UTC)
        cert_id = uuid4()

        class FakeCert:
            id = cert_id
            code = "CE"
            name = "CE Marking"
            issued_by = "European Commission"
            scope = "European conformity"
            logo_url = None
            active = True
            created_at = now
            updated_at = now

        resp = CertificationResponse.model_validate(FakeCert())
        assert resp.id == cert_id
        assert resp.code == "CE"


class TestApplicationSchemas:
    def test_application_create_valid(self) -> None:
        data = ApplicationCreate(code="water", name="Water", description="H2O")
        assert data.code == "water"

    def test_application_create_defaults(self) -> None:
        data = ApplicationCreate(code="water", name="Water")
        assert data.active is True
        assert data.description is None

    def test_application_patch_partial(self) -> None:
        patch = ApplicationPatch(description="Updated")
        assert patch.description == "Updated"
        assert patch.name is None

    def test_application_response_from_attributes(self) -> None:
        now = datetime.now(tz=UTC)
        app_id = uuid4()

        class FakeApp:
            id = app_id
            code = "water"
            name = "Water"
            description = "Drinking water"
            active = True
            created_at = now
            updated_at = now

        resp = ApplicationResponse.model_validate(FakeApp())
        assert resp.id == app_id
        assert resp.code == "water"


class TestProductLinkSchemas:
    def test_product_cert_link_required_field(self) -> None:
        cert_id = uuid4()
        link = ProductCertificationLink(certification_id=cert_id)
        assert link.certification_id == cert_id
        assert link.obtained_at is None

    def test_product_cert_link_with_dates(self) -> None:
        link = ProductCertificationLink(
            certification_id=uuid4(),
            obtained_at=date(2025, 1, 1),
            expires_at=date(2030, 12, 31),
            notes="Test note",
        )
        assert link.obtained_at == date(2025, 1, 1)
        assert link.notes == "Test note"

    def test_product_app_link_defaults(self) -> None:
        link = ProductApplicationLink(application_id=uuid4())
        assert link.is_primary is False
        assert link.position == 0

    def test_product_app_link_position_bounds(self) -> None:
        # Valid
        link = ProductApplicationLink(application_id=uuid4(), position=32767)
        assert link.position == 32767
        # Invalid negative
        with pytest.raises(Exception):
            ProductApplicationLink(application_id=uuid4(), position=-1)


class TestCertificationOwnerType:
    """Fase 5 — owner_type polymorphic en ProductCertificationLink/Response."""

    def test_owner_type_enum_values(self) -> None:
        assert {o.value for o in CertificationOwnerType} == {
            "product",
            "variant",
            "series",
        }

    def test_cert_link_defaults_owner_type_product(self) -> None:
        """Sin owner_type explícito → 'product' (compat con clientes legacy)."""
        link = ProductCertificationLink(certification_id=uuid4())
        assert link.owner_type == CertificationOwnerType.product
        assert link.owner_id is None

    def test_cert_link_with_series_owner(self) -> None:
        """Certificación adjunta a serie completa."""
        link = ProductCertificationLink(
            certification_id=uuid4(),
            owner_type=CertificationOwnerType.series,
            owner_id="series-pn40-platinum",
        )
        assert link.owner_type == CertificationOwnerType.series
        assert link.owner_id == "series-pn40-platinum"

    def test_cert_response_includes_owner_fields(self) -> None:
        """ProductCertificationResponse expone owner_type/owner_id."""
        now = datetime.now(tz=UTC)
        cert_id = uuid4()
        resp = ProductCertificationResponse(
            certification_id=cert_id,
            code="CE",
            name="CE",
            issued_by=None,
            scope=None,
            logo_url=None,
            certificate_pdf_asset_id=None,
            obtained_at=None,
            expires_at=None,
            notes=None,
            created_at=now,
            owner_type=CertificationOwnerType.series,
            owner_id="series-pn40",
        )
        assert resp.owner_type == CertificationOwnerType.series
        assert resp.owner_id == "series-pn40"

    def test_cert_response_from_link_backfills_legacy(self) -> None:
        """from_link maneja rows legacy sin owner_type (default 'product')."""
        now = datetime.now(tz=UTC)

        class _FakeCert:
            code = "CE"
            name = "CE Marking"
            issued_by = None
            scope = None
            logo_url = None

        class _FakeLink:
            certification_id = uuid4()
            certificate_pdf_asset_id = None
            obtained_at = None
            expires_at = None
            notes = None
            created_at = now
            owner_type = "product"
            owner_id = "MT-A-001"
            certification = _FakeCert()

        resp = ProductCertificationResponse.from_link(_FakeLink())
        assert resp.owner_type == CertificationOwnerType.product
        assert resp.owner_id == "MT-A-001"
