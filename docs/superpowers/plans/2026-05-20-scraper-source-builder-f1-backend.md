# Scraper Source Builder — Fase 1 (Backend del motor) — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Construir el backend del motor de scraper configurable data-driven, de modo que se pueda dar de alta un sitio de precios de competidor (perfil `competitor_price`), definir su receta de extracción como JSON, validarla y scrapearlo — todo sin escribir código de adapter.

**Architecture:** Una `ScraperSource` es una definición de sitio en DB; una `ScraperSourceRecipe` (versionada, una `is_live` por source) contiene el JSON de extracción (URL templates, `list_item_selector`, `fields` con selectores CSS, transforms declarativos). Un `GenericConfigurableFetcher` implementa el `FetcherPort` existente: lee la receta, hace fetch, extrae con selectores CSS (selectolax) y mapea a `CandidateRaw` — el mismo contrato que ya consume el pipeline de matching. Los adapters hardcodeados de Amazon/Noon no se tocan.

**Tech Stack:** FastAPI · SQLAlchemy 2.0 async · Alembic · Pydantic v2 · selectolax (CSS selectors, ya en `pyproject.toml`) · curl_cffi (fetch `static`) · pytest + testcontainers · Celery.

---

## Decisiones de arquitectura (leer antes de empezar)

1. **`get_fetcher()` NO se modifica.** Es síncrona y no puede hacer la consulta async a DB que requiere una source. En su lugar se añade `async def resolve_fetcher(channel, session)` en el mismo módulo: si el canal es hardcodeado delega en `get_fetcher()`, si no, busca un `ScraperSource` por slug. Esto cumple el "fallback" del spec sin romper la función existente.

2. **Modos de fetch en F1: solo `static` (curl_cffi).** El enum acepta `headless`/`stealth` (se almacenan), pero `GenericConfigurableFetcher` para una source con esos modos lanza `NotImplementedError` con mensaje claro — comportamiento real y testeado, no un placeholder. Los modos browser se implementan en una fase posterior.

3. **Selectores: solo CSS en F1** (selectolax no soporta XPath). El campo `selector` de la receta es siempre un selector CSS. XPath queda fuera de alcance de F1.

4. **Perfil `competitor_price` → `CandidateRaw`.** La receta mapea sus `fields` a nombres canónicos: `external_id` y `title` (obligatorios), `brand`, `price_aed`, `delivery_text`; cualquier otro field va a `CandidateRaw.specs`. La persistencia reutiliza `CompetitorBrandRepository.upsert_listing()` sin cambios — por eso `scraper_sources` lleva un FK nullable `competitor_brand_id` y el `scrape_source_task` requiere que esté seteado.

5. **Snippets LLM (híbrido B) NO entran en F1.** El campo `has_unapproved_snippet` y la columna existen, pero F1 solo implementa transforms declarativos. El sandbox de snippets es de una fase posterior.

6. **Permisos:** se reutilizan `products:read` / `products:write` (como el router `scraper.py` existente). No se crean permisos nuevos.

## File Structure

| Archivo | Acción | Responsabilidad |
|---------|--------|-----------------|
| `alembic/versions/20260602_145_scraper_sources.py` | Crear | Migración: 4 enum types + 3 tablas |
| `app/db/models/scraper_sources.py` | Crear | Modelos ORM: `ScraperSource`, `ScraperSourceRecipe`, `ScraperSourceTestRun` |
| `app/db/models/__init__.py` | Modificar | Registrar el módulo nuevo para Alembic/metadata |
| `app/schemas/scraper_sources.py` | Crear | Schemas Pydantic: receta + request/response de API |
| `app/services/scraper/recipe_transforms.py` | Crear | Motor de transforms declarativos |
| `app/services/scraper/recipe_extractor.py` | Crear | Aplica receta → HTML → registros (selectolax) |
| `app/services/matching/adapters/generic_configurable.py` | Crear | `GenericConfigurableFetcher` (FetcherPort) |
| `app/services/matching/adapter_registry.py` | Modificar | Añadir `resolve_fetcher()` async |
| `app/repositories/scraper_sources.py` | Crear | `ScraperSourceRepository` |
| `app/services/scraper/source_validation_service.py` | Crear | `SourceValidationService` |
| `app/api/routes/scraper_sources.py` | Crear | Router REST `/scraper-sources` |
| `app/api/routes/__init__.py` | Modificar | Registrar el router |
| `app/workers/tasks/scraper.py` | Modificar | Añadir `scrape_source_task` |
| `tests/fixtures/scraper_sources/serp_sample.html` | Crear | HTML de muestra para tests de extracción |
| `tests/unit/test_recipe_transforms.py` | Crear | Tests del motor de transforms |
| `tests/unit/test_recipe_extractor.py` | Crear | Tests del extractor |
| `tests/unit/test_generic_configurable_fetcher.py` | Crear | Tests del fetcher genérico |
| `tests/integration/test_scraper_source_repository.py` | Crear | Tests del repositorio |
| `tests/integration/test_source_validation_service.py` | Crear | Tests del servicio de validación |
| `tests/integration/test_resolve_fetcher.py` | Crear | Tests del resolver |
| `tests/api/test_scraper_sources_api.py` | Crear | Tests de los endpoints |

**Comandos:** todos los `pytest`/`alembic` se ejecutan desde `mt-pricing-backend/`.

---

## Task 1: Migración Alembic — enums + 3 tablas

**Files:**
- Create: `mt-pricing-backend/alembic/versions/20260602_145_scraper_sources.py`

- [ ] **Step 1: Escribir la migración**

```python
"""scraper_sources — motor de scraper configurable data-driven (Scraper Source Builder F1).

Revision ID: 20260602_145
Revises: 20260602_144
Create Date: 2026-05-20

Crea las tablas del módulo Scraper Source Builder:
- scraper_sources: definición configurable de un sitio a scrapear
- scraper_source_recipes: receta de extracción versionada (una is_live por source)
- scraper_source_test_runs: resultados de validación de recetas
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = "20260602_145"
down_revision = "20260602_144"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    destination_profile = postgresql.ENUM(
        "competitor_price", "product_data", name="scraper_destination_profile"
    )
    fetch_mode = postgresql.ENUM(
        "static", "headless", "stealth", name="scraper_fetch_mode"
    )
    source_status = postgresql.ENUM(
        "draft", "testing", "active", "disabled", "degraded",
        name="scraper_source_status",
    )
    validation_status = postgresql.ENUM(
        "unvalidated", "passing", "failing",
        name="scraper_recipe_validation_status",
    )
    destination_profile.create(bind, checkfirst=True)
    fetch_mode.create(bind, checkfirst=True)
    source_status.create(bind, checkfirst=True)
    validation_status.create(bind, checkfirst=True)

    op.create_table(
        "scraper_sources",
        sa.Column("id", sa.UUID(), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("name", sa.String(160), nullable=False),
        sa.Column("slug", sa.String(80), nullable=False),
        sa.Column("base_url", sa.Text(), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column(
            "destination_profile",
            postgresql.ENUM(name="scraper_destination_profile", create_type=False),
            nullable=False,
        ),
        sa.Column(
            "fetch_mode",
            postgresql.ENUM(name="scraper_fetch_mode", create_type=False),
            nullable=False,
            server_default=sa.text("'static'::scraper_fetch_mode"),
        ),
        sa.Column(
            "status",
            postgresql.ENUM(name="scraper_source_status", create_type=False),
            nullable=False,
            server_default=sa.text("'draft'::scraper_source_status"),
        ),
        sa.Column("competitor_brand_id", sa.UUID(), nullable=True),
        sa.Column("created_by", sa.UUID(), nullable=True),
        sa.Column("generated_by", sa.String(100), nullable=True),
        sa.Column("last_validated_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["competitor_brand_id"], ["competitor_brands.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["created_by"], ["users.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("slug", name="uq_scraper_sources_slug"),
    )

    op.create_table(
        "scraper_source_recipes",
        sa.Column("id", sa.UUID(), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("source_id", sa.UUID(), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("is_live", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("recipe", postgresql.JSONB(), nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column(
            "validation_status",
            postgresql.ENUM(name="scraper_recipe_validation_status", create_type=False),
            nullable=False,
            server_default=sa.text("'unvalidated'::scraper_recipe_validation_status"),
        ),
        sa.Column("has_unapproved_snippet", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("created_by", sa.UUID(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["source_id"], ["scraper_sources.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["created_by"], ["users.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("source_id", "version", name="uq_recipe_source_version"),
    )
    op.create_index(
        "uq_recipe_one_live_per_source",
        "scraper_source_recipes",
        ["source_id"],
        unique=True,
        postgresql_where=sa.text("is_live"),
    )

    op.create_table(
        "scraper_source_test_runs",
        sa.Column("id", sa.UUID(), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("source_id", sa.UUID(), nullable=False),
        sa.Column("recipe_id", sa.UUID(), nullable=False),
        sa.Column("test_url", sa.Text(), nullable=False),
        sa.Column("html_snapshot_ref", sa.Text(), nullable=True),
        sa.Column("extracted", postgresql.JSONB(), nullable=False, server_default=sa.text("'[]'::jsonb")),
        sa.Column("field_results", postgresql.JSONB(), nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["source_id"], ["scraper_sources.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["recipe_id"], ["scraper_source_recipes.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_source_test_runs_source", "scraper_source_test_runs", ["source_id", "created_at"]
    )


def downgrade() -> None:
    op.drop_index("ix_source_test_runs_source", table_name="scraper_source_test_runs")
    op.drop_table("scraper_source_test_runs")
    op.drop_index("uq_recipe_one_live_per_source", table_name="scraper_source_recipes")
    op.drop_table("scraper_source_recipes")
    op.drop_table("scraper_sources")
    for enum_name in (
        "scraper_recipe_validation_status",
        "scraper_source_status",
        "scraper_fetch_mode",
        "scraper_destination_profile",
    ):
        op.execute(f"DROP TYPE IF EXISTS {enum_name}")
```

