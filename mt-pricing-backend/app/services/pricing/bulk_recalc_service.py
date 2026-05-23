"""BulkRecalcService — orquestador del recalc nocturno (US-1B-01-07).

Patrón:
- Itera todos los SKUs activos con coste activo en al menos un scheme.
- Para cada SKU dispara ``PricingService.recalculate_for_product`` (mismo path
  del manual recalc) capturando errores recoverables.
- Acumula métricas (skus_processed, status_counts, avg_margin_delta) y emite
  un audit batch ``action='nightly_recalc_batch'`` con el summary.

Diseño testable:
- ``PricingServiceProtocol`` Protocol mockeable.
- ``ProductRepoProtocol`` Protocol mockeable (sólo necesita ``list_active_skus``).
- ``AuditRepoProtocol`` Protocol mockeable (record).

Mutex con manual recalc (US-1B-01-04 / R-S5-04): si está presente un
``mutex`` Redis-like callable + lock falla, se skipea el batch con razón
`manual_recalc_in_progress`.

Convención: el caller (Celery task) abre la session y llama
``await BulkRecalcService(session).run(actor)``. La session NO se commitea acá —
el caller decide.
"""

from __future__ import annotations

import logging
from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field
from datetime import datetime, timezone
from decimal import Decimal
from typing import Any, Protocol
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.product import Product
from app.db.models.user import User
from app.repositories.audit import AuditRepository
from app.services.pricing.pricing_service import (
    PricingDomainError,
    PricingService,
)

logger = logging.getLogger(__name__)


# Default cron expression (Asia/Dubai 02:00 = UTC 22:00 prev day, but spec
# pinned a 0 2 * * * cron — tomado tal cual del prompt). El DatabaseScheduler
# lee el cron desde job_definitions.cron_expression; este string se documenta
# acá como source of truth para el seed.
NIGHTLY_RECALC_CRON: str = "0 2 * * *"
NIGHTLY_RECALC_TASK_NAME: str = "mt.pricing.bulk_recalc"
NIGHTLY_RECALC_TIMEZONE: str = "Asia/Dubai"

# Threshold para SEV2 alert (R-S5-04). 5% > umbral → emite warning + audit
# adicional con flag `failure_rate_alert=true`.
FAILURE_RATE_ALERT_THRESHOLD: float = 0.05


class PricingServiceProtocol(Protocol):
    """Contracto mínimo del PricingService consumido por el bulk recalc."""

    async def recalculate_for_product(self, product_id: UUID | str, actor: User) -> list[Any]: ...


class ProductRepoProtocol(Protocol):
    async def list_active_skus(self) -> list[str]: ...


class AuditRepoProtocol(Protocol):
    async def record(self, **kwargs: Any) -> Any: ...


MutexAcquire = Callable[[], Awaitable[bool]]


@dataclass(slots=True)
class BulkRecalcResult:
    """Métricas + outcome del run nocturno."""

    started_at: datetime
    finished_at: datetime | None = None
    skus_total: int = 0
    skus_processed: int = 0
    skus_skipped: int = 0
    skus_failed: int = 0
    status_counts: dict[str, int] = field(default_factory=dict)
    avg_margin_delta: Decimal | None = None
    errors: list[dict[str, Any]] = field(default_factory=list)
    skipped: bool = False
    skip_reason: str | None = None
    failure_rate_alert: bool = False

    @property
    def duration_seconds(self) -> float:
        if self.finished_at is None:
            return 0.0
        return (self.finished_at - self.started_at).total_seconds()

    @property
    def failure_rate(self) -> float:
        if self.skus_processed == 0:
            return 0.0
        return self.skus_failed / self.skus_processed

    def to_dict(self) -> dict[str, Any]:
        return {
            "started_at": self.started_at.isoformat(),
            "finished_at": self.finished_at.isoformat() if self.finished_at else None,
            "duration_seconds": round(self.duration_seconds, 3),
            "skus_total": self.skus_total,
            "skus_processed": self.skus_processed,
            "skus_skipped": self.skus_skipped,
            "skus_failed": self.skus_failed,
            "status_counts": dict(self.status_counts),
            "avg_margin_delta": str(self.avg_margin_delta)
            if self.avg_margin_delta is not None
            else None,
            "failure_rate": round(self.failure_rate, 4),
            "failure_rate_alert": self.failure_rate_alert,
            "skipped": self.skipped,
            "skip_reason": self.skip_reason,
            "errors": list(self.errors[:50]),  # cap audit payload size
        }


