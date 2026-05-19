# Product Model Hierarchy & Enrichment Foundation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Introduce `product_models` as the missing hierarchy level between `series` and `products` (SKUs), add rich technical tables (JSONB dimensions, P/T curves by gasket, Kv/flow data, model-level BOM with material grades, issued certificates with lifecycle), and wire the existing ficha enrichment pipeline to populate the new model-level entities — without breaking any existing functionality.

**Architecture:** Three phases: F1 adds all new DB tables and columns via Alembic migrations and ORM models; F2 updates the ficha enrichment backend (schemas, extractor tool schema, series resolver, applier) to write to the new entities; F3 updates the frontend `/fichas` wizard to display the richer model-level data. Each phase is independently deployable and backward-compatible because all new FKs are nullable during migration.

**Tech Stack:** FastAPI + SQLAlchemy 2.0 async + Alembic + PostgreSQL JSONB · Next.js 15 + React 19 + TypeScript · Anthropic SDK (tool_use)

---

## Scope Note

This plan is split into 3 independent sub-phases that can each be shipped and tested before starting the next:

- **F1 (Tasks 1–6):** DB schema + ORM models only. No application logic changes.
- **F2 (Tasks 7–11):** Backend services + schemas updated to write to new tables.
- **F3 (Tasks 12–14):** Frontend wizard updated to display new hierarchy.

---

## File Map

### New files to create
- `mt-pricing-backend/app/db/models/product_models.py` — ORM: `ProductModel`, `ModelDimensionRow`, `ModelFlowData`, `ModelTechTable`
- `mt-pricing-backend/app/db/models/certificates.py` — ORM: `Certificate`, `CertificateScope`
- `mt-pricing-backend/app/db/models/brand_certifications.py` — ORM: `BrandCertification`
- `mt-pricing-backend/alembic/versions/20260529_126_product_models.py` — migration F1a
- `mt-pricing-backend/alembic/versions/20260529_127_certificates.py` — migration F1b
- `mt-pricing-backend/alembic/versions/20260529_128_brand_certifications.py` — migration F1c
- `mt-pricing-backend/alembic/versions/20260529_129_documents_series_fields.py` — migration F1d
- `mt-pricing-backend/alembic/versions/20260529_130_product_materials_grade.py` — migration F1e
- `mt-pricing-backend/alembic/versions/20260529_131_products_model_fk.py` — migration F1f
- `mt-pricing-backend/app/services/ficha_enrichment/model_writer.py` — service: write extracted data to `product_models`
- `mt-pricing-backend/tests/unit/services/ficha_enrichment/test_model_writer.py`
- `mt-pricing-backend/tests/unit/db/models/test_product_models.py`

### Files to modify
- `mt-pricing-backend/app/db/models/__init__.py` — export new ORM classes
- `mt-pricing-backend/app/db/models/product.py` — add `model_id` FK + relationship
- `mt-pricing-backend/app/db/models/components.py` — add `material_grade`, `material_standard`, `surface_treatment` to `ProductMaterial`
- `mt-pricing-backend/app/db/models/documents.py` — add `doc_number`, `series_id` FK, `signatory_name`, `signatory_role`; extend CHECK constraint
- `mt-pricing-backend/app/db/models/vocabularies.py` — add `thread_standard`, `revision`, `revision_date` to `Series`; add `BrandCertification` relationship to `Brand`
- `mt-pricing-backend/app/schemas/ficha_enrich.py` — add `ExtractedMaterialGrade`, `ExtractedCertificate`, `ExtractedDimensionRowV2` (with `dn_secondary_label`), `ExtractedFlowData`; extend `FichaExtractionResult`
- `mt-pricing-backend/app/services/ficha_enrichment/extractor.py` — extend `_TOOL_SCHEMA` with new fields
- `mt-pricing-backend/app/services/ficha_enrichment/series_resolver.py` — call `model_writer` after resolving SKUs
- `mt-pricing-backend/app/services/ficha_enrichment/applier.py` — write `model_components`, `model_dimension_rows`, `certificates` during apply
- `mt-pricing-frontend/lib/api/endpoints/ficha-enrich.ts` — add new TypeScript types
- `mt-pricing-frontend/app/(app)/fichas/_client.tsx` — display model hierarchy and certificates

---

## F1: Database Schema

---

### Task 1: ORM model — `product_models` + related tables

**Files:**
- Create: `mt-pricing-backend/app/db/models/product_models.py`
- Create: `mt-pricing-backend/tests/unit/db/models/test_product_models.py`

#### Context

`product_models` sits between `series` (commercial line, e.g., "Gold Series PN30") and `products` (individual SKUs, e.g., 4295015). A model code (e.g., 4295) represents one physical valve shape; 4295 = red body (base), 42952 = blue body (color variant). `variant_of_id` captures this at the model level rather than just SKU-to-SKU.

`model_dimension_rows` stores per-DN dimensions as JSONB because the dimension schema varies by product family (ball valves: L/H/M; strainers: L/H/ØD/ØK/b/c/BOLTS; fittings: A/C/K/D). `dn_secondary_mm` handles reducing fittings (two DN sizes per row: inlet × outlet).

`model_flow_data` stores Kv/Cv flow coefficients and filter mesh size per DN — specific to strainers and filters.

`model_tech_tables` is a per-model version of the existing `product_tech_tables` (which is per-SKU). Stores P/T curves (optionally segmented by gasket material), materials matrix, dimension tables.

- [ ] **Step 1: Write the failing test**

```python
# mt-pricing-backend/tests/unit/db/models/test_product_models.py
"""Unit tests for ProductModel ORM — pure Python (no DB)."""
import uuid
from app.db.models.product_models import ProductModel, ModelDimensionRow, ModelFlowData, ModelTechTable


def test_product_model_instantiation():
    m = ProductModel(
        id=uuid.uuid4(),
        series_id=uuid.uuid4(),
        code="4295",
        color_label="red",
    )
    assert m.code == "4295"
    assert m.color_label == "red"
    assert m.variant_of_id is None


def test_model_dimension_row_jsonb_default():
    row = ModelDimensionRow(
        model_id=uuid.uuid4(),
        dn_mm=15,
        dimensions={},
    )
    assert row.dimensions == {}
    assert row.dn_secondary_mm is None


def test_model_flow_data_defaults():
    fd = ModelFlowData(
        model_id=uuid.uuid4(),
        dn_mm=25,
    )
    assert fd.kv is None
    assert fd.mesh_mm is None


def test_model_tech_table_kind():
    tt = ModelTechTable(
        model_id=uuid.uuid4(),
        kind="pt_curve",
        data={},
    )
    assert tt.kind == "pt_curve"
    assert tt.gasket_material is None
```

- [ ] **Step 2: Run test to verify it fails**

```
cd mt-pricing-backend
pytest tests/unit/db/models/test_product_models.py -v
```
Expected: ImportError — `app.db.models.product_models` does not exist yet.

- [ ] **Step 3: Create the ORM file**

