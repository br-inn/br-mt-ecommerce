"""jobs_admin_perms — añade `jobs:read`, `jobs:write`, `jobs:run`.

Las rutas `app/api/routes/jobs.py` (admin DatabaseScheduler) usan estos permisos
vía `require_permissions(...)` pero la seed inicial (20260506_001) sólo declaró
permisos para products/prices/costs/users/etc. Esta migration completa el
catálogo y asigna los permisos a los roles canónicos:

- jobs:read  → ti_integracion, gerente_comercial, admin
- jobs:write → ti_integracion, admin
- jobs:run   → ti_integracion, admin

Revision ID: 20260507_012
Revises: 20260507_011
"""

from __future__ import annotations

from collections.abc import Sequence

from alembic import op

revision: str = "20260507_012"
down_revision: str | None = "20260507_011"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute(
        """
        INSERT INTO permissions (code, description) VALUES
            ('jobs:read',  'Listar/leer job_definitions y JobRuns'),
            ('jobs:write', 'Crear/editar job_definitions (cron, args, enabled)'),
            ('jobs:run',   'Disparar ejecuciones ad-hoc (run-now)')
        ON CONFLICT (code) DO NOTHING;
        """
    )

    op.execute(
        """
        INSERT INTO role_permissions (role_id, permission_id)
        SELECT r.id, p.id
        FROM roles r CROSS JOIN permissions p
        WHERE
            (r.code = 'gerente_comercial' AND p.code IN ('jobs:read'))
         OR (r.code = 'ti_integracion'   AND p.code IN ('jobs:read','jobs:write','jobs:run'))
         OR (r.code = 'admin'            AND p.code IN ('jobs:read','jobs:write','jobs:run'))
        ON CONFLICT DO NOTHING;
        """
    )

    # Sync permissions_snapshot JSONB cache (mismo patrón que migration 011 deja
    # implicit; aquí explícito porque assign_role no se ejecuta retroactivo).
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
            SELECT id FROM permissions
            WHERE code IN ('jobs:read', 'jobs:write', 'jobs:run')
        );
        """
    )
    op.execute(
        """
        DELETE FROM permissions
        WHERE code IN ('jobs:read', 'jobs:write', 'jobs:run');
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
