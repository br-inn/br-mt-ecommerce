"""EP-ERP-06 — Finanzas: Celery tasks.

Tasks:
- mt.finance.refresh_pl_mv            — refrescar mv_pl_summary (nightly)
- mt.finance.refresh_copa_mv          — refrescar mv_copa_summary (nightly)
- mt.finance.run_fx_revaluation       — revaluación FX al cierre de período
- mt.finance.period_close_reminder    — verificar períodos pendientes de cierre
- mt.finance.calc_price_variance      — calcular varianza al registrar GR
- mt.finance.run_balance_reconciliation — verificar SUM(open_items) = gl_balance (daily)

TODO: Register mt.finance.refresh_copa_mv and mt.finance.run_balance_reconciliation
      in the job_definitions table with a nightly/daily schedule respectively.
"""

from __future__ import annotations

import asyncio
import logging
import uuid as _uuid
from datetime import UTC, date, datetime
from decimal import Decimal
from typing import Any
from uuid import UUID

from app.workers.worker import celery_app

log = logging.getLogger(__name__)


def _run_async(coro: Any) -> Any:
    """Helper para ejecutar corrutinas en el contexto síncrono de Celery."""
    try:
        loop = asyncio.get_event_loop()
        if loop.is_running():
            raise RuntimeError("event loop already running")
    except RuntimeError:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
    return loop.run_until_complete(coro)


@celery_app.task(
    name="mt.finance.refresh_pl_mv",
    bind=True,
    autoretry_for=(Exception,),
    max_retries=3,
    default_retry_delay=300,
)
def refresh_pl_mv(self: object) -> dict:
    """Refrescar la vista materializada mv_pl_summary.

    Ejecutar nightly después del cierre de asientos del día.
    Se registra en job_definitions con schedule diario.
    """

    async def _inner() -> dict:
        from sqlalchemy import text

        from app.db.engine import get_sessionmaker

        async with get_sessionmaker()() as session:
            await session.execute(text("REFRESH MATERIALIZED VIEW CONCURRENTLY mv_pl_summary"))
            await session.commit()
            log.info("mv_pl_summary refreshed OK")
            return {
                "status": "ok",
                "refreshed_at": datetime.now(UTC).isoformat(),
            }

    return _run_async(_inner())