- [ ] **Step 2: Aplicar la migración**

Run: `alembic upgrade head`
Expected: sin errores; salida termina en `Running upgrade 20260602_144 -> 20260602_145`.

- [ ] **Step 3: Verificar reversibilidad**

Run: `alembic downgrade -1 && alembic upgrade head`
Expected: el downgrade dropea las 3 tablas y los 4 tipos sin error; el upgrade las recrea. Sin excepciones.

- [ ] **Step 4: Commit**

```bash
git add alembic/versions/20260602_145_scraper_sources.py
git commit -m "feat(scraper): migración de tablas del Scraper Source Builder"
```

---

## Task 2: Modelos ORM

**Files:**
- Create: `mt-pricing-backend/app/db/models/scraper_sources.py`
- Modify: `mt-pricing-backend/app/db/models/__init__.py`
- Test: `mt-pricing-backend/tests/integration/test_scraper_source_repository.py` (solo el primer test aquí; el resto en Task 7)

- [ ] **Step 1: Escribir el test que falla**

Crear `tests/integration/test_scraper_source_repository.py`:

```python
import pytest

from app.db.models.scraper_sources import ScraperSource


@pytest.mark.integration
async def test_scraper_source_persists(db_session):
    source = ScraperSource(
        name="ACME Tools",
        slug="acme-tools",
        base_url="https://acme.example",
        destination_profile="competitor_price",
        fetch_mode="static",
        status="draft",
    )
    db_session.add(source)
    await db_session.flush()

    assert source.id is not None
    assert source.created_at is not None
    assert source.status == "draft"
```

- [ ] **Step 2: Correr el test para verificar que falla**

Run: `pytest tests/integration/test_scraper_source_repository.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'app.db.models.scraper_sources'`.

- [ ] **Step 3: Escribir los modelos**

Crear `app/db/models/scraper_sources.py`:

```python
"""Modelos del módulo Scraper Source Builder — motor de scraper configurable.

Ver docs/superpowers/specs/2026-05-20-scraper-source-builder-design.md
"""
from __future__ import annotations

from datetime import datetime
from typing import Any
from uuid import UUID

from sqlalchemy import (
    Boolean,
    DateTime,
    Enum,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base
from app.db.mixins import TimestampMixin, UuidPkMixin
from app.db.types import UUID_PG

_DESTINATION_PROFILE = Enum(
    "competitor_price", "product_data",
    name="scraper_destination_profile", create_type=False,
)
_FETCH_MODE = Enum(
    "static", "headless", "stealth",
    name="scraper_fetch_mode", create_type=False,
)
_SOURCE_STATUS = Enum(
    "draft", "testing", "active", "disabled", "degraded",
    name="scraper_source_status", create_type=False,
)
_VALIDATION_STATUS = Enum(
    "unvalidated", "passing", "failing",
    name="scraper_recipe_validation_status", create_type=False,
)


class ScraperSource(UuidPkMixin, TimestampMixin, Base):
    """Definición configurable y data-driven de un sitio a scrapear."""

    __tablename__ = "scraper_sources"

    name: Mapped[str] = mapped_column(String(160), nullable=False)
    slug: Mapped[str] = mapped_column(String(80), nullable=False)
    base_url: Mapped[str] = mapped_column(Text, nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    destination_profile: Mapped[str] = mapped_column(_DESTINATION_PROFILE, nullable=False)
    fetch_mode: Mapped[str] = mapped_column(
        _FETCH_MODE, nullable=False, server_default=text("'static'::scraper_fetch_mode")
    )
    status: Mapped[str] = mapped_column(
        _SOURCE_STATUS, nullable=False, server_default=text("'draft'::scraper_source_status")
    )
    competitor_brand_id: Mapped[UUID | None] = mapped_column(
        UUID_PG, ForeignKey("competitor_brands.id", ondelete="SET NULL"), nullable=True
    )
    created_by: Mapped[UUID | None] = mapped_column(
        UUID_PG, ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    generated_by: Mapped[str | None] = mapped_column(String(100), nullable=True)
    last_validated_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    __table_args__ = (UniqueConstraint("slug", name="uq_scraper_sources_slug"),)


class ScraperSourceRecipe(UuidPkMixin, Base):
    """Receta de extracción versionada. Una receta is_live por source."""

    __tablename__ = "scraper_source_recipes"

    source_id: Mapped[UUID] = mapped_column(
        UUID_PG, ForeignKey("scraper_sources.id", ondelete="CASCADE"), nullable=False
    )
    version: Mapped[int] = mapped_column(Integer, nullable=False)
    is_live: Mapped[bool] = mapped_column(
        Boolean, nullable=False, server_default=text("false")
    )
    recipe: Mapped[dict[str, Any]] = mapped_column(
        JSONB, nullable=False, server_default=text("'{}'::jsonb")
    )
    validation_status: Mapped[str] = mapped_column(
        _VALIDATION_STATUS,
        nullable=False,
        server_default=text("'unvalidated'::scraper_recipe_validation_status"),
    )
    has_unapproved_snippet: Mapped[bool] = mapped_column(
        Boolean, nullable=False, server_default=text("false")
    )
    created_by: Mapped[UUID | None] = mapped_column(
        UUID_PG, ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=text("now()")
    )

    __table_args__ = (
        UniqueConstraint("source_id", "version", name="uq_recipe_source_version"),
    )


class ScraperSourceTestRun(UuidPkMixin, Base):
    """Resultado de validar una receta contra una URL de muestra."""

    __tablename__ = "scraper_source_test_runs"

    source_id: Mapped[UUID] = mapped_column(
        UUID_PG, ForeignKey("scraper_sources.id", ondelete="CASCADE"), nullable=False
    )
    recipe_id: Mapped[UUID] = mapped_column(
        UUID_PG, ForeignKey("scraper_source_recipes.id", ondelete="CASCADE"), nullable=False
    )
    test_url: Mapped[str] = mapped_column(Text, nullable=False)
    html_snapshot_ref: Mapped[str | None] = mapped_column(Text, nullable=True)
    extracted: Mapped[list[dict[str, Any]]] = mapped_column(
        JSONB, nullable=False, server_default=text("'[]'::jsonb")
    )
    field_results: Mapped[dict[str, str]] = mapped_column(
        JSONB, nullable=False, server_default=text("'{}'::jsonb")
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=text("now()")
    )
```

- [ ] **Step 4: Registrar el módulo para Alembic/metadata**

Abrir `app/db/models/__init__.py` y, junto a los imports de modelos existentes (siguiendo el mismo estilo del archivo), añadir:

```python
from app.db.models.scraper_sources import (  # noqa: F401
    ScraperSource,
    ScraperSourceRecipe,
    ScraperSourceTestRun,
)
```

Si el archivo mantiene una lista `__all__`, añadir los tres nombres a esa lista.

- [ ] **Step 5: Correr el test para verificar que pasa**

Run: `pytest tests/integration/test_scraper_source_repository.py -v`
Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add app/db/models/scraper_sources.py app/db/models/__init__.py tests/integration/test_scraper_source_repository.py
git commit -m "feat(scraper): modelos ORM del Scraper Source Builder"
```

---

## Task 3: Schemas Pydantic de la receta

**Files:**
- Create: `mt-pricing-backend/app/schemas/scraper_sources.py`
- Test: `mt-pricing-backend/tests/unit/test_recipe_schema.py`

- [ ] **Step 1: Escribir el test que falla**

Crear `tests/unit/test_recipe_schema.py`:

```python
import pytest
from pydantic import ValidationError

from app.schemas.scraper_sources import Recipe


def test_valid_recipe_parses():
    recipe = Recipe.model_validate({
        "url_templates": {"search": "https://acme.example/s?q={query}"},
        "list_item_selector": "div.product",
        "fields": [
            {"name": "external_id", "selector": "a.pid", "extract": "attr:data-id"},
            {"name": "title", "selector": "h2.name", "extract": "text"},
            {"name": "price_aed", "selector": "span.price", "type": "currency"},
        ],
    })
    assert len(recipe.fields) == 3
    assert recipe.fields[0].extract == "attr:data-id"


