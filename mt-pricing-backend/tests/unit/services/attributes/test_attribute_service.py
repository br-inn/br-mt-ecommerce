"""Unit tests for attribute services — Fase 2 EAV.

Covers:
- AttributeService: list with filters, create with code conflict, delete
  blocked when values exist.
- FamilyAttributeService: link idempotency, is_in_template, unlink not found.
- AttributeValueService: template validation (attribute must be in family
  template) + type validation + enum option ownership.

All tests use in-memory async-mocks — no DB.
"""

from __future__ import annotations

from decimal import Decimal
from typing import Any
from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest

from app.schemas.attributes import AttributeValueCreate
from app.services.attributes.attribute_service import (
    AttributeDomainError,
    AttributeService,
    AttributeValueService,
    FamilyAttributeService,
)

pytestmark = pytest.mark.unit


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
def _make_attr_def(
    code: str = "dn_nominal",
    data_type: str = "integer",
    scope: str = "variant",
    attr_id: Any = None,
) -> MagicMock:
    m = MagicMock()
    m.id = attr_id or uuid4()
    m.code = code
    m.label_en = code.replace("_", " ").title()
    m.data_type = data_type
    m.unit = "mm" if data_type in ("number", "integer", "dimension") else None
    m.description_en = None
    m.is_filterable = True
    m.is_seo_relevant = False
    m.scope = scope
    return m


def _make_option(attr_id: Any, code: str = "ss316") -> MagicMock:
    m = MagicMock()
    m.id = uuid4()
    m.attribute_id = attr_id
    m.code = code
    m.label_en = code.upper()
    m.order_index = 0
    return m


def _make_product(sku: str = "X-001", family_id: Any = None) -> MagicMock:
    m = MagicMock()
    m.sku = sku
    m.family_id = family_id or uuid4()
    return m


def _fake_session_with_execute(scalar_result: Any = None, scalars_all: Any = None) -> MagicMock:
    """Build an AsyncMock session whose execute() returns a settable result."""
    session = MagicMock()
    session.commit = AsyncMock()
    session.rollback = AsyncMock()
    session.flush = AsyncMock()
    session.refresh = AsyncMock()
    session.add = MagicMock()
    session.delete = AsyncMock()
    session.get = AsyncMock(return_value=None)

    exec_result = MagicMock()
    exec_result.scalar_one_or_none = MagicMock(return_value=scalar_result)
    if scalars_all is not None:
        scalars = MagicMock()
        scalars.all = MagicMock(return_value=scalars_all)
        exec_result.scalars = MagicMock(return_value=scalars)
    exec_result.rowcount = 1
    session.execute = AsyncMock(return_value=exec_result)
    return session


# ===========================================================================
# AttributeService
# ===========================================================================
class TestAttributeService:
    @pytest.mark.asyncio
    async def test_list_definitions_no_filters(self) -> None:
        attrs = [_make_attr_def("a"), _make_attr_def("b")]
        session = _fake_session_with_execute(scalars_all=attrs)
        svc = AttributeService(session)
        out = await svc.list_definitions()
        assert out == attrs

    @pytest.mark.asyncio
    async def test_get_definition_not_found(self) -> None:
        session = _fake_session_with_execute()
        session.get = AsyncMock(return_value=None)
        svc = AttributeService(session)
        with pytest.raises(AttributeDomainError) as exc:
            await svc.get_definition(uuid4())
        assert exc.value.code == "attribute_not_found"
        assert exc.value.status_code == 404

    @pytest.mark.asyncio
    async def test_get_definition_by_code_not_found(self) -> None:
        session = _fake_session_with_execute(scalar_result=None)
        svc = AttributeService(session)
        with pytest.raises(AttributeDomainError) as exc:
            await svc.get_definition_by_code("missing")
        assert exc.value.code == "attribute_not_found"

    @pytest.mark.asyncio
    async def test_create_definition_conflict(self) -> None:
        existing = _make_attr_def("dup")
        session = _fake_session_with_execute(scalar_result=existing)
        svc = AttributeService(session)
        with pytest.raises(AttributeDomainError) as exc:
            await svc.create_definition(
                {
                    "code": "dup",
                    "label_en": "Dup",
                    "data_type": "text",
                    "scope": "product",
                }
            )
        assert exc.value.code == "attribute_code_conflict"
        assert exc.value.status_code == 409

    @pytest.mark.asyncio
    async def test_delete_definition_blocked_when_values_exist(self) -> None:
        attr = _make_attr_def("dn_nominal")
        # First execute() for get_definition does not run (we use session.get
        # for that); the second execute() is the existing-values probe.
        session = MagicMock()
        session.get = AsyncMock(return_value=attr)
        session.commit = AsyncMock()
        session.delete = AsyncMock()
        # session.execute returns an object whose scalar_one_or_none() yields
        # a non-None value -> values exist.
        exec_result = MagicMock()
        exec_result.scalar_one_or_none = MagicMock(return_value=uuid4())
        session.execute = AsyncMock(return_value=exec_result)

        svc = AttributeService(session)
        with pytest.raises(AttributeDomainError) as exc:
            await svc.delete_definition(attr.id)
        assert exc.value.code == "attribute_has_values"
        # Ensure we did NOT actually delete
        session.delete.assert_not_called()

    @pytest.mark.asyncio
    async def test_create_option_rejects_non_enum_attribute(self) -> None:
        attr = _make_attr_def("dn_nominal", data_type="integer")
        session = MagicMock()
        session.get = AsyncMock(return_value=attr)
        svc = AttributeService(session)
        with pytest.raises(AttributeDomainError) as exc:
            await svc.create_option(attr.id, {"code": "x", "label_en": "X", "order_index": 0})
        assert exc.value.code == "attribute_not_enum"


