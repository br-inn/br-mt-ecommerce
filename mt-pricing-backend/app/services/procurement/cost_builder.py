"""Build the goods-receipt actual_breakdown from the two MT invoices (F0.5).

Only summable EUR cost components belong here — CostService.compute_landed_aed
sums any numeric value by suffix, so metadata (hs_code/incoterm) must NOT be included.
"""

from __future__ import annotations

from decimal import ROUND_HALF_UP, Decimal


def build_actual_breakdown(
    commercial_eur: Decimal,
    import_value_eur: Decimal,
    tariff_pct: Decimal,
) -> dict[str, str]:
    duty = (import_value_eur * tariff_pct / Decimal("100")).quantize(
        Decimal("0.0001"), rounding=ROUND_HALF_UP
    )
    return {
        "commercial_eur": str(commercial_eur),
        "import_duty_eur": str(duty),
    }
