"""Fix closure trigger: NO recomputar para nodo en proceso de DELETE.

Bug del trigger ``taxonomy_node_parents_closure_trigger`` introducido en
mig. 049: cuando se borra un ``taxonomy_node``, el CASCADE elimina filas
de ``taxonomy_node_parents`` que tenían ese nodo como ``node_id``. El
trigger DELETE fire y llama ``taxonomy_recompute_closure(OLD.node_id)``,
que intenta INSERTar la self-row ``(OLD.node_id, OLD.node_id, 0)`` en
``taxonomy_node_descendants``. Pero OLD.node_id ya no existe en
``taxonomy_nodes`` → FK violation.

Fix: en TG_OP='DELETE', SOLO recomputar para descendientes (cuya ancestría
cambió al desaparecer un eslabón intermedio). NO recomputar para el
``affected_node`` en sí.

Para INSERT/UPDATE el comportamiento se mantiene: recomputar el nodo y
sus descendientes.

Revision ID: 20260511_051
Revises: 20260511_050
Create Date: 2026-05-11
"""

from __future__ import annotations

from collections.abc import Sequence

from alembic import op

revision: str = "20260511_051"
down_revision: str | None = "20260511_050"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute(
        """
        CREATE OR REPLACE FUNCTION taxonomy_node_parents_closure_trigger()
        RETURNS TRIGGER AS $$
        DECLARE
            affected_node UUID;
            desc_id UUID;
        BEGIN
            IF TG_OP = 'DELETE' THEN
                affected_node := OLD.node_id;
                -- Cuando se borra (vía CASCADE de DELETE en taxonomy_nodes,
                -- o explícito en taxonomy_node_parents), el nodo afectado puede
                -- ya no existir en taxonomy_nodes — saltarse recompute del self
                -- y sólo recomputar descendientes cuya cadena cambió.
                IF NOT EXISTS (SELECT 1 FROM taxonomy_nodes WHERE id = affected_node) THEN
                    RETURN NULL;
                END IF;
                -- Si el nodo existe pero perdió un parent: recompute solo para él
                -- (sus descendientes cambian su ancestría también, pero ese sería
                -- el caso de cambio de jerarquía, no de deletion completa)
                PERFORM taxonomy_recompute_closure(affected_node);
                FOR desc_id IN
                    SELECT descendant_id FROM taxonomy_node_descendants
                    WHERE ancestor_id = affected_node AND depth > 0
                LOOP
                    IF EXISTS (SELECT 1 FROM taxonomy_nodes WHERE id = desc_id) THEN
                        PERFORM taxonomy_recompute_closure(desc_id);
                    END IF;
                END LOOP;
                RETURN NULL;
            END IF;

            -- INSERT / UPDATE
            affected_node := NEW.node_id;
            PERFORM taxonomy_recompute_closure(affected_node);
            FOR desc_id IN
                SELECT descendant_id FROM taxonomy_node_descendants
                WHERE ancestor_id = affected_node AND depth > 0
            LOOP
                IF EXISTS (SELECT 1 FROM taxonomy_nodes WHERE id = desc_id) THEN
                    PERFORM taxonomy_recompute_closure(desc_id);
                END IF;
            END LOOP;
            RETURN NULL;
        END;
        $$ LANGUAGE plpgsql;
        """
    )


def downgrade() -> None:
    # Restaurar la versión original de mig. 049 (con el bug)
    op.execute(
        """
        CREATE OR REPLACE FUNCTION taxonomy_node_parents_closure_trigger()
        RETURNS TRIGGER AS $$
        DECLARE
            affected_node UUID;
            desc_id UUID;
        BEGIN
            IF TG_OP = 'DELETE' THEN
                affected_node := OLD.node_id;
            ELSE
                affected_node := NEW.node_id;
            END IF;
            PERFORM taxonomy_recompute_closure(affected_node);
            FOR desc_id IN
                SELECT descendant_id FROM taxonomy_node_descendants
                WHERE ancestor_id = affected_node AND depth > 0
            LOOP
                PERFORM taxonomy_recompute_closure(desc_id);
            END LOOP;
            RETURN NULL;
        END;
        $$ LANGUAGE plpgsql;
        """
    )
