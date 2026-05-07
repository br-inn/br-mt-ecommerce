"""rbac_dedicated — US-1A-07-04 (Sprint 5).

Permisos dedicados por dominio para reemplazar el uso oportunista de
``products:read|write`` en endpoints de matches/channels/pricing-engine.

Cambios:

- Permisos nuevos:
  - ``matches:read``           — listar/ver match candidates (Sprint 3+).
  - ``matches:write``          — refresh/validate/discard.
  - ``prices:override_review`` — disparar review/override sobre el flujo
    state-machine del motor v5.1 (counter-proposals, simulate con
    overrides arbitrarios). Distinto de ``prices:approve`` (gerente solo).

- Permisos ya existentes (no duplicar — ON CONFLICT):
  - ``channels:read`` y ``channels:manage`` (seedeados en migración 010).
  - ``graphrag:admin`` (seedeado en migración 025 por Agent E S4 — esta
    migración los referencia para asignación a ``ti_integracion`` por
    coherencia, pero el INSERT en ``permissions`` es idempotente).

- Rol nuevo ``auditor`` (read-only, RBAC fino) — agregado como ``is_system``.

- Mapping rol → permiso:

  =================== =====================================================
  Rol                 Permisos asignados (delta de esta migración)
  =================== =====================================================
  comercial           matches:read, matches:write
  gerente_comercial   matches:write, channels:manage, prices:override_review
  ti_integracion      channels:manage, graphrag:admin
  auditor             matches:read, channels:read (read-only)
  admin               TODO downstream — admin recibe todos los permisos vía
                      la regla `r.code = 'admin'` del seed inicial cuando
                      se ejecutan las migraciones. Aquí lo asignamos
                      explícitamente para que `permissions_snapshot` quede
                      coherente.
  =================== =====================================================

NOTA: ``permissions_snapshot`` (JSONB cache en ``roles``) se resincroniza al
final del upgrade — mismo patrón que ``20260507_012_jobs_admin_perms``.

Revision ID: 20260507_026
Revises: 20260507_025
Create Date: 2026-05-07
"""

from __future__ import annotations

from collections.abc import Sequence

from alembic import op

revision: str = "20260507_026"
down_revision: str | None = "20260507_025"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # ----- 1. Seed permisos nuevos (idempotente) ----------------------------
    op.execute(
        """
        INSERT INTO permissions (code, description) VALUES
            ('matches:read',           'Listar/ver match candidates'),
            ('matches:write',          'Refresh/validate/discard match candidates'),
            ('prices:override_review', 'Disparar review/override sobre prices (counter-proposals, what-if)')
        ON CONFLICT (code) DO NOTHING;
        """
    )

    # Permisos ya existentes — re-aseguramos (idempotente). Si por algún
    # motivo la migración 010 / 025 no se ejecutó (entornos esquemados a
    # mano), esta migración cubre el gap.
    op.execute(
        """
        INSERT INTO permissions (code, description) VALUES
            ('channels:read',   'Listar canales'),
            ('channels:manage', 'Gestionar estado de canales'),
            ('graphrag:admin',  'Administrar GraphRAG (replay CDC, ver health avanzado)')
        ON CONFLICT (code) DO NOTHING;
        """
    )

    # ----- 2. Rol ``auditor`` (read-only) -----------------------------------
    op.execute(
        """
        INSERT INTO roles (code, name, description, is_system) VALUES
            ('auditor', 'Auditor', 'Acceso read-only — auditorías internas/externas', true)
        ON CONFLICT (code) DO NOTHING;
        """
    )

    # ----- 3. Asignación rol → permiso --------------------------------------
    op.execute(
        """
        INSERT INTO role_permissions (role_id, permission_id)
        SELECT r.id, p.id
        FROM roles r CROSS JOIN permissions p
        WHERE
            (r.code = 'comercial'         AND p.code IN ('matches:read', 'matches:write'))
         OR (r.code = 'gerente_comercial' AND p.code IN ('matches:write', 'channels:manage', 'prices:override_review'))
         OR (r.code = 'ti_integracion'    AND p.code IN ('channels:manage', 'graphrag:admin'))
         OR (r.code = 'auditor'           AND p.code IN ('matches:read', 'channels:read'))
         OR (r.code = 'admin'             AND p.code IN (
                'matches:read', 'matches:write',
                'channels:read', 'channels:manage',
                'prices:override_review', 'graphrag:admin'
            ))
        ON CONFLICT DO NOTHING;
        """
    )

    # ----- 4. Resync ``permissions_snapshot`` -------------------------------
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
        WHERE r.code IN ('comercial', 'gerente_comercial', 'ti_integracion', 'auditor', 'admin');
        """
    )


def downgrade() -> None:
    # 1. Quitar role_permissions de los nuevos permisos.
    op.execute(
        """
        DELETE FROM role_permissions
        WHERE permission_id IN (
            SELECT id FROM permissions
            WHERE code IN ('matches:read', 'matches:write', 'prices:override_review')
        );
        """
    )

    # 2. Quitar asignaciones específicas de auditor (incluye channels:read
    #    y matches:read si existían). La fila role 'auditor' se elimina
    #    abajo por completo.
    op.execute(
        """
        DELETE FROM role_permissions
        WHERE role_id IN (SELECT id FROM roles WHERE code = 'auditor');
        """
    )

    # 3. Borrar permisos nuevos. NO tocamos channels:* / graphrag:admin
    #    (los seedeó otra migration y su downgrade los purga).
    op.execute(
        """
        DELETE FROM permissions
        WHERE code IN ('matches:read', 'matches:write', 'prices:override_review');
        """
    )

    # 4. Borrar rol auditor (solo si lo creó esta migration — chequeo por
    #    is_system + code).
    op.execute(
        """
        DELETE FROM roles WHERE code = 'auditor' AND is_system = true;
        """
    )

    # 5. Resync permissions_snapshot.
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
        WHERE r.code IN ('comercial', 'gerente_comercial', 'ti_integracion', 'admin');
        """
    )
