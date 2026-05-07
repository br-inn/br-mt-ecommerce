---
title: "MT MDM + Pricing — SQLAlchemy 2.0 Async Models (Fase 1)"
status: "draft"
version: "1.0"
created: "2026-05-06"
project_name: "mt-pricing-mdm-phase1"
related: ["prd-mt-pricing-mdm-phase1.md", "architecture-mt-pricing-mdm-phase1.md", "mt-users-module-design.md", "mt-jobs-module-design.md", "mt-api-contract-openapi.yaml"]
---

# Modelos SQLAlchemy 2.0 async — `mt-pricing-backend/`

> Documento canónico de **modelos ORM** para Fase 1. Cada `Mapped[T]` está alineado 1:1 con los DTO de `mt-api-contract-openapi.yaml` (mismos nombres de campo, mismos tipos lógicos). Compatibles con `alembic revision --autogenerate` sin trabajos manuales adicionales (extensiones, enums, particiones y RLS van en migraciones data-only adicionales — ver §11).

## 0. Estructura de carpetas

```
mt-pricing-backend/
├── alembic/
│   ├── env.py
│   └── versions/
└── app/
    └── db/
        ├── __init__.py
        ├── base.py
        ├── engine.py
        ├── session.py
        ├── mixins.py
        ├── enums.py
        ├── jsonb_schemas.py        # TypedDict / Pydantic mirror para JSONB
        ├── models/
        │   ├── __init__.py
        │   ├── users.py            # User, Role, Permission, UserRole, RolePermission
        │   ├── products.py         # Product, ProductTranslation, ProductImage
        │   ├── suppliers.py
        │   ├── costs.py
        │   ├── prices.py
        │   ├── channels.py         # Channel, Scheme, ChannelStateHistory
        │   ├── currencies.py       # Currency, FxRate
        │   ├── exception_rules.py
        │   ├── imports.py          # ImportBatch, ImportError (run_rows)
        │   ├── jobs.py             # JobDefinition, JobRun
        │   ├── audit.py            # AuditEvent (PARTITION BY RANGE)
        │   ├── material_compat.py  # MaterialCompatibility
        │   ├── kb.py               # KbSource, KbChunk, KbReference
        │   └── comparator.py       # CompetitorListing, MatchCandidate, MatchDecision
        └── repositories/
            ├── products.py
            └── prices.py
```

## 1. Setup base — `app/db/base.py`

```python
"""Declarative Base con AsyncAttrs (SQLAlchemy 2.0 async)."""
from sqlalchemy.orm import DeclarativeBase
from sqlalchemy.ext.asyncio import AsyncAttrs

class Base(AsyncAttrs, DeclarativeBase):
    """Base declarativa para todos los modelos del proyecto.

    AsyncAttrs habilita el acceso awaitable a relationships lazy
    (e.g. `await user.awaitable_attrs.roles`) sin forzar eager loading.
    """
    pass
```

> **Nota.** No usamos `MappedAsDataclass` porque queremos campos opcionales con `default=None` sin forzar `kw_only=True` en cada modelo, y porque algunos modelos (Audit, KB) necesitan `__table_args__` muy específicos que conviven mejor con la sintaxis ORM tradicional.

## 2. Connection — `app/db/engine.py`

```python
"""AsyncEngine para Postgres/Supabase usando asyncpg.

Roles (ADR-031):
- `mt_app`     → role aplicativo, sujeto a RLS
- `service_role` → solo para tasks Celery con bypass de RLS controlado
- `mt_migrate` → role para Alembic (DDL)
"""
from __future__ import annotations
import os
from sqlalchemy.ext.asyncio import AsyncEngine, create_async_engine

DATABASE_URL = os.environ["DATABASE_URL"]                       # postgresql+asyncpg://mt_app:...@host/db
DATABASE_URL_MIGRATE = os.environ.get("DATABASE_URL_MIGRATE")    # mt_migrate
POOL_SIZE = int(os.environ.get("DB_POOL_SIZE", "10"))
MAX_OVERFLOW = int(os.environ.get("DB_MAX_OVERFLOW", "10"))

def make_engine(url: str = DATABASE_URL, *, echo: bool = False) -> AsyncEngine:
    return create_async_engine(
        url,
        echo=echo,
        pool_pre_ping=True,
        pool_size=POOL_SIZE,
        max_overflow=MAX_OVERFLOW,
        pool_recycle=1800,
        connect_args={
            "server_settings": {
                "application_name": "mt-pricing-backend",
                "timezone": "UTC",
            },
            "statement_cache_size": 0,   # Supabase pgbouncer en modo transaction
        },
    )

engine: AsyncEngine = make_engine()
```

## 3. Async session factory — `app/db/session.py`

```python
"""AsyncSession factory + dependency FastAPI."""
from __future__ import annotations
from collections.abc import AsyncIterator
from sqlalchemy.ext.asyncio import async_sessionmaker, AsyncSession
from app.db.engine import engine

AsyncSessionLocal: async_sessionmaker[AsyncSession] = async_sessionmaker(
    engine,
    expire_on_commit=False,
    autoflush=False,
    class_=AsyncSession,
)

async def get_session() -> AsyncIterator[AsyncSession]:
    """FastAPI dependency. Cierra la session al terminar la request."""
    async with AsyncSessionLocal() as session:
        try:
            yield session
        except Exception:
            await session.rollback()
            raise
        else:
            await session.commit()
```

## 4. Mixins comunes — `app/db/mixins.py`

```python
"""AuditMixin + SoftDeleteMixin + UuidPkMixin (uuidv7-ready)."""
from __future__ import annotations
from datetime import datetime
from uuid import UUID
from sqlalchemy import DateTime, ForeignKey, text
from sqlalchemy.dialects.postgresql import UUID as PgUUID
from sqlalchemy.orm import Mapped, mapped_column

# ────────────────────────────────────────────────────────
# uuidv7 helper
# ────────────────────────────────────────────────────────
# Supabase-managed Postgres soporta `gen_random_uuid()` (pgcrypto). La
# extensión `pg_uuidv7` (ADR-031) ya está disponible en builds recientes.
# Cuando esté en producción, reemplazar `gen_random_uuid()` por `uuid_generate_v7()`
# (server_default) con `op.execute("ALTER TABLE ... ALTER COLUMN id SET DEFAULT uuid_generate_v7()")`.
# TODO(infra): habilitar pg_uuidv7 cuando esté en el plan Pro de Supabase.
UUID_DEFAULT_SQL = text("gen_random_uuid()")

class UuidPkMixin:
    id: Mapped[UUID] = mapped_column(
        PgUUID(as_uuid=True), primary_key=True, server_default=UUID_DEFAULT_SQL
    )

class AuditMixin:
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=text("now()")
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=text("now()"),
        onupdate=text("now()"),
    )
    created_by: Mapped[UUID | None] = mapped_column(
        PgUUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    updated_by: Mapped[UUID | None] = mapped_column(
        PgUUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )

class SoftDeleteMixin:
    deleted_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True, default=None
    )
```

## 5. Enums Python — `app/db/enums.py`

