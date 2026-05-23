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

# Familia slug EN → término funcional canónico EN.
# NOTE: "industrial" anchors Amazon results in the PVF segment, avoiding
# consumer household products that dominate when the term is omitted.
FAMILY_FUNCTIONAL_EN: dict[str, str] = {
    "ball_valve": "ball valve industrial",
    "gate_valve": "gate valve industrial",
    "globe_valve": "globe valve industrial",
    "check_valve": "check valve industrial",
    "valves_ball": "ball valve industrial",
    "fittings": "pipe fitting industrial",
    "butterfly_valve": "butterfly valve industrial",
    "strainer": "Y strainer industrial",
    "pressure_gauge": "pressure gauge industrial",
}

# Spanish DB family/subfamily names → English search term.
# The MT catalog stores categories in Spanish; these mappings let QueryBuilder
# produce useful Amazon queries without requiring English slugs.
FAMILY_ES_TO_EN: dict[str, str] = {
    "HIDROSANITARIO": "ball valve industrial",
    "VALVULAS": "valve industrial",
    "VÁLVULAS": "valve industrial",
    "ACCESORIOS": "pipe fitting industrial",
    "TUBERIA": "pipe industrial",
    "TUBERÍAS": "pipe industrial",
    "BRIDAS": "flange industrial",
    "FILTROS": "strainer industrial",
    "MANOMETROS": "pressure gauge industrial",
    "MANÓMETROS": "pressure gauge industrial",
    "HIDRANTES": "fire hydrant industrial",
}

# Familia → término AR canónico.
FAMILY_AR: dict[str, str] = {
    "ball_valve": "صمام كروي",
    "valves_ball": "صمام كروي",
    "gate_valve": "صمام بوابة",
    "globe_valve": "صمام كروي عالمي",
    "check_valve": "صمام عدم رجوع",
    "fittings": "وصلات أنابيب",
    "HIDROSANITARIO": "صمام كروي",
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
    "carbon_steel": "carbon steel",
    "ductile_iron": "ductile iron",
    "bronze": "bronze",
}

# Brands that are house/OEM labels and will not appear on Amazon.
# Searching for these as brand anchors produces zero or misleading results.
_HOUSE_BRANDS: frozenset[str] = frozenset({"mt", "mitsa", "mt technologies", "m.t."})

# Core product type keywords extracted from the `type` DB field.
# Used to derive a family search term when family slug lookup fails.
_TYPE_TERM_MAP: tuple[tuple[str, str], ...] = (
    ("ball valve", "ball valve industrial"),
    ("gate valve", "gate valve industrial"),
    ("globe valve", "globe valve industrial"),
    ("check valve", "check valve industrial"),
    ("butterfly valve", "butterfly valve industrial"),
    ("y strainer", "Y strainer industrial"),
    ("strainer", "strainer industrial"),
    ("pressure gauge", "pressure gauge industrial"),
    ("pipe fitting", "pipe fitting industrial"),
    ("elbow", "pipe elbow industrial"),
    ("tee fitting", "pipe tee industrial"),
    ("nipple", "pipe nipple industrial"),
    ("coupling", "pipe coupling industrial"),
    ("union", "pipe union industrial"),
    ("flange", "flange industrial"),
    ("reducer", "pipe reducer industrial"),
    ("valve", "valve industrial"),
    ("fitting", "pipe fitting industrial"),
)

_DN_NUMERIC_RE = re.compile(r"DN\s*(\d{1,4})", re.IGNORECASE)
_DN_INT_RE = re.compile(r"^\s*(\d{1,4})\s*$")
_SPEC_TOKEN_RE = re.compile(
    r"\b(DN\d+|PN\d+|M-F|F-F|M-M|[12]-WAY|BSP[T]?|NPT[F]?|[Gg]\d+|"
    r"Rc\d*|FLANGED|THREADED|WAFER|WELD|SCREWED)\b",
    re.IGNORECASE,
)


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


def _extract_size_token(dn_value: Any) -> str:
    """Return an Amazon-friendly size token from the `dn` DB field.

    The MT catalog stores sizes in two formats:
    - Inch format already: ``'1/2"'``, ``'3/4"'``, ``'1"'``, ``'1-1/2"'``
    - Metric DN format:    ``'DN50'``, ``50`` (integer)

    Inch values are returned as-is (normalized). DN values are converted via
    ``DN_TO_INCH``.  Unknown formats are returned as-is so information is never
    silently lost.
    """
    if dn_value is None:
        return ""
    text = str(dn_value).strip()
    if not text:
        return ""

    # Already inch format: contains a quote character or fraction like '1/2'
    if any(c in text for c in ('"', "”", "’")) or re.search(r"\d/\d", text):
        clean = text.replace("”", '"').replace("’", '"')
        if not clean.endswith('"'):
            clean = clean.rstrip("\"'") + '"'
        return clean

    # DN integer format → convert to inches
    dn_int = _dn_to_int(text)
    if dn_int is not None:
        return DN_TO_INCH.get(dn_int, f"DN{dn_int}")

    return text


