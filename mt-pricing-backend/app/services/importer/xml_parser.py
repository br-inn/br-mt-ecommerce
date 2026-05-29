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
    "material", "dn", "pn", "connection", "size",
    "gtin", "intrastat_code", "erp_name", "weight_unit",
    "lifecycle_status", "revision", "data_quality",
    "parent_sku", "display_pair_sku", "video_url", "external_url",
)
_INT_FIELDS: tuple[str, ...] = ("temp_min_c", "temp_max_c")
_DECIMAL_FIELDS: tuple[str, ...] = ("weight", "pressure_max_bar")
_BOOL_FIELDS: tuple[str, ...] = ("is_parent", "is_variant")

_VALIDATABLE = set(_TEXT_FIELDS) | set(_INT_FIELDS) | set(_DECIMAL_FIELDS) | {"sku"}

# Campos que el XML transporta pero que ProductCreate (extra="forbid") NO acepta:
# description_en / marketing_copy_en los consume el applier más tarde (siguen como
# escalares top-level); manufacturing_method se pliega en specs (no es columna).
_NOT_IN_PRODUCT_CREATE = frozenset(
    {"description_en", "marketing_copy_en", "manufacturing_method"}
)


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


def _jsonb_block(
    parent: Element, name: str, int_keys: frozenset[str]
) -> tuple[dict[str, Any], list[str]]:
    """Devuelve (bloque, errores_de_cast). Cast inválido → error de fila, no abort."""
    block = parent.find(f"{{{NS}}}{name}")
    out: dict[str, Any] = {}
    errors: list[str] = []
    if block is None:
        return out, errors
    for child in block:
        key = _tag(child)
        if child.text is None:
            continue
        val = child.text.strip()
        if not val:
            continue
        if key in int_keys:
            try:
                out[key] = int(val)
            except ValueError:
                errors.append(f"{name}.{key}: valor entero inválido '{val}'.")
        else:
            out[key] = val
    return out, errors


_DIM_INT: frozenset[str] = frozenset()
_PKG_INT: frozenset[str] = frozenset({"qty_per_box", "moq_inner_box", "x_pallet"})


def _build_scalars(article: Element) -> tuple[dict[str, Any], list[str]]:
    """Devuelve (payload_escalar, errores_de_cast). Cast inválido → error de fila."""
    payload: dict[str, Any] = {}
    errors: list[str] = []
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
            try:
                payload[f] = int(v)
            except ValueError:
                errors.append(f"{f}: valor entero inválido '{v}'.")
    for f in _DECIMAL_FIELDS:
        v = _text(article, f)
        if v is not None:
            try:
                payload[f] = str(Decimal(v))
            except (ValueError, ArithmeticError):
                errors.append(f"{f}: valor decimal inválido '{v}'.")
    for f in _BOOL_FIELDS:
        v = _text(article, f)
        if v is not None:
            payload[f] = v.lower() == "true"
    dc = article.find(f"{{{NS}}}division_codes")
    if dc is not None:
        codes = [c.text.strip() for c in dc if c.text and c.text.strip()]
        if codes:
            payload["division_codes"] = codes
    return payload, errors


def _validate_row(payload: dict[str, Any]) -> list[str]:
    scalars = {
        k: v
        for k, v in payload.items()
        if k in _VALIDATABLE and k not in _NOT_IN_PRODUCT_CREATE
    }
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
    root_tag = _tag(root)
    if root_tag != "catalog":
        raise XmlParseError(f"Raíz esperada 'catalog', recibida '{root_tag}'.")

    rows: list[ParsedRow] = []
    seen: dict[str, int] = {}
    duplicates: list[str] = []

    for i, article in enumerate(root.findall(f"{{{NS}}}article"), start=1):
        payload, cast_errors = _build_scalars(article)
        dimensions, dim_errors = _jsonb_block(article, "dimensions", _DIM_INT)
        packaging, pkg_errors = _jsonb_block(article, "packaging", _PKG_INT)
        specs, spec_errors = _jsonb_block(article, "specs", frozenset())
        # manufacturing_method no es columna de Product: se pliega en specs JSONB.
        mfg = _text(article, "manufacturing_method")
        if mfg is not None:
            specs["manufacturing_method"] = mfg
        payload["dimensions"] = dimensions
        payload["packaging"] = packaging
        payload["specs"] = specs
        errors = _validate_row(payload)
        errors = cast_errors + dim_errors + pkg_errors + spec_errors + errors
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