```python
"""Enums Python alineados con DDL Postgres (`*_t` types).

Importante: el nombre del enum Postgres se declara en cada Column con
`postgresql_using` y `name=` para que Alembic genere `CREATE TYPE ... AS ENUM (...)`
correctamente.
"""
from __future__ import annotations
from enum import StrEnum

class DataQuality(StrEnum):
    COMPLETE = "complete"
    PARTIAL = "partial"
    BLOCKED = "blocked"
    MIGRATED_DEMO = "migrated_demo"

class TranslationStatus(StrEnum):
    PENDING = "pending"
    DRAFT = "draft"
    APPROVED = "approved"

class ChannelState(StrEnum):
    INACTIVE = "inactive"
    PRE_LAUNCH = "pre_launch"
    PILOT = "pilot"
    LIVE = "live"
    PAUSED = "paused"
    DEPRECATED = "deprecated"

class PriceState(StrEnum):
    DRAFT = "draft"
    PENDING_REVIEW = "pending_review"
    AUTO_APPROVED = "auto_approved"
    APPROVED = "approved"
    REJECTED = "rejected"
    REVISED = "revised"
    EXPORTED = "exported"
    SUPERSEDED = "superseded"
    MIGRATED = "migrated"

class CostStatus(StrEnum):
    DRAFT = "draft"
    APPROVED = "approved"
    SUPERSEDED = "superseded"
    MIGRATED = "migrated"

class Scheme(StrEnum):
    FBA = "FBA"
    FBM = "FBM"
    DIRECT_B2C = "DIRECT_B2C"
    DIRECT_B2B = "DIRECT_B2B"
    MARKETPLACE = "MARKETPLACE"

class FxSource(StrEnum):
    MANUAL = "manual"
    FEED_XE = "feed_xe"
    FEED_OANDA = "feed_oanda"
    FEED_ECB = "feed_ecb"
    MIGRATED_INFERRED = "migrated_inferred"

class ImportType(StrEnum):
    PIM_REAL = "pim_real"
    COSTS_REAL = "costs_real"
    EXCEL_DEMO = "excel_demo"
    TRANSLATIONS = "translations"
    FX = "fx"
    DATASHEETS = "datasheets"
    MATERIAL_COMPATIBILITY = "material_compatibility"

class ImportStatus(StrEnum):
    QUEUED = "queued"
    PARSING = "parsing"
    VALIDATING = "validating"
    PREVIEW_READY = "preview_ready"
    APPLYING = "applying"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"

class JobStatus(StrEnum):
    IDLE = "idle"
    RUNNING = "running"
    SUCCESS = "success"
    FAILURE = "failure"
    CANCELLED = "cancelled"

class JobOwner(StrEnum):
    INFRA = "infra"
    BUSINESS = "business"

class ScheduleType(StrEnum):
    CRON = "cron"
    INTERVAL = "interval"

class MatchStatus(StrEnum):
    UNMATCHED = "unmatched"
    CANDIDATE = "candidate"
    CONFIRMED = "confirmed"
    REJECTED = "rejected"

class CompatT(StrEnum):
    A = "A"
    B = "B"
    C = "C"
    D = "D"
    SIN_DATO = "SIN_DATO"
```

## 6. JSONB schemas tipados — `app/db/jsonb_schemas.py`

```python
"""Pydantic V2 mirrors para columnas JSONB.

Los modelos ORM almacenan `dict[str, Any]` (JSONB) pero los servicios
validan y serializan con estos modelos para garantizar consistencia
con OpenAPI (`CostBreakdown`, `PriceBreakdown`, ...).
"""
from __future__ import annotations
from decimal import Decimal
from typing import Annotated, Any, Literal
from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator
import re

# ISO 4217 (3 letras mayúsculas)
CurrencyCode = Annotated[str, Field(min_length=3, max_length=3, pattern=r"^[A-Z]{3}$")]
# ISO 639-1 (2 letras minúsculas)
LanguageCode = Annotated[str, Field(min_length=2, max_length=2, pattern=r"^[a-z]{2}$")]
# ISO 3166 alpha-2
CountryCode = Annotated[str, Field(min_length=2, max_length=2, pattern=r"^[A-Z]{2}$")]

PHONE_RE = re.compile(r"^\+?[0-9 .\-()]{6,20}$")

class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid", populate_by_name=True, str_strip_whitespace=True)


class CostBreakdownPayload(StrictModel):
    """Mirror tipado de la fila costs."""
    fob: Decimal = Decimal("0")
    freight: Decimal = Decimal("0")
    customs: Decimal = Decimal("0")
    fba_fees: Decimal = Decimal("0")
    fbm_fees: Decimal = Decimal("0")
    payment_fees: Decimal = Decimal("0")
    marketing_fees: Decimal = Decimal("0")
    other_fees: dict[str, Decimal] = Field(default_factory=dict)


class PriceBreakdownPayload(StrictModel):
    cost_in_base: Decimal
    margin_abs: Decimal
    margin_pct: Decimal
    fees_breakdown: dict[str, Decimal] = Field(default_factory=dict)
    fx_rate_used: Decimal


class AlertItem(StrictModel):
    code: str
    message: str


class AlertPayload(StrictModel):
    critical: list[AlertItem] = Field(default_factory=list)
    warnings: list[AlertItem] = Field(default_factory=list)


class ProductSpecsPayload(StrictModel):
    """JSONB de products.specs. Permite extras controlados via additionalProperties."""
    model_config = ConfigDict(extra="allow")  # specs son extensibles por familia
    thread_standard: Literal["BSP", "NPT", "ISO_228", "ISO_7_1", "NONE"] | None = None
    body_material: str | None = None
    seat_material: str | None = None
    max_temperature_c: int | None = None
    max_pressure_bar: float | None = None
    certification: list[str] = Field(default_factory=list)
    weight_kg: float | None = None


class ContactPayload(StrictModel):
    email: EmailStr | None = None
    phone: str | None = None

    @field_validator("phone")
    @classmethod
    def _phone(cls, v: str | None) -> str | None:
        if v is None:
            return v
        if not PHONE_RE.match(v):
            raise ValueError("invalid phone format")
        return v
```

## 7. Modelos

### 7.1 Users / Roles / Permissions — `app/db/models/users.py`

```python
"""User, Role, Permission + assoc tables.

Decisión (ver §12 Inconsistencias resueltas):
- Tabla aplicativa `users` (NO `profiles`) por consistencia con resto de DDL
  arquitectura. La FK desde `auth.users(id)` (Supabase) se materializa via
  trigger Postgres `on_auth_user_created`.
- `users.id` = `auth.users.id` (UUID 1:1).
- Roles soportan tanto `code` (texto estable) como `id` (UUID surrogate) para
  compatibilidad con users-module-design (UUID-based) y architecture (code-based).
"""
from __future__ import annotations
from datetime import datetime
from uuid import UUID
from sqlalchemy import (
    Boolean, CheckConstraint, DateTime, ForeignKey, Index, String, Text,
    UniqueConstraint, text,
)
from sqlalchemy.dialects.postgresql import CITEXT, JSONB, UUID as PgUUID
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.db.base import Base
from app.db.mixins import AuditMixin, UuidPkMixin


class Role(UuidPkMixin, Base):
    __tablename__ = "roles"

    code: Mapped[str] = mapped_column(Text, unique=True, nullable=False)
    name: Mapped[str] = mapped_column(Text, nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    is_system: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default=text("true"))
    permissions_snapshot: Mapped[dict] = mapped_column(JSONB, nullable=False, server_default=text("'[]'::jsonb"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=text("now()"))
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=text("now()"), onupdate=text("now()"))

    role_permissions: Mapped[list["RolePermission"]] = relationship(back_populates="role", cascade="all, delete-orphan")
    users: Mapped[list["User"]] = relationship(back_populates="role")

    __table_args__ = (
        Index("idx_roles_code", "code"),
    )


class Permission(UuidPkMixin, Base):
    __tablename__ = "permissions"

    code: Mapped[str] = mapped_column(Text, unique=True, nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=text("now()"))

    role_permissions: Mapped[list["RolePermission"]] = relationship(back_populates="permission", cascade="all, delete-orphan")


class RolePermission(Base):
    __tablename__ = "role_permissions"

    role_id: Mapped[UUID] = mapped_column(PgUUID(as_uuid=True), ForeignKey("roles.id", ondelete="CASCADE"), primary_key=True)
    permission_id: Mapped[UUID] = mapped_column(PgUUID(as_uuid=True), ForeignKey("permissions.id", ondelete="CASCADE"), primary_key=True)
    granted_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=text("now()"))

    role: Mapped[Role] = relationship(back_populates="role_permissions")
    permission: Mapped[Permission] = relationship(back_populates="role_permissions")


class User(Base):
    __tablename__ = "users"

    # PK 1:1 con auth.users.id de Supabase
    id: Mapped[UUID] = mapped_column(PgUUID(as_uuid=True), primary_key=True)
    email: Mapped[str] = mapped_column(CITEXT, unique=True, nullable=False)
    full_name: Mapped[str | None] = mapped_column(Text)
    avatar_url: Mapped[str | None] = mapped_column(Text)
    locale: Mapped[str] = mapped_column(String(2), nullable=False, server_default=text("'es'"))
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default=text("true"))
    role_id: Mapped[UUID | None] = mapped_column(PgUUID(as_uuid=True), ForeignKey("roles.id", ondelete="SET NULL"))

    last_login_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    failed_logins: Mapped[int] = mapped_column(nullable=False, server_default=text("0"))
    locked_until: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=text("now()"))
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=text("now()"), onupdate=text("now()"))
    created_by: Mapped[UUID | None] = mapped_column(PgUUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"))

    role: Mapped[Role | None] = relationship(back_populates="users", foreign_keys=[role_id])

    __table_args__ = (
        CheckConstraint("locale IN ('es','en','ar')", name="ck_users_locale"),
        Index("idx_users_role", "role_id"),
        Index("idx_users_active", "is_active", postgresql_where=text("is_active = true")),
    )
```

