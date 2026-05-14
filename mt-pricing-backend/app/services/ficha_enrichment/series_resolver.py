"""Detecta la serie desde el filename del PDF y genera SKUs candidatos desde tabla DN."""
from __future__ import annotations

import re

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.product import Product
from app.schemas.ficha_enrich import FieldDiff, FichaExtractionResult, SkuDiffResult

_IMPERIAL_TO_DN: dict[str, int] = {
    '1/8"': 6, "1/8": 6,
    '1/4"': 8, "1/4": 8,
    '3/8"': 10, "3/8": 10,
    '1/2"': 15, "1/2": 15,
    '3/4"': 20, "3/4": 20,
    '1"': 25, "1": 25,
    '1-1/4"': 32, '1 1/4"': 32, "1-1/4": 32, '1 1/4': 32,
    '1-1/2"': 40, '1 1/2"': 40, "1-1/2": 40, '1 1/2': 40,
    '2"': 50, "2": 50,
    '2-1/2"': 65, '2 1/2"': 65, "2-1/2": 65,
    '3"': 80, "3": 80,
    '4"': 100, "4": 100,
}


def extract_series_prefix(filename: str) -> str | None:
    """Extrae prefijo de serie: 'MTFT_4097.pdf' → '4097'."""
    match = re.search(r'MTFT[_\-]?(\d+)', filename, re.IGNORECASE)
    return match.group(1) if match else None


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


async def resolve_series(
    session: AsyncSession,
    series_prefix: str,
    extraction: FichaExtractionResult,
) -> list[SkuDiffResult]:
    """
    Genera SKUs candidatos desde la tabla DN y verifica cuáles existen en DB.
    Devuelve SkuDiffResult con status='existing' o 'new'.
    """
    from app.services.ficha_enrichment.differ import FichaEnrichmentDiffer

    candidates = generate_candidate_skus(series_prefix, extraction)

    # Si no hay dimensiones en el PDF, fallback: buscar los existentes con LIKE
    if not candidates:
        result = await session.execute(
            select(Product)
            .where(Product.sku.like(f"{series_prefix}%"))
            .order_by(Product.sku)
        )
        existing = list(result.scalars().all())
        if existing:
            differ = FichaEnrichmentDiffer()
            return differ.compute_batch(existing, extraction)
        return []

    # Verificar cuáles existen
    result = await session.execute(
        select(Product).where(Product.sku.in_(candidates))
    )
    existing_products = {p.sku: p for p in result.scalars().all()}

    differ = FichaEnrichmentDiffer()
    sku_diffs: list[SkuDiffResult] = []
    for sku in candidates:
        if sku in existing_products:
            product = existing_products[sku]
            diffs = differ.compute(product, extraction)
            sku_diffs.append(SkuDiffResult(sku=sku, status="existing", diffs=diffs))
        else:
            # SKU nuevo: todos los campos extraídos son "new" (current_value = None)
            scalars = extraction.scalars.model_dump(exclude_none=True)
            diffs = [
                FieldDiff(field_name=k, current_value=None, extracted_value=v, has_change=True)
                for k, v in scalars.items()
            ]
            sku_diffs.append(SkuDiffResult(sku=sku, status="new", diffs=diffs))

    return sku_diffs


__all__ = [
    "extract_series_prefix",
    "dn_label_to_int",
    "generate_candidate_skus",
    "resolve_series",
]
