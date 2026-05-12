"""US-1B-02-01 — price status enum: published + archived + trigger FSM.

Agrega `published` y `archived` al dominio de `prices.status` y crea el
trigger `ck_price_status_transition` como segunda línea de defensa del FSM.

Revision ID: 20260512_070
Revises: 20260517_069
Create Date: 2026-05-12
"""

from __future__ import annotations

from alembic import op

revision: str = "20260512_070"
down_revision: str = "20260517_069"
branch_labels = None
depends_on = None

# Valores completos del enum PriceState tras esta migración
_ALL_STATUS = (
    "draft",
    "pending_review",
    "auto_approved",
    "approved",
    "rejected",
    "published",
    "archived",
    "revised",
    "exported",
    "superseded",
    "migrated",
)

_STATUS_IN = "(" + ",".join(f"'{s}'" for s in _ALL_STATUS) + ")"

# Valores antes de esta migración (sin published/archived)
_OLD_STATUS = (
    "draft",
    "pending_review",
    "auto_approved",
    "approved",
    "rejected",
    "revised",
    "exported",
    "superseded",
    "migrated",
)

_OLD_STATUS_IN = "(" + ",".join(f"'{s}'" for s in _OLD_STATUS) + ")"


def upgrade() -> None:
    # 1. Ampliar CHECK en prices.status
    op.drop_constraint("ck_prices_status", "prices", type_="check")
    op.create_check_constraint(
        "ck_prices_status",
        "prices",
        f"status IN {_STATUS_IN}",
    )

    # 2. Ampliar CHECKs en price_approval_events
    op.drop_constraint(
        "ck_price_approval_events_from_status", "price_approval_events", type_="check"
    )
    op.drop_constraint(
        "ck_price_approval_events_to_status", "price_approval_events", type_="check"
    )
    op.create_check_constraint(
        "ck_price_approval_events_from_status",
        "price_approval_events",
        f"from_status IN {_STATUS_IN}",
    )
    op.create_check_constraint(
        "ck_price_approval_events_to_status",
        "price_approval_events",
        f"to_status IN {_STATUS_IN}",
    )

    # 3. Trigger function — segunda línea de defensa FSM
    op.execute("""
        CREATE OR REPLACE FUNCTION fn_check_price_status_transition()
        RETURNS TRIGGER AS $$
        BEGIN
            IF OLD.status IS NOT DISTINCT FROM NEW.status THEN
                RETURN NEW;
            END IF;

            IF NOT (
                (OLD.status = 'draft'         AND NEW.status IN ('auto_approved','pending_review','rejected')) OR
                (OLD.status = 'auto_approved' AND NEW.status IN ('approved','exported','published','revised')) OR
                (OLD.status = 'pending_review' AND NEW.status IN ('approved','rejected','revised')) OR
                (OLD.status = 'approved'      AND NEW.status IN ('exported','published','revised')) OR
                (OLD.status = 'rejected'      AND NEW.status = 'draft') OR
                (OLD.status = 'revised'       AND NEW.status IN ('pending_review','rejected')) OR
                (OLD.status = 'published'     AND NEW.status = 'archived') OR
                (OLD.status = 'exported'      AND NEW.status = 'archived') OR
                (OLD.status = 'migrated'      AND NEW.status IN ('approved','rejected'))
            ) THEN
                RAISE EXCEPTION
                    'Transición inválida en prices: % → %  (id=%)',
                    OLD.status, NEW.status, OLD.id;
            END IF;

            RETURN NEW;
        END;
        $$ LANGUAGE plpgsql;
    """)

    op.execute("DROP TRIGGER IF EXISTS ck_price_status_transition ON prices;")
    op.execute("""
        CREATE TRIGGER ck_price_status_transition
        BEFORE UPDATE ON prices
        FOR EACH ROW
        WHEN (OLD.status IS DISTINCT FROM NEW.status)
        EXECUTE FUNCTION fn_check_price_status_transition();
    """)


def downgrade() -> None:
    op.execute("DROP TRIGGER IF EXISTS ck_price_status_transition ON prices;")
    op.execute("DROP FUNCTION IF EXISTS fn_check_price_status_transition();")

    op.drop_constraint("ck_prices_status", "prices", type_="check")
    op.create_check_constraint(
        "ck_prices_status",
        "prices",
        f"status IN {_OLD_STATUS_IN}",
    )

    op.drop_constraint(
        "ck_price_approval_events_from_status", "price_approval_events", type_="check"
    )
    op.drop_constraint(
        "ck_price_approval_events_to_status", "price_approval_events", type_="check"
    )
    op.create_check_constraint(
        "ck_price_approval_events_from_status",
        "price_approval_events",
        f"from_status IN {_OLD_STATUS_IN}",
    )
    op.create_check_constraint(
        "ck_price_approval_events_to_status",
        "price_approval_events",
        f"to_status IN {_OLD_STATUS_IN}",
    )