### 7.2 Products — `app/db/models/products.py`

```python
"""Product + ProductTranslation + ProductImage."""
from __future__ import annotations
from datetime import datetime
from uuid import UUID
from sqlalchemy import (
    Boolean, CheckConstraint, DateTime, ForeignKey, Index, String, Text,
    UniqueConstraint, text,
)
from sqlalchemy.dialects.postgresql import ARRAY, JSONB, UUID as PgUUID
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.db.base import Base
from app.db.enums import DataQuality, TranslationStatus
from app.db.mixins import UuidPkMixin

try:
    from pgvector.sqlalchemy import Vector  # type: ignore
except ImportError:  # local dev sin pgvector
    Vector = None  # type: ignore


class Product(Base):
    __tablename__ = "products"

    sku: Mapped[str] = mapped_column(Text, primary_key=True)
    internal_id: Mapped[UUID] = mapped_column(
        PgUUID(as_uuid=True), nullable=False, unique=True,
        server_default=text("gen_random_uuid()")
    )

    name_en: Mapped[str] = mapped_column(Text, nullable=False)
    description_en: Mapped[str | None] = mapped_column(Text)
    marketing_copy_en: Mapped[str | None] = mapped_column(Text)

    family: Mapped[str] = mapped_column(Text, nullable=False)
    subfamily: Mapped[str | None] = mapped_column(Text)
    type: Mapped[str | None] = mapped_column(Text)
    material: Mapped[str | None] = mapped_column(Text)
    dn: Mapped[str | None] = mapped_column(Text)
    pn: Mapped[str | None] = mapped_column(Text)
    connection: Mapped[str | None] = mapped_column(Text)
    brand: Mapped[str | None] = mapped_column(Text)
    specs: Mapped[dict] = mapped_column(JSONB, nullable=False, server_default=text("'{}'::jsonb"))

    data_quality: Mapped[DataQuality] = mapped_column(
        String(16), nullable=False, server_default=text("'partial'")
    )
    manual_locked_fields: Mapped[list[str]] = mapped_column(
        ARRAY(Text), nullable=False, server_default=text("'{}'::text[]")
    )
    active: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default=text("true"))

    # Embedding (Fase 1.5+)
    if Vector is not None:
        embedding = mapped_column(Vector(1536), nullable=True)
    else:
        embedding: Mapped[list[float] | None] = mapped_column(ARRAY(Text), nullable=True)
    embedding_model: Mapped[str | None] = mapped_column(Text)
    embedding_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=text("now()"))
    created_by: Mapped[UUID | None] = mapped_column(PgUUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"))
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=text("now()"), onupdate=text("now()"))
    updated_by: Mapped[UUID | None] = mapped_column(PgUUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"))

    translations: Mapped[list["ProductTranslation"]] = relationship(back_populates="product", cascade="all, delete-orphan")
    images: Mapped[list["ProductImage"]] = relationship(back_populates="product", cascade="all, delete-orphan")

    __table_args__ = (
        Index("idx_products_family", "family"),
        Index("idx_products_brand", "brand"),
        Index("idx_products_active", "active", postgresql_where=text("active = true")),
        Index("idx_products_specs_gin", "specs", postgresql_using="gin"),
        Index(
            "idx_products_name_trgm", "name_en",
            postgresql_using="gin",
            postgresql_ops={"name_en": "gin_trgm_ops"},
        ),
        # HNSW reservado Fase 1.5+ (no se crea ahora):
        # Index("idx_products_embedding", "embedding", postgresql_using="hnsw",
        #       postgresql_ops={"embedding": "vector_cosine_ops"}),
    )


class ProductTranslation(Base):
    __tablename__ = "product_translations"

    sku: Mapped[str] = mapped_column(
        Text, ForeignKey("products.sku", ondelete="CASCADE"), primary_key=True
    )
    lang: Mapped[str] = mapped_column(String(2), primary_key=True)
    name: Mapped[str | None] = mapped_column(Text)
    description: Mapped[str | None] = mapped_column(Text)
    marketing_copy: Mapped[str | None] = mapped_column(Text)
    status: Mapped[TranslationStatus] = mapped_column(String(16), nullable=False, server_default=text("'pending'"))
    translated_by: Mapped[UUID | None] = mapped_column(PgUUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"))
    translated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    reviewed_by: Mapped[UUID | None] = mapped_column(PgUUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"))
    reviewed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=text("now()"))
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=text("now()"), onupdate=text("now()"))

    product: Mapped[Product] = relationship(back_populates="translations")

    __table_args__ = (
        CheckConstraint("lang IN ('es','ar')", name="ck_translations_lang"),
        Index("idx_translations_status", "lang", "status"),
    )


class ProductImage(UuidPkMixin, Base):
    __tablename__ = "product_images"

    sku: Mapped[str] = mapped_column(Text, ForeignKey("products.sku", ondelete="CASCADE"), nullable=False)
    role: Mapped[str] = mapped_column(Text, nullable=False)
    storage_path: Mapped[str] = mapped_column(Text, unique=True, nullable=False)
    alt_text: Mapped[str | None] = mapped_column(Text)
    width: Mapped[int | None] = mapped_column()
    height: Mapped[int | None] = mapped_column()
    hash_sha256: Mapped[str | None] = mapped_column(Text)
    status: Mapped[str] = mapped_column(Text, nullable=False, server_default=text("'active'"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=text("now()"))
    created_by: Mapped[UUID | None] = mapped_column(PgUUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"))

    product: Mapped[Product] = relationship(back_populates="images")

    __table_args__ = (
        CheckConstraint("status IN ('active','archived','broken')", name="ck_images_status"),
        Index("idx_images_sku_role", "sku", "role"),
    )
```

### 7.3 Suppliers — `app/db/models/suppliers.py`

```python
from __future__ import annotations
from datetime import datetime
from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String, Text, text
from sqlalchemy.dialects.postgresql import CITEXT
from sqlalchemy.orm import Mapped, mapped_column
from app.db.base import Base


class Supplier(Base):
    __tablename__ = "suppliers"

    code: Mapped[str] = mapped_column(Text, primary_key=True)
    name: Mapped[str] = mapped_column(Text, nullable=False)
    contact_email: Mapped[str | None] = mapped_column(CITEXT)
    contact_phone: Mapped[str | None] = mapped_column(Text)
    contract_currency: Mapped[str] = mapped_column(
        String(3), ForeignKey("currencies.code"), nullable=False
    )
    lead_time_days: Mapped[int | None] = mapped_column(Integer)
    payment_terms: Mapped[str | None] = mapped_column(Text)
    notes: Mapped[str | None] = mapped_column(Text)
    active: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default=text("true"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=text("now()"))
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=text("now()"), onupdate=text("now()"))
```

### 7.4 Currencies & FX — `app/db/models/currencies.py`

