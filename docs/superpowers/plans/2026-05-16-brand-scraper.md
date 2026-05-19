# Brand Scraper Module — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Añadir un módulo de marcas competidoras que permite registrar brands y disparar scraping en Amazon UAE filtrado por brand + categoría específica, almacenando resultados en `competitor_listings`.

**Architecture:** Se añade la tabla `competitor_brands` para registrar marcas (con dept y opcionalmente un node de categoría Amazon). Se extiende el `Query` dataclass con campos `dept`/`category_node` para que los adapters construyan URLs filtradas. Una nueva Celery task `scrape_brand_task` orquesta la búsqueda y hace upsert en `competitor_listings` con FK a la marca. El flujo SKU existente no se toca.

**Tech Stack:** FastAPI + SQLAlchemy 2.0 async + Alembic + Celery + curl_cffi + patchright + Pydantic v2

---

## File Map

| Archivo | Acción | Responsabilidad |
|---------|--------|-----------------|
| `app/services/matching/ports.py` | Modify | Añadir `dept` y `category_node` a `Query` |
| `app/services/matching/adapters/curl_cffi_amazon_uae.py` | Modify | `_fetch_serp` recibe `Query` completo; URL usa `query.dept` + `query.category_node` |
| `app/services/matching/adapters/patchright_amazon_uae.py` | Modify | `_fetch_serp_with` recibe `Query` completo; misma URL logic |
| `app/db/models/comparator.py` | Modify | Añadir `CompetitorBrand` model + FK `competitor_brand_id` en `CompetitorListing` |
| `app/db/models/__init__.py` | Modify | Registrar `CompetitorBrand` |
| `alembic/versions/20260530_132_competitor_brands.py` | Create | Migration: tabla + FK column |
| `app/schemas/competitor_brands.py` | Create | Pydantic schemas CRUD + trigger |
| `app/repositories/competitor_brands.py` | Create | CRUD repo + upsert_listing |
| `app/api/routes/competitor_brands.py` | Create | REST CRUD + POST /run-brand |
| `app/api/routes/__init__.py` | Modify | Registrar `competitor_brands` router |
| `app/workers/tasks/scraper.py` | Modify | Añadir `scrape_brand_task` + `scrape_brands_batch_task` |
| `tests/api/test_competitor_brands_crud.py` | Create | API CRUD + trigger tests |
| `tests/workers/test_scrape_brand_task.py` | Create | Task logic con fetcher mock |
| `tests/services/test_brand_query_extension.py` | Create | Query dataclass + URL building unit tests |

---

## Task 1: Extender `Query` con campos de filtro de categoría

**Files:**
- Modify: `mt-pricing-backend/app/services/matching/ports.py`
- Create: `mt-pricing-backend/tests/services/test_brand_query_extension.py`

- [ ] **Step 1: Escribir test que verifica los nuevos campos de Query**

```python
# tests/services/test_brand_query_extension.py
"""Unit tests para la extensión de Query con dept + category_node."""
from app.services.matching.ports import Query


def test_query_default_dept():
    q = Query(text="Nibco ball valve", source="amazon_uae")
    assert q.dept == "industrial"
    assert q.category_node is None


def test_query_custom_dept():
    q = Query(text="Nibco", source="amazon_uae", dept="tools")
    assert q.dept == "tools"


def test_query_with_category_node():
    q = Query(text="Nibco", source="amazon_uae", category_node="16118159031")
    assert q.category_node == "16118159031"
    assert q.dept == "industrial"


def test_query_frozen_still_works():
    q = Query(text="Kitz", source="amazon_uae", type="brand", dept="industrial")
    # frozen dataclass — no puede ser mutado
    import dataclasses
    assert dataclasses.is_dataclass(q)
```

- [ ] **Step 2: Ejecutar test para verificar que falla**

```
cd mt-pricing-backend
pytest tests/services/test_brand_query_extension.py -v
```

Expected: `FAILED` — `Query() got unexpected keyword argument 'dept'`

- [ ] **Step 3: Añadir `dept` y `category_node` al dataclass `Query`**

En `app/services/matching/ports.py`, reemplazar la clase `Query`:

```python
@dataclass(frozen=True)
class Query:
    """Una query elaborada por el Query Builder (Etapa 1)."""

    text: str
    source: str
    lang: str = "en"
    type: str = "spec"
    dept: str = "industrial"
    category_node: str | None = None
```

- [ ] **Step 4: Ejecutar test para verificar que pasa**

```
pytest tests/services/test_brand_query_extension.py -v
```

Expected: 4 tests PASSED

- [ ] **Step 5: Commit**

```bash
git add mt-pricing-backend/app/services/matching/ports.py \
        mt-pricing-backend/tests/services/test_brand_query_extension.py
git commit -m "feat(matching): add dept + category_node to Query for brand-scoped SERP"
```

---

## Task 2: Actualizar adapters para usar `query.dept` y `query.category_node`

**Files:**
- Modify: `mt-pricing-backend/app/services/matching/adapters/curl_cffi_amazon_uae.py`
- Modify: `mt-pricing-backend/app/services/matching/adapters/patchright_amazon_uae.py`
- Create: `mt-pricing-backend/tests/services/test_brand_query_extension.py` (añadir tests de URL)

- [ ] **Step 1: Añadir tests de URL building al archivo existente de tests**

Añadir al final de `tests/services/test_brand_query_extension.py`:

