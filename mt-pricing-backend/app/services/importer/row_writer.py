"""ScalarWriter and JsonbWriter for the PIM import pipeline."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

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
            if current != new_val:
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