```python
from __future__ import annotations
from datetime import datetime
from decimal import Decimal
from uuid import UUID
from sqlalchemy import (
    BigInteger, Boolean, CheckConstraint, DateTime, ForeignKey, Index, Integer,
    Numeric, String, Text, text,
)
from sqlalchemy.dialects.postgresql import UUID as PgUUID
from sqlalchemy.orm import Mapped, mapped_column
from app.db.base import Base
from app.db.enums import FxSource


class Currency(Base):
    __tablename__ = "currencies"

    code: Mapped[str] = mapped_column(String(3), primary_key=True)
    name: Mapped[str] = mapped_column(Text, nullable=False)
    symbol: Mapped[str | None] = mapped_column(Text)
    decimals: Mapped[int] = mapped_column(Integer, nullable=False, server_default=text("2"))
    is_base: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default=text("false"))
    active: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default=text("true"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=text("now()"))

    __table_args__ = (
        CheckConstraint("decimals BETWEEN 0 AND 8", name="ck_currencies_decimals"),
        Index("uq_currencies_one_base", "is_base", unique=True, postgresql_where=text("is_base = true")),
    )


class FxRate(Base):
    __tablename__ = "fx_rates"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    from_currency: Mapped[str] = mapped_column(String(3), ForeignKey("currencies.code"), nullable=False)
    to_currency: Mapped[str] = mapped_column(String(3), ForeignKey("currencies.code"), nullable=False)
    rate: Mapped[Decimal] = mapped_column(Numeric(18, 8), nullable=False)
    effective_from: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    effective_to: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    source: Mapped[FxSource] = mapped_column(String(32), nullable=False, server_default=text("'manual'"))
    entered_by: Mapped[UUID | None] = mapped_column(PgUUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"))
    notes: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=text("now()"))

    __table_args__ = (
        CheckConstraint("rate > 0", name="ck_fx_rate_positive"),
        CheckConstraint("from_currency <> to_currency", name="ck_fx_distinct"),
        CheckConstraint("effective_to IS NULL OR effective_to > effective_from", name="ck_fx_period"),
        Index("idx_fx_pair_time", "from_currency", "to_currency", "effective_from"),
        Index("idx_fx_active", "from_currency", "to_currency",
              postgresql_where=text("effective_to IS NULL")),
    )
```

### 7.5 Channels / Schemes / ChannelStateHistory — `app/db/models/channels.py`

```python
from __future__ import annotations
from datetime import date, datetime
from uuid import UUID
from sqlalchemy import (
    BigInteger, Boolean, Date, DateTime, ForeignKey, Index, String, Text, text,
)
from sqlalchemy.dialects.postgresql import ARRAY, JSONB, UUID as PgUUID
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.db.base import Base
from app.db.enums import ChannelState, Scheme


class Scheme_(Base):  # nombre de clase con underscore para no chocar con enum
    __tablename__ = "schemes"

    code: Mapped[Scheme] = mapped_column(String(32), primary_key=True)
    name: Mapped[str] = mapped_column(Text, nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    cost_components_template: Mapped[dict] = mapped_column(JSONB, nullable=False, server_default=text("'{}'::jsonb"))
    active: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default=text("true"))


class Channel(Base):
    __tablename__ = "channels"

    code: Mapped[str] = mapped_column(Text, primary_key=True)
    name: Mapped[str] = mapped_column(Text, nullable=False)
    state: Mapped[ChannelState] = mapped_column(String(16), nullable=False, server_default=text("'inactive'"))
    schemes_supported: Mapped[list[str]] = mapped_column(ARRAY(String(32)), nullable=False, server_default=text("'{}'::text[]"))
    currency: Mapped[str] = mapped_column(String(3), ForeignKey("currencies.code"), nullable=False, server_default=text("'AED'"))
    requires_translations: Mapped[list[str]] = mapped_column(ARRAY(String(2)), nullable=False, server_default=text("'{}'::text[]"))
    go_live_target: Mapped[date | None] = mapped_column(Date)
    notes: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=text("now()"))
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=text("now()"), onupdate=text("now()"))

    history: Mapped[list["ChannelStateHistory"]] = relationship(back_populates="channel", cascade="all, delete-orphan")


class ChannelStateHistory(Base):
    __tablename__ = "channel_state_history"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    channel_code: Mapped[str] = mapped_column(Text, ForeignKey("channels.code", ondelete="CASCADE"), nullable=False)
    from_state: Mapped[ChannelState | None] = mapped_column(String(16))
    to_state: Mapped[ChannelState] = mapped_column(String(16), nullable=False)
    changed_by: Mapped[UUID | None] = mapped_column(PgUUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"))
    changed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=text("now()"))
    reason: Mapped[str | None] = mapped_column(Text)

    channel: Mapped[Channel] = relationship(back_populates="history")

    __table_args__ = (
        Index("idx_channel_state_history", "channel_code", "changed_at"),
    )
```

### 7.6 Costs — `app/db/models/costs.py`

```python
from __future__ import annotations
from datetime import datetime
from decimal import Decimal
from uuid import UUID
from sqlalchemy import (
    CheckConstraint, Computed, DateTime, ForeignKey, Index, Numeric, String,
    Text, text,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID as PgUUID
from sqlalchemy.orm import Mapped, mapped_column
from app.db.base import Base
from app.db.enums import CostStatus, Scheme
from app.db.mixins import UuidPkMixin


class Cost(UuidPkMixin, Base):
    __tablename__ = "costs"

    sku: Mapped[str] = mapped_column(Text, ForeignKey("products.sku"), nullable=False)
    scheme: Mapped[Scheme] = mapped_column(String(32), nullable=False)
    supplier_code: Mapped[str] = mapped_column(Text, ForeignKey("suppliers.code"), nullable=False)

    fob: Mapped[Decimal] = mapped_column(Numeric(18, 4), nullable=False, server_default=text("0"))
    freight: Mapped[Decimal] = mapped_column(Numeric(18, 4), nullable=False, server_default=text("0"))
    customs: Mapped[Decimal] = mapped_column(Numeric(18, 4), nullable=False, server_default=text("0"))
    fba_fees: Mapped[Decimal] = mapped_column(Numeric(18, 4), nullable=False, server_default=text("0"))
    fbm_fees: Mapped[Decimal] = mapped_column(Numeric(18, 4), nullable=False, server_default=text("0"))
    payment_fees: Mapped[Decimal] = mapped_column(Numeric(18, 4), nullable=False, server_default=text("0"))
    marketing_fees: Mapped[Decimal] = mapped_column(Numeric(18, 4), nullable=False, server_default=text("0"))
    other_fees: Mapped[dict] = mapped_column(JSONB, nullable=False, server_default=text("'{}'::jsonb"))

    # Generated column STORED
    total: Mapped[Decimal] = mapped_column(
        Numeric(18, 4),
        Computed("fob + freight + customs + fba_fees + fbm_fees + payment_fees + marketing_fees", persisted=True),
        nullable=False,
    )

    currency: Mapped[str] = mapped_column(String(3), ForeignKey("currencies.code"), nullable=False)

    fx_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    fx_rate_to_base: Mapped[Decimal] = mapped_column(Numeric(18, 8), nullable=False)
    total_in_base: Mapped[Decimal] = mapped_column(Numeric(18, 4), nullable=False)

    effective_from: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    effective_to: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    status: Mapped[CostStatus] = mapped_column(String(16), nullable=False, server_default=text("'draft'"))

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=text("now()"))
    created_by: Mapped[UUID | None] = mapped_column(PgUUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"))
    approved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    approved_by: Mapped[UUID | None] = mapped_column(PgUUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"))

    __table_args__ = (
        CheckConstraint("effective_to IS NULL OR effective_to > effective_from", name="ck_costs_period"),
        Index("idx_costs_sku_scheme", "sku", "scheme", "effective_from"),
        Index("idx_costs_supplier", "supplier_code", "effective_from"),
    )
```

### 7.7 Prices — `app/db/models/prices.py`

