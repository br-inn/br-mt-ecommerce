"""Etapa 1 — Query Builder.

Traduce un SKU MT a un set de queries multi-canal / multi-idioma siguiendo la
estrategia descrita en ``mt-product-matching-pipeline-detail.md`` §3.

Generamos para cada SKU:
- Brand + spec EN (si hay brand)
- Spec técnica EN
- Functional EN (fallback)
- Spec AR (mercado UAE)
- Norm-based (cuando hay norma)
- Part-number (sku como término exacto)

Sprint 3 foundation: las queries se devuelven como objetos ``Query``; los
adapters stubs las ignoran (devuelven canned data) — la utilidad real será
cuando se conecten Bright Data + Playwright.
"""

from __future__ import annotations

import re
from collections.abc import Iterable
from typing import Any

from app.services.matching.ports import SUPPORTED_CHANNELS, Query

# DN métrico → pulgadas (extracto canónico §3.3 del pipeline doc).
DN_TO_INCH: dict[int, str] = {
    8: '1/4"',
    10: '3/8"',
    15: '1/2"',
    20: '3/4"',
    25: '1"',
    32: '1-1/4"',
    40: '1-1/2"',
    50: '2"',
    65: '2-1/2"',
    80: '3"',
    100: '4"',
    125: '5"',
    150: '6"',
}

# Familia → término funcional canónico EN (broad fallback).
FAMILY_FUNCTIONAL_EN: dict[str, str] = {
    "ball_valve": "ball valve plumbing",
    "gate_valve": "gate valve",
    "globe_valve": "globe valve",
    "check_valve": "check valve",
    "valves_ball": "ball valve plumbing",
    "fittings": "pipe fitting",
}

# Familia → término AR canónico.
FAMILY_AR: dict[str, str] = {
    "ball_valve": "صمام كروي",
    "valves_ball": "صمام كروي",
    "gate_valve": "صمام بوابة",
    "globe_valve": "صمام كروي عالمي",
    "check_valve": "صمام عدم رجوع",
    "fittings": "وصلات أنابيب",
}

# Materiales canónicos → palabra clave usada en queries EN.
MATERIAL_TO_EN: dict[str, str] = {
    "brass": "brass",
    "brass_CW617N": "brass",
    "brass_CW602N": "brass",
    "ss316": "stainless steel 316",
    "ss304": "stainless steel 304",
    "pvc": "PVC",
    "cpvc": "CPVC",
    "cast_iron": "cast iron",
}

_DN_NUMERIC_RE = re.compile(r"DN\s*(\d{1,4})", re.IGNORECASE)
_DN_INT_RE = re.compile(r"^\s*(\d{1,4})\s*$")


def _dn_to_int(dn_value: Any) -> int | None:
    """Acepta ``"DN50"``, ``"50"``, ``50`` y devuelve int."""
    if dn_value is None:
        return None
    if isinstance(dn_value, int):
        return dn_value
    text = str(dn_value).strip()
    m = _DN_NUMERIC_RE.search(text)
    if m:
        return int(m.group(1))
    m = _DN_INT_RE.match(text)
    if m:
        return int(m.group(1))
    return None


def _normalize_material(material: str | None) -> str | None:
    if material is None:
        return None
    key = material.strip()
    if not key:
        return None
    return MATERIAL_TO_EN.get(key, MATERIAL_TO_EN.get(key.lower(), key))