```python
from urllib.parse import quote_plus
_BASE = "https://www.amazon.ae"


def _build_serp_url(query: Query) -> str:
    """Replica la lógica del adapter — helper para tests."""
    url = f"{_BASE}/s?k={quote_plus(query.text)}"
    if query.dept:
        url += f"&i={query.dept}"
    if query.category_node:
        url += f"&rh=n:{query.category_node}"
    url += "&language=en_AE"
    return url


def test_serp_url_default_dept():
    q = Query(text="ball valve", source="amazon_uae")
    url = _build_serp_url(q)
    assert "&i=industrial" in url
    assert "rh=n:" not in url


def test_serp_url_with_category_node():
    q = Query(text="Nibco", source="amazon_uae", category_node="16118159031")
    url = _build_serp_url(q)
    assert "&i=industrial" in url
    assert "&rh=n:16118159031" in url


def test_serp_url_brand_query_type():
    q = Query(text="Kitz", source="amazon_uae", type="brand", dept="tools")
    url = _build_serp_url(q)
    assert "&i=tools" in url
    assert "Kitz" in url
```

- [ ] **Step 2: Ejecutar nuevos tests para confirmar que pasan** (son tests del helper, no del adapter real)

```
pytest tests/services/test_brand_query_extension.py -v
```

Expected: todos PASSED

- [ ] **Step 3: Actualizar `curl_cffi_amazon_uae.py`**

Cambiar la llamada en `fetch()` — línea ~97:
```python
# ANTES:
serp_results = await self._fetch_serp(session, query.text)

# DESPUÉS:
serp_results = await self._fetch_serp(session, query)
```

Cambiar la signatura y cuerpo de `_fetch_serp` — líneas ~180-193:
```python
async def _fetch_serp(self, session: AsyncSession, query: Query) -> list[dict]:
    url = f"{_AMAZON_AE_BASE}/s?k={quote_plus(query.text)}"
    if query.dept:
        url += f"&i={query.dept}"
    if query.category_node:
        url += f"&rh=n:{query.category_node}"
    url += "&language=en_AE"

    logger.debug("scraper.serp.fetch", extra={"url": url})
    resp = await session.get(url)

    self._check_blocked(resp)

    # Delay before first PDP to avoid burst pattern.
    await asyncio.sleep(random.uniform(1.5, 4.0))

    return extract_top_results(resp.text, top_n=6)
```

- [ ] **Step 4: Actualizar `patchright_amazon_uae.py`**

Cambiar la llamada en `fetch()` — línea ~151:
```python
# ANTES:
serp_results = await self._fetch_serp_with(context, query.text)

# DESPUÉS:
serp_results = await self._fetch_serp_with(context, query)
```

Cambiar la signatura y cuerpo de `_fetch_serp_with` — líneas ~203-214:
```python
async def _fetch_serp_with(self, context: object, query: Query) -> list[dict]:
    """Navigate to SERP using ``context``; return extracted results."""
    url = f"{_AMAZON_AE_BASE}/s?k={quote_plus(query.text)}"
    if query.dept:
        url += f"&i={query.dept}"
    if query.category_node:
        url += f"&rh=n:{query.category_node}"
    url += "&language=en_AE"
    logger.debug("patchright.serp.fetch", extra={"url": url})

    html, final_url = await self._page_get_with(context, url)
    self._check_blocked(200, final_url)

    # Polite delay before first PDP.
    await asyncio.sleep(random.uniform(1.5, 4.0))

    return extract_top_results(html, top_n=6)
```

Añadir import de `Query` al top de `patchright_amazon_uae.py` si no está (verificar que ya importa `Query` de `ports`).

- [ ] **Step 5: Ejecutar tests de unit para verificar que no hay regresiones**

```
pytest tests/services/ -v
```

Expected: todos PASSED

- [ ] **Step 6: Commit**

```bash
git add mt-pricing-backend/app/services/matching/adapters/curl_cffi_amazon_uae.py \
        mt-pricing-backend/app/services/matching/adapters/patchright_amazon_uae.py \
        mt-pricing-backend/tests/services/test_brand_query_extension.py
git commit -m "feat(scraper): adapters usan query.dept + query.category_node para filtrar SERP"
```

---

## Task 3: Modelo ORM `CompetitorBrand` + FK en `CompetitorListing`

**Files:**
- Modify: `mt-pricing-backend/app/db/models/comparator.py`
- Modify: `mt-pricing-backend/app/db/models/__init__.py`

- [ ] **Step 1: Añadir `CompetitorBrand` al principio de `comparator.py`** (antes de `CompetitorListing`)

Insertar después de los imports existentes, antes de `MATCH_DECISIONS`:

```python
class CompetitorBrand(UuidPkMixin, TimestampMixin, Base):
    """Marca competidora registrada para scraping periódico en Amazon UAE."""

    __tablename__ = "competitor_brands"

    name: Mapped[str] = mapped_column(String(200), nullable=False)
    amazon_search_term: Mapped[str | None] = mapped_column(String(200), nullable=True)
    amazon_dept: Mapped[str] = mapped_column(
        String(100), nullable=False, server_default=text("'industrial'")
    )
    amazon_category_node: Mapped[str | None] = mapped_column(String(50), nullable=True)
    is_active: Mapped[bool] = mapped_column(
        Boolean, nullable=False, server_default=text("true")
    )
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    last_scraped_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    __table_args__ = (
        Index("ux_competitor_brands_name", func.lower(name), unique=True),
    )

    @property
    def effective_search_term(self) -> str:
        """Término de búsqueda real: amazon_search_term si está definido, sino name."""
        return self.amazon_search_term or self.name
```