```python
from __future__ import annotations
from datetime import datetime
from decimal import Decimal
from uuid import UUID
from sqlalchemy import (
    CheckConstraint, DateTime, ForeignKey, Index, Integer, Numeric, String,
    Text, text,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID as PgUUID
from sqlalchemy.orm import Mapped, mapped_column
from app.db.base import Base
from app.db.enums import PriceState, Scheme
from app.db.mixins import UuidPkMixin


class Price(UuidPkMixin, Base):
    __tablename__ = "prices"

    sku: Mapped[str] = mapped_column(Text, ForeignKey("products.sku"), nullable=False)
    channel_code: Mapped[str] = mapped_column(Text, ForeignKey("channels.code"), nullable=False)
    scheme: Mapped[Scheme] = mapped_column(String(32), nullable=False)

    amount: Mapped[Decimal] = mapped_column(Numeric(18, 4), nullable=False)
    currency: Mapped[str] = mapped_column(String(3), ForeignKey("currencies.code"), nullable=False)
    pvp_min: Mapped[Decimal | None] = mapped_column(Numeric(18, 4))
    margin_pct: Mapped[Decimal | None] = mapped_column(Numeric(8, 4))
    rule_applied: Mapped[str | None] = mapped_column(Text)
    breakdown: Mapped[dict | None] = mapped_column(JSONB)
    alerts: Mapped[dict | None] = mapped_column(JSONB)

    fx_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    fx_rate_to_base: Mapped[Decimal] = mapped_column(Numeric(18, 8), nullable=False)
    amount_in_base: Mapped[Decimal] = mapped_column(Numeric(18, 4), nullable=False)

    status: Mapped[PriceState] = mapped_column(String(32), nullable=False, server_default=text("'draft'"))
    auto_approve_reason: Mapped[dict | None] = mapped_column(JSONB)
    rejection_reason: Mapped[str | None] = mapped_column(Text)

    proposed_by: Mapped[UUID | None] = mapped_column(PgUUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"))
    proposed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    approved_by: Mapped[UUID | None] = mapped_column(PgUUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"))
    approved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    exported_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    supersedes_id: Mapped[UUID | None] = mapped_column(PgUUID(as_uuid=True), ForeignKey("prices.id", ondelete="SET NULL"))
    supersedes_chain: Mapped[int] = mapped_column(Integer, nullable=False, server_default=text("0"))

    valid_from: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=text("now()"))
    valid_to: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=text("now()"))
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=text("now()"), onupdate=text("now()"))

    __table_args__ = (
        CheckConstraint("amount >= 0", name="ck_prices_amount_positive"),
        CheckConstraint("valid_to IS NULL OR valid_to > valid_from", name="ck_prices_period"),
        Index("idx_prices_sku_channel_scheme", "sku", "channel_code", "scheme", "valid_from"),
        Index("idx_prices_status", "status",
              postgresql_where=text("status IN ('pending_review','draft','revised')")),
    )
```

### 7.8 Exception rules — `app/db/models/exception_rules.py`

```python
from __future__ import annotations
from datetime import datetime
from uuid import UUID
from sqlalchemy import (
    Boolean, CheckConstraint, DateTime, ForeignKey, String, Text, text,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID as PgUUID
from sqlalchemy.orm import Mapped, mapped_column
from app.db.base import Base
from app.db.enums import Scheme


class ExceptionRule(Base):
    __tablename__ = "exception_rules"

    code: Mapped[str] = mapped_column(Text, primary_key=True)
    name: Mapped[str] = mapped_column(Text, nullable=False)
    scope: Mapped[str] = mapped_column(Text, nullable=False)
    channel_code: Mapped[str | None] = mapped_column(Text, ForeignKey("channels.code"))
    scheme: Mapped[Scheme | None] = mapped_column(String(32))
    params: Mapped[dict] = mapped_column(JSONB, nullable=False, server_default=text("'{}'::jsonb"))
    enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default=text("true"))
    updated_by: Mapped[UUID | None] = mapped_column(PgUUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"))
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=text("now()"), onupdate=text("now()"))

    __table_args__ = (
        CheckConstraint(
            "scope IN ('global','per_channel','per_scheme','per_channel_scheme')",
            name="ck_exception_rules_scope",
        ),
    )
```

### 7.9 Imports — `app/db/models/imports.py`

```python
from __future__ import annotations
from datetime import datetime
from uuid import UUID
from sqlalchemy import (
    BigInteger, DateTime, ForeignKey, Index, Integer, String, Text, text,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID as PgUUID
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.db.base import Base
from app.db.enums import ImportStatus, ImportType
from app.db.mixins import UuidPkMixin


class ImportBatch(UuidPkMixin, Base):
    """Mapea a tabla `import_runs` (DDL arquitectura). Renombrado en Python por
    claridad con OpenAPI; `__tablename__` mantiene el nombre real Postgres."""
    __tablename__ = "import_runs"

    type: Mapped[ImportType] = mapped_column(String(32), nullable=False)
    file_url: Mapped[str] = mapped_column(Text, nullable=False)
    file_hash_sha256: Mapped[str] = mapped_column(Text, nullable=False)
    idempotency_key: Mapped[str] = mapped_column(Text, unique=True, nullable=False)
    uploaded_by: Mapped[UUID | None] = mapped_column(PgUUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"))
    status: Mapped[ImportStatus] = mapped_column(String(32), nullable=False, server_default=text("'queued'"))
    preview: Mapped[dict | None] = mapped_column(JSONB)
    summary: Mapped[dict | None] = mapped_column(JSONB)
    error_log: Mapped[dict | None] = mapped_column(JSONB)
    applied_by: Mapped[UUID | None] = mapped_column(PgUUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"))
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=text("now()"))
    preview_ready_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    applied_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    rows: Mapped[list["ImportError"]] = relationship(back_populates="run", cascade="all, delete-orphan")

    __table_args__ = (
        Index("idx_import_runs_type_status", "type", "status", "started_at"),
    )


class ImportError(Base):
    """Mapea a `import_run_rows`. Una fila por entidad procesada."""
    __tablename__ = "import_run_rows"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    run_id: Mapped[UUID] = mapped_column(PgUUID(as_uuid=True), ForeignKey("import_runs.id", ondelete="CASCADE"), nullable=False)
    row_index: Mapped[int] = mapped_column(Integer, nullable=False)
    entity_type: Mapped[str] = mapped_column(Text, nullable=False)
    entity_id: Mapped[str | None] = mapped_column(Text)
    action: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[str] = mapped_column(Text, nullable=False)
    error: Mapped[str | None] = mapped_column(Text)
    data: Mapped[dict | None] = mapped_column(JSONB)

    run: Mapped[ImportBatch] = relationship(back_populates="rows")

    __table_args__ = (
        Index("idx_import_run_rows_run", "run_id", "row_index"),
    )
```

### 7.10 Jobs — `app/db/models/jobs.py`

```python
from __future__ import annotations
from datetime import datetime
from uuid import UUID
from sqlalchemy import (
    Boolean, CheckConstraint, DateTime, ForeignKey, Index, Integer, String,
    Text, text,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID as PgUUID
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.db.base import Base
from app.db.enums import JobOwner, JobStatus, ScheduleType
from app.db.mixins import UuidPkMixin


class JobDefinition(UuidPkMixin, Base):
    __tablename__ = "job_definitions"

    code: Mapped[str] = mapped_column(Text, unique=True, nullable=False)
    task_name: Mapped[str] = mapped_column(Text, nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    owner: Mapped[JobOwner] = mapped_column(String(16), nullable=False, server_default=text("'infra'"))
    schedule_type: Mapped[ScheduleType] = mapped_column(String(16), nullable=False)
    cron_expression: Mapped[str | None] = mapped_column(Text)
    interval_seconds: Mapped[int | None] = mapped_column(Integer)
    timezone: Mapped[str] = mapped_column(Text, nullable=False, server_default=text("'Asia/Dubai'"))
    queue: Mapped[str] = mapped_column(Text, nullable=False, server_default=text("'default'"))
    args: Mapped[list] = mapped_column(JSONB, nullable=False, server_default=text("'[]'::jsonb"))
    kwargs: Mapped[dict] = mapped_column(JSONB, nullable=False, server_default=text("'{}'::jsonb"))
    enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default=text("true"))

    last_run_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    last_status: Mapped[JobStatus | None] = mapped_column(String(16))
    last_error: Mapped[str | None] = mapped_column(Text)
    last_celery_task_id: Mapped[str | None] = mapped_column(Text)

    edited_by: Mapped[UUID | None] = mapped_column(PgUUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=text("now()"))
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=text("now()"), onupdate=text("now()"))

    runs: Mapped[list["JobRun"]] = relationship(back_populates="definition", cascade="all, delete-orphan")

    __table_args__ = (
        CheckConstraint(
            "(schedule_type='cron' AND cron_expression IS NOT NULL) OR "
            "(schedule_type='interval' AND interval_seconds IS NOT NULL)",
            name="ck_job_schedule_complete",
        ),
        Index("idx_jobs_enabled", "enabled", postgresql_where=text("enabled = true")),
    )


class JobRun(Base):
    __tablename__ = "job_runs"

    run_id: Mapped[UUID] = mapped_column(PgUUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()"))
    job_id: Mapped[UUID] = mapped_column(PgUUID(as_uuid=True), ForeignKey("job_definitions.id", ondelete="CASCADE"), nullable=False)
    job_code: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[JobStatus] = mapped_column(String(16), nullable=False, server_default=text("'idle'"))
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    retries: Mapped[int] = mapped_column(Integer, nullable=False, server_default=text("0"))
    celery_task_id: Mapped[str | None] = mapped_column(Text)
    result: Mapped[dict | None] = mapped_column(JSONB)
    error: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=text("now()"))
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=text("now()"), onupdate=text("now()"))

    definition: Mapped[JobDefinition] = relationship(back_populates="runs")

    __table_args__ = (
        Index("idx_job_runs_job_started", "job_id", "started_at"),
        Index("idx_job_runs_status", "status",
              postgresql_where=text("status IN ('idle','running')")),
    )
```