```python
# mt-pricing-backend/app/db/models/product_models.py
"""ORM — product_models hierarchy: Series → ProductModel → Product (SKU).

product_models: numeric code (4295, 4097 …) + color variant pairing.
model_dimension_rows: per-DN dimensions as JSONB (schema varies by family).
model_flow_data: Kv/Cv + mesh per DN (strainers/filters only).
model_tech_tables: per-model P/T curves, materials matrix, etc.
"""
from __future__ import annotations

from datetime import datetime
from typing import Any
from uuid import UUID

from sqlalchemy import (
    DateTime,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    String,
    Text,
    UniqueConstraint,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base
from app.db.mixins import UuidPkMixin
from app.db.types import UUID_PG


class ProductModel(UuidPkMixin, Base):
    """Nivel modelo: code numérico que agrupa SKUs de la misma forma física.

    Ejemplo: code='4295', variant_of_id→ProductModel(code='4097') cuando
    el 4295 es la variante roja del 4097 azul.
    """
    __tablename__ = "product_models"

    series_id: Mapped[UUID | None] = mapped_column(
        UUID_PG, ForeignKey("series.id", ondelete="RESTRICT"), nullable=True
    )
    code: Mapped[str] = mapped_column(Text, nullable=False, unique=True)
    color_label: Mapped[str | None] = mapped_column(String(32), nullable=True)
    connection_type: Mapped[str | None] = mapped_column(
        String(32), nullable=True,
        comment="thread_bsp | thread_bspt | thread_npt | flange_en | flange_ansi"
    )
    thread_standard: Mapped[str | None] = mapped_column(String(32), nullable=True)
    active: Mapped[bool] = mapped_column(
        Boolean, nullable=False, server_default=text("true")
    )
    variant_of_id: Mapped[UUID | None] = mapped_column(
        UUID_PG,
        ForeignKey("product_models.id", ondelete="SET NULL"),
        nullable=True,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=text("now()")
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=text("now()")
    )

    series: Mapped["Series"] = relationship(  # type: ignore[name-defined]
        "Series", foreign_keys=[series_id]
    )
    variant_of: Mapped["ProductModel | None"] = relationship(
        "ProductModel", remote_side="ProductModel.id", foreign_keys=[variant_of_id]
    )
    dimension_rows: Mapped[list["ModelDimensionRow"]] = relationship(
        back_populates="model", cascade="all, delete-orphan"
    )
    flow_data: Mapped[list["ModelFlowData"]] = relationship(
        back_populates="model", cascade="all, delete-orphan"
    )
    tech_tables: Mapped[list["ModelTechTable"]] = relationship(
        back_populates="model", cascade="all, delete-orphan"
    )

    __table_args__ = (
        Index("idx_product_models_series", "series_id"),
        Index("idx_product_models_variant_of", "variant_of_id"),
    )


class ModelDimensionRow(UuidPkMixin, Base):
    """Dimensiones por DN para un model — JSONB para soportar cualquier schema de familia.

    Schema ball valve: {"L_mm": 57, "H_mm": 72, "M_mm": 64}
    Schema fitting:    {"A_mm": 24, "C_mm": 15, "K_mm": 28, "D_mm": 12}
    Schema strainer:   {"L_mm": 130, "H_mm": 145, "ØD_mm": 95, "ØK_mm": 65, "b_mm": 14, "bolts": "4xM16"}
    """
    __tablename__ = "model_dimension_rows"

    model_id: Mapped[UUID] = mapped_column(
        UUID_PG, ForeignKey("product_models.id", ondelete="CASCADE"), nullable=False
    )
    dn_mm: Mapped[int] = mapped_column(Integer, nullable=False)
    dn_secondary_mm: Mapped[int | None] = mapped_column(
        Integer, nullable=True,
        comment="Solo para reductores (ej. reducción 1/2 x 3/8): DN salida"
    )
    dimensions: Mapped[dict[str, Any]] = mapped_column(
        JSONB, nullable=False, server_default=text("'{}'::jsonb")
    )
    source: Mapped[str] = mapped_column(
        Text, nullable=False, server_default=text("'manual'")
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=text("now()")
    )

    model: Mapped[ProductModel] = relationship(back_populates="dimension_rows")

    __table_args__ = (
        UniqueConstraint("model_id", "dn_mm", "dn_secondary_mm", name="uq_model_dim_rows"),
        Index("idx_model_dim_rows_model", "model_id"),
        Index("idx_model_dim_rows_dn", "dn_mm"),
    )


class ModelFlowData(UuidPkMixin, Base):
    """Coeficientes de flujo Kv/Cv + malla por DN (filtros/coladores)."""
    __tablename__ = "model_flow_data"

    model_id: Mapped[UUID] = mapped_column(
        UUID_PG, ForeignKey("product_models.id", ondelete="CASCADE"), nullable=False
    )
    dn_mm: Mapped[int] = mapped_column(Integer, nullable=False)
    kv: Mapped[float | None] = mapped_column(Numeric(10, 3), nullable=True)
    cv: Mapped[float | None] = mapped_column(Numeric(10, 3), nullable=True)
    mesh_mm: Mapped[float | None] = mapped_column(
        Numeric(6, 2), nullable=True,
        comment="Tamaño de malla en mm (ej. 1.8, 1.0)"
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=text("now()")
    )

    model: Mapped[ProductModel] = relationship(back_populates="flow_data")

    __table_args__ = (
        UniqueConstraint("model_id", "dn_mm", "mesh_mm", name="uq_model_flow"),
        Index("idx_model_flow_model", "model_id"),
    )


class ModelTechTable(UuidPkMixin, Base):
    """Tabla técnica a nivel modelo: curva P/T (por material junta), matriz materiales, etc.

    kind values: 'pt_curve' | 'materials_matrix' | 'dimensions_by_dn' | 'kv_table'
    Para curvas P/T con múltiples materiales de junta: una fila por material.
    data schema para pt_curve: [{"temperature_c": 20, "pressure_max_bar": 16}, ...]
    """
    __tablename__ = "model_tech_tables"

    model_id: Mapped[UUID] = mapped_column(
        UUID_PG, ForeignKey("product_models.id", ondelete="CASCADE"), nullable=False
    )
    kind: Mapped[str] = mapped_column(Text, nullable=False)
    gasket_material: Mapped[str | None] = mapped_column(
        Text, nullable=True,
        comment="Solo para kind=pt_curve con múltiples juntas: EPDM | PTFE | GRAFITO"
    )
    schema_version: Mapped[str] = mapped_column(
        Text, nullable=False, server_default=text("'v1'")
    )
    source: Mapped[str] = mapped_column(
        Text, nullable=False, server_default=text("'manual'")
    )
    data: Mapped[dict[str, Any]] = mapped_column(
        JSONB, nullable=False, server_default=text("'{}'::jsonb")
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=text("now()")
    )

    model: Mapped[ProductModel] = relationship(back_populates="tech_tables")

    __table_args__ = (
        UniqueConstraint("model_id", "kind", "gasket_material", name="uq_model_tech_table"),
        Index("idx_model_tech_tables_model", "model_id"),
        Index("idx_model_tech_tables_kind", "kind"),
    )
```

Note: `Boolean` must be imported from `sqlalchemy` — add it to the import block at the top alongside the other sqlalchemy imports.

- [ ] **Step 4: Run the test again**

```
pytest tests/unit/db/models/test_product_models.py -v
```
Expected: PASS (4 tests).

- [ ] **Step 5: Register in `__init__.py`**

Open `mt-pricing-backend/app/db/models/__init__.py`. At the end of the existing imports block add:

```python
from app.db.models.product_models import (  # noqa: F401
    ProductModel,
    ModelDimensionRow,
    ModelFlowData,
    ModelTechTable,
)
```

- [ ] **Step 6: Commit**

```bash
git add mt-pricing-backend/app/db/models/product_models.py \
        mt-pricing-backend/app/db/models/__init__.py \
        mt-pricing-backend/tests/unit/db/models/test_product_models.py
git commit -m "feat(model): ProductModel ORM — hierarchy level between Series and SKU"
```

---

### Task 2: ORM model — `certificates` + `certificate_scopes`

**Files:**
- Create: `mt-pricing-backend/app/db/models/certificates.py`
- Modify: `mt-pricing-backend/app/db/models/__init__.py`

#### Context

`certificates` represents an *issued* certificate (actual document with number, issuer, dates, status). This is distinct from `certifications` (catalog of certification concepts). A `Certificate` belongs to a `ProductModel` (model-level, e.g., ACS for 4097 series). `certificate_scopes` links a certificate to individual SKUs or DN ranges it covers. Status lifecycle: `valid` → `expiring_soon` (≤ 90 days) → `critical` (≤ 30 days) → `expired`. `renewing` is a special status set manually.

- [ ] **Step 1: Write the failing test**

```python
# mt-pricing-backend/tests/unit/db/models/test_certificates.py
"""Unit tests for Certificate ORM — pure Python (no DB)."""
import uuid
from datetime import date
from app.db.models.certificates import Certificate, CertificateScope


def test_certificate_instantiation():
    cert = Certificate(
        id=uuid.uuid4(),
        cert_number="23 ACC LY 482",
        certification_id=uuid.uuid4(),
        model_id=uuid.uuid4(),
        issuer="Carso",
        issued_at=date(2023, 7, 11),
        expires_at=date(2028, 7, 11),
        status="valid",
    )
    assert cert.cert_number == "23 ACC LY 482"
    assert cert.status == "valid"


def test_certificate_scope_instantiation():
    scope = CertificateScope(
        certificate_id=uuid.uuid4(),
        sku="4097015",
    )
    assert scope.sku == "4097015"
    assert scope.dn_min is None
```

- [ ] **Step 2: Run test to verify it fails**

```
pytest tests/unit/db/models/test_certificates.py -v
```
Expected: ImportError.

- [ ] **Step 3: Create the ORM file**

```python
# mt-pricing-backend/app/db/models/certificates.py
"""ORM — certificates (documentos de certificación emitidos con lifecycle).

Diferencia clave con 'certifications':
  certifications = catálogo de conceptos curados por admin (ACS, WRAS, PZH…)
  certificates   = documento real emitido (nº 23 ACC LY 482, exp 11/07/2028)

Un Certificate tiene owner model_id (nivel modelo/serie). Los SKUs/DN que
cubre se detallan en certificate_scopes.
"""
from __future__ import annotations

from datetime import date, datetime
from uuid import UUID

from sqlalchemy import (
    CheckConstraint,
    Date,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    Text,
    UniqueConstraint,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base
from app.db.mixins import UuidPkMixin
from app.db.types import UUID_PG

_CERT_STATUSES = ("valid", "expiring_soon", "critical", "expired", "renewing")


class Certificate(UuidPkMixin, Base):
    """Certificado emitido con número, fechas, estado lifecycle."""
    __tablename__ = "certificates"

    # Owner — a nivel modelo (series)
    model_id: Mapped[UUID | None] = mapped_column(
        UUID_PG, ForeignKey("product_models.id", ondelete="SET NULL"), nullable=True
    )
    # Concepto (link al catálogo)
    certification_id: Mapped[UUID | None] = mapped_column(
        UUID_PG, ForeignKey("certifications.id", ondelete="RESTRICT"), nullable=True
    )
    cert_number: Mapped[str] = mapped_column(Text, nullable=False)
    issuer: Mapped[str | None] = mapped_column(Text, nullable=True)
    issued_at: Mapped[date | None] = mapped_column(Date, nullable=True)
    expires_at: Mapped[date | None] = mapped_column(Date, nullable=True)
    status: Mapped[str] = mapped_column(
        Text, nullable=False, server_default=text("'valid'")
    )
    signatory_name: Mapped[str | None] = mapped_column(Text, nullable=True)
    signatory_role: Mapped[str | None] = mapped_column(Text, nullable=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=text("now()")
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=text("now()")
    )

    scopes: Mapped[list["CertificateScope"]] = relationship(
        back_populates="certificate", cascade="all, delete-orphan"
    )

    __table_args__ = (
        CheckConstraint(
            "status IN ('valid','expiring_soon','critical','expired','renewing')",
            name="ck_certificate_status",
        ),
        Index("idx_certificates_model", "model_id"),
        Index("idx_certificates_certification", "certification_id"),
        Index("idx_certificates_status", "status"),
        Index("idx_certificates_expires", "expires_at"),
    )


class CertificateScope(UuidPkMixin, Base):
    """SKU o rango de DN cubierto por un certificado."""
    __tablename__ = "certificate_scopes"

    certificate_id: Mapped[UUID] = mapped_column(
        UUID_PG, ForeignKey("certificates.id", ondelete="CASCADE"), nullable=False
    )
    # Optional: SKU específico o rango de DN
    sku: Mapped[str | None] = mapped_column(
        Text, ForeignKey("products.sku", ondelete="CASCADE"), nullable=True
    )
    dn_min: Mapped[int | None] = mapped_column(Integer, nullable=True)
    dn_max: Mapped[int | None] = mapped_column(Integer, nullable=True)

    certificate: Mapped[Certificate] = relationship(back_populates="scopes")

    __table_args__ = (
        CheckConstraint(
            "dn_min IS NULL OR dn_max IS NULL OR dn_max >= dn_min",
            name="ck_cert_scope_dn",
        ),
        Index("idx_cert_scopes_cert", "certificate_id"),
        Index("idx_cert_scopes_sku", "sku"),
    )
```