class QueryBuilder:
    """Construye queries multi-fuente para un SKU MT.

    Uso::

        qb = QueryBuilder()
        queries = qb.build_for_sku({
            "sku": "MTBR4001050",
            "name_en": "Brass ball valve DN50 PN25 BSP",
            "family": "ball_valve",
            "dn": "DN50",
            "pn": "PN25",
            "material": "brass",
            "brand": "Pegler",
        })
    """

    def __init__(self, channels: Iterable[str] | None = None) -> None:
        self.channels: tuple[str, ...] = tuple(channels) if channels else SUPPORTED_CHANNELS

    # ----------------------------------------------------------------------
    # API pública
    # ----------------------------------------------------------------------
    def build_for_sku(self, sku: dict[str, Any]) -> list[Query]:
        """Genera queries para todos los canales soportados.

        El SKU dict acepta tanto el shape de ``Product`` (ORM via
        ``Product.__dict__``) como un dict construido a mano.
        """
        queries: list[Query] = []
        for channel in self.channels:
            queries.extend(self._build_per_channel(sku, channel))
        return queries

    # ----------------------------------------------------------------------
    # Internals
    # ----------------------------------------------------------------------
    def _build_per_channel(self, sku: dict[str, Any], channel: str) -> list[Query]:
        out: list[Query] = []

        sku_code = str(sku.get("sku") or sku.get("codigo") or "").strip()
        family = (sku.get("family") or "").strip()
        material_en = _normalize_material(sku.get("material"))
        brand = (sku.get("brand") or "").strip() or None
        dn_int = _dn_to_int(sku.get("dn"))
        pn_str = str(sku.get("pn") or "").strip()
        pn_clean = pn_str.replace("PN", "").strip() if pn_str else ""
        connection = (sku.get("connection") or "").strip()
        norma = (sku.get("norma") or "").strip()
        name_en = (sku.get("name_en") or "").strip()

        inch = DN_TO_INCH.get(dn_int) if dn_int is not None else None

        # 1. Brand + spec EN
        if brand and (material_en or family):
            tokens = [
                f'"{brand}"',
                material_en or "",
                FAMILY_FUNCTIONAL_EN.get(family, family.replace("_", " ")),
                f"DN{dn_int}" if dn_int else "",
                inch or "",
                connection,
            ]
            out.append(
                Query(
                    text=_join_tokens(tokens),
                    source=channel,
                    lang="en",
                    type="brand_spec",
                )
            )

        # 2. Spec técnica EN
        tokens = [
            material_en or "",
            FAMILY_FUNCTIONAL_EN.get(family, family.replace("_", " ")),
            inch or (f"DN{dn_int}" if dn_int else ""),
            connection,
            f"PN{pn_clean}" if pn_clean else "",
        ]
        spec_text = _join_tokens(tokens)
        if spec_text:
            out.append(
                Query(
                    text=spec_text,
                    source=channel,
                    lang="en",
                    type="spec",
                )
            )

        # 3. Functional EN (fallback amplio)
        if family in FAMILY_FUNCTIONAL_EN:
            out.append(
                Query(
                    text=FAMILY_FUNCTIONAL_EN[family],
                    source=channel,
                    lang="en",
                    type="functional",
                )
            )

        # 4. Spec AR (especialmente útil en Noon)
        ar_term = FAMILY_AR.get(family)
        if ar_term:
            ar_tokens = [ar_term, inch or (f"DN{dn_int}" if dn_int else "")]
            out.append(
                Query(
                    text=" ".join(t for t in ar_tokens if t).strip(),
                    source=channel,
                    lang="ar",
                    type="spec_ar",
                )
            )

        # 5. Norm-based
        if norma:
            tokens = [
                norma,
                material_en or "",
                FAMILY_FUNCTIONAL_EN.get(family, family.replace("_", " ")),
                inch or (f"DN{dn_int}" if dn_int else ""),
            ]
            out.append(
                Query(
                    text=_join_tokens(tokens),
                    source=channel,
                    lang="en",
                    type="norm",
                )
            )

        # 6. Part number (SKU code)
        if sku_code:
            text = f"{brand} {sku_code}".strip() if brand else sku_code
            out.append(
                Query(
                    text=text,
                    source=channel,
                    lang="en",
                    type="part_number",
                )
            )

        # Si no se generó nada (datos ultrapobres) caemos al name_en como
        # último recurso para no devolver lista vacía.
        if not out and name_en:
            out.append(
                Query(text=name_en, source=channel, lang="en", type="raw_name")
            )
        return out


def _join_tokens(tokens: Iterable[str]) -> str:
    """Une tokens separando por espacios, dejando fuera los vacíos y
    colapsando whitespace múltiple.
    """
    cleaned = [t.strip() for t in tokens if t and t.strip()]
    if not cleaned:
        return ""
    joined = " ".join(cleaned)
    return re.sub(r"\s+", " ", joined).strip()


def build_queries(sku: dict[str, Any], channels: Iterable[str] | None = None) -> list[Query]:
    """Functional helper sobre :class:`QueryBuilder`."""
    return QueryBuilder(channels).build_for_sku(sku)