### 7.11 Audit — `app/db/models/audit.py`

```python
"""AuditEvent particionada por mes (PARTITION BY RANGE on occurred_at).

⚠ El particionamiento se gestiona via DDL crudo en una migración Alembic
posterior (alembic/versions/XXXX_audit_partitions.py) usando `op.execute(...)`.
SQLAlchemy soporta `postgresql_partition_by` declarativo desde 2.0.
"""
from __future__ import annotations
from datetime import datetime
from uuid import UUID
from sqlalchemy import (
    BigInteger, DateTime, Index, PrimaryKeyConstraint, Text, text,
)
from sqlalchemy.dialects.postgresql import INET, JSONB, UUID as PgUUID
from sqlalchemy.orm import Mapped, mapped_column
from app.db.base import Base


class AuditEvent(Base):
    __tablename__ = "audit_events"

    # PK compuesto requerido para partitioning by occurred_at
    id: Mapped[int] = mapped_column(BigInteger, autoincrement=True, nullable=False)
    occurred_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=text("now()"))
    actor_id: Mapped[UUID | None] = mapped_column(PgUUID(as_uuid=True))
    actor_email: Mapped[str | None] = mapped_column(Text)
    actor_role: Mapped[str | None] = mapped_column(Text)
    entity_type: Mapped[str] = mapped_column(Text, nullable=False)
    entity_id: Mapped[str] = mapped_column(Text, nullable=False)
    action: Mapped[str] = mapped_column(Text, nullable=False)
    before: Mapped[dict | None] = mapped_column(JSONB)
    after: Mapped[dict | None] = mapped_column(JSONB)
    diff: Mapped[dict | None] = mapped_column(JSONB)
    reason: Mapped[str | None] = mapped_column(Text)
    rules_evaluated: Mapped[dict | None] = mapped_column(JSONB)
    request_id: Mapped[UUID | None] = mapped_column(PgUUID(as_uuid=True))
    ip: Mapped[str | None] = mapped_column(INET)
    user_agent: Mapped[str | None] = mapped_column(Text)

    __table_args__ = (
        PrimaryKeyConstraint("id", "occurred_at", name="pk_audit_events"),
        Index("idx_audit_entity", "entity_type", "entity_id", "occurred_at"),
        Index("idx_audit_actor", "actor_id", "occurred_at"),
        Index("idx_audit_action", "action", "occurred_at"),
        Index("idx_audit_request", "request_id"),
        {"postgresql_partition_by": "RANGE (occurred_at)"},
    )
```

### 7.12 Material compatibility — `app/db/models/material_compat.py`

```python
from __future__ import annotations
from datetime import datetime
from sqlalchemy import BigInteger, DateTime, Index, Integer, String, Text, text
from sqlalchemy.orm import Mapped, mapped_column
from app.db.base import Base
from app.db.enums import CompatT


class MaterialCompatibility(Base):
    __tablename__ = "material_compatibilities"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    fluid: Mapped[str] = mapped_column(Text, nullable=False)
    temperature_c: Mapped[int | None] = mapped_column(Integer)
    laton: Mapped[CompatT | None] = mapped_column(String(16))
    acero_carbono: Mapped[CompatT | None] = mapped_column(String(16))
    fundicion: Mapped[CompatT | None] = mapped_column(String(16))
    ss304: Mapped[CompatT | None] = mapped_column(String(16))
    ss316: Mapped[CompatT | None] = mapped_column(String(16))
    epdm: Mapped[CompatT | None] = mapped_column(String(16))
    nbr: Mapped[CompatT | None] = mapped_column(String(16))
    fkm: Mapped[CompatT | None] = mapped_column(String(16))
    ptfe: Mapped[CompatT | None] = mapped_column(String(16))
    rptfe_fg15: Mapped[CompatT | None] = mapped_column(String(16))
    rptfe_gr15: Mapped[CompatT | None] = mapped_column(String(16))
    source_row: Mapped[int | None] = mapped_column(Integer)
    source_file: Mapped[str] = mapped_column(
        Text, nullable=False,
        server_default=text("'Copia de Compatibilidad de Materiales MT V4.xlsx'"),
    )
    imported_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=text("now()"))

    __table_args__ = (
        Index("idx_compat_fluid", "fluid"),
    )
```

### 7.13 Knowledge Base — `app/db/models/kb.py`

```python
"""KbSource + KbChunk + KbReference. Indexación activa Fase 1.5+."""
from __future__ import annotations
from datetime import datetime
from uuid import UUID
from sqlalchemy import (
    Boolean, DateTime, ForeignKey, Index, Integer, Text, text,
)
from sqlalchemy.dialects.postgresql import ARRAY, JSONB, UUID as PgUUID
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.db.base import Base
from app.db.mixins import UuidPkMixin

try:
    from pgvector.sqlalchemy import Vector  # type: ignore
except ImportError:
    Vector = None  # type: ignore


class KbSource(UuidPkMixin, Base):
    __tablename__ = "kb_sources"

    type: Mapped[str] = mapped_column(Text, nullable=False)
    code: Mapped[str | None] = mapped_column(Text)
    title: Mapped[str] = mapped_column(Text, nullable=False)
    storage_path: Mapped[str] = mapped_column(Text, unique=True, nullable=False)
    language: Mapped[str] = mapped_column(Text, nullable=False, server_default=text("'en'"))
    version: Mapped[str | None] = mapped_column(Text)
    sku_links: Mapped[list[str]] = mapped_column(ARRAY(Text), nullable=False, server_default=text("'{}'::text[]"))
    indexed: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default=text("false"))
    metadata_: Mapped[dict] = mapped_column("metadata", JSONB, nullable=False, server_default=text("'{}'::jsonb"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=text("now()"))
    created_by: Mapped[UUID | None] = mapped_column(PgUUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"))

    chunks: Mapped[list["KbChunk"]] = relationship(back_populates="source", cascade="all, delete-orphan")
    references: Mapped[list["KbReference"]] = relationship(back_populates="source", cascade="all, delete-orphan")


class KbChunk(UuidPkMixin, Base):
    __tablename__ = "kb_chunks"

    source_id: Mapped[UUID] = mapped_column(PgUUID(as_uuid=True), ForeignKey("kb_sources.id", ondelete="CASCADE"), nullable=False)
    chunk_index: Mapped[int] = mapped_column(Integer, nullable=False)
    text: Mapped[str] = mapped_column(Text, nullable=False)
    page: Mapped[int | None] = mapped_column(Integer)
    metadata_: Mapped[dict] = mapped_column("metadata", JSONB, nullable=False, server_default=text("'{}'::jsonb"))
    if Vector is not None:
        embedding = mapped_column(Vector(1536), nullable=True)
    else:
        embedding: Mapped[list[float] | None] = mapped_column(ARRAY(Text), nullable=True)
    embedding_model: Mapped[str | None] = mapped_column(Text)
    embedding_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    source: Mapped[KbSource] = relationship(back_populates="chunks")

    __table_args__ = (
        Index("idx_kb_chunks_source", "source_id", "chunk_index", unique=True),
        # HNSW Fase 1.5+:
        # Index("idx_kb_chunks_embedding", "embedding", postgresql_using="hnsw",
        #       postgresql_ops={"embedding": "vector_cosine_ops"}),
    )


class KbReference(Base):
    __tablename__ = "kb_references"

    source_id: Mapped[UUID] = mapped_column(PgUUID(as_uuid=True), ForeignKey("kb_sources.id", ondelete="CASCADE"), primary_key=True)
    sku: Mapped[str] = mapped_column(Text, ForeignKey("products.sku", ondelete="CASCADE"), primary_key=True)
    role: Mapped[str] = mapped_column(Text, nullable=False)  # 'datasheet','manual',...
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=text("now()"))

    source: Mapped[KbSource] = relationship(back_populates="references")
```

