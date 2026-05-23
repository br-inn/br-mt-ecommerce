"""ExceptionEvaluator — decide auto_approved vs pending_review.

Reglas de evaluación (en orden):
1. Si no hay precio anterior → auto_approved (primera vez).
2. Si delta margin > rule.margin_threshold_pct → pending_review.
3. Si new_price.margin_pct < rule.min_margin_pct → pending_review.
4. Si hay alerts severity=critical → pending_review.
5. Si rule_applied cambió respecto a prev → pending_review.
6. Si delta FX > rule.fx_swing_threshold_pct → pending_review.
7. Default → auto_approved.

Las `ExceptionRule` se filtran por (channel_id, scheme_code) — primero las
específicas, luego las globales (NULL).
"""

from __future__ import annotations

from decimal import Decimal
from typing import Any

from app.db.models.pricing import ExceptionRule
from app.services.pricing.rule_engine import PricingResult


class ExceptionEvaluator:
    """Decide initial status ('auto_approved' | 'pending_review') de un Price."""

    @staticmethod
    def _resolve_rules_for(
        active_rules: list[ExceptionRule],
        channel_id: Any,
        scheme_code: str,
    ) -> dict[str, Decimal]:
        """Combina las reglas aplicables, override por especificidad.

        Más específico primero (channel+scheme) > channel only > scheme only > global.
        Toma el threshold MÁS ESTRICTO (mayor min_margin, menor delta) de los aplicables.
        """
        margin_threshold: Decimal | None = None
        fx_swing_threshold: Decimal | None = None
        min_margin_pct: Decimal | None = None

        for rule in active_rules:
            if not rule.active:
                continue
            ch_match = rule.channel_id is None or rule.channel_id == channel_id
            sc_match = rule.scheme_code is None or rule.scheme_code == scheme_code
            if not (ch_match and sc_match):
                continue
            if rule.margin_threshold_pct is not None:
                if margin_threshold is None or rule.margin_threshold_pct < margin_threshold:
                    margin_threshold = Decimal(str(rule.margin_threshold_pct))
            if rule.fx_swing_threshold_pct is not None:
                if fx_swing_threshold is None or rule.fx_swing_threshold_pct < fx_swing_threshold:
                    fx_swing_threshold = Decimal(str(rule.fx_swing_threshold_pct))
            if rule.min_margin_pct is not None:
                if min_margin_pct is None or rule.min_margin_pct > min_margin_pct:
                    min_margin_pct = Decimal(str(rule.min_margin_pct))

        return {
            "margin_threshold_pct": margin_threshold or Decimal("0"),
            "fx_swing_threshold_pct": fx_swing_threshold or Decimal("0"),
            "min_margin_pct": min_margin_pct or Decimal("0"),
        }

    @classmethod
    def evaluate(
        cls,
        new_price: PricingResult,
        prev_price: Any | None,
        channel_id: Any,
        scheme_code: str,
        active_rules: list[ExceptionRule],
        prev_fx_rate: Decimal | None = None,
        current_fx_rate: Decimal | None = None,
    ) -> tuple[str, list[dict[str, Any]]]:
        """Devuelve (next_status, evaluation_reasons).

        next_status ∈ {'auto_approved', 'pending_review'}.
        evaluation_reasons es una lista de dicts con `code` + `message` que el
        caller puede persistir como metadata del evento de aprobación.
        """
        thresholds = cls._resolve_rules_for(active_rules, channel_id, scheme_code)
        reasons: list[dict[str, Any]] = []

        # 4. Critical alerts del motor → siempre pending
        if any(a.get("severity") == "critical" for a in new_price.alerts):
            reasons.append(
                {
                    "code": "critical_alerts",
                    "message": "El motor detectó alertas críticas",
                    "alerts": [a for a in new_price.alerts if a.get("severity") == "critical"],
                }
            )
            return "pending_review", reasons

        # 3. Min margin threshold (siempre, incluso si no hay prev)
        min_m = thresholds["min_margin_pct"]
        margin_pct_pct = new_price.margin_pct * Decimal("100")
        if min_m > 0 and margin_pct_pct < min_m:
            reasons.append(
                {
                    "code": "below_min_margin",
                    "message": (f"Margen {margin_pct_pct:.2f}% < mínimo configurado {min_m}%"),
                }
            )
            return "pending_review", reasons

        # 1. Sin prev → auto_approved
        if prev_price is None:
            reasons.append(
                {"code": "first_price", "message": "Primera propuesta para este SKU/canal/scheme"}
            )
            return "auto_approved", reasons

        # 2. Delta margin
        prev_margin_raw = getattr(prev_price, "margin_pct", None)
        margin_threshold = thresholds["margin_threshold_pct"]
        if prev_margin_raw is not None and margin_threshold > 0:
            prev_margin = Decimal(str(prev_margin_raw))
            delta = abs(new_price.margin_pct - prev_margin) * Decimal("100")
            if delta > margin_threshold:
                reasons.append(
                    {
                        "code": "margin_delta_exceeded",
                        "message": (f"Delta margen {delta:.2f}% > umbral {margin_threshold}%"),
                        "prev_margin_pct": str(prev_margin),
                        "new_margin_pct": str(new_price.margin_pct),
                    }
                )
                return "pending_review", reasons

        # 5. Rule changed
        prev_rule = getattr(prev_price, "rule_applied", None)
        if prev_rule and prev_rule != new_price.rule_applied:
            reasons.append(
                {
                    "code": "rule_changed",
                    "message": f"Regla aplicada cambió: {prev_rule} → {new_price.rule_applied}",
                }
            )
            return "pending_review", reasons

        # 6. FX swing
        fx_swing_threshold = thresholds["fx_swing_threshold_pct"]
        if (
            fx_swing_threshold > 0
            and prev_fx_rate is not None
            and current_fx_rate is not None
            and prev_fx_rate > 0
        ):
            fx_swing = abs(current_fx_rate - prev_fx_rate) / prev_fx_rate * Decimal("100")
            if fx_swing > fx_swing_threshold:
                reasons.append(
                    {
                        "code": "fx_swing_exceeded",
                        "message": (f"FX swing {fx_swing:.2f}% > umbral {fx_swing_threshold}%"),
                    }
                )
                return "pending_review", reasons

        reasons.append(
            {
                "code": "auto_approved_default",
                "message": "Sin excepciones detectadas — auto-aprobado",
            }
        )
        return "auto_approved", reasons


__all__ = ["ExceptionEvaluator"]
