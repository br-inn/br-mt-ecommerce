"""Golden numbers v5.1 — bundling psicológico + rounding tiers.

Implementación firmada por Paula (Sprint 0 — `sprint0-v51-rules-extraction.md`).

Reglas de bundling psicológico para precios AED:

- Tier 1 (≤ 10 AED): snap al `.49` o `.99` más cercano dentro de ±0.30 AED.
- Tier 2 (10 < AED ≤ 100): snap al `.95` o `.99` (precio percibido más caro pero
  redondo). Tolerancia ±0.30 AED.
- Tier 3 (100 < AED ≤ 1.000): snap al múltiplo de 5 (.95) o al `.99` final.
  Tolerancia ±0.50 AED.
- Tier 4 (> 1.000 AED): snap al múltiplo de 10 (.99 al final). Tolerancia ±2 AED.

Override flags soportados en `apply_golden_numbers`:

- `disable_bundling`: bypass total, retorna `raw` con redondeo half-up a 2 dec.
- `bundle_strategy`: fuerza estrategia (`.49`, `.95`, `.99`, `auto`).
- `tolerance_override`: override del umbral de snap (en AED).

ADR-069 — "Estrategia bundling psicológico AED" — documenta elección de tier
por canal:
- ``amazon_uae`` / ``noon_uae``: estrategia `auto` (.49/.95/.99 por tier).
- ``b2c_direct``: `.99` (más agresivo retail).
- ``b2b_direct``: `disable_bundling=True` (precios netos sin bundling).
- ``marketplace_listing``: `auto`.

Convención: todos los cálculos en `Decimal`. Outputs son `Decimal` con 2
decimales de cuantización. JSON-safe via `str()` en breakdown.
"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import ROUND_HALF_UP, Decimal
from typing import Literal

__all__ = [
    "BUNDLING_STRATEGIES",
    "TIER_CONFIG",
    "GoldenTier",
    "apply_golden_numbers",
    "channel_default_strategy",
    "round_half_up",
    "snap_to_tier",
]


BundleStrategy = Literal["auto", ".49", ".95", ".99", "none"]

BUNDLING_STRATEGIES: tuple[str, ...] = ("auto", ".49", ".95", ".99", "none")


@dataclass(frozen=True)
class GoldenTier:
    """Configuración de un tier de bundling.

    `endings` es la lista de "terminaciones" (parte fraccional o múltiplo
    permitido). Para tiers con múltiplos discretos (e.g. múltiplos de 5), se
    expresa como Decimal '5.00' / '10.00' indicando el módulo + el `.99`
    (terminación) que se aplica al final.
    """

    name: str
    upper_bound: Decimal  # exclusive: tier aplica si raw <= upper_bound
    endings: tuple[Decimal, ...]  # decimales válidos (e.g. 0.49, 0.99)
    modulus: Decimal | None  # si no None, snap al múltiplo del modulus
    tolerance: Decimal


# Tabla de tiers — orden estricto por upper_bound ascendente.
TIER_CONFIG: tuple[GoldenTier, ...] = (
    GoldenTier(
        name="tier_1_small",
        upper_bound=Decimal("10.00"),
        endings=(Decimal("0.49"), Decimal("0.99")),
        modulus=None,
        tolerance=Decimal("0.30"),
    ),
    GoldenTier(
        name="tier_2_medium",
        upper_bound=Decimal("100.00"),
        endings=(Decimal("0.95"), Decimal("0.99")),
        modulus=None,
        tolerance=Decimal("0.30"),
    ),
    GoldenTier(
        name="tier_3_large",
        upper_bound=Decimal("1000.00"),
        endings=(Decimal("0.95"), Decimal("0.99")),
        modulus=Decimal("5.00"),
        tolerance=Decimal("0.50"),
    ),
    GoldenTier(
        name="tier_4_xlarge",
        upper_bound=Decimal("999999999.00"),
        endings=(Decimal("0.99"),),
        modulus=Decimal("10.00"),
        tolerance=Decimal("2.00"),
    ),
)


_CHANNEL_DEFAULTS: dict[str, BundleStrategy] = {
    "amazon_uae": "auto",
    "noon_uae": "auto",
    "b2c_direct": ".99",
    "b2b_direct": "none",
    "marketplace_listing": "auto",
}


def channel_default_strategy(channel_code: str | None) -> BundleStrategy:
    """Devuelve la estrategia default configurada por canal (ADR-069)."""
    if channel_code is None:
        return "auto"
    return _CHANNEL_DEFAULTS.get(channel_code, "auto")


def round_half_up(value: Decimal | float | int | str, places: int = 2) -> Decimal:
    """Redondeo half-up — Excel/v5.1 compatible."""
    if not isinstance(value, Decimal):
        value = Decimal(str(value))
    quant = Decimal("1").scaleb(-places)
    return value.quantize(quant, rounding=ROUND_HALF_UP)


def _select_tier(raw: Decimal) -> GoldenTier:
    """Selecciona el primer tier cuyo upper_bound ≥ raw."""
    for tier in TIER_CONFIG:
        if raw <= tier.upper_bound:
            return tier
    return TIER_CONFIG[-1]


def _candidates_for_tier(raw: Decimal, tier: GoldenTier) -> list[Decimal]:
    """Genera los candidatos a snap dentro del tier, dado el `raw`.

    Para tiers con `modulus`, se generan candidatos en torno al múltiplo más
    cercano (anterior, actual, siguiente) combinados con cada terminación.
    Para tiers sin modulus, se generan candidatos por parte entera ±1.
    """
    candidates: list[Decimal] = []
    if tier.modulus is not None and tier.modulus > 0:
        # múltiplo más cercano (e.g. 5, 10) — buscamos floor / ceil
        base = (raw // tier.modulus) * tier.modulus
        anchors = (base, base + tier.modulus, base - tier.modulus)
        for anchor in anchors:
            if anchor < 0:
                continue
            for ending in tier.endings:
                # 105 + 0.99 = 105.99 ; pero queremos 104.99 si la terminación
                # es .99 y modulus 5: usamos anchor - 0.01 truco (modulus_n - 0.01)
                # Reformulamos: candidato = (anchor - modulus) + (modulus - 1) + ending
                # Más simple: si ending in {0.95, 0.99}, candidato = anchor - 1 + ending
                # cuando modulus es 5, anchor-1+.99 = base+4.99 ≈ siguiente "redondo"
                cand_a = anchor - Decimal("1") + ending  # e.g. 104.99
                cand_b = anchor + ending  # e.g. 100.99 (anchor=100, ending=.99)
                if cand_a >= 0:
                    candidates.append(round_half_up(cand_a, 2))
                if cand_b >= 0:
                    candidates.append(round_half_up(cand_b, 2))
    else:
        integer_part = int(raw)
        # ±1 alrededor del entero del raw.
        for n in (integer_part - 1, integer_part, integer_part + 1):
            if n < 0:
                continue
            for ending in tier.endings:
                cand = Decimal(n) + ending
                candidates.append(round_half_up(cand, 2))
    # Únicos + ordenados.
    return sorted(set(candidates))


def snap_to_tier(
    raw: Decimal,
    *,
    strategy: BundleStrategy = "auto",
    tolerance_override: Decimal | None = None,
    tier: GoldenTier | None = None,
) -> tuple[Decimal, dict[str, str]]:
    """Aplica snap psicológico al `raw`.

    Returns:
        Tupla (precio_final, info) donde info trae:
            - tier_name: nombre del tier aplicado
            - strategy: estrategia efectiva
            - delta_aed: diferencia signed entre raw y final (precision 2)
            - applied: 'true' / 'false' indicando si hubo snap real
    """
    if strategy == "none":
        final = round_half_up(raw, 2)
        return final, {
            "tier_name": "none",
            "strategy": "none",
            "delta_aed": str(round_half_up(final - raw, 2)),
            "applied": "false",
        }

    selected_tier = tier or _select_tier(raw)
    tolerance = tolerance_override if tolerance_override is not None else selected_tier.tolerance

    # Filter endings by strategy (si no es 'auto').
    effective_endings: tuple[Decimal, ...]
    if strategy == "auto":
        effective_endings = selected_tier.endings
    else:
        forced = Decimal(strategy)
        effective_endings = (forced,)

    # Generamos candidatos respetando endings efectivos
    forced_tier = (
        selected_tier
        if strategy == "auto"
        else GoldenTier(
            name=selected_tier.name,
            upper_bound=selected_tier.upper_bound,
            endings=effective_endings,
            modulus=selected_tier.modulus,
            tolerance=selected_tier.tolerance,
        )
    )
    candidates = _candidates_for_tier(raw, forced_tier)
    if not candidates:
        final = round_half_up(raw, 2)
        return final, {
            "tier_name": selected_tier.name,
            "strategy": strategy,
            "delta_aed": "0.00",
            "applied": "false",
        }

    # Mejor candidato = el más cercano al raw dentro de la tolerancia.
    raw_q = round_half_up(raw, 2)
    best = min(candidates, key=lambda c: abs(c - raw_q))
    delta = abs(best - raw_q)
    if delta > tolerance:
        # No snap — fuera de tolerancia. Devolvemos raw round half-up.
        final = round_half_up(raw, 2)
        return final, {
            "tier_name": selected_tier.name,
            "strategy": strategy,
            "delta_aed": str(round_half_up(final - raw, 2)),
            "applied": "false",
            "rejected_best_candidate": str(best),
            "rejected_delta": str(delta),
        }

    return best, {
        "tier_name": selected_tier.name,
        "strategy": strategy,
        "delta_aed": str(round_half_up(best - raw_q, 2)),
        "applied": "true",
    }


def apply_golden_numbers(
    raw_price_aed: Decimal | float | int | str,
    *,
    channel_code: str | None = None,
    overrides: dict[str, object] | None = None,
) -> tuple[Decimal, dict[str, str]]:
    """API pública del módulo — ajusta `raw_price_aed` a su golden number.

    Args:
        raw_price_aed: precio crudo del motor (Decimal-castable).
        channel_code: canal (define la estrategia por defecto).
        overrides: dict con flags:
            - ``disable_bundling`` (bool): bypass.
            - ``bundle_strategy`` (BundleStrategy): fuerza estrategia.
            - ``tolerance_override`` (Decimal | float): override umbral.

    Returns:
        Tupla (precio_ajustado, info_breakdown).
    """
    raw = Decimal(str(raw_price_aed))
    overrides = overrides or {}

    if overrides.get("disable_bundling"):
        return round_half_up(raw, 2), {
            "tier_name": "disabled",
            "strategy": "none",
            "delta_aed": "0.00",
            "applied": "false",
            "override_disable_bundling": "true",
        }

    strategy: BundleStrategy = overrides.get("bundle_strategy") or channel_default_strategy(  # type: ignore[assignment]
        channel_code
    )
    if strategy not in BUNDLING_STRATEGIES:
        # Sanitización defensiva — caída a 'auto'.
        strategy = "auto"

    tolerance_override_raw = overrides.get("tolerance_override")
    tolerance_override = (
        Decimal(str(tolerance_override_raw)) if tolerance_override_raw is not None else None
    )

    return snap_to_tier(
        raw,
        strategy=strategy,  # type: ignore[arg-type]
        tolerance_override=tolerance_override,
    )
