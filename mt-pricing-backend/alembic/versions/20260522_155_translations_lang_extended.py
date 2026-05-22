"""Extend product_translations.lang constraint to include fr/de/it/pt.
Add ai_generated to TranslationStatus enum.
"""
from __future__ import annotations

from alembic import op

revision = "20260522_155"
down_revision = "20260602_146"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # 1. Extend lang CHECK constraint
    op.drop_constraint("ck_translations_lang", "product_translations")
    op.create_check_constraint(
        "ck_translations_lang",
        "product_translations",
        "lang IN ('es', 'ar', 'en', 'fr', 'de', 'it', 'pt')",
    )

    # 2. Extend status CHECK constraint to include ai_generated
    # (constraint is String+CHECK, not a native PG enum — simple drop+recreate)
    op.drop_constraint("ck_translations_status", "product_translations")
    op.create_check_constraint(
        "ck_translations_status",
        "product_translations",
        "status IN ('pending','draft','ai_generated','approved')",
    )


def downgrade() -> None:
    # Restore lang constraint to original three languages
    op.drop_constraint("ck_translations_lang", "product_translations")
    op.create_check_constraint(
        "ck_translations_lang",
        "product_translations",
        "lang IN ('es', 'ar', 'en')",
    )

    # Restore status constraint — note: existing rows with ai_generated
    # will violate this constraint if any were written before downgrade.
    op.drop_constraint("ck_translations_status", "product_translations")
    op.create_check_constraint(
        "ck_translations_status",
        "product_translations",
        "status IN ('pending','draft','approved')",
    )