def _normalize_material(material: str | None) -> str | None:
    if material is None:
        return None
    key = material.strip()
    if not key:
        return None
    return MATERIAL_TO_EN.get(key, MATERIAL_TO_EN.get(key.lower(), key))


def _is_house_brand(brand: str | None) -> bool:
    """True for MT own-brand labels that won't appear on Amazon."""
    return (brand or "").strip().lower() in _HOUSE_BRANDS


def _clean_product_type(product_type: str) -> str:
    """Strip spec tokens from the `type` field to get the core product noun.

    ``'Ball Valve M-F PN30'`` → ``'ball valve'``
    ``'Gate Valve BSP PN16'`` → ``'gate valve'``
    """
    if not product_type:
        return ""
    clean = _SPEC_TOKEN_RE.sub("", product_type)
    clean = re.sub(r"\s+", " ", clean).strip().lower()
    return clean


_ERP_NOISE_RE = re.compile(r"\berg\.\b", re.IGNORECASE)


def _clean_erp_name(name: str) -> str:
    """Clean ERP name for use as an Amazon search query.

    Removes abbreviation noise (e.g. 'erg.') while preserving all spec
    keywords (size, PN, handle color, material) that help Amazon find the
    right product in the Industrial & Scientific department.
    """
    if not name:
        return ""
    clean = _ERP_NOISE_RE.sub("", name)
    return re.sub(r"\s+", " ", clean).strip()


def _family_term_from_type(product_type: str) -> str:
    """Derive a family search term from the English `type` field.

    Uses ``_TYPE_TERM_MAP`` to find the longest matching substring so that
    ``'Ball Valve M-F PN30'`` → ``'ball valve industrial'``.
    """
    if not product_type:
        return ""
    lower = product_type.lower()
    for keyword, term in _TYPE_TERM_MAP:
        if keyword in lower:
            return term
    return ""


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

        # House brands (e.g. "MT") are unknown on Amazon — omit from queries.
        raw_brand = (sku.get("brand") or "").strip()
        brand: str | None = None if _is_house_brand(raw_brand) else (raw_brand or None)

        pn_str = str(sku.get("pn") or "").strip()
        pn_clean = pn_str.replace("PN", "").strip() if pn_str else ""
        norma = (sku.get("norma") or "").strip()

        # model-level fields — more precise than SKU-level when present
        model_thread_standard = (sku.get("model_thread_standard") or "").strip()
        model_connection_type = (sku.get("model_connection_type") or "").strip()

        # Size: handles both '1/2"' (inch already in DB) and 'DN50' (metric).
        size_token = _extract_size_token(sku.get("dn"))

        # ERP name is the richest English description available (e.g.
        # "M-F Ball Valve PN30 red stainless steel handle 1/2"").
        erp_name_raw = (sku.get("erp_name") or "").strip()
        erp_name = _clean_erp_name(erp_name_raw)

        # `product_type` (e.g. "Ball Valve M-F PN30") from the ORM `type` field.
        product_type = (sku.get("product_type") or "").strip()
        name_en = erp_name or product_type or (sku.get("name_en") or "").strip()

        # Resolve family search term: slug EN → Spanish DB name → type field.
        family_term = (
            FAMILY_FUNCTIONAL_EN.get(family)
            or FAMILY_FUNCTIONAL_EN.get(family.lower())
            or FAMILY_ES_TO_EN.get(family.upper())
            or _family_term_from_type(product_type or erp_name)
        )

        # 1. ERP name query — highest priority: the full English product name from
        #    the ERP is the most descriptive and should be tried first on Amazon.
        if erp_name:
            out.append(Query(text=erp_name, source=channel, lang="en", type="erp_name"))

        # 2. Type-spec: English `type` field + material + size (structured fallback).
        if product_type and (material_en or size_token):
            type_noun = _clean_product_type(product_type)
            tokens = [
                material_en or "",
                type_noun or family_term or "",
                size_token,
                f"PN{pn_clean}" if pn_clean else "",
            ]
            out.append(
                Query(text=_join_tokens(tokens), source=channel, lang="en", type="type_spec")
            )

        # 3. Brand + spec (only for recognized 3rd-party brands on Amazon)
        if brand and (material_en or family_term):
            tokens = [
                f'"{brand}"',
                material_en or "",
                family_term or "",
                size_token,
            ]
            out.append(
                Query(text=_join_tokens(tokens), source=channel, lang="en", type="brand_spec")
            )

        # 4. Spec técnica EN — material + category + size + thread + PN
        # model_thread_standard is more reliable than raw connection field
        # (e.g. "BSP" vs "BSP M-F PN30" which would add noise to the query)
        _conn_parts = (sku.get("connection") or "").strip().split()
        thread_token = model_thread_standard or (_conn_parts[0] if _conn_parts else "")
        tokens = [
            material_en or "",
            family_term or "",
            size_token,
            thread_token or "",
            f"PN{pn_clean}" if pn_clean else "",
        ]
        spec_text = _join_tokens(tokens)
        if spec_text:
            out.append(Query(text=spec_text, source=channel, lang="en", type="spec"))

        # 5. Functional EN — category + size (broad fallback)
        if family_term:
            func_tokens = [family_term, size_token]
            out.append(
                Query(text=_join_tokens(func_tokens), source=channel, lang="en", type="functional")
            )

        # 6. Spec AR — ONLY for Noon UAE (Arabic is irrelevant on Amazon UAE).
        if channel == "noon_uae":
            ar_term = (
                FAMILY_AR.get(family)
                or FAMILY_AR.get(family.upper())
                or FAMILY_AR.get(family.lower())
            )
            if ar_term:
                ar_tokens = [ar_term, size_token]
                out.append(
                    Query(
                        text=" ".join(t for t in ar_tokens if t).strip(),
                        source=channel,
                        lang="ar",
                        type="spec_ar",
                    )
                )

        # 7. Norm-based (e.g. DIN259, ISO228)
        if norma:
            tokens = [norma, material_en or "", family_term or "", size_token]
            out.append(Query(text=_join_tokens(tokens), source=channel, lang="en", type="norm"))

        # 8. EAN barcode — exact product match
        ean = str((sku.get("packaging") or {}).get("ean_individual") or "").strip()
        if len(ean) >= 12:
            out.append(Query(text=ean, source=channel, lang="en", type="ean"))

        # 9. Part number (SKU code)
        if sku_code:
            pn_text = f"{brand} {sku_code}".strip() if brand else sku_code
            out.append(Query(text=pn_text, source=channel, lang="en", type="part_number"))

        # Fallback when all data is missing
        if not out and name_en:
            out.append(Query(text=name_en, source=channel, lang="en", type="raw_name"))

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


