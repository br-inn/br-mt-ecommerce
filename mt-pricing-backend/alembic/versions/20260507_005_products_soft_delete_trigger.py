"""products_soft_delete_trigger — bloqueo físico de DELETE en products (US-1A-02-10).

Cumple BR-1a-07 / NFR-35: VAT UAE 7-año retention obliga preservar histórico,
por lo tanto NO se permite DELETE físico en `products`. Patrón replicable
a futuras tablas (`costs`, `prices`, `suppliers` — su trigger se aplica en
sus respectivos sprints/migraciones).

Implementación:
- Función `raise_use_soft_delete()` PL/pgSQL que lanza EXCEPTION con SQLSTATE
  custom `'P0001'` y mensaje en español.
- Trigger `BEFORE DELETE ON products FOR EACH ROW`.

El bypass es deliberado para `service_role` (Supabase admin) NO previsto: el
trigger se dispara para *todas* las conexiones, incluyendo `service_role`.
Si en el futuro hace falta una excepción (purge GDPR), se hace por:
1. `ALTER TABLE products DISABLE TRIGGER trg_products_no_hard_delete;`
2. `DELETE ...`
3. `ALTER TABLE ... ENABLE TRIGGER ...`
en una transacción auditada.

API: FastAPI no expone endpoint DELETE — auto-retorna 405 si no está mapeado.
Doble defensa: API capa + DB trigger.

Revision ID: 20260507_005
Revises: 20260507_004
Create Date: 2026-05-07
"""

from __future__ import annotations

from collections.abc import Sequence

from alembic import op

revision: str = "20260507_005"
down_revision: str | None = "20260507_004"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute(
        """
        CREATE OR REPLACE FUNCTION raise_use_soft_delete()
        RETURNS TRIGGER LANGUAGE plpgsql AS $$
        BEGIN
            RAISE EXCEPTION
                'DELETE físico bloqueado por compliance VAT UAE (NFR-35). '
                'Use UPDATE para set active=false (soft-deactivate).'
                USING ERRCODE = 'P0001';
        END
        $$;
        """
    )
    op.execute(
        """
        COMMENT ON FUNCTION raise_use_soft_delete() IS
            'Bloquea DELETE físico en tablas con audit trail VAT-compliant. '
            'Aplicar via BEFORE DELETE trigger row-level.';
        """
    )

    op.execute(
        """
        DROP TRIGGER IF EXISTS trg_products_no_hard_delete ON products;
        CREATE TRIGGER trg_products_no_hard_delete
            BEFORE DELETE ON products
            FOR EACH ROW
            EXECUTE FUNCTION raise_use_soft_delete();
        """
    )


def downgrade() -> None:
    op.execute("DROP TRIGGER IF EXISTS trg_products_no_hard_delete ON products;")
    op.execute("DROP FUNCTION IF EXISTS raise_use_soft_delete();")