- [ ] **Step 2: Añadir `competitor_brand_id` FK a `CompetitorListing`**

En la clase `CompetitorListing`, después del campo `sanity_check_skipped` (línea ~128) y antes de `__table_args__`, añadir:

```python
    # Marca competidora origen del scrape — nullable para listings de match_sku flow
    competitor_brand_id: Mapped[UUID | None] = mapped_column(
        UUID_PG,
        ForeignKey("competitor_brands.id", ondelete="SET NULL"),
        nullable=True,
    )
```

Y en `__table_args__` de `CompetitorListing`, añadir el índice:

```python
        Index("ix_competitor_listings_brand_id", "competitor_brand_id"),
```

- [ ] **Step 3: Registrar `CompetitorBrand` en `app/db/models/__init__.py`**

Buscar en `__init__.py` la línea que importa `CompetitorListing` (o `comparator`) y añadir `CompetitorBrand`:

```python
from app.db.models.comparator import CompetitorBrand, CompetitorListing, MatchDecision
```

- [ ] **Step 4: Verificar que los modelos se importan sin errores**

```
cd mt-pricing-backend
python -c "from app.db.models.comparator import CompetitorBrand, CompetitorListing; print('OK')"
```

Expected: `OK`

- [ ] **Step 5: Commit**

```bash
git add mt-pricing-backend/app/db/models/comparator.py \
        mt-pricing-backend/app/db/models/__init__.py
git commit -m "feat(db): CompetitorBrand model + competitor_brand_id FK en CompetitorListing"
```

---

## Task 4: Migración Alembic

**Files:**
- Create: `mt-pricing-backend/alembic/versions/20260530_132_competitor_brands.py`

- [ ] **Step 1: Crear el archivo de migración**

```python
# alembic/versions/20260530_132_competitor_brands.py
"""competitor_brands table + competitor_brand_id FK en competitor_listings.

Revision ID: 20260530132
Revises: 20260529131
Create Date: 2026-05-30
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "20260530132"
down_revision = "20260529131"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "competitor_brands",
        sa.Column("id", sa.UUID(), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("name", sa.String(200), nullable=False),
        sa.Column("amazon_search_term", sa.String(200), nullable=True),
        sa.Column("amazon_dept", sa.String(100), server_default="industrial", nullable=False),
        sa.Column("amazon_category_node", sa.String(50), nullable=True),
        sa.Column("is_active", sa.Boolean(), server_default=sa.text("true"), nullable=False),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("last_scraped_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ux_competitor_brands_name",
        "competitor_brands",
        [sa.text("lower(name)")],
        unique=True,
    )

    op.add_column(
        "competitor_listings",
        sa.Column("competitor_brand_id", sa.UUID(), nullable=True),
    )
    op.create_foreign_key(
        "fk_competitor_listings_brand",
        "competitor_listings",
        "competitor_brands",
        ["competitor_brand_id"],
        ["id"],
        ondelete="SET NULL",
    )
    op.create_index(
        "ix_competitor_listings_brand_id",
        "competitor_listings",
        ["competitor_brand_id"],
    )


def downgrade() -> None:
    op.drop_index("ix_competitor_listings_brand_id", table_name="competitor_listings")
    op.drop_constraint("fk_competitor_listings_brand", "competitor_listings", type_="foreignkey")
    op.drop_column("competitor_listings", "competitor_brand_id")

    op.drop_index("ux_competitor_brands_name", table_name="competitor_brands")
    op.drop_table("competitor_brands")
```

**Importante:** verificar cuál es el `down_revision` real ejecutando:
```
cd mt-pricing-backend
alembic heads
```
Si el head actual no es `20260529131`, ajustar `down_revision` con el valor devuelto.

- [ ] **Step 2: Verificar que alembic puede generar el SQL sin errores**

```
cd mt-pricing-backend
alembic upgrade 20260530132 --sql 2>&1 | head -50
```

Expected: SQL válido sin errores de parse.

- [ ] **Step 3: Aplicar la migración al Docker local**

```
./infra/scripts/migrate.sh
docker restart mt-backend
```

Expected: `Running upgrade ... -> 20260530132, competitor_brands table + FK`

- [ ] **Step 4: Commit**

```bash
git add mt-pricing-backend/alembic/versions/20260530_132_competitor_brands.py
git commit -m "feat(migration): 132 competitor_brands table + competitor_brand_id FK"
```

---

## Task 5: Schemas Pydantic + Repository

**Files:**
- Create: `mt-pricing-backend/app/schemas/competitor_brands.py`
- Create: `mt-pricing-backend/app/repositories/competitor_brands.py`

- [ ] **Step 1: Crear schemas Pydantic**

```python
# app/schemas/competitor_brands.py
"""Pydantic schemas para el módulo de marcas competidoras."""
from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field, model_validator


class CompetitorBrandCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=200)
    amazon_search_term: str | None = Field(None, max_length=200)
    amazon_dept: str = Field("industrial", max_length=100)
    amazon_category_node: str | None = Field(None, max_length=50)
    is_active: bool = True
    notes: str | None = None


class CompetitorBrandUpdate(BaseModel):
    name: str | None = Field(None, min_length=1, max_length=200)
    amazon_search_term: str | None = None
    amazon_dept: str | None = Field(None, max_length=100)
    amazon_category_node: str | None = None
    is_active: bool | None = None
    notes: str | None = None


class CompetitorBrandRead(BaseModel):
    id: UUID
    name: str
    amazon_search_term: str | None
    amazon_dept: str
    amazon_category_node: str | None
    is_active: bool
    notes: str | None
    last_scraped_at: datetime | None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class BrandScrapeRunRequest(BaseModel):
    brand_ids: list[UUID] | None = Field(
        None,
        description="UUIDs de las marcas a scrapear. None = todas las activas.",
    )
    force: bool = False


class BrandScrapeRunResponse(BaseModel):
    job_id: str | None
    total_brands: int
    status: str
```

