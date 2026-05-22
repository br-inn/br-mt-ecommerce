"""Add ai_generated to TranslationStatus CHECK constraint.

Lang constraint already expanded to all 7 languages by migration 20260513_100 —
no lang changes here.
"""
from __future__ import annotations

from alembic import op

revision = "20260522_155"
down_revision = "20260602_146"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Extend status CHECK constraint to include ai_generated.
    # (constraint is String+CHECK, not a native PG enum — simple drop+recreate)
    # Previous constraint (after migration 020): pending, draft, pending_review, approved, stale
    op.execute(
        "ALTER TABLE product_translations DROP CONSTRAINT IF EXISTS ck_translations_status"
    )
    op.create_check_constraint(
        "ck_translations_status",
        "product_translations",
        "status IN ('pending','draft','pending_review','approved','stale','ai_generated')",
    )


def downgrade() -> None:
    # Restore status constraint to the 5-value set that existed after migration 020.
    # Note: existing rows with ai_generated will violate this constraint if any
    # were written before downgrade.
    op.execute(
        "ALTER TABLE product_translations DROP CONSTRAINT IF EXISTS ck_translations_status"
    )
    op.create_check_constraint(
        "ck_translations_status",
        "product_translations",
        "status IN ('pending','draft','pending_review','approved','stale')",
    )
