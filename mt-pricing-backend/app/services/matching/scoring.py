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

import re
from dataclasses import dataclass, field
from decimal import ROUND_HALF_UP, Decimal
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from app.services.matching.material_normalizer import MaterialNormalizer

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
    "material": Decimal("0.18"),
    "pn": Decimal("0.14"),
    "thread_standard": Decimal("0.14"),  # key must match dim_scores key
    "norma": Decimal("0.14"),
    "brand_tier": Decimal("0.18"),
    "delivery": Decimal("0.14"),
    "data_completeness": Decimal("0.08"),
    # New dimensions — zero weight in legacy default (overridden by taxonomy profiles):
    "application_class": Decimal("0.00"),
    "connection_gender": Decimal("0.00"),
    "handle": Decimal("0.00"),
    "dn": Decimal("0.00"),
    "product_type": Decimal("0.00"),
    "ways": Decimal("0.00"),
    "actuator": Decimal("0.00"),
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


# Pesos por componente para scoring compuesto de material.
# Si el SKU no especifica un componente, se omite de la ponderación.
_COMPONENT_WEIGHTS: dict[str, Decimal] = {
    "body": Decimal("0.50"),
    "ball": Decimal("0.30"),
    "seat": Decimal("0.15"),
    "stem": Decimal("0.05"),
}


def _material_score_pair(
    a: str | None,
    b: str | None,
    norm: MaterialNormalizer,
) -> Decimal:
    """Score 0-1 entre dos strings de material usando homologación."""
    if a is None and b is None:
        return Decimal("0.5")
    if a is None or b is None:
        return Decimal("0.3")
    if norm.same_canonical(a, b):
        return Decimal("1.0")
    if norm.same_family(a, b):
        # Misma familia (ej. brass vs brass_cw617n) — match parcial.
        return Decimal("0.75")
    return Decimal("0.0")


def _material_score(
    sku_material: str | None,
    cand_material: str | None,
    norm: MaterialNormalizer | None = None,
    sku_components: list[dict[str, str]] | None = None,
    cand_components: dict[str, str] | None = None,
) -> Decimal:
    """Score de material con soporte para composición body/ball/seat.

    Cuando el SKU tiene componentes definidos (product_materials), el score
    se pondera por componente. Si el candidato no especifica un componente,
    se trata como desconocido (score parcial 0.4), no como mismatch.

    Args:
        sku_material: campo plano ``products.material`` (fallback).
        cand_material: campo plano del candidato.
        norm: normalizador de homologación. Si None, usa STATIC_NORMALIZER.
        sku_components: lista [{component, material}] de product_materials.
        cand_components: dict {component: material_str} del candidato.
    """
    from app.services.matching.material_normalizer import STATIC_NORMALIZER

    n = norm or STATIC_NORMALIZER

    # ── Scoring compuesto (body/ball/seat) cuando hay datos de componentes ──
    if sku_components:
        # Agrupar por componente — tomar posición 0 (primaria).
        sku_by_comp: dict[str, str] = {}
        for row in sku_components:
            comp = (row.get("component") or "").lower()
            if comp in _COMPONENT_WEIGHTS and comp not in sku_by_comp:
                sku_by_comp[comp] = row.get("material", "")

        if sku_by_comp:
            total_w = Decimal("0")
            weighted = Decimal("0")
            has_cand_components = bool(cand_components)
            for comp, w in _COMPONENT_WEIGHTS.items():
                sku_mat = sku_by_comp.get(comp)
                if sku_mat is None:
                    continue  # componente no definido en SKU — omitir
                total_w += w
                cand_mat = (cand_components or {}).get(comp)
                if cand_mat is None:
                    if comp == "body" and cand_material and not has_cand_components:
                        # El candidato indica material plano pero no por componente:
                        # comparar el body del SKU contra el material plano del candidato.
                        # Evita que materiales incompatibles (PVC, acero inox) reciban
                        # score parcial 0.4 y esquiven material_mismatch.
                        weighted += w * _material_score_pair(sku_mat, cand_material, n)
                    else:
                        # Candidato no especifica este componente — penalización leve.
                        weighted += w * Decimal("0.4")
                else:
                    weighted += w * _material_score_pair(sku_mat, cand_mat, n)
            if total_w > 0:
                return weighted / total_w

    # ── Fallback: comparación plana ──────────────────────────────────────────
    return _material_score_pair(sku_material, cand_material, n)


# Escala estándar de PN — usada para calcular distancia de grados.
_PN_GRADES: tuple[int, ...] = (6, 10, 16, 25, 40, 63, 100, 160, 250, 400)
# Máximo de grados por encima aceptables sin penalización dura.
# +1 → 0.85, +2 → 0.55, +3 → 0.20, +4 o más → 0.0 (pn_too_far_above)
_PN_MAX_GRADE_ABOVE = 3


