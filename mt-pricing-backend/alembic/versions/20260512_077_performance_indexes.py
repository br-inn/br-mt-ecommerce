"""Performance hardening — índices en tablas de alta frecuencia.

Revision ID: 20260512_077
Revises: 20260512_075
Create Date: 2026-05-12
"""

from __future__ import annotations

from collections.abc import Sequence

from alembic import op
from sqlalchemy import text

revision: str = "20260512_077"
down_revision: str = "20260512_075"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # ------------------------------------------------------------------
    # prices
    # Existentes en DB (NO duplicar):
    #   idx_prices_lookup       (product_sku, channel_id, scheme_code)
    #   idx_prices_pending      (status) WHERE status IN (pending_review,draft) — partial
    #   idx_prices_active       (product_sku, channel_id, scheme_code) WHERE valid_to IS NULL
    #   idx_prices_escalated    (escalated) WHERE escalated=true — ya existe
    #   uq_prices_one_approved_active
    #   + índices implícitos en product_sku y status
    #
    # Nuevos: filtro por canal + status para cola aprobación; orden recientes.
    # ------------------------------------------------------------------
    op.create_index(
        "idx_prices_channel_status",
        "prices",
        ["channel_id", "status"],
        postgresql_using="btree",
    )
    op.create_index(
        "idx_prices_updated_at",
        "prices",
        ["updated_at"],
        postgresql_using="btree",
        postgresql_ops={"updated_at": "DESC"},
    )

    # ------------------------------------------------------------------
    # exception_rules
    # Existentes en DB (NO duplicar):
    #   idx_exception_rules_active  (active) WHERE active=true — partial
    #
    # Nuevo: combo (active, channel_id) para el ExceptionEvaluator que
    #   filtra reglas activas + canal específico o NULL (global).
    # ------------------------------------------------------------------
    op.create_index(
        "idx_exception_rules_active_channel",
        "exception_rules",
        ["active", "channel_id"],
        postgresql_using="btree",
    )

    # ------------------------------------------------------------------
    # match_candidates
    # Existentes en DB (NO duplicar):
    #   idx_match_candidates_sku_status        (product_sku, status)
    #   idx_match_candidates_confidence        (calibrated_confidence) — mig 074
    #   idx_match_candidates_calibrated        (calibrated_confidence) — alias previo
    #   idx_match_candidates_unique_external   UNIQUE
    #
    # Nuevo: label para filtrar accept/reject/skip en queries de training data.
    # ------------------------------------------------------------------
    op.create_index(
        "idx_match_candidates_label",
        "match_candidates",
        ["label"],
        postgresql_using="btree",
        postgresql_where=text("label IS NOT NULL"),
    )

    # ------------------------------------------------------------------
    # audit_events
    # Existentes en DB (NO duplicar):
    #   idx_audit_entity   (entity_type, entity_id, event_at)
    #   idx_audit_actor    (actor_id, event_at)
    #   idx_audit_action   (action, event_at)
    #   idx_audit_request  (request_id)
    #
    # Tabla particionada RANGE(event_at). Nuevo índice (entity_type, event_at)
    # cubre timeline queries que filtran por tipo sin entity_id.
    # ------------------------------------------------------------------
    op.create_index(
        "idx_audit_events_entity_type_event_at",
        "audit_events",
        ["entity_type", "event_at"],
        postgresql_using="btree",
        postgresql_ops={"event_at": "DESC"},
    )


def downgrade() -> None:
    op.drop_index("idx_audit_events_entity_type_event_at", table_name="audit_events")
    op.drop_index("idx_match_candidates_label", table_name="match_candidates")
    op.drop_index("idx_exception_rules_active_channel", table_name="exception_rules")
    op.drop_index("idx_prices_updated_at", table_name="prices")
    op.drop_index("idx_prices_channel_status", table_name="prices")
