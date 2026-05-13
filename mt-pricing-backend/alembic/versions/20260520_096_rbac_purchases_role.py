"""rbac_purchases_role — merge heads + rol responsable_compras + permisos faltantes.

Problemas resueltos:
  1. Merge de los dos heads activos (095 / 076) en uno solo.
  2. Permisos que el código usaba pero no existían en BD:
       purchases:read, purchases:write  (módulo Compras EP-INV-01)
       imports:read, imports:write      (importadores PIM / costos / materiales)
       admin:read                       (feature flags, calibrator — sidebar)
       users:invite                     (invitar usuarios)
       users:assign_role                (asignar/revocar rol desde admin UI)
       users:force_logout               (forzar logout)
  3. Nuevo rol `responsable_compras` para el módulo de inventario/compras.
  4. Asignación rol → permiso para todos los roles canónicos.
  5. Resync de permissions_snapshot en todos los roles afectados.

Revision ID: 096
Revises: 095, 076  (merge)
Create Date: 2026-05-20
"""

from __future__ import annotations

from collections.abc import Sequence

from alembic import op

revision: str = "096"
down_revision: tuple[str, str] = ("095", "076")
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # ------------------------------------------------------------------
    # 1. Permisos nuevos (idempotente)
    # ------------------------------------------------------------------
    op.execute(
        """
        INSERT INTO permissions (code, description) VALUES
            ('purchases:read',      'Leer pedidos de compra y recepciones'),
            ('purchases:write',     'Crear/gestionar pedidos y recepciones de compra'),
            ('imports:read',        'Ver historial de importaciones (admin)'),
            ('imports:write',       'Ejecutar importaciones PIM / costos / materiales'),
            ('admin:read',          'Acceso read-only a configuración admin (flags, calibrator)'),
            ('users:invite',        'Invitar usuarios al sistema'),
            ('users:assign_role',   'Asignar o revocar roles a usuarios'),
            ('users:force_logout',  'Forzar cierre de sesión de un usuario')
        ON CONFLICT (code) DO NOTHING;
        """
    )

    # ------------------------------------------------------------------
    # 2. Rol responsable_compras (nuevo)
    # ------------------------------------------------------------------
    op.execute(
        """
        INSERT INTO roles (code, name, description, is_system)
        VALUES (
            'responsable_compras',
            'Responsable de Compras',
            'Gestión de pedidos de compra, recepciones y coste MAP',
            true
        )
        ON CONFLICT (code) DO NOTHING;
        """
    )

    # ------------------------------------------------------------------
    # 3. Asignación rol → permiso
    # ------------------------------------------------------------------
    op.execute(
        """
        INSERT INTO role_permissions (role_id, permission_id)
        SELECT r.id, p.id
        FROM roles r CROSS JOIN permissions p
        WHERE
            -- responsable_compras: acceso completo al módulo de compras
            (r.code = 'responsable_compras' AND p.code IN (
                'purchases:read', 'purchases:write',
                'products:read', 'suppliers:read', 'costs:read',
                'imports:read', 'fx:read'
            ))
            -- comercial: puede ver pedidos (read-only)
         OR (r.code = 'comercial' AND p.code IN (
                'purchases:read'
            ))
            -- gerente_comercial: puede ver pedidos y reportes
         OR (r.code = 'gerente_comercial' AND p.code IN (
                'purchases:read', 'imports:read', 'admin:read'
            ))
            -- ti_integracion: gestión completa de compras, imports y users
         OR (r.code = 'ti_integracion' AND p.code IN (
                'purchases:read', 'purchases:write',
                'imports:read', 'imports:write',
                'admin:read',
                'users:invite', 'users:assign_role', 'users:force_logout'
            ))
            -- admin: todos los permisos nuevos
         OR (r.code = 'admin' AND p.code IN (
                'purchases:read', 'purchases:write',
                'imports:read', 'imports:write',
                'admin:read',
                'users:invite', 'users:assign_role', 'users:force_logout'
            ))
        ON CONFLICT DO NOTHING;
        """
    )

    # ------------------------------------------------------------------
    # 4. Resync permissions_snapshot en todos los roles afectados
    # ------------------------------------------------------------------
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
        WHERE r.code IN (
            'responsable_compras',
            'comercial',
            'gerente_comercial',
            'ti_integracion',
            'admin'
        );
        """
    )


def downgrade() -> None:
    # 1. Quitar role_permissions de los permisos nuevos
    op.execute(
        """
        DELETE FROM role_permissions
        WHERE permission_id IN (
            SELECT id FROM permissions
            WHERE code IN (
                'purchases:read', 'purchases:write',
                'imports:read', 'imports:write',
                'admin:read',
                'users:invite', 'users:assign_role', 'users:force_logout'
            )
        );
        """
    )

    # 2. Quitar role_permissions del rol responsable_compras
    op.execute(
        """
        DELETE FROM role_permissions
        WHERE role_id IN (SELECT id FROM roles WHERE code = 'responsable_compras');
        """
    )

    # 3. Borrar rol
    op.execute(
        "DELETE FROM roles WHERE code = 'responsable_compras' AND is_system = true;"
    )

    # 4. Borrar permisos nuevos
    op.execute(
        """
        DELETE FROM permissions
        WHERE code IN (
            'purchases:read', 'purchases:write',
            'imports:read', 'imports:write',
            'admin:read',
            'users:invite', 'users:assign_role', 'users:force_logout'
        );
        """
    )

    # 5. Resync snapshot
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
        WHERE r.code IN (
            'comercial', 'gerente_comercial', 'ti_integracion', 'admin'
        );
        """
    )