def test_recipe_rejects_empty_fields():
    with pytest.raises(ValidationError):
        Recipe.model_validate({
            "url_templates": {"search": "https://acme.example/s?q={query}"},
            "fields": [],
        })


def test_field_rejects_invalid_extract():
    with pytest.raises(ValidationError):
        Recipe.model_validate({
            "url_templates": {"search": "https://acme.example/s?q={query}"},
            "fields": [{"name": "title", "selector": "h2", "extract": "bogus"}],
        })
```

- [ ] **Step 2: Correr el test para verificar que falla**

Run: `pytest tests/unit/test_recipe_schema.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'app.schemas.scraper_sources'`.

- [ ] **Step 3: Escribir los schemas**

Crear `app/schemas/scraper_sources.py`:

```python
"""Schemas Pydantic del módulo Scraper Source Builder.

Bloque 1: estructura de la receta (validación del JSONB).
Bloque 2 (Task 10): schemas request/response de la API.
"""
from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field, field_validator


class RecipeTransform(BaseModel):
    """Transform declarativo de un field. Snippets LLM no entran en F1."""

    op: Literal["regex_capture", "strip_currency", "replace", "map_values", "unit_factor"]
    pattern: str | None = None
    find: str | None = None
    replace_with: str | None = None
    mapping: dict[str, str] | None = None
    factor: float | None = None


class RecipeField(BaseModel):
    name: str = Field(min_length=1, max_length=64)
    selector: str = Field(min_length=1)
    extract: str = Field(default="text")
    type: Literal["str", "float", "int", "currency", "bool"] = "str"
    transform: RecipeTransform | None = None

    @field_validator("extract")
    @classmethod
    def _valid_extract(cls, v: str) -> str:
        if v in ("text", "html") or v.startswith("attr:"):
            return v
        raise ValueError("extract debe ser 'text', 'html', o 'attr:<nombre>'")


class RecipeUrlTemplates(BaseModel):
    search: str | None = None
    pdp: str | None = None
    list: str | None = None
    product: str | None = None


class RecipePagination(BaseModel):
    next_selector: str | None = None
    max_pages: int = Field(default=1, ge=1, le=50)


class Recipe(BaseModel):
    url_templates: RecipeUrlTemplates
    list_item_selector: str | None = None
    pagination: RecipePagination | None = None
    fields: list[RecipeField] = Field(min_length=1)
    anti_bot_hints: dict[str, Any] = Field(default_factory=dict)
```

- [ ] **Step 4: Correr el test para verificar que pasa**

Run: `pytest tests/unit/test_recipe_schema.py -v`
Expected: PASS (3 tests).

- [ ] **Step 5: Commit**

```bash
git add app/schemas/scraper_sources.py tests/unit/test_recipe_schema.py
git commit -m "feat(scraper): schema Pydantic de la receta de extracción"
```

---

## Task 4: Motor de transforms declarativos

**Files:**
- Create: `mt-pricing-backend/app/services/scraper/recipe_transforms.py`
- Test: `mt-pricing-backend/tests/unit/test_recipe_transforms.py`

- [ ] **Step 1: Escribir el test que falla**

Crear `tests/unit/test_recipe_transforms.py`:

```python
import pytest

from app.services.scraper.recipe_transforms import apply_transform


def test_none_transform_is_identity():
    assert apply_transform(None, "  hola ") == "  hola "


def test_regex_capture_returns_group_one():
    t = {"op": "regex_capture", "pattern": r"ASIN:\s*(\w+)"}
    assert apply_transform(t, "ASIN: B0CXYZ123 end") == "B0CXYZ123"


def test_regex_capture_no_match_returns_empty():
    t = {"op": "regex_capture", "pattern": r"(\d{4})"}
    assert apply_transform(t, "sin numeros") == ""


def test_strip_currency_keeps_digits():
    t = {"op": "strip_currency"}
    assert apply_transform(t, "AED 1,234.50") == "1234.50"


def test_replace():
    t = {"op": "replace", "find": " AED", "replace_with": ""}
    assert apply_transform(t, "99 AED") == "99"


def test_map_values():
    t = {"op": "map_values", "mapping": {"In Stock": "true", "Out": "false"}}
    assert apply_transform(t, "In Stock") == "true"
    assert apply_transform(t, "Desconocido") == "Desconocido"


def test_unit_factor_multiplies():
    t = {"op": "unit_factor", "factor": 0.0689476}
    assert float(apply_transform(t, "100 PSI")) == pytest.approx(6.89476)


def test_unknown_op_raises():
    with pytest.raises(ValueError, match="Unknown transform op"):
        apply_transform({"op": "nuke"}, "x")
```

- [ ] **Step 2: Correr el test para verificar que falla**

Run: `pytest tests/unit/test_recipe_transforms.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'app.services.scraper.recipe_transforms'`.

- [ ] **Step 3: Escribir el motor de transforms**

Crear `app/services/scraper/recipe_transforms.py`:

```python
"""Motor de transforms declarativos para recetas de scraper.

Cada transform es una operación pura y segura sobre un valor de texto extraído.
El escape hatch de snippets generados por LLM (híbrido B) NO está aquí — llega
en una fase posterior con su sandbox dedicado.
"""
from __future__ import annotations

import re
from typing import Any

_NUMERIC_RE = re.compile(r"[^0-9.\-]")


def _to_number(value: str) -> float:
    return float(_NUMERIC_RE.sub("", value.replace(",", "")))


def apply_transform(transform: dict[str, Any] | None, value: str) -> str:
    """Aplica un transform declarativo a un valor de texto. None = identidad."""
    if transform is None:
        return value
    op = transform.get("op")
    if op == "regex_capture":
        match = re.search(transform["pattern"], value)
        if match is None:
            return ""
        return match.group(1) if match.groups() else match.group(0)
    if op == "strip_currency":
        return _NUMERIC_RE.sub("", value.replace(",", ""))
    if op == "replace":
        return value.replace(transform["find"], transform.get("replace_with", ""))
    if op == "map_values":
        return transform.get("mapping", {}).get(value, value)
    if op == "unit_factor":
        try:
            return str(_to_number(value) * float(transform["factor"]))
        except (ValueError, TypeError):
            return ""
    raise ValueError(f"Unknown transform op: {op!r}")
```

- [ ] **Step 4: Correr el test para verificar que pasa**

Run: `pytest tests/unit/test_recipe_transforms.py -v`
Expected: PASS (8 tests).

- [ ] **Step 5: Commit**

```bash
git add app/services/scraper/recipe_transforms.py tests/unit/test_recipe_transforms.py
git commit -m "feat(scraper): motor de transforms declarativos de recetas"
```

---

## Task 5: Extractor de recetas (selectolax)

**Files:**
- Create: `mt-pricing-backend/app/services/scraper/recipe_extractor.py`
- Create: `mt-pricing-backend/tests/fixtures/scraper_sources/serp_sample.html`
- Test: `mt-pricing-backend/tests/unit/test_recipe_extractor.py`

- [ ] **Step 1: Crear el fixture HTML**

Crear `tests/fixtures/scraper_sources/serp_sample.html`:

```html
<!doctype html>
<html>
<body>
  <div class="results">
    <div class="product" data-id="P-1001">
      <h2 class="name">Bola de acero inox 1/2"</h2>
      <span class="price">AED 1,250.00</span>
      <span class="brand">ACME</span>
      <span class="stock">In Stock</span>
    </div>
    <div class="product" data-id="P-1002">
      <h2 class="name">Valvula compuerta DN50</h2>
      <span class="price">AED 980.00</span>
      <span class="brand">ACME</span>
      <span class="stock">Out</span>
    </div>
  </div>
</body>
</html>
```

- [ ] **Step 2: Escribir el test que falla**

Crear `tests/unit/test_recipe_extractor.py`:

```python
from pathlib import Path

from app.services.scraper.recipe_extractor import extract_records, field_results

_FIXTURE = Path(__file__).parent.parent / "fixtures" / "scraper_sources" / "serp_sample.html"

_RECIPE = {
    "url_templates": {"search": "https://acme.example/s?q={query}"},
    "list_item_selector": "div.product",
    "fields": [
        {"name": "external_id", "selector": "h2.name", "extract": "text"},
        {"name": "title", "selector": "h2.name", "extract": "text"},
        {"name": "brand", "selector": "span.brand", "extract": "text"},
        {"name": "price_aed", "selector": "span.price", "type": "currency"},
        {"name": "in_stock", "selector": "span.stock", "type": "bool",
         "transform": {"op": "map_values", "mapping": {"In Stock": "true", "Out": "false"}}},
        {"name": "missing", "selector": "span.does-not-exist", "extract": "text"},
    ],
}


def test_extract_records_one_per_item():
    html = _FIXTURE.read_text(encoding="utf-8")
    records = extract_records(html, _RECIPE)
    assert len(records) == 2