def _parse_pn(pn: str | None) -> int | None:
    if pn is None:
        return None
    try:
        return int(str(pn).upper().replace("PN", "").strip())
    except (TypeError, ValueError):
        return None


def _pn_grade_distance(a: int, b: int) -> int | None:
    """Distancia en grados de escala entre dos PN. Positivo = b mayor que a."""
    try:
        ia = _PN_GRADES.index(a)
        ib = _PN_GRADES.index(b)
        return ib - ia
    except ValueError:
        return None


def _pn_score(sku_pn: str | None, cand_pn: str | None) -> tuple[Decimal, list[str]]:
    """PN score + notas. Retorna (score, notes).

    Reglas:
    - Igual → 1.0
    - Superior hasta +3 grados → score degradado (0.85 / 0.55 / 0.20)
    - Superior +4 grados → 0.0 + nota pn_too_far_above (precio fuera de rango)
    - Inferior → 0.0 + nota pn_below_sku_requirement
    - Sin datos → 0.5
    """
    notes: list[str] = []
    s_int = _parse_pn(sku_pn)
    c_int = _parse_pn(cand_pn)

    if s_int is None or c_int is None:
        return Decimal("0.5"), notes

    if c_int == s_int:
        return Decimal("1.0"), notes

    if c_int < s_int:
        notes.append("pn_below_sku_requirement")
        return Decimal("0.0"), notes

    # Candidato superior — verificar distancia de grados
    dist = _pn_grade_distance(s_int, c_int)
    if dist is None:
        # Valores fuera de la escala estándar — diferencia porcentual
        ratio = c_int / s_int
        if ratio <= 1.6:
            return Decimal("0.85"), notes
        if ratio <= 2.5:
            return Decimal("0.40"), notes
        notes.append("pn_too_far_above")
        return Decimal("0.0"), notes

    grade_scores = {1: Decimal("0.85"), 2: Decimal("0.55"), 3: Decimal("0.20")}
    if dist <= _PN_MAX_GRADE_ABOVE:
        return grade_scores.get(dist, Decimal("0.20")), notes

    notes.append("pn_too_far_above")
    return Decimal("0.0"), notes


# ── Estándar de rosca ────────────────────────────────────────────────────────

_THREAD_STD_PATTERNS: dict[str, frozenset[str]] = {
    "bsp": frozenset(
        {"bsp", "bspp", "bspt", "g thread", "g-thread", "rp", "rc", "iso 228", "en iso 228"}
    ),
    "npt": frozenset({"npt", "nptf", "ansi b1.20"}),
    "metric": frozenset({"metric", "din", "m10", "m12", "m14", "m16", "m20"}),
}


def _extract_thread_standard(text: str | None) -> str | None:
    if not text:
        return None
    t = text.lower()
    for std, patterns in _THREAD_STD_PATTERNS.items():
        if any(p in t for p in patterns):
            return std
    return None


def _thread_score(sku_thread: str | None, cand_thread: str | None) -> tuple[Decimal, list[str]]:
    """Retorna (score, notes). Estándar de rosca es blocker duro."""
    notes: list[str] = []
    sku_std = _extract_thread_standard(sku_thread)
    cand_std = _extract_thread_standard(cand_thread)

    if sku_std is None or cand_std is None:
        # Sin información suficiente — score neutro, no blocker
        if sku_thread and cand_thread:
            # Hay texto pero no se reconoció estándar — comparación literal
            score = Decimal("1.0") if _eq_norm(sku_thread, cand_thread) else Decimal("0.3")
            return score, notes
        return Decimal("0.5"), notes

    if sku_std == cand_std:
        return Decimal("1.0"), notes

    notes.append("thread_standard_mismatch")
    return Decimal("0.0"), notes


# ── DN / Tamaño ───────────────────────────────────────────────────────────────

_DN_INCH_RE = re.compile(r'(\d+(?:[/-]\d+)?)\s*["“”]')  # "  o comillas tipográficas
_DN_INCH_WORD_RE = re.compile(r"(\d+(?:[/-]\d+)?)[- ]*(?:inch|in\b)", re.IGNORECASE)
_DN_METRIC_RE = re.compile(r"\bDN\s*(\d{1,4})\b", re.IGNORECASE)
_DN_INT_RE = re.compile(r"^\s*(\d{1,4})\s*$")

# DN métrico → pulgadas canónicas (para comparar ambos formatos)
_DN_TO_INCH: dict[int, str] = {
    8: "1/4",
    10: "3/8",
    15: "1/2",
    20: "3/4",
    25: "1",
    32: "1-1/4",
    40: "1-1/2",
    50: "2",
    65: "2-1/2",
    80: "3",
    100: "4",
    125: "5",
    150: "6",
    200: "8",
    250: "10",
    300: "12",
}
_INCH_TO_DN: dict[str, int] = {v: k for k, v in _DN_TO_INCH.items()}