# ===========================================================================
# FamilyAttributeService
# ===========================================================================
class TestFamilyAttributeService:
    @pytest.mark.asyncio
    async def test_link_attribute_not_found(self) -> None:
        session = MagicMock()
        session.get = AsyncMock(return_value=None)
        svc = FamilyAttributeService(session)
        with pytest.raises(AttributeDomainError) as exc:
            await svc.link(
                uuid4(), uuid4(), {"group_code": "x", "order_index": 0, "is_required": False}
            )
        assert exc.value.code == "attribute_not_found"

    @pytest.mark.asyncio
    async def test_link_is_idempotent_patches_existing(self) -> None:
        attr = _make_attr_def("dn_nominal")
        existing_link = MagicMock()
        existing_link.family_id = uuid4()
        existing_link.attribute_id = attr.id
        existing_link.group_code = "old_group"
        existing_link.order_index = 0
        existing_link.is_required = False
        existing_link.default_value = None
        existing_link.validation_rule = None

        session = MagicMock()
        session.get = AsyncMock(return_value=attr)
        session.commit = AsyncMock()
        session.flush = AsyncMock()
        # First execute (look for existing link) returns existing_link
        exec_result = MagicMock()
        exec_result.scalar_one_or_none = MagicMock(return_value=existing_link)
        session.execute = AsyncMock(return_value=exec_result)

        svc = FamilyAttributeService(session)
        out = await svc.link(
            existing_link.family_id,
            attr.id,
            {
                "group_code": "new_group",
                "order_index": 99,
                "is_required": True,
                "default_value": None,
                "validation_rule": None,
            },
        )
        assert out is existing_link
        assert existing_link.group_code == "new_group"
        assert existing_link.order_index == 99
        assert existing_link.is_required is True

    @pytest.mark.asyncio
    async def test_unlink_not_found(self) -> None:
        session = MagicMock()
        exec_result = MagicMock()
        exec_result.scalar_one_or_none = MagicMock(return_value=None)
        session.execute = AsyncMock(return_value=exec_result)
        svc = FamilyAttributeService(session)
        with pytest.raises(AttributeDomainError) as exc:
            await svc.unlink(uuid4(), uuid4())
        assert exc.value.code == "family_attribute_not_found"

    @pytest.mark.asyncio
    async def test_is_in_template_positive(self) -> None:
        session = MagicMock()
        exec_result = MagicMock()
        exec_result.scalar_one_or_none = MagicMock(return_value=uuid4())
        session.execute = AsyncMock(return_value=exec_result)
        svc = FamilyAttributeService(session)
        assert await svc.is_in_template(uuid4(), uuid4()) is True

    @pytest.mark.asyncio
    async def test_is_in_template_negative(self) -> None:
        session = MagicMock()
        exec_result = MagicMock()
        exec_result.scalar_one_or_none = MagicMock(return_value=None)
        session.execute = AsyncMock(return_value=exec_result)
        svc = FamilyAttributeService(session)
        assert await svc.is_in_template(uuid4(), uuid4()) is False


