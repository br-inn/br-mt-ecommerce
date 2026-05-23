"""Aplica una receta de extracción a un documento HTML usando selectores CSS.

F1 soporta selectores CSS (via selectolax). XPath queda para una fase posterior.
"""

from __future__ import annotations

import re
from typing import Any

from selectolax.parser import HTMLParser

from app.services.scraper.recipe_transforms import apply_transform

_CURRENCY_RE = re.compile(r"[^0-9.]")
_TRUTHY = {"true", "1", "yes", "in stock", "available", "disponible"}


def coerce_type(value: str | None, type_: str) -> Any:
    """Convierte un valor de texto al tipo canónico. Devuelve None si no puede."""
    if value is None:
        return None
    if type_ == "str":
        return value
    text_ = value.strip()
    try:
        if type_ == "float":
            return float(text_)
        if type_ == "int":
            return int(float(text_))
        if type_ == "currency":
            cleaned = _CURRENCY_RE.sub("", text_)
            return float(cleaned) if cleaned else None
        if type_ == "bool":
            return text_.lower() in _TRUTHY
    except (ValueError, TypeError):
        return None
    return value


def _extract_field(node: Any, field: dict[str, Any]) -> Any:
    target = node.css_first(field["selector"])
    if target is None:
        return None
    extract = field.get("extract", "text")
    if extract == "html":
        raw = target.html
    elif extract.startswith("attr:"):
        raw = target.attributes.get(extract.split(":", 1)[1])
    else:
        raw = target.text(strip=True)
    if raw is None:
        return None
    raw = apply_transform(field.get("transform"), raw)
    return coerce_type(raw, field.get("type", "str"))


def extract_records(html: str, recipe: dict[str, Any]) -> list[dict[str, Any]]:
    """Extrae registros de un HTML según la receta.

    Con ``list_item_selector`` produce un registro por nodo coincidente; sin él,
    un único registro tomado del documento entero. Cada registro es un dict
    ``{field_name: valor_o_None}``.
    """
    tree = HTMLParser(html)
    fields = recipe.get("fields", [])
    list_sel = recipe.get("list_item_selector")
    if list_sel:
        items = tree.css(list_sel)
    else:
        root = tree.body if tree.body is not None else tree.root
        items = [root] if root is not None else []
    records: list[dict[str, Any]] = []
    for item in items:
        records.append({f["name"]: _extract_field(item, f) for f in fields})
    return records


def field_results(records: list[dict[str, Any]], recipe: dict[str, Any]) -> dict[str, str]:
    """pass/fail por field — 'pass' si el field es no-nulo/no-vacío en >=1 registro."""
    results: dict[str, str] = {}
    for f in recipe.get("fields", []):
        name = f["name"]
        ok = any(r.get(name) not in (None, "") for r in records)
        results[name] = "pass" if ok else "fail"
    return results