- [ ] **Step 4: Run the test again**

```
pytest tests/unit/db/models/test_certificates.py -v
```
Expected: PASS (2 tests).

- [ ] **Step 5: Add to `__init__.py`**

```python
from app.db.models.certificates import Certificate, CertificateScope  # noqa: F401
```

- [ ] **Step 6: Commit**

```bash
git add mt-pricing-backend/app/db/models/certificates.py \
        mt-pricing-backend/app/db/models/__init__.py \
        mt-pricing-backend/tests/unit/db/models/test_certificates.py
git commit -m "feat(model): Certificate + CertificateScope ORM — issued cert lifecycle"
```

---

### Task 3: ORM extensions — `Series`, `documents`, `ProductMaterial`, `Brand`

**Files:**
- Modify: `mt-pricing-backend/app/db/models/vocabularies.py`
- Modify: `mt-pricing-backend/app/db/models/documents.py`
- Modify: `mt-pricing-backend/app/db/models/components.py`

#### Context

Four small extensions to existing ORM models, all backward-compatible (nullable columns):

1. **`Series`**: add `thread_standard` (ISO 228-1 vs ISO 7/1), `revision` (doc revision code), `revision_date` (date of last rev).
2. **`documents`**: add `doc_number` (e.g., "202604-GOLDSERIES"), `series_id` FK → `series.id`, `signatory_name`, `signatory_role`. Also extend the CHECK constraint to include `"declaracion_conformidad"` type.
3. **`ProductMaterial`**: add `material_grade` (e.g., "EN-GJL-250"), `material_standard` (e.g., "ASTM A307"), `surface_treatment` (e.g., "Epoxy").
4. **`Brand`**: add relationship `brand_certifications` (link to `brand_certifications` table created in migration, ORM-only for now).

- [ ] **Step 1: Modify `Series` in `vocabularies.py`**

Find the `Series` class (around line 425). After the `sort_order` column, add:

```python
    thread_standard: Mapped[str | None] = mapped_column(
        String(32), nullable=True,
        comment="ISO 228-1 (BSP) | ISO 7/1 (BSPT) | ASME B1.20.1 (NPT)"
    )
    revision: Mapped[str | None] = mapped_column(Text, nullable=True)
    revision_date: Mapped[date | None] = mapped_column(
        Date, nullable=True
    )
```

Also add `Date` and `date` to the sqlalchemy/datetime imports at the top of the file if not already present.

- [ ] **Step 2: Modify `Document` in `documents.py`**

In the `Document` class body, after `issued_at`, add:

```python
    doc_number: Mapped[str | None] = mapped_column(Text, nullable=True)
    series_id: Mapped[UUID | None] = mapped_column(
        UUID_PG, ForeignKey("series.id", ondelete="SET NULL"), nullable=True
    )
    signatory_name: Mapped[str | None] = mapped_column(Text, nullable=True)
    signatory_role: Mapped[str | None] = mapped_column(Text, nullable=True)
```

Update `DOCUMENT_TYPES` tuple to include `"declaracion_conformidad"`:

```python
DOCUMENT_TYPES = (
    "ficha_tecnica",
    "manual",
    "declaracion_ce",
    "declaracion_conformidad",
    "certificado",
    "catalogo",
)
```

Add to `__table_args__`:

```python
        Index("ix_doc_series", "series_id"),
```

Import `UUID_PG` from `app.db.types` if not already (check existing imports in the file).

- [ ] **Step 3: Modify `ProductMaterial` in `components.py`**

After the `observations` column, add:

```python
    material_grade: Mapped[str | None] = mapped_column(
        Text, nullable=True,
        comment="ej. EN-GJL-250, AISI 304, CW617N"
    )
    material_standard: Mapped[str | None] = mapped_column(
        Text, nullable=True,
        comment="ej. ASTM A307, UNE-EN-12165"
    )
    surface_treatment: Mapped[str | None] = mapped_column(
        Text, nullable=True,
        comment="ej. Epoxy, Nickel, Zinc, None"
    )
```

- [ ] **Step 4: Run existing tests to confirm no regressions**

```
cd mt-pricing-backend
pytest tests/unit/ -v --tb=short -q 2>&1 | head -50
```
Expected: same pass/fail count as before; new nullable columns don't break existing tests.

- [ ] **Step 5: Commit**

```bash
git add mt-pricing-backend/app/db/models/vocabularies.py \
        mt-pricing-backend/app/db/models/documents.py \
        mt-pricing-backend/app/db/models/components.py
git commit -m "feat(model): extend Series/Document/ProductMaterial with new nullable fields"
```

---

### Task 4: Add `model_id` FK to `Product`

**Files:**
- Modify: `mt-pricing-backend/app/db/models/product.py`

#### Context

`products.model_id` links each SKU to its `product_models` row. Nullable during migration — will be backfilled for existing SKUs by the ficha enrichment applier. This is a read/write FK: many SKUs can share the same model (e.g., 4295015, 4295020, 4295025 all → model 4295).

- [ ] **Step 1: Write the failing test**

```python
# mt-pricing-backend/tests/unit/db/models/test_product_model_fk.py
"""Test that Product has model_id attribute (pure Python, no DB)."""
from app.db.models.product import Product


def test_product_has_model_id():
    p = Product(sku="4295015", family="valvulas", brand_id=None, family_id=None)
    assert hasattr(p, "model_id")
    assert p.model_id is None  # nullable default
```

- [ ] **Step 2: Run to confirm it fails**

```
pytest tests/unit/db/models/test_product_model_fk.py -v
```
Expected: AttributeError — `Product` has no attribute `model_id`.

- [ ] **Step 3: Add the FK column to `Product`**

In `mt-pricing-backend/app/db/models/product.py`, after the `series_id` column (around line 179), add:

```python
    model_id: Mapped[UUID | None] = mapped_column(
        UUID_PG,
        ForeignKey("product_models.id", ondelete="SET NULL"),
        nullable=True,
    )
```

And add the relationship after the existing `materials` relationship:

```python
    model: Mapped["ProductModel | None"] = relationship(  # type: ignore[name-defined]
        "ProductModel",
        foreign_keys="[Product.model_id]",
        lazy="select",
    )
```

Add `"ProductModel"` to the TYPE_CHECKING imports at the top if needed (follow existing pattern).

- [ ] **Step 4: Run the test again**

```
pytest tests/unit/db/models/test_product_model_fk.py -v
```
Expected: PASS.

- [ ] **Step 5: Run full unit test suite**

```
pytest tests/unit/ -q --tb=short 2>&1 | tail -20
```
Expected: no regressions.

- [ ] **Step 6: Commit**

```bash
git add mt-pricing-backend/app/db/models/product.py \
        mt-pricing-backend/tests/unit/db/models/test_product_model_fk.py
git commit -m "feat(model): Product.model_id FK → product_models (nullable)"
```

---

### Task 5: Alembic migrations F1a–F1f

**Files:**
- Create: `mt-pricing-backend/alembic/versions/20260529_126_product_models.py`
- Create: `mt-pricing-backend/alembic/versions/20260529_127_certificates.py`
- Create: `mt-pricing-backend/alembic/versions/20260529_128_documents_series_fields.py`
- Create: `mt-pricing-backend/alembic/versions/20260529_129_product_materials_grade.py`
- Create: `mt-pricing-backend/alembic/versions/20260529_130_products_model_fk.py`

#### Context

Migration naming convention from project: `YYYYMMDD_NNN_description.py`. The last migration is `20260528_125`. Use sequential numbers 126–130. Each migration must have a `down_revision` pointing to the previous one (chain: 125 → 126 → 127 → 128 → 129 → 130).

All new FKs use `DEFERRABLE INITIALLY DEFERRED` pattern — not enforced here since it's not the project norm; just use standard `RESTRICT` / `SET NULL` as seen in existing migrations.

**Important:** Run `./infra/scripts/migrate.sh` after creating all files, then verify with `docker restart mt-backend`.

- [ ] **Step 1: Create migration 126 — `product_models`**

