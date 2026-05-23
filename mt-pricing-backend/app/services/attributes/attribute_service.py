"""Attribute services — Fase 2 EAV typed attribute system.

- ``AttributeService``: CRUD para AttributeDefinition + AttributeOption.
- ``FamilyAttributeService``: link/unlink atributos a familias (template).
- ``AttributeValueService``: upsert/list/delete valores por owner; valida
  contra plantilla de familia (un atributo solo puede asignarse a un
  producto si está en family_attributes de la familia del producto, o si
  está marcado como scope agnóstico).
- ``AttributeDomainError``: errores de dominio normalizados.
"""

from __future__ import annotations

from collections.abc import Sequence
from typing import Any
from uuid import UUID

from sqlalchemy import delete, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.db.models.attributes import (
    AttributeDefinition,
    AttributeOption,
    AttributeValue,
    FamilyAttribute,
)
from app.db.models.product import Product
from app.schemas.attributes import (
    AttributeValueBase,
    validate_value_matches_type,
)


class AttributeDomainError(Exception):
    """Domain error for attribute operations — maps to HTTP via API layer."""

    def __init__(self, message: str, code: str, status_code: int = 400) -> None:
        super().__init__(message)
        self.message = message
        self.code = code
        self.status_code = status_code


# ===========================================================================
# AttributeService — CRUD definitions + options
# ===========================================================================
class AttributeService:
    """Admin-only CRUD for attribute_definitions + attribute_options."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    # ---- definitions -------------------------------------------------------
    async def list_definitions(
        self,
        *,
        only_filterable: bool = False,
        only_seo: bool = False,
        scope: str | None = None,
    ) -> Sequence[AttributeDefinition]:
        stmt = select(AttributeDefinition)
        if only_filterable:
            stmt = stmt.where(AttributeDefinition.is_filterable.is_(True))
        if only_seo:
            stmt = stmt.where(AttributeDefinition.is_seo_relevant.is_(True))
        if scope is not None:
            stmt = stmt.where(AttributeDefinition.scope.in_([scope, "both"]))
        stmt = stmt.order_by(AttributeDefinition.code)
        result = await self.session.execute(stmt)
        return result.scalars().all()

    async def get_definition(self, attr_id: UUID) -> AttributeDefinition:
        row = await self.session.get(AttributeDefinition, attr_id)
        if row is None:
            raise AttributeDomainError(
                f"Attribute {attr_id} not found",
                code="attribute_not_found",
                status_code=404,
            )
        return row

    async def get_definition_by_code(self, code: str) -> AttributeDefinition:
        stmt = select(AttributeDefinition).where(AttributeDefinition.code == code)
        result = await self.session.execute(stmt)
        row = result.scalar_one_or_none()
        if row is None:
            raise AttributeDomainError(
                f"Attribute with code '{code}' not found",
                code="attribute_not_found",
                status_code=404,
            )
        return row

    async def create_definition(self, data: dict[str, Any]) -> AttributeDefinition:
        existing = await self.session.execute(
            select(AttributeDefinition).where(AttributeDefinition.code == data["code"])
        )
        if existing.scalar_one_or_none() is not None:
            raise AttributeDomainError(
                f"Attribute with code '{data['code']}' already exists",
                code="attribute_code_conflict",
                status_code=409,
            )
        row = AttributeDefinition(**data)
        self.session.add(row)
        try:
            await self.session.commit()
        except IntegrityError as e:
            await self.session.rollback()
            raise AttributeDomainError(
                f"Attribute creation failed: {e.orig}",
                code="attribute_create_failed",
                status_code=400,
            ) from e
        await self.session.refresh(row)
        return row

    async def patch_definition(self, attr_id: UUID, data: dict[str, Any]) -> AttributeDefinition:
        row = await self.get_definition(attr_id)
        for k, v in data.items():
            setattr(row, k, v)
        await self.session.flush()
        await self.session.commit()
        return row

    async def delete_definition(self, attr_id: UUID) -> None:
        row = await self.get_definition(attr_id)
        # Check no values exist (ON DELETE RESTRICT would do this, but the
        # error path is clearer here).
        existing_values = await self.session.execute(
            select(AttributeValue.id).where(AttributeValue.attribute_id == attr_id).limit(1)
        )
        if existing_values.scalar_one_or_none() is not None:
            raise AttributeDomainError(
                f"Cannot delete attribute {attr_id}: has assigned values",
                code="attribute_has_values",
                status_code=409,
            )
        await self.session.delete(row)
        await self.session.commit()

    # ---- options -----------------------------------------------------------
    async def list_options(self, attr_id: UUID) -> Sequence[AttributeOption]:
        stmt = (
            select(AttributeOption)
            .where(AttributeOption.attribute_id == attr_id)
            .order_by(AttributeOption.order_index, AttributeOption.code)
        )
        result = await self.session.execute(stmt)
        return result.scalars().all()

    async def get_option(self, option_id: UUID) -> AttributeOption:
        row = await self.session.get(AttributeOption, option_id)
        if row is None:
            raise AttributeDomainError(
                f"Option {option_id} not found",
                code="attribute_option_not_found",
                status_code=404,
            )
        return row

    async def create_option(self, attr_id: UUID, data: dict[str, Any]) -> AttributeOption:
        attr = await self.get_definition(attr_id)
        if attr.data_type != "enum":
            raise AttributeDomainError(
                f"Cannot add options to non-enum attribute (data_type={attr.data_type})",
                code="attribute_not_enum",
                status_code=400,
            )
        row = AttributeOption(attribute_id=attr_id, **data)
        self.session.add(row)
        try:
            await self.session.commit()
        except IntegrityError as e:
            await self.session.rollback()
            raise AttributeDomainError(
                f"Option creation failed: {e.orig}",
                code="attribute_option_conflict",
                status_code=409,
            ) from e
        await self.session.refresh(row)
        return row

    async def patch_option(self, option_id: UUID, data: dict[str, Any]) -> AttributeOption:
        row = await self.get_option(option_id)
        for k, v in data.items():
            setattr(row, k, v)
        await self.session.flush()
        await self.session.commit()
        return row

    async def delete_option(self, option_id: UUID) -> None:
        row = await self.get_option(option_id)
        await self.session.delete(row)
        await self.session.commit()


# ===========================================================================
# FamilyAttributeService — template per family
# ===========================================================================
class FamilyAttributeService:
    """Link/unlink attributes to families (template)."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def list_for_family(self, family_id: UUID) -> Sequence[FamilyAttribute]:
        stmt = (
            select(FamilyAttribute)
            .where(FamilyAttribute.family_id == family_id)
            .options(selectinload(FamilyAttribute.attribute))
            .order_by(
                FamilyAttribute.group_code,
                FamilyAttribute.order_index,
            )
        )
        result = await self.session.execute(stmt)
        return result.scalars().all()

    async def link(
        self, family_id: UUID, attribute_id: UUID, data: dict[str, Any]
    ) -> FamilyAttribute:
        # Validate attribute exists
        attr = await self.session.get(AttributeDefinition, attribute_id)
        if attr is None:
            raise AttributeDomainError(
                f"Attribute {attribute_id} not found",
                code="attribute_not_found",
                status_code=404,
            )
        # Idempotent: if link exists, patch it; otherwise create.
        existing = await self.session.execute(
            select(FamilyAttribute).where(
                FamilyAttribute.family_id == family_id,
                FamilyAttribute.attribute_id == attribute_id,
            )
        )
        link = existing.scalar_one_or_none()
        if link is not None:
            for k, v in data.items():
                if k in ("family_id", "attribute_id"):
                    continue
                setattr(link, k, v)
            await self.session.flush()
            await self.session.commit()
            return link

        link = FamilyAttribute(
            family_id=family_id,
            attribute_id=attribute_id,
            **{k: v for k, v in data.items() if k not in ("family_id", "attribute_id")},
        )
        self.session.add(link)
        try:
            await self.session.commit()
        except IntegrityError as e:
            await self.session.rollback()
            raise AttributeDomainError(
                f"Family-attribute link failed: {e.orig}",
                code="family_attribute_conflict",
                status_code=409,
            ) from e
        await self.session.refresh(link)
        return link

    async def unlink(self, family_id: UUID, attribute_id: UUID) -> None:
        stmt = select(FamilyAttribute).where(
            FamilyAttribute.family_id == family_id,
            FamilyAttribute.attribute_id == attribute_id,
        )
        result = await self.session.execute(stmt)
        link = result.scalar_one_or_none()
        if link is None:
            raise AttributeDomainError(
                f"Family={family_id} attribute={attribute_id} link not found",
                code="family_attribute_not_found",
                status_code=404,
            )
        await self.session.delete(link)
        await self.session.commit()

    async def is_in_template(self, family_id: UUID, attribute_id: UUID) -> bool:
        stmt = select(FamilyAttribute.id).where(
            FamilyAttribute.family_id == family_id,
            FamilyAttribute.attribute_id == attribute_id,
        )
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none() is not None