### 7.14 Comparator — `app/db/models/comparator.py`

```python
"""CompetitorListing + MatchCandidate + MatchDecision (research workstream §17)."""
from __future__ import annotations
from datetime import datetime
from decimal import Decimal
from uuid import UUID
from sqlalchemy import (
    DateTime, ForeignKey, Index, Numeric, String, Text, text,
)
from sqlalchemy.dialects.postgresql import ARRAY, JSONB, UUID as PgUUID
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.db.base import Base
from app.db.enums import MatchStatus
from app.db.mixins import UuidPkMixin

try:
    from pgvector.sqlalchemy import Vector  # type: ignore
except ImportError:
    Vector = None  # type: ignore


class CompetitorListing(UuidPkMixin, Base):
    __tablename__ = "competitor_listings"

    source: Mapped[str] = mapped_column(Text, nullable=False)
    source_listing_id: Mapped[str | None] = mapped_column(Text)
    url: Mapped[str] = mapped_column(Text, nullable=False)
    title: Mapped[str | None] = mapped_column(Text)
    description: Mapped[str | None] = mapped_column(Text)
    price_amount: Mapped[Decimal | None] = mapped_column(Numeric(18, 4))
    price_currency: Mapped[str | None] = mapped_column(String(3))
    images: Mapped[list[str]] = mapped_column(ARRAY(Text), nullable=False, server_default=text("'{}'::text[]"))
    raw: Mapped[dict] = mapped_column(JSONB, nullable=False, server_default=text("'{}'::jsonb"))
    if Vector is not None:
        embedding = mapped_column(Vector(1536), nullable=True)
    else:
        embedding: Mapped[list[float] | None] = mapped_column(ARRAY(Text), nullable=True)
    reverse_image_hits: Mapped[dict | None] = mapped_column(JSONB)
    reverse_image_searched_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    reverse_image_provider: Mapped[str | None] = mapped_column(Text)
    fetched_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=text("now()"))

    __table_args__ = (
        Index("idx_cl_source", "source", "source_listing_id", unique=True),
        Index("idx_cl_url", "url"),
    )


class MatchCandidate(UuidPkMixin, Base):
    __tablename__ = "match_candidates"

    sku: Mapped[str] = mapped_column(Text, ForeignKey("products.sku", ondelete="CASCADE"), nullable=False)
    listing_id: Mapped[UUID] = mapped_column(PgUUID(as_uuid=True), ForeignKey("competitor_listings.id", ondelete="CASCADE"), nullable=False)
    score_image: Mapped[Decimal | None] = mapped_column(Numeric(8, 6))
    score_text: Mapped[Decimal | None] = mapped_column(Numeric(8, 6))
    score_specs: Mapped[Decimal | None] = mapped_column(Numeric(8, 6))
    score_combined: Mapped[Decimal] = mapped_column(Numeric(8, 6), nullable=False)
    threshold_band: Mapped[str] = mapped_column(Text, nullable=False)  # auto_match | human_queue | discard
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=text("now()"))

    __table_args__ = (
        Index("idx_match_candidates_sku", "sku", "score_combined"),
    )


class MatchDecision(UuidPkMixin, Base):
    __tablename__ = "match_decisions"

    sku: Mapped[str] = mapped_column(Text, ForeignKey("products.sku", ondelete="CASCADE"), nullable=False)
    listing_id: Mapped[UUID] = mapped_column(PgUUID(as_uuid=True), ForeignKey("competitor_listings.id", ondelete="CASCADE"), nullable=False)
    verdict: Mapped[str] = mapped_column(Text, nullable=False)              # match | no_match | uncertain
    decided_by: Mapped[str] = mapped_column(Text, nullable=False)            # auto | human | judge
    decided_by_user_id: Mapped[UUID | None] = mapped_column(PgUUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"))
    score_combined: Mapped[Decimal | None] = mapped_column(Numeric(8, 6))
    judge_rationale: Mapped[str | None] = mapped_column(Text)
    judge_image_regions: Mapped[list[dict] | None] = mapped_column(JSONB)
    deal_breakers_triggered: Mapped[list[str]] = mapped_column(ARRAY(Text), nullable=False, server_default=text("'{}'::text[]"))
    decided_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=text("now()"))

    __table_args__ = (
        Index("idx_match_decisions_sku", "sku", "decided_at"),
        Index("idx_match_decisions_listing", "listing_id"),
    )
```

## 8. Repositorios — `app/db/repositories/`

### 8.1 `products.py`

```python
"""ProductRepository: encapsula queries SQLAlchemy 2.0 select."""
from __future__ import annotations
from collections.abc import Sequence
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload
from app.db.models.products import Product, ProductTranslation, ProductImage
from app.db.enums import DataQuality


class ProductRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def get_by_sku(self, sku: str, *, with_translations: bool = False) -> Product | None:
        stmt = select(Product).where(Product.sku == sku)
        if with_translations:
            stmt = stmt.options(
                selectinload(Product.translations),
                selectinload(Product.images),
            )
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def list(
        self,
        *,
        family: str | None = None,
        data_quality: DataQuality | None = None,
        active: bool | None = True,
        search: str | None = None,
        cursor: str | None = None,
        limit: int = 50,
    ) -> Sequence[Product]:
        stmt = select(Product)
        if family:
            stmt = stmt.where(Product.family == family)
        if data_quality:
            stmt = stmt.where(Product.data_quality == data_quality)
        if active is not None:
            stmt = stmt.where(Product.active == active)
        if search:
            stmt = stmt.where(Product.name_en.op("%")(search))  # pg_trgm similarity operator
        if cursor:
            stmt = stmt.where(Product.sku > cursor)
        stmt = stmt.order_by(Product.sku.asc()).limit(limit)
        result = await self.session.execute(stmt)
        return result.scalars().all()

    async def count_by_quality(self) -> dict[str, int]:
        stmt = (
            select(Product.data_quality, func.count())
            .group_by(Product.data_quality)
        )
        result = await self.session.execute(stmt)
        return {row[0]: row[1] for row in result.all()}
```

### 8.2 `prices.py`

```python
"""PriceRepository."""
from __future__ import annotations
from collections.abc import Sequence
from datetime import datetime
from uuid import UUID
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from app.db.enums import PriceState, Scheme
from app.db.models.prices import Price


class PriceRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def by_id(self, price_id: UUID) -> Price | None:
        return await self.session.get(Price, price_id)

    async def list_by_sku(
        self,
        sku: str,
        *,
        channel_code: str | None = None,
        scheme: Scheme | None = None,
        as_of: datetime | None = None,
    ) -> Sequence[Price]:
        stmt = select(Price).where(Price.sku == sku)
        if channel_code:
            stmt = stmt.where(Price.channel_code == channel_code)
        if scheme:
            stmt = stmt.where(Price.scheme == scheme)
        if as_of:
            stmt = stmt.where(
                Price.valid_from <= as_of,
                (Price.valid_to.is_(None)) | (Price.valid_to > as_of),
            )
        stmt = stmt.order_by(Price.valid_from.desc())
        result = await self.session.execute(stmt)
        return result.scalars().all()

    async def queue_pending_for_manager(
        self, *, cursor: UUID | None = None, limit: int = 50
    ) -> Sequence[Price]:
        stmt = select(Price).where(Price.status == PriceState.PENDING_REVIEW)
        if cursor:
            stmt = stmt.where(Price.id > cursor)
        stmt = stmt.order_by(Price.id.asc()).limit(limit)
        result = await self.session.execute(stmt)
        return result.scalars().all()
```

## 9. `app/db/models/__init__.py`