# ===========================================================================
# AttributeValueService
# ===========================================================================
class TestAttributeValueServiceUpsert:
    @pytest.mark.asyncio
    async def test_product_not_found(self) -> None:
        session = MagicMock()
        session.get = AsyncMock(return_value=None)
        svc = AttributeValueService(session)
        payload = AttributeValueCreate(value_number=Decimal("50"))
        with pytest.raises(AttributeDomainError) as exc:
            await svc.upsert_for_product("MISSING", "dn_nominal", payload)
        assert exc.value.code == "product_not_found"

    @pytest.mark.asyncio
    async def test_attribute_not_in_family_template(self) -> None:
        # Product exists; attribute exists; but template does not include it.
        product = _make_product()
        attr = _make_attr_def("dn_nominal", data_type="integer")

        session = MagicMock()
        # session.get is called twice: once for Product (returns product),
        # we don't model that here — we use side_effect.
        session.get = AsyncMock(side_effect=[product])

        # Execute is called in this order:
        #   1) get_definition_by_code -> attr
        #   2) is_in_template -> None (not in template)
        exec_results: list[MagicMock] = []
        for value in [attr, None]:
            r = MagicMock()
            r.scalar_one_or_none = MagicMock(return_value=value)
            exec_results.append(r)
        session.execute = AsyncMock(side_effect=exec_results)
        session.commit = AsyncMock()

        svc = AttributeValueService(session)
        payload = AttributeValueCreate(value_number=Decimal("50"))
        with pytest.raises(AttributeDomainError) as exc:
            await svc.upsert_for_product(product.sku, "dn_nominal", payload)
        assert exc.value.code == "attribute_not_in_family_template"
        assert exc.value.status_code == 409

    @pytest.mark.asyncio
    async def test_value_type_mismatch(self) -> None:
        # Attribute is 'enum' but payload populates value_number -> mismatch.
        product = _make_product()
        attr = _make_attr_def("material_body", data_type="enum")

        session = MagicMock()
        session.get = AsyncMock(side_effect=[product])
        exec_results: list[MagicMock] = []
        # 1) get_definition_by_code -> attr
        r1 = MagicMock()
        r1.scalar_one_or_none = MagicMock(return_value=attr)
        exec_results.append(r1)
        # 2) is_in_template -> truthy
        r2 = MagicMock()
        r2.scalar_one_or_none = MagicMock(return_value=uuid4())
        exec_results.append(r2)
        session.execute = AsyncMock(side_effect=exec_results)
        session.commit = AsyncMock()

        svc = AttributeValueService(session)
        # Payload uses value_number, but data_type=enum needs value_enum_id.
        payload = AttributeValueCreate(value_number=Decimal("50"))
        with pytest.raises(AttributeDomainError) as exc:
            await svc.upsert_for_product(product.sku, "material_body", payload)
        assert exc.value.code == "attribute_value_type_mismatch"
        assert exc.value.status_code == 400

    @pytest.mark.asyncio
    async def test_enum_option_belongs_to_wrong_attribute(self) -> None:
        product = _make_product()
        attr = _make_attr_def("material_body", data_type="enum")
        other_attr_id = uuid4()
        # Option points to a DIFFERENT attribute_id -> mismatch.
        wrong_option = _make_option(attr_id=other_attr_id, code="brass")

        session = MagicMock()
        # session.get: Product (first), then AttributeOption (later)
        session.get = AsyncMock(side_effect=[product, wrong_option])
        # execute calls:
        # 1) get_definition_by_code -> attr
        # 2) is_in_template -> truthy
        r1 = MagicMock()
        r1.scalar_one_or_none = MagicMock(return_value=attr)
        r2 = MagicMock()
        r2.scalar_one_or_none = MagicMock(return_value=uuid4())
        session.execute = AsyncMock(side_effect=[r1, r2])
        session.commit = AsyncMock()

        svc = AttributeValueService(session)
        payload = AttributeValueCreate(value_enum_id=wrong_option.id)
        with pytest.raises(AttributeDomainError) as exc:
            await svc.upsert_for_product(product.sku, "material_body", payload)
        assert exc.value.code == "attribute_enum_option_mismatch"

    @pytest.mark.asyncio
    async def test_delete_for_product_not_found(self) -> None:
        attr = _make_attr_def("dn_nominal")
        session = MagicMock()
        # get_definition_by_code -> attr
        r1 = MagicMock()
        r1.scalar_one_or_none = MagicMock(return_value=attr)
        # delete statement returns rowcount=0
        r2 = MagicMock()
        r2.rowcount = 0
        session.execute = AsyncMock(side_effect=[r1, r2])
        session.commit = AsyncMock()

        svc = AttributeValueService(session)
        with pytest.raises(AttributeDomainError) as exc:
            await svc.delete_for_product("X-001", "dn_nominal")
        assert exc.value.code == "attribute_value_not_found"
        assert exc.value.status_code == 404