```python
# mt-pricing-backend/alembic/versions/20260529_126_product_models.py
"""product_models + model_dimension_rows + model_flow_data + model_tech_tables"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "20260529_126"
down_revision = "20260528_125"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "product_models",
        sa.Column("id", sa.UUID(), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("series_id", sa.UUID(), nullable=True),
        sa.Column("code", sa.Text(), nullable=False),
        sa.Column("color_label", sa.String(32), nullable=True),
        sa.Column("connection_type", sa.String(32), nullable=True),
        sa.Column("thread_standard", sa.String(32), nullable=True),
        sa.Column("active", sa.Boolean(), server_default=sa.text("true"), nullable=False),
        sa.Column("variant_of_id", sa.UUID(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["series_id"], ["series.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["variant_of_id"], ["product_models.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("code"),
    )
    op.create_index("idx_product_models_series", "product_models", ["series_id"])
    op.create_index("idx_product_models_variant_of", "product_models", ["variant_of_id"])

    op.create_table(
        "model_dimension_rows",
        sa.Column("id", sa.UUID(), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("model_id", sa.UUID(), nullable=False),
        sa.Column("dn_mm", sa.Integer(), nullable=False),
        sa.Column("dn_secondary_mm", sa.Integer(), nullable=True),
        sa.Column("dimensions", sa.dialects.postgresql.JSONB(), server_default=sa.text("'{}'::jsonb"), nullable=False),
        sa.Column("source", sa.Text(), server_default=sa.text("'manual'"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["model_id"], ["product_models.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("model_id", "dn_mm", "dn_secondary_mm", name="uq_model_dim_rows"),
    )
    op.create_index("idx_model_dim_rows_model", "model_dimension_rows", ["model_id"])
    op.create_index("idx_model_dim_rows_dn", "model_dimension_rows", ["dn_mm"])

    op.create_table(
        "model_flow_data",
        sa.Column("id", sa.UUID(), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("model_id", sa.UUID(), nullable=False),
        sa.Column("dn_mm", sa.Integer(), nullable=False),
        sa.Column("kv", sa.Numeric(10, 3), nullable=True),
        sa.Column("cv", sa.Numeric(10, 3), nullable=True),
        sa.Column("mesh_mm", sa.Numeric(6, 2), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["model_id"], ["product_models.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("model_id", "dn_mm", "mesh_mm", name="uq_model_flow"),
    )
    op.create_index("idx_model_flow_model", "model_flow_data", ["model_id"])

    op.create_table(
        "model_tech_tables",
        sa.Column("id", sa.UUID(), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("model_id", sa.UUID(), nullable=False),
        sa.Column("kind", sa.Text(), nullable=False),
        sa.Column("gasket_material", sa.Text(), nullable=True),
        sa.Column("schema_version", sa.Text(), server_default=sa.text("'v1'"), nullable=False),
        sa.Column("source", sa.Text(), server_default=sa.text("'manual'"), nullable=False),
        sa.Column("data", sa.dialects.postgresql.JSONB(), server_default=sa.text("'{}'::jsonb"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["model_id"], ["product_models.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("model_id", "kind", "gasket_material", name="uq_model_tech_table"),
    )
    op.create_index("idx_model_tech_tables_model", "model_tech_tables", ["model_id"])
    op.create_index("idx_model_tech_tables_kind", "model_tech_tables", ["kind"])


def downgrade() -> None:
    op.drop_table("model_tech_tables")
    op.drop_table("model_flow_data")
    op.drop_table("model_dimension_rows")
    op.drop_table("product_models")
```

- [ ] **Step 2: Create migration 127 — `certificates`**

```python
# mt-pricing-backend/alembic/versions/20260529_127_certificates.py
"""certificates + certificate_scopes"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "20260529_127"
down_revision = "20260529_126"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "certificates",
        sa.Column("id", sa.UUID(), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("model_id", sa.UUID(), nullable=True),
        sa.Column("certification_id", sa.UUID(), nullable=True),
        sa.Column("cert_number", sa.Text(), nullable=False),
        sa.Column("issuer", sa.Text(), nullable=True),
        sa.Column("issued_at", sa.Date(), nullable=True),
        sa.Column("expires_at", sa.Date(), nullable=True),
        sa.Column("status", sa.Text(), server_default=sa.text("'valid'"), nullable=False),
        sa.Column("signatory_name", sa.Text(), nullable=True),
        sa.Column("signatory_role", sa.Text(), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.CheckConstraint(
            "status IN ('valid','expiring_soon','critical','expired','renewing')",
            name="ck_certificate_status",
        ),
        sa.ForeignKeyConstraint(["model_id"], ["product_models.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["certification_id"], ["certifications.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("idx_certificates_model", "certificates", ["model_id"])
    op.create_index("idx_certificates_status", "certificates", ["status"])
    op.create_index("idx_certificates_expires", "certificates", ["expires_at"])

    op.create_table(
        "certificate_scopes",
        sa.Column("id", sa.UUID(), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("certificate_id", sa.UUID(), nullable=False),
        sa.Column("sku", sa.Text(), nullable=True),
        sa.Column("dn_min", sa.Integer(), nullable=True),
        sa.Column("dn_max", sa.Integer(), nullable=True),
        sa.CheckConstraint(
            "dn_min IS NULL OR dn_max IS NULL OR dn_max >= dn_min",
            name="ck_cert_scope_dn",
        ),
        sa.ForeignKeyConstraint(["certificate_id"], ["certificates.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["sku"], ["products.sku"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("idx_cert_scopes_cert", "certificate_scopes", ["certificate_id"])


def downgrade() -> None:
    op.drop_table("certificate_scopes")
    op.drop_table("certificates")
```

- [ ] **Step 3: Create migration 128 — documents + series extensions**

```python
# mt-pricing-backend/alembic/versions/20260529_128_documents_series_fields.py
"""Extend documents (doc_number, series_id, signatory) + series (thread_standard, revision)"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "20260529_128"
down_revision = "20260529_127"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # --- documents ---
    op.add_column("documents", sa.Column("doc_number", sa.Text(), nullable=True))
    op.add_column("documents", sa.Column("series_id", sa.UUID(), nullable=True))
    op.add_column("documents", sa.Column("signatory_name", sa.Text(), nullable=True))
    op.add_column("documents", sa.Column("signatory_role", sa.Text(), nullable=True))
    op.create_foreign_key("fk_documents_series", "documents", "series", ["series_id"], ["id"], ondelete="SET NULL")
    op.create_index("ix_doc_series", "documents", ["series_id"])

    # Drop old CHECK and recreate with declaracion_conformidad added
    op.drop_constraint("ck_documents_type", "documents", type_="check")
    op.create_check_constraint(
        "ck_documents_type",
        "documents",
        "type IN ('ficha_tecnica','manual','declaracion_ce','declaracion_conformidad','certificado','catalogo')",
    )

    # --- series ---
    op.add_column("series", sa.Column("thread_standard", sa.String(32), nullable=True))
    op.add_column("series", sa.Column("revision", sa.Text(), nullable=True))
    op.add_column("series", sa.Column("revision_date", sa.Date(), nullable=True))


def downgrade() -> None:
    op.drop_column("series", "revision_date")
    op.drop_column("series", "revision")
    op.drop_column("series", "thread_standard")

    op.drop_constraint("ck_documents_type", "documents", type_="check")
    op.create_check_constraint(
        "ck_documents_type",
        "documents",
        "type IN ('ficha_tecnica','manual','declaracion_ce','certificado','catalogo')",
    )
    op.drop_index("ix_doc_series", "documents")
    op.drop_constraint("fk_documents_series", "documents", type_="foreignkey")
    op.drop_column("documents", "signatory_role")
    op.drop_column("documents", "signatory_name")
    op.drop_column("documents", "series_id")
    op.drop_column("documents", "doc_number")
```

- [ ] **Step 4: Create migration 129 — product_materials grade fields**

```python
# mt-pricing-backend/alembic/versions/20260529_129_product_materials_grade.py
"""Add material_grade, material_standard, surface_treatment to product_materials"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "20260529_129"
down_revision = "20260529_128"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("product_materials", sa.Column("material_grade", sa.Text(), nullable=True))
    op.add_column("product_materials", sa.Column("material_standard", sa.Text(), nullable=True))
    op.add_column("product_materials", sa.Column("surface_treatment", sa.Text(), nullable=True))


def downgrade() -> None:
    op.drop_column("product_materials", "surface_treatment")
    op.drop_column("product_materials", "material_standard")
    op.drop_column("product_materials", "material_grade")
```

- [ ] **Step 5: Create migration 130 — products.model_id FK**

```python
# mt-pricing-backend/alembic/versions/20260529_130_products_model_fk.py
"""Add products.model_id FK → product_models"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "20260529_130"
down_revision = "20260529_129"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("products", sa.Column("model_id", sa.UUID(), nullable=True))
    op.create_foreign_key(
        "fk_products_model_id", "products", "product_models", ["model_id"], ["id"], ondelete="SET NULL"
    )
    op.create_index("idx_products_model_id", "products", ["model_id"])


def downgrade() -> None:
    op.drop_index("idx_products_model_id", "products")
    op.drop_constraint("fk_products_model_id", "products", type_="foreignkey")
    op.drop_column("products", "model_id")
```

- [ ] **Step 6: Run migrations**

```
./infra/scripts/migrate.sh
docker restart mt-backend
curl http://localhost:8080/health/live
```
Expected: `{"status": "ok"}` or equivalent.

- [ ] **Step 7: Verify tables exist**

```
docker exec mt-db psql -U mt_app -d mt_db -c "\dt product_models model_dimension_rows model_flow_data model_tech_tables certificates certificate_scopes"
```
Expected: all 6 tables listed.

- [ ] **Step 8: Commit**

```bash
git add mt-pricing-backend/alembic/versions/20260529_126_product_models.py \
        mt-pricing-backend/alembic/versions/20260529_127_certificates.py \
        mt-pricing-backend/alembic/versions/20260529_128_documents_series_fields.py \
        mt-pricing-backend/alembic/versions/20260529_129_product_materials_grade.py \
        mt-pricing-backend/alembic/versions/20260529_130_products_model_fk.py
git commit -m "feat(alembic): migrations 126-130 — product_models hierarchy + certificates"
```

---

### Task 6: F1 smoke test — verify DB layer end to end

**Files:** none (verification only)

- [ ] **Step 1: Run full unit test suite**