- [ ] **Step 2: Crear repositorio**

```python
# app/repositories/competitor_brands.py
"""CRUD repository para CompetitorBrand + upsert de competitor_listings."""
from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.comparator import CompetitorBrand, CompetitorListing
from app.services.matching.ports import CandidateRaw


class CompetitorBrandRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def create(
        self,
        name: str,
        *,
        amazon_search_term: str | None = None,
        amazon_dept: str = "industrial",
        amazon_category_node: str | None = None,
        is_active: bool = True,
        notes: str | None = None,
    ) -> CompetitorBrand:
        brand = CompetitorBrand(
            name=name,
            amazon_search_term=amazon_search_term,
            amazon_dept=amazon_dept,
            amazon_category_node=amazon_category_node,
            is_active=is_active,
            notes=notes,
        )
        self._session.add(brand)
        await self._session.flush()
        return brand

    async def get(self, brand_id: UUID) -> CompetitorBrand | None:
        return await self._session.get(CompetitorBrand, brand_id)

    async def get_by_name(self, name: str) -> CompetitorBrand | None:
        stmt = select(CompetitorBrand).where(
            func.lower(CompetitorBrand.name) == name.lower()
        )
        result = await self._session.execute(stmt)
        return result.scalar_one_or_none()

    async def list_active(self) -> list[CompetitorBrand]:
        stmt = select(CompetitorBrand).where(CompetitorBrand.is_active.is_(True))
        result = await self._session.execute(stmt)
        return list(result.scalars().all())

    async def list_all(self) -> list[CompetitorBrand]:
        stmt = select(CompetitorBrand).order_by(CompetitorBrand.name)
        result = await self._session.execute(stmt)
        return list(result.scalars().all())

    async def update(self, brand: CompetitorBrand, **kwargs: object) -> CompetitorBrand:
        for key, value in kwargs.items():
            if value is not None or key in ("amazon_search_term", "amazon_category_node", "notes"):
                setattr(brand, key, value)
        brand.updated_at = datetime.now(tz=timezone.utc)
        await self._session.flush()
        return brand

    async def touch_scraped(self, brand: CompetitorBrand) -> None:
        brand.last_scraped_at = datetime.now(tz=timezone.utc)
        brand.updated_at = datetime.now(tz=timezone.utc)
        await self._session.flush()

    async def upsert_listing(
        self,
        candidate: CandidateRaw,
        *,
        competitor_brand_id: UUID,
    ) -> None:
        """Upsert un CandidateRaw en competitor_listings vinculado a la marca."""
        now = datetime.now(tz=timezone.utc)
        image_url: str = candidate.raw_payload.get("image_url", "") or ""
        stmt = (
            pg_insert(CompetitorListing)
            .values(
                source=candidate.source,
                source_id=candidate.external_id,
                source_url=candidate.raw_payload.get("url"),
                raw_payload_jsonb=candidate.raw_payload,
                normalized_jsonb={
                    "title": candidate.title,
                    "brand": candidate.brand,
                    "price_aed": str(candidate.price_aed) if candidate.price_aed else None,
                    "specs": candidate.specs,
                },
                image_url=image_url or None,
                competitor_brand_id=competitor_brand_id,
                last_seen_at=now,
            )
            .on_conflict_do_update(
                index_elements=["source", "source_id"],
                set_={
                    "raw_payload_jsonb": pg_insert(CompetitorListing).excluded.raw_payload_jsonb,
                    "normalized_jsonb": pg_insert(CompetitorListing).excluded.normalized_jsonb,
                    "image_url": pg_insert(CompetitorListing).excluded.image_url,
                    "competitor_brand_id": competitor_brand_id,
                    "last_seen_at": now,
                },
            )
        )
        await self._session.execute(stmt)
```

- [ ] **Step 3: Verificar imports sin errores**

```
cd mt-pricing-backend
python -c "from app.schemas.competitor_brands import CompetitorBrandCreate; from app.repositories.competitor_brands import CompetitorBrandRepository; print('OK')"
```

Expected: `OK`

- [ ] **Step 4: Commit**

```bash
git add mt-pricing-backend/app/schemas/competitor_brands.py \
        mt-pricing-backend/app/repositories/competitor_brands.py
git commit -m "feat(brands): schemas Pydantic + CompetitorBrandRepository con upsert_listing"
```

---

## Task 6: API routes CRUD + trigger

**Files:**
- Create: `mt-pricing-backend/app/api/routes/competitor_brands.py`
- Modify: `mt-pricing-backend/app/api/routes/__init__.py`
- Create: `mt-pricing-backend/tests/api/test_competitor_brands_crud.py`

- [ ] **Step 1: Escribir tests de API**