def test_extract_records_field_values():
    html = _FIXTURE.read_text(encoding="utf-8")
    records = extract_records(html, _RECIPE)
    first = records[0]
    assert first["title"] == 'Bola de acero inox 1/2"'
    assert first["brand"] == "ACME"
    assert first["price_aed"] == 1250.0
    assert first["in_stock"] is True
    assert records[1]["in_stock"] is False
    assert first["missing"] is None


def test_extract_attr():
    recipe = {
        "url_templates": {"search": "x"},
        "list_item_selector": "div.product",
        "fields": [{"name": "external_id", "selector": "div.product", "extract": "attr:data-id"}],
    }
    # selector relativo al item: el propio nodo no se re-selecciona, usamos un hijo
    html = _FIXTURE.read_text(encoding="utf-8")
    recipe["fields"][0]["selector"] = "h2.name"
    records = extract_records(html, recipe)
    assert records[0]["external_id"] == 'Bola de acero inox 1/2"'


def test_field_results_pass_fail():
    html = _FIXTURE.read_text(encoding="utf-8")
    records = extract_records(html, _RECIPE)
    results = field_results(records, _RECIPE)
    assert results["title"] == "pass"
    assert results["missing"] == "fail"
```

- [ ] **Step 3: Correr el test para verificar que falla**

Run: `pytest tests/unit/test_recipe_extractor.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'app.services.scraper.recipe_extractor'`.

- [ ] **Step 4: Escribir el extractor**

Crear `app/services/scraper/recipe_extractor.py`:

```python
"""Aplica una receta de extracción a un documento HTML usando selectores CSS.

F1 soporta selectores CSS (via selectolax). XPath queda para una fase posterior.
"""
from __future__ import annotations

import re
from typing import Any

from selectolax.parser import HTMLParser

from app.services.scraper.recipe_transforms import apply_transform

_CURRENCY_RE = re.compile(r"[^0-9.]")
_TRUTHY = {"true", "1", "yes", "in stock", "available", "disponible"}


def coerce_type(value: str | None, type_: str) -> Any:
    """Convierte un valor de texto al tipo canónico. Devuelve None si no puede."""
    if value is None:
        return None
    if type_ == "str":
        return value
    text_ = value.strip()
    try:
        if type_ == "float":
            return float(text_)
        if type_ == "int":
            return int(float(text_))
        if type_ == "currency":
            cleaned = _CURRENCY_RE.sub("", text_)
            return float(cleaned) if cleaned else None
        if type_ == "bool":
            return text_.lower() in _TRUTHY
    except (ValueError, TypeError):
        return None
    return value


def _extract_field(node: Any, field: dict[str, Any]) -> Any:
    target = node.css_first(field["selector"])
    if target is None:
        return None
    extract = field.get("extract", "text")
    if extract == "html":
        raw = target.html
    elif extract.startswith("attr:"):
        raw = target.attributes.get(extract.split(":", 1)[1])
    else:
        raw = target.text(strip=True)
    if raw is None:
        return None
    raw = apply_transform(field.get("transform"), raw)
    return coerce_type(raw, field.get("type", "str"))


def extract_records(html: str, recipe: dict[str, Any]) -> list[dict[str, Any]]:
    """Extrae registros de un HTML según la receta.

    Con ``list_item_selector`` produce un registro por nodo coincidente; sin él,
    un único registro tomado del documento entero. Cada registro es un dict
    ``{field_name: valor_o_None}``.
    """
    tree = HTMLParser(html)
    fields = recipe.get("fields", [])
    list_sel = recipe.get("list_item_selector")
    if list_sel:
        items = tree.css(list_sel)
    else:
        root = tree.body if tree.body is not None else tree.root
        items = [root] if root is not None else []
    records: list[dict[str, Any]] = []
    for item in items:
        records.append({f["name"]: _extract_field(item, f) for f in fields})
    return records


def field_results(records: list[dict[str, Any]], recipe: dict[str, Any]) -> dict[str, str]:
    """pass/fail por field — 'pass' si el field es no-nulo/no-vacío en >=1 registro."""
    results: dict[str, str] = {}
    for f in recipe.get("fields", []):
        name = f["name"]
        ok = any(r.get(name) not in (None, "") for r in records)
        results[name] = "pass" if ok else "fail"
    return results
```

- [ ] **Step 5: Correr el test para verificar que pasa**

Run: `pytest tests/unit/test_recipe_extractor.py -v`
Expected: PASS (4 tests).

- [ ] **Step 6: Commit**

```bash
git add app/services/scraper/recipe_extractor.py tests/fixtures/scraper_sources/serp_sample.html tests/unit/test_recipe_extractor.py
git commit -m "feat(scraper): extractor de recetas con selectores CSS"
```

---

## Task 6: GenericConfigurableFetcher

**Files:**
- Create: `mt-pricing-backend/app/services/matching/adapters/generic_configurable.py`
- Test: `mt-pricing-backend/tests/unit/test_generic_configurable_fetcher.py`

- [ ] **Step 1: Escribir el test que falla**

Crear `tests/unit/test_generic_configurable_fetcher.py`:

```python
from pathlib import Path
from types import SimpleNamespace

import pytest

from app.services.matching.adapters.generic_configurable import GenericConfigurableFetcher
from app.services.matching.ports import Query

_FIXTURE = Path(__file__).parent.parent / "fixtures" / "scraper_sources" / "serp_sample.html"

_RECIPE = {
    "url_templates": {"search": "https://acme.example/s?q={query}"},
    "list_item_selector": "div.product",
    "fields": [
        {"name": "external_id", "selector": "h2.name", "extract": "text"},
        {"name": "title", "selector": "h2.name", "extract": "text"},
        {"name": "brand", "selector": "span.brand", "extract": "text"},
        {"name": "price_aed", "selector": "span.price", "type": "currency"},
        {"name": "stock", "selector": "span.stock", "extract": "text"},
    ],
}


def _source(fetch_mode="static"):
    return SimpleNamespace(slug="acme-tools", fetch_mode=fetch_mode)


async def test_fetch_maps_records_to_candidate_raw():
    html = _FIXTURE.read_text(encoding="utf-8")

    async def fake_fetch(url: str) -> str:
        assert url == "https://acme.example/s?q=valvula"
        return html

    fetcher = GenericConfigurableFetcher(_source(), _RECIPE, html_fetcher=fake_fetch)
    out = await fetcher.fetch(Query(text="valvula", source="acme-tools"))

    assert fetcher.channel == "acme-tools"
    assert len(out) == 2
    first = out[0]
    assert first.source == "acme-tools"
    assert first.title == 'Bola de acero inox 1/2"'
    assert str(first.price_aed) == "1250.0"
    assert first.brand == "ACME"
    assert first.specs["stock"] == "In Stock"


async def test_non_static_fetch_mode_raises():
    with pytest.raises(NotImplementedError, match="headless"):
        GenericConfigurableFetcher(_source(fetch_mode="headless"), _RECIPE)
```

- [ ] **Step 2: Correr el test para verificar que falla**

Run: `pytest tests/unit/test_generic_configurable_fetcher.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'app.services.matching.adapters.generic_configurable'`.

- [ ] **Step 3: Escribir el fetcher**

Crear `app/services/matching/adapters/generic_configurable.py`:

```python
"""Fetcher genérico data-driven — ejecuta la receta de un ScraperSource.

Implementa el FetcherPort existente. F1 soporta el modo de fetch 'static'
(curl_cffi). Los modos 'headless'/'stealth' se implementan en una fase posterior:
construir un fetcher para esos modos lanza NotImplementedError.
"""
from __future__ import annotations

import os
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation
from typing import Any, Awaitable, Callable

from app.services.matching.ports import CandidateRaw, Query
from app.services.scraper.recipe_extractor import extract_records

HtmlFetcher = Callable[[str], Awaitable[str]]

_CANONICAL_FIELDS = {"external_id", "title", "brand", "price_aed", "delivery_text"}
_BASE_HEADERS = {
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-AE,en;q=0.9,ar;q=0.8",
}


async def _curl_cffi_fetch(url: str) -> str:
    from curl_cffi.requests import AsyncSession

    impersonate = os.environ.get("SCRAPER_IMPERSONATE", "chrome124")
    timeout = int(os.environ.get("SCRAPER_TIMEOUT", "30"))
    async with AsyncSession(
        impersonate=impersonate, headers=_BASE_HEADERS, timeout=timeout
    ) as session:
        resp = await session.get(url)
        return resp.text