def _normalize_dn(text: str | None) -> str | None:
    """Normaliza DN a pulgadas canónicas para comparación cross-format.

    Soporta: '1/2"', '1/2 inch', '1/2in', 'DN15', '15', '1-1/2"'.
    Usado tanto para campos de spec limpios como para extracción desde títulos.
    """
    if not text:
        return None
    t = text.strip()

    # Formato pulgadas con símbolo: '1/2"', '1"', '1-1/2"' (ASCII o tipográfico)
    m = _DN_INCH_RE.search(t)
    if m:
        return m.group(1).replace(" ", "").lower()

    # Formato DN métrico: 'DN50', 'DN 15'
    m = _DN_METRIC_RE.search(t)
    if m:
        dn_int = int(m.group(1))
        return _DN_TO_INCH.get(dn_int, f"dn{dn_int}")

    # Formato "inch" word: '1/2 inch', '1/2in', '3/4 Inch'
    m = _DN_INCH_WORD_RE.search(t)
    if m:
        return m.group(1).replace(" ", "").lower()

    # Entero puro (campo spec): '15', '50'
    m = _DN_INT_RE.match(t)
    if m:
        dn_int = int(m.group(1))
        # Enteros como 2, 3, 4 son pulgadas canónicas; 15, 50 son valores DN.
        if str(dn_int) in _INCH_TO_DN:
            return str(dn_int)
        return _DN_TO_INCH.get(dn_int, f"dn{dn_int}")

    return t.lower()


def _dn_score(sku_dn: str | None, cand_dn: str | None) -> tuple[Decimal, list[str]]:
    """DN debe coincidir. Retorna (score, notes)."""
    notes: list[str] = []
    if sku_dn is None or cand_dn is None:
        return Decimal("0.5"), notes

    sku_norm = _normalize_dn(sku_dn)
    cand_norm = _normalize_dn(cand_dn)

    if sku_norm == cand_norm:
        return Decimal("1.0"), notes

    notes.append("dn_mismatch")
    return Decimal("0.0"), notes


# ── Tipo de producto + mini qualifier ─────────────────────────────────────────

_MINI_TOKENS: frozenset[str] = frozenset(
    {"mini", "miniball", "mini-ball", "compact ball", "minibola"}
)

# Palabras en el título de un candidato que indican uso residencial/doméstico.
# El SKU siempre se asume "commercial" en familias de válvulas (productos MT).
_RESIDENTIAL_TOKENS: frozenset[str] = frozenset(
    {
        "shower",
        "bathtub",
        "bath tap",
        "faucet",
        "washing machine",
        "drinking water",
        "potable water",
        "garden hose",
        "rv water",
        "motorhome water",
        "household",
        "home plumbing",
        "kitchen sink",
        "irrigation valve",
    }
)


def _detect_application_class(
    title: str | None,
    specs: dict[str, Any] | None = None,
) -> str | None:
    """Detecta clase de aplicación desde specs estructurados o palabras clave en título."""
    s = specs or {}
    explicit = str(s.get("application_class") or s.get("application") or "").lower()
    if any(w in explicit for w in ("residential", "domestic", "household")):
        return "residential"
    if any(w in explicit for w in ("industrial", "commercial", "process")):
        return "commercial"
    if not title:
        return None
    t = title.lower()
    if any(tok in t for tok in _RESIDENTIAL_TOKENS):
        return "residential"
    return None


def _application_class_score(
    sku_class: str | None,
    cand_class: str | None,
) -> tuple[Decimal, list[str]]:
    """Score de clase de aplicación. Residencial vs comercial → mismatch."""
    if sku_class is None or cand_class is None:
        return Decimal("0.5"), []
    if sku_class == cand_class:
        return Decimal("1.0"), []
    return Decimal("0.0"), ["application_class_mismatch"]


# Familia → palabras clave en título del candidato
_FAMILY_TO_KEYWORDS: dict[str, frozenset[str]] = {
    "ball_valve": frozenset({"ball valve", "ball-valve", "kugelhahn", "válvula bola", "bola"}),
    "valves_ball": frozenset({"ball valve", "ball-valve", "válvula bola"}),
    "gate_valve": frozenset({"gate valve", "válvula compuerta", "schieber"}),
    "globe_valve": frozenset({"globe valve", "válvula globo"}),
    "check_valve": frozenset({"check valve", "non-return valve", "válvula retención", "clapet"}),
    "butterfly_valve": frozenset({"butterfly valve", "válvula mariposa", "absperrklappen"}),
    "strainer": frozenset({"strainer", "y-strainer", "filtro y", "filter"}),
    "pressure_gauge": frozenset({"pressure gauge", "manometer", "manómetro", "pressure meter"}),
    "HIDROSANITARIO": frozenset({"ball valve", "ball-valve", "válvula bola"}),
    "FILTROS": frozenset({"strainer", "y-strainer"}),
    "MANOMETROS": frozenset({"pressure gauge", "manometer", "manómetro"}),
}