```
cd mt-pricing-backend
pytest tests/unit/ -q --tb=short 2>&1 | tail -30
```
Expected: new tests pass, no regressions.

- [ ] **Step 2: Check Alembic head**

```
docker exec mt-backend alembic current
```
Expected: `20260529_130 (head)`.

- [ ] **Step 3: Verify new columns with psql**

```
docker exec mt-db psql -U mt_app -d mt_db -c "\d product_models"
docker exec mt-db psql -U mt_app -d mt_db -c "\d products" | grep model_id
docker exec mt-db psql -U mt_app -d mt_db -c "\d product_materials" | grep material_grade
docker exec mt-db psql -U mt_app -d mt_db -c "\d documents" | grep doc_number
```
Expected: columns present.

- [ ] **Step 4: Commit** (none — only verification)

---

## F2: Backend Services

---

### Task 7: Extend Pydantic schemas — new extraction types

**Files:**
- Modify: `mt-pricing-backend/app/schemas/ficha_enrich.py`
- Create: `mt-pricing-backend/tests/unit/schemas/test_ficha_enrich_v2.py`

#### Context

The ficha enrichment extractor currently captures `materials` (component + material text only). We need to extend it with:
- `ExtractedMaterial`: add `material_grade`, `material_standard`, `surface_treatment` (all optional str).
- `ExtractedDimensionRow`: add `dn_secondary_label` (str|None) for reducing fittings.
- `ExtractedCertificate`: new schema for issued certs captured from the PDF (cert_number, issuer, expires_at as str, certification_code).
- `ExtractedFlowData`: new schema for Kv/Cv + mesh per DN.
- `FichaExtractionResult`: add `certificates: list[ExtractedCertificate]` and `flow_data: list[ExtractedFlowData]`.

- [ ] **Step 1: Write the failing tests**

```python
# mt-pricing-backend/tests/unit/schemas/test_ficha_enrich_v2.py
"""Tests for extended ficha_enrich schemas."""
from app.schemas.ficha_enrich import (
    ExtractedMaterial,
    ExtractedDimensionRow,
    ExtractedCertificate,
    ExtractedFlowData,
    FichaExtractionResult,
    ExtractedScalars,
    ExtractedSpecs,
)


def test_extracted_material_has_grade():
    m = ExtractedMaterial(
        component="body",
        material="gunmetal",
        material_grade="EN-GJL-250",
        material_standard="UNE-EN-12165",
        surface_treatment="None",
    )
    assert m.material_grade == "EN-GJL-250"
    assert m.surface_treatment == "None"


def test_extracted_dimension_row_has_secondary():
    row = ExtractedDimensionRow(
        dn_label='1/2"',
        dn_secondary_label='3/8"',
        values={"A_mm": 24},
    )
    assert row.dn_secondary_label == '3/8"'


def test_extracted_certificate():
    cert = ExtractedCertificate(
        certification_code="ACS",
        cert_number="23 ACC LY 482",
        issuer="Carso",
        expires_at="2028-07-11",
    )
    assert cert.certification_code == "ACS"
    assert cert.cert_number == "23 ACC LY 482"


def test_extracted_flow_data():
    fd = ExtractedFlowData(dn_label='1"', kv=18.5, mesh_mm=1.8)
    assert fd.kv == 18.5
    assert fd.mesh_mm == 1.8


def test_ficha_extraction_result_has_certs_and_flow():
    result = FichaExtractionResult(
        scalars=ExtractedScalars(),
        specs=ExtractedSpecs(),
        certificates=[
            ExtractedCertificate(certification_code="WRAS", cert_number="240908012")
        ],
        flow_data=[
            ExtractedFlowData(dn_label='1"', kv=18.5)
        ],
    )
    assert len(result.certificates) == 1
    assert result.certificates[0].certification_code == "WRAS"
    assert len(result.flow_data) == 1
```

- [ ] **Step 2: Run test to verify it fails**

```
pytest tests/unit/schemas/test_ficha_enrich_v2.py -v
```
Expected: ImportError or ValidationError on missing fields.

- [ ] **Step 3: Update `ficha_enrich.py` schemas**

In `ExtractedMaterial` class, add three optional fields:
```python
    material_grade: str | None = None
    material_standard: str | None = None
    surface_treatment: str | None = None
```

In `ExtractedDimensionRow` class, add:
```python
    dn_secondary_label: str | None = None
```

Add two new classes after `ExtractedSpecs`:

```python
class ExtractedCertificate(BaseModel):
    """Certificado emitido detectado en el PDF."""
    certification_code: str  # e.g. "ACS", "WRAS", "PZH", "CE"
    cert_number: str | None = None
    issuer: str | None = None
    issued_at: str | None = None   # ISO date string "YYYY-MM-DD"
    expires_at: str | None = None  # ISO date string "YYYY-MM-DD"
    signatory_name: str | None = None
    signatory_role: str | None = None


class ExtractedFlowData(BaseModel):
    """Coeficiente de flujo Kv/Cv + malla por DN."""
    dn_label: str
    kv: float | None = None
    cv: float | None = None
    mesh_mm: float | None = None
```

In `FichaExtractionResult`, add two new fields after `pt_curve_points`:
```python
    certificates: list[ExtractedCertificate] = Field(default_factory=list)
    flow_data: list[ExtractedFlowData] = Field(default_factory=list)
```

- [ ] **Step 4: Run test again**

```
pytest tests/unit/schemas/test_ficha_enrich_v2.py -v
```
Expected: PASS (5 tests).

- [ ] **Step 5: Run all unit tests**

```
pytest tests/unit/ -q --tb=short 2>&1 | tail -20
```
Expected: no regressions.

- [ ] **Step 6: Commit**

```bash
git add mt-pricing-backend/app/schemas/ficha_enrich.py \
        mt-pricing-backend/tests/unit/schemas/test_ficha_enrich_v2.py
git commit -m "feat(schemas): ExtractedCertificate + ExtractedFlowData + grade fields in extraction"
```

---

### Task 8: Extend extractor tool schema — new fields for Claude

**Files:**
- Modify: `mt-pricing-backend/app/services/ficha_enrichment/extractor.py`
- Create: `mt-pricing-backend/tests/unit/services/ficha_enrichment/test_extractor_schema.py`

#### Context

The Claude `tool_use` schema (`_TOOL_SCHEMA`) controls what fields Claude extracts from the PDF. We need to add:
1. `materials[].material_grade`, `materials[].material_standard`, `materials[].surface_treatment`
2. `dimensions[].dn_secondary_label` (for reducing fittings)
3. `certificates` array with cert_number, issuer, expires_at, certification_code
4. `flow_data` array with dn_label, kv, mesh_mm

The test verifies the schema structure (no API call needed — just check the dict shape).

- [ ] **Step 1: Write the failing test**

```python
# mt-pricing-backend/tests/unit/services/ficha_enrichment/test_extractor_schema.py
"""Verify _TOOL_SCHEMA contains required new fields (no API call)."""
from app.services.ficha_enrichment.extractor import _TOOL_SCHEMA


def test_materials_has_grade_fields():
    materials_items = _TOOL_SCHEMA["input_schema"]["properties"]["materials"]["items"]
    props = materials_items["properties"]
    assert "material_grade" in props
    assert "material_standard" in props
    assert "surface_treatment" in props


def test_dimensions_has_secondary_dn():
    dim_items = _TOOL_SCHEMA["input_schema"]["properties"]["dimensions"]["items"]
    props = dim_items["properties"]
    assert "dn_secondary_label" in props


def test_certificates_field_exists():
    props = _TOOL_SCHEMA["input_schema"]["properties"]
    assert "certificates" in props
    cert_items = props["certificates"]["items"]["properties"]
    assert "certification_code" in cert_items
    assert "cert_number" in cert_items
    assert "expires_at" in cert_items


def test_flow_data_field_exists():
    props = _TOOL_SCHEMA["input_schema"]["properties"]
    assert "flow_data" in props
    fd_items = props["flow_data"]["items"]["properties"]
    assert "dn_label" in fd_items
    assert "kv" in fd_items
    assert "mesh_mm" in fd_items
```

- [ ] **Step 2: Run to verify it fails**

```
pytest tests/unit/services/ficha_enrichment/test_extractor_schema.py -v
```
Expected: AssertionError on missing keys.

- [ ] **Step 3: Update `_TOOL_SCHEMA` in `extractor.py`**

Find the `materials` items properties (around line 72) and add after `observations`:

```python
                        "material_grade": {
                            "type": "string",
                            "description": "Grado material según norma (ej. EN-GJL-250, CW617N, AISI 304)"
                        },
                        "material_standard": {
                            "type": "string",
                            "description": "Norma del material (ej. UNE-EN-12165, ASTM A307)"
                        },
                        "surface_treatment": {
                            "type": "string",
                            "description": "Tratamiento superficial (ej. Nickel, Epoxy, Zinc, None)"
                        },
```

Find the `dimensions` items properties and add after `values`:

```python
                        "dn_secondary_label": {
                            "type": "string",
                            "description": "DN salida para reductores (ej. '3/8\"' en una reducción 1/2 x 3/8)"
                        },
```

Add two new top-level properties to `input_schema.properties` (after `flow_data` / `pt_curve_points`):

