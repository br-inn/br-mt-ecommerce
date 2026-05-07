"""suppliers_permissions — añade `suppliers:read` y `suppliers:write` (US-1A-03-02).

Las rutas `app/api/routes/suppliers.py` ya usaban estos permisos vía
`require_permissions(...)` pero la seed inicial (20260506_001) sólo declaró
permisos para products/prices/costs/etc. Esta migration completa el catálogo y
asigna los permisos a los roles canónicos:

- suppliers:read → comercial, gerente_comercial, ti_integracion, admin
- suppliers:write → ti_integracion, admin (gerente_comercial sólo lee)

Revision ID: 20260507_011
Revises: 20260507_010
"""

from __future__ import annotations

from collections.abc import Sequence

from alembic import op

revision: str = "20260507_011"
down_revision: str | None = "20260507_010"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute(
        """
        INSERT INTO permissions (code, description) VALUES
            ('suppliers:read',  'Listar/leer proveedores'),
            ('suppliers:write', 'Crear/editar proveedores')
        ON CONFLICT (code) DO NOTHING;
        """
    )

    # Asignar a roles canónicos.
    op.execute(
        """
        INSERT INTO role_permissions (role_id, permission_id)
        SELECT r.id, p.id
        FROM roles r CROSS JOIN permissions p
        WHERE
            (r.code = 'comercial'        AND p.code IN ('suppliers:read'))
         OR (r.code = 'gerente_comercial' AND p.code IN ('suppliers:read'))
         OR (r.code = 'ti_integracion'   AND p.code IN ('suppliers:read','suppliers:write'))
         OR (r.code = 'admin'            AND p.code IN ('suppliers:read','suppliers:write'))
        ON CONFLICT DO NOTHING;
        """
    )


def downgrade() -> None:
    op.execute(
        """
        DELETE FROM role_permissions
        WHERE permission_id IN (
            SELECT id FROM permissions
            WHERE code IN ('suppliers:read', 'suppliers:write')
        );
        """
    )
    op.execute(
        """
        DELETE FROM permissions WHERE code IN ('suppliers:read', 'suppliers:write');
        """
    )