_WAYS_RE = re.compile(
    r"\b([23])\s*-?\s*(?:way|port|vías?|wege)\b|\b(?:two|three)\s*-?\s*way\b",
    re.IGNORECASE,
)
_WAYS_WORD: dict[str, int] = {"two": 2, "three": 3}


def _extract_ways(text: str | None) -> int | None:
    if not text:
        return None
    m = _WAYS_RE.search(text)
    if not m:
        return None
    raw = m.group(1)
    if raw:
        return int(raw)
    word = m.group(0).split("-")[0].split()[0].lower()
    return _WAYS_WORD.get(word)


def _has_mini(text: str | None) -> bool:
    if not text:
        return False
    t = text.lower()
    return any(tok in t for tok in _MINI_TOKENS)


def _product_type_score(
    sku_family: str | None,
    sku_type_text: str | None,
    cand_title: str | None,
    cand_specs: dict[str, Any],
) -> tuple[Decimal, list[str]]:
    """Score de tipo de producto y mini qualifier. Retorna (score, notes)."""
    notes: list[str] = []

    # ── Mini qualifier ───────────────────────────────────────────────────────
    sku_is_mini = _has_mini(sku_type_text)
    cand_is_mini = _has_mini(cand_title) or _has_mini(str(cand_specs.get("valve_type", "")))
    if sku_is_mini != cand_is_mini:
        notes.append("mini_mismatch")
        return Decimal("0.0"), notes

    # ── Tipo de producto via familia MT ─────────────────────────────────────
    if not sku_family:
        return Decimal("0.5"), notes

    keywords = (
        _FAMILY_TO_KEYWORDS.get(sku_family)
        or _FAMILY_TO_KEYWORDS.get(sku_family.upper())
        or _FAMILY_TO_KEYWORDS.get(sku_family.strip().lower().replace(" ", "_"))
    )
    if not keywords:
        return Decimal("0.5"), notes

    candidate_text = f"{cand_title or ''} {cand_specs.get('valve_type', '')}".lower()
    if any(kw in candidate_text for kw in keywords):
        return Decimal("1.0"), notes

    # El candidato no menciona el tipo esperado → mismatch de producto
    notes.append("product_type_mismatch")
    return Decimal("0.0"), notes


# ── Número de vías ────────────────────────────────────────────────────────────


def _ways_score(
    sku_type_text: str | None,
    cand_title: str | None,
    cand_specs: dict[str, Any],
) -> tuple[Decimal, list[str]]:
    """Score de vías (2-way vs 3-way). Retorna (score, notes)."""
    notes: list[str] = []
    sku_ways = _extract_ways(sku_type_text)
    cand_ways = _extract_ways(cand_title) or _extract_ways(str(cand_specs.get("valve_type", "")))

    if sku_ways is None and cand_ways is None:
        return Decimal("0.5"), notes  # sin datos en ninguno de los dos

    if cand_ways is None:
        return Decimal("0.5"), notes  # candidato sin datos de vías — no determinar

    # SKU no declara vías → asumir 2-way (estándar para válvulas de bola/globo).
    # Un candidato que explícitamente dice "3-way" no es el mismo producto.
    if sku_ways is None:
        sku_ways = 2

    if sku_ways == cand_ways:
        return Decimal("1.0"), notes

    notes.append("ways_mismatch")
    return Decimal("0.0"), notes


# ── Extracción de maneta desde texto libre ────────────────────────────────────

_HANDLE_COLORS: frozenset[str] = frozenset(
    {
        "red",
        "blue",
        "black",
        "yellow",
        "green",
        "orange",
        "white",
        "grey",
        "gray",
    }
)

_HANDLE_TYPES: frozenset[str] = frozenset(
    {
        "butterfly",
        "lever",
        "t-bar",
        "wing",
        "ergonomic",
        "lockable",
    }
)


def _extract_handle_color(text: str | None) -> str | None:
    """Extrae color de maneta buscando colores dentro de ±3 palabras de 'handle'."""
    if not text:
        return None
    words = re.split(r"\W+", text.lower())
    for i, w in enumerate(words):
        if w == "handle":
            window = words[max(0, i - 3) : i + 4]
            for cw in window:
                if cw in _HANDLE_COLORS:
                    return cw
    return None