class GenericConfigurableFetcher:
    """FetcherPort que ejecuta una receta data-driven contra un sitio configurado."""

    def __init__(
        self,
        source: Any,
        recipe: dict[str, Any],
        *,
        html_fetcher: HtmlFetcher | None = None,
    ) -> None:
        self._source = source
        self._recipe = recipe
        if html_fetcher is not None:
            self._html_fetcher: HtmlFetcher = html_fetcher
        elif source.fetch_mode == "static":
            self._html_fetcher = _curl_cffi_fetch
        else:
            raise NotImplementedError(
                f"fetch_mode {source.fetch_mode!r} no soportado en F1 — solo 'static'"
            )

    @property
    def channel(self) -> str:
        return self._source.slug

    def _build_url(self, query: Query) -> str:
        templates = self._recipe.get("url_templates", {})
        template = templates.get("search") or templates.get("list")
        if not template:
            raise ValueError("recipe.url_templates no define 'search' ni 'list'")
        return template.replace("{query}", query.text)

    async def fetch(self, query: Query, *, sku: str | None = None) -> list[CandidateRaw]:
        url = self._build_url(query)
        html = await self._html_fetcher(url)
        records = extract_records(html, self._recipe)
        out: list[CandidateRaw] = []
        for record in records:
            if not record.get("external_id") or not record.get("title"):
                continue
            out.append(self._to_candidate(record))
        return out

    def _to_candidate(self, record: dict[str, Any]) -> CandidateRaw:
        price_aed: Decimal | None = None
        price_raw = record.get("price_aed")
        if price_raw is not None:
            try:
                price_aed = Decimal(str(price_raw))
            except (InvalidOperation, ValueError):
                price_aed = None
        specs = {
            k: v
            for k, v in record.items()
            if k not in _CANONICAL_FIELDS and v is not None
        }
        return CandidateRaw(
            source=self.channel,
            external_id=str(record["external_id"]),
            title=str(record["title"]),
            brand=record.get("brand"),
            price_aed=price_aed,
            delivery_text=record.get("delivery_text"),
            specs=specs,
            raw_payload={"recipe_source": self.channel, "extracted": record},
            fetched_at=datetime.now(tz=timezone.utc),
        )
```

- [ ] **Step 4: Correr el test para verificar que pasa**

Run: `pytest tests/unit/test_generic_configurable_fetcher.py -v`
Expected: PASS (2 tests).

- [ ] **Step 5: Commit**

```bash
git add app/services/matching/adapters/generic_configurable.py tests/unit/test_generic_configurable_fetcher.py
git commit -m "feat(scraper): GenericConfigurableFetcher data-driven"
```

---

## Task 7: ScraperSourceRepository

**Files:**
- Create: `mt-pricing-backend/app/repositories/scraper_sources.py`
- Test: `mt-pricing-backend/tests/integration/test_scraper_source_repository.py` (añadir tests al archivo creado en Task 2)

- [ ] **Step 1: Escribir los tests que fallan**

Añadir al final de `tests/integration/test_scraper_source_repository.py`:

```python
from app.repositories.scraper_sources import ScraperSourceRepository

_RECIPE_A = {"url_templates": {"search": "x"}, "fields": [{"name": "title", "selector": "h2"}]}
_RECIPE_B = {"url_templates": {"search": "y"}, "fields": [{"name": "title", "selector": "h3"}]}


async def _make_source(repo: ScraperSourceRepository, slug: str = "acme") -> "object":
    return await repo.create(
        name="ACME", slug=slug, base_url="https://acme.example",
        destination_profile="competitor_price",
    )


@pytest.mark.integration
async def test_repo_create_and_get_by_slug(db_session):
    repo = ScraperSourceRepository(db_session)
    source = await _make_source(repo, "acme-1")
    fetched = await repo.get_by_slug("acme-1")
    assert fetched is not None
    assert fetched.id == source.id


@pytest.mark.integration
async def test_repo_add_recipe_increments_version(db_session):
    repo = ScraperSourceRepository(db_session)
    source = await _make_source(repo, "acme-2")
    r1 = await repo.add_recipe(source.id, _RECIPE_A)
    r2 = await repo.add_recipe(source.id, _RECIPE_B)
    assert r1.version == 1
    assert r2.version == 2


@pytest.mark.integration
async def test_repo_set_recipe_live_is_exclusive(db_session):
    repo = ScraperSourceRepository(db_session)
    source = await _make_source(repo, "acme-3")
    r1 = await repo.add_recipe(source.id, _RECIPE_A)
    r2 = await repo.add_recipe(source.id, _RECIPE_B)
    await repo.set_recipe_live(r1.id)
    await repo.set_recipe_live(r2.id)
    live = await repo.get_live_recipe(source.id)
    assert live is not None
    assert live.id == r2.id
```

- [ ] **Step 2: Correr los tests para verificar que fallan**

Run: `pytest tests/integration/test_scraper_source_repository.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'app.repositories.scraper_sources'`.

- [ ] **Step 3: Escribir el repositorio**

Crear `app/repositories/scraper_sources.py`:

```python
"""Repositorio de ScraperSource y sus recetas versionadas."""
from __future__ import annotations

from typing import Any
from uuid import UUID

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.scraper_sources import (
    ScraperSource,
    ScraperSourceRecipe,
    ScraperSourceTestRun,
)


class ScraperSourceRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def create(
        self,
        *,
        name: str,
        slug: str,
        base_url: str,
        destination_profile: str,
        fetch_mode: str = "static",
        description: str | None = None,
        competitor_brand_id: UUID | None = None,
        created_by: UUID | None = None,
    ) -> ScraperSource:
        source = ScraperSource(
            name=name,
            slug=slug,
            base_url=base_url,
            destination_profile=destination_profile,
            fetch_mode=fetch_mode,
            description=description,
            competitor_brand_id=competitor_brand_id,
            created_by=created_by,
            status="draft",
        )
        self._session.add(source)
        await self._session.flush()
        return source

    async def get(self, source_id: UUID) -> ScraperSource | None:
        return await self._session.get(ScraperSource, source_id)

    async def get_by_slug(self, slug: str) -> ScraperSource | None:
        result = await self._session.execute(
            select(ScraperSource).where(ScraperSource.slug == slug)
        )
        return result.scalar_one_or_none()

    async def list_all(self) -> list[ScraperSource]:
        result = await self._session.execute(
            select(ScraperSource).order_by(ScraperSource.created_at.desc())
        )
        return list(result.scalars().all())

    async def add_recipe(
        self, source_id: UUID, recipe: dict[str, Any], *, created_by: UUID | None = None
    ) -> ScraperSourceRecipe:
        result = await self._session.execute(
            select(ScraperSourceRecipe.version)
            .where(ScraperSourceRecipe.source_id == source_id)
            .order_by(ScraperSourceRecipe.version.desc())
            .limit(1)
        )
        last_version = result.scalar_one_or_none()
        row = ScraperSourceRecipe(
            source_id=source_id,
            version=(last_version or 0) + 1,
            recipe=recipe,
            created_by=created_by,
        )
        self._session.add(row)
        await self._session.flush()
        return row

    async def get_recipe(self, recipe_id: UUID) -> ScraperSourceRecipe | None:
        return await self._session.get(ScraperSourceRecipe, recipe_id)

    async def get_live_recipe(self, source_id: UUID) -> ScraperSourceRecipe | None:
        result = await self._session.execute(
            select(ScraperSourceRecipe).where(
                ScraperSourceRecipe.source_id == source_id,
                ScraperSourceRecipe.is_live.is_(True),
            )
        )
        return result.scalar_one_or_none()

    async def set_recipe_live(self, recipe_id: UUID) -> None:
        recipe = await self._session.get(ScraperSourceRecipe, recipe_id)
        if recipe is None:
            raise ValueError(f"recipe {recipe_id} not found")
        await self._session.execute(
            update(ScraperSourceRecipe)
            .where(
                ScraperSourceRecipe.source_id == recipe.source_id,
                ScraperSourceRecipe.is_live.is_(True),
            )
            .values(is_live=False)
        )
        await self._session.flush()
        recipe.is_live = True
        await self._session.flush()

    async def record_test_run(
        self,
        *,
        source_id: UUID,
        recipe_id: UUID,
        test_url: str,
        extracted: list[dict[str, Any]],
        field_results: dict[str, str],
        html_snapshot_ref: str | None = None,
    ) -> ScraperSourceTestRun:
        run = ScraperSourceTestRun(
            source_id=source_id,
            recipe_id=recipe_id,
            test_url=test_url,
            extracted=extracted,
            field_results=field_results,
            html_snapshot_ref=html_snapshot_ref,
        )
        self._session.add(run)
        await self._session.flush()
        return run
```

- [ ] **Step 4: Correr los tests para verificar que pasan**

Run: `pytest tests/integration/test_scraper_source_repository.py -v`
Expected: PASS (4 tests, incluido el de Task 2).

- [ ] **Step 5: Commit**

```bash
git add app/repositories/scraper_sources.py tests/integration/test_scraper_source_repository.py
git commit -m "feat(scraper): repositorio de ScraperSource y recetas"
```

---

## Task 8: SourceValidationService

**Files:**
- Create: `mt-pricing-backend/app/services/scraper/source_validation_service.py`
- Test: `mt-pricing-backend/tests/integration/test_source_validation_service.py`

- [ ] **Step 1: Escribir el test que falla**

Crear `tests/integration/test_source_validation_service.py`:

```python
from pathlib import Path

import pytest
from sqlalchemy import select

from app.db.models.scraper_sources import ScraperSourceTestRun
from app.repositories.scraper_sources import ScraperSourceRepository
from app.services.scraper.source_validation_service import SourceValidationService