```python
# tests/api/test_competitor_brands_crud.py
"""Integration tests para /competitor-brands CRUD + trigger."""
from __future__ import annotations

import os
import time
from uuid import UUID, uuid4

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from jose import jwt
from sqlalchemy.ext.asyncio import AsyncSession

os.environ.setdefault("SUPABASE_JWT_SECRET", "test-jwt-secret-deterministic-32chars!")
os.environ.setdefault("SUPABASE_URL", "https://test.supabase.co")
os.environ.setdefault("SUPABASE_ANON_KEY", "anon-test")
os.environ.setdefault("SUPABASE_SERVICE_ROLE_KEY", "service-test")

JWT_SECRET = "test-jwt-secret-deterministic-32chars!"


def _emit_jwt(*, sub: str, email: str) -> str:
    now = int(time.time())
    return jwt.encode(
        {
            "sub": sub,
            "aud": "authenticated",
            "email": email,
            "iat": now,
            "exp": now + 3600,
            "app_metadata": {"role": "comercial"},
        },
        JWT_SECRET,
        algorithm="HS256",
    )


async def _seed_user_with_perms(session: AsyncSession, perms_codes: list[str]):
    from app.db.models.user import Permission, Role, RolePermission, User

    perm_ids = []
    for code in perms_codes:
        perm = Permission(id=uuid4(), code=code, description=code)
        session.add(perm)
        perm_ids.append(perm.id)
    await session.flush()

    role = Role(id=uuid4(), name=f"role_{uuid4().hex[:6]}", description="test")
    session.add(role)
    await session.flush()

    for pid in perm_ids:
        session.add(RolePermission(role_id=role.id, permission_id=pid))
    await session.flush()

    user_id = uuid4()
    user = User(
        id=user_id,
        email=f"{uuid4().hex[:8]}@test.com",
        role_id=role.id,
        is_active=True,
    )
    session.add(user)
    await session.flush()

    token = _emit_jwt(sub=str(user_id), email=user.email)
    return user_id, token


@pytest_asyncio.fixture
async def client_with_write_perms(db_session):
    _user_id, token = await _seed_user_with_perms(
        db_session, ["products:write", "products:read"]
    )
    await db_session.commit()

    from app.main import app
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as c:
        c.headers["Authorization"] = f"Bearer {token}"
        yield c


@pytest.mark.asyncio
async def test_create_brand_happy_path(client_with_write_perms):
    resp = await client_with_write_perms.post(
        "/api/v1/competitor-brands/",
        json={"name": "Nibco", "amazon_dept": "industrial"},
    )
    assert resp.status_code == 201
    data = resp.json()
    assert data["name"] == "Nibco"
    assert data["amazon_dept"] == "industrial"
    assert data["is_active"] is True
    UUID(data["id"])  # válido UUID


@pytest.mark.asyncio
async def test_create_brand_duplicate_name_returns_409(client_with_write_perms):
    payload = {"name": "Kitz Duplicate"}
    await client_with_write_perms.post("/api/v1/competitor-brands/", json=payload)
    resp = await client_with_write_perms.post("/api/v1/competitor-brands/", json=payload)
    assert resp.status_code == 409


@pytest.mark.asyncio
async def test_list_brands(client_with_write_perms):
    await client_with_write_perms.post(
        "/api/v1/competitor-brands/", json={"name": "Crane List Test"}
    )
    resp = await client_with_write_perms.get("/api/v1/competitor-brands/")
    assert resp.status_code == 200
    assert isinstance(resp.json(), list)
    names = [b["name"] for b in resp.json()]
    assert "Crane List Test" in names


@pytest.mark.asyncio
async def test_patch_brand(client_with_write_perms):
    create_resp = await client_with_write_perms.post(
        "/api/v1/competitor-brands/", json={"name": "PatchBrand"}
    )
    brand_id = create_resp.json()["id"]
    patch_resp = await client_with_write_perms.patch(
        f"/api/v1/competitor-brands/{brand_id}",
        json={"amazon_category_node": "16118159031", "is_active": False},
    )
    assert patch_resp.status_code == 200
    assert patch_resp.json()["amazon_category_node"] == "16118159031"
    assert patch_resp.json()["is_active"] is False


@pytest.mark.asyncio
async def test_get_brand_not_found(client_with_write_perms):
    resp = await client_with_write_perms.get(
        f"/api/v1/competitor-brands/{uuid4()}"
    )
    assert resp.status_code == 404
```

- [ ] **Step 2: Ejecutar tests para confirmar que fallan (ruta no existe)**

```
cd mt-pricing-backend
pytest tests/api/test_competitor_brands_crud.py -v
```

Expected: `FAILED` — 404 or connection errors (ruta no registrada)

- [ ] **Step 3: Crear `app/api/routes/competitor_brands.py`**