# ===========================================================================
# AttributeValueService — upsert/list/delete by owner
# ===========================================================================
class AttributeValueService:
    """Manage attribute values for products / variants with template validation."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.attribute_svc = AttributeService(session)
        self.template_svc = FamilyAttributeService(session)

    # ---- list / get --------------------------------------------------------
    async def list_for_product(self, sku: str) -> Sequence[AttributeValue]:
        stmt = (
            select(AttributeValue)
            .where(
                AttributeValue.owner_type == "product",
                AttributeValue.owner_id == sku,
            )
            .options(selectinload(AttributeValue.attribute))
            .order_by(AttributeValue.attribute_id)
        )
        result = await self.session.execute(stmt)
        return result.scalars().all()

    async def get_for_product(self, sku: str, attribute_code: str) -> AttributeValue:
        attr = await self.attribute_svc.get_definition_by_code(attribute_code)
        stmt = select(AttributeValue).where(
            AttributeValue.owner_type == "product",
            AttributeValue.owner_id == sku,
            AttributeValue.attribute_id == attr.id,
        )
        result = await self.session.execute(stmt)
        row = result.scalar_one_or_none()
        if row is None:
            raise AttributeDomainError(
                f"No value for product={sku} attribute={attribute_code}",
                code="attribute_value_not_found",
                status_code=404,
            )
        return row

    # ---- upsert ------------------------------------------------------------
    async def upsert_for_product(
        self,
        sku: str,
        attribute_code: str,
        payload: AttributeValueBase,
    ) -> AttributeValue:
        """Upsert a value for a product, validating against family template."""
        # 1. Verify product exists + fetch its family_id.
        product = await self.session.get(Product, sku)
        if product is None:
            raise AttributeDomainError(
                f"Product {sku} not found",
                code="product_not_found",
                status_code=404,
            )

        # 2. Verify attribute exists.
        attr = await self.attribute_svc.get_definition_by_code(attribute_code)

        # 3. Verify attribute is in family template.
        in_template = await self.template_svc.is_in_template(product.family_id, attr.id)
        if not in_template:
            raise AttributeDomainError(
                (
                    f"Attribute '{attribute_code}' is not part of the template "
                    f"for family_id={product.family_id}. "
                    f"Add it via /admin/families/{{family_id}}/attributes/{{attr_id}}."
                ),
                code="attribute_not_in_family_template",
                status_code=409,
            )

        # 4. Validate payload field matches attribute data_type.
        try:
            validate_value_matches_type(payload, attr.data_type)  # type: ignore[arg-type]
        except ValueError as e:
            raise AttributeDomainError(
                str(e),
                code="attribute_value_type_mismatch",
                status_code=400,
            ) from e

        # 5. If enum, verify value_enum_id belongs to this attribute.
        if attr.data_type == "enum" and payload.value_enum_id is not None:
            option = await self.session.get(AttributeOption, payload.value_enum_id)
            if option is None or option.attribute_id != attr.id:
                raise AttributeDomainError(
                    (
                        f"value_enum_id={payload.value_enum_id} does not belong "
                        f"to attribute '{attribute_code}'"
                    ),
                    code="attribute_enum_option_mismatch",
                    status_code=400,
                )

        # 6. Upsert: find existing by (owner_type, owner_id, attribute_id, language).
        existing_stmt = select(AttributeValue).where(
            AttributeValue.owner_type == "product",
            AttributeValue.owner_id == sku,
            AttributeValue.attribute_id == attr.id,
            AttributeValue.language.is_(None)
            if payload.language is None
            else AttributeValue.language == payload.language,
        )
        existing = await self.session.execute(existing_stmt)
        row = existing.scalar_one_or_none()

        payload_dict = payload.model_dump()
        if row is None:
            row = AttributeValue(
                owner_type="product",
                owner_id=sku,
                attribute_id=attr.id,
                **payload_dict,
            )
            self.session.add(row)
        else:
            for k, v in payload_dict.items():
                setattr(row, k, v)

        try:
            await self.session.commit()
        except IntegrityError as e:
            await self.session.rollback()
            raise AttributeDomainError(
                f"Attribute value upsert failed: {e.orig}",
                code="attribute_value_upsert_failed",
                status_code=400,
            ) from e
        await self.session.refresh(row)
        return row

    # ---- delete ------------------------------------------------------------
    async def delete_for_product(self, sku: str, attribute_code: str) -> None:
        attr = await self.attribute_svc.get_definition_by_code(attribute_code)
        stmt = delete(AttributeValue).where(
            AttributeValue.owner_type == "product",
            AttributeValue.owner_id == sku,
            AttributeValue.attribute_id == attr.id,
        )
        result = await self.session.execute(stmt)
        if result.rowcount == 0:
            raise AttributeDomainError(
                f"No value for product={sku} attribute={attribute_code}",
                code="attribute_value_not_found",
                status_code=404,
            )
        await self.session.commit()