class _DefaultProductRepo:
    """Adapter mínimo: SELECT sku FROM products WHERE active=true AND deleted_at IS NULL."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def list_active_skus(self) -> list[str]:
        # Fase B (mig 066): active deriva de lifecycle_status='active'.
        stmt = select(Product.sku).where(
            Product.lifecycle_status == "active",
            Product.deleted_at.is_(None),
        )
        rows = (await self._session.execute(stmt)).all()
        return [r[0] for r in rows]


class BulkRecalcService:
    """Orquestador del recalc nocturno.

    Uso típico (Celery task ``mt.pricing.bulk_recalc``)::

        async with sessionmaker() as session:
            user = await users.get_system_actor()
            svc = BulkRecalcService(session)
            result = await svc.run(actor=user)
            await session.commit()
        return result.to_dict()

    Constructor inyectable para tests sin DB:
        ``BulkRecalcService(session, pricing_service=mock, product_repo=mock,
                              audit_repo=mock, mutex_acquire=mock)``.
    """

    def __init__(
        self,
        session: AsyncSession | None = None,
        *,
        pricing_service: PricingServiceProtocol | None = None,
        product_repo: ProductRepoProtocol | None = None,
        audit_repo: AuditRepoProtocol | None = None,
        mutex_acquire: MutexAcquire | None = None,
    ) -> None:
        self._session = session
        # Permitimos instanciación pura mock — pero si no hay session, requerimos
        # los Protocols inyectados.
        if session is None and (
            pricing_service is None or product_repo is None or audit_repo is None
        ):
            raise ValueError(
                "BulkRecalcService requiere session o (pricing_service, product_repo, audit_repo)."
            )
        self._pricing = (
            pricing_service if pricing_service is not None else PricingService(session)  # type: ignore[arg-type]
        )
        self._products = (
            product_repo if product_repo is not None else _DefaultProductRepo(session)  # type: ignore[arg-type]
        )
        self._audit = (
            audit_repo if audit_repo is not None else AuditRepository(session)  # type: ignore[arg-type]
        )
        self._mutex = mutex_acquire

    # ------------------------------------------------------------------ run
    async def run(
        self,
        *,
        actor: User,
        source: str = "nightly_beat",
    ) -> BulkRecalcResult:
        """Ejecuta el batch completo. Idempotente — si mutex no lo permite, skipea."""
        result = BulkRecalcResult(started_at=datetime.now(tz=timezone.utc))

        if self._mutex is not None:
            try:
                acquired = await self._mutex()
            except Exception:  # noqa: BLE001 — mutex no debe romper el batch
                logger.exception("BulkRecalcService.mutex_acquire_failed")
                acquired = True
            if not acquired:
                result.skipped = True
                result.skip_reason = "manual_recalc_in_progress"
                result.finished_at = datetime.now(tz=timezone.utc)
                logger.warning(
                    "bulk_recalc skipped: manual recalc mutex held",
                    extra={"source": source},
                )
                return result

        skus = await self._products.list_active_skus()
        result.skus_total = len(skus)
        margin_deltas: list[Decimal] = []

        for sku in skus:
            try:
                prices = await self._pricing.recalculate_for_product(sku, actor)
            except PricingDomainError as exc:
                result.skus_failed += 1
                result.errors.append(
                    {
                        "sku": sku,
                        "code": exc.code,
                        "message": exc.message,
                    }
                )
                continue
            except Exception as exc:  # noqa: BLE001 — unhandled error per-SKU
                logger.exception("bulk_recalc.unhandled sku=%s", sku)
                result.skus_failed += 1
                result.errors.append(
                    {
                        "sku": sku,
                        "code": "unhandled_exception",
                        "message": f"{type(exc).__name__}: {exc!s}"[:500],
                    }
                )
                continue

            if not prices:
                # SKU sin coste para ningún scheme → contado como skipped (no
                # hay precio nuevo, pero tampoco fallo dominio).
                result.skus_skipped += 1
                continue

            result.skus_processed += 1
            for p in prices:
                status = getattr(p, "status", None) or "unknown"
                result.status_counts[status] = result.status_counts.get(status, 0) + 1
                # margin_pct es Decimal en el modelo Price.
                m = getattr(p, "margin_pct", None)
                if m is not None:
                    try:
                        margin_deltas.append(Decimal(str(m)))
                    except (TypeError, ValueError):
                        pass

        if margin_deltas:
            total = sum(margin_deltas, Decimal("0"))
            result.avg_margin_delta = total / Decimal(len(margin_deltas))

        if result.failure_rate >= FAILURE_RATE_ALERT_THRESHOLD and result.skus_processed > 0:
            result.failure_rate_alert = True
            logger.warning(
                "bulk_recalc.failure_rate_alert rate=%.4f",
                result.failure_rate,
                extra={"source": source, "errors": result.errors[:10]},
            )

        result.finished_at = datetime.now(tz=timezone.utc)

        # Audit batch — entity_id = ISO-date para idempotency casi-trivial
        # (un batch al día). No falla el run si el audit falla.
        try:
            await self._audit.record(
                entity_type="pricing_batch",
                entity_id=result.started_at.strftime("%Y-%m-%d"),
                action="nightly_recalc_batch",
                actor_id=getattr(actor, "id", None),
                actor_email=getattr(actor, "email", None),
                after=result.to_dict(),
                payload_diff={"source": source},
            )
        except Exception:  # noqa: BLE001
            logger.exception("bulk_recalc.audit_record_failed")

        logger.info(
            "bulk_recalc.completed",
            extra={
                "source": source,
                "skus_total": result.skus_total,
                "skus_processed": result.skus_processed,
                "skus_failed": result.skus_failed,
                "duration_seconds": result.duration_seconds,
            },
        )
        return result


__all__ = [
    "BulkRecalcResult",
    "BulkRecalcService",
    "FAILURE_RATE_ALERT_THRESHOLD",
    "NIGHTLY_RECALC_CRON",
    "NIGHTLY_RECALC_TASK_NAME",
    "NIGHTLY_RECALC_TIMEZONE",
    "PricingServiceProtocol",
    "ProductRepoProtocol",
    "AuditRepoProtocol",
]
