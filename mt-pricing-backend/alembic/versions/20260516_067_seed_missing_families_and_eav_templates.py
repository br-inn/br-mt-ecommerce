"""Follow-up of mig 056 — seed missing families needed for EAV templates.

Mig 056 (``20260514_056_eav_family_templates.py``) corrió en best-effort y
saltó las 3 familias ``filter`` / ``ball_valve`` / ``butterfly_valve`` porque
todavía no existían en la tabla ``families``. Esta migración:

1. Inserta esas 3 familias (idempotente, ``ON CONFLICT (code) DO NOTHING``).
2. Re-ejecuta la lógica de seed EAV templates de mig 056 sólo para esas
   familias (link de attributes a families según PDF §8.2).

Si algún ``attribute_definitions.code`` referenciado no existe, se loggea
via ``print`` y se salta (best-effort, igual que mig 056).

Downgrade: drop ``family_attributes`` para esos 3 family ids. NO drop las
families — ésas son data persistente y otras migraciones futuras pueden
asumir su existencia.

Revision ID: 20260516_067
Revises: 20260515_066
Create Date: 2026-05-16
"""

from __future__ import annotations

from collections.abc import Sequence

from alembic import op
from sqlalchemy import text

revision: str = "20260516_067"
down_revision: str | None = "20260515_066"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


# Families a sembrar: code -> (name, slug-ish description marker).
# `families` schema (verificado vía information_schema):
#   id, code, name, description, sort_order, active, created_at, updated_at.
# Slug no existe como columna — se omite (los archivos de spec viven en
# `app/schemas/specs/` con nombre = code).
_FAMILIES: list[tuple[str, str]] = [
    ("filter", "Filter"),
    ("ball_valve", "Ball Valve"),
    ("butterfly_valve", "Butterfly Valve"),
]


# Templates copiados literal de mig 056 (PDF §8.2):
#   family_code -> [(group_code, attribute_code, order_index, is_required), ...]
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

    # ------------------------------------------------------------------
    # 1) Insertar las 3 familias faltantes (idempotente).
    # ------------------------------------------------------------------
    for code, name in _FAMILIES:
        bind.execute(
            text(
                """
                INSERT INTO families (code, name, sort_order, active)
                VALUES (:code, :name, 0, true)
                ON CONFLICT (code) DO NOTHING
                """
            ),
            {"code": code, "name": name},
        )
        print(f"[mig 067] ensured family '{code}' present")

    # ------------------------------------------------------------------
    # 2) Re-ejecutar seed EAV templates para esas familias (best-effort).
    # ------------------------------------------------------------------
    inserted = 0
    skipped = 0
    for family_code, rows in _TEMPLATES.items():
        family_row = bind.execute(
            text("SELECT id FROM families WHERE code = :code"),
            {"code": family_code},
        ).fetchone()
        if family_row is None:
            print(
                f"[mig 067] family '{family_code}' not found AFTER insert — "
                f"unexpected; skipping {len(rows)} entries."
            )
            continue
        family_id = family_row[0]

        for group_code, attr_code, order_index, is_required in rows:
            attr_row = bind.execute(
                text(
                    "SELECT id FROM attribute_definitions WHERE code = :code"
                ),
                {"code": attr_code},
            ).fetchone()
            if attr_row is None:
                print(
                    f"[mig 067] attribute '{attr_code}' not found — "
                    f"skipping link to family '{family_code}'."
                )
                skipped += 1
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
            inserted += 1

    print(
        f"[mig 067] EAV template seed done: inserted={inserted} "
        f"skipped={skipped}"
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
    # NOTE: las families NO se borran (data persistente).
