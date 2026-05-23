"""Extend documents (doc_number, series_id, signatory) + series (thread_standard, revision)"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "20260529_128"
down_revision = "20260529_127"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # --- documents ---
    op.add_column("documents", sa.Column("doc_number", sa.Text(), nullable=True))
    op.add_column("documents", sa.Column("series_id", sa.UUID(), nullable=True))
    op.add_column("documents", sa.Column("signatory_name", sa.Text(), nullable=True))
    op.add_column("documents", sa.Column("signatory_role", sa.Text(), nullable=True))
    op.create_foreign_key(
        "fk_documents_series", "documents", "series", ["series_id"], ["id"], ondelete="SET NULL"
    )
    op.create_index("ix_doc_series", "documents", ["series_id"])

    # Drop old CHECK and recreate including declaracion_conformidad
    op.drop_constraint("ck_documents_type", "documents", type_="check")
    op.create_check_constraint(
        "ck_documents_type",
        "documents",
        "type IN ('ficha_tecnica','manual','declaracion_ce','declaracion_conformidad','certificado','catalogo')",
    )

    # --- series ---
    op.add_column("series", sa.Column("thread_standard", sa.String(32), nullable=True))
    op.add_column("series", sa.Column("revision", sa.Text(), nullable=True))
    op.add_column("series", sa.Column("revision_date", sa.Date(), nullable=True))


def downgrade() -> None:
    op.drop_column("series", "revision_date")
    op.drop_column("series", "revision")
    op.drop_column("series", "thread_standard")

    op.drop_constraint("ck_documents_type", "documents", type_="check")
    op.create_check_constraint(
        "ck_documents_type",
        "documents",
        "type IN ('ficha_tecnica','manual','declaracion_ce','certificado','catalogo')",
    )
    op.drop_index("ix_doc_series", table_name="documents")
    op.drop_constraint("fk_documents_series", "documents", type_="foreignkey")
    op.drop_column("documents", "signatory_role")
    op.drop_column("documents", "signatory_name")
    op.drop_column("documents", "series_id")
    op.drop_column("documents", "doc_number")