_FIXTURE = Path(__file__).parent.parent / "fixtures" / "scraper_sources" / "serp_sample.html"

_RECIPE = {
    "url_templates": {"search": "https://acme.example/s?q={query}"},
    "list_item_selector": "div.product",
    "fields": [
        {"name": "external_id", "selector": "h2.name", "extract": "text"},
        {"name": "title", "selector": "h2.name", "extract": "text"},
        {"name": "missing", "selector": "span.nope", "extract": "text"},
    ],
}


@pytest.mark.integration
async def test_validate_records_and_persists_test_run(db_session):
    repo = ScraperSourceRepository(db_session)
    source = await repo.create(
        name="ACME", slug="acme-val", base_url="https://acme.example",
        destination_profile="competitor_price",
    )
    recipe_row = await repo.add_recipe(source.id, _RECIPE)

    html = _FIXTURE.read_text(encoding="utf-8")

    async def fake_fetch(url: str) -> str:
        return html

    service = SourceValidationService(db_session)
    result = await service.validate(
        source.id, recipe_row.id, "https://acme.example/s?q=valvula",
        html_fetcher=fake_fetch,
    )

    assert len(result["records"]) == 2
    assert result["field_results"]["title"] == "pass"
    assert result["field_results"]["missing"] == "fail"
    assert result["status"] == "failing"

    refreshed = await repo.get_recipe(recipe_row.id)
    assert refreshed.validation_status == "failing"

    runs = (
        await db_session.execute(
            select(ScraperSourceTestRun).where(ScraperSourceTestRun.source_id == source.id)
        )
    ).scalars().all()
    assert len(runs) == 1
```

- [ ] **Step 2: Correr el test para verificar que falla**

Run: `pytest tests/integration/test_source_validation_service.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'app.services.scraper.source_validation_service'`.

- [ ] **Step 3: Escribir el servicio**

Crear `app/services/scraper/source_validation_service.py`:

```python
"""Servicio de validación de recetas — corre una receta contra una URL de muestra
y registra el resultado por field."""
from __future__ import annotations

from typing import Any, Awaitable, Callable
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.repositories.scraper_sources import ScraperSourceRepository
from app.services.scraper.recipe_extractor import extract_records, field_results

HtmlFetcher = Callable[[str], Awaitable[str]]


class SourceValidationService:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session
        self._repo = ScraperSourceRepository(session)

    async def validate(
        self,
        source_id: UUID,
        recipe_id: UUID,
        test_url: str,
        *,
        html_fetcher: HtmlFetcher,
    ) -> dict[str, Any]:
        """Corre la receta contra ``test_url``, persiste un test run y actualiza
        el ``validation_status`` de la receta. Devuelve records + field_results."""
        recipe_row = await self._repo.get_recipe(recipe_id)
        if recipe_row is None:
            raise ValueError(f"recipe {recipe_id} not found")

        html = await html_fetcher(test_url)
        records = extract_records(html, recipe_row.recipe)
        results = field_results(records, recipe_row.recipe)

        await self._repo.record_test_run(
            source_id=source_id,
            recipe_id=recipe_id,
            test_url=test_url,
            extracted=records,
            field_results=results,
        )

        all_pass = bool(results) and all(v == "pass" for v in results.values())
        recipe_row.validation_status = "passing" if all_pass else "failing"
        await self._session.flush()

        return {
            "records": records,
            "field_results": results,
            "status": recipe_row.validation_status,
        }
```

- [ ] **Step 4: Correr el test para verificar que pasa**

Run: `pytest tests/integration/test_source_validation_service.py -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add app/services/scraper/source_validation_service.py tests/integration/test_source_validation_service.py
git commit -m "feat(scraper): servicio de validación de recetas"
```

---

## Task 9: resolve_fetcher en adapter_registry

**Files:**
- Modify: `mt-pricing-backend/app/services/matching/adapter_registry.py`
- Test: `mt-pricing-backend/tests/integration/test_resolve_fetcher.py`

- [ ] **Step 1: Escribir el test que falla**

Crear `tests/integration/test_resolve_fetcher.py`:

```python
import pytest

from app.repositories.scraper_sources import ScraperSourceRepository
from app.services.matching.adapter_registry import resolve_fetcher
from app.services.matching.adapters.generic_configurable import GenericConfigurableFetcher

_RECIPE = {
    "url_templates": {"search": "https://acme.example/s?q={query}"},
    "list_item_selector": "div.product",
    "fields": [{"name": "title", "selector": "h2.name"}],
}


@pytest.mark.integration
async def test_resolve_hardcoded_channel_returns_existing(db_session):
    fetcher = await resolve_fetcher("amazon_uae", db_session)
    assert fetcher.channel == "amazon_uae"


@pytest.mark.integration
async def test_resolve_source_slug_returns_generic(db_session):
    repo = ScraperSourceRepository(db_session)
    source = await repo.create(
        name="ACME", slug="acme-resolve", base_url="https://acme.example",
        destination_profile="competitor_price",
    )
    recipe_row = await repo.add_recipe(source.id, _RECIPE)
    await repo.set_recipe_live(recipe_row.id)
    source.status = "active"
    await db_session.flush()

    fetcher = await resolve_fetcher("acme-resolve", db_session)
    assert isinstance(fetcher, GenericConfigurableFetcher)
    assert fetcher.channel == "acme-resolve"


@pytest.mark.integration
async def test_resolve_unknown_channel_raises(db_session):
    with pytest.raises(ValueError, match="Unknown matching channel"):
        await resolve_fetcher("does-not-exist", db_session)
```

- [ ] **Step 2: Correr el test para verificar que falla**

Run: `pytest tests/integration/test_resolve_fetcher.py -v`
Expected: FAIL — `ImportError: cannot import name 'resolve_fetcher'`.

- [ ] **Step 3: Añadir `resolve_fetcher` al registry**

En `app/services/matching/adapter_registry.py`, añadir al final del archivo:

```python
async def resolve_fetcher(
    channel: str,
    session: "AsyncSession",
    *,
    html_fetcher: "HtmlFetcher | None" = None,
) -> "FetcherPort":
    """Resuelve un canal a un fetcher.

    Canales hardcodeados (``SUPPORTED_CHANNELS``) delegan en ``get_fetcher()``.
    Cualquier otro canal se interpreta como el ``slug`` de un ``ScraperSource``:
    si existe y está ``active``/``testing`` con receta ``is_live``, devuelve un
    ``GenericConfigurableFetcher``.

    Raises:
        ValueError: canal desconocido o source sin receta live.
    """
    from app.services.matching.ports import SUPPORTED_CHANNELS

    if channel in SUPPORTED_CHANNELS:
        return get_fetcher(channel)

    from app.repositories.scraper_sources import ScraperSourceRepository
    from app.services.matching.adapters.generic_configurable import (
        GenericConfigurableFetcher,
    )

    repo = ScraperSourceRepository(session)
    source = await repo.get_by_slug(channel)
    if source is None or source.status not in ("active", "testing"):
        raise ValueError(f"Unknown matching channel: {channel!r}")
    live = await repo.get_live_recipe(source.id)
    if live is None:
        raise ValueError(f"Source {channel!r} has no live recipe")
    return GenericConfigurableFetcher(source, live.recipe, html_fetcher=html_fetcher)
```

Y añadir al bloque `if TYPE_CHECKING:` del inicio del archivo:

```python
    from collections.abc import Awaitable, Callable

    from sqlalchemy.ext.asyncio import AsyncSession

    HtmlFetcher = Callable[[str], Awaitable[str]]
```

- [ ] **Step 4: Correr el test para verificar que pasa**

Run: `pytest tests/integration/test_resolve_fetcher.py -v`
Expected: PASS (3 tests).

- [ ] **Step 5: Verificar que no hay regresión en el registry**

Run: `pytest tests/ -k "adapter_registry or get_fetcher" -v`
Expected: PASS — los tests existentes de `get_fetcher` siguen verdes (no se modificó la función).

- [ ] **Step 6: Commit**

```bash
git add app/services/matching/adapter_registry.py tests/integration/test_resolve_fetcher.py
git commit -m "feat(scraper): resolve_fetcher con fallback a sources configurables"
```

---

## Task 10: Router REST de scraper-sources

**Files:**
- Modify: `mt-pricing-backend/app/schemas/scraper_sources.py` (añadir schemas de API)
- Create: `mt-pricing-backend/app/api/routes/scraper_sources.py`
- Modify: `mt-pricing-backend/app/api/routes/__init__.py`
- Test: `mt-pricing-backend/tests/api/test_scraper_sources_api.py`

- [ ] **Step 1: Añadir schemas de API**

Añadir al final de `app/schemas/scraper_sources.py`:

```python
from datetime import datetime  # noqa: E402
from uuid import UUID  # noqa: E402


