"""dn_nps_dimensions — tabla de referencia DN↔NPS y dimensiones por norma.

Dos tablas nuevas:
  1. dn_nps_reference      — lookup global DN ↔ NPS ↔ OD de tubería (dato fijo de norma).
  2. product_bore_dimensions — bore real + face-to-face por estándar aplicable a cada SKU.

Motivación:
  El campo `dn` de `products` es una etiqueta nominal (ISO 6708 — adimensional).
  Las dimensiones físicas reales (bore, face-to-face, OD de brida) dependen del
  estándar aplicado: EN 558, ASME B16.10, AWWA C504, etc.
  Un producto puede cumplir varios estándares simultáneamente con dimensiones
  distintas (ej: butterfly wafer MTFT_5114 soporta ANSI 150 / EN-1092 / DIN 2576).

Slot 099.
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "099"
down_revision: str = "098"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


# ---------------------------------------------------------------------------
# Seed data — equivalencias DN↔NPS según ISO 6708 / ASME B36.10M
# OD de tubería según EN 10220 / ASME B36.10M (son idénticos en la mayoría)
# ---------------------------------------------------------------------------
DN_NPS_SEED = [
    # (dn, nps, nps_label, od_pipe_mm)
    ("15", "0.5", '½"', 21.3),
    ("20", "0.75", '¾"', 26.7),
    ("25", "1", '1"', 33.4),
    ("32", "1.25", '1¼"', 42.2),
    ("40", "1.5", '1½"', 48.3),
    ("50", "2", '2"', 60.3),
    ("65", "2.5", '2½"', 76.1),
    ("80", "3", '3"', 88.9),
    ("100", "4", '4"', 114.3),
    ("125", "5", '5"', 139.7),
    ("150", "6", '6"', 168.3),
    ("200", "8", '8"', 219.1),
    ("250", "10", '10"', 273.0),
    ("300", "12", '12"', 323.9),
    ("350", "14", '14"', 355.6),
    ("400", "16", '16"', 406.4),
    ("450", "18", '18"', 457.2),
    ("500", "20", '20"', 508.0),
    ("600", "24", '24"', 609.6),
    ("700", "28", '28"', 711.2),
    ("800", "32", '32"', 812.8),
    ("900", "36", '36"', 914.4),
    ("1000", "40", '40"', 1016.0),
]


def upgrade() -> None:
    # ------------------------------------------------------------------
    # 1. dn_nps_reference — tabla de referencia global (inmutable de norma)
    # ------------------------------------------------------------------
    op.create_table(
        "dn_nps_reference",
        sa.Column(
            "dn_nominal",
            sa.Text,
            primary_key=True,
            comment="Tamaño nominal métrico: '80', '100', '150' (sin prefijo DN)",
        ),
        sa.Column(
            "nps_nominal",
            sa.Text,
            nullable=False,
            comment="Tamaño nominal americano: '3', '4', '6' (sin comillas)",
        ),
        sa.Column(
            "nps_label",
            sa.Text,
            nullable=False,
            comment="Etiqueta legible NPS: '3\"', '4\"', '6\"'",
        ),
        sa.Column(
            "od_pipe_mm",
            sa.Numeric(8, 2),
            nullable=True,
            comment="OD exterior de tubería según EN 10220 / ASME B36.10M (mm)",
        ),
        sa.Column("notes", sa.Text, nullable=True, comment="Aclaraciones o excepciones de norma"),
    )
    op.create_index("uq_dn_nps_ref_dn", "dn_nps_reference", ["dn_nominal"], unique=True)

    # Seed con datos de norma
    op.bulk_insert(
        sa.table(
            "dn_nps_reference",
            sa.column("dn_nominal", sa.Text),
            sa.column("nps_nominal", sa.Text),
            sa.column("nps_label", sa.Text),
            sa.column("od_pipe_mm", sa.Numeric),
        ),
        [
            {"dn_nominal": r[0], "nps_nominal": r[1], "nps_label": r[2], "od_pipe_mm": r[3]}
            for r in DN_NPS_SEED
        ],
    )

    # ------------------------------------------------------------------
    # 2. product_bore_dimensions — dimensiones por SKU × estándar aplicable
    # ------------------------------------------------------------------
    op.create_table(
        "product_bore_dimensions",
        sa.Column("id", sa.UUID, primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column(
            "product_sku",
            sa.Text,
            sa.ForeignKey("products.sku", ondelete="CASCADE"),
            nullable=False,
            comment="SKU del producto",
        ),
        # Sistema de referencia
        sa.Column(
            "standard_system",
            sa.String(16),
            nullable=False,
            comment="Sistema: DIN | ASME | AWWA | ISO",
        ),
        sa.Column(
            "standard_code",
            sa.Text,
            nullable=False,
            comment="Código completo: 'EN 558 Serie 20', 'ASME B16.10 Class 150', 'AWWA C504'",
        ),
        sa.Column(
            "pressure_class",
            sa.String(20),
            nullable=True,
            comment="Clase de presión aplicable: 'PN6', 'PN10', 'PN16', 'Class 150', 'Class 300'",
        ),
        # Dimensiones reales (todas opcionales — sólo las que aplican al tipo de válvula)
        sa.Column(
            "bore_mm",
            sa.Numeric(8, 2),
            nullable=True,
            comment="Diámetro de paso (waterway bore) en mm — la dimensión que el spec llama dn_real",
        ),
        sa.Column(
            "face_to_face_mm",
            sa.Numeric(8, 2),
            nullable=True,
            comment="Distancia cara a cara (construcción) en mm",
        ),
        sa.Column(
            "end_to_end_mm",
            sa.Numeric(8, 2),
            nullable=True,
            comment="Distancia extremo a extremo (con bridas) en mm",
        ),
        sa.Column(
            "flange_od_mm",
            sa.Numeric(8, 2),
            nullable=True,
            comment="Diámetro exterior de brida en mm",
        ),
        sa.Column(
            "bolt_circle_mm",
            sa.Numeric(8, 2),
            nullable=True,
            comment="Diámetro del círculo de pernos en mm",
        ),
        sa.Column(
            "bolt_count", sa.Integer, nullable=True, comment="Número de pernos/tornillos de brida"
        ),
        sa.Column(
            "bolt_size",
            sa.String(16),
            nullable=True,
            comment="Tamaño de perno: 'M16', '5/8\"', etc.",
        ),
        # Metadatos
        sa.Column(
            "is_primary",
            sa.Boolean,
            nullable=False,
            server_default=sa.text("false"),
            comment="True si este estándar es el de referencia principal del producto",
        ),
        sa.Column("notes", sa.Text, nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
    )

    op.create_index(
        "uq_product_bore_dim_sku_std_pclass",
        "product_bore_dimensions",
        ["product_sku", "standard_code", "pressure_class"],
        unique=True,
    )
    op.create_index("idx_product_bore_dim_sku", "product_bore_dimensions", ["product_sku"])
    op.create_index("idx_product_bore_dim_system", "product_bore_dimensions", ["standard_system"])

    # CHECK: sistema de referencia válido
    op.create_check_constraint(
        "ck_bore_dim_system",
        "product_bore_dimensions",
        "standard_system IN ('DIN', 'ASME', 'AWWA', 'ISO', 'JIS', 'GOST')",
    )

    # ------------------------------------------------------------------
    # 3. products — columna bore_mm escalar para queries simples
    #    (el valor del estándar principal — desnormalización útil)
    # ------------------------------------------------------------------
    op.add_column(
        "products",
        sa.Column(
            "bore_mm",
            sa.Numeric(8, 2),
            nullable=True,
            comment="Bore real del producto (estándar principal). Ej: 87.0 para DN80 wafer. "
            "Detalle completo por norma en product_bore_dimensions.",
        ),
    )
    op.add_column(
        "products",
        sa.Column(
            "dimensional_standard",
            sa.String(16),
            nullable=True,
            comment="Sistema dimensional principal: DIN | ASME | AWWA | ISO",
        ),
    )


def downgrade() -> None:
    op.drop_column("products", "dimensional_standard")
    op.drop_column("products", "bore_mm")
    op.drop_table("product_bore_dimensions")
    op.drop_table("dn_nps_reference")
