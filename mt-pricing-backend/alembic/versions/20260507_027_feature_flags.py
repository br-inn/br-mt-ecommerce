"""feature_flags — US-1A-09-08 (Sprint 5).

Crea la tabla ``feature_flags`` (key-value JSONB con audit columns), siembra
los toggles canónicos de red real a ``false`` y registra los permisos
``flags:manage`` + ``kill-switch:execute``.

Cambios:
- Tabla ``feature_flags`` (PK ``key`` TEXT, ``value_jsonb`` JSONB,
  ``updated_by`` UUID FK→users, ``updated_at``, ``created_at``).
- Seed flags (todos ``{"enabled": false}``):
    * ``MT_LIVE_NETWORK_AMAZON_UAE``  — ON activa Bright Data adapter.
    * ``MT_LIVE_NETWORK_NOON_UAE``    — ON activa Playwright Noon adapter.
    * ``MT_LIVE_NETWORK_SP_API``      — ON activa Amazon SP-API real.
    * ``MT_LIVE_NETWORK_NOON_API``    — ON activa Noon partner API real.
    * ``MT_LIVE_NETWORK_VLM_JUDGE``   — ON activa VLM judge HTTP real.
    * ``KILL_SWITCH``                 — global override; ON bypassa todos los
      MT_LIVE_NETWORK_*.
- Permisos ``flags:manage`` (read/write flags) y ``kill-switch:execute``
  (engage/disengage), asignados a roles ``ti_integracion`` y ``admin``.

Slot 027:
- ``down_revision='20260507_026'`` — el slot 026 puede provenir de migraciones
  hermanas (sprint 5 paralelo). Si todavía no existe al hacer ``upgrade head``,
  se renumera localmente.

Revision ID: 20260507_027
Revises: 20260507_026
Create Date: 2026-05-07
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.dialects.postgresql import UUID as PgUUID

from alembic import op

revision: str = "20260507_027"
down_revision: str | None = "20260507_026"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


_FLAGS: tuple[str, ...] = (
    "MT_LIVE_NETWORK_AMAZON_UAE",
    "MT_LIVE_NETWORK_NOON_UAE",
    "MT_LIVE_NETWORK_SP_API",
    "MT_LIVE_NETWORK_NOON_API",
    "MT_LIVE_NETWORK_VLM_JUDGE",
    "KILL_SWITCH",
)


def upgrade() -> None:
    # ----- Tabla feature_flags ----------------------------------------------
    op.create_table(
        "feature_flags",
        sa.Column("key", sa.Text, primary_key=True, nullable=False),
        sa.Column(
            "value_jsonb",
            JSONB,
            nullable=False,
            server_default=sa.text("'{\"enabled\": false}'::jsonb"),
        ),
        sa.Column(
            "updated_by",
            PgUUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
    )

    # ----- Seed canonical flags (all OFF) -----------------------------------
    for key in _FLAGS:
        op.execute(
            f"""
            INSERT INTO feature_flags (key, value_jsonb)
            VALUES ('{key}', '{{"enabled": false}}'::jsonb)
            ON CONFLICT (key) DO NOTHING;
            """
        )

    # ----- Permissions seed --------------------------------------------------
    op.execute(
        """
        INSERT INTO permissions (code, description) VALUES
            ('flags:manage',
             'Listar y togglear feature flags (excluye kill-switch)'),
            ('kill-switch:execute',
             'Engage / disengage global kill-switch (corta toda la red real)')
        ON CONFLICT (code) DO NOTHING;
        """
    )
    op.execute(
        """
        INSERT INTO role_permissions (role_id, permission_id)
        SELECT r.id, p.id
        FROM roles r CROSS JOIN permissions p
        WHERE
            (r.code = 'ti_integracion' AND p.code IN ('flags:manage', 'kill-switch:execute'))
         OR (r.code = 'admin'          AND p.code IN ('flags:manage', 'kill-switch:execute'))
        ON CONFLICT DO NOTHING;
        """
    )

    # ----- Sync permissions_snapshot JSONB cache (mismo patrón que 012) -----
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
        WHERE r.code IN ('ti_integracion', 'admin');
        """
    )


def downgrade() -> None:
    op.execute(
        """
        DELETE FROM role_permissions
        WHERE permission_id IN (
            SELECT id FROM permissions
            WHERE code IN ('flags:manage', 'kill-switch:execute')
        );
        """
    )
    op.execute(
        """
        DELETE FROM permissions
        WHERE code IN ('flags:manage', 'kill-switch:execute');
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
        WHERE r.code IN ('ti_integracion', 'admin');
        """
    )
    op.drop_table("feature_flags")