```python
            "certificates": {
                "type": "array",
                "description": "Certificados emitidos detectados en el PDF (ACS, WRAS, PZH, CE/PED, etc.)",
                "items": {
                    "type": "object",
                    "required": ["certification_code"],
                    "properties": {
                        "certification_code": {
                            "type": "string",
                            "description": "Código de la certificación: ACS | WRAS | PZH | CE | FM | ISO9001 | WRAS"
                        },
                        "cert_number": {"type": "string"},
                        "issuer": {"type": "string", "description": "Organismo emisor (ej. Carso, BSI, TÜV)"},
                        "issued_at": {"type": "string", "description": "Fecha emisión ISO (YYYY-MM-DD)"},
                        "expires_at": {"type": "string", "description": "Fecha caducidad ISO (YYYY-MM-DD)"},
                        "signatory_name": {"type": "string"},
                        "signatory_role": {"type": "string"},
                    },
                },
            },
            "flow_data": {
                "type": "array",
                "description": "Coeficientes Kv/Cv y malla de filtración por DN (coladores/filtros)",
                "items": {
                    "type": "object",
                    "required": ["dn_label"],
                    "properties": {
                        "dn_label": {"type": "string", "description": "Etiqueta DN como aparece en la tabla"},
                        "kv": {"type": "number", "description": "Coeficiente de flujo Kv (m³/h)"},
                        "cv": {"type": "number", "description": "Coeficiente de flujo Cv (US gpm)"},
                        "mesh_mm": {"type": "number", "description": "Tamaño malla en mm (ej. 1.8, 1.0)"},
                    },
                },
            },
```

- [ ] **Step 4: Update `_parse_tool_result` in extractor to map new fields**

In the `_parse_tool_result` method (or equivalent function that converts the Claude tool output to `FichaExtractionResult`), ensure it maps:
- `inp.get("certificates", [])` → `FichaExtractionResult.certificates` as `list[ExtractedCertificate]`
- `inp.get("flow_data", [])` → `FichaExtractionResult.flow_data` as `list[ExtractedFlowData]`
- For each material in `inp.get("materials", [])`, map `material_grade`, `material_standard`, `surface_treatment`
- For each dimension in `inp.get("dimensions", [])`, map `dn_secondary_label`

Find the existing parsing code (it converts the tool result dict to Pydantic objects) and extend the `ExtractedMaterial` and `ExtractedDimensionRow` instantiation to include the new fields using `.get(..., None)`.

- [ ] **Step 5: Run all tests**

```
pytest tests/unit/ -q --tb=short 2>&1 | tail -20
```
Expected: PASS including 4 new schema tests.

- [ ] **Step 6: Commit**

```bash
git add mt-pricing-backend/app/services/ficha_enrichment/extractor.py \
        mt-pricing-backend/tests/unit/services/ficha_enrichment/test_extractor_schema.py
git commit -m "feat(extractor): extend tool schema — certificates, flow_data, material grades, reducing fittings"
```

---

### Task 9: `model_writer.py` — write extracted data to `product_models`

**Files:**
- Create: `mt-pricing-backend/app/services/ficha_enrichment/model_writer.py`
- Create: `mt-pricing-backend/tests/unit/services/ficha_enrichment/test_model_writer.py`

#### Context

`model_writer.py` is the service that receives a `series_prefix` (e.g., "4097") + `FichaExtractionResult` and writes to `product_models`, `model_dimension_rows`, `model_flow_data`, `model_tech_tables`, and `certificates`. It also links existing `products` rows to the `ProductModel` via `products.model_id`.

Logic:
1. `upsert_model(session, series_prefix, variant_series, extraction)` → `ProductModel`
   - Find or create `ProductModel` with code=series_prefix
   - If variant_series provided, find or create variant model and set `variant_of_id`
2. `write_dimension_rows(session, model, extraction)` — upsert dimension rows from `extraction.dimensions`
3. `write_flow_data(session, model, extraction)` — upsert flow data from `extraction.flow_data`
4. `write_pt_curves(session, model, extraction)` — write P/T curve points to `model_tech_tables` (kind='pt_curve', gasket_material=None unless multiple detected)
5. `write_certificates(session, model, extraction)` — upsert `Certificate` rows from `extraction.certificates`
6. `link_products_to_model(session, model, series_prefix)` — UPDATE products SET model_id=model.id WHERE sku LIKE '{series_prefix}%' AND model_id IS NULL

Tests use mocked sessions (pure logic, no DB required).

- [ ] **Step 1: Write the failing tests**

```python
# mt-pricing-backend/tests/unit/services/ficha_enrichment/test_model_writer.py
"""Unit tests for model_writer — pure logic, mocked session."""
import uuid
from unittest.mock import AsyncMock, MagicMock, patch
import pytest
from app.services.ficha_enrichment.model_writer import (
    _parse_dn_from_label,
    _build_dimensions_dict,
    write_pt_curves_data,
)
from app.schemas.ficha_enrich import (
    FichaExtractionResult,
    ExtractedScalars,
    ExtractedSpecs,
    ExtractedDimensionRow,
    ExtractedFlowData,
)


def _make_result(**kwargs):
    return FichaExtractionResult(
        scalars=ExtractedScalars(),
        specs=ExtractedSpecs(),
        **kwargs,
    )


def test_parse_dn_from_label_imperial():
    from app.services.ficha_enrichment.series_resolver import dn_label_to_int
    assert dn_label_to_int('1/2"') == 15
    assert dn_label_to_int("DN25") == 25


def test_build_dimensions_dict():
    row = ExtractedDimensionRow(
        dn_label="DN15",
        values={"L_mm": 57.0, "H_mm": 72.0},
    )
    result = _build_dimensions_dict(row)
    assert result == {"L_mm": 57.0, "H_mm": 72.0}


def test_build_dimensions_dict_with_secondary():
    row = ExtractedDimensionRow(
        dn_label='1/2"',
        dn_secondary_label='3/8"',
        values={"A_mm": 24.0},
    )
    result = _build_dimensions_dict(row)
    assert result == {"A_mm": 24.0}


def test_write_pt_curves_data_single():
    result = _make_result(
        pt_curve_points=[
            {"temperature_c": 20, "pressure_max_bar": 30},
            {"temperature_c": 120, "pressure_max_bar": 20},
        ]
    )
    tables = write_pt_curves_data(result)
    assert len(tables) == 1
    assert tables[0]["kind"] == "pt_curve"
    assert tables[0]["gasket_material"] is None
    assert len(tables[0]["data"]) == 2
```

- [ ] **Step 2: Run to verify it fails**

```
pytest tests/unit/services/ficha_enrichment/test_model_writer.py -v
```
Expected: ImportError.

- [ ] **Step 3: Create `model_writer.py`**

```python
# mt-pricing-backend/app/services/ficha_enrichment/model_writer.py
"""Writes extracted ficha data to product_models and related tables."""
from __future__ import annotations

import logging
from typing import Any

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.certificates import Certificate
from app.db.models.product_models import (
    ModelDimensionRow,
    ModelFlowData,
    ModelTechTable,
    ProductModel,
)
from app.db.models.product import Product
from app.schemas.ficha_enrich import (
    ExtractedDimensionRow,
    ExtractedFlowData,
    FichaExtractionResult,
)
from app.services.ficha_enrichment.series_resolver import dn_label_to_int

logger = logging.getLogger(__name__)


def _build_dimensions_dict(row: ExtractedDimensionRow) -> dict[str, Any]:
    return dict(row.values)


def write_pt_curves_data(extraction: FichaExtractionResult) -> list[dict[str, Any]]:
    """Returns list of dicts {kind, gasket_material, data} for ModelTechTable creation."""
    if not extraction.pt_curve_points:
        return []
    return [{"kind": "pt_curve", "gasket_material": None, "data": extraction.pt_curve_points}]


async def upsert_model(
    session: AsyncSession,
    series_prefix: str,
    variant_series: str | None = None,
) -> ProductModel:
    """Find or create ProductModel for series_prefix. Links variant if provided."""
    result = await session.execute(
        select(ProductModel).where(ProductModel.code == series_prefix)
    )
    model = result.scalar_one_or_none()
    if model is None:
        model = ProductModel(code=series_prefix)
        session.add(model)
        await session.flush()

    if variant_series:
        v_result = await session.execute(
            select(ProductModel).where(ProductModel.code == variant_series)
        )
        variant = v_result.scalar_one_or_none()
        if variant is None:
            variant = ProductModel(code=variant_series, variant_of_id=model.id)
            session.add(variant)
            await session.flush()
        elif variant.variant_of_id is None:
            variant.variant_of_id = model.id

    return model


async def write_dimension_rows(
    session: AsyncSession,
    model: ProductModel,
    extraction: FichaExtractionResult,
) -> None:
    """Upsert dimension rows from extraction.dimensions."""
    for row in extraction.dimensions:
        dn = dn_label_to_int(row.dn_label)
        if dn is None:
            logger.warning("model_writer: cannot parse DN from '%s'", row.dn_label)
            continue
        dn_sec = dn_label_to_int(row.dn_secondary_label) if row.dn_secondary_label else None

        existing = await session.execute(
            select(ModelDimensionRow).where(
                ModelDimensionRow.model_id == model.id,
                ModelDimensionRow.dn_mm == dn,
                ModelDimensionRow.dn_secondary_mm == dn_sec,
            )
        )
        dim_row = existing.scalar_one_or_none()
        if dim_row is None:
            dim_row = ModelDimensionRow(
                model_id=model.id,
                dn_mm=dn,
                dn_secondary_mm=dn_sec,
                dimensions=_build_dimensions_dict(row),
                source="ficha_enrichment",
            )
            session.add(dim_row)
        else:
            dim_row.dimensions = _build_dimensions_dict(row)


async def write_flow_data_rows(
    session: AsyncSession,
    model: ProductModel,
    extraction: FichaExtractionResult,
) -> None:
    """Upsert flow data rows."""
    for fd in extraction.flow_data:
        dn = dn_label_to_int(fd.dn_label)
        if dn is None:
            continue
        existing = await session.execute(
            select(ModelFlowData).where(
                ModelFlowData.model_id == model.id,
                ModelFlowData.dn_mm == dn,
                ModelFlowData.mesh_mm == fd.mesh_mm,
            )
        )
        row = existing.scalar_one_or_none()
        if row is None:
            row = ModelFlowData(
                model_id=model.id,
                dn_mm=dn,
                kv=fd.kv,
                cv=fd.cv,
                mesh_mm=fd.mesh_mm,
            )
            session.add(row)
        else:
            row.kv = fd.kv
            row.cv = fd.cv


async def write_model_tech_tables(
    session: AsyncSession,
    model: ProductModel,
    extraction: FichaExtractionResult,
) -> None:
    """Write P/T curve and flow table to model_tech_tables."""
    for table_data in write_pt_curves_data(extraction):
        existing = await session.execute(
            select(ModelTechTable).where(
                ModelTechTable.model_id == model.id,
                ModelTechTable.kind == table_data["kind"],
                ModelTechTable.gasket_material == table_data["gasket_material"],
            )
        )
        tt = existing.scalar_one_or_none()
        if tt is None:
            tt = ModelTechTable(
                model_id=model.id,
                kind=table_data["kind"],
                gasket_material=table_data["gasket_material"],
                data=table_data["data"],
                source="ficha_enrichment",
            )
            session.add(tt)
        else:
            tt.data = table_data["data"]


async def write_certificates(
    session: AsyncSession,
    model: ProductModel,
    extraction: FichaExtractionResult,
) -> None:
    """Create Certificate rows from extraction.certificates (skip if cert_number already exists for model)."""
    for cert_data in extraction.certificates:
        if not cert_data.cert_number:
            continue
        existing = await session.execute(
            select(Certificate).where(
                Certificate.model_id == model.id,
                Certificate.cert_number == cert_data.cert_number,
            )
        )
        if existing.scalar_one_or_none() is not None:
            continue  # already saved
        cert = Certificate(
            model_id=model.id,
            cert_number=cert_data.cert_number,
            issuer=cert_data.issuer,
            signatory_name=cert_data.signatory_name,
            signatory_role=cert_data.signatory_role,
            status="valid",
        )
        session.add(cert)


async def link_products_to_model(
    session: AsyncSession,
    model: ProductModel,
    series_prefix: str,
) -> None:
    """Set model_id on existing products with matching SKU prefix where not already set."""
    await session.execute(
        update(Product)
        .where(
            Product.sku.like(f"{series_prefix}%"),
            Product.model_id.is_(None),
        )
        .values(model_id=model.id)
    )


async def write_model_data(
    session: AsyncSession,
    series_prefix: str,
    extraction: FichaExtractionResult,
    variant_series: str | None = None,
) -> ProductModel:
    """Orchestrates all model-level writes for one series."""
    model = await upsert_model(session, series_prefix, variant_series)
    await write_dimension_rows(session, model, extraction)
    await write_flow_data_rows(session, model, extraction)
    await write_model_tech_tables(session, model, extraction)
    await write_certificates(session, model, extraction)
    await link_products_to_model(session, model, series_prefix)
    return model


__all__ = [
    "write_model_data",
    "upsert_model",
    "write_dimension_rows",
    "write_flow_data_rows",
    "write_model_tech_tables",
    "write_certificates",
    "link_products_to_model",
    "_build_dimensions_dict",
    "write_pt_curves_data",
]
```