def _extract_handle_type(text: str | None) -> str | None:
    """Extrae tipo de maneta buscando keywords en contexto de 'handle'."""
    if not text:
        return None
    t = text.lower()
    for htype in _HANDLE_TYPES:
        # Match "butterfly handle" o "handle ergonomic" (hasta 20 chars entre ellos)
        if re.search(
            rf"\b{re.escape(htype)}\b.{{0,20}}handle|handle.{{0,20}}\b{re.escape(htype)}\b",
            t,
        ):
            return htype
    return None


def _handle_score(
    sku_specs: dict[str, Any] | None,
    cand_specs: dict[str, Any],
    *,
    sku_text: str | None = None,
    cand_text: str | None = None,
) -> tuple[Decimal, list[str]]:
    """Compara tipo/color de maneta. Retorna (score, notes).

    Score: 0.5 neutral (sin datos), 1.0 match confirmado, 0.0 mismatch confirmado.
    Impacto adicional: match_service aplica lógica pool-relativa sobre la nota.
    """
    sku_s = sku_specs or {}

    # Color — specs primero, fallback a texto
    sku_color = (sku_s.get("handle_color") or "").strip().lower() or _extract_handle_color(sku_text)
    cand_color = (cand_specs.get("handle_color") or "").strip().lower() or _extract_handle_color(
        cand_text
    )

    # Tipo/material — specs primero, fallback a texto
    sku_type = (
        sku_s.get("handle_material") or sku_s.get("handle_type") or ""
    ).strip().lower() or _extract_handle_type(sku_text)
    cand_type = (
        cand_specs.get("handle_material") or cand_specs.get("handle_type") or ""
    ).strip().lower() or _extract_handle_type(cand_text)

    if not sku_color and not sku_type:
        return Decimal("0.5"), []  # SKU sin datos de maneta — neutral

    if not cand_color and not cand_type:
        # Candidato sin datos de maneta cuando el SKU tiene color → probable mismatch.
        if sku_color:
            return Decimal("0.0"), ["handle_mismatch"]
        return Decimal("0.5"), []  # SKU solo tiene tipo, sin datos candidato → neutral

    # Cuando ambos lados tienen COLOR: el color determina el match.
    if sku_color and cand_color:
        if sku_color == cand_color:
            return Decimal("1.0"), []
        return Decimal("0.5"), []  # colores distintos — no es hard-block de precio

    # Sin color en alguno de los lados → el TIPO determina si es mismatch.
    if sku_type and cand_type:
        if sku_type == cand_type:
            return Decimal("1.0"), []
        return Decimal("0.0"), ["handle_mismatch"]

    return Decimal("0.5"), []


# ── Actuador ──────────────────────────────────────────────────────────────────

_MANUAL_ACTUATORS: frozenset[str] = frozenset(
    {
        "manual",
        "lever",
        "handle",
        "free shaft",
        "handwheel",
        "manual lever",
    }
)
_ELECTRIC_ACTUATORS: frozenset[str] = frozenset(
    {
        "electric",
        "motorized",
        "motor",
        "electrical",
        "electro",
    }
)
_FLUID_ACTUATORS: frozenset[str] = frozenset(
    {
        "pneumatic",
        "hydraulic",
    }
)
_GEAR_ACTUATORS: frozenset[str] = frozenset(
    {
        "gearbox",
        "gear",
        "worm gear",
        "worm",
    }
)


def _actuator_category(text: str | None) -> str | None:
    if not text:
        return None
    t = text.lower().strip()
    if any(k in t for k in _ELECTRIC_ACTUATORS):
        return "electric"
    if any(k in t for k in _FLUID_ACTUATORS):
        return "fluid"
    if any(k in t for k in _GEAR_ACTUATORS):
        return "gear"
    if any(k in t for k in _MANUAL_ACTUATORS):
        return "manual"
    return t


def _actuator_score(
    sku_actuation: str | None,
    cand_actuation: str | None,
) -> tuple[Decimal, list[str]]:
    """Compara tipo de actuador. Emite actuator_mismatch si categorías incompatibles."""
    sku_cat = _actuator_category(sku_actuation)
    cand_cat = _actuator_category(cand_actuation)

    if sku_cat is None or cand_cat is None:
        return Decimal("0.5"), []  # sin datos suficientes

    if sku_cat == cand_cat:
        return Decimal("1.0"), []

    # Manual y gear son ambos manuales en sentido amplio — penalización leve
    if {sku_cat, cand_cat} <= {"manual", "gear"}:
        return Decimal("0.5"), []

    return Decimal("0.0"), ["actuator_mismatch"]