@celery_app.task(
    name="mt.finance.run_fx_revaluation",
    bind=True,
    autoretry_for=(Exception,),
    max_retries=2,
    default_retry_delay=60,
)
def run_fx_revaluation(
    self: object,
    fiscal_year: int,
    period: int,
    user_id: str,
) -> dict:
    """Ejecutar revaluación FX para un período.

    Llamado desde el API endpoint o programáticamente al cierre de período.

    Args:
        fiscal_year: Año fiscal
        period: Número de período
        user_id: UUID del usuario que dispara la revaluación
    """

    async def _inner() -> dict:
        from sqlalchemy import select, text

        from app.db.engine import get_sessionmaker
        from app.db.models.finance import FinancialEntry, GlAccount
        from app.db.models.pricing import FXRate

        async with get_sessionmaker()() as session:
            # Obtener cuentas en moneda extranjera
            foreign_accounts = (
                (
                    await session.execute(
                        select(GlAccount).where(
                            GlAccount.currency != "AED",
                            GlAccount.is_blocked.is_(False),
                        )
                    )
                )
                .scalars()
                .all()
            )

            fx_acct = (
                await session.execute(select(GlAccount).where(GlAccount.account_code == "7100"))
            ).scalar_one_or_none()

            if not fx_acct:
                log.warning("Cuenta 7100 (FX) no encontrada — abortando revaluación")
                return {"status": "skipped", "reason": "no account 7100"}

            today = date.today()
            entries_created = 0

            for acct in foreign_accounts:
                bal_row = (
                    (
                        await session.execute(
                            text("""
                            SELECT
                                COALESCE(SUM(debit_amount - credit_amount), 0) AS balance_local,
                                currency_code,
                                COALESCE(AVG(fx_rate), 1) AS avg_rate
                            FROM financial_entries
                            WHERE gl_account_id = :acct_id
                              AND fiscal_year = :fy
                              AND posting_period <= :period
                            GROUP BY currency_code
                        """),
                            {
                                "acct_id": str(acct.id),
                                "fy": fiscal_year,
                                "period": period,
                            },
                        )
                    )
                    .mappings()
                    .one_or_none()
                )

                if not bal_row or not bal_row["balance_local"]:
                    continue

                currency = bal_row["currency_code"]
                if currency == "AED":
                    continue

                fx_rate_obj = (
                    await session.execute(
                        select(FXRate)
                        .where(
                            FXRate.from_currency == currency,
                            FXRate.to_currency == "AED",
                        )
                        .order_by(FXRate.effective_date.desc())
                        .limit(1)
                    )
                ).scalar_one_or_none()

                if not fx_rate_obj:
                    continue

                rate_closing = Decimal(str(fx_rate_obj.rate))
                rate_original = Decimal(str(bal_row["avg_rate"])) or Decimal("1")
                balance_local = Decimal(str(bal_row["balance_local"]))
                balance_foreign = balance_local / rate_original
                fx_diff = balance_foreign * (rate_closing - rate_original)

                if fx_diff == 0:
                    continue

                entry_number = (
                    f"FXREV-{fiscal_year}-P{period:02d}-"
                    f"{acct.account_code}-{_uuid.uuid4().hex[:6].upper()}"
                )
                debit = abs(fx_diff) if fx_diff < 0 else Decimal("0")
                credit = abs(fx_diff) if fx_diff > 0 else Decimal("0")

                fe = FinancialEntry(
                    entry_number=entry_number,
                    journal_date=today,
                    posting_period=period,
                    fiscal_year=fiscal_year,
                    entry_type="FX_REVAL",
                    source_module="fx",
                    gl_account_id=fx_acct.id,
                    debit_amount=debit,
                    credit_amount=credit,
                    currency_code="AED",
                    fx_rate=rate_closing,
                    description=f"FX Reval {acct.account_code} {currency}",
                    preparer_id=UUID(user_id) if user_id else None,
                )
                session.add(fe)
                entries_created += 1

            await session.commit()
            log.info(
                "FX revaluation FY%d P%d: %d entries created",
                fiscal_year,
                period,
                entries_created,
            )
            return {
                "status": "ok",
                "fiscal_year": fiscal_year,
                "period": period,
                "entries_created": entries_created,
            }

    return _run_async(_inner())


@celery_app.task(
    name="mt.finance.calc_price_variance",
    bind=True,
    autoretry_for=(Exception,),
    max_retries=3,
    default_retry_delay=30,
)
def calc_price_variance(
    self: object,
    po_line_id: str | None,
    product_sku: str,
    actual_unit_price: str,
    fiscal_year: int,
    period: int,
) -> dict:
    """Calcular varianza de precio al registrar un Goods Receipt.

    Llamado desde el task de inventory/goods receipt processing.

    Args:
        po_line_id: UUID de la línea de PO (puede ser None)
        product_sku: SKU del producto (FK a products.sku — TEXT, NUNCA UUID)
        actual_unit_price: Precio real en el GR (string Decimal)
        fiscal_year: Año fiscal
        period: Período contable
    """

    async def _inner() -> dict:
        from sqlalchemy import select

        from app.db.engine import get_sessionmaker
        from app.db.models.finance import PriceVariance, StandardCost

        async with get_sessionmaker()() as session:
            actual_cost = Decimal(actual_unit_price)

            # Obtener costo estándar vigente
            std_result = (
                await session.execute(
                    select(StandardCost)
                    .where(
                        StandardCost.product_sku == product_sku,
                        StandardCost.fiscal_year == fiscal_year,
                        StandardCost.cost_type == "standard",
                    )
                    .order_by(StandardCost.valid_from.desc())
                    .limit(1)
                )
            ).scalar_one_or_none()

            if not std_result:
                log.warning(
                    "StandardCost no encontrado para SKU %s FY%d",
                    product_sku,
                    fiscal_year,
                )
                return {"status": "skipped", "reason": "no standard cost"}

            standard_cost = std_result.standard_cost
            variance_pct = (
                ((actual_cost - standard_cost) / standard_cost * 100).quantize(Decimal("0.0001"))
                if standard_cost
                else None
            )

            pv = PriceVariance(
                po_line_id=UUID(po_line_id) if po_line_id else None,
                product_sku=product_sku,
                standard_cost=standard_cost,
                actual_cost=actual_cost,
                variance_pct=variance_pct,
                period=period,
                fiscal_year=fiscal_year,
            )
            session.add(pv)
            await session.commit()

            variance = actual_cost - standard_cost
            log.info(
                "PriceVariance: SKU=%s std=%.4f actual=%.4f var=%.4f",
                product_sku,
                standard_cost,
                actual_cost,
                variance,
            )

            # Bug 2 fix: trigger alert when variance exceeds 5%
            if variance_pct is not None and abs(variance_pct) > 5:
                log.warning(
                    "FINANCE ALERT — price variance >5%% for SKU %s: "
                    "std=%.4f actual=%.4f variance_pct=%.4f FY=%d P%02d",
                    product_sku,
                    standard_cost,
                    actual_cost,
                    variance_pct,
                    fiscal_year,
                    period,
                )

            return {
                "status": "ok",
                "product_sku": product_sku,
                "standard_cost": str(standard_cost),
                "actual_cost": str(actual_cost),
                "variance": str(variance),
                "variance_pct": str(variance_pct),
                "alert_triggered": variance_pct is not None and abs(variance_pct) > 5,
            }

    return _run_async(_inner())