- [ ] **Step 4: Run the tests**

```
pytest tests/unit/services/ficha_enrichment/test_model_writer.py -v
```
Expected: PASS (4 tests).

- [ ] **Step 5: Commit**

```bash
git add mt-pricing-backend/app/services/ficha_enrichment/model_writer.py \
        mt-pricing-backend/tests/unit/services/ficha_enrichment/test_model_writer.py
git commit -m "feat(enrichment): model_writer — write extraction to product_models hierarchy"
```

---

### Task 10: Wire `model_writer` into `series_resolver` and `applier`

**Files:**
- Modify: `mt-pricing-backend/app/services/ficha_enrichment/series_resolver.py`
- Modify: `mt-pricing-backend/app/services/ficha_enrichment/applier.py`
- Modify: `mt-pricing-backend/app/api/routes/ficha_enrich.py`

#### Context

The series resolver currently only resolves SKU diffs. After resolving, it should also call `write_model_data` so model-level data is persisted. This happens in the `apply` flow (not preview), so the change is in `apply_ficha_series` route which calls the applier.

Two changes:
1. In `applier.py`, after all SKUs are applied, call `write_model_data` for each series group.
2. In `ficha_enrich.py` `apply_ficha_series`, pass `series_groups` context to the applier (currently lost after preview — the apply request carries `body.series` string but not the full group structure).

Simplest approach: in `apply_ficha_series`, after processing all SKUs, call `write_model_data(session, body.series, body.extraction)`. No need to pass groups — series_prefix is sufficient, and the ficha already carries the variant info in `body.variant_links`.

- [ ] **Step 1: Add call in `apply_ficha_series` route**

In `mt-pricing-backend/app/api/routes/ficha_enrich.py`, at the bottom of `apply_ficha_series` after the `for target_sku in body.apply_to_skus` loop (before `document_id` block), add:

```python
    # Write model-level data (dimensions, P/T, certs, flow)
    from app.services.ficha_enrichment.model_writer import write_model_data
    # Determine base and variant series from apply_to_skus + variant_links
    variant_bases = set(body.variant_links.values()) if body.variant_links else set()
    all_series_codes = {body.series}
    # If variant_links has variant_sku → base_sku, detect unique variants
    variant_series: str | None = None
    for v_sku, base_sku in (body.variant_links or {}).items():
        # Infer series code from SKU prefix (strip last 3 digits)
        if len(v_sku) > 3:
            all_series_codes.add(v_sku[:-3])
        if len(base_sku) > 3:
            all_series_codes.add(base_sku[:-3])

    await write_model_data(session, body.series, body.extraction)
```

- [ ] **Step 2: Also extend `ProductMaterial` writes in applier to include grade fields**

In `mt-pricing-backend/app/services/ficha_enrichment/applier.py`, in the section that writes materials (around the `apply_materials` block), extend `ProductMaterial` instantiation:

Find where `ProductMaterial` objects are created (look for `ProductMaterial(product_sku=...`) and add:

```python
            new_mat = ProductMaterial(
                product_sku=sku,
                component=mat.component,
                position=mat.position,
                material=mat.material,
                observations=mat.observations,
                material_grade=mat.material_grade,       # new
                material_standard=mat.material_standard, # new
                surface_treatment=mat.surface_treatment, # new
            )
```

- [ ] **Step 3: Run unit tests**

```
pytest tests/unit/ -q --tb=short 2>&1 | tail -20
```
Expected: PASS, no regressions.

- [ ] **Step 4: Redeploy backend**

```
docker restart mt-backend mt-worker
curl http://localhost:8080/health/live
```

- [ ] **Step 5: Commit**

```bash
git add mt-pricing-backend/app/api/routes/ficha_enrich.py \
        mt-pricing-backend/app/services/ficha_enrichment/applier.py
git commit -m "feat(enrichment): wire model_writer into apply flow — persist model hierarchy on apply"
```

---

### Task 11: Update TypeScript API types and frontend hooks

**Files:**
- Modify: `mt-pricing-frontend/lib/api/endpoints/ficha-enrich.ts`

#### Context

The `FichaSeriesApplyResponse` and `FichaSeriesPreviewResponse` TS types need to include the new extraction fields so the frontend can render them. Add `ExtractedCertificate`, `ExtractedFlowData`, and update `ExtractedMaterial` to include grade fields.

- [ ] **Step 1: Update `ficha-enrich.ts`**

In `ExtractedMaterial` interface, add:
```typescript
  material_grade?: string | null;
  material_standard?: string | null;
  surface_treatment?: string | null;
```

In `ExtractedDimensionRow` interface, add:
```typescript
  dn_secondary_label?: string | null;
```

Add two new interfaces before `FichaExtractionResult`:
```typescript
export interface ExtractedCertificate {
  certification_code: string;
  cert_number?: string | null;
  issuer?: string | null;
  issued_at?: string | null;
  expires_at?: string | null;
  signatory_name?: string | null;
  signatory_role?: string | null;
}

export interface ExtractedFlowData {
  dn_label: string;
  kv?: number | null;
  cv?: number | null;
  mesh_mm?: number | null;
}
```

In `FichaExtractionResult` interface, add:
```typescript
  certificates: ExtractedCertificate[];
  flow_data: ExtractedFlowData[];
```

- [ ] **Step 2: Verify TypeScript compiles**

```
cd mt-pricing-frontend
npx tsc --noEmit 2>&1 | head -30
```
Expected: 0 errors related to the changed types.

- [ ] **Step 3: Commit**

```bash
git add mt-pricing-frontend/lib/api/endpoints/ficha-enrich.ts
git commit -m "feat(frontend/types): add ExtractedCertificate, ExtractedFlowData, material grade fields"
```

---

## F3: Frontend Wizard

---

### Task 12: Display model hierarchy in `/fichas` wizard — SKU table enhancement

**Files:**
- Modify: `mt-pricing-frontend/app/(app)/fichas/_client.tsx`

#### Context

The current wizard shows a flat list of SKUs (SkuDiffResult[]). We need to enhance it to show:
1. **Model grouping**: group SKUs by series code. If `series_groups` is available in the response, render one accordion section per model (base + variant together).
2. **Certificate badges**: if extraction contains certificates, display them as badges above the SKU table (code + cert_number + expires_at).
3. **Reducing fitting indicator**: if a dimension row has `dn_secondary_label`, show both DNs in the table (e.g., "DN15 × DN10").

Read the current `_client.tsx` before making changes. Preserve all existing functionality.

- [ ] **Step 1: Read the current file**

```
# Read mt-pricing-frontend/app/(app)/fichas/_client.tsx
```

