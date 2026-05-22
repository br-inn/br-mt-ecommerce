"""ScalarWriter and JsonbWriter for the PIM import pipeline."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any
from uuid import UUID

from sqlalchemy import func, or_, select, text
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.product import ProductTranslation
from app.db.models.vocabularies import Certification, ProductCertification

# Valid scalar fields on the products table
_PRODUCT_SCALAR_FIELDS: frozenset[str] = frozenset({
    "family", "subfamily", "type", "material", "dn", "pn", "connection",
    "brand", "weight", "weight_unit", "intrastat_code", "erp_name",
    "hs_code", "country_of_origin", "base_uom", "data_quality",
    "bore_mm", "pressure_max_bar", "temp_min_c", "temp_max_c",
    "series", "size", "revision", "external_url", "video_url",
    "gtin", "dimensional_standard",
})
_JSONB_FIELDS: frozenset[str] = frozenset({"dimensions", "packaging", "specs"})


@dataclass
class WriteResult:
    bucket: str  # inserted | updated | no_change | error | locked
    changed_fields: list[str] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)


class ScalarWriter:
    """Writes scalar fields to products. Detects updated/no_change."""

    async def write(
        self,
        session: AsyncSession,
        sku: str,
        existing: Any | None,
        scalars: dict[str, Any],
        locked_fields: set[str],
    ) -> WriteResult:
        changed: list[str] = []
        for field_name, new_val in scalars.items():
            if field_name not in _PRODUCT_SCALAR_FIELDS:
                continue
            if field_name in locked_fields:
                continue
            current = getattr(existing, field_name, None) if existing else None
            if existing is not None and current != new_val:
                setattr(existing, field_name, new_val)
                changed.append(field_name)
        if not changed:
            return WriteResult(bucket="no_change")
        return WriteResult(bucket="updated", changed_fields=changed)


class JsonbWriter:
    """Merges JSONB fields on products. Does not overwrite absent keys."""

    async def write(
        self,
        session: AsyncSession,
        existing: Any,
        jsonb: dict[str, dict[str, Any]],
        locked_fields: set[str],
    ) -> None:
        for bucket, kv in jsonb.items():
            if not kv:
                continue
            if bucket not in _JSONB_FIELDS:
                continue
            current: dict[str, Any] = getattr(existing, bucket, {}) or {}
            merged = {**current, **{
                k: v for k, v in kv.items()
                if f"{bucket}.{k}" not in locked_fields
            }}
            setattr(existing, bucket, merged)


class TranslationWriter:
    """Upsert translations into product_translations."""

    async def write(
        self,
        session: AsyncSession,
        sku: str,
        translations: dict[str, str],
        locked_fields: set[str],
    ) -> None:
        for lang, name in translations.items():
            if f"translations.{lang}" in locked_fields:
                continue
            stmt = (
                pg_insert(ProductTranslation)
                .values(sku=sku, lang=lang, name=name, status="imported")
                .on_conflict_do_update(
                    index_elements=["sku", "lang"],
                    set_={"name": name, "status": "imported", "updated_at": text("now()")},
                )
            )
            await session.execute(stmt)


class CertificationWriter:
    """Get-or-create Certification vocab entries + M:N insert. Additive-only."""

    async def write(
        self,
        session: AsyncSession,
        sku: str,
        certifications: list[str],
    ) -> None:
        names = [n.strip() for n in certifications if n and n.strip()]
        if not names:
            return

        name_to_code: dict[str, str] = {
            n: n.upper().replace(" ", "_") for n in names
        }
        codes = list(name_to_code.values())
        names_lower = [n.lower() for n in names]

        # Single SELECT for all certs at once
        result = await session.execute(
            select(Certification).where(
                or_(
                    Certification.code.in_(codes),
                    func.lower(Certification.name).in_(names_lower),
                )
            )
        )
        existing_certs = result.scalars().all()
        by_code: dict[str, Certification] = {c.code: c for c in existing_certs}
        by_name_lower: dict[str, Certification] = {
            c.name.lower(): c for c in existing_certs
        }

        cert_ids: list[Any] = []
        for cert_name, code in name_to_code.items():
            cert = by_code.get(code) or by_name_lower.get(cert_name.lower())
            if cert is None:
                cert = Certification(code=code, name=cert_name)
                session.add(cert)
                await session.flush()  # need the PK for the M:N row
                by_code[code] = cert
            cert_ids.append(cert.id)

        if cert_ids:
            stmt = (
                pg_insert(ProductCertification)
                .values([
                    {"product_sku": sku, "certification_id": cid}
                    for cid in cert_ids
                ])
                .on_conflict_do_nothing()
            )
            await session.execute(stmt)


class RowWriter:
    """Pipeline that composes the 4 writers for a single ParsedProduct."""

    def __init__(self) -> None:
        self._scalar_writer = ScalarWriter()
        self._jsonb_writer = JsonbWriter()
        self._translation_writer = TranslationWriter()
        self._cert_writer = CertificationWriter()

    async def apply(
        self,
        session: AsyncSession,
        parsed: Any,  # ParsedProduct — avoid circular import
        existing: Any | None,
        locked_fields: set[str],
        actor_id: UUID | None,
    ) -> WriteResult:
        if parsed.is_error_row:
            return WriteResult(bucket="error", errors=parsed.errors)

        scalar_result = await self._scalar_writer.write(
            session=session,
            sku=parsed.sku,
            existing=existing,
            scalars=parsed.scalars,
            locked_fields=locked_fields,
        )
        await self._jsonb_writer.write(
            session=session,
            existing=existing,
            jsonb=parsed.jsonb,
            locked_fields=locked_fields,
        )
        if parsed.has_translations:
            await self._translation_writer.write(
                session=session,
                sku=parsed.sku,
                translations=parsed.translations,
                locked_fields=locked_fields,
            )
        if parsed.has_certifications:
            await self._cert_writer.write(
                session=session,
                sku=parsed.sku,
                certifications=parsed.certifications,
            )
        return scalar_result
