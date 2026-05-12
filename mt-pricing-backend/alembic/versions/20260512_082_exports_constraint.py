"""Constraint DB: no-export sin aprobación — US-1B-04-03.

Crea la función PostgreSQL ``fn_channel_approved_prices`` que retorna
solo precios en estado ``approved`` o ``auto_approved`` para un canal
y scheme dado. Esta función es la única puerta de entrada para exportar
precios; garantiza a nivel DB que no pueden salir precios sin aprobación.

Revision ID: 20260512_082
Revises: 20260512_081
Create Date: 2026-05-12
"""

from __future__ import annotations

from collections.abc import Sequence

from alembic import op

revision: str = "20260512_082"
down_revision: str = "20260512_081"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

# ---------------------------------------------------------------------------
# SQL de la función — idempotente via CREATE OR REPLACE
# ---------------------------------------------------------------------------
_CREATE_FN = """\
CREATE OR REPLACE FUNCTION fn_channel_approved_prices(
    p_channel_id  UUID,
    p_scheme_code TEXT
)
RETURNS TABLE(
    price_id  UUID,
    sku       TEXT,
    amount    NUMERIC,
    fx_at     TIMESTAMPTZ
)
LANGUAGE sql
STABLE
AS $$
    SELECT
        p.id          AS price_id,
        p.product_sku AS sku,
        p.amount      AS amount,
        p.fx_at       AS fx_at
    FROM prices p
    WHERE
        p.channel_id  = p_channel_id
        AND p.scheme_code = p_scheme_code
        AND p.status IN ('approved', 'auto_approved');
$$;
"""

_DROP_FN = "DROP FUNCTION IF EXISTS fn_channel_approved_prices(UUID, TEXT);"


def upgrade() -> None:
    op.execute(_CREATE_FN)


def downgrade() -> None:
    op.execute(_DROP_FN)
