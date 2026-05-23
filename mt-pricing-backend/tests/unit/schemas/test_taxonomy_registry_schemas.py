"""Unit tests — Pydantic schemas para registry polimórfico de taxonomías.

No tocan BD. Validan reglas de slug, enums, defaults, y rechazo de extras.
"""

from __future__ import annotations

from datetime import UTC, datetime
from uuid import uuid4

import pytest
from pydantic import ValidationError

from app.schemas.taxonomy_registry import (
    FamilySchemaCreate,
    ProductTaxonomyLinkCreate,
    TaxonomyAliasCreate,
    TaxonomyNodeCreate,
    TaxonomyNodeUpdate,
    TaxonomyTypeCreate,
    TaxonomyTypeRead,
    TaxonomyTypeUpdate,
)

pytestmark = pytest.mark.unit


# ---------------------------------------------------------------------------
# Slug validation — comportamiento compartido entre todos los schemas
# ---------------------------------------------------------------------------


class TestSlugValidation:
    @pytest.mark.parametrize(
        "valid_slug",
        [
            "division",
            "business_line",
            "market_oil_gas",
            "tier_1",
            "abc_123_xyz",
            "a",
        ],
    )
    def test_valid_slugs_accepted(self, valid_slug: str) -> None:
        instance = TaxonomyTypeCreate(slug=valid_slug)
        assert instance.slug == valid_slug

    @pytest.mark.parametrize(
        "invalid_slug",
        [
            "Division",  # uppercase
            "1division",  # comienza con dígito
            "_division",  # comienza con underscore
            "div-ision",  # guión medio
            "div ision",  # espacio
            "división",  # acento (Unicode no-ASCII)
            "",  # vacío
            "DIV",  # todo mayúsculas
        ],
    )
    def test_invalid_slugs_rejected(self, invalid_slug: str) -> None:
        with pytest.raises(ValidationError):
            TaxonomyTypeCreate(slug=invalid_slug)


# ---------------------------------------------------------------------------
# TaxonomyType
# ---------------------------------------------------------------------------


class TestTaxonomyTypeCreate:
    def test_minimal_valid_payload(self) -> None:
        t = TaxonomyTypeCreate(slug="market")
        assert t.slug == "market"
        # defaults
        assert t.is_hierarchical is False
        assert t.value_kind == "enum_open"
        assert t.filterable is True
        assert t.required_for_products is False
        assert t.active is True
        assert t.label_i18n == {}
        assert t.depth_max is None

    def test_full_payload(self) -> None:
        t = TaxonomyTypeCreate(
            slug="certification",
            label_i18n={"es": "Certificaciones", "en": "Certifications"},
            is_hierarchical=True,
            depth_max=3,
            value_kind="enum_closed",
            filterable=True,
            display_order=50,
            ui_layout={"icon": "shield", "position": 5},
            governance_policy={"approval_required": True},
            required_for_products=False,
            external_mappings={"schema_org": "qualitativeValue"},
        )
        assert t.depth_max == 3
        assert t.value_kind == "enum_closed"
        assert t.external_mappings["schema_org"] == "qualitativeValue"

    def test_depth_max_must_be_positive(self) -> None:
        with pytest.raises(ValidationError):
            TaxonomyTypeCreate(slug="foo", depth_max=0)
        with pytest.raises(ValidationError):
            TaxonomyTypeCreate(slug="foo", depth_max=-1)

    @pytest.mark.parametrize(
        "value_kind",
        [
            "enum_closed",
            "enum_open",
            "numeric_with_unit",
            "freetext",
            "reference_to_other_type",
        ],
    )
    def test_all_value_kinds_accepted(self, value_kind: str) -> None:
        t = TaxonomyTypeCreate(slug="foo", value_kind=value_kind)  # type: ignore[arg-type]
        assert t.value_kind == value_kind

    def test_invalid_value_kind_rejected(self) -> None:
        with pytest.raises(ValidationError):
            TaxonomyTypeCreate(slug="foo", value_kind="custom_kind")  # type: ignore[arg-type]

    def test_extra_fields_rejected(self) -> None:
        with pytest.raises(ValidationError):
            TaxonomyTypeCreate(slug="foo", unknown="x")  # type: ignore[call-arg]


class TestTaxonomyTypeUpdate:
    def test_all_optional(self) -> None:
        u = TaxonomyTypeUpdate()
        assert u.label_i18n is None
        assert u.value_kind is None

    def test_partial_update(self) -> None:
        u = TaxonomyTypeUpdate(active=False, display_order=99)
        assert u.active is False
        assert u.display_order == 99
        assert u.value_kind is None

    def test_cannot_update_slug(self) -> None:
        # slug NO está en el schema → Pydantic rechaza por extra="forbid"
        with pytest.raises(ValidationError):
            TaxonomyTypeUpdate(slug="new_slug")  # type: ignore[call-arg]


