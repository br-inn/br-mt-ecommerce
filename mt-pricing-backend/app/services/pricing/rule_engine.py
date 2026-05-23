"""Pricing rule engine v5.1 ported.

Las 18 reglas del motor v5.1 (ver
`_bmad-output/planning-artifacts/sprint0-v51-rules-extraction.md`) implementadas
de forma determinística y aisladas en métodos puros para que el comparador
(Sprint 4+) pueda inyectar `market` data sin reescribir el motor.

Convenciones:
- Todos los cálculos en `Decimal` para evitar errores de redondeo.
- Margen siempre se expresa en fracción decimal (0.5 = 50%) excepto en
  `min_margin_pct` (que el contrato exception_rules persiste como porcentaje
  numérico, ej. 5.0 = 5%).
- `breakdown` es JSON-serializable (Decimal → float) para persistencia JSONB.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from decimal import ROUND_HALF_UP, Decimal
from typing import Any

# --- Configuración global motor v5.1 (reflejo de `MT_Pricing_Run_Kit/src/config.py`) ---
EUR_TO_AED_DEFAULT = Decimal("4.29")

# Costes operativos por % sobre venta (fallback formula)
LOGISTICA_PCT = Decimal("0.05")
VAT_PCT = Decimal("0.05")
REFERRAL_PCT = Decimal("0.13")
BANCOS_PCT = Decimal("0.015")
DEVOLUCIONES_PCT = Decimal("0.04")

# FBA fee fallback por banda de peso (kg)
FBA_FEE_SMALL = Decimal("8.0")
FBA_FEE_MEDIUM = Decimal("14.0")
FBA_FEE_HEAVY = Decimal("35.0")
WEIGHT_SMALL_KG = Decimal("0.5")
WEIGHT_MEDIUM_KG = Decimal("2.0")

# Match thresholds (Amazon UAE scrape scoring)
MATCH_HIGH_THRESHOLD = 80
MATCH_LOW_THRESHOLD = 60

# Política agresiva
AGG_MATCH_PCT_OF_MEDIAN = Decimal("0.98")
AGG_MIN_MARGIN_OVER_PVP_MIN = Decimal("1.05")
AGG_NO_MATCH_MULT = Decimal("1.15")
MAX_PCT_OVER_MEDIAN = Decimal("1.20")

# Multiplicadores G2 (industrial sin match)
G2_MULTIPLIERS = {
    "default": Decimal("2.5"),
    "stainless": Decimal("2.8"),
    "cast_iron": Decimal("3.0"),
}

# Premium velocidad (delivery advantage)
DELIVERY_PREMIUM_HIGH_DAYS = 7
DELIVERY_PREMIUM_HIGH_PCT = Decimal("1.15")
DELIVERY_PREMIUM_MED_DAYS = 3
DELIVERY_PREMIUM_MED_PCT = Decimal("1.05")
MT_DELIVERY_DAYS = 2

# Channel multipliers (ajustes por canal — defaults)
CHANNEL_MULTIPLIERS: dict[str, Decimal] = {
    "amazon_uae": Decimal("1.00"),
    "noon_uae": Decimal("1.00"),
    "b2c_direct": Decimal(
        "0.95"
    ),  # Marketing propio menor → más margen, precio levemente competitivo
    "b2b_direct": Decimal("0.85"),  # Distribuidor descuenta volumen
    "marketplace_listing": Decimal("1.00"),
}


# ---------------------------------------------------------------------------
# Pricing result DTO
# ---------------------------------------------------------------------------
@dataclass
class PricingResult:
    """Output del motor — igualable 1:1 con `Price` row antes de persistir."""

    amount: Decimal
    pvp_min: Decimal | None
    margin_pct: Decimal  # fracción decimal (0.5 = 50%)
    rule_applied: str
    formula: str
    breakdown: dict[str, Any] = field(default_factory=dict)
    alerts: list[dict[str, Any]] = field(default_factory=list)
    fx_at: datetime = field(default_factory=lambda: datetime.now(tz=UTC))
    has_velocity_premium: bool = False
    has_critical_alerts: bool = False
    has_warnings: bool = False
    cap_applied: bool = False
    floor_applied: bool = False

    def to_jsonable_breakdown(self) -> dict[str, Any]:
        """Devuelve breakdown con Decimals convertidos a str (para JSONB)."""
        return _decimals_to_str(self.breakdown)

    def to_jsonable_alerts(self) -> list[dict[str, Any]]:
        return [_decimals_to_str(a) for a in self.alerts]


def _decimals_to_str(obj: Any) -> Any:
    """Convierte Decimals recursivamente a str para JSONB-safe."""
    if isinstance(obj, Decimal):
        return str(obj)
    if isinstance(obj, dict):
        return {k: _decimals_to_str(v) for k, v in obj.items()}
    if isinstance(obj, list):
        return [_decimals_to_str(v) for v in obj]
    return obj


def _round(value: Decimal | float, places: int = 2) -> Decimal:
    """Redondeo half-up — Excel-compatible."""
    if not isinstance(value, Decimal):
        value = Decimal(str(value))
    quant = Decimal("1").scaleb(-places)
    return value.quantize(quant, rounding=ROUND_HALF_UP)


# ---------------------------------------------------------------------------
# Engine
# ---------------------------------------------------------------------------
class PricingRuleEngine:
    """Motor v5.1 portado. Reglas determinísticas + alertas.

    Inputs (al método `calculate`):
        - product: dict-like con sku, family, subfamily, material, weight_kg, etc.
                   (cualquier objeto SQLAlchemy sirve via getattr).
        - channel: dict-like con code (str).
        - scheme: dict-like con code (FBA/FBM/DIRECT_B2C/DIRECT_B2B/MARKETPLACE).
        - cost: dict-like con total (Decimal/float), breakdown (dict),
                opcional master_data dict si se quiere usar regla
                `regla_pvp_min_excel_master`.
        - fx_rate: Decimal (EUR→AED si scheme retail UAE).
        - market: dict opcional con candidates_summary del comparador
                  (median_aed, best_score, delivery_advantage_days).
        - prev_price: dict opcional con margin_pct, amount del precio anterior
                      (para regla_alerts críticas).

    Output: PricingResult con amount, pvp_min, margin_pct, breakdown, alerts.
    """

    def __init__(
        self,
        eur_to_aed: Decimal | None = None,
        channel_multipliers: dict[str, Decimal] | None = None,
    ) -> None:
        self.fx_eur_aed = eur_to_aed or EUR_TO_AED_DEFAULT
        self.channel_multipliers = channel_multipliers or CHANNEL_MULTIPLIERS

    # ----------------------------------------------------------------------
    # 2.1 — regla_aed_to_eur
    # ----------------------------------------------------------------------
    def aed_to_eur(self, aed: Decimal) -> Decimal:
        return _round(aed / self.fx_eur_aed, 2)

    # ----------------------------------------------------------------------
    # 2.2 — regla_calcular_mediana
    # ----------------------------------------------------------------------
    @staticmethod
    def calculate_median(prices: list[Decimal | float]) -> Decimal | None:
        valid = [Decimal(str(p)) for p in prices if p and Decimal(str(p)) > 0]
        if not valid:
            return None
        valid.sort()
        n = len(valid)
        mid = n // 2
        if n % 2 == 1:
            return _round(valid[mid], 2)
        return _round((valid[mid - 1] + valid[mid]) / Decimal(2), 2)

    # ----------------------------------------------------------------------
    # 2.3 — regla_calcular_margen_pct
    # ----------------------------------------------------------------------
    @staticmethod
    def calc_margin_pct(pvp: Decimal, total_costes: Decimal | None) -> Decimal:
        if pvp <= 0 or total_costes is None:
            return Decimal("0")
        return _round((pvp - total_costes) / pvp, 4)

    # ----------------------------------------------------------------------
    # 2.5 — regla_fba_fee_fallback
    # ----------------------------------------------------------------------
    @staticmethod
    def get_fba_fee_fallback(weight_kg: Decimal | None, grupo: str) -> Decimal:
        if weight_kg is None:
            if "G2" in grupo.upper():
                return FBA_FEE_HEAVY
            return FBA_FEE_MEDIUM
        if weight_kg < WEIGHT_SMALL_KG:
            return FBA_FEE_SMALL
        if weight_kg < WEIGHT_MEDIUM_KG:
            return FBA_FEE_MEDIUM
        return FBA_FEE_HEAVY

    # ----------------------------------------------------------------------
    # 2.6 — regla_detect_g2_subtype
    # ----------------------------------------------------------------------
    @staticmethod
    def detect_g2_subtype(subfamilia: str | None, name: str | None) -> str:
        text_corpus = f"{subfamilia or ''} {name or ''}".lower()
        if any(t in text_corpus for t in ["inox", "stainless", "s.s.", " ss "]):
            return "stainless"
        if any(t in text_corpus for t in ["fundic", "cast iron", "hierro fund"]):
            return "cast_iron"
        return "default"

    # ----------------------------------------------------------------------
    # 2.4 — regla_recalculo_costes_dinamico
    # ----------------------------------------------------------------------
    @staticmethod
    def compute_costs_from_master(pvp: Decimal, master: dict[str, Any]) -> dict[str, Any]:
        """Refit operativo: % calibrados en Excel se aplican al PVP nuevo."""
        pvp_ref = Decimal(str(master.get("pvp_lanzamiento_aed") or 1))
        coste_base = Decimal(str(master.get("coste_aed_ud") or 0))
        arancel = Decimal(str(master.get("arancel_aed_ud") or 0))

        pcts: dict[str, Decimal] = {}
        component_keys = [
            ("referral_aed_ud", "referral_pct"),
            ("iva_aed_ud", "iva_pct"),
            ("ppc_aed_ud", "ppc_pct"),
            ("otros_aed_ud", "otros_pct"),
        ]
        for k_aed, k_pct in component_keys:
            valor_aed = master.get(k_aed)
            if valor_aed is not None and pvp_ref > 0:
                pcts[k_pct] = Decimal(str(valor_aed)) / pvp_ref
            else:
                pcts[k_pct] = Decimal("0")

        # Costes fijos (no escalan con PVP)
        fba = Decimal(str(master.get("fba_fee_aed_ud") or 0))
        envio_fc = Decimal(str(master.get("envio_fc_aed_ud") or 0))
        storage = Decimal(str(master.get("storage_aed_mes_ud") or 0))

        # Recalcular operativos
        referral_aed = pvp * pcts["referral_pct"]
        iva_aed = pvp * pcts["iva_pct"]
        ppc_aed = pvp * pcts["ppc_pct"]
        otros_aed = pvp * pcts["otros_pct"]

        operativos = referral_aed + iva_aed + ppc_aed + otros_aed + fba + envio_fc + storage
        total = coste_base + arancel + operativos

        return {
            "coste_base_aed": _round(coste_base, 4),
            "arancel_aed": _round(arancel, 4),
            "referral_aed": _round(referral_aed, 4),
            "iva_aed": _round(iva_aed, 4),
            "ppc_aed": _round(ppc_aed, 4),
            "otros_aed": _round(otros_aed, 4),
            "fba_fee_aed": _round(fba, 4),
            "envio_fc_aed": _round(envio_fc, 4),
            "storage_aed": _round(storage, 4),
            "operativos_aed": _round(operativos, 4),
            "total_costes_aed": _round(total, 4),
            "pcts": {k: str(v) for k, v in pcts.items()},
        }

    # ----------------------------------------------------------------------
    # 2.7 + 2.8 — regla_pvp_min_excel_master / regla_pvp_min_formula_global
    # ----------------------------------------------------------------------
    def compute_pvp_min(
        self,
        coste: Decimal,
        weight: Decimal | None,
        grupo: str,
        master: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        # RAMA 1 — Excel master (preferida)
        if master and master.get("pvp_min_viable_aed"):
            breakdown: dict[str, Any] = {}
            mapping = [
                ("coste_aed_ud", "coste_aed"),
                ("arancel_aed_ud", "arancel_aed"),
                ("referral_aed_ud", "referral_aed"),
                ("fba_fee_aed_ud", "fba_fee_aed"),
                ("iva_aed_ud", "iva_aed"),
                ("ppc_aed_ud", "ppc_aed"),
                ("otros_aed_ud", "otros_aed"),
                ("envio_fc_aed_ud", "envio_fc_aed"),
                ("storage_aed_mes_ud", "storage_aed_mes"),
            ]
            for k_excel, k_brk in mapping:
                if master.get(k_excel) is not None:
                    breakdown[k_brk] = _round(Decimal(str(master[k_excel])), 4)
            return {
                "pvp_min": _round(Decimal(str(master["pvp_min_viable_aed"])), 2),
                "total_costes": (
                    _round(Decimal(str(master["total_costes_aed_ud"])), 2)
                    if master.get("total_costes_aed_ud")
                    else None
                ),
                "breakdown": breakdown,
                "source": "excel_master",
            }

        # RAMA 2 — fórmula global
        if coste <= 0:
            return {
                "pvp_min": Decimal("0"),
                "total_costes": None,
                "breakdown": {},
                "source": "error",
                "error": "Coste invalido",
            }

        fba_fee = self.get_fba_fee_fallback(weight, grupo)
        logistica = coste * LOGISTICA_PCT
        numerador = coste + logistica + fba_fee

        pct_sobre_venta = VAT_PCT + REFERRAL_PCT + BANCOS_PCT + DEVOLUCIONES_PCT  # 0.235
        if pct_sobre_venta >= 1:
            return {
                "pvp_min": Decimal("0"),
                "source": "error",
                "error": "% suman ≥100%",
            }

        pvp_min_calc = numerador / (Decimal("1") - pct_sobre_venta)
        vat_aed = pvp_min_calc * VAT_PCT
        referral_aed = pvp_min_calc * REFERRAL_PCT
        bancos_aed = pvp_min_calc * BANCOS_PCT
        devol_aed = pvp_min_calc * DEVOLUCIONES_PCT
        total_costes = coste + logistica + fba_fee + vat_aed + referral_aed + bancos_aed + devol_aed

        return {
            "pvp_min": _round(pvp_min_calc, 2),
            "total_costes": _round(total_costes, 2),
            "breakdown": {
                "coste_aed": _round(coste, 4),
                "logistica_aed": _round(logistica, 4),
                "fba_fee_aed": _round(fba_fee, 4),
                "vat_aed": _round(vat_aed, 4),
                "referral_aed": _round(referral_aed, 4),
                "bancos_aed": _round(bancos_aed, 4),
                "devoluciones_aed": _round(devol_aed, 4),
            },
            "source": "formula_global",
        }

    # ----------------------------------------------------------------------
    # 2.9 — regla_analyze_candidates
    # ----------------------------------------------------------------------
    def analyze_candidates(self, candidates: list[dict[str, Any]] | None) -> dict[str, Any]:
        if not candidates:
            return {
                "median_aed": None,
                "best_score": 0,
                "has_match": False,
                "has_low_match": False,
                "delivery_advantage_days": None,
                "n_total": 0,
            }
        prices = [c.get("price_aed") for c in candidates if c.get("price_aed")]
        median = self.calculate_median(prices)
        scores = [c.get("score_v2") or c.get("score") or 0 for c in candidates]
        best_score = max(scores) if scores else 0
        has_match = best_score >= MATCH_HIGH_THRESHOLD
        has_low_match = MATCH_LOW_THRESHOLD <= best_score < MATCH_HIGH_THRESHOLD

        # Delivery advantage
        advantages: list[Decimal] = []
        n_china = n_uae = n_prime = 0
        mt_days = Decimal(MT_DELIVERY_DAYS)
        for c in candidates:
            d_min = c.get("delivery_days_min")
            d_max = c.get("delivery_days_max")
            if d_min is not None and d_max is not None:
                comp_avg = (Decimal(str(d_min)) + Decimal(str(d_max))) / Decimal(2)
                advantages.append(comp_avg - mt_days)
            origin = (c.get("delivery_origin") or "").upper()
            if origin in {"CN", "CHINA"}:
                n_china += 1
            elif origin in {"UAE", "AE"}:
                n_uae += 1
            if c.get("prime_eligible"):
                n_prime += 1
        delivery_adv: Decimal | None = (
            sum(advantages) / Decimal(len(advantages)) if advantages else None
        )

        return {
            "median_aed": median,
            "best_score": best_score,
            "has_match": has_match,
            "has_low_match": has_low_match,
            "delivery_advantage_days": delivery_adv,
            "n_from_china": n_china,
            "n_from_uae": n_uae,
            "n_prime": n_prime,
            "n_total": len(candidates),
        }

    # ----------------------------------------------------------------------
    # 2.10 - 2.14 — apply_aggressive_policy (premium velocidad + match + g2)
    # ----------------------------------------------------------------------
    def apply_aggressive_policy(
        self,
        market: dict[str, Any],
        pvp_min: Decimal,
        grupo: str,
        subfamilia: str | None,
        name: str | None,
        coste: Decimal,
    ) -> dict[str, Any]:
        median = market.get("median_aed")
        delivery_adv = market.get("delivery_advantage_days")
        has_match = market.get("has_match", False)
        has_low_match = market.get("has_low_match", False)

        # 2.10 — Premium velocidad ALTA / MEDIA
        if median and (has_match or has_low_match) and delivery_adv is not None:
            if delivery_adv >= Decimal(DELIVERY_PREMIUM_HIGH_DAYS):
                pvp = max(median * DELIVERY_PREMIUM_HIGH_PCT, pvp_min * AGG_MIN_MARGIN_OVER_PVP_MIN)
                return {
                    "pvp_target": _round(pvp, 2),
                    "rule": "premium_velocidad_alta",
                    "formula": f"mediana × {DELIVERY_PREMIUM_HIGH_PCT} — competidores +{delivery_adv}d más lentos",
                    "delivery_premium_applied": True,
                    "delivery_advantage_days": delivery_adv,
                }
            if delivery_adv >= Decimal(DELIVERY_PREMIUM_MED_DAYS):
                pvp = max(median * DELIVERY_PREMIUM_MED_PCT, pvp_min * AGG_MIN_MARGIN_OVER_PVP_MIN)
                return {
                    "pvp_target": _round(pvp, 2),
                    "rule": "premium_velocidad_media",
                    "formula": f"mediana × {DELIVERY_PREMIUM_MED_PCT} — ventaja entrega {delivery_adv}d",
                    "delivery_premium_applied": True,
                    "delivery_advantage_days": delivery_adv,
                }

        # 2.11 — Match alto
        if has_match and median:
            pvp = max(median * AGG_MATCH_PCT_OF_MEDIAN, pvp_min * AGG_MIN_MARGIN_OVER_PVP_MIN)
            return {
                "pvp_target": _round(pvp, 2),
                "rule": "aggressive_match_high",
                "formula": "max(mediana × 0.98, PVP_MIN × 1.05)",
                "delivery_premium_applied": False,
            }

        # 2.12 — Match incierto
        if has_low_match and median:
            pvp = max(median * Decimal("1.10"), pvp_min * Decimal("1.10"))
            return {
                "pvp_target": _round(pvp, 2),
                "rule": "aggressive_match_low",
                "formula": "max(mediana × 1.10, PVP_MIN × 1.10) — match incierto",
                "delivery_premium_applied": False,
            }

        # 2.13 — G2 sin match
        if "G2" in grupo.upper():
            subtype = self.detect_g2_subtype(subfamilia, name)
            mult = G2_MULTIPLIERS[subtype]
            pvp = max(coste * mult, pvp_min * AGG_NO_MATCH_MULT)
            return {
                "pvp_target": _round(pvp, 2),
                "rule": f"aggressive_g2_no_match_{subtype}",
                "formula": f"max(coste × {mult}, PVP_MIN × 1.15)",
                "delivery_premium_applied": False,
            }

        # 2.14 — G1 sin match (fallback)
        pvp = pvp_min * AGG_NO_MATCH_MULT
        return {
            "pvp_target": _round(pvp, 2),
            "rule": "aggressive_g1_no_match",
            "formula": "PVP_MIN × 1.15 — G1 sin referencia",
            "delivery_premium_applied": False,
        }

    # ----------------------------------------------------------------------
    # 2.16 — regla_cap_superior_y_floor
    # ----------------------------------------------------------------------
    @staticmethod
    def apply_cap_and_floor(
        pvp_target: Decimal,
        median: Decimal | None,
        pvp_min: Decimal,
        delivery_premium_applied: bool,
    ) -> tuple[Decimal, bool, bool, list[dict[str, Any]]]:
        alerts: list[dict[str, Any]] = []
        cap_applied = False
        floor_applied = False
        pvp = pvp_target

        # Cap arriba
        if median and pvp > median * MAX_PCT_OVER_MEDIAN and not delivery_premium_applied:
            cap_value = median * MAX_PCT_OVER_MEDIAN
            alerts.append(
                {
                    "severity": "warning",
                    "code": "cap_applied",
                    "message": f"Cap aplicado: {pvp} > mediana×1.20 ({_round(cap_value, 2)})",
                }
            )
            pvp = _round(cap_value, 2)
            cap_applied = True

        # Floor estricto
        if pvp < pvp_min:
            alerts.append(
                {
                    "severity": "critical",
                    "code": "floor_forced",
                    "message": f"FLOOR forzado: target {pvp} < PVP_MIN {pvp_min}",
                }
            )
            pvp = pvp_min
            floor_applied = True

        return pvp, cap_applied, floor_applied, alerts

    # ----------------------------------------------------------------------
    # 2.17 — regla_alertas_automaticas
    # ----------------------------------------------------------------------
    @staticmethod
    def collect_alerts(
        market: dict[str, Any],
        policy: dict[str, Any],
        pvp_min: Decimal,
        pvp: Decimal,
        median: Decimal | None,
        scheme_min_margin: Decimal | None,
        margin_pct: Decimal,
    ) -> list[dict[str, Any]]:
        alerts: list[dict[str, Any]] = []

        if market.get("has_low_match"):
            alerts.append(
                {
                    "severity": "warning",
                    "code": "match_low_quality",
                    "message": f"Match calidad media (score={market.get('best_score')})",
                }
            )

        if median and pvp_min > median * Decimal("1.05"):
            alerts.append(
                {
                    "severity": "warning",
                    "code": "pvp_min_above_median",
                    "message": f"Mediana ({median}) bajo PVP_MIN×1.05 — margen ajustado",
                }
            )

        if policy.get("delivery_premium_applied"):
            adv = policy.get("delivery_advantage_days")
            alerts.append(
                {
                    "severity": "info",
                    "code": "velocity_premium",
                    "message": f"Premium velocidad — competidores +{adv}d más lentos",
                }
            )

        if median and pvp_min > median * MAX_PCT_OVER_MEDIAN:
            alerts.append(
                {
                    "severity": "critical",
                    "code": "product_uncompetitive",
                    "message": f"PVP_MIN ({pvp_min}) > mediana × cap ({median}×{MAX_PCT_OVER_MEDIAN}) — producto inviable",
                }
            )

        # Min margin enforcement
        if scheme_min_margin is not None and margin_pct * Decimal("100") < scheme_min_margin:
            alerts.append(
                {
                    "severity": "critical",
                    "code": "margin_below_min",
                    "message": (
                        f"Margen {margin_pct * 100:.2f}% por debajo del mínimo "
                        f"{scheme_min_margin}% configurado"
                    ),
                }
            )

        return alerts

    # ----------------------------------------------------------------------
    # 2.18 — regla_canal_recomendado_passthrough (no-op por ahora — viene del Excel)
    # ----------------------------------------------------------------------
    @staticmethod
    def canal_recomendado_passthrough(master: dict[str, Any] | None) -> dict[str, Any]:
        if not master:
            return {}
        return {
            "canal_recomendado": master.get("canal_recomendado"),
            "estado_fba_excel": master.get("estado_fba"),
            "roi_fba_excel": master.get("roi_fba"),
            "margen_fbm_excel": master.get("margen_fbm"),
        }

    # ----------------------------------------------------------------------
    # ENTRY POINT — calculate
    # ----------------------------------------------------------------------
    def calculate(
        self,
        product: Any,
        channel: Any,
        scheme: Any,
        cost: Any,
        fx_rate: Decimal | None = None,
        prev_price: Any | None = None,
        market: dict[str, Any] | None = None,
        master_data: dict[str, Any] | None = None,
        scheme_min_margin: Decimal | None = None,
        scenario_overrides: dict[str, Any] | None = None,
    ) -> PricingResult:
        """Orquesta las 18 reglas y devuelve `PricingResult`.

        `scenario_overrides` permite el simulador what-if pisar coste/median/etc
        sin tocar BD.
        """

        def g(obj: Any, attr: str, default: Any = None) -> Any:
            if obj is None:
                return default
            if isinstance(obj, dict):
                return obj.get(attr, default)
            return getattr(obj, attr, default)

        sku = g(product, "sku") or g(product, "id")
        family = g(product, "family") or ""
        subfamily = g(product, "subfamily")
        material = g(product, "material") or ""
        weight_raw = g(product, "weight")
        weight: Decimal | None = Decimal(str(weight_raw)) if weight_raw is not None else None
        name = g(product, "name_en")

        # Determinar grupo G1/G2 — heurística simple (industrial = G2)
        grupo = "G2" if (family or "").upper() == "INDUSTRIAL" else "G1"
        if scenario_overrides and scenario_overrides.get("grupo"):
            grupo = scenario_overrides["grupo"]

        # Coste
        cost_breakdown = g(cost, "breakdown") or {}
        coste_total_raw = g(cost, "total")
        coste = Decimal(str(coste_total_raw or 0))
        if scenario_overrides and scenario_overrides.get("cost_total") is not None:
            coste = Decimal(str(scenario_overrides["cost_total"]))

        # FX
        fx = fx_rate or self.fx_eur_aed
        if scenario_overrides and scenario_overrides.get("fx_rate"):
            fx = Decimal(str(scenario_overrides["fx_rate"]))

        # Master Excel data (opcional — permite regla excel_master)
        if scenario_overrides and scenario_overrides.get("master_data"):
            master_data = scenario_overrides["master_data"]

        # Channel multiplier
        channel_code = g(channel, "code") or "amazon_uae"
        ch_mult = self.channel_multipliers.get(channel_code, Decimal("1.0"))

        # PVP_MIN (regla 2.7 / 2.8)
        pvp_min_result = self.compute_pvp_min(coste, weight, grupo, master_data)
        pvp_min = pvp_min_result["pvp_min"]
        breakdown_pvp_min = pvp_min_result.get("breakdown") or {}
        pvp_min_source = pvp_min_result.get("source")

        # Market analysis
        if market is None and scenario_overrides:
            market = scenario_overrides.get("market")
        market_summary = market or self.analyze_candidates(None)
        if scenario_overrides and scenario_overrides.get("median_aed"):
            market_summary = {
                **market_summary,
                "median_aed": Decimal(str(scenario_overrides["median_aed"])),
            }

        # Política agresiva (2.10-2.14)
        policy = self.apply_aggressive_policy(
            market=market_summary,
            pvp_min=pvp_min,
            grupo=grupo,
            subfamilia=subfamily,
            name=name,
            coste=coste,
        )
        pvp_target = policy["pvp_target"]

        # Channel multiplier (no aplica a B2C/B2B en muchos casos pero lo dejamos como ajuste fino)
        if ch_mult != Decimal("1.0"):
            pvp_target = _round(pvp_target * ch_mult, 2)

        # Cap + floor (2.16)
        pvp_final, cap_applied, floor_applied, cap_alerts = self.apply_cap_and_floor(
            pvp_target=pvp_target,
            median=market_summary.get("median_aed"),
            pvp_min=pvp_min,
            delivery_premium_applied=policy.get("delivery_premium_applied", False),
        )

        # Recalcular total_costes para PVP final via master refit (regla 2.4) si hay master
        total_costes = pvp_min_result.get("total_costes") or coste
        breakdown_final: dict[str, Any] = {
            "pvp_min_breakdown": _decimals_to_str(breakdown_pvp_min),
            "pvp_min_source": pvp_min_source,
            "policy_rule": policy["rule"],
            "policy_formula": policy["formula"],
            "channel_multiplier": str(ch_mult),
            "cost_breakdown": cost_breakdown,
        }
        if master_data:
            refit = self.compute_costs_from_master(pvp_final, master_data)
            total_costes = refit["total_costes_aed"]
            breakdown_final["refit"] = _decimals_to_str(refit)
        breakdown_final["pvp_target_pre_cap"] = str(pvp_target)
        breakdown_final["pvp_aed_final"] = str(pvp_final)
        breakdown_final["pvp_eur_final"] = str(self.aed_to_eur(pvp_final))
        breakdown_final["fx_eur_aed"] = str(fx)

        # Margen (2.3)
        margin_pct = self.calc_margin_pct(pvp_final, total_costes)

        # Alerts (2.17)
        alerts = list(cap_alerts)
        alerts.extend(
            self.collect_alerts(
                market=market_summary,
                policy=policy,
                pvp_min=pvp_min,
                pvp=pvp_final,
                median=market_summary.get("median_aed"),
                scheme_min_margin=scheme_min_margin,
                margin_pct=margin_pct,
            )
        )

        # Detección de cambio de régimen vs prev_price (regla soft — alerts info)
        if prev_price is not None:
            prev_rule = g(prev_price, "rule_applied")
            if prev_rule and prev_rule != policy["rule"]:
                alerts.append(
                    {
                        "severity": "info",
                        "code": "rule_changed",
                        "message": f"Regla cambió: {prev_rule} → {policy['rule']}",
                    }
                )
            prev_margin_raw = g(prev_price, "margin_pct")
            if prev_margin_raw is not None:
                prev_margin = Decimal(str(prev_margin_raw))
                delta = abs(margin_pct - prev_margin) * Decimal("100")
                breakdown_final["prev_margin_pct"] = str(prev_margin)
                breakdown_final["margin_delta_pct"] = str(delta)

        has_critical = any(a.get("severity") == "critical" for a in alerts)
        has_warnings = any(a.get("severity") == "warning" for a in alerts)
        has_velocity_premium = policy["rule"].startswith("premium_velocidad")

        # Regla 2.18 — passthrough metadata
        breakdown_final.update(_decimals_to_str(self.canal_recomendado_passthrough(master_data)))

        return PricingResult(
            amount=pvp_final,
            pvp_min=pvp_min,
            margin_pct=margin_pct,
            rule_applied=policy["rule"],
            formula=policy["formula"],
            breakdown=breakdown_final,
            alerts=alerts,
            fx_at=datetime.now(tz=UTC),
            has_velocity_premium=has_velocity_premium,
            has_critical_alerts=has_critical,
            has_warnings=has_warnings,
            cap_applied=cap_applied,
            floor_applied=floor_applied,
        )


__all__ = ["PricingResult", "PricingRuleEngine"]
