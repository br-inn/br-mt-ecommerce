"""audit_perms — añade `audit:read` para la timeline de eventos.

US-1A-07-01 (Sprint 1.5): el endpoint `GET /api/v1/audit/events` requiere
`audit:read`. Este permiso se concede a los roles con visibilidad agregada
sobre cambios de catálogo/usuarios/jobs:

- audit:read → gerente_comercial, ti_integracion, admin

Revision ID: 20260507_014
Revises: 20260507_013
"""

from __future__ import annotations

from collections.abc import Sequence

from alembic import op

revision: str = "20260507_014"
down_revision: str | None = "20260507_013"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute(
        """
        INSERT INTO permissions (code, description) VALUES
            ('audit:read', 'Leer audit_events (timeline producto/usuario/job/role)')
        ON CONFLICT (code) DO NOTHING;
        """
    )

    op.execute(
        """
        INSERT INTO role_permissions (role_id, permission_id)
        SELECT r.id, p.id
        FROM roles r CROSS JOIN permissions p
        WHERE
            (r.code = 'gerente_comercial' AND p.code = 'audit:read')
         OR (r.code = 'ti_integracion'    AND p.code = 'audit:read')
         OR (r.code = 'admin'             AND p.code = 'audit:read')
        ON CONFLICT DO NOTHING;
        """
    )

    op.execute(
        """
        UPDATE roles r
        SET permissions_snapshot = COALESCE(
            (
                SELECT jsonb_agg(p.code ORDER BY p.code)
                FROM role_permissions rp
                JOIN permissions p ON p.id = rp.permission_id
                WHERE rp.role_id = r.id
            ),
            '[]'::jsonb
        )
        WHERE r.code IN ('gerente_comercial', 'ti_integracion', 'admin');
        """
    )


def downgrade() -> None:
    op.execute(
        """
        DELETE FROM role_permissions
        WHERE permission_id IN (
            SELECT id FROM permissions WHERE code = 'audit:read'
        );
        """
    )
    op.execute("DELETE FROM permissions WHERE code = 'audit:read';")
    op.execute(
        """
        UPDATE roles r
        SET permissions_snapshot = COALESCE(
            (
                SELECT jsonb_agg(p.code ORDER BY p.code)
                FROM role_permissions rp
                JOIN permissions p ON p.id = rp.permission_id
                WHERE rp.role_id = r.id
            ),
            '[]'::jsonb
        )
        WHERE r.code IN ('gerente_comercial', 'ti_integracion', 'admin');
        """
    )