class ScraperSourceCreate(BaseModel):
    name: str = Field(min_length=1, max_length=160)
    slug: str = Field(min_length=1, max_length=80, pattern=r"^[a-z0-9-]+$")
    base_url: str = Field(min_length=1)
    destination_profile: Literal["competitor_price", "product_data"]
    fetch_mode: Literal["static", "headless", "stealth"] = "static"
    description: str | None = None
    competitor_brand_id: UUID | None = None


class ScraperSourceRead(BaseModel):
    id: UUID
    name: str
    slug: str
    base_url: str
    description: str | None
    destination_profile: str
    fetch_mode: str
    status: str
    competitor_brand_id: UUID | None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class RecipeSubmit(BaseModel):
    """Receta enviada por el cliente — se valida contra el schema Recipe."""

    recipe: Recipe


class RecipeRead(BaseModel):
    id: UUID
    source_id: UUID
    version: int
    is_live: bool
    validation_status: str
    has_unapproved_snippet: bool
    recipe: dict[str, Any]

    model_config = {"from_attributes": True}


class ValidateRequest(BaseModel):
    recipe_id: UUID
    test_url: str = Field(min_length=1)


class ValidateResponse(BaseModel):
    status: str
    field_results: dict[str, str]
    records: list[dict[str, Any]]
```

- [ ] **Step 2: Escribir el test que falla**

Crear `tests/api/test_scraper_sources_api.py` — replicar el bloque de setup de entorno + helpers JWT/seeding del archivo existente `tests/api/test_competitor_brands_crud.py` (mismas líneas 17-31 de overrides de entorno, `_emit_jwt`, `_seed_user_with_perms`). Luego:

```python
@pytest.mark.api
async def test_create_and_list_source(client, db_session):
    user_id, token = await _seed_user_with_perms(
        db_session, ["products:read", "products:write"]
    )
    await db_session.commit()

    resp = await client.post(
        "/api/v1/scraper-sources",
        json={
            "name": "ACME Tools",
            "slug": "acme-api",
            "base_url": "https://acme.example",
            "destination_profile": "competitor_price",
        },
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 201
    body = resp.json()
    assert body["slug"] == "acme-api"
    assert body["status"] == "draft"

    list_resp = await client.get(
        "/api/v1/scraper-sources",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert list_resp.status_code == 200
    assert any(s["slug"] == "acme-api" for s in list_resp.json())


@pytest.mark.api
async def test_add_recipe_to_source(client, db_session):
    user_id, token = await _seed_user_with_perms(
        db_session, ["products:read", "products:write"]
    )
    await db_session.commit()

    src = await client.post(
        "/api/v1/scraper-sources",
        json={
            "name": "ACME", "slug": "acme-recipe-api",
            "base_url": "https://acme.example",
            "destination_profile": "competitor_price",
        },
        headers={"Authorization": f"Bearer {token}"},
    )
    source_id = src.json()["id"]

    recipe_resp = await client.post(
        f"/api/v1/scraper-sources/{source_id}/recipes",
        json={
            "recipe": {
                "url_templates": {"search": "https://acme.example/s?q={query}"},
                "list_item_selector": "div.product",
                "fields": [{"name": "title", "selector": "h2.name"}],
            }
        },
        headers={"Authorization": f"Bearer {token}"},
    )
    assert recipe_resp.status_code == 201
    assert recipe_resp.json()["version"] == 1
```

> Nota: usar las fixtures `client` y `db_session` tal como las define `tests/conftest.py` / el conftest de `tests/api/`. Si el cliente de test del proyecto se llama distinto (revisar `test_competitor_brands_crud.py`), usar ese nombre.

- [ ] **Step 3: Correr el test para verificar que falla**

Run: `pytest tests/api/test_scraper_sources_api.py -v`
Expected: FAIL — 404 en `/api/v1/scraper-sources` (router no registrado).

- [ ] **Step 4: Escribir el router**

Crear `app/api/routes/scraper_sources.py`:

```python
"""Router REST del módulo Scraper Source Builder (F1)."""
from __future__ import annotations

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import require_permissions
from app.db import get_db_session
from app.db.models.user import User
from app.repositories.scraper_sources import ScraperSourceRepository
from app.schemas.scraper_sources import (
    RecipeRead,
    RecipeSubmit,
    ScraperSourceCreate,
    ScraperSourceRead,
    ValidateRequest,
    ValidateResponse,
)
from app.services.matching.adapters.generic_configurable import _curl_cffi_fetch
from app.services.scraper.source_validation_service import SourceValidationService

router = APIRouter(prefix="/scraper-sources", tags=["scraper-sources"])


@router.post(
    "",
    response_model=ScraperSourceRead,
    status_code=status.HTTP_201_CREATED,
    operation_id="createScraperSource",
)
async def create_source(
    body: ScraperSourceCreate,
    user: Annotated[User, Depends(require_permissions("products:write"))],
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> ScraperSourceRead:
    repo = ScraperSourceRepository(session)
    if await repo.get_by_slug(body.slug) is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={"error": "duplicate_slug", "detail": f"slug '{body.slug}' ya existe."},
        )
    source = await repo.create(
        name=body.name,
        slug=body.slug,
        base_url=body.base_url,
        destination_profile=body.destination_profile,
        fetch_mode=body.fetch_mode,
        description=body.description,
        competitor_brand_id=body.competitor_brand_id,
        created_by=user.id,
    )
    await session.commit()
    return ScraperSourceRead.model_validate(source)


@router.get("", response_model=list[ScraperSourceRead], operation_id="listScraperSources")
async def list_sources(
    _user: Annotated[User, Depends(require_permissions("products:read"))],
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> list[ScraperSourceRead]:
    repo = ScraperSourceRepository(session)
    return [ScraperSourceRead.model_validate(s) for s in await repo.list_all()]


@router.get(
    "/{source_id}", response_model=ScraperSourceRead, operation_id="getScraperSource"
)
async def get_source(
    source_id: UUID,
    _user: Annotated[User, Depends(require_permissions("products:read"))],
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> ScraperSourceRead:
    repo = ScraperSourceRepository(session)
    source = await repo.get(source_id)
    if source is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="source not found")
    return ScraperSourceRead.model_validate(source)


@router.post(
    "/{source_id}/recipes",
    response_model=RecipeRead,
    status_code=status.HTTP_201_CREATED,
    operation_id="addScraperSourceRecipe",
)
async def add_recipe(
    source_id: UUID,
    body: RecipeSubmit,
    user: Annotated[User, Depends(require_permissions("products:write"))],
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> RecipeRead:
    repo = ScraperSourceRepository(session)
    if await repo.get(source_id) is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="source not found")
    recipe_row = await repo.add_recipe(
        source_id, body.recipe.model_dump(mode="json"), created_by=user.id
    )
    await session.commit()
    return RecipeRead.model_validate(recipe_row)


@router.post(
    "/{source_id}/validate",
    response_model=ValidateResponse,
    operation_id="validateScraperSourceRecipe",
)
async def validate_recipe(
    source_id: UUID,
    body: ValidateRequest,
    _user: Annotated[User, Depends(require_permissions("products:write"))],
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> ValidateResponse:
    repo = ScraperSourceRepository(session)
    if await repo.get(source_id) is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="source not found")
    service = SourceValidationService(session)
    try:
        result = await service.validate(
            source_id, body.recipe_id, body.test_url, html_fetcher=_curl_cffi_fetch
        )
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)
        ) from exc
    await session.commit()
    return ValidateResponse(**result)


@router.post(
    "/{source_id}/activate",
    response_model=ScraperSourceRead,
    operation_id="activateScraperSource",
)
async def activate_source(
    source_id: UUID,
    body: ValidateRequest,
    _user: Annotated[User, Depends(require_permissions("products:write"))],
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> ScraperSourceRead:
    """Promueve una receta a is_live y la source a 'active'.

    Requiere que la receta esté ``passing`` y sin snippets sin aprobar.
    """
    repo = ScraperSourceRepository(session)
    source = await repo.get(source_id)
    if source is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="source not found")
    recipe = await repo.get_recipe(body.recipe_id)
    if recipe is None or recipe.source_id != source_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="recipe not found")
    if recipe.validation_status != "passing":
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="la receta debe estar 'passing' para activarse",
        )
    if recipe.has_unapproved_snippet:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="la receta tiene snippets sin aprobar",
        )
    await repo.set_recipe_live(body.recipe_id)
    source.status = "active"
    await session.commit()
    return ScraperSourceRead.model_validate(source)
```

> El campo `body.test_url` del schema `ValidateRequest` se ignora en `activate`; reutilizamos el schema solo por su `recipe_id`. Si se prefiere, crear un `ActivateRequest` con solo `recipe_id` — opcional, no bloqueante para F1.

- [ ] **Step 5: Registrar el router**

En `app/api/routes/__init__.py`: añadir `scraper_sources` a la línea de import de routers (junto a `scraper`, `competitor_brands`), y añadir junto a los `router.include_router(...)`:

```python
router.include_router(scraper_sources.router)
```

- [ ] **Step 6: Correr el test para verificar que pasa**

Run: `pytest tests/api/test_scraper_sources_api.py -v`
Expected: PASS (2 tests).

- [ ] **Step 7: Commit**

```bash
git add app/schemas/scraper_sources.py app/api/routes/scraper_sources.py app/api/routes/__init__.py tests/api/test_scraper_sources_api.py
git commit -m "feat(scraper): API REST de scraper-sources (CRUD + validar + activar)"
```

---

## Task 11: Celery task scrape_source_task

**Files:**
- Modify: `mt-pricing-backend/app/workers/tasks/scraper.py`
- Test: `mt-pricing-backend/tests/integration/test_scrape_source_task.py`

- [ ] **Step 1: Escribir el test que falla**

Crear `tests/integration/test_scrape_source_task.py`:

```python
from pathlib import Path

