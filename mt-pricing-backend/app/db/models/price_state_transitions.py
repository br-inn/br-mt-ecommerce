"""PriceStateTransition — tabla declarativa de transiciones legales del FSM de precios.

Creada por migración 20260507_021 (pricing_engine_v51). Contiene las
transiciones canónicas de estado del Price state machine, espejando el
contrato Python en ``app.services.pricing.state_machine.ALLOWED_TRANSITIONS``
para enforcement BD-side via trigger ``prices_state_machine_trg``.

La tabla siempre se gestiona como datos de referencia (seed); no se crea
ni destruye desde el ORM — solo se declara para que Alembic la conozca.
"""

from __future__ import annotations

from sqlalchemy import String
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class PriceStateTransition(Base):
    __tablename__ = "price_state_transitions"

    from_status: Mapped[str] = mapped_column(String, primary_key=True, nullable=False)
    to_status: Mapped[str] = mapped_column(String, primary_key=True, nullable=False)
