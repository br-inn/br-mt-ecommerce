"""materials dedupe — remap EN duplicates to Spanish canonicals + deactivate.

Stage 3 — Wave 11 follow-up (post-046):

La migración 046 hizo backfill desde ``products.material`` TEXT y, además
del seed inicial de 6 códigos canónicos en español (``laton``,
``acero_inoxidable``, ``fundicion``, ``galvanizado``, ``plastico_pvc``,
``ppr``), insertó ~16 códigos en inglés (``brass``, ``cast_iron``,
``stainless_steel``, ``stainless_steel_304``, ``stainless_steel_316l``,
``galvanised_steel``, ``copper``, ``multilayer``, ``polyethylene``,
``pe_xa``, ``pvc``, ``pvc-u``, ``polyamide``, ``abs``, ``nbr``, ``epdm``).

Como resultado, ~3.405 productos quedaron apuntando a duplicados EN en
lugar de a los canónicos en español del catálogo MT.

Esta migración hace **3 cosas idempotentes**:

1. **Remap**: ``products.material_id`` de duplicados EN → canónico ES.
2. **Deactivate**: 8 duplicados EN remapeados → ``active=false`` (no se
   borran para preservar histórico/auditoría y evitar romper FK por
   ``ondelete=RESTRICT``).
3. **Rename in place**: 8 entradas EN no mapeadas (no tienen canónico ES
   equivalente) renombradas a nombre en español y con ``family_kind``
   asignado. ``code`` se mantiene para no romper referencias.

Mapeo a canónicos:
- ``brass``                → ``laton``
- ``cast_iron``            → ``fundicion``
- ``stainless_steel``      → ``acero_inoxidable``
- ``stainless_steel_304``  → ``acero_inoxidable``
- ``stainless_steel_316l`` → ``acero_inoxidable``
- ``galvanised_steel``     → ``galvanizado``
- ``pvc``                  → ``plastico_pvc``
- ``pvc-u``                → ``plastico_pvc``

Renombrados in place (mismo ``code``, nuevo ``name`` ES + ``family_kind``):
- ``copper``       → "Cobre"      (metal)
- ``multilayer``   → "Multicapa"  (composite)
- ``polyethylene`` → "Polietileno"(polymer)
- ``pe_xa``        → "PE-Xa"      (polymer)
- ``polyamide``    → "Poliamida"  (polymer)
- ``abs``          → "ABS"        (polymer)
- ``nbr``          → "NBR"        (polymer)
- ``epdm``         → "EPDM"       (polymer)

Revision ID: 20260509_047
Revises: 20260509_046
Create Date: 2026-05-09
"""

from __future__ import annotations

from collections.abc import Sequence

from alembic import op

revision: str = "20260509_047"
down_revision: str | None = "20260509_046"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


# (en_code, es_canonical_code) — duplicados que se colapsan en el canónico ES.
_REMAP: tuple[tuple[str, str], ...] = (
    ("brass", "laton"),
    ("cast_iron", "fundicion"),
    ("stainless_steel", "acero_inoxidable"),
    ("stainless_steel_304", "acero_inoxidable"),
    ("stainless_steel_316l", "acero_inoxidable"),
    ("galvanised_steel", "galvanizado"),
    ("pvc", "plastico_pvc"),
    ("pvc-u", "plastico_pvc"),
)

# (code, new_name, family_kind) — entradas EN sin canónico ES equivalente,
# renombradas in place a nombre en español con family_kind asignado.
_RENAME_IN_PLACE: tuple[tuple[str, str, str], ...] = (
    ("copper", "Cobre", "metal"),
    ("multilayer", "Multicapa", "composite"),
    ("polyethylene", "Polietileno", "polymer"),
    ("pe_xa", "PE-Xa", "polymer"),
    ("polyamide", "Poliamida", "polymer"),
    ("abs", "ABS", "polymer"),
    ("nbr", "NBR", "polymer"),
    ("epdm", "EPDM", "polymer"),
)


def upgrade() -> None:
    # 1. Remap products.material_id: EN duplicate → ES canonical.
    #    Idempotente: el WHERE filtra por code EN específico; tras correrla
    #    una vez los productos ya apuntan al ES y el JOIN del UPDATE no
    #    encuentra filas para reasignar.
    for en_code, es_code in _REMAP:
        op.execute(
            f"""
            UPDATE products p
            SET material_id = (SELECT id FROM materials WHERE code = '{es_code}')
            WHERE p.material_id = (SELECT id FROM materials WHERE code = '{en_code}');
            """
        )

    # 2. Deactivate los 8 EN remapeados — no DELETE (RESTRICT FK + auditoría).
    en_codes_remapped = ", ".join(f"'{code}'" for code, _ in _REMAP)
    op.execute(
        f"""
        UPDATE materials
        SET active = false,
            updated_at = now()
        WHERE code IN ({en_codes_remapped});
        """
    )

    # 3. Rename in place los 8 EN no-mapeados: name → ES, family_kind set.
    for code, new_name, family_kind in _RENAME_IN_PLACE:
        # Escape single quotes en el nombre por seguridad (no aplica aquí pero
        # mantenemos la convención).
        safe_name = new_name.replace("'", "''")
        op.execute(
            f"""
            UPDATE materials
            SET name = '{safe_name}',
                family_kind = '{family_kind}',
                updated_at = now()
            WHERE code = '{code}';
            """
        )


def downgrade() -> None:
    # Revertir: re-activar duplicados EN. NO re-mapeamos products
    # (perderíamos la info de a qué canónico apuntaban). Los renames in
    # place se dejan tal cual — el rollback estricto requiere snapshot
    # previo del estado, fuera de scope para una dedupe.
    en_codes_remapped = ", ".join(f"'{code}'" for code, _ in _REMAP)
    op.execute(
        f"""
        UPDATE materials
        SET active = true,
            updated_at = now()
        WHERE code IN ({en_codes_remapped});
        """
    )