- [ ] **Step 2: Add `CertificateBadge` component inline**

At the top of the component (before the main return), add:

```tsx
function CertificateBadge({ cert }: { cert: ExtractedCertificate }) {
  const expiresLabel = cert.expires_at
    ? new Date(cert.expires_at).toLocaleDateString("es-ES", { year: "numeric", month: "short" })
    : null;
  return (
    <span className="inline-flex items-center gap-1 rounded-full border px-2 py-0.5 text-xs font-medium">
      <span className="font-semibold">{cert.certification_code}</span>
      {cert.cert_number && <span className="text-muted-foreground">#{cert.cert_number}</span>}
      {expiresLabel && <span className="text-muted-foreground">exp. {expiresLabel}</span>}
    </span>
  );
}
```

- [ ] **Step 3: Render certificate badges**

In the wizard step where the extraction results are shown (before the SKU table), add:

```tsx
{preview.extraction.certificates.length > 0 && (
  <div className="flex flex-wrap gap-1.5">
    <span className="text-xs text-muted-foreground self-center">Certs:</span>
    {preview.extraction.certificates.map((cert, i) => (
      <CertificateBadge key={i} cert={cert} />
    ))}
  </div>
)}
```

- [ ] **Step 4: Group SKUs by series group in the SKU selector**

Where `series_groups` from the preview response is available, render a grouped layout:

```tsx
{preview.series_groups && preview.series_groups.length > 0 ? (
  <div className="space-y-3">
    {preview.series_groups.map((group) => (
      <div key={group.base_series} className="rounded-md border">
        <div className="flex items-center gap-2 px-3 py-2 bg-muted/50 text-sm font-medium">
          Serie {group.base_series}
          {group.variant_series && (
            <span className="text-muted-foreground">/ {group.variant_series}</span>
          )}
        </div>
        <div className="divide-y">
          {[...group.base_skus, ...group.variant_skus].map((skuResult) => (
            <SkuRow key={skuResult.sku} skuResult={skuResult} /* existing row component */ />
          ))}
        </div>
      </div>
    ))}
  </div>
) : (
  /* existing flat list rendering */
  <div className="divide-y">
    {preview.series_skus.map((skuResult) => (
      <SkuRow key={skuResult.sku} skuResult={skuResult} />
    ))}
  </div>
)}
```

Adapt `SkuRow` to whatever structure exists in `_client.tsx` — the key point is using the same checkbox selection logic.

- [ ] **Step 5: Verify TypeScript compiles**

```
cd mt-pricing-frontend
npx tsc --noEmit 2>&1 | head -30
```
Expected: 0 errors.

- [ ] **Step 6: Start dev server and verify wizard renders**

```
docker restart mt-frontend
```
Open browser at `http://localhost:3000/fichas`, upload MTFT_4097.pdf, verify:
- Certificate badges appear (ACS, WRAS, PZH)
- Series groups show (4097/40972, 4295/42952, etc.)

- [ ] **Step 7: Commit**

```bash
git add mt-pricing-frontend/app/(app)/fichas/_client.tsx
git commit -m "feat(fichas): group SKUs by model, display certificate badges in wizard"
```

---

### Task 13: Display flow data and reducing fitting DN in wizard

**Files:**
- Modify: `mt-pricing-frontend/app/(app)/fichas/_client.tsx`

#### Context

Two small additions:
1. **Kv/flow table**: if `extraction.flow_data.length > 0`, render a small table showing DN | Kv | Cv | Mesh columns in the extraction details panel.
2. **Reducing fitting DN**: in the dimensions preview table (if present), show both DNs for rows where `dn_secondary_label` is set (format: "DN15 × DN10").

These are display-only additions — no state or API changes.

- [ ] **Step 1: Add Kv/flow table to extraction details**

Find where dimension rows are displayed in the wizard (look for `extraction.dimensions` rendering). After that section, add:

```tsx
{preview.extraction.flow_data.length > 0 && (
  <div className="mt-3">
    <p className="text-xs font-medium mb-1.5">Coeficientes de flujo (Kv/Cv)</p>
    <table className="w-full text-xs border-collapse">
      <thead>
        <tr className="bg-muted/40">
          <th className="px-2 py-1 text-left border">DN</th>
          <th className="px-2 py-1 text-right border">Kv (m³/h)</th>
          <th className="px-2 py-1 text-right border">Cv</th>
          <th className="px-2 py-1 text-right border">Malla (mm)</th>
        </tr>
      </thead>
      <tbody>
        {preview.extraction.flow_data.map((fd, i) => (
          <tr key={i}>
            <td className="px-2 py-1 border">{fd.dn_label}</td>
            <td className="px-2 py-1 border text-right">{fd.kv ?? "—"}</td>
            <td className="px-2 py-1 border text-right">{fd.cv ?? "—"}</td>
            <td className="px-2 py-1 border text-right">{fd.mesh_mm ?? "—"}</td>
          </tr>
        ))}
      </tbody>
    </table>
  </div>
)}
```

- [ ] **Step 2: Handle reducing fitting DN labels**

In the dimensions table rendering, replace the simple `{row.dn_label}` cell with:

```tsx
<td className="px-2 py-1 border font-mono">
  {row.dn_label}
  {row.dn_secondary_label && (
    <span className="text-muted-foreground"> × {row.dn_secondary_label}</span>
  )}
</td>
```

- [ ] **Step 3: TypeScript compile check**

```
cd mt-pricing-frontend
npx tsc --noEmit 2>&1 | head -30
```
Expected: 0 errors.

- [ ] **Step 4: Redeploy and test**

```
docker restart mt-frontend
```
Open `/fichas`, upload MTFT_5110ANSI.pdf (Y-strainer), verify:
- Kv/flow table appears with DN and Kv columns populated
- Upload MTFT_001.pdf (fittings), verify reducing fittings show "DN15 × DN10" format

- [ ] **Step 5: Commit**

```bash
git add mt-pricing-frontend/app/(app)/fichas/_client.tsx
git commit -m "feat(fichas): flow data table + reducing fitting dual-DN display"
```

---

### Task 14: Final redeploy + E2E smoke test

**Files:** none (verification only)

- [ ] **Step 1: Full redeploy**

```
docker restart mt-backend mt-frontend mt-worker mt-beat
curl http://localhost:8080/health/live
```
Expected: `{"status": "ok"}`.

- [ ] **Step 2: Verify Alembic head**

```
docker exec mt-backend alembic current
```
Expected: `20260529_130 (head)`.

- [ ] **Step 3: E2E test MTFT_4097.pdf**

1. Go to `http://localhost:3000/fichas`
2. Upload `MTFT_4097.pdf`
3. Verify preview shows: series groups (4097/40972, 4295/42952, 4098/40982, etc.), certificate badges (ACS, WRAS, PZH), dimension rows for each DN
4. Apply to all SKUs
5. After apply, open `http://localhost:3000/catalogo/<any 4097 SKU>` and verify product still loads

- [ ] **Step 4: Verify `product_models` row created in DB**

```
docker exec mt-db psql -U mt_app -d mt_db -c "SELECT code, color_label, variant_of_id FROM product_models ORDER BY code;"
```
Expected: rows like `4097 | NULL | NULL`, `40972 | NULL | <uuid of 4097>`.

- [ ] **Step 5: Verify `model_dimension_rows` populated**

```
docker exec mt-db psql -U mt_app -d mt_db -c "SELECT model_id, dn_mm, dimensions FROM model_dimension_rows LIMIT 5;"
```
Expected: rows with JSONB dimension data.

- [ ] **Step 6: Verify `products.model_id` linked**

```
docker exec mt-db psql -U mt_app -d mt_db -c "SELECT sku, model_id FROM products WHERE sku LIKE '4097%' ORDER BY sku;"
```
Expected: all 4097xxx SKUs have a non-null `model_id`.

- [ ] **Step 7: Commit** (none — verification only)

---

## Self-Review

### Spec coverage check

| Requirement | Task |
|-------------|------|
| `product_models` table with `variant_of_id` | T1, T5 |
| `model_dimension_rows` JSONB schema | T1, T5 |
| `dn_secondary_mm` reducing fittings | T1, T5 |
| `model_flow_data` (Kv/Cv/mesh) | T1, T5 |
| `model_tech_tables` P/T curves per gasket | T1, T5 |
| `certificates` with lifecycle status | T2, T5 |
| `certificate_scopes` | T2, T5 |
| `Series.thread_standard/revision` | T3, T5 |
| `Document.doc_number/series_id/signatory` | T3, T5 |
| `ProductMaterial.material_grade/standard/surface_treatment` | T3, T5 |
| `products.model_id` FK | T4, T5 |
| Extractor tool schema — new fields | T8 |
| Pydantic schemas — new types | T7 |
| `model_writer` service | T9 |
| Wire model_writer into apply flow | T10 |
| TS types updated | T11 |
| Frontend: certificate badges | T12 |
| Frontend: series group layout | T12 |
| Frontend: flow data table | T13 |
| Frontend: reducing fitting dual-DN | T13 |
| E2E validation | T14 |

### Potential issues

- `ModelDimensionRow` uses `dn_secondary_mm == None` in the UNIQUE constraint — PostgreSQL treats `NULL != NULL`, so two rows with the same `model_id` + `dn_mm` but both `dn_secondary_mm IS NULL` would NOT violate the unique constraint (correct behavior). Two reducing fittings with different outlet DNs are correctly distinct rows.
- Migration 128 drops and recreates the CHECK constraint on `documents.type` — verify the constraint name matches what's in the DB before running (check with `\d documents` in psql).
- `Boolean` in `product_models.py` Task 1 Step 3 needs to be imported: `from sqlalchemy import Boolean, ...`.