@celery_app.task(
    name="mt.finance.period_close_reminder",
    bind=True,
    autoretry_for=(Exception,),
    max_retries=1,
    default_retry_delay=60,
)
def period_close_reminder(self: object) -> dict:
    """Verificar períodos open con date_to < today y registrar en log.

    Ejecutar mensualmente (job_definition scheduled).
    """

    async def _inner() -> dict:
        from sqlalchemy import select

        from app.db.engine import get_sessionmaker
        from app.db.models.finance import PostingPeriod

        async with get_sessionmaker()() as session:
            today = date.today()
            open_periods = (
                (
                    await session.execute(
                        select(PostingPeriod)
                        .where(
                            PostingPeriod.status == "open",
                            PostingPeriod.date_to < today,
                        )
                        .order_by(PostingPeriod.fiscal_year, PostingPeriod.period_num)
                    )
                )
                .scalars()
                .all()
            )

            if not open_periods:
                return {"status": "ok", "pending_periods": 0}

            log.warning(
                "Períodos open vencidos: %s",
                [(p.fiscal_year, p.period_num) for p in open_periods],
            )
            return {
                "status": "ok",
                "pending_periods": len(open_periods),
                "periods": [
                    {"fiscal_year": p.fiscal_year, "period_num": p.period_num} for p in open_periods
                ],
            }

    return _run_async(_inner())


# ===========================================================================
# Bug 4 (PERFORMANCE) — Refresh mv_copa_summary materialized view (nightly)
# TODO: CREATE MATERIALIZED VIEW mv_copa_summary migration required before
#       this task is activated. Register in job_definitions with daily schedule.
# ===========================================================================


@celery_app.task(
    name="mt.finance.refresh_copa_mv",
    bind=True,
    autoretry_for=(Exception,),
    max_retries=3,
    default_retry_delay=300,
)
def refresh_copa_mv(self: object) -> dict:
    """Refrescar la vista materializada mv_copa_summary.

    Ejecutar nightly después del cierre de asientos del día.
    Se registra en job_definitions con schedule diario (igual que refresh_pl_mv).
    """

    async def _inner() -> dict:
        from sqlalchemy import text

        from app.db.engine import get_sessionmaker

        async with get_sessionmaker()() as session:
            await session.execute(text("REFRESH MATERIALIZED VIEW CONCURRENTLY mv_copa_summary"))
            await session.commit()
            log.info("mv_copa_summary refreshed OK")
            return {
                "status": "ok",
                "refreshed_at": datetime.now(UTC).isoformat(),
            }

    return _run_async(_inner())


# ===========================================================================
# Bug 3 fix — Daily balance reconciliation (US-ERP-06-01 spec requirement)
# TODO: Register in job_definitions with a daily schedule (e.g. 02:00 UTC).
# ===========================================================================