```python
# app/api/routes/competitor_brands.py
"""Competitor Brands — gestión de marcas competidoras + trigger de scraping."""
from __future__ import annotations

import logging
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_db_session, require_permissions
from app.db.models.user import User
from app.repositories.competitor_brands import CompetitorBrandRepository
from app.schemas.competitor_brands import (
    BrandScrapeRunRequest,
    BrandScrapeRunResponse,
    CompetitorBrandCreate,
    CompetitorBrandRead,
    CompetitorBrandUpdate,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/competitor-brands", tags=["competitor-brands"])


@router.post(
    "/",
    response_model=CompetitorBrandRead,
    status_code=status.HTTP_201_CREATED,
    operation_id="createCompetitorBrand",
)
async def create_brand(
    body: CompetitorBrandCreate,
    _user: Annotated[User, Depends(require_permissions("products:write"))],
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> CompetitorBrandRead:
    repo = CompetitorBrandRepository(session)
    existing = await repo.get_by_name(body.name)
    if existing:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={"error": "duplicate_name", "detail": f"Brand '{body.name}' ya existe."},
        )
    brand = await repo.create(
        name=body.name,
        amazon_search_term=body.amazon_search_term,
        amazon_dept=body.amazon_dept,
        amazon_category_node=body.amazon_category_node,
        is_active=body.is_active,
        notes=body.notes,
    )
    await session.commit()
    return CompetitorBrandRead.model_validate(brand)


@router.get(
    "/",
    response_model=list[CompetitorBrandRead],
    operation_id="listCompetitorBrands",
)
async def list_brands(
    _user: Annotated[User, Depends(require_permissions("products:read"))],
    session: Annotated[AsyncSession, Depends(get_db_session)],
    active_only: bool = False,
) -> list[CompetitorBrandRead]:
    repo = CompetitorBrandRepository(session)
    brands = await repo.list_active() if active_only else await repo.list_all()
    return [CompetitorBrandRead.model_validate(b) for b in brands]


@router.get(
    "/{brand_id}",
    response_model=CompetitorBrandRead,
    operation_id="getCompetitorBrand",
)
async def get_brand(
    brand_id: UUID,
    _user: Annotated[User, Depends(require_permissions("products:read"))],
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> CompetitorBrandRead:
    repo = CompetitorBrandRepository(session)
    brand = await repo.get(brand_id)
    if not brand:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Brand not found")
    return CompetitorBrandRead.model_validate(brand)


@router.patch(
    "/{brand_id}",
    response_model=CompetitorBrandRead,
    operation_id="updateCompetitorBrand",
)
async def update_brand(
    brand_id: UUID,
    body: CompetitorBrandUpdate,
    _user: Annotated[User, Depends(require_permissions("products:write"))],
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> CompetitorBrandRead:
    repo = CompetitorBrandRepository(session)
    brand = await repo.get(brand_id)
    if not brand:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Brand not found")
    updated = await repo.update(brand, **body.model_dump(exclude_none=True))
    await session.commit()
    return CompetitorBrandRead.model_validate(updated)


@router.post(
    "/run",
    response_model=BrandScrapeRunResponse,
    status_code=status.HTTP_202_ACCEPTED,
    operation_id="runBrandScrape",
)
async def run_brand_scrape(
    body: BrandScrapeRunRequest,
    _user: Annotated[User, Depends(require_permissions("products:write"))],
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> BrandScrapeRunResponse:
    from celery import group as celery_group
    from app.workers.tasks.scraper import scrape_brand_task

    repo = CompetitorBrandRepository(session)
    if body.brand_ids:
        brands = [b for bid in body.brand_ids if (b := await repo.get(bid)) is not None]
    else:
        brands = await repo.list_active()

    if not brands:
        return BrandScrapeRunResponse(job_id=None, total_brands=0, status="nothing_to_do")

    job = celery_group(
        scrape_brand_task.s(str(b.id), force=body.force) for b in brands
    ).apply_async(queue="comparator")
    job.save()

    logger.info(
        "scraper.brand_batch_queued",
        extra={"total_brands": len(brands), "group_id": job.id},
    )
    return BrandScrapeRunResponse(
        job_id=job.id,
        total_brands=len(brands),
        status="queued",
    )
```

- [ ] **Step 4: Registrar el router en `app/api/routes/__init__.py`**

Añadir el import junto a los otros routes:
```python
from app.api.routes import competitor_brands
```

Y en el bloque de `router.include_router(...)`, junto al de scraper:
```python
# EP-SCR-02 — Competitor brands CRUD + brand scrape trigger
router.include_router(competitor_brands.router)
```

- [ ] **Step 5: Ejecutar tests de API**

```
cd mt-pricing-backend
pytest tests/api/test_competitor_brands_crud.py -v
```

Expected: todos PASSED

- [ ] **Step 6: Commit**

```bash
git add mt-pricing-backend/app/api/routes/competitor_brands.py \
        mt-pricing-backend/app/api/routes/__init__.py \
        mt-pricing-backend/tests/api/test_competitor_brands_crud.py
git commit -m "feat(api): /competitor-brands CRUD + /competitor-brands/run trigger"
```

---

## Task 7: Celery task `scrape_brand_task`

**Files:**
- Modify: `mt-pricing-backend/app/workers/tasks/scraper.py`
- Create: `mt-pricing-backend/tests/workers/test_scrape_brand_task.py`

- [ ] **Step 1: Escribir tests para la task**

```python
# tests/workers/test_scrape_brand_task.py
"""Tests para scrape_brand_task — mock del fetcher."""
from __future__ import annotations

import asyncio
from datetime import datetime, timezone
from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest

from app.services.matching.ports import CandidateRaw, Query


def _make_candidate(asin: str = "B001TEST01") -> CandidateRaw:
    return CandidateRaw(
        source="amazon_uae",
        external_id=asin,
        title="Nibco 1/2 Ball Valve Bronze",
        brand="Nibco",
        price_aed=Decimal("45.00"),
        specs={"valve_type": "ball"},
        raw_payload={
            "asin": asin,
            "url": f"https://www.amazon.ae/dp/{asin}",
            "image_url": "https://example.com/img.jpg",
            "query_text": "Nibco",
            "query_type": "brand",
        },
        fetched_at=datetime.now(tz=timezone.utc),
    )


@pytest.mark.asyncio
async def test_scrape_brand_builds_correct_query():
    """La task construye un Query con type=brand y los campos de la marca."""
    from app.workers.tasks.scraper import _build_brand_query
    from app.db.models.comparator import CompetitorBrand

    brand = CompetitorBrand(
        id=uuid4(),
        name="Nibco",
        amazon_search_term=None,
        amazon_dept="industrial",
        amazon_category_node="16118159031",
        is_active=True,
    )

    query = _build_brand_query(brand)
    assert query.text == "Nibco"
    assert query.type == "brand"
    assert query.dept == "industrial"
    assert query.category_node == "16118159031"
    assert query.source == "amazon_uae"


@pytest.mark.asyncio
async def test_scrape_brand_uses_amazon_search_term_over_name():
    """Si amazon_search_term está definido, se usa como texto de búsqueda."""
    from app.workers.tasks.scraper import _build_brand_query
    from app.db.models.comparator import CompetitorBrand

    brand = CompetitorBrand(
        id=uuid4(),
        name="Nibco Inc.",
        amazon_search_term="Nibco",
        amazon_dept="industrial",
        amazon_category_node=None,
        is_active=True,
    )

    query = _build_brand_query(brand)
    assert query.text == "Nibco"
```

