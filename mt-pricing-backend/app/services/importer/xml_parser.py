"""Parser XML de la plantilla estándar de artículos → ParseResult.

Produce el mismo ParseResult/ParsedRow que el parser xlsx para enchufarse antes
del differ. Validación tolerante por fila: errores por <article> van a
ParsedRow.errors (no abortan el archivo). Errores de archivo (XML malformado,
raíz != catalog, entidades inseguras) se lanzan como XmlParseError.
"""
from __future__ import annotations

from decimal import Decimal
from typing import Any, BinaryIO
from xml.etree.ElementTree import Element, ParseError  # solo tipos + excepción

import defusedxml.ElementTree as DET  # parseo seguro (XXE/billion-laughs)
from defusedxml.common import DefusedXmlException
from pydantic import ValidationError

from app.schemas.products import ProductCreate
from app.services.importer.parser import ParsedRow, ParseResult

NS = "https://mtme-api/schemas/articulos/v1"

_TEXT_FIELDS: tuple[str, ...] = (
    "name_en", "description_en", "marketing_copy_en",
    "family", "subfamily", "type", "series", "brand",
    "material", "dn", "pn", "connection", "size", "manufacturing_method",
    "gtin", "intrastat_code", "erp_name", "weight_unit",
    "lifecycle_status", "revision", "data_quality",
    "parent_sku", "display_pair_sku", "video_url", "external_url",
)
_INT_FIELDS: tuple[str, ...] = ("temp_min_c", "temp_max_c")
_DECIMAL_FIELDS: tuple[str, ...] = ("weight", "pressure_max_bar")
_BOOL_FIELDS: tuple[str, ...] = ("is_parent", "is_variant")

_VALIDATABLE = set(_TEXT_FIELDS) | set(_INT_FIELDS) | set(_DECIMAL_FIELDS) | {"sku"}


class XmlParseError(ValueError):
    """Error de archivo (malformado / raíz incorrecta / inseguro) — aborta el parse."""


def _tag(elem: Element) -> str:
    t = elem.tag
    return t.split("}", 1)[1] if "}" in t else t


def _text(parent: Element, name: str) -> str | None:
    child = parent.find(f"{{{NS}}}{name}")
    if child is None or child.text is None:
        return None
    s = child.text.strip()
    return s or None


def _jsonb_block(parent: Element, name: str, int_keys: frozenset[str]) -> dict[str, Any]:
    block = parent.find(f"{{{NS}}}{name}")
    out: dict[str, Any] = {}
    if block is None:
        return out
    for child in block:
        key = _tag(child)
        if child.text is None:
            continue
        val = child.text.strip()
        if not val:
            continue
        out[key] = int(float(val)) if key in int_keys else val
    return out


_DIM_INT: frozenset[str] = frozenset()
_PKG_INT: frozenset[str] = frozenset({"qty_per_box", "moq_inner_box", "x_pallet"})


def _build_scalars(article: Element) -> dict[str, Any]:
    payload: dict[str, Any] = {}
    sku = _text(article, "sku")
    if sku is not None:
        payload["sku"] = sku
    for f in _TEXT_FIELDS:
        v = _text(article, f)
        if v is not None:
            payload[f] = v
    for f in _INT_FIELDS:
        v = _text(article, f)
        if v is not None:
            payload[f] = int(float(v))
    for f in _DECIMAL_FIELDS:
        v = _text(article, f)
        if v is not None:
            payload[f] = str(Decimal(v))
    for f in _BOOL_FIELDS:
        v = _text(article, f)
        if v is not None:
            payload[f] = v.lower() == "true"
    dc = article.find(f"{{{NS}}}division_codes")
    if dc is not None:
        codes = [c.text.strip() for c in dc if c.text and c.text.strip()]
        if codes:
            payload["division_codes"] = codes
    return payload


def _validate_row(payload: dict[str, Any]) -> list[str]:
    scalars = {k: v for k, v in payload.items() if k in _VALIDATABLE}
    try:
        ProductCreate(**scalars)  # type: ignore[arg-type]
    except ValidationError as exc:
        return [f"{e['loc'][0] if e['loc'] else '?'}: {e['msg']}" for e in exc.errors()]
    return []


def parse_xml_stream(source: bytes | BinaryIO) -> ParseResult:
    data = source if isinstance(source, bytes) else source.read()
    try:
        root = DET.fromstring(data)
    except (ParseError, DefusedXmlException) as exc:
        raise XmlParseError(f"XML inválido o inseguro: {exc}") from exc
    if _tag(root) != "catalog":
        raise XmlParseError(f"Raíz esperada 'catalog', recibida '{_tag(root)}'.")

    rows: list[ParsedRow] = []
    seen: dict[str, int] = {}
    duplicates: list[str] = []

    for i, article in enumerate(root.findall(f"{{{NS}}}article"), start=1):
        payload = _build_scalars(article)
        payload["dimensions"] = _jsonb_block(article, "dimensions", _DIM_INT)
        payload["packaging"] = _jsonb_block(article, "packaging", _PKG_INT)
        payload["specs"] = _jsonb_block(article, "specs", frozenset())
        errors = _validate_row(payload)
        sku = payload.get("sku")
        if sku is not None:
            if sku in seen:
                duplicates.append(sku)
                errors.append(
                    f"SKU duplicado en archivo (primera ocurrencia row {seen[sku]})."
                )
            else:
                seen[sku] = i
        rows.append(ParsedRow(row_index=i, sku=sku, payload=payload, errors=errors))

    return ParseResult(
        rows=rows, header_errors=[], total_data_rows=len(rows), duplicate_skus=duplicates
    )
