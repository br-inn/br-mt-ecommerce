"""State machine v5.1 — extiende `state_machine.py` con golden numbers + alerts.

Sprint 4 — US-1B-01-02 (golden numbers v5.1 + bundling psicológico).

Capa fina sobre el FSM existente que:

1. Aplica `apply_golden_numbers` al output del motor antes de persistir.
2. Clasifica alerts en 3 buckets: ``critical`` / ``warning`` / ``info``.
3. Decide el estado inicial según política v5.1:
    - Si `has_critical_alerts` → ``pending_review`` (no auto-aprobable).
    - Si `has_warnings` y delta_pct > threshold → ``pending_review``.
    - En otro caso → ``auto_approved``.
4. Soporta override flags por request:
    - ``force_pending_review`` (bool): obliga `pending_review`.
    - ``force_auto_approved`` (bool): obliga `auto_approved` (requiere
      permission `prices:override_review` — el caller valida).
    - ``disable_bundling`` (bool): pasa al `apply_golden_numbers`.
    - ``bundle_strategy`` (str): pasa al `apply_golden_numbers`.

NOTA: este módulo NO toca el `state_machine.py` clásico — sólo lo extiende.
El `transition()` existente sigue siendo la SSoT para validaciones de
transición legales. Aquí solo decidimos el `to_status` inicial y aplicamos
post-procesado al `PricingResult`.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from decimal import Decimal
from typing import Any

from app.services.pricing.golden_numbers import apply_golden_numbers
from app.services.pricing.state_machine import (
    ALLOWED_TRANSITIONS,
    InvalidTransition,
    is_valid_transition,
)

__all__ = [
    "ALLOWED_TRANSITIONS",
    "AlertLevel",
    "InvalidTransition",
    "InvalidV51Override",
    "V51Decision",
    "apply_v51",
    "classify_alerts",
    "decide_initial_status",
    "is_valid_transition",
]


AlertLevel = str  # 'critical' | 'warning' | 'info'

# Default warning_delta — si delta_pct vs precio anterior > este umbral, force pending_review.
_DEFAULT_DELTA_WARN_PCT = Decimal("10.0")


class InvalidV51Override(Exception):
    """Override flags inconsistentes (e.g. force_pending + force_auto)."""


@dataclass
class V51Decision:
    """Resultado del pipeline v5.1.

    `final_amount` ya viene con bundling psicológico aplicado (si procede).
    `initial_status` indica el estado destino post-INSERT (`auto_approved` o
    `pending_review`). El caller debe llamar `transition()` con este valor.
    """

    final_amount: Decimal
    initial_status: str  # 'auto_approved' | 'pending_review'
    bundling_info: dict[str, str] = field(default_factory=dict)
    classified_alerts: dict[str, list[dict[str, Any]]] = field(default_factory=dict)
    decision_reasons: list[str] = field(default_factory=list)
    overrides_applied: dict[str, Any] = field(default_factory=dict)

    @property
    def has_critical(self) -> bool:
        return bool(self.classified_alerts.get("critical"))

    @property
    def has_warnings(self) -> bool:
        return bool(self.classified_alerts.get("warning"))


def classify_alerts(
    alerts: list[dict[str, Any]] | None,
) -> dict[str, list[dict[str, Any]]]:
    """Agrupa alerts en buckets ``critical`` / ``warning`` / ``info``.

    Acepta dos shapes (compat con ambos motores):
    - {"severity": "critical", "code": "...", "message": "..."}
    - {"level": "critical", ...}
    """
    buckets: dict[str, list[dict[str, Any]]] = {
        "critical": [],
        "warning": [],
        "info": [],
    }
    if not alerts:
        return buckets
    for a in alerts:
        sev = (a.get("severity") or a.get("level") or "info").lower()
        if sev not in buckets:
            sev = "info"
        buckets[sev].append(a)
    return buckets


def _as_decimal(value: Any) -> Decimal | None:
    if value is None:
        return None
    try:
        return Decimal(str(value))
    except (ArithmeticError, ValueError, TypeError):
        return None


def decide_initial_status(
    classified: dict[str, list[dict[str, Any]]],
    *,
    delta_margin_pct: Decimal | None = None,
    delta_warn_pct: Decimal | None = None,
    overrides: dict[str, Any] | None = None,
) -> tuple[str, list[str]]:
    """Decide el estado inicial respetando overrides y reglas v5.1.

    Returns: (status, reasons[]).
    """
    overrides = overrides or {}
    reasons: list[str] = []

    if overrides.get("force_pending_review") and overrides.get("force_auto_approved"):
        raise InvalidV51Override(
            "force_pending_review y force_auto_approved son mutuamente exclusivos."
        )

    if overrides.get("force_pending_review"):
        reasons.append("override:force_pending_review")
        return "pending_review", reasons

    if overrides.get("force_auto_approved"):
        reasons.append("override:force_auto_approved")
        return "auto_approved", reasons

    if classified.get("critical"):
        reasons.append("critical_alerts_present")
        return "pending_review", reasons

    delta_threshold = delta_warn_pct if delta_warn_pct is not None else _DEFAULT_DELTA_WARN_PCT
    if delta_margin_pct is not None and abs(delta_margin_pct) > delta_threshold:
        reasons.append(f"delta_margin_pct_above_threshold:{delta_threshold}%")
        return "pending_review", reasons

    if classified.get("warning"):
        # Warnings sólos no bloquean auto_approved, pero sí marcan razón.
        reasons.append("warnings_present_auto_approved")
        return "auto_approved", reasons

    reasons.append("clean_no_alerts")
    return "auto_approved", reasons


def apply_v51(
    *,
    raw_amount: Decimal | float | int | str,
    alerts: list[dict[str, Any]] | None = None,
    channel_code: str | None = None,
    delta_margin_pct: Decimal | None = None,
    delta_warn_pct: Decimal | None = None,
    overrides: dict[str, Any] | None = None,
) -> V51Decision:
    """Pipeline v5.1: golden numbers → classify alerts → decide status.

    Esta es la única función pública que el ``PricingService`` debe llamar
    para integrar v5.1 sobre el output del motor.

    Args:
        raw_amount: precio crudo del motor (`PricingResult.amount`).
        alerts: lista de alerts del motor.
        channel_code: para resolver la estrategia de bundling default.
        delta_margin_pct: delta vs precio previo (en puntos %, e.g. 12.3
            significa 12.3%). Si supera ``delta_warn_pct`` (default 10) →
            pending_review.
        delta_warn_pct: override del umbral del delta.
        overrides: dict con flags:
            - ``disable_bundling``
            - ``bundle_strategy`` (e.g. ``.99``, ``.49``, ``.95``, ``auto``, ``none``)
            - ``tolerance_override``
            - ``force_pending_review``
            - ``force_auto_approved``
            - ``delta_warn_pct_override`` (alias del param `delta_warn_pct`)
    """
    overrides = overrides or {}
    bundling_overrides = {
        k: v
        for k, v in overrides.items()
        if k in {"disable_bundling", "bundle_strategy", "tolerance_override"}
    }

    final_amount, bundling_info = apply_golden_numbers(
        raw_price_aed=raw_amount,
        channel_code=channel_code,
        overrides=bundling_overrides,
    )

    classified = classify_alerts(alerts)

    effective_delta_warn = delta_warn_pct
    if "delta_warn_pct_override" in overrides:
        ov = _as_decimal(overrides["delta_warn_pct_override"])
        if ov is not None:
            effective_delta_warn = ov

    initial_status, reasons = decide_initial_status(
        classified,
        delta_margin_pct=delta_margin_pct,
        delta_warn_pct=effective_delta_warn,
        overrides=overrides,
    )

    overrides_applied = {
        k: overrides[k]
        for k in (
            "disable_bundling",
            "bundle_strategy",
            "tolerance_override",
            "force_pending_review",
            "force_auto_approved",
            "delta_warn_pct_override",
        )
        if k in overrides
    }

    return V51Decision(
        final_amount=final_amount,
        initial_status=initial_status,
        bundling_info=bundling_info,
        classified_alerts=classified,
        decision_reasons=reasons,
        overrides_applied=overrides_applied,
    )