- [ ] **Step 2: Ejecutar tests para confirmar que fallan**

```
cd mt-pricing-backend
pytest tests/workers/test_scrape_brand_task.py -v
```

Expected: `FAILED` — `ImportError: cannot import name '_build_brand_query'`

- [ ] **Step 3: Añadir la task y helpers a `workers/tasks/scraper.py`**

Al final del archivo `app/workers/tasks/scraper.py`, añadir:

```python
# ---------------------------------------------------------------------------
# Helpers para brand scraping
# ---------------------------------------------------------------------------


def _build_brand_query(brand: "CompetitorBrand") -> "Query":  # noqa: F821
    """Construye el Query para buscar todos los productos de una marca en Amazon."""
    from app.db.models.comparator import CompetitorBrand as _CB  # noqa: F401
    from app.services.matching.ports import Query

    return Query(
        text=brand.amazon_search_term or brand.name,
        source="amazon_uae",
        type="brand",
        dept=brand.amazon_dept,
        category_node=brand.amazon_category_node,
    )


# ---------------------------------------------------------------------------
# Task individual — una marca
# ---------------------------------------------------------------------------


@celery_app.task(
    bind=True,
    name="mt.scraper.scrape_brand",
    max_retries=3,
    default_retry_delay=120,
    acks_late=True,
    queue="comparator",
)
def scrape_brand_task(self, brand_id: str, *, force: bool = False) -> dict:  # type: ignore[override]
    """Scraping de todos los productos de una marca competidora en Amazon UAE.

    Busca en Amazon usando `amazon_search_term` (o `name`) filtrado por
    `amazon_dept` y opcionalmente `amazon_category_node`. Hace upsert de los
    resultados en `competitor_listings` con FK a la marca.

    Args:
        brand_id: UUID de la marca en `competitor_brands`.
        force: Si True, re-scrapea aunque `last_scraped_at` sea reciente.
    """
    logger.info("scraper.brand_start", extra={"brand_id": brand_id, "force": force})

    async def _run_async() -> dict:
        from app.core.config import settings
        from app.db.models.comparator import CompetitorBrand
        from app.repositories.competitor_brands import CompetitorBrandRepository
        from app.repositories.feature_flags import FeatureFlagRepository
        from app.services.feature_flags.flag_service import (
            FlagService,
            set_default_service,
            warmup_local_cache,
        )
        from app.services.matching.adapter_registry import get_fetcher
        from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
        from sqlalchemy.pool import NullPool
        from uuid import UUID

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
            bind=engine,
            expire_on_commit=False,
            autoflush=False,
            class_=AsyncSession,
        )
        try:
            # ── Warmup flags ────────────────────────────────────────────────
            try:
                async with session_factory() as flag_session:
                    flag_repo = FeatureFlagRepository(flag_session)
                    flag_svc = FlagService(flag_repo=flag_repo, redis=None)
                    set_default_service(flag_svc)
                    all_flags = await flag_svc.get_all()
                    warmup_local_cache(all_flags)
            except Exception:
                logger.warning("scraper.brand.flags_warmup_failed", extra={"brand_id": brand_id})

            # ── Scraping ────────────────────────────────────────────────────
            async with session_factory() as session:
                repo = CompetitorBrandRepository(session)
                brand = await repo.get(UUID(brand_id))
                if not brand:
                    logger.warning("scraper.brand.not_found", extra={"brand_id": brand_id})
                    return {"brand_id": brand_id, "status": "not_found", "upserted": 0}

                if not brand.is_active:
                    logger.info("scraper.brand.inactive", extra={"brand_id": brand_id})
                    return {"brand_id": brand_id, "status": "inactive", "upserted": 0}

                fetcher = get_fetcher("amazon_uae")
                query = _build_brand_query(brand)
                candidates = await fetcher.fetch(query)

                upserted = 0
                for candidate in candidates:
                    await repo.upsert_listing(candidate, competitor_brand_id=brand.id)
                    upserted += 1

                await repo.touch_scraped(brand)
                await session.commit()

        finally:
            await engine.dispose()

        return {"brand_id": brand_id, "status": "ok", "upserted": upserted}

    try:
        result = asyncio.run(_run_async())
        logger.info(
            "scraper.brand_done",
            extra={"brand_id": brand_id, "upserted": result.get("upserted", 0)},
        )
        return result

    except Exception as exc:
        logger.exception(
            "scraper.brand_failed",
            extra={"brand_id": brand_id, "error": str(exc), "retries": self.request.retries},
        )
        raise self.retry(
            exc=exc,
            countdown=120 * (2 ** self.request.retries),
        )


# ---------------------------------------------------------------------------
# Task batch — fan-out de marcas
# ---------------------------------------------------------------------------


@celery_app.task(
    name="mt.scraper.scrape_brands_batch",
    acks_late=True,
    queue="comparator",
)
def scrape_brands_batch_task(brand_ids: list[str] | None = None, *, force: bool = False) -> dict:
    """Fan-out de `scrape_brand_task` para todas las marcas activas o las indicadas.

    Puede ser disparado por Beat (job_definitions) o desde la API.
    brand_ids=None → carga todas las marcas activas.
    """
    if brand_ids is None:
        # Cargar marcas activas sincronamente
        import asyncio as _asyncio

        async def _load_brands() -> list[str]:
            from app.core.config import settings
            from app.db.models.comparator import CompetitorBrand
            from sqlalchemy import select
            from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
            from sqlalchemy.pool import NullPool

            engine = create_async_engine(
                str(settings.DATABASE_URL),
                poolclass=NullPool,
                connect_args={"statement_cache_size": 0},
            )
            session_factory = async_sessionmaker(bind=engine, class_=AsyncSession)
            try:
                async with session_factory() as session:
                    stmt = select(CompetitorBrand.id).where(CompetitorBrand.is_active.is_(True))
                    result = await session.execute(stmt)
                    return [str(row[0]) for row in result.all()]
            finally:
                await engine.dispose()

        brand_ids = _asyncio.run(_load_brands())

    if not brand_ids:
        logger.warning("scraper.brands_batch_empty")
        return {"group_id": None, "total": 0}

    job = celery_group(
        scrape_brand_task.s(bid, force=force) for bid in brand_ids
    ).apply_async(queue="comparator")
    job.save()

    logger.info(
        "scraper.brands_batch_dispatched",
        extra={"group_id": job.id, "total": len(brand_ids)},
    )
    return {"group_id": job.id, "total": len(brand_ids)}
```