# ---------------------------------------------------------------------------
# Tier-based query builder (migrado de MT_Pricing_Run_Kit/src/search_builder_v4.py)
# ---------------------------------------------------------------------------


def _dedupe_words(s: str) -> str:
    """Remove consecutive and globally-duplicate words, preserving order."""
    seen_lower: set[str] = set()
    final: list[str] = []
    for word in s.split():
        wl = word.lower()
        if wl not in seen_lower:
            final.append(word)
            seen_lower.add(wl)
    return " ".join(final)


def _norm_size(size_in: str) -> str:
    """Normalize '1 1/2"' → '1-1/2' for Amazon search queries."""
    if not size_in:
        return ""
    s = size_in.strip().replace('"', "").replace("“", "").strip()
    return re.sub(r"\s+", "-", s)


def _category_singular(cat: str) -> str:
    """Convert 'Ball Valves' → 'ball valve' (performs better on Amazon)."""
    if not cat:
        return ""
    s = re.sub(r"\s+", " ", cat.strip().lower())
    if s.endswith("ies"):
        s = s[:-3] + "y"
    elif s.endswith("s"):
        s = s[:-1]
    return s


def _tier_material(product_data: dict[str, Any]) -> str:
    """Pick the most specific material keyword available."""
    ficha = product_data.get("ficha") or {}
    web = product_data.get("web") or {}
    # alloy codes (CW617N, SS316…) are the most precise
    alloy_codes = ficha.get("alloy_codes") or []
    if alloy_codes:
        return alloy_codes[0]
    mats = ficha.get("materials") or {}
    if isinstance(mats, dict) and mats.get("body"):
        return str(mats["body"][0]).replace("_", " ")
    if web.get("material"):
        return str(web["material"])
    # fall back to the flat 'material' field used in build_for_sku
    return _normalize_material(product_data.get("material")) or ""