def _norma_score(sku_norma: str | None, cand_norma: str | None) -> Decimal:
    if sku_norma is None and cand_norma is None:
        return Decimal("0.5")
    if sku_norma is None or cand_norma is None:
        return Decimal("0.4")
    if _eq_norm(sku_norma, cand_norma):
        return Decimal("1.0")
    if _starts_or_contains(cand_norma, sku_norma) or _starts_or_contains(sku_norma, cand_norma):
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


# ── Bore type (full bore / reduced bore) ─────────────────────────────────────

_BORE_ALIASES: dict[str, str] = {
    "full bore": "full_bore",
    "full_bore": "full_bore",
    "full port": "full_bore",
    "full flow": "full_bore",
    "fb": "full_bore",
    "reduced bore": "reduced_bore",
    "reduced_bore": "reduced_bore",
    "standard bore": "reduced_bore",
    "rb": "reduced_bore",
    "sb": "reduced_bore",
}


def _normalize_bore(text: str | None) -> str | None:
    if not text:
        return None
    return _BORE_ALIASES.get(text.lower().strip())


def _bore_type_score(sku_bore: str | None, cand_bore: str | None) -> list[str]:
    """Emite bore_type_mismatch cuando ambos tienen dato y difieren."""
    sku_b = _normalize_bore(sku_bore)
    cand_b = _normalize_bore(cand_bore)
    if sku_b and cand_b and sku_b != cand_b:
        return ["bore_type_mismatch"]
    return []


# ── Seat / seal material ──────────────────────────────────────────────────────

_SEAT_MAT_FAMILY: dict[str, str] = {
    "ptfe": "ptfe",
    "rptfe": "ptfe",
    "teflon": "ptfe",
    "polytetrafluoroethylene": "ptfe",
    "epdm": "epdm",
    "nbr": "nbr",
    "buna": "nbr",
    "buna-n": "nbr",
    "buna n": "nbr",
    "fkm": "fkm",
    "fpm": "fkm",
    "viton": "fkm",
    "metal": "metal",
    "stainless": "metal",
    "ss316": "metal",
    "brass": "metal",
    "carbon steel": "metal",
    "silicone": "silicone",
    "vmq": "silicone",
}


def _normalize_seat_mat(text: str | None) -> str | None:
    if not text:
        return None
    return _SEAT_MAT_FAMILY.get(text.lower().strip())


def _seat_material_score(sku_seat: str | None, cand_seat: str | None) -> list[str]:
    """Emite seat_material_mismatch cuando las familias de asiento difieren."""
    sku_f = _normalize_seat_mat(sku_seat)
    cand_f = _normalize_seat_mat(cand_seat)
    if sku_f and cand_f and sku_f != cand_f:
        return ["seat_material_mismatch"]
    return []


def _seal_material_score(sku_seal: str | None, cand_seal: str | None) -> list[str]:
    """Emite seal_material_mismatch cuando familias de sello difieren."""
    sku_f = _normalize_seat_mat(sku_seal)  # misma tabla de familias
    cand_f = _normalize_seat_mat(cand_seal)
    if sku_f and cand_f and sku_f != cand_f:
        return ["seal_material_mismatch"]
    return []


_GENDER_ALIASES: dict[str, str] = {
    "male-female": "male-female",
    "m-f": "male-female",
    "male/female": "male-female",
    "m/f": "male-female",
    "female-male": "male-female",
    "f-m": "male-female",
    "female-female": "female-female",
    "f-f": "female-female",
    "female to female": "female-female",
    "male-male": "male-male",
    "m-m": "male-male",
    "male to male": "male-male",
}


def _normalize_gender(text: str | None) -> str | None:
    if not text:
        return None
    return _GENDER_ALIASES.get(text.lower().strip())


def _connection_gender_score(
    sku_gender: str | None, cand_gender: str | None
) -> tuple[Decimal, list[str]]:
    """Score de género de conexión (entrada/salida M-F). Retorna (score, notes)."""
    sku_g = _normalize_gender(sku_gender)
    cand_g = _normalize_gender(cand_gender)
    if sku_g is None or cand_g is None:
        return Decimal("0.5"), []
    if sku_g == cand_g:
        return Decimal("1.0"), []
    return Decimal("0.0"), ["connection_gender_mismatch"]


# Campos clave cuya presencia mide qué tan bien se puede puntuar un candidato.
_COMPLETENESS_FIELDS = 6


