"""US-1B-02-09 — audit trail extendido para prices y exception_rules.

Crea dos triggers DB (belt-and-suspenders) que capturan INSERT/UPDATE
directos a `prices` y `exception_rules` y escriben en `audit_events`,
complementando la capa de aplicación (`AuditRepository.record`).

Revision ID: 20260512_071
Revises: 20260512_070
Create Date: 2026-05-12
"""

from __future__ import annotations

from collections.abc import Sequence

from alembic import op

revision: str = "20260512_071"
down_revision: str = "20260512_070"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # ------------------------------------------------------------------
    # Trigger function: prices → audit_events
    # Captura INSERT y UPDATE; para UPDATE registra payload_diff con
    # old_status / new_status. actor_user_id viene de la sesión local
    # (SET app.current_user_id = '<uuid>') — puede ser NULL para system
    # writes.
    # ------------------------------------------------------------------
    op.execute(
        """
        CREATE OR REPLACE FUNCTION fn_audit_prices()
        RETURNS TRIGGER
        LANGUAGE plpgsql
        SECURITY DEFINER
        AS $$
        DECLARE
            v_actor_id      uuid;
            v_action        text;
            v_payload_diff  jsonb;
            v_old_status    text;
            v_new_status    text;
        BEGIN
            -- Recuperar actor desde sesión local (puede ser NULL)
            BEGIN
                v_actor_id := current_setting('app.current_user_id', true)::uuid;
            EXCEPTION WHEN others THEN
                v_actor_id := NULL;
            END;

            IF TG_OP = 'INSERT' THEN
                v_action       := 'price.status_changed';
                v_old_status   := NULL;
                v_new_status   := NEW.status;
                v_payload_diff := jsonb_build_object(
                    'old_status', v_old_status,
                    'new_status', v_new_status
                );
            ELSE
                -- UPDATE
                v_action       := 'price.status_changed';
                v_old_status   := OLD.status;
                v_new_status   := NEW.status;
                v_payload_diff := jsonb_build_object(
                    'old_status', v_old_status,
                    'new_status', v_new_status
                );
            END IF;

            INSERT INTO audit_events (
                event_at,
                actor_id,
                entity_type,
                entity_id,
                action,
                payload_diff
            ) VALUES (
                now(),
                v_actor_id,
                'price',
                NEW.id::text,
                v_action,
                v_payload_diff
            );

            RETURN NEW;
        END;
        $$;
        """
    )

    op.execute(
        "CREATE TRIGGER trg_audit_prices "
        "AFTER INSERT OR UPDATE ON prices "
        "FOR EACH ROW EXECUTE FUNCTION fn_audit_prices();"
    )

    # ------------------------------------------------------------------
    # Trigger function: exception_rules → audit_events
    # ------------------------------------------------------------------
    op.execute(
        """
        CREATE OR REPLACE FUNCTION fn_audit_exception_rules()
        RETURNS TRIGGER
        LANGUAGE plpgsql
        SECURITY DEFINER
        AS $$
        DECLARE
            v_actor_id      uuid;
            v_action        text;
            v_payload_diff  jsonb;
        BEGIN
            BEGIN
                v_actor_id := current_setting('app.current_user_id', true)::uuid;
            EXCEPTION WHEN others THEN
                v_actor_id := NULL;
            END;

            IF TG_OP = 'INSERT' THEN
                v_action       := 'exception_rule.updated';
                v_payload_diff := jsonb_build_object(
                    'code',   NEW.code,
                    'active', NEW.active
                );
            ELSE
                v_action       := 'exception_rule.updated';
                v_payload_diff := jsonb_build_object(
                    'old_active', OLD.active,
                    'new_active', NEW.active,
                    'code',       NEW.code
                );
            END IF;

            INSERT INTO audit_events (
                event_at,
                actor_id,
                entity_type,
                entity_id,
                action,
                payload_diff
            ) VALUES (
                now(),
                v_actor_id,
                'exception_rule',
                NEW.id::text,
                v_action,
                v_payload_diff
            );

            RETURN NEW;
        END;
        $$;
        """
    )

    op.execute(
        "CREATE TRIGGER trg_audit_exception_rules "
        "AFTER INSERT OR UPDATE ON exception_rules "
        "FOR EACH ROW EXECUTE FUNCTION fn_audit_exception_rules();"
    )


def downgrade() -> None:
    op.execute("DROP TRIGGER IF EXISTS trg_audit_prices ON prices;")
    op.execute("DROP FUNCTION IF EXISTS fn_audit_prices();")
    op.execute("DROP TRIGGER IF EXISTS trg_audit_exception_rules ON exception_rules;")
    op.execute("DROP FUNCTION IF EXISTS fn_audit_exception_rules();")
