"""delivery_classifier.py — Clasifica el plazo de entrega de un candidato Amazon/Noon.

Contexto de negocio:
  MT tiene stock físico en UAE para entrega inmediata.
  Un candidato con entrega de 30-60 días desde China es un match válido
  de producto, pero su precio NO es comparable en el mismo escenario de
  compra (cliente necesita entrega rápida vs. importación larga).

  Por eso, el price_confidence_score es INDEPENDIENTE del match score:
  el candidato sigue siendo válido para identificar el producto, pero
  su precio se marca como "referencial" si viene de importación larga.

Categorías:
  local_stock — UAE/GCC, entrega ≤ 5 días → price_confidence 100
  regional    — entrega 6-21 días          → price_confidence 70
  import      — entrega > 21 días / China  → price_confidence 30
  unknown     — sin info suficiente        → price_confidence 60
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import NamedTuple


# ─── Resultado ───────────────────────────────────────────────────────────────


class DeliveryClassification(NamedTuple):
    category: str       # "local_stock" | "regional" | "import" | "unknown"
    estimated_days: int | None
    price_confidence_score: int  # 0-100
    note: str           # razón legible para el panel de análisis


# ─── Patrones ────────────────────────────────────────────────────────────────

# Señales de stock local UAE/GCC (entrega ≤ 5 días)
_LOCAL_PATTERNS = [
    re.compile(r"\bin\s+stock\b", re.I),
    re.compile(r"\bget\s+it\s+(by\s+)?(today|tomorrow|monday|tuesday|wednesday|thursday|friday|saturday|sunday)\b", re.I),
    re.compile(r"\bfree\s+delivery\s+(today|tomorrow|mon|tue|wed|thu|fri|sat|sun|\d+\s*(jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec))", re.I),
    re.compile(r"\b(same|next)\s+day\s+delivery\b", re.I),
    re.compile(r"\bdelivery\s+in\s+[1-5]\s+(?:business\s+)?days?\b", re.I),
    re.compile(r"\bships\s+from\s+(?:uae|dubai|abu\s+dhabi|sharjah|gcc|abudhabi)\b", re.I),
    re.compile(r"\bsold\s+by\s+amazon\.ae\b", re.I),
    re.compile(r"\bamazon\.ae\b.*\bfulfilled\b", re.I),
    re.compile(r"\bfulfilled\s+by\s+amazon\b", re.I),
]

# Señales de importación larga / China
_IMPORT_PATTERNS = [
    re.compile(r"\bships?\s+from\s+china\b", re.I),
    re.compile(r"\bshipped\s+from\s+china\b", re.I),
    re.compile(r"\bsold\s+by\s+(?:\w+\s+)?china\b", re.I),
    re.compile(r"\bimport(?:ed|s?)?\b", re.I),
    re.compile(r"\bfactory\s+(?:direct|ship|order)\b", re.I),
    re.compile(r"\bmanufacturer\b", re.I),
]

# Extrae número de días explícito (ej. "15 to 30 days" → 22 días promedio)
_DAYS_RANGE_RE = re.compile(
    r"(\d+)\s*(?:to|-)\s*(\d+)\s*(?:business\s+)?days?", re.I
)
_DAYS_SINGLE_RE = re.compile(
    r"(\d+)\s+(?:business\s+)?days?", re.I
)
_WEEKS_RANGE_RE = re.compile(
    r"(\d+)\s*(?:to|-)\s*(\d+)\s*weeks?", re.I
)
_WEEKS_SINGLE_RE = re.compile(
    r"(\d+)\s*weeks?", re.I
)


# ─── Clasificador ────────────────────────────────────────────────────────────


def _extract_days(text: str) -> int | None:
    """Extrae el número estimado de días de entrega del texto."""
    m = _DAYS_RANGE_RE.search(text)
    if m:
        lo, hi = int(m.group(1)), int(m.group(2))
        return (lo + hi) // 2

    m = _DAYS_SINGLE_RE.search(text)
    if m:
        return int(m.group(1))

    m = _WEEKS_RANGE_RE.search(text)
    if m:
        lo, hi = int(m.group(1)), int(m.group(2))
        return ((lo + hi) // 2) * 7

    m = _WEEKS_SINGLE_RE.search(text)
    if m:
        return int(m.group(1)) * 7

    return None


def classify_delivery(delivery_text: str | None) -> DeliveryClassification:
    """Clasifica el texto de entrega de un candidato Amazon/Noon.

    Args:
        delivery_text: Texto tal como lo devuelve el scraper (en inglés).
                       Puede ser None si el scraper no lo capturó.

    Returns:
        DeliveryClassification con categoría, días estimados y score de confianza.
    """
    if not delivery_text or not delivery_text.strip():
        return DeliveryClassification(
            category="unknown",
            estimated_days=None,
            price_confidence_score=60,
            note="Sin información de entrega",
        )

    text = delivery_text.strip()

    # 1. Verificar stock local UAE primero (señal más fuerte)
    for pat in _LOCAL_PATTERNS:
        if pat.search(text):
            return DeliveryClassification(
                category="local_stock",
                estimated_days=_extract_days(text) or 2,
                price_confidence_score=100,
                note=f"Stock en UAE/GCC — precio comparable al de MT",
            )

    # 2. Extraer días explícitos del texto
    estimated_days = _extract_days(text)

    # 3. Verificar señales de importación / China
    for pat in _IMPORT_PATTERNS:
        if pat.search(text):
            days = estimated_days or 45
            return DeliveryClassification(
                category="import",
                estimated_days=days,
                price_confidence_score=30,
                note=f"Importación (China/fábrica) — precio referencial, no comparable con stock UAE",
            )

    # 4. Clasificar por días si los tenemos
    if estimated_days is not None:
        if estimated_days <= 5:
            return DeliveryClassification(
                category="local_stock",
                estimated_days=estimated_days,
                price_confidence_score=100,
                note=f"Entrega ≤ {estimated_days} días — stock local o regional cercano",
            )
        if estimated_days <= 21:
            return DeliveryClassification(
                category="regional",
                estimated_days=estimated_days,
                price_confidence_score=70,
                note=f"Entrega ~{estimated_days} días — precio parcialmente comparable",
            )
        return DeliveryClassification(
            category="import",
            estimated_days=estimated_days,
            price_confidence_score=30,
            note=f"Entrega ~{estimated_days} días — plazo largo, precio referencial",
        )

    # 5. Sin señales claras
    return DeliveryClassification(
        category="unknown",
        estimated_days=None,
        price_confidence_score=60,
        note="Plazo de entrega no determinado — precio con confianza moderada",
    )


__all__ = ["DeliveryClassification", "classify_delivery"]