import pytest

from app.repositories.scraper_sources import ScraperSourceRepository
from app.workers.tasks.scraper import _scrape_source_async

_FIXTURE = Path(__file__).parent.parent / "fixtures" / "scraper_sources" / "serp_sample.html"

_RECIPE = {
    "url_templates": {"search": "https://acme.example/s?q={query}"},
    "list_item_selector": "div.product",
    "fields": [
        {"name": "external_id", "selector": "h2.name", "extract": "text"},
        {"name": "title", "selector": "h2.name", "extract": "text"},
        {"name": "brand", "selector": "span.brand", "extract": "text"},
        {"name": "price_aed", "selector": "span.price", "type": "currency"},
    ],
}


@pytest.mark.integration
async def test_scrape_source_async_upserts_listings(db_session):
    from app.db.models.comparator import CompetitorBrand

    brand = CompetitorBrand(name="ACME", amazon_dept="industrial", is_active=True)
    db_session.add(brand)
    await db_session.flush()

    repo = ScraperSourceRepository(db_session)
    source = await repo.create(
        name="ACME", slug="acme-task", base_url="https://acme.example",
        destination_profile="competitor_price", competitor_brand_id=brand.id,
    )
    recipe_row = await repo.add_recipe(source.id, _RECIPE)
    await repo.set_recipe_live(recipe_row.id)
    source.status = "active"
    await db_session.flush()

    html = _FIXTURE.read_text(encoding="utf-8")

    async def fake_fetch(url: str) -> str:
        return html

    result = await _scrape_source_async(
        db_session, str(source.id), search_text="valvula", html_fetcher=fake_fetch
    )
    assert result["status"] == "ok"
    assert result["upserted"] == 2
```

> Si la construcción de `CompetitorBrand` requiere más campos obligatorios, revisar el modelo en `app/db/models/comparator.py` y completarlos — el test solo necesita una marca persistida con `is_active=True`.

- [ ] **Step 2: Correr el test para verificar que falla**

Run: `pytest tests/integration/test_scrape_source_task.py -v`
Expected: FAIL — `ImportError: cannot import name '_scrape_source_async'`.

- [ ] **Step 3: Añadir la task y su helper async**

En `app/workers/tasks/scraper.py`, añadir el helper async (testeable, sin Celery) y la task que lo envuelve. Colocar tras `scrape_brand_task`:

```python
async def _scrape_source_async(
    session,
    source_id: str,
    *,
    search_text: str,
    html_fetcher=None,
) -> dict:
    """Ejecuta un ScraperSource configurable y upserta los listings resultantes.

    Reutiliza el contrato CandidateRaw → CompetitorListing del scraper existente.
    Requiere que la source tenga ``competitor_brand_id`` (perfil competitor_price).
    """
    from uuid import UUID

    from app.repositories.competitor_brands import CompetitorBrandRepository
    from app.repositories.scraper_sources import ScraperSourceRepository
    from app.services.matching.adapter_registry import resolve_fetcher
    from app.services.matching.ports import Query

    src_repo = ScraperSourceRepository(session)
    source = await src_repo.get(UUID(source_id))
    if source is None:
        return {"source_id": source_id, "status": "not_found", "upserted": 0}
    if source.status != "active":
        return {"source_id": source_id, "status": "inactive", "upserted": 0}
    if source.competitor_brand_id is None:
        return {"source_id": source_id, "status": "no_brand", "upserted": 0}

    fetcher = await resolve_fetcher(source.slug, session, html_fetcher=html_fetcher)
    query = Query(text=search_text, source=source.slug)
    candidates = await fetcher.fetch(query)

    brand_repo = CompetitorBrandRepository(session)
    upserted = 0
    for candidate in candidates:
        await brand_repo.upsert_listing(
            candidate, competitor_brand_id=source.competitor_brand_id
        )
        upserted += 1
    await session.commit()
    return {"source_id": source_id, "status": "ok", "upserted": upserted}


@celery_app.task(
    bind=True,
    name="mt.scraper.scrape_source",
    max_retries=3,
    default_retry_delay=120,
    acks_late=True,
    queue="scraper",
)
def scrape_source_task(self, source_id: str, *, search_text: str) -> dict:  # type: ignore[override]
    """Celery task: ejecuta un ScraperSource configurable."""
    logger.info("scraper.source_start", extra={"source_id": source_id})

    async def _run() -> dict:
        from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
        from sqlalchemy.pool import NullPool

        from app.core.config import settings

        engine = create_async_engine(
            str(settings.DATABASE_URL),
            poolclass=NullPool,
            connect_args={
                "statement_cache_size": 0,
                "server_settings": {
                    "application_name": "mt-scraper-worker",
                    "timezone": "UTC",
                },
            },
        )
        session_factory = async_sessionmaker(
            bind=engine, expire_on_commit=False, autoflush=False, class_=AsyncSession
        )
        try:
            async with session_factory() as session:
                return await _scrape_source_async(
                    session, source_id, search_text=search_text
                )
        finally:
            await engine.dispose()

    try:
        result = asyncio.run(_run())
        logger.info(
            "scraper.source_done",
            extra={"source_id": source_id, "upserted": result.get("upserted", 0)},
        )
        return result
    except SoftTimeLimitExceeded:
        logger.warning("scraper.source_soft_timeout", extra={"source_id": source_id})
        raise
    except Exception as exc:
        logger.exception(
            "scraper.source_failed",
            extra={"source_id": source_id, "error": str(exc)},
        )
        raise self.retry(exc=exc, countdown=120 * (2 ** self.request.retries))
```

> El helper `_scrape_source_async` recibe la `session` y un `html_fetcher` opcional para ser testeable sin red ni Celery; la task `scrape_source_task` lo invoca con sesión real y `html_fetcher=None` (usa curl_cffi).

- [ ] **Step 4: Correr el test para verificar que pasa**

Run: `pytest tests/integration/test_scrape_source_task.py -v`
Expected: PASS.

- [ ] **Step 5: Suite completa de regresión del dominio scraper**

Run: `pytest tests/ -k "scraper or matching or competitor" -v`
Expected: PASS — sin regresiones en los tests existentes de scraper/matching/competitor.

- [ ] **Step 6: Commit**

```bash
git add app/workers/tasks/scraper.py tests/integration/test_scrape_source_task.py
git commit -m "feat(scraper): Celery task scrape_source para sources configurables"
```

---

## Verificación final

- [ ] **Suite completa del backend**

Run: `pytest tests/ -q`
Expected: toda la suite verde (o sin nuevos fallos respecto al baseline previo a esta rama).

- [ ] **Migración aplicada en dev**

Run: `./infra/scripts/migrate.sh && docker restart mt-backend`
Verificar: `curl http://localhost:${CADDY_HTTP_PORT:-8081}/health/live` responde OK.

- [ ] **Smoke manual de la API**

Crear una source vía `POST /api/v1/scraper-sources`, añadir una receta, validarla contra una URL real de un sitio simple, y confirmar que `field_results` es coherente.

---

## Mapa de cobertura del spec (auto-revisión)

| Requisito del spec (F1) | Task |
|--------------------------|------|
| Tablas `scraper_sources` / `scraper_source_recipes` / `scraper_source_test_runs` (§3) | 1, 2 |
| Receta versionada, una `is_live` por source (§3.2) | 1 (índice parcial), 7 |
| Estructura JSONB de la receta (§3.3) | 3 |
| Transforms declarativos (§3.4 — modalidad A) | 4 |
| `GenericConfigurableFetcher` implementa `FetcherPort` (§4.2) | 6 |
| Modo de fetch `static`; `headless`/`stealth` diferidos (§4.2, decisión 2) | 6 |
| Fallback de resolución de canal (§2, §4.3) | 9 |
| `SourceValidationService` con pass/fail por field (§4.4) | 8 |
| Perfil `competitor_price` → `CandidateRaw` → `CompetitorListing` (§4.6) | 6, 11 |
| API REST del módulo (§4.7, subconjunto F1) | 10 |
| Persistencia de producción vía Celery (§6 "Producción") | 11 |

**Fuera de F1 (fases posteriores, ya en el spec):** descubrimiento por IA (§4.1), modos `headless`/`stealth`, snippets LLM + sandbox (§4.5, §3.4-B), perfil `product_data` (§4.6), monitoreo/alertas y ciclo `degraded` (§4 monitoreo), todo el frontend (§5).