class TestTaxonomyTypeRead:
    def test_from_attributes(self) -> None:
        now = datetime.now(tz=UTC)
        type_id = uuid4()

        class FakeType:
            id = type_id
            slug = "division"
            is_system = True
            label_i18n = {"es": "Divisiones"}
            is_hierarchical = False
            depth_max = None
            value_kind = "enum_closed"
            filterable = True
            display_order = 10
            ui_layout = {"icon": "layers"}
            governance_policy = {}
            required_for_products = True
            external_mappings = {}
            schema_version = 1
            active = True
            created_at = now
            updated_at = now

        read = TaxonomyTypeRead.model_validate(FakeType())
        assert read.slug == "division"
        assert read.is_system is True
        assert read.depth_max is None


# ---------------------------------------------------------------------------
# TaxonomyNode
# ---------------------------------------------------------------------------


class TestTaxonomyNodeCreate:
    def test_minimal_valid_payload(self) -> None:
        n = TaxonomyNodeCreate(slug="hidrosanitario")
        assert n.slug == "hidrosanitario"
        assert n.labels == {}
        assert n.attributes == {}
        assert n.parent_id is None
        assert n.additional_parents == []
        assert n.active is True

    def test_with_i18n_labels_and_attributes(self) -> None:
        n = TaxonomyNodeCreate(
            slug="api_6d",
            labels={"es": "API 6D", "en": "API 6D"},
            attributes={"issuer": "American Petroleum Institute", "version": 24},
        )
        assert n.attributes["version"] == 24

    def test_multi_inheritance_parents(self) -> None:
        p1 = uuid4()
        p2 = uuid4()
        n = TaxonomyNodeCreate(
            slug="ball_valve_api",
            parent_id=p1,
            additional_parents=[p2],
        )
        assert n.parent_id == p1
        assert p2 in n.additional_parents

    def test_invalid_slug_rejected(self) -> None:
        with pytest.raises(ValidationError):
            TaxonomyNodeCreate(slug="Ball Valve")


class TestTaxonomyNodeUpdate:
    def test_partial_update(self) -> None:
        succ = uuid4()
        u = TaxonomyNodeUpdate(
            superseded_by=succ,
            valid_until=datetime.now(tz=UTC),
        )
        assert u.superseded_by == succ
        assert u.active is None

    def test_cannot_update_slug(self) -> None:
        with pytest.raises(ValidationError):
            TaxonomyNodeUpdate(slug="new")  # type: ignore[call-arg]


# ---------------------------------------------------------------------------
# TaxonomyAlias
# ---------------------------------------------------------------------------


class TestTaxonomyAliasCreate:
    def test_valid(self) -> None:
        target = uuid4()
        a = TaxonomyAliasCreate(
            alias_slug="business_line",
            canonical_node_id=target,
        )
        assert a.alias_slug == "business_line"
        assert a.canonical_node_id == target

    def test_invalid_alias_slug(self) -> None:
        with pytest.raises(ValidationError):
            TaxonomyAliasCreate(
                alias_slug="Business-Line",
                canonical_node_id=uuid4(),
            )


# ---------------------------------------------------------------------------
# ProductTaxonomyLink
# ---------------------------------------------------------------------------


class TestProductTaxonomyLinkCreate:
    def test_default_role_is_belongs_to(self) -> None:
        link = ProductTaxonomyLinkCreate(node_id=uuid4())
        assert link.role == "belongs_to"
        assert link.weight == 0

    @pytest.mark.parametrize(
        "role",
        ["belongs_to", "compatible_with", "replaces", "recommends"],
    )
    def test_all_valid_roles(self, role: str) -> None:
        link = ProductTaxonomyLinkCreate(node_id=uuid4(), role=role)  # type: ignore[arg-type]
        assert link.role == role

    def test_invalid_role_rejected(self) -> None:
        with pytest.raises(ValidationError):
            ProductTaxonomyLinkCreate(node_id=uuid4(), role="competes_with")  # type: ignore[arg-type]


# ---------------------------------------------------------------------------
# FamilySchema
# ---------------------------------------------------------------------------


class TestFamilySchemaCreate:
    def test_valid_minimal(self) -> None:
        s = FamilySchemaCreate(
            family_slug="ball_valve",
            json_schema={"type": "object", "properties": {"dn": {"type": "integer"}}},
        )
        assert s.schema_version == 1
        assert s.family_slug == "ball_valve"

    def test_schema_version_must_be_positive(self) -> None:
        with pytest.raises(ValidationError):
            FamilySchemaCreate(
                family_slug="filter",
                json_schema={},
                schema_version=0,
            )

    def test_invalid_family_slug(self) -> None:
        with pytest.raises(ValidationError):
            FamilySchemaCreate(
                family_slug="Ball-Valve",
                json_schema={},
            )
