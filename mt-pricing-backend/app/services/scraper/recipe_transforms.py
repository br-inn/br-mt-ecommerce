"""Motor de transforms declarativos para recetas de scraper.

Cada transform es una operación pura y segura sobre un valor de texto extraído.
El escape hatch de snippets generados por LLM (híbrido B) NO está aquí — llega
en una fase posterior con su sandbox dedicado.
"""

from __future__ import annotations

import re
from typing import Any

_NUMERIC_RE = re.compile(r"[^0-9.\-]")


def _to_number(value: str) -> float:
    return float(_NUMERIC_RE.sub("", value.replace(",", "")))


def apply_transform(transform: dict[str, Any] | None, value: str) -> str:
    """Aplica un transform declarativo a un valor de texto. None = identidad."""
    if transform is None:
        return value
    op = transform.get("op")
    if op == "regex_capture":
        match = re.search(transform["pattern"], value)
        if match is None:
            return ""
        return match.group(1) if match.groups() else match.group(0)
    if op == "strip_currency":
        return _NUMERIC_RE.sub("", value.replace(",", ""))
    if op == "replace":
        return value.replace(transform["find"], transform.get("replace_with", ""))
    if op == "map_values":
        return transform.get("mapping", {}).get(value, value)
    if op == "unit_factor":
        try:
            return str(_to_number(value) * float(transform["factor"]))
        except (ValueError, TypeError):
            return ""
    raise ValueError(f"Unknown transform op: {op!r}")