def _tier_end_word(product_data: dict[str, Any]) -> str:
    ficha = product_data.get("ficha") or {}
    name_en = (product_data.get("nombre_en") or product_data.get("name_en") or "").lower()
    for kw in ("flanged", "threaded", "wafer", "lugged", "lug", "weld", "press-fit", "compression"):
        if kw in name_en:
            return kw
    end_conn = ficha.get("end_connection") or []
    if end_conn:
        return str(end_conn[0]).replace("_", " ")
    return ""


def _tier_pn_value(product_data: dict[str, Any]) -> int | None:
    name_en = product_data.get("nombre_en") or product_data.get("name_en") or ""
    m = re.search(r"\bPN[- ]?(\d{2,3})\b", name_en, re.IGNORECASE)
    if m:
        return int(m.group(1))
    ficha = product_data.get("ficha") or {}
    pn = ficha.get("pressure_pn")
    return int(pn) if pn is not None else None


def build_tiers(
    product_data: dict[str, Any],
    *,
    include_competitor_anchor: bool = True,
) -> list[tuple[str, str]]:
    """Build ordered tier queries for a product, compatible with search_builder_v4 tiers.

    Args:
        product_data: Dict representing one product/SKU. Supports both the
            flat shape used by :meth:`QueryBuilder.build_for_sku` *and* the
            nested ``ficha``/``excel``/``web`` shape from the Run Kit.
        include_competitor_anchor: When True, T0 (competitor-anchored)
            queries are prepended when data is available.

    Returns:
        Ordered list of ``(tier_id, query_text)`` pairs. Empty tiers are
        omitted so the caller can stop at the first tier with a good match.
    """
    out: list[tuple[str, str]] = []
    web = product_data.get("web") or {}
    excel = product_data.get("excel") or {}

    # ── T0: competitor anchor ────────────────────────────────────────────────
    # Only built when caller has a competitors list embedded in product_data.
    if include_competitor_anchor:
        cat = web.get("category", "")
        cat_singular = _category_singular(cat)
        size_in = web.get("size_in", "") or str(excel.get("medidas_clean", "")).replace('"', "")
        web_mat = web.get("material", "")
        mat_t0 = web_mat.replace("_", " ") if web_mat else ""
        for comp in product_data.get("competitors") or []:
            cat_list = comp.get("category_match") or []
            if not any(c.lower() == cat.lower() or c.lower() in cat.lower() for c in cat_list):
                continue
            parts = [comp["brand_canonical"].lower(), cat_singular]
            if mat_t0:
                parts.append(mat_t0)
            if size_in:
                parts.append(_norm_size(size_in))
            q = _dedupe_words(" ".join(p for p in parts if p))
            if q:
                out.append((f"T0_{comp['brand_canonical']}", q))

    # ── T1: EAN / barcode ────────────────────────────────────────────────────
    ean = str(excel.get("ean_individual") or "").strip()
    if len(ean) >= 12:
        out.append(("T1_ean", ean))

    # ── T2: technical — material + category + size + end-connection + PN ─────
    mat = _tier_material(product_data)
    cat = _category_singular(web.get("category", ""))
    size_in = web.get("size_in", "") or str(excel.get("medidas_clean", ""))
    size_dn = web.get("size_dn", "")
    ends = _tier_end_word(product_data)
    pn = _tier_pn_value(product_data)

    t2_parts = [p for p in [mat, cat, ends, _norm_size(size_in), size_dn] if p]
    if pn:
        t2_parts.append(f"PN{pn}")
    t2 = _dedupe_words(" ".join(t2_parts).strip())
    if t2:
        out.append(("T2_technical", t2))

    # ── T3: functional — 'about' text keywords + size ────────────────────────
    about = web.get("about", "")
    if about:
        after_range = re.split(r"range\.\s*", about, maxsplit=1)
        body = after_range[-1] if len(after_range) > 1 else about
        first_sent = body.split(".")[0]
        kws = re.findall(r"[A-Za-z][A-Za-z0-9-]{2,}", first_sent)
        _stop = {"with", "and", "for", "the", "this", "that", "mt", "are", "have", "used"}
        keep = [k for k in kws if k.lower() not in _stop][:6]
        if size_in:
            keep.append(_norm_size(size_in))
        t3 = " ".join(keep).lower().strip()
        if t3:
            out.append(("T3_functional", t3))

    # ── T4: product name from excel ───────────────────────────────────────────
    product_name = str(excel.get("product_name") or "").strip()
    if product_name:
        out.append(("T4_product_name", product_name))

    # ── T5: raw EN name (fallback) ────────────────────────────────────────────
    nombre_en = str(product_data.get("nombre_en") or product_data.get("name_en") or "").strip()
    if nombre_en:
        out.append(("T5_fallback", nombre_en))

    return out
