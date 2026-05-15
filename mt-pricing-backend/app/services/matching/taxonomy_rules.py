"""Taxonomy-aware matching rules — blockers y pesos por familia de producto.

Para cada familia define:
  hard_blockers — notas de scoring que fuerzan kind=unknown sin importar score.
  weights       — pesos de dimensiones que suman 1.0 (override de SCORING_WEIGHTS).

Las familias sin perfil caen al perfil ``_default`` (blockers históricos).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from decimal import Decimal


@dataclass(frozen=True)
class TaxonomyProfile:
    hard_blockers: frozenset[str]
    weights: dict[str, Decimal] = field(default_factory=dict)


# ---------------------------------------------------------------------------
# Blocker sets reutilizables
# ---------------------------------------------------------------------------
_BASE_VALVE_BLOCKERS: frozenset[str] = frozenset({
    "dn_mismatch",
    "material_mismatch",
    "product_type_mismatch",
    "ways_mismatch",
    "pn_below_sku_requirement",
    "pn_too_far_above",
})

# ball_valve añade mini_mismatch (mini/micro son productos distintos de precio incomparable)
_FULL_VALVE_BLOCKERS: frozenset[str] = _BASE_VALVE_BLOCKERS | frozenset({
    "mini_mismatch",
})

# ---------------------------------------------------------------------------
# Pesos por familia — suman 1.0
# ---------------------------------------------------------------------------
_VALVE_WEIGHTS: dict[str, Decimal] = {
    "material":          Decimal("0.17"),
    "pn":                Decimal("0.11"),
    "dn":                Decimal("0.17"),
    "product_type":      Decimal("0.11"),
    "thread_standard":   Decimal("0.14"),
    "ways":              Decimal("0.05"),
    "norma":             Decimal("0.04"),
    "brand_tier":        Decimal("0.07"),
    "delivery":          Decimal("0.06"),
    "data_completeness": Decimal("0.08"),
}

_STRAINER_WEIGHTS: dict[str, Decimal] = {
    "material":          Decimal("0.18"),
    "pn":                Decimal("0.11"),
    "dn":                Decimal("0.18"),
    "product_type":      Decimal("0.14"),
    "thread_standard":   Decimal("0.14"),
    "ways":              Decimal("0.00"),
    "norma":             Decimal("0.05"),
    "brand_tier":        Decimal("0.07"),
    "delivery":          Decimal("0.05"),
    "data_completeness": Decimal("0.08"),
}

_GAUGE_WEIGHTS: dict[str, Decimal] = {
    "material":          Decimal("0.18"),
    "pn":                Decimal("0.19"),
    "dn":                Decimal("0.09"),
    "product_type":      Decimal("0.18"),
    "thread_standard":   Decimal("0.09"),
    "ways":              Decimal("0.00"),
    "norma":             Decimal("0.05"),
    "brand_tier":        Decimal("0.07"),
    "delivery":          Decimal("0.07"),
    "data_completeness": Decimal("0.08"),
}

_DEFAULT_WEIGHTS: dict[str, Decimal] = {
    "material":          Decimal("0.18"),
    "pn":                Decimal("0.14"),
    "dn":                Decimal("0.00"),
    "product_type":      Decimal("0.00"),
    "thread_standard":   Decimal("0.14"),
    "ways":              Decimal("0.00"),
    "norma":             Decimal("0.14"),
    "brand_tier":        Decimal("0.18"),
    "delivery":          Decimal("0.14"),
    "data_completeness": Decimal("0.08"),
}

# ---------------------------------------------------------------------------
# Registro de perfiles
# ---------------------------------------------------------------------------
TAXONOMY_PROFILES: dict[str, TaxonomyProfile] = {
    # ── Válvulas de bola ─────────────────────────────────────────────────────
    "ball_valve":   TaxonomyProfile(_FULL_VALVE_BLOCKERS, _VALVE_WEIGHTS),
    "valves_ball":  TaxonomyProfile(_FULL_VALVE_BLOCKERS, _VALVE_WEIGHTS),
    "HIDROSANITARIO": TaxonomyProfile(_FULL_VALVE_BLOCKERS, _VALVE_WEIGHTS),
    # ── Otras válvulas ───────────────────────────────────────────────────────
    "gate_valve":      TaxonomyProfile(_BASE_VALVE_BLOCKERS, _VALVE_WEIGHTS),
    "globe_valve":     TaxonomyProfile(_BASE_VALVE_BLOCKERS, _VALVE_WEIGHTS),
    "check_valve":     TaxonomyProfile(_BASE_VALVE_BLOCKERS, _VALVE_WEIGHTS),
    "butterfly_valve": TaxonomyProfile(_BASE_VALVE_BLOCKERS, _VALVE_WEIGHTS),
    # ── Filtros / strainers ──────────────────────────────────────────────────
    "strainer":  TaxonomyProfile(_BASE_VALVE_BLOCKERS, _STRAINER_WEIGHTS),
    "FILTROS":   TaxonomyProfile(_BASE_VALVE_BLOCKERS, _STRAINER_WEIGHTS),
    # ── Manómetros ───────────────────────────────────────────────────────────
    "pressure_gauge": TaxonomyProfile(
        frozenset({"product_type_mismatch", "pn_below_sku_requirement", "pn_too_far_above"}),
        _GAUGE_WEIGHTS,
    ),
    "MANOMETROS":  TaxonomyProfile(
        frozenset({"product_type_mismatch", "pn_below_sku_requirement", "pn_too_far_above"}),
        _GAUGE_WEIGHTS,
    ),
    # ── Default ──────────────────────────────────────────────────────────────
    "_default": TaxonomyProfile(
        frozenset({"pn_below_sku_requirement", "thread_mismatch", "material_mismatch"}),
        _DEFAULT_WEIGHTS,
    ),
}


def get_profile(family: str | None) -> TaxonomyProfile:
    """Devuelve el perfil de taxonomía para una familia. Fallback a _default."""
    if family:
        p = TAXONOMY_PROFILES.get(family) or TAXONOMY_PROFILES.get(family.upper())
        if p:
            return p
    return TAXONOMY_PROFILES["_default"]