- [ ] **Step 4: Ejecutar tests**

```
cd mt-pricing-backend
pytest tests/workers/test_scrape_brand_task.py -v
```

Expected: todos PASSED

- [ ] **Step 5: Commit**

```bash
git add mt-pricing-backend/app/workers/tasks/scraper.py \
        mt-pricing-backend/tests/workers/test_scrape_brand_task.py
git commit -m "feat(worker): scrape_brand_task + scrape_brands_batch_task para marcas competidoras"
```

---

## Task 8: Registrar task routing + smoke test

**Files:**
- Modify: `mt-pricing-backend/app/workers/worker.py` (si tiene `task_routes`)
- Docker restart

- [ ] **Step 1: Verificar task_routes en worker.py**

```
grep -n "task_routes\|scraper" mt-pricing-backend/app/workers/worker.py
```

Si hay una dict de `task_routes` con `"mt.scraper.*"` → `"comparator"`, añadir:
```python
"mt.scraper.scrape_brand": {"queue": "comparator"},
"mt.scraper.scrape_brands_batch": {"queue": "comparator"},
```

Si el routing ya usa wildcard `"mt.scraper.*"`, no cambiar nada.

- [ ] **Step 2: Ejecutar todos los tests del módulo**

```
cd mt-pricing-backend
pytest tests/services/test_brand_query_extension.py \
       tests/api/test_competitor_brands_crud.py \
       tests/workers/test_scrape_brand_task.py -v
```

Expected: todos PASSED

- [ ] **Step 3: Redesplegar backend y worker**

```
docker restart mt-backend mt-worker mt-beat
```

- [ ] **Step 4: Smoke test — crear una marca y listarla**

```bash
# Obtener JWT del usuario de prueba local (ajustar según el setup local)
TOKEN=$(curl -s -X POST http://localhost:8081/api/v1/auth/login \
  -H "Content-Type: application/json" \
  -d '{"email":"admin@test.com","password":"admin"}' | jq -r .access_token)

# Crear marca
curl -s -X POST http://localhost:8081/api/v1/competitor-brands/ \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"name":"Nibco","amazon_dept":"industrial","notes":"Competitor PVF brand"}' | jq .

# Listar marcas
curl -s http://localhost:8081/api/v1/competitor-brands/ \
  -H "Authorization: Bearer $TOKEN" | jq .[].name
```

Expected: respuesta 201 con brand creada, luego lista que incluye "Nibco".

- [ ] **Step 5: Verificar health**

```
curl http://localhost:8081/health/live
```

Expected: `{"status":"ok"}`

- [ ] **Step 6: Commit final**

```bash
git add mt-pricing-backend/app/workers/worker.py
git commit -m "feat(brands): registrar task routes brand scraper en worker"
```

---

## Self-Review

### Spec Coverage

| Req | Task |
|-----|------|
| Scraper por brand | Task 7 (`scrape_brand_task`) |
| Módulo de adición de brand (CRUD) | Task 5 + 6 |
| Buscar por brand en categoría específica | Task 1 + 2 (Query.dept/category_node) |
| Limitar a categoría para evitar errores | Task 2 (URL filter `&i=dept&rh=n:node`) |
| Persistir resultados vinculados a la marca | Task 5 (upsert_listing con competitor_brand_id) |
| Trigger manual desde API | Task 6 (`POST /competitor-brands/run`) |

### Placeholder scan ✓
No hay TBDs ni referencias sin definir.

### Type consistency ✓
- `_build_brand_query(brand: CompetitorBrand) -> Query` definido en Task 7, referenciado en tests del mismo task.
- `CompetitorBrandRepository.upsert_listing` definido en Task 5, llamado en Task 7.
- `Query.dept` y `Query.category_node` definidos en Task 1, usados en Task 2 y Task 7.
