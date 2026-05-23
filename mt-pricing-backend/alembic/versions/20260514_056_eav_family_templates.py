"""Fase 2 — EAV plantillas por familia (PDF §8.2 alignment).

Vincula attribute_definitions a families existentes vía family_attributes.

Templates aplicados (best-effort — si la familia no existe, se loggea y se
salta esa entrada; el seed NO falla):

- filter:
    group filter_dimensions: dim_L, dim_H, dn_nominal
    group filter_general:    manufacturing_method, material_body,
                             material_seal, actuation_type

- ball_valve:
    group ball_dimensions:   dim_L, dim_H, dim_H1, dim_W, torque, kv,
                             dn_nominal, iso5211_flange
    group ball_general:      manufacturing_method, material_body,
                             material_seal, actuation_type

- butterfly_valve:
    group butterfly_dimensions: dim_L, dim_H, dn_nominal, torque,
                                iso5211_flange
    group butterfly_general:    manufacturing_method, material_body,
                                material_seal, actuation_type

Revision ID: 20260514_056
Revises: 20260514_055
Create Date: 2026-05-14
"""

from __future__ import annotations

from collections.abc import Sequence

from alembic import op
from sqlalchemy import text

revision: str = "20260514_056"
down_revision: str | None = "20260514_055"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


# Templates: family_code -> list of (group_code, attribute_code, order_index, is_required)
_TEMPLATES: dict[str, list[tuple[str, str, int, bool]]] = {
    "filter": [
        # filter_dimensions
        ("filter_dimensions", "dim_L", 10, False),
        ("filter_dimensions", "dim_H", 20, False),
        ("filter_dimensions", "dn_nominal", 30, True),
        # filter_general
        ("filter_general", "manufacturing_method", 10, False),
        ("filter_general", "material_body", 20, True),
        ("filter_general", "material_seal", 30, False),
        ("filter_general", "actuation_type", 40, False),
    ],
    "ball_valve": [
        # ball_dimensions
        ("ball_dimensions", "dim_L", 10, False),
        ("ball_dimensions", "dim_H", 20, False),
        ("ball_dimensions", "dim_H1", 30, False),
        ("ball_dimensions", "dim_W", 40, False),
        ("ball_dimensions", "torque", 50, False),
        ("ball_dimensions", "kv", 60, False),
        ("ball_dimensions", "dn_nominal", 70, True),
        ("ball_dimensions", "iso5211_flange", 80, False),
        # ball_general
        ("ball_general", "manufacturing_method", 10, False),
        ("ball_general", "material_body", 20, True),
        ("ball_general", "material_seal", 30, False),
        ("ball_general", "actuation_type", 40, False),
    ],
    "butterfly_valve": [
        # butterfly_dimensions
        ("butterfly_dimensions", "dim_L", 10, False),
        ("butterfly_dimensions", "dim_H", 20, False),
        ("butterfly_dimensions", "dn_nominal", 30, True),
        ("butterfly_dimensions", "torque", 40, False),
        ("butterfly_dimensions", "iso5211_flange", 50, False),
        # butterfly_general
        ("butterfly_general", "manufacturing_method", 10, False),
        ("butterfly_general", "material_body", 20, True),
        ("butterfly_general", "material_seal", 30, False),
        ("butterfly_general", "actuation_type", 40, False),
    ],
}


def upgrade() -> None:
    bind = op.get_bind()

    for family_code, rows in _TEMPLATES.items():
        # Best-effort lookup — log + skip if family missing.
        family_row = bind.execute(
            text("SELECT id FROM families WHERE code = :code"),
            {"code": family_code},
        ).fetchone()
        if family_row is None:
            print(
                f"[mig 056] family '{family_code}' not found in families — "
                f"skipping {len(rows)} template entries (best-effort)."
            )
            continue
        family_id = family_row[0]

        for group_code, attr_code, order_index, is_required in rows:
            attr_row = bind.execute(
                text("SELECT id FROM attribute_definitions WHERE code = :code"),
                {"code": attr_code},
            ).fetchone()
            if attr_row is None:
                print(
                    f"[mig 056] attribute '{attr_code}' not found — skipping "
                    f"link to family '{family_code}'."
                )
                continue
            attr_id = attr_row[0]

            bind.execute(
                text(
                    """
                    INSERT INTO family_attributes
                        (family_id, attribute_id, group_code,
                         order_index, is_required)
                    VALUES (:family_id, :attribute_id, :group_code,
                            :order_index, :is_required)
                    ON CONFLICT (family_id, attribute_id) DO NOTHING
                    """
                ),
                {
                    "family_id": family_id,
                    "attribute_id": attr_id,
                    "group_code": group_code,
                    "order_index": order_index,
                    "is_required": is_required,
                },
            )


def downgrade() -> None:
    bind = op.get_bind()

    for family_code, rows in _TEMPLATES.items():
        family_row = bind.execute(
            text("SELECT id FROM families WHERE code = :code"),
            {"code": family_code},
        ).fetchone()
        if family_row is None:
            continue
        family_id = family_row[0]
        attr_codes = [r[1] for r in rows]
        bind.execute(
            text(
                """
                DELETE FROM family_attributes
                WHERE family_id = :family_id
                  AND attribute_id IN (
                      SELECT id FROM attribute_definitions
                      WHERE code = ANY(:codes)
                  )
                """
            ),
            {"family_id": family_id, "codes": attr_codes},
        )
