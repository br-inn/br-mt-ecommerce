"""Cost model — US-1A-04-02 (motor de costes con FX as-of trigger).

Reemplaza el modelo `Cost` parcial que vivía en `pricing.py`. Schema alineado
con sprint3-backlog-refined US-1A-04-02:

- ``id`` UUID PK
- ``sku`` FK → products.sku (CASCADE) — renombrado vs antiguo `product_sku`
- ``scheme_code`` FK → schemes.code (RESTRICT)
- ``supplier_code`` FK → suppliers.code (SET NULL) — opcional
- ``currency_origin`` FK → currencies.code (RESTRICT) — moneda del FOB
- ``fx_rate_id`` FK → fx_rates.id (SET NULL) — autopoblado por trigger
  ``costs_stamp_fx_trg`` (BEFORE INSERT/UPDATE). NULL si currency_origin='AED'.
- ``breakdown`` JSONB — claves convencionales:
    * ``*_aed`` → no convierten (ya en moneda destino)
    * ``*_eur`` (o ``*_<currency_origin>`` lower) → convierten via fx_rate.rate
    * ``*_pct`` → porcentaje aplicado sobre subtotal (componente fee variable)
- ``scheme_landed_aed`` NUMERIC(14,4) — calculado por trigger AFTER, no
  GENERATED (los componentes JSONB hacen un GENERATED imposible).
- ``valid_from`` DATE NOT NULL — inicio de vigencia del coste. El trigger
  busca el FX vigente a esta fecha vía ``fx_rate_at(currency_origin, 'AED', NEW.valid_from)``.
- ``valid_to`` DATE NULL — fin de vigencia (inclusive). NULL = rango abierto
  (vigente indefinidamente). La exclusión GiST ``ex_costs_no_overlap`` evita
  solapes por clave ``(sku, scheme_code, coalesce(supplier_code,''))``.
  ``effective_at`` y ``status`` ya no son columnas: se exponen como hybrids de
  compatibilidad (``effective_at``→``valid_from``; ``status`` derivado por fecha).
- ``fx_inferred`` BOOL default FALSE — marca importer (FX asumido por defecto del batch).
- ``version`` INT default 1 — incrementa al supersede.
- AuditMixin (``created_by``, ``updated_by``) + TimestampMixin (``created_at``, ``updated_at``).

Refs:
- US-1A-04-02 / US-1A-04-03 (`_bmad-output/planning-artifacts/sprint3-backlog-refined.md`)
- BR-1a-04 (no FX as-of → no cost persisted)
- ADR-045 (persistencia híbrida)
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal
from uuid import UUID

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    Date,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    String,
    Text,
    and_,
    case,
    func,
    or_,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.ext.hybrid import hybrid_property
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base
from app.db.mixins import AuditMixin, TimestampMixin, UuidPkMixin
from app.db.types import UUID_PG

COST_STATUSES = ("active", "superseded")


class Cost(UuidPkMixin, TimestampMixin, AuditMixin, Base):
    """Coste vigente o histórico de un SKU × scheme × supplier.

    Versionado: cada `update` crea row nueva con `version=prev+1, status='active'`
    y la previa pasa a `superseded`. El UNIQUE parcial garantiza coherencia.
    """

    __tablename__ = "costs"

    sku: Mapped[str] = mapped_column(
        Text,
        ForeignKey("products.sku", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    scheme_code: Mapped[str] = mapped_column(
        String(32),
        ForeignKey("schemes.code", ondelete="RESTRICT"),
        nullable=False,
    )
    supplier_code: Mapped[str | None] = mapped_column(
        Text, ForeignKey("suppliers.code", ondelete="SET NULL"), nullable=True
    )
    currency_origin: Mapped[str] = mapped_column(
        String(3),
        ForeignKey("currencies.code", ondelete="RESTRICT"),
        nullable=False,
    )
    fx_rate_id: Mapped[UUID | None] = mapped_column(
        UUID_PG, ForeignKey("fx_rates.id", ondelete="SET NULL"), nullable=True
    )
    breakdown: Mapped[dict] = mapped_column(
        JSONB, nullable=False, server_default=text("'{}'::jsonb")
    )
    scheme_landed_aed: Mapped[Decimal | None] = mapped_column(Numeric(14, 4), nullable=True)
    valid_from: Mapped[date] = mapped_column(Date, nullable=False)
    valid_to: Mapped[date | None] = mapped_column(Date, nullable=True)
    fx_inferred: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default=text("false"))
    version: Mapped[int] = mapped_column(Integer, nullable=False, server_default=text("1"))

    __table_args__ = (
        CheckConstraint("version >= 1", name="ck_costs_version_pos"),
        CheckConstraint(
            "scheme_landed_aed IS NULL OR scheme_landed_aed >= 0",
            name="ck_costs_landed_nonneg",
        ),
        Index("idx_costs_sku_scheme", "sku", "scheme_code"),
        Index("idx_costs_valid_from", "sku", "scheme_code", "valid_from"),
    )

    # ------------------------------------------------------------------
    # Backward-compat hybrid attrs — pricing_service.py todavía lee
    # `cost.total` y `cost.product_sku` (semántica antigua). Mapeamos al
    # nuevo schema sin romper consumidores S2.
    # ------------------------------------------------------------------
    @hybrid_property
    def total(self):  # type: ignore[override]
        """Compat: alias de `scheme_landed_aed` (Decimal). 0 si NULL."""
        from decimal import Decimal as _D

        return self.scheme_landed_aed if self.scheme_landed_aed is not None else _D("0")

    @hybrid_property
    def product_sku(self):  # type: ignore[override]
        """Compat: alias de `sku`."""
        return self.sku

    @hybrid_property
    def currency(self):  # type: ignore[override]
        """Compat: el endpoint legacy lee `cost.currency` (origen)."""
        return self.currency_origin

    @hybrid_property
    def fx_at(self):  # type: ignore[override]
        """Compat: la fecha as-of se expone como `fx_at` (alias `valid_from`)."""
        return self.valid_from

    @fx_at.expression  # type: ignore[no-redef]
    def fx_at(cls):
        return cls.valid_from

    @hybrid_property
    def effective_at(self):  # type: ignore[override]
        """Compat: el viejo `effective_at` mapea a `valid_from` (la fecha as-of).

        Consumidores legacy / DTOs todavía leen `cost.effective_at`.
        """
        return self.valid_from

    @effective_at.expression  # type: ignore[no-redef]
    def effective_at(cls):
        return cls.valid_from

    @hybrid_property
    def status(self):  # type: ignore[override]
        """Compat: estado derivado por fecha (la columna real fue dropeada).

        'active' si el rango está vigente hoy (rango abierto o `today` dentro de
        ``[valid_from, valid_to]``); en caso contrario 'superseded'.
        """
        today = date.today()
        if self.valid_to is None or (self.valid_from <= today <= self.valid_to):
            return "active"
        return "superseded"

    @status.expression  # type: ignore[no-redef]
    def status(cls):
        """Expresión SQL equivalente para filtros tipo `Cost.status == 'active'`."""
        today = func.current_date()
        return case(
            (
                or_(
                    cls.valid_to.is_(None),
                    and_(cls.valid_from <= today, today <= cls.valid_to),
                ),
                "active",
            ),
            else_="superseded",
        )


__all__ = ["COST_STATUSES", "Cost"]