```python
"""Re-export todos los modelos para que Alembic los descubra."""
from app.db.models.users import User, Role, Permission, RolePermission
from app.db.models.products import Product, ProductTranslation, ProductImage
from app.db.models.suppliers import Supplier
from app.db.models.currencies import Currency, FxRate
from app.db.models.channels import Channel, Scheme_, ChannelStateHistory
from app.db.models.costs import Cost
from app.db.models.prices import Price
from app.db.models.exception_rules import ExceptionRule
from app.db.models.imports import ImportBatch, ImportError
from app.db.models.jobs import JobDefinition, JobRun
from app.db.models.audit import AuditEvent
from app.db.models.material_compat import MaterialCompatibility
from app.db.models.kb import KbSource, KbChunk, KbReference
from app.db.models.comparator import CompetitorListing, MatchCandidate, MatchDecision

__all__ = [
    "User", "Role", "Permission", "RolePermission",
    "Product", "ProductTranslation", "ProductImage",
    "Supplier", "Currency", "FxRate",
    "Channel", "Scheme_", "ChannelStateHistory",
    "Cost", "Price", "ExceptionRule",
    "ImportBatch", "ImportError",
    "JobDefinition", "JobRun",
    "AuditEvent", "MaterialCompatibility",
    "KbSource", "KbChunk", "KbReference",
    "CompetitorListing", "MatchCandidate", "MatchDecision",
]
```

## 10. `alembic/env.py` — instrucciones

```python
"""Async Alembic env.py para autogenerate."""
from logging.config import fileConfig
import asyncio
from alembic import context
from sqlalchemy.ext.asyncio import async_engine_from_config
from sqlalchemy import pool

from app.db.base import Base
import app.db.models  # noqa: F401  -- importa todos los modelos

config = context.config
fileConfig(config.config_file_name)
target_metadata = Base.metadata

def run_migrations_online() -> None:
    connectable = async_engine_from_config(
        config.get_section(config.config_ini_section),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )

    async def _run() -> None:
        async with connectable.connect() as conn:
            await conn.run_sync(_do)

    def _do(connection):
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
            include_schemas=False,
            compare_type=True,
            compare_server_default=True,
        )
        with context.begin_transaction():
            context.run_migrations()

    asyncio.run(_run())

run_migrations_online()
```

### Generar migración inicial

```bash
# Pre-requisito: tener engine apuntando a Postgres limpio (Supabase shadow DB recomendado).
alembic revision --autogenerate -m "fase1_initial_schema"
alembic upgrade head
```

> **Tras autogenerate**, añadir manualmente las migraciones data-only que no se infieren del modelo: (1) `CREATE EXTENSION` (pgcrypto, pg_trgm, vector, citext, pg_uuidv7), (2) `CREATE TYPE *_t AS ENUM` (Alembic los genera como `String` en este modelo — ver §12 nota 2), (3) particiones mensuales de `audit_events`, (4) trigger `audit_row_change`, (5) RLS policies, (6) seeds (currencies, schemes, channels, exception_rules, job_definitions, roles+permissions).

## 11. Migraciones manuales necesarias (post-autogenerate)

| Archivo | Contenido |
|---|---|
| `XXXX_extensions_and_enums.py` | `CREATE EXTENSION` + `CREATE TYPE *_t AS ENUM (...)` |
| `XXXX_audit_partitions.py` | Convertir `audit_events` a particionada (drop+recreate o `ATTACH PARTITION`) + crear N particiones futuras |
| `XXXX_audit_trigger.py` | Función `audit_row_change()` + triggers en tablas críticas |
| `XXXX_rls_policies.py` | RLS enable + policies por tabla (ver `mt-users-module-design.md §5.1.6`) |
| `XXXX_seeds_fase1.py` | INSERT en currencies, schemes, channels, exception_rules, job_definitions, roles, permissions, role_permissions |

## 12. Inconsistencias resueltas

### 12.1 `users` vs `profiles`
**Conflicto.** `mt-users-module-design.md` §5.1.1 define la tabla aplicativa como `public.profiles` (1:1 con `auth.users`), mientras que `architecture-mt-pricing-mdm-phase1.md` §8.2 define `public.users`.

**Decisión.** Usar `public.users` (architecture). Razón: (a) el resto del DDL referencia `users(id)` en FKs (audit_events.actor_id, costs.created_by, prices.proposed_by, ...); (b) renombrar a profiles obligaría a renombrar 14 FKs; (c) la 1:1 con `auth.users` se mantiene via `users.id = auth.users.id` y trigger `on_auth_user_created`.

**Impacto.** El módulo de usuarios usa `public.users` en SQLAlchemy; la integración con Supabase Auth se mantiene idéntica al diseño v1.1 (supabase-py `auth.admin.*`).

### 12.2 `roles.code` (TEXT) vs `roles.id` (UUID)
**Conflicto.** Architecture §8.2 usa `roles.code` como PK TEXT; users-module-design §5.1.1 usa `roles.id` UUID + `code` único.

**Decisión.** Modelo híbrido: `roles.id` UUID PK + `roles.code` UNIQUE. `users.role_id` → `roles.id`. Razón: (a) UUID es más estable para FK desde JWT cache; (b) `code` se mantiene UNIQUE para semántica humana en API y RLS (`auth.jwt() ->> 'role'` matchea código). FK `user_roles.role_code` mencionada en architecture se reemplaza por `users.role_id` (relación 1:N rol→usuario, no muchos-a-muchos — Fase 1 cada usuario tiene un rol único, ver users-module-design §5.1.1).

**Impacto.** `user_roles` association table NO se materializa en Fase 1 (un usuario = un rol). Si Fase 2+ necesita multi-rol, se añade entonces.

### 12.3 `costs` columnas — `breakdown` JSONB vs columnas explícitas
**Conflicto.** PRD §10.1 modela costs con `breakdown JSONB`; architecture §8.6 modela cada componente como columna NUMERIC explícita más `total` GENERATED.

**Decisión.** Adoptar architecture §8.6 (columnas explícitas + `total` GENERATED). Razón: (a) permite CHECK constraints, indices y queries SQL puras (`WHERE fba_fees > 10`); (b) el DDL ya está compilado en architecture v1.4; (c) `other_fees JSONB` mantiene extensibilidad para fees ad-hoc; (d) OpenAPI expone `CostBreakdown` con los mismos campos para consistencia.

**Impacto.** El DTO `CostBreakdown` en OpenAPI tiene los mismos campos planos que las columnas SQLAlchemy. El servicio `costs_svc` puede aceptar `CostBreakdownPayload` (Pydantic) y mapear directo a las columnas.

### 12.4 (bonus) `prices.amount` vs `price_aed`
**Conflicto.** PRD §10.1 usa `price_aed` (asume base AED hard-coded); architecture §8.7 usa `amount + currency + amount_in_base` para soporte multi-moneda.

**Decisión.** Adoptar architecture (`amount`, `currency`, `amount_in_base` + `fx_rate_to_base`). Razón: AED es la moneda base actual pero el sistema debe estar preparado para canales en USD/SAR.

## 13. TODO / Dudas pendientes

> **TODO único significativo: enum types Postgres vs `String` en SQLAlchemy.**
> Los modelos arriba usan `Mapped[Enum] = mapped_column(String(N), ...)` (varchars con CHECK lógico via Pydantic). Razón: SQLAlchemy `Enum(MyPyEnum, name="...", create_type=True)` genera `CREATE TYPE ... AS ENUM` automáticamente, pero (a) Alembic autogenerate no detecta cambios de valores de enum (requiere `op.execute("ALTER TYPE ... ADD VALUE")` manual); (b) si dos modelos importan el mismo enum SQLAlchemy refleja `create_type=True` dos veces y Alembic falla con "type already exists". La opción "limpia" es declararlos una vez con `Enum(..., create_type=False)` y crearlos en una migración manual de extensiones, pero pierde validación tipada en el ORM.
>
> **Dejado pendiente:** decidir antes del Sprint 1 si: (a) mantener `String + CHECK + Pydantic enum`, (b) usar `Enum(create_type=False)` con migración manual de tipos, o (c) usar `pg_enum_t` como TIPO DDL pero `Mapped[str]` en Python (compromise). El backend arranca con (a) — si el equipo decide (b), el cambio es local al `Mapped[T]` y no toca migraciones de columnas.
