"""Detecta series desde texto del PDF y filename; genera SKUs candidatos."""

from __future__ import annotations

import re

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.product import Product
from app.schemas.ficha_enrich import (
    FichaExtractionResult,
    FieldDiff,
    SeriesGroupResult,
    SkuDiffResult,
)

_IMPERIAL_TO_DN: dict[str, int] = {
    '1/8"': 6,
    "1/8": 6,
    '1/4"': 8,
    "1/4": 8,
    '3/8"': 10,
    "3/8": 10,
    '1/2"': 15,
    "1/2": 15,
    '3/4"': 20,
    "3/4": 20,
    '1"': 25,
    "1": 25,
    '1-1/4"': 32,
    '1 1/4"': 32,
    "1-1/4": 32,
    "1 1/4": 32,
    '1-1/2"': 40,
    '1 1/2"': 40,
    "1-1/2": 40,
    "1 1/2": 40,
    '2"': 50,
    "2": 50,
    '2-1/2"': 65,
    '2 1/2"': 65,
    "2-1/2": 65,
    '3"': 80,
    "3": 80,
    '4"': 100,
    "4": 100,
}

_DN_TO_SIZE: dict[int, str] = {
    6: '1/8"',
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
}


def dn_to_size(dn: int | str | None) -> str | None:
    """Return canonical inch size string for a DN value (e.g. 15 → '1/2"')."""
    if dn is None:
        return None
    try:
        return _DN_TO_SIZE.get(int(dn))
    except (ValueError, TypeError):
        return None


# Detecta pares de series "NNNN / NNNNN" en cabeceras de página del PDF.
_SERIES_PAIR_RE = re.compile(r"\b(\d{4,5})\s*/\s*(\d{4,6})\b")


def extract_series_prefix(filename: str) -> str | None:
    """Extrae prefijo de serie del filename: 'MTFT_4097.pdf' → '4097'."""
    match = re.search(r"MTFT[_\-]?(\d+)", filename, re.IGNORECASE)
    return match.group(1) if match else None


def _is_color_variant(base: str, candidate: str) -> bool:
    """True si candidate es variante de color de base (patron base + '2', una cifra más)."""
    return (
        len(candidate) == len(base) + 1 and candidate.startswith(base) and candidate.endswith("2")
    )


def extract_all_series_from_text(text: str) -> list[tuple[str, str | None]]:
    """
    Escanea el texto del PDF para detectar todos los códigos de serie y variantes de color.
    Detecta pares 'NNNN / NNNNN2' (base / variante).
    Devuelve lista de (serie_base, variante_o_None) en orden de aparición, sin duplicados.
    """
    seen: dict[str, str | None] = {}

    for m in _SERIES_PAIR_RE.finditer(text):
        a, b = m.group(1), m.group(2)
        if _is_color_variant(a, b):
            if a not in seen:
                seen[a] = b
        elif _is_color_variant(b, a):
            if b not in seen:
                seen[b] = a
        else:
            # Ambos son series independientes
            if a not in seen:
                seen[a] = None
            if b not in seen:
                seen[b] = None

    return list(seen.items())


def dn_label_to_int(label: str) -> int | None:
    """Convierte etiqueta DN a entero mm: 'DN15' → 15, '1/2"' → 15."""
    label = label.strip()
    if label.upper().startswith("DN"):
        try:
            return int(label[2:].strip())
        except ValueError:
            pass
    if label in _IMPERIAL_TO_DN:
        return _IMPERIAL_TO_DN[label]
    try:
        return int(float(label))
    except ValueError:
        return None


def generate_candidate_skus(series_prefix: str, extraction: FichaExtractionResult) -> list[str]:
    """Genera SKUs candidatos combinando prefijo + sufijo DN (zero-padded 3 dígitos)."""
    dns: list[int] = []
    for row in extraction.dimensions:
        dn = dn_label_to_int(row.dn_label)
        if dn is not None and dn not in dns:
            dns.append(dn)
    dns.sort()
    return [f"{series_prefix}{dn:03d}" for dn in dns]


async def _resolve_sku_diffs(
    session: AsyncSession,
    series_prefix: str,
    extraction: FichaExtractionResult,
) -> list[SkuDiffResult]:
    """Genera y verifica SKUs candidatos para un prefijo de serie."""
    from app.services.ficha_enrichment.differ import FichaEnrichmentDiffer

    candidates = generate_candidate_skus(series_prefix, extraction)

    if not candidates:
        result = await session.execute(
            select(Product).where(Product.sku.like(f"{series_prefix}%")).order_by(Product.sku)
        )
        existing = list(result.scalars().all())
        if existing:
            differ = FichaEnrichmentDiffer()
            return differ.compute_batch(existing, extraction)
        return []

    result = await session.execute(select(Product).where(Product.sku.in_(candidates)))
    existing_products = {p.sku: p for p in result.scalars().all()}

    differ = FichaEnrichmentDiffer()
    sku_diffs: list[SkuDiffResult] = []
    for sku in candidates:
        if sku in existing_products:
            product = existing_products[sku]
            diffs = differ.compute(product, extraction)
            sku_diffs.append(SkuDiffResult(sku=sku, status="existing", diffs=diffs))
        else:
            scalars = extraction.scalars.model_dump(exclude_none=True)
            diffs = [
                FieldDiff(field_name=k, current_value=None, extracted_value=v, has_change=True)
                for k, v in scalars.items()
            ]
            sku_diffs.append(SkuDiffResult(sku=sku, status="new", diffs=diffs))
    return sku_diffs


async def resolve_series(
    session: AsyncSession,
    series_prefix: str,
    extraction: FichaExtractionResult,
) -> list[SkuDiffResult]:
    """Resuelve SKUs para una serie (interfaz legacy)."""
    return await _resolve_sku_diffs(session, series_prefix, extraction)


async def resolve_all_series(
    session: AsyncSession,
    pdf_text: str,
    extraction: FichaExtractionResult,
    filename_prefix: str | None = None,
) -> list[SeriesGroupResult]:
    """
    Detecta todas las series en el texto del PDF y resuelve SKUs para cada grupo.
    Cada grupo contiene una serie base (ej. 4097) y su variante de color opcional (ej. 40972).
    Fallback al prefijo del filename si no se detectan series en el texto.
    """
    detected = extract_all_series_from_text(pdf_text)

    if not detected and filename_prefix:
        detected = [(filename_prefix, None)]

    groups: list[SeriesGroupResult] = []
    for base_series, variant_series in detected:
        base_skus = await _resolve_sku_diffs(session, base_series, extraction)
        variant_skus = (
            await _resolve_sku_diffs(session, variant_series, extraction) if variant_series else []
        )
        groups.append(
            SeriesGroupResult(
                base_series=base_series,
                variant_series=variant_series,
                base_skus=base_skus,
                variant_skus=variant_skus,
            )
        )

    return groups


__all__ = [
    "dn_label_to_int",
    "extract_all_series_from_text",
    "extract_series_prefix",
    "generate_candidate_skus",
    "resolve_all_series",
    "resolve_series",
]