@celery_app.task(
    name="mt.finance.run_balance_reconciliation",
    bind=True,
    autoretry_for=(Exception,),
    max_retries=2,
    default_retry_delay=120,
)
def run_balance_reconciliation(self: object) -> dict:
    """Verificar que SUM(open_items) == gl_balance para cuentas is_reconciling=True.

    Para cada cuenta reconciliante:
    - Calcula el saldo GL: SUM(debit_amount - credit_amount) de financial_entries.
    - Calcula el saldo de partidas abiertas: SUM(amount) de vendor_open_items (status != 'paid')
      y SUM(amount) de customer_open_items (status != 'paid').
    - Si la diferencia absoluta > 0 → registra un warning de alerta de finanzas.

    TODO: Registrar en job_definitions con schedule diario.
    """

    async def _inner() -> dict:
        from decimal import ROUND_HALF_UP

        from sqlalchemy import func, select

        from app.db.engine import get_sessionmaker
        from app.db.models.finance import FinancialEntry, GlAccount, VendorOpenItem
        from app.db.models.sales import CustomerOpenItem

        async with get_sessionmaker()() as session:
            # Fetch all reconciling GL accounts
            reconciling_accounts = (
                (
                    await session.execute(
                        select(GlAccount).where(
                            GlAccount.is_reconciling.is_(True),
                            GlAccount.is_blocked.is_(False),
                        )
                    )
                )
                .scalars()
                .all()
            )

            if not reconciling_accounts:
                log.info("run_balance_reconciliation: no reconciling accounts found")
                return {"status": "ok", "mismatches": 0, "accounts_checked": 0}

            mismatches: list[dict] = []

            for acct in reconciling_accounts:
                # 1. GL balance: SUM(debit - credit) for this account (all time)
                gl_balance_row = (
                    await session.execute(
                        select(
                            func.coalesce(
                                func.sum(
                                    FinancialEntry.debit_amount - FinancialEntry.credit_amount
                                ),
                                Decimal("0"),
                            ).label("gl_balance")
                        ).where(FinancialEntry.gl_account_id == acct.id)
                    )
                ).one()
                gl_balance = Decimal(str(gl_balance_row.gl_balance))

                # 2. Open items balance (vendor AP subledger — unpaid items)
                vendor_oi_row = (
                    await session.execute(
                        select(
                            func.coalesce(func.sum(VendorOpenItem.amount), Decimal("0")).label(
                                "open_balance"
                            )
                        ).where(
                            VendorOpenItem.status.notin_(["paid"]),
                        )
                    )
                ).one()
                vendor_oi_balance = Decimal(str(vendor_oi_row.open_balance))

                # 3. Open items balance (customer AR subledger — uncollected items)
                customer_oi_row = (
                    await session.execute(
                        select(
                            func.coalesce(func.sum(CustomerOpenItem.amount), Decimal("0")).label(
                                "open_balance"
                            )
                        ).where(
                            CustomerOpenItem.status.notin_(["paid"]),
                        )
                    )
                ).one()
                customer_oi_balance = Decimal(str(customer_oi_row.open_balance))

                open_items_total = (vendor_oi_balance + customer_oi_balance).quantize(
                    Decimal("0.0001"), rounding=ROUND_HALF_UP
                )
                gl_balance_q = gl_balance.quantize(Decimal("0.0001"), rounding=ROUND_HALF_UP)
                diff = abs(gl_balance_q - open_items_total)

                if diff > Decimal("0"):
                    mismatch_info = {
                        "account_code": acct.account_code,
                        "account_name": acct.account_name,
                        "gl_balance": str(gl_balance_q),
                        "open_items_total": str(open_items_total),
                        "difference": str(diff),
                    }
                    mismatches.append(mismatch_info)
                    # Alert: log warning for finance team review
                    log.warning(
                        "FINANCE ALERT — reconciliation mismatch on account %s (%s): "
                        "gl_balance=%s open_items=%s diff=%s",
                        acct.account_code,
                        acct.account_name,
                        gl_balance_q,
                        open_items_total,
                        diff,
                    )

            if mismatches:
                log.error(
                    "run_balance_reconciliation: %d mismatch(es) found — manual review required",
                    len(mismatches),
                )
            else:
                log.info(
                    "run_balance_reconciliation: all %d reconciling account(s) balanced OK",
                    len(reconciling_accounts),
                )

            return {
                "status": "ok" if not mismatches else "alert",
                "accounts_checked": len(reconciling_accounts),
                "mismatches": len(mismatches),
                "mismatch_detail": mismatches,
            }

    return _run_async(_inner())