def _data_completeness_score(candidate: dict[str, Any]) -> Decimal:
    """Porcentaje de campos clave presentes: 1.0=completo, 0.0=sin datos.

    Penaliza candidatos donde todos los scores serían 0.5 neutral por falta
    de datos, distinguiéndolos de candidatos con specs reales que confirman
    el match.
    """
    specs = candidate.get("specs") or {}
    fields = [
        candidate.get("material") or specs.get("material") or specs.get("material_type"),
        candidate.get("pn") or specs.get("pn") or specs.get("maximum_pressure"),
        (
            candidate.get("thread")
            or candidate.get("connection")
            or specs.get("thread")
            or specs.get("thread_type")
            or specs.get("connection_type")
        ),
        candidate.get("dn") or candidate.get("size") or specs.get("dn") or specs.get("size"),
        candidate.get("brand"),
        candidate.get("delivery_text"),
    ]
    present = sum(1 for f in fields if f)
    return Decimal(str(present)) / Decimal(str(_COMPLETENESS_FIELDS))


def compute_scoring(
    sku: dict[str, Any],
    candidate: dict[str, Any],
    *,
    weights: dict[str, Decimal] | None = None,
    material_normalizer: MaterialNormalizer | None = None,
) -> ScoringBreakdown:
    """Calcula score 0-100 del candidato vs SKU con reglas de taxonomía.

    Args:
        sku: dict con campos del producto MT. Campos usados:
            material, pn, dn, thread/connection, family, product_type/type,
            erp_name, norma, brand, product_materials (lista componentes).
        candidate: dict con campos del candidato + delivery_text.
        weights: override de pesos. Si None, se resuelve por perfil de familia.
        material_normalizer: instancia de MaterialNormalizer.
    """
    from app.services.matching.taxonomy_rules import get_profile

    family = sku.get("family") or ""
    profile = get_profile(family)
    w = weights or profile.weights or SCORING_WEIGHTS

    cand_specs = candidate.get("specs") or {}

    # ── Material ─────────────────────────────────────────────────────────────
    sku_material = sku.get("material")
    cand_material = candidate.get("material") or cand_specs.get("material")
    sku_components: list[dict[str, str]] = sku.get("product_materials") or []
    cand_components: dict[str, str] = {
        k: str(v) for k, v in (cand_specs.get("material_components") or {}).items() if v
    }
    mat_score = _material_score(
        sku_material,
        cand_material,
        norm=material_normalizer,
        sku_components=sku_components or None,
        cand_components=cand_components or None,
    )

    # ── PN ───────────────────────────────────────────────────────────────────
    sku_pn = sku.get("pn")
    cand_pn = candidate.get("pn") or cand_specs.get("pn")
    pn_score, pn_notes = _pn_score(sku_pn, cand_pn)

    # ── DN / Tamaño ──────────────────────────────────────────────────────────
    sku_dn = sku.get("dn")
    # Check top-level "size" too — _score_and_upsert may set it from thread_size
    # or title fallback without propagating it into cand_dict["specs"].
    cand_dn = (
        candidate.get("dn")
        or candidate.get("size")
        or cand_specs.get("dn")
        or cand_specs.get("size")
    )
    dn_score, dn_notes = _dn_score(sku_dn, cand_dn)

    # ── Estándar de rosca ─────────────────────────────────────────────────────
    sku_thread = sku.get("thread") or sku.get("connection")
    cand_thread = (
        candidate.get("thread")
        or candidate.get("connection")
        or cand_specs.get("thread")
        or cand_specs.get("connection")
    )
    thread_score, thread_notes = _thread_score(sku_thread, cand_thread)

    # ── Tipo de producto + mini qualifier ─────────────────────────────────────
    sku_type_text = sku.get("product_type") or sku.get("erp_name") or ""
    cand_title = candidate.get("title") or ""
    pt_score, pt_notes = _product_type_score(family, sku_type_text, cand_title, cand_specs)

    # ── Número de vías ────────────────────────────────────────────────────────
    ways_score, ways_notes = _ways_score(sku_type_text, cand_title, cand_specs)

    # ── Maneta (handle) — nota pool-relativa, sin peso propio ─────────────────
    # Textos del SKU: erp_name + product_type (contienen color/tipo de maneta)
    _sku_handle_text = (
        " ".join(
            filter(
                None,
                [
                    sku.get("erp_name"),
                    sku.get("product_type"),
                    sku.get("name_en"),
                ],
            )
        )
        or None
    )
    # Textos del candidato: título + description_text almacenado
    _cand_handle_text = (
        " ".join(
            filter(
                None,
                [
                    candidate.get("title"),
                    candidate.get("description_text"),
                    str(cand_specs.get("_description_text") or ""),
                ],
            )
        )
        or None
    )
    handle_score_val, handle_notes = _handle_score(
        sku.get("specs"),
        cand_specs,
        sku_text=_sku_handle_text,
        cand_text=_cand_handle_text,
    )

    # ── Actuador ──────────────────────────────────────────────────────────────
    sku_actuation = (sku.get("specs") or {}).get("actuation_type")
    cand_actuation = cand_specs.get("actuation_type")
    actuator_score, actuator_notes = _actuator_score(sku_actuation, cand_actuation)

    # ── Género de conexión (tipo entrada/salida M-F) ───────────────────────────
    sku_conn_gender = (sku.get("specs") or {}).get("end_connection_gender")
    cand_conn_gender = cand_specs.get("connection_gender") or cand_specs.get(
        "end_connection_gender"
    )
    gender_score, gender_notes = _connection_gender_score(sku_conn_gender, cand_conn_gender)

    # ── Clase de aplicación (residencial vs comercial) ────────────────────────
    sku_specs_dict = sku.get("specs") or {}
    _sku_app_title = sku.get("erp_name") or sku.get("product_type") or sku.get("name_en")
    sku_app_class = _detect_application_class(_sku_app_title, sku_specs_dict)
    # MT solo vende productos industriales/comerciales — default "commercial" si no hay datos
    if sku_app_class is None:
        sku_app_class = "commercial"
    cand_app_class = _detect_application_class(cand_title, cand_specs)
    app_score, app_notes = _application_class_score(sku_app_class, cand_app_class)

    # ── Bore type (full bore / reduced bore) — nota pool-relativa ────────────
    sku_bore = (sku.get("specs") or {}).get("bore_type")
    cand_bore = cand_specs.get("bore_type")
    bore_notes = _bore_type_score(sku_bore, cand_bore)

    # ── Asiento (seat material) — nota pool-relativa ───────────────────────────
    sku_seat = (sku.get("specs") or {}).get("seat_material")
    cand_seat = cand_specs.get("seat_material")
    seat_notes = _seat_material_score(sku_seat, cand_seat)

    # ── Sello (seal material) — nota pool-relativa ────────────────────────────
    sku_seal = (sku.get("specs") or {}).get("seal_material")
    cand_seal = cand_specs.get("seal_material")
    seal_notes = _seal_material_score(sku_seal, cand_seal)

    # ── Norma / estándar ──────────────────────────────────────────────────────
    sku_norma = sku.get("norma") or (sku.get("specs") or {}).get("norma")
    cand_norma = candidate.get("norma") or cand_specs.get("norma")
    norma_s = _norma_score(sku_norma, cand_norma)

    # ── Brand tier ────────────────────────────────────────────────────────────
    brand_s = _brand_score(sku.get("brand"), candidate.get("brand"))

    # ── Delivery ──────────────────────────────────────────────────────────────
    delivery_s = _delivery_score(candidate.get("delivery_text"))

    # ── Completitud de datos del candidato ───────────────────────────────────
    completeness_s = _data_completeness_score(candidate)

    dim_scores: dict[str, Decimal] = {
        "material": mat_score,
        "pn": pn_score,
        "dn": dn_score,
        "product_type": pt_score,
        "thread_standard": thread_score,
        "ways": ways_score,
        "norma": norma_s,
        "brand_tier": brand_s,
        "delivery": delivery_s,
        "data_completeness": completeness_s,
        "actuator": actuator_score,
        "application_class": app_score,
        "connection_gender": gender_score,
        "handle": handle_score_val,
    }

    weighted = Decimal("0")
    for dim, raw in dim_scores.items():
        dim_w = w.get(dim, Decimal("0"))
        weighted += raw * dim_w

    score_int = int(_round(weighted * Decimal("100"), 0))
    score_int = max(0, min(100, score_int))

    breakdown = {dim: float(_round(s, 4)) for dim, s in dim_scores.items()}
    weights_out = {dim: float(w.get(dim, Decimal("0"))) for dim in dim_scores}

    # Acumular todas las notas de los sub-scorers
    notes: list[str] = list(
        pn_notes
        + dn_notes
        + thread_notes
        + pt_notes
        + ways_notes
        + handle_notes
        + actuator_notes
        + gender_notes
        + bore_notes
        + seat_notes
        + seal_notes
        + app_notes
    )
    if mat_score == Decimal("0.0") and (sku_material or cand_material):
        notes.append("material_mismatch")
    elif sku_components and cand_material and not cand_components and material_normalizer:
        # Cuando el SKU tiene componentes pero el candidato sólo tiene material plano,
        # el score de componentes usa penalización leve (0.4) para partes desconocidas
        # y mat_score nunca llega a 0.0. Detectamos incompatibilidad comparando
        # el material del body del SKU contra el material plano del candidato.
        _sku_body = next(
            (
                r.get("material")
                for r in sku_components
                if (r.get("component") or "").lower() == "body"
            ),
            sku_material,
        )
        if _sku_body and not material_normalizer.same_family(_sku_body, cand_material):
            notes.append("material_mismatch")

    return ScoringBreakdown(
        score=score_int,
        breakdown=breakdown,
        weights=weights_out,
        notes=notes,
    )
