"""Scoring del matching pipeline foundation.

Implementa lo que Sprint 3 necesita del scorer:

1. **G1 target**: precio mediano del peer-group × 1.10 (regla de pricing
   competitivo cuando existen peers con score alto). Equivalente al "pricing
   competitivo G1" del motor v5.1.
2. **G2 target**: ``coste_landed × multiplicador`` cuando no hay peers
   confiables (G2). Multiplicador depende del subtipo (default / stainless /
   cast_iron) — refleja ``rule_engine.G2_MULTIPLIERS``.
3. **Score 0-100** multi-dimensional con pesos hardcoded por dimensión
   (material, PN, rosca/connection, norma, brand-tier, delivery). Esta es la
   forma reducida del scorer multi-dim §7 del pipeline doc; los pesos están
   marcados ``TODO(ADR)`` para que cuando entren ML/embeddings los pesos
   provengan de ``comparator_config``.

El módulo es **puro**: sin IO, sin DB. Todos los cálculos en :class:`Decimal`
para evitar errores de redondeo.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from decimal import ROUND_HALF_UP, Decimal
from typing import Any

# ---------------------------------------------------------------------------
# G1 / G2 constantes de negocio
# ---------------------------------------------------------------------------
# Pricing competitivo G1 — 10% sobre la mediana del peer group.
# TODO(ADR-PRICING-G1): externalizar a `comparator_config` por familia.
G1_MEDIAN_MULTIPLIER: Decimal = Decimal("1.10")

# G2 — coste landed × multiplicador. Replica `rule_engine.G2_MULTIPLIERS`.
# TODO(ADR-PRICING-G2): unificar fuente de verdad — Sprint 3 duplica los
# multiplicadores para mantener `matching` desacoplado del motor de pricing.
G2_MULTIPLIERS: dict[str, Decimal] = {
    "default": Decimal("2.5"),
    "stainless": Decimal("2.8"),
    "cast_iron": Decimal("3.0"),
}

# Score multi-dim — pesos hardcoded (suman 1.0).
# TODO(ADR-MATCH-WEIGHTS): mover pesos a `comparator_config` con override por
# canal/familia. Ver `mt-product-matching-pipeline-detail.md` §7.1.
SCORING_WEIGHTS: dict[str, Decimal] = {
    "material": Decimal("0.20"),
    "pn": Decimal("0.15"),
    "thread": Decimal("0.15"),  # connection / rosca
    "norma": Decimal("0.15"),
    "brand_tier": Decimal("0.20"),
    "delivery": Decimal("0.15"),
}
DEFAULT_WEIGHTS = SCORING_WEIGHTS  # alias público

# Brand tiers — referencia: Pegler/Arco/Giacomini/Apollo/Nibco son tier-1.
# TODO(ADR-BRAND-TIERS): seed desde tabla `brand_tiers` cuando exista.
BRAND_TIERS: dict[str, str] = {
    "pegler": "tier1",
    "arco": "tier1",
    "giacomini": "tier1",
    "apollo": "tier1",
    "nibco": "tier1",
    "viega": "tier1",
}


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
def _round(value: Decimal | float, places: int = 2) -> Decimal:
    """Redondeo half-up — alineado con el motor v5.1."""
    if not isinstance(value, Decimal):
        value = Decimal(str(value))
    quant = Decimal("1").scaleb(-places)
    return value.quantize(quant, rounding=ROUND_HALF_UP)


def _median(values: list[Decimal]) -> Decimal | None:
    valid = sorted([v for v in values if v is not None and v > 0])
    if not valid:
        return None
    n = len(valid)
    mid = n // 2
    if n % 2 == 1:
        return valid[mid]
    return (valid[mid - 1] + valid[mid]) / Decimal(2)


def _detect_g2_subtype(material: str | None, name: str | None = None) -> str:
    """Replica simplificada de :meth:`PricingRuleEngine.detect_g2_subtype`."""
    text = f"{material or ''} {name or ''}".lower()
    if any(t in text for t in ["inox", "stainless", "ss316", "ss304", "s.s.", " ss "]):
        return "stainless"
    if any(t in text for t in ["cast iron", "fundic", "cast_iron"]):
        return "cast_iron"
    return "default"


# ---------------------------------------------------------------------------
# G1 / G2 target prices
# ---------------------------------------------------------------------------
def compute_g1_target(peer_prices: list[Decimal | float | int]) -> Decimal | None:
    """G1: precio mediano del peer group × 1.10.

    Args:
        peer_prices: lista de precios AED de candidatos clasificados como
            ``peer`` (ver ``MatchCandidate.kind``).

    Returns:
        ``None`` si no hay peers válidos; sino la mediana × 1.10 redondeada
        a 2 decimales.
    """
    if not peer_prices:
        return None
    decimals = [Decimal(str(p)) for p in peer_prices if p and Decimal(str(p)) > 0]
    if not decimals:
        return None
    median = _median(decimals)
    if median is None:
        return None
    return _round(median * G1_MEDIAN_MULTIPLIER, 2)


def compute_g2_target(
    landed_cost: Decimal | float | int,
    *,
    material: str | None = None,
    name: str | None = None,
    subtype: str | None = None,
) -> Decimal | None:
    """G2: coste landed × multiplicador (subtipo material).

    Args:
        landed_cost: coste total (incluye logística, arancel, etc.) en AED.
        material: nombre del material para detectar el subtipo.
        name: opcional, fallback si el material no está poblado.
        subtype: si ya se conoce el subtipo (``default|stainless|cast_iron``),
            saltarse la detección.

    Returns:
        ``None`` si el coste es ≤ 0.
    """
    if landed_cost is None:
        return None
    cost = Decimal(str(landed_cost))
    if cost <= 0:
        return None
    sub = subtype or _detect_g2_subtype(material, name)
    multiplier = G2_MULTIPLIERS.get(sub, G2_MULTIPLIERS["default"])
    return _round(cost * multiplier, 2)


# ---------------------------------------------------------------------------
# Score 0-100 multi-dimensional
# ---------------------------------------------------------------------------
@dataclass
class ScoringBreakdown:
    """Breakdown per-dimensión + score combinado.

    Persistido en ``match_candidates.score`` (combinado, 0-100). El breakdown
    completo va a ``raw_payload`` o a ``specs_jsonb`` para auditoría.
    """

    score: int
    breakdown: dict[str, float] = field(default_factory=dict)
    weights: dict[str, float] = field(default_factory=dict)
    notes: list[str] = field(default_factory=list)

    def as_dict(self) -> dict[str, Any]:
        return {
            "score": self.score,
            "breakdown": dict(self.breakdown),
            "weights": dict(self.weights),
            "notes": list(self.notes),
        }


def _eq_norm(a: str | None, b: str | None) -> bool:
    if a is None or b is None:
        return False
    return str(a).strip().lower() == str(b).strip().lower()


def _starts_or_contains(haystack: str | None, needle: str | None) -> bool:
    if haystack is None or needle is None:
        return False
    return str(needle).strip().lower() in str(haystack).strip().lower()


def _material_score(sku_material: str | None, cand_material: str | None) -> Decimal:
    if sku_material is None and cand_material is None:
        return Decimal("0.5")
    if sku_material is None or cand_material is None:
        return Decimal("0.3")
    if _eq_norm(sku_material, cand_material):
        return Decimal("1.0")
    # `brass_CW617N` ↔ `brass` debería matchear parcialmente.
    s = sku_material.lower()
    c = cand_material.lower()
    if s.split("_")[0] == c.split("_")[0]:
        return Decimal("0.85")
    return Decimal("0.0")


def _pn_score(sku_pn: str | None, cand_pn: str | None) -> Decimal:
    """PN: candidato igual o superior al SKU = OK; inferior penaliza."""
    if sku_pn is None or cand_pn is None:
        return Decimal("0.5")
    try:
        s = int(str(sku_pn).replace("PN", "").strip())
        c = int(str(cand_pn).replace("PN", "").strip())
    except (TypeError, ValueError):
        return Decimal("0.5")
    if c == s:
        return Decimal("1.0")
    if c > s:
        return Decimal("0.9")  # sobredimensionado pero compatible
    # PN menor = no soporta presión → penalización fuerte.
    return Decimal("0.0")


def _thread_score(sku_thread: str | None, cand_thread: str | None) -> Decimal:
    if sku_thread is None or cand_thread is None:
        return Decimal("0.5")
    return Decimal("1.0") if _eq_norm(sku_thread, cand_thread) else Decimal("0.0")


def _norma_score(sku_norma: str | None, cand_norma: str | None) -> Decimal:
    if sku_norma is None and cand_norma is None:
        return Decimal("0.5")
    if sku_norma is None or cand_norma is None:
        return Decimal("0.4")
    if _eq_norm(sku_norma, cand_norma):
        return Decimal("1.0")
    if _starts_or_contains(cand_norma, sku_norma) or _starts_or_contains(
        sku_norma, cand_norma
    ):
        return Decimal("0.7")
    return Decimal("0.2")


def _brand_score(sku_brand: str | None, cand_brand: str | None) -> Decimal:
    if cand_brand is None:
        return Decimal("0.3")
    if sku_brand and _eq_norm(sku_brand, cand_brand):
        return Decimal("1.0")
    tier = BRAND_TIERS.get((cand_brand or "").lower())
    if tier == "tier1":
        return Decimal("0.7")
    return Decimal("0.4")


_DELIVERY_DAYS_KEYWORDS: dict[str, int] = {
    "same day": 0,
    "next day": 1,
    "1 day": 1,
    "2 days": 2,
    "3 days": 3,
    "4-7 days": 5,
    "1 week": 7,
    "2 weeks": 14,
    "3-4 weeks": 28,
}


def _delivery_score(delivery_text: str | None) -> Decimal:
    """Heurística simple: menos días = mejor. Sin parser real (Sprint 3)."""
    if not delivery_text:
        return Decimal("0.5")
    text = delivery_text.lower().strip()
    for kw, days in _DELIVERY_DAYS_KEYWORDS.items():
        if kw in text:
            if days <= 1:
                return Decimal("1.0")
            if days <= 3:
                return Decimal("0.9")
            if days <= 7:
                return Decimal("0.7")
            if days <= 14:
                return Decimal("0.5")
            return Decimal("0.3")
    return Decimal("0.5")


def compute_scoring(
    sku: dict[str, Any],
    candidate: dict[str, Any],
    *,
    weights: dict[str, Decimal] | None = None,
) -> ScoringBreakdown:
    """Calcula score 0-100 del candidato vs SKU.

    Args:
        sku: dict con ``material``, ``pn``, ``thread``/``connection``,
            ``norma``, ``brand``.
        candidate: dict con las mismas claves más ``delivery_text``.
        weights: override de pesos (defaults en :data:`SCORING_WEIGHTS`).
    """
    w = weights or SCORING_WEIGHTS
    cand_specs = candidate.get("specs") or {}

    sku_material = sku.get("material")
    cand_material = candidate.get("material") or cand_specs.get("material")

    sku_pn = sku.get("pn")
    cand_pn = candidate.get("pn") or cand_specs.get("pn")

    sku_thread = sku.get("thread") or sku.get("connection")
    cand_thread = (
        candidate.get("thread")
        or candidate.get("connection")
        or cand_specs.get("thread")
        or cand_specs.get("connection")
    )

    sku_norma = sku.get("norma") or (sku.get("specs") or {}).get("norma")
    cand_norma = candidate.get("norma") or cand_specs.get("norma")

    sku_brand = sku.get("brand")
    cand_brand = candidate.get("brand")

    delivery_text = candidate.get("delivery_text")

    dim_scores: dict[str, Decimal] = {
        "material": _material_score(sku_material, cand_material),
        "pn": _pn_score(sku_pn, cand_pn),
        "thread": _thread_score(sku_thread, cand_thread),
        "norma": _norma_score(sku_norma, cand_norma),
        "brand_tier": _brand_score(sku_brand, cand_brand),
        "delivery": _delivery_score(delivery_text),
    }

    weighted = Decimal("0")
    for dim, raw in dim_scores.items():
        weighted += raw * w.get(dim, Decimal("0"))

    score_int = int(_round(weighted * Decimal("100"), 0))
    score_int = max(0, min(100, score_int))

    breakdown = {dim: float(_round(s, 4)) for dim, s in dim_scores.items()}
    weights_out = {dim: float(w.get(dim, Decimal("0"))) for dim in dim_scores}

    notes: list[str] = []
    if sku_pn and cand_pn and dim_scores["pn"] == Decimal("0.0"):
        notes.append("pn_below_sku_requirement")
    if sku_thread and cand_thread and dim_scores["thread"] == Decimal("0.0"):
        notes.append("thread_mismatch")
    if dim_scores["material"] == Decimal("0.0"):
        notes.append("material_mismatch")

    return ScoringBreakdown(
        score=score_int,
        breakdown=breakdown,
        weights=weights_out,
        notes=notes,
    )
